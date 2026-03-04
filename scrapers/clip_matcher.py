"""
CLIP-based Image Matcher — local, unlimited reverse image search.

Uses OpenCLIP to generate image embeddings, then matches against a local
reference database of Grailed sold items. Combined with smart title parsing
for a hybrid text+image identification pipeline.

No API keys. No rate limits. Runs locally on Apple Silicon.

Usage:
    from scrapers.clip_matcher import CLIPMatcher

    matcher = CLIPMatcher()

    # Build/update reference DB from Grailed sold items
    await matcher.index_sold_items(sold_items)

    # Identify a listing by image + title
    result = await matcher.identify(image_url, title, brand)
    print(result["product_name"], result["confidence"], result["price_range"])
"""

import asyncio
import io
import json
import logging
import os
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple

import httpx
import numpy as np

logger = logging.getLogger("clip_matcher")

# ── Lazy-load heavy deps ────────────────────────────────────────────────────

_clip_model = None
_clip_preprocess = None
_clip_tokenizer = None

def _load_clip():
    """Lazy-load CLIP model (first call takes ~2-3s, then cached)."""
    global _clip_model, _clip_preprocess, _clip_tokenizer
    if _clip_model is not None:
        return _clip_model, _clip_preprocess, _clip_tokenizer

    try:
        import open_clip
        import torch

        # ViT-B/32 is fast and good enough for fashion matching
        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k"
        )
        tokenizer = open_clip.get_tokenizer("ViT-B-32")
        model.eval()

        # Use MPS (Metal) on Apple Silicon if available
        if torch.backends.mps.is_available():
            model = model.to("mps")
            logger.info("CLIP loaded on Apple Silicon (MPS)")
        else:
            logger.info("CLIP loaded on CPU")

        _clip_model = model
        _clip_preprocess = preprocess
        _clip_tokenizer = tokenizer
        return model, preprocess, tokenizer

    except ImportError:
        raise ImportError(
            "open-clip-torch not installed. Run: pip install open-clip-torch torch Pillow"
        )


# ── Reference Database ──────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent / "data"
CLIP_DB_PATH = DATA_DIR / "clip_reference.pkl"

@dataclass
class RefItem:
    """A reference item in the CLIP database."""
    source_id: str
    title: str
    brand: str
    price: float
    url: str
    image_url: str
    embedding: np.ndarray  # CLIP image embedding (512-d)
    season: str = ""
    category: str = ""
    indexed_at: str = ""


class CLIPReferenceDB:
    """Local database of CLIP embeddings for sold items."""

    def __init__(self, path: Path = CLIP_DB_PATH):
        self.path = path
        self.items: List[RefItem] = []
        self._embeddings_matrix: Optional[np.ndarray] = None
        self._dirty = False

    def load(self):
        """Load from disk."""
        if self.path.exists():
            try:
                with open(self.path, "rb") as f:
                    data = pickle.load(f)
                self.items = data.get("items", [])
                self._rebuild_matrix()
                logger.info(f"Loaded {len(self.items)} reference items from {self.path}")
            except Exception as e:
                logger.warning(f"Failed to load CLIP DB: {e}")
                self.items = []

    def save(self):
        """Save to disk."""
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "wb") as f:
            pickle.dump({"items": self.items, "version": 1}, f)
        self._dirty = False
        logger.info(f"Saved {len(self.items)} reference items to {self.path}")

    def add(self, item: RefItem):
        """Add an item (deduplicates by source_id)."""
        # Skip if already indexed
        existing_ids = {i.source_id for i in self.items}
        if item.source_id in existing_ids:
            return
        self.items.append(item)
        self._dirty = True
        self._embeddings_matrix = None  # Invalidate cache

    def _rebuild_matrix(self):
        """Build numpy matrix of all embeddings for fast similarity search."""
        if not self.items:
            self._embeddings_matrix = None
            return
        self._embeddings_matrix = np.stack([i.embedding for i in self.items])
        # Normalize for cosine similarity via dot product
        norms = np.linalg.norm(self._embeddings_matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self._embeddings_matrix = self._embeddings_matrix / norms

    def search(self, query_embedding: np.ndarray, top_k: int = 10, brand_filter: str = "") -> List[Tuple[RefItem, float]]:
        """Find most similar items by cosine similarity."""
        if not self.items or self._embeddings_matrix is None:
            self._rebuild_matrix()
        if self._embeddings_matrix is None or len(self._embeddings_matrix) == 0:
            return []

        # Normalize query
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)

        # Cosine similarity = dot product of normalized vectors
        similarities = self._embeddings_matrix @ query_norm

        # Optional brand filter
        if brand_filter:
            brand_lower = brand_filter.lower()
            for idx, item in enumerate(self.items):
                if brand_lower not in item.brand.lower():
                    similarities[idx] = -1  # Exclude

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            sim = float(similarities[idx])
            if sim < 0.1:  # Skip very low matches
                continue
            results.append((self.items[idx], sim))

        return results

    @property
    def size(self) -> int:
        return len(self.items)


# ── CLIP Matcher ────────────────────────────────────────────────────────────

class CLIPMatcher:
    """
    Hybrid text + image product identifier.

    Strategy:
    1. Parse title to extract brand, model, season, material (fast, handles 80%)
    2. If title is vague, use CLIP image embedding to find visual matches
    3. Combine both signals for final identification
    """

    def __init__(self):
        self.db = CLIPReferenceDB()
        self.db.load()
        self._http: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._http = httpx.AsyncClient(timeout=30, follow_redirects=True)
        return self

    async def __aexit__(self, *args):
        if self._http:
            await self._http.aclose()

    async def _download_image(self, url: str) -> Optional[bytes]:
        """Download image bytes from URL."""
        if not self._http:
            self._http = httpx.AsyncClient(timeout=30, follow_redirects=True)
        try:
            resp = await self._http.get(url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                return resp.content
        except Exception:
            pass
        return None

    def _embed_image(self, image_bytes: bytes) -> Optional[np.ndarray]:
        """Generate CLIP embedding for an image."""
        try:
            import torch
            from PIL import Image

            model, preprocess, _ = _load_clip()
            device = next(model.parameters()).device

            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img_tensor = preprocess(img).unsqueeze(0).to(device)

            with torch.no_grad():
                embedding = model.encode_image(img_tensor)
                embedding = embedding.cpu().numpy().flatten()

            return embedding
        except Exception as e:
            logger.warning(f"CLIP embed failed: {e}")
            return None

    def _embed_text(self, text: str) -> Optional[np.ndarray]:
        """Generate CLIP text embedding."""
        try:
            import torch

            model, _, tokenizer = _load_clip()
            device = next(model.parameters()).device

            tokens = tokenizer([text]).to(device)

            with torch.no_grad():
                embedding = model.encode_text(tokens)
                embedding = embedding.cpu().numpy().flatten()

            return embedding
        except Exception as e:
            logger.warning(f"CLIP text embed failed: {e}")
            return None

    async def index_sold_items(self, sold_items: list, brand: str = ""):
        """
        Add sold items to the reference DB.
        Call this during scraping to build up the reference database over time.
        """
        indexed = 0
        for item in sold_items:
            if not item.images:
                continue
            if not item.price or item.price <= 0:
                continue

            image_bytes = await self._download_image(item.images[0])
            if not image_bytes:
                continue

            embedding = self._embed_image(image_bytes)
            if embedding is None:
                continue

            # Extract season from title
            import re
            season = ""
            season_match = re.search(r'((?:ss|aw|fw|spring|fall|autumn|winter)[/\s.-]?\d{2,4})', item.title.lower())
            if season_match:
                season = season_match.group(1).strip()

            ref = RefItem(
                source_id=item.source_id,
                title=item.title,
                brand=brand or item.brand or "",
                price=item.price,
                url=item.url,
                image_url=item.images[0],
                embedding=embedding,
                season=season,
                indexed_at=datetime.utcnow().isoformat(),
            )
            self.db.add(ref)
            indexed += 1

        if indexed > 0:
            self.db.save()
            logger.info(f"Indexed {indexed} new sold items (DB total: {self.db.size})")

        return indexed

    async def identify(
        self,
        image_url: str,
        title: str,
        brand: str,
        top_k: int = 5,
    ) -> Dict:
        """
        Identify a product using hybrid text + image matching.

        Returns:
            {
                "product_name": str or None,
                "confidence": float (0-1),
                "season": str or None,
                "price_range": (min, max) or None,
                "avg_price": float or None,
                "method": "title_parse" | "clip_image" | "hybrid",
                "matches": [...],
            }
        """
        from .comp_matcher import parse_title, build_search_queries

        # ── Step 1: Title parsing (fast, handles most cases) ────────
        parsed = parse_title(brand, title)
        title_confidence = 0.0
        title_product_name = None

        # Also do our own model extraction (comp_matcher may miss due to regex order)
        import re
        _all_models = [
            "geobasket", "geo basket", "ramones", "ramone", "kiss boot", "creatch",
            "bauhaus", "bela", "pods", "mega lace", "stooges", "intarsia", "dust",
            "memphis", "babel", "sphinx", "cyclops", "island", "sisyphus", "hustler",
            "ozweego", "response trail", "replicant", "cylon", "runner", "orion",
            "virginia creeper", "riot", "tabi", "replica", "gat", "german army",
            "fusion", "paint splatter", "deconstructed", "triple s", "track",
            "speed trainer", "defender", "box logo", "bogo", "astro", "flak", "painter",
        ]
        detected_model = parsed.model
        if not detected_model:
            title_lower = title.lower()
            for m in _all_models:
                if m in title_lower:
                    detected_model = m
                    break

        if detected_model:
            title_product_name = detected_model
            title_confidence = 0.8
            if parsed.sub_brand and detected_model != parsed.sub_brand.lower():
                title_product_name = f"{parsed.sub_brand} {detected_model}"
                title_confidence = 0.9
        elif parsed.sub_brand and parsed.item_type_specific:
            title_product_name = f"{parsed.sub_brand} {parsed.item_type_specific}"
            title_confidence = 0.6
        elif parsed.item_type_specific and parsed.material:
            title_product_name = f"{parsed.material} {parsed.item_type_specific}"
            title_confidence = 0.5
        elif parsed.sub_brand and parsed.key_details:
            title_product_name = f"{parsed.sub_brand} {' '.join(parsed.key_details[:2])}"
            title_confidence = 0.45

        # If title gives us a strong ID (model name found), we might be done
        if title_confidence >= 0.8 and self.db.size == 0:
            return {
                "product_name": title_product_name,
                "confidence": title_confidence,
                "season": parsed.season or None,
                "price_range": None,
                "avg_price": None,
                "method": "title_parse",
                "matches": [],
                "parsed": parsed,
            }

        # ── Step 2: CLIP image matching (for visual confirmation / vague titles) ──
        clip_matches = []
        clip_confidence = 0.0

        if self.db.size > 0 and image_url:
            image_bytes = await self._download_image(image_url)
            if image_bytes:
                embedding = self._embed_image(image_bytes)
                if embedding is not None:
                    raw_matches = self.db.search(
                        embedding, top_k=top_k, brand_filter=brand,
                    )

                    for ref_item, sim in raw_matches:
                        clip_matches.append({
                            "title": ref_item.title,
                            "price": ref_item.price,
                            "similarity": sim,
                            "url": ref_item.url,
                            "season": ref_item.season,
                            "brand": ref_item.brand,
                        })

                    if clip_matches:
                        clip_confidence = clip_matches[0]["similarity"]

        # ── Step 3: Combine signals ─────────────────────────────────
        # Best product name
        product_name = title_product_name
        method = "title_parse"

        if clip_matches and clip_confidence > 0.7:
            # CLIP found a strong match — extract product name from matched title
            best_match = clip_matches[0]
            clip_parsed = parse_title(brand, best_match["title"])
            if clip_parsed.model:
                clip_product = clip_parsed.model
                if clip_parsed.sub_brand:
                    clip_product = f"{clip_parsed.sub_brand} {clip_parsed.model}"

                if title_confidence < 0.6:
                    # Title was vague, trust CLIP
                    product_name = clip_product
                    method = "clip_image"
                else:
                    # Both have info — combine
                    product_name = title_product_name or clip_product
                    method = "hybrid"

        # Overall confidence
        confidence = max(title_confidence, clip_confidence)
        if method == "hybrid":
            confidence = min(1.0, title_confidence * 0.5 + clip_confidence * 0.5 + 0.2)

        # Price range from matches
        prices = [m["price"] for m in clip_matches if m["price"] > 0]
        price_range = (min(prices), max(prices)) if prices else None
        avg_price = sum(prices) / len(prices) if prices else None

        # Season — prefer title-parsed, then from matches
        season = parsed.season
        if not season and clip_matches:
            for m in clip_matches:
                if m.get("season"):
                    season = m["season"]
                    break

        return {
            "product_name": product_name,
            "confidence": confidence,
            "season": season or None,
            "price_range": price_range,
            "avg_price": avg_price,
            "method": method,
            "matches": clip_matches[:5],
            "parsed": parsed,
        }

    async def identify_and_price(
        self,
        image_url: str,
        title: str,
        brand: str,
    ) -> Dict:
        """
        Full pipeline: identify product + get precise Grailed comps.

        Combines CLIP matching with targeted Grailed sold search
        for the most accurate pricing possible.
        """
        # Step 1: Identify the product
        id_result = await self.identify(image_url, title, brand)

        # Step 2: If we got a product name, search Grailed for exact comps
        precise_comps = None
        if id_result["product_name"] and id_result["confidence"] >= 0.5:
            search_query = f"{brand} {id_result['product_name']}"
            if id_result.get("season"):
                search_query += f" {id_result['season']}"

            try:
                from .grailed import GrailedScraper
                async with GrailedScraper() as scraper:
                    sold = await scraper.search_sold(search_query, max_results=10)
                    if sold:
                        sold_prices = [s.price for s in sold if s.price > 0]
                        if sold_prices:
                            precise_comps = {
                                "query": search_query,
                                "count": len(sold_prices),
                                "avg": sum(sold_prices) / len(sold_prices),
                                "min": min(sold_prices),
                                "max": max(sold_prices),
                                "median": sorted(sold_prices)[len(sold_prices) // 2],
                            }

                            # Also index these for future matching
                            await self.index_sold_items(sold, brand=brand)
            except Exception as e:
                logger.warning(f"Grailed comp search failed: {e}")

        id_result["precise_comps"] = precise_comps
        return id_result


# ── Convenience functions ───────────────────────────────────────────────────

async def quick_identify(image_url: str, title: str, brand: str) -> Dict:
    """One-shot identify without managing context."""
    async with CLIPMatcher() as matcher:
        return await matcher.identify_and_price(image_url, title, brand)


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    async def test():
        print("CLIP Matcher Test")
        print("=" * 70)

        matcher = CLIPMatcher()
        async with matcher:
            print(f"Reference DB: {matcher.db.size} items")

            # Test title parsing (always works)
            tests = [
                ("rick owens", "Rick Owens DRKSHDW Geobasket Sneakers Black 42"),
                ("raf simons", "Vintage jacket rare designer"),  # Vague title
                ("maison margiela", "Maison Margiela Tabi Boots White Leather 42"),
                ("balenciaga", "Balenciaga Triple S Black 43"),
            ]

            for brand, title in tests:
                result = await matcher.identify(
                    image_url="",  # No image for test
                    title=title,
                    brand=brand,
                )
                print(f"\n{'─'*50}")
                print(f"📦 {title}")
                print(f"   Product: {result['product_name'] or '???'}")
                print(f"   Confidence: {result['confidence']:.0%}")
                print(f"   Season: {result['season'] or '—'}")
                print(f"   Method: {result['method']}")
                if result.get("price_range"):
                    print(f"   Price range: ${result['price_range'][0]:.0f}-${result['price_range'][1]:.0f}")

    asyncio.run(test())

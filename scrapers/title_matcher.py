"""
Title Matcher — NLP/embedding-based semantic title matching for comp finding.

Goes beyond keyword matching to understand that:
- "Rick Owens DRKSHDW Ramones" ≈ "RO Dark Shadow Canvas High Tops"
- "Margiela Artisanal" ≈ "MMM Line 0" ≈ "Maison Martin Margiela Artisanal"
- "Number Nine AW05" ≈ "Number (N)ine The High Streets"

Uses sentence-transformers for embeddings + alias database for known equivalences.
"""

import os
import re
import sqlite3
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("title_matcher")

DB_PATH = Path(__file__).parent.parent / "data" / "archive.db"

# ══════════════════════════════════════════════════════════════
# ALIAS DATABASE — Known name equivalences in archive fashion
# ══════════════════════════════════════════════════════════════

BRAND_ALIASES: Dict[str, List[str]] = {
    "rick owens": ["ro", "rickowens", "rick owen", "rick o"],
    "rick owens drkshdw": ["drkshdw", "dark shadow", "ro drkshdw", "rick owens dark shadow"],
    "maison margiela": ["mmm", "margiela", "maison martin margiela", "martin margiela"],
    "mm6 maison margiela": ["mm6", "mm6 margiela"],
    "raf simons": ["raf", "rafsimons"],
    "number (n)ine": ["number nine", "numbernine", "n(n)", "number n ine", "number nine x"],
    "undercover": ["undercoverism", "uc", "jun takahashi undercover"],
    "comme des garcons": ["cdg", "comme des garçons", "commes des garcons", "comme de garcon"],
    "comme des garcons homme plus": ["cdg homme plus", "cdg hp", "comme homme plus"],
    "yohji yamamoto": ["yohji", "yamamoto", "yoji yamamoto", "y. yamamoto"],
    "yohji yamamoto pour homme": ["yohji pour homme", "yamamoto pour homme"],
    "helmut lang": ["helmut", "hl"],
    "carol christian poell": ["ccp", "c.c.p.", "c.c.p"],
    "a1923": ["a diciannoveventitre", "a1923"],
    "boris bidjan saberi": ["bbs", "boris bidjan", "11 by bbs"],
    "julius": ["julius_7", "julius 7"],
    "the viridi-anne": ["viridi anne", "tva"],
    "issey miyake": ["issey", "miyake"],
    "issey miyake homme plisse": ["homme plisse", "plisse", "homme plissé"],
    "chrome hearts": ["ch", "chrome heart"],
    "saint laurent": ["slp", "saint laurent paris", "ysl"],
    "dior homme": ["dior men", "dior", "dior hommes"],
    "balenciaga": ["balenci"],
    "supreme": [],
    "bape": ["a bathing ape", "bathing ape"],
    "vivienne westwood": ["westwood", "vw", "vivienne"],
    "kapital": ["kapital kountry"],
    "needles": [],
    "visvim": [],
    "wtaps": ["w)taps", "double taps"],
    "neighborhood": ["nbhd"],
    "stone island": ["si", "stoney"],
    "c.p. company": ["cp company", "c.p company"],
    "prada": [],
    "gucci": [],
    "versace": [],
    "jean paul gaultier": ["jpg", "gaultier", "jean-paul gaultier"],
    "thierry mugler": ["mugler"],
    "dolce gabbana": ["dolce & gabbana", "d&g"],
    "ann demeulemeester": ["ann d", "ann demeule"],
    "dries van noten": ["dries", "dvn"],
    "vetements": [],
}

MODEL_ALIASES: Dict[str, List[str]] = {
    "geobasket": ["geo basket", "geobaskets", "geo", "geo baskets"],
    "ramones": ["ramone", "ramo", "ramone low", "ramones low"],
    "dunks": ["dunk", "drkshdw dunk", "rick dunk"],
    "stooges": ["stooges jacket", "stooges leather"],
    "intarsia": ["intarsia knit"],
    "bauhaus": ["bauhaus jacket", "bauhaus leather"],
    "ozweego": ["ozweegos", "raf ozweego", "adidas ozweego"],
    "response trail": ["response trail runner"],
    "tabi": ["tabi boots", "tabi boot", "split toe"],
    "german army trainer": ["gat", "replica sneaker", "gats"],
    "triple s": ["triple-s"],
    "speed trainer": ["speed", "speed runner"],
    "box logo": ["bogo", "box logo hoodie", "box logo tee"],
    "painter": ["painter pants", "painter jeans", "painter denim"],
    "astro": ["astro biker", "astro moto"],
}

# Season/collection name mappings
COLLECTION_ALIASES: Dict[str, List[str]] = {
    "raf simons aw01": ["riot riot riot", "riot"],
    "raf simons aw02": ["virginia creeper", "creeper"],
    "raf simons aw03": ["closer", "raf closer"],
    "raf simons ss04": ["consumed", "may the circle be unbroken"],
    "number nine aw01": ["soloist"],
    "number nine aw04": ["a closed darkness", "give peace a chance"],
    "number nine aw05": ["the high streets", "high streets"],
    "number nine aw06": ["nil"],
    "undercover aw03": ["scab"],
    "undercover ss05": ["arts and crafts"],
    "helmut lang fw98": ["astro biker", "astro moto era"],
    "helmut lang fw04": ["final collection", "last collection"],
}


def _build_alias_lookup() -> Dict[str, str]:
    """Build reverse lookup: alias → canonical name."""
    lookup = {}
    for canonical, aliases in BRAND_ALIASES.items():
        lookup[canonical.lower()] = canonical
        for alias in aliases:
            lookup[alias.lower()] = canonical
    return lookup

ALIAS_LOOKUP = _build_alias_lookup()


def canonicalize_brand(brand: str) -> str:
    """Resolve brand aliases to canonical name."""
    return ALIAS_LOOKUP.get(brand.lower().strip(), brand.lower().strip())


def expand_title_with_aliases(title: str) -> str:
    """
    Expand a title by replacing aliases with canonical names.
    This improves both keyword matching and embedding similarity.
    """
    result = title.lower()

    # Expand brand aliases
    for canonical, aliases in BRAND_ALIASES.items():
        for alias in aliases:
            if alias and alias.lower() in result:
                # Add canonical name if not already present
                if canonical not in result:
                    result = result.replace(alias.lower(), f"{alias.lower()} ({canonical})")
                break

    # Expand model aliases
    for canonical, aliases in MODEL_ALIASES.items():
        for alias in aliases:
            if alias and alias.lower() in result:
                if canonical not in result:
                    result = result.replace(alias.lower(), f"{alias.lower()} ({canonical})")
                break

    return result


# ══════════════════════════════════════════════════════════════
# EMBEDDING-BASED MATCHING
# ══════════════════════════════════════════════════════════════

_model = None
_model_name = "all-MiniLM-L6-v2"  # Fast, good quality, 384-dim embeddings


def _get_model():
    """Lazy-load the sentence transformer model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading sentence transformer: {_model_name}")
            _model = SentenceTransformer(_model_name)
            logger.info("Model loaded successfully")
        except ImportError:
            logger.warning("sentence-transformers not installed, embedding matching disabled")
            return None
    return _model


def get_title_embedding(title: str) -> Optional[np.ndarray]:
    """Get embedding vector for a title string."""
    model = _get_model()
    if model is None:
        return None
    # Expand aliases for better matching
    expanded = expand_title_with_aliases(title)
    return model.encode(expanded, normalize_embeddings=True)


def get_title_embeddings_batch(titles: List[str]) -> Optional[np.ndarray]:
    """Batch encode multiple titles. Much faster than one-by-one."""
    model = _get_model()
    if model is None:
        return None
    expanded = [expand_title_with_aliases(t) for t in titles]
    return model.encode(expanded, normalize_embeddings=True, batch_size=64)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two normalized vectors."""
    return float(np.dot(a, b))


def find_similar_titles(
    query_title: str,
    candidate_titles: List[str],
    top_k: int = 10,
    min_similarity: float = 0.4,
) -> List[Tuple[int, float]]:
    """
    Find the most similar titles from candidates using embeddings.

    Returns: List of (index, similarity_score) tuples, sorted by similarity.
    """
    model = _get_model()
    if model is None:
        return []

    query_expanded = expand_title_with_aliases(query_title)
    candidates_expanded = [expand_title_with_aliases(t) for t in candidate_titles]

    # Batch encode
    all_texts = [query_expanded] + candidates_expanded
    embeddings = model.encode(all_texts, normalize_embeddings=True, batch_size=64)

    query_emb = embeddings[0]
    candidate_embs = embeddings[1:]

    # Compute similarities
    similarities = np.dot(candidate_embs, query_emb)

    # Get top-k above threshold
    results = []
    for idx in np.argsort(similarities)[::-1]:
        sim = float(similarities[idx])
        if sim < min_similarity:
            break
        results.append((int(idx), sim))
        if len(results) >= top_k:
            break

    return results


# ══════════════════════════════════════════════════════════════
# HYBRID SIMILARITY (structured + embedding)
# ══════════════════════════════════════════════════════════════

def hybrid_similarity(
    listing_title: str,
    comp_title: str,
    structured_score: float,
    listing_embedding: Optional[np.ndarray] = None,
    comp_embedding: Optional[np.ndarray] = None,
) -> float:
    """
    Combine structured keyword matching with embedding similarity.

    structured_score: the existing score from score_comp_similarity()
    Returns blended score 0.0-1.0.
    """
    # If embeddings available, blend 50/50
    if listing_embedding is not None and comp_embedding is not None:
        emb_score = cosine_similarity(listing_embedding, comp_embedding)
        # Embedding similarity is on 0-1 scale but tends to cluster 0.3-0.9
        # Rescale to be more useful
        emb_score = max(0, (emb_score - 0.3) / 0.6)  # 0.3→0, 0.9→1.0
        return 0.50 * structured_score + 0.50 * emb_score

    # Without embeddings, use alias-boosted structured score
    return structured_score


# ══════════════════════════════════════════════════════════════
# HISTORICAL DB: COMP EMBEDDING STORAGE
# ══════════════════════════════════════════════════════════════

def ensure_embedding_columns():
    """Add embedding column to sold_comps table if not present."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    try:
        c.execute("PRAGMA table_info(sold_comps)")
        cols = {row[1] for row in c.fetchall()}

        new_cols = {
            "title_embedding": "BLOB",
            "platform": "TEXT",
            "item_type": "TEXT",
            "model_name": "TEXT",
            "sub_brand": "TEXT",
            "material": "TEXT",
            "color": "TEXT",
            "season": "TEXT",
            "shipping_cost": "REAL",
            "is_auction": "INTEGER DEFAULT 0",
            "num_bids": "INTEGER",
            "normalized_price": "REAL",
        }

        for col, col_type in new_cols.items():
            if col not in cols:
                c.execute(f"ALTER TABLE sold_comps ADD COLUMN {col} {col_type}")
                logger.info(f"Added column {col} to sold_comps")

        conn.commit()
    finally:
        conn.close()


def save_comp_with_embedding(
    search_key: str,
    title: str,
    brand: str,
    sold_price: float,
    source: str = "",
    source_id: str = "",
    size: str = "",
    condition: str = "",
    sold_url: str = "",
    sold_date: str = "",
    embedding: Optional[np.ndarray] = None,
    platform: str = "",
    item_type: str = "",
    model_name: str = "",
    sub_brand: str = "",
    material: str = "",
    color: str = "",
    season: str = "",
    shipping_cost: Optional[float] = None,
    is_auction: bool = False,
    num_bids: Optional[int] = None,
    normalized_price: Optional[float] = None,
):
    """Save a sold comp with all enhanced fields including embedding."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    try:
        emb_blob = embedding.tobytes() if embedding is not None else None

        c.execute("""
            INSERT OR IGNORE INTO sold_comps
            (search_key, brand, title, sold_price, size, sold_url, source, source_id,
             condition, sold_date, fetched_at, title_embedding, platform, item_type,
             model_name, sub_brand, material, color, season, shipping_cost,
             is_auction, num_bids, normalized_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            search_key, brand, title, sold_price, size, sold_url, source, source_id,
            condition, sold_date, datetime_now_str(), emb_blob, platform, item_type,
            model_name, sub_brand, material, color, season, shipping_cost,
            1 if is_auction else 0, num_bids, normalized_price,
        ))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to save comp: {e}")
    finally:
        conn.close()


def search_comps_by_embedding(
    query_embedding: np.ndarray,
    brand: str = "",
    limit: int = 50,
    min_price: float = 0,
) -> List[dict]:
    """
    Search the historical comp database using embedding similarity.
    Falls back to title-based search if no embeddings stored.
    """
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    try:
        where = ["sold_price > ?"]
        params: list = [min_price]

        if brand:
            where.append("LOWER(brand) = LOWER(?)")
            params.append(brand)

        # Get all comps with embeddings for this brand
        c.execute(
            f"SELECT id, title, sold_price, size, condition, sold_date, source, "
            f"source_id, sold_url, title_embedding, platform, is_auction, num_bids, "
            f"shipping_cost, normalized_price "
            f"FROM sold_comps WHERE {' AND '.join(where)} "
            f"AND title_embedding IS NOT NULL "
            f"ORDER BY id DESC LIMIT 500",
            params
        )
        rows = c.fetchall()

        if not rows:
            return []

        # Compute similarities
        results = []
        for row in rows:
            emb_blob = row[9]
            if emb_blob is None:
                continue
            comp_emb = np.frombuffer(emb_blob, dtype=np.float32)
            if len(comp_emb) != len(query_embedding):
                continue
            sim = cosine_similarity(query_embedding, comp_emb)
            results.append({
                "id": row[0],
                "title": row[1],
                "sold_price": row[2],
                "size": row[3],
                "condition": row[4],
                "sold_date": row[5],
                "source": row[6],
                "source_id": row[7],
                "url": row[8],
                "similarity": sim,
                "platform": row[10] or row[6],
                "is_auction": bool(row[11]),
                "num_bids": row[12],
                "shipping_cost": row[13],
                "normalized_price": row[14],
            })

        # Sort by similarity
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    finally:
        conn.close()


def backfill_embeddings(batch_size: int = 100, max_items: int = 5000):
    """
    Backfill embeddings for existing sold comps that don't have them.
    Run this once to bootstrap, then new comps get embedded on save.
    """
    model = _get_model()
    if model is None:
        logger.error("Cannot backfill: sentence-transformers not available")
        return 0

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    total = 0

    try:
        c.execute(
            "SELECT id, title FROM sold_comps WHERE title_embedding IS NULL LIMIT ?",
            (max_items,)
        )
        rows = c.fetchall()

        if not rows:
            logger.info("No comps need backfilling")
            return 0

        logger.info(f"Backfilling embeddings for {len(rows)} comps...")

        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            ids = [r[0] for r in batch]
            titles = [expand_title_with_aliases(r[1]) for r in batch]

            embeddings = model.encode(titles, normalize_embeddings=True, batch_size=64)

            for row_id, emb in zip(ids, embeddings):
                c.execute(
                    "UPDATE sold_comps SET title_embedding = ? WHERE id = ?",
                    (emb.astype(np.float32).tobytes(), row_id)
                )
            conn.commit()
            total += len(batch)
            logger.info(f"  Backfilled {total}/{len(rows)} comps")

    finally:
        conn.close()

    logger.info(f"Backfill complete: {total} comps embedded")
    return total


def datetime_now_str() -> str:
    from datetime import datetime
    return datetime.now().isoformat()


# Initialize on import
try:
    ensure_embedding_columns()
except Exception as e:
    logger.warning(f"Could not ensure embedding columns: {e}")

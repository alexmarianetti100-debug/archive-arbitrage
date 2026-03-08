"""
GrailedVelocitySource — Top-selling items on Grailed by sold volume.

Strategy:
  Fetch the Grailed sold index with an empty query (returns most recently sold
  items across all categories). Group by (brand + product model). The items
  that appear most frequently in sold results = highest sell-through volume.
  Those become today's search targets.

One API call. No brand list. No baseline. Grailed tells us what's selling.
"""

import asyncio
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from .base import TrendSignal, TrendSource

logger = logging.getLogger("trend.grailed_velocity")

# ── Tuning ───────────────────────────────────────────────────────────────────
# Algolia caps at 1000 results regardless of pages × per_page, so we search
# per-brand instead of a single empty query. Each brand gets its own 1000-item
# window, giving dense product-level clustering.
SOLD_PER_BRAND = 1000   # Items to fetch per brand (Algolia max)
SOLD_DAYS = 30          # Only count sales from the last 30 days (monthly volume)
MIN_SALES = 2           # Min sales per brand window to be considered
MIN_AVG_PRICE = 150.0   # Minimum average sold price — filters cheap volume items
MAX_TARGETS = 150       # Cap on total targets returned (more candidates for tiering)

# Priority brands fetched every run (high archive value, consistent deal flow)
PRIORITY_BRANDS = [
    "rick owens", "chrome hearts", "maison margiela", "helmut lang",
    "jean paul gaultier", "raf simons", "dior homme", "number (n)ine",
    "saint laurent", "bottega veneta", "yohji yamamoto", "comme des garcons",
    "undercover", "balenciaga", "vivienne westwood", "issey miyake",
    "ann demeulemeester", "julius", "junya watanabe", "prada",
]

# ── Archive brands we care about (client-side filter) ────────────────────────
ARCHIVE_BRANDS = {
    "rick owens", "chrome hearts", "raf simons", "helmut lang",
    "maison margiela", "comme des garcons", "undercover", "number (n)ine",
    "yohji yamamoto", "balenciaga", "saint laurent", "prada", "dior homme",
    "vivienne westwood", "jean paul gaultier", "issey miyake", "julius",
    "bottega veneta", "celine", "junya watanabe", "kapital", "visvim",
    "hysteric glamour", "needles", "sacai", "bape", "wtaps", "givenchy",
    "gucci", "versace", "dries van noten", "mihara yasuhiro", "burberry",
    "enfants riches deprimes", "wacko maria", "human made", "number nine",
    "ann demeulemeester", "carol christian poell", "boris bidjan saberi",
    "haider ackermann", "alexander mcqueen", "thierry mugler", "stone island",
    "amiri", "gallery dept", "vetements", "acronym", "alyx", "supreme",
    "off-white", "neighborhood",
}

# ── Filler words stripped before product key extraction ──────────────────────
STRIP_WORDS = {
    "xs", "sm", "md", "lg", "xl", "xxl", "xxxl", "os",
    "black", "white", "grey", "gray", "red", "blue", "brown", "green", "nude",
    "beige", "tan", "cream", "ivory", "silver", "gold", "purple", "yellow",
    "orange", "pink", "olive", "navy", "ecru", "khaki", "camel", "dark", "light",
    "nwt", "bnwt", "vnds", "deadstock", "new", "used", "worn", "ds",
    "the", "a", "an", "in", "for", "with", "and", "or", "from", "by", "of",
    "authentic", "genuine", "original", "vintage", "archive", "rare", "grail",
    "mens", "womens", "unisex", "men", "women", "ss", "fw", "aw",
}

# ── Known product model keywords (longest/most specific first) ───────────────
PRODUCT_MODELS = [
    # Rick Owens
    "banana dunks", "geobasket", "ramones high", "ramones low", "ramones",
    "kiss boots", "larry boots", "sickle boots",
    "stooges leather jacket", "stooges",
    "dustulator leather jacket", "dustulator",
    "memphis leather jacket", "memphis",
    "intarsia knit", "intarsia",
    "bauhaus cargo", "bauhaus",
    "creatch cargo", "creatch",
    "drkshdw detroit cut", "detroit cut",
    "level tee", "pentagram hoodie", "champion hoodie", "blistered leather",
    # Chrome Hearts
    "cemetery cross pendant", "cemetery cross",
    "dagger pendant", "floral cross ring", "floral cross",
    "cross pendant", "cross ring",
    "scroll bracelet", "matty boy hoodie", "matty boy",
    "horseshoe hoodie", "paper chain necklace", "paper chain",
    "fuck you ring",
    # Raf Simons
    "riot bomber", "consumed hoodie", "consumed",
    "peter saville joy division", "peter saville",
    "virginia creeper", "history of my world",
    "tape bomber", "ozweego", "response trail",
    "cylon boots", "sterling ruby",
    # Helmut Lang
    "bondage jacket", "bondage pants",
    "astro biker jacket", "astro biker",
    "painter jeans", "flak jacket",
    "archive strap", "archive tank top", "nylon bomber",
    # Maison Margiela
    "tabi ankle boots", "tabi boots", "tabi",
    "replica gat", "glam slam bag", "glam slam",
    "numbers tee", "paint splatter", "deconstructed blazer",
    # Dior Homme
    "navigate leather", "bee embroidery", "b23 oblique",
    "hedi leather jacket", "atelier tee", "saddle bag",
    "oblique jacket", "scoop neck tee",
    # Balenciaga
    "triple s", "speed trainer", "defender",
    "3xl sneaker", "balenciaga runner",
    "political campaign hoodie", "oversized denim jacket",
    # Saint Laurent
    "wyatt boots", "chain boots", "l01 leather jacket",
    "blood luster jacket", "court classic",
    # Jean Paul Gaultier
    "mesh top", "mesh long sleeve", "cyberbaba", "tattoo top", "corset",
    # Celine
    "triomphe bag", "triomphe belt", "luggage bag", "box bag", "western boots",
    # Vivienne Westwood
    "orb necklace", "pearl choker", "armor ring", "pearl necklace",
    # Number (N)ine
    "skull cashmere", "high streets", "kurt cobain",
    "heart skull sweater", "heart skull",
    "touch me im sick", "marlboro", "guitar strap",
    # Undercover
    "scab", "85 bomber", "less but better", "arts and crafts",
    "68 blue", "psycho color", "but beautiful", "grace jacket",
    # Issey Miyake
    "homme plisse pants", "homme plisse jacket", "homme plisse tee", "homme plisse",
    "pleats please", "bao bao bag", "bao bao",
    # Kapital
    "century denim", "boro jacket", "bandana patchwork",
    # Bottega Veneta
    "puddle boots", "tire boots", "cassette bag",
    # Prada
    "americas cup", "cloudbust", "linea rossa", "re nylon", "gabardine",
    # Generic high-value
    "leather jacket", "cargo pants", "knit sweater", "denim jacket", "bomber jacket",
]

_SEASON_RE = re.compile(r'\b(?:fw|ss|aw)\s*\d{2,4}\b', re.IGNORECASE)
_SIZE_NUMBER_RE = re.compile(r'\b\d{1,3}(?:\.\d)?\b')


class GrailedVelocitySource(TrendSource):
    """
    Pulls the top-selling items from Grailed's sold index by raw volume.
    """

    @property
    def name(self) -> str:
        return "grailed_velocity"

    @property
    def weight(self) -> float:
        return 1.0

    async def fetch_signals(self) -> list[TrendSignal]:
        from scrapers.grailed import GrailedScraper

        cutoff = datetime.now(timezone.utc) - timedelta(days=SOLD_DAYS)

        # Fetch sold items per brand concurrently (Algolia caps at 1000 per query,
        # so searching brand-by-brand gives us 1000 items per brand = dense clustering)
        logger.info(
            f"  Fetching sold data for {len(PRIORITY_BRANDS)} brands "
            f"({SOLD_PER_BRAND} items each, last {SOLD_DAYS} days)..."
        )

        async with GrailedScraper() as scraper:
            sem = asyncio.Semaphore(4)  # max 4 concurrent brand fetches

            async def fetch_brand(brand: str) -> list:
                async with sem:
                    try:
                        items = await scraper.search_sold_bulk(brand, pages=1, per_page=SOLD_PER_BRAND)
                        logger.info(f"    {brand}: {len(items)} items")
                        return items
                    except Exception as e:
                        logger.warning(f"    {brand}: fetch failed ({e})")
                        return []

            brand_results = await asyncio.gather(*[fetch_brand(b) for b in PRIORITY_BRANDS])

        total_items = sum(len(r) for r in brand_results)
        logger.info(f"  Got {total_items} sold items across {len(PRIORITY_BRANDS)} brands — clustering by product...")

        # Group by (brand, product_key), count sales within the time window
        groups: dict[tuple[str, str], list] = defaultdict(list)

        for brand, items in zip(PRIORITY_BRANDS, brand_results):
            for item in items:
                sale_date = self._get_sale_date(item)
                if sale_date and sale_date < cutoff:
                    continue

                detected_brand = self._detect_brand(item.title, item.raw_data or {})
                # Accept the fetched brand or the detected brand (Grailed sometimes
                # returns items from related brands in a brand search)
                effective_brand = detected_brand if detected_brand else brand

                product_key = self._extract_product_key(item.title, effective_brand)
                if not product_key or product_key == "general":
                    continue

                groups[(effective_brand, product_key)].append(item)

        # Build signals from groups meeting MIN_SALES + MIN_AVG_PRICE
        candidates: list[TrendSignal] = []

        for (brand, product_key), sold_items in groups.items():
            count = len(sold_items)
            if count < MIN_SALES:
                continue

            prices = [i.price for i in sold_items if i.price and i.price > 0]
            if not prices:
                continue
            avg_price = sum(prices) / len(prices)

            # Hard floor: skip cheap items regardless of volume
            if avg_price < MIN_AVG_PRICE:
                continue

            # Opportunity score = dollar velocity (avg price × monthly sold count)
            # This ranks a $600 jacket selling 10×/month above a $200 tee selling 20×/month
            opportunity_score = avg_price * count

            candidates.append(TrendSignal(
                brand=brand.title(),
                item_type=product_key,
                specific_query=f"{brand} {product_key}",
                trend_score=0.0,            # filled in below after normalisation
                trend_direction="rising" if count >= 8 else "stable",
                signal_sources=[self.name],
                est_sold_volume=count,
                avg_sold_price=avg_price,
                opportunity_score=opportunity_score,
            ))

        # Normalise trend_score against the max opportunity_score in this batch
        if candidates:
            max_opp = max(s.opportunity_score for s in candidates)
            for sig in candidates:
                sig.trend_score = min(1.0, sig.opportunity_score / max_opp)

        # Sort by opportunity score (dollar velocity), not raw count
        candidates.sort(key=lambda s: s.opportunity_score, reverse=True)

        logger.info(f"  {len(candidates)} targets identified (avg_price ≥ ${MIN_AVG_PRICE:.0f}, sales ≥ {MIN_SALES}/mo). Top by opportunity:")
        for sig in candidates[:20]:
            logger.info(
                f"    [${sig.avg_sold_price:.0f} avg × {sig.est_sold_volume} sold "
                f"= ${sig.opportunity_score:.0f} opp] {sig.specific_query}"
            )

        return candidates[:MAX_TARGETS]

    def _get_sale_date(self, item) -> Optional[datetime]:
        raw = item.raw_data or {}
        for field in ("sold_at", "created_at"):
            val = raw.get(field)
            if val:
                try:
                    dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except (ValueError, TypeError):
                    continue
        if item.listed_at:
            dt = item.listed_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        return None

    def _detect_brand(self, title: str, raw_data: dict) -> str:
        """Detect archive brand from Algolia designer field, then title fallback."""
        designers = raw_data.get("designers", [])
        if designers and isinstance(designers, list):
            d = designers[0]
            name = (d.get("name", "") if isinstance(d, dict) else str(d)).lower().strip()
            if name in ARCHIVE_BRANDS:
                return name

        title_lower = title.lower()
        for brand in sorted(ARCHIVE_BRANDS, key=len, reverse=True):
            if brand in title_lower:
                return brand
        return ""

    def _extract_product_key(self, title: str, brand: str) -> str:
        title_lower = title.lower().strip()

        # Pass 1: known model keywords
        for model in PRODUCT_MODELS:
            if model in title_lower:
                return model

        # Pass 2: strip brand + filler, take first 3 meaningful tokens
        cleaned = title_lower
        for word in brand.lower().split():
            cleaned = re.sub(r'\b' + re.escape(word) + r'\b', '', cleaned)
        cleaned = _SEASON_RE.sub('', cleaned)
        cleaned = _SIZE_NUMBER_RE.sub('', cleaned)

        tokens = cleaned.split()
        meaningful = [
            t for t in tokens
            if t and t not in STRIP_WORDS and len(t) > 1 and not t.isdigit()
        ]

        return " ".join(meaningful[:3]) if meaningful else "general"

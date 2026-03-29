"""Comp Validation Safety Net — 5-check filter for comp quality.

Runs AFTER is_exact_match() filtering, BEFORE gap calculation.
Catches mismatches that fingerprint extraction missed.
Uses broader regex patterns than the fingerprinter.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("comp_validator")

# Broad category keywords — derived from canonical taxonomy + extra aggressive keywords
# for the validator (which intentionally catches more mismatches than the fingerprinter).
from core.categories import ITEM_TYPES as _CANONICAL_TYPES, CATEGORY_MAP as _CAT_MAP

def _build_broad_keywords() -> dict[str, list[str]]:
    """Build broad category keyword dict from canonical fine-grained types."""
    broad: dict[str, set[str]] = {}
    for fine_type, keywords in _CANONICAL_TYPES.items():
        broad_cat = _CAT_MAP.get(fine_type, "accessories")
        broad.setdefault(broad_cat, set()).update(keywords)
    # Extra aggressive keywords the validator uses but aren't in the canonical list
    broad.setdefault("footwear", set()).update(["heels", "slippers"])
    broad.setdefault("outerwear", set()).update(["vest", "gilet"])
    broad.setdefault("tops", set()).update(["tank", "top", "polo", "henley"])
    broad.setdefault("bottoms", set()).update(["skirt"])
    broad.setdefault("accessories", set()).update(["gloves"])
    return {k: sorted(v, key=len, reverse=True) for k, v in broad.items()}

CATEGORY_KEYWORDS: dict[str, list[str]] = _build_broad_keywords()

MATERIAL_KEYWORDS = [
    "leather", "suede", "canvas", "nylon", "denim", "mesh", "wool",
    "cashmere", "silk", "cotton", "rubber", "patent", "shearling",
    "velvet", "corduroy", "gore-tex", "waxed", "coated", "knit",
]

# Brands with extended recency window (archive pieces sell infrequently).
# These get a 365-day comp window instead of 180 days because vintage/archive
# pieces have low liquidity and sparse comp data.
# Contemporary luxury brands (Balenciaga, Gucci, Prada, etc.) are NOT included —
# they have high production volume and 180 days is sufficient.
ARCHIVE_BRANDS = {
    # Original set
    "helmut lang", "number nine", "number (n)ine", "carol christian poell",
    "jean colonna", "walter van beirendonck", "boris bidjan saberi",
    # Core archive designers
    "raf simons",
    "undercover", "undercoverism",
    "yohji yamamoto",
    "rick owens", "drkshdw",
    "maison margiela", "martin margiela", "margiela",
    "dior homme",
    "jean paul gaultier", "gaultier",
    "ann demeulemeester",
    "thierry mugler", "mugler",
    "alexander mcqueen", "mcqueen",
    "issey miyake",
    "junya watanabe",
    "comme des garcons", "cdg",
    "vivienne westwood",
    # Niche archive / cult designers
    "enfants riches deprimes", "erd",
    "julius",
    "guidi",
    "kapital",
    "haider ackermann",
    "dries van noten",
    "hysteric glamour",
    "takahiromiyashita thesoloist", "soloist",
    "ccp",
    "sacai",
    "craig green",
    "kiko kostadinov",
}

COMP_MAX_AGE_DAYS = 180
ARCHIVE_MAX_AGE_DAYS = 365

# Contemporary high-volume brands — shorter comp window (market moves fast)
CONTEMPORARY_BRANDS = {
    "balenciaga", "gucci", "prada", "louis vuitton", "bottega veneta",
    "saint laurent", "burberry", "acne studios", "lemaire", "amiri",
    "off-white", "palm angels", "fear of god", "essentials",
    "stone island", "moncler", "canada goose",
}
CONTEMPORARY_MAX_AGE_DAYS = 120  # 4 months — prices shift quickly for high-volume brands


def get_comp_max_age(brand: str) -> int:
    """Get the appropriate comp age limit for a brand."""
    brand_lower = brand.lower().strip()
    if brand_lower in ARCHIVE_BRANDS:
        return ARCHIVE_MAX_AGE_DAYS  # 365d — sparse sales, long-lived value
    if brand_lower in CONTEMPORARY_BRANDS:
        return CONTEMPORARY_MAX_AGE_DAYS  # 120d — high volume, fast depreciation
    return COMP_MAX_AGE_DAYS  # 180d — default


def _extract_category(title: str) -> Optional[str]:
    title_lower = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in sorted(keywords, key=len, reverse=True):
            if kw in title_lower:
                return category
    return None


def _extract_material(title: str) -> Optional[str]:
    title_lower = title.lower()
    for mat in MATERIAL_KEYWORDS:
        if re.search(rf'\b{re.escape(mat)}\b', title_lower):
            return mat
    return None


def check_category_parity(listing_title: str, comp_title: str) -> bool:
    """Check 1: Broad category must match (if detectable)."""
    listing_cat = _extract_category(listing_title)
    comp_cat = _extract_category(comp_title)
    if listing_cat and comp_cat:
        return listing_cat == comp_cat
    return True


def check_line_parity(
    listing_title: str, listing_brand: str,
    comp_title: str, comp_brand: str,
) -> bool:
    """Check 2: Mainline vs diffusion must agree.

    Uses asymmetric thresholds:
    - Diffusion = multiplier < 0.5
    - Mainline = multiplier >= 0.8
    - Middle zone (0.5-0.8) = secondary lines, match either side
    """
    from core.line_detection import detect_line
    _, listing_mult, _ = detect_line(listing_title, listing_brand)
    _, comp_mult, _ = detect_line(comp_title, comp_brand)
    if listing_mult < 0.5 and comp_mult >= 0.8:
        return False
    if listing_mult >= 0.8 and comp_mult < 0.5:
        return False
    return True


def check_material_parity(listing_title: str, comp_title: str) -> bool:
    """Check 3: Material must match if detectable in both."""
    listing_mat = _extract_material(listing_title)
    comp_mat = _extract_material(comp_title)
    if listing_mat and comp_mat:
        return listing_mat == comp_mat
    return True


def check_recency(sold_date_str: Optional[str], archive_brand: bool = False, brand: str = "") -> bool:
    """Check 4: Comp must be recent enough. Per-brand age limits."""
    if not sold_date_str:
        return True
    try:
        sold_dt = datetime.fromisoformat(sold_date_str.replace("Z", "+00:00"))
        # Use per-brand age limit if brand provided, else fall back to binary flag
        if brand:
            max_age = get_comp_max_age(brand)
        else:
            max_age = ARCHIVE_MAX_AGE_DAYS if archive_brand else COMP_MAX_AGE_DAYS
        age = (datetime.now(sold_dt.tzinfo) - sold_dt).days
        return age <= max_age
    except (ValueError, TypeError):
        return True


def remove_outliers(prices: list[float]) -> list[float]:
    """Check 5: Remove comps > 2x or < 0.5x the median price."""
    if len(prices) < 3:
        return prices
    sorted_prices = sorted(prices)
    median = sorted_prices[len(sorted_prices) // 2]
    if median <= 0:
        return prices
    return [p for p in prices if 0.5 * median <= p <= 2.0 * median]


@dataclass
class CompValidationResult:
    surviving_count: int
    original_count: int
    confidence: str  # "full" (5+), "reduced" (3-4), "low" (1-2), "none" (0)
    score_penalty: int  # Points to subtract from quality score
    surviving_indices: list[int]


def validate_comps(
    listing_title: str,
    listing_brand: str,
    comp_titles: list[str],
    comp_prices: list[float],
    comp_sold_dates: list[Optional[str]] = None,
) -> CompValidationResult:
    """Run all 5 validation checks on a comp set."""
    if comp_sold_dates is None:
        comp_sold_dates = [None] * len(comp_titles)

    is_archive = listing_brand.lower().strip() in ARCHIVE_BRANDS
    surviving = list(range(len(comp_titles)))

    surviving = [i for i in surviving if check_category_parity(listing_title, comp_titles[i])]
    surviving = [i for i in surviving if check_line_parity(listing_title, listing_brand, comp_titles[i], listing_brand)]
    surviving = [i for i in surviving if check_material_parity(listing_title, comp_titles[i])]
    surviving = [i for i in surviving if check_recency(comp_sold_dates[i], brand=listing_brand)]

    if len(surviving) >= 3:
        surviving_prices = [comp_prices[i] for i in surviving]
        valid_prices = set(remove_outliers(surviving_prices))
        surviving = [i for i in surviving if comp_prices[i] in valid_prices]

    n = len(surviving)
    if n >= 5:
        confidence, penalty = "full", 0
    elif n >= 3:
        confidence, penalty = "reduced", 10
    elif n >= 1:
        confidence, penalty = "low", 0
    else:
        confidence, penalty = "none", 0

    original = len(comp_titles)
    if original > n:
        logger.info(f"Comp validator: {original} -> {n} comps survived ({original - n} rejected, confidence={confidence})")

    return CompValidationResult(
        surviving_count=n, original_count=original,
        confidence=confidence, score_penalty=penalty,
        surviving_indices=surviving,
    )

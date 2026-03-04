"""
Size Normalizer — Adjust comp prices based on size premiums/discounts.

Archive fashion has significant size-based price variation:
- Small sizes (XS-S, 28-30, EU 40-42) command premiums for many brands
- Asian market demand drives small-size premiums
- Vintage sizing runs smaller than modern
"""

import re
from typing import Optional


# ══════════════════════════════════════════════════════════════
# GENERAL SIZE ADJUSTMENTS (relative to most common/baseline size)
# ══════════════════════════════════════════════════════════════

SIZE_ADJUSTMENTS = {
    "tops": {
        "xxs": 1.05, "xs": 1.10, "s": 1.12, "m": 1.05,
        "l": 1.00, "xl": 0.95, "xxl": 0.90, "xxxl": 0.85,
        # EU/IT numeric
        "44": 1.15, "46": 1.12, "48": 1.05, "50": 1.00,
        "52": 0.95, "54": 0.92, "56": 0.88,
    },
    "bottoms": {
        # Waist sizes (inches)
        "26": 1.05, "27": 1.08, "28": 1.12, "29": 1.10,
        "30": 1.05, "31": 1.02, "32": 1.00, "33": 0.98,
        "34": 0.95, "36": 0.90, "38": 0.85, "40": 0.80,
    },
    "outerwear": {
        "xxs": 1.02, "xs": 1.05, "s": 1.05, "m": 1.02,
        "l": 1.00, "xl": 0.98, "xxl": 0.95,
        "44": 1.08, "46": 1.05, "48": 1.02, "50": 1.00,
        "52": 0.97, "54": 0.93, "56": 0.90,
    },
    "footwear": {
        # EU sizes
        "38": 0.88, "39": 0.92, "40": 0.95, "41": 1.00,
        "42": 1.02, "43": 1.00, "44": 0.98, "45": 0.95,
        "46": 0.90, "47": 0.85,
        # US sizes
        "7": 0.90, "7.5": 0.92, "8": 0.95, "8.5": 0.97,
        "9": 1.00, "9.5": 1.00, "10": 1.00, "10.5": 1.00,
        "11": 0.98, "11.5": 0.97, "12": 0.95, "13": 0.90, "14": 0.85,
    },
}

# ══════════════════════════════════════════════════════════════
# BRAND-SPECIFIC OVERRIDES
# ══════════════════════════════════════════════════════════════

BRAND_SIZE_OVERRIDES = {
    "rick owens": {
        "footwear": {
            # Rick runs large + Asian market demand for small sizes
            "39": 1.15, "40": 1.20, "41": 1.22, "42": 1.15,
            "43": 1.05, "44": 1.00, "45": 0.95, "46": 0.90,
        },
        "tops": {
            "44": 1.18, "46": 1.15, "48": 1.08, "50": 1.00,
            "52": 0.95, "54": 0.90,
            "xs": 1.15, "s": 1.15, "m": 1.05, "l": 1.00, "xl": 0.95,
        },
    },
    "raf simons": {
        "tops": {
            "44": 1.22, "46": 1.18, "48": 1.10, "50": 1.00,
            "52": 0.95, "54": 0.90,
        },
        "outerwear": {
            "44": 1.25, "46": 1.20, "48": 1.10, "50": 1.00,
            "52": 0.95, "54": 0.90,
        },
    },
    "number nine": {
        "tops": {
            # Japanese brand — all sizes are relatively small
            "1": 1.15, "2": 1.10, "3": 1.00, "4": 0.95,
            "s": 1.12, "m": 1.05, "l": 1.00, "xl": 0.95,
        },
    },
    "undercover": {
        "tops": {
            "1": 1.12, "2": 1.08, "3": 1.00, "4": 0.95, "5": 0.90,
            "s": 1.10, "m": 1.05, "l": 1.00, "xl": 0.95,
        },
    },
    "helmut lang": {
        "tops": {
            "44": 1.15, "46": 1.12, "48": 1.05, "50": 1.00,
            "52": 0.95,
        },
        "bottoms": {
            "28": 1.15, "29": 1.12, "30": 1.08, "31": 1.02,
            "32": 1.00, "33": 0.97, "34": 0.95, "36": 0.88,
        },
    },
    "comme des garcons": {
        "tops": {
            "xs": 1.15, "s": 1.12, "m": 1.05, "l": 1.00, "xl": 0.92,
        },
    },
    "maison margiela": {
        "footwear": {
            # Tabis — smaller sizes premium
            "38": 1.10, "39": 1.12, "40": 1.10, "41": 1.05,
            "42": 1.00, "43": 0.98, "44": 0.95, "45": 0.90,
        },
    },
    "supreme": {
        "tops": {
            # Supreme — S and M are most sought after
            "s": 1.15, "m": 1.10, "l": 1.00, "xl": 0.95, "xxl": 0.88,
        },
    },
}


def normalize_size(size_str: str) -> str:
    """Normalize size string for lookup."""
    if not size_str:
        return ""
    s = size_str.strip().lower()
    # Remove "size" prefix
    s = re.sub(r"^(?:size|sz|eu|us|uk|it|jp)\s*", "", s)
    # Remove trailing units
    s = re.sub(r"\s*(?:eu|us|uk|it)$", "", s)
    return s.strip()


def detect_item_category(item_type: str) -> str:
    """Map item_type to size category."""
    item_type = (item_type or "").lower()

    footwear = ["boots", "shoes", "sneakers", "sandals", "slides", "derbies", "loafers", "mules"]
    bottoms = ["pants", "jeans", "trousers", "shorts", "denim", "cargo"]
    outerwear = ["jacket", "coat", "parka", "bomber", "blazer", "vest"]
    # Default tops: tee, shirt, hoodie, sweater, etc.

    for kw in footwear:
        if kw in item_type:
            return "footwear"
    for kw in bottoms:
        if kw in item_type:
            return "bottoms"
    for kw in outerwear:
        if kw in item_type:
            return "outerwear"
    return "tops"


def get_size_multiplier(
    size: str,
    item_type: str = "",
    brand: str = "",
) -> float:
    """
    Get the price multiplier for a given size.
    Returns 1.0 if size not found or not applicable.
    """
    size_norm = normalize_size(size)
    if not size_norm:
        return 1.0

    category = detect_item_category(item_type)
    brand_lower = brand.lower().strip()

    # Check brand-specific first
    if brand_lower in BRAND_SIZE_OVERRIDES:
        brand_cats = BRAND_SIZE_OVERRIDES[brand_lower]
        if category in brand_cats:
            mult = brand_cats[category].get(size_norm)
            if mult is not None:
                return mult

    # Fall back to general
    if category in SIZE_ADJUSTMENTS:
        mult = SIZE_ADJUSTMENTS[category].get(size_norm)
        if mult is not None:
            return mult

    return 1.0


def adjust_for_size(
    price: float,
    listing_size: str,
    comp_size: str,
    item_type: str = "",
    brand: str = "",
) -> float:
    """
    Adjust a comp's price based on size difference from the listing.

    If listing is size 41 (multiplier 1.22) and comp is size 44 (1.00),
    the comp sold for less than this size would — adjust up by 1.22/1.00.
    """
    listing_mult = get_size_multiplier(listing_size, item_type, brand)
    comp_mult = get_size_multiplier(comp_size, item_type, brand)

    if comp_mult <= 0:
        return price

    # Ratio: how much more/less the listing's size is worth
    adjustment = listing_mult / comp_mult

    # Cap extreme adjustments at ±30%
    adjustment = max(0.70, min(1.30, adjustment))

    return price * adjustment

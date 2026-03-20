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
    "rings": {
        # Ring sizes (US) — smaller sizes command premiums due to rarity
        # Most common sizes are 8-10 (baseline). Smaller = rarer = premium.
        "4": 1.25, "4.5": 1.22, "5": 1.20, "5.5": 1.18,
        "6": 1.15, "6.5": 1.12, "7": 1.08, "7.5": 1.05,
        "8": 1.02, "8.5": 1.00, "9": 1.00, "9.5": 1.00,
        "10": 0.98, "10.5": 0.97, "11": 0.95, "11.5": 0.93,
        "12": 0.90, "13": 0.85, "14": 0.80,
        # EU ring sizes
        "47": 1.20, "48": 1.18, "49": 1.15, "50": 1.12,
        "51": 1.08, "52": 1.05, "53": 1.02, "54": 1.00,
        "55": 1.00, "56": 1.00, "57": 0.98, "58": 0.97,
        "59": 0.95, "60": 0.93, "61": 0.90, "62": 0.88,
        "63": 0.85, "64": 0.82,
    },
    "bracelets": {
        # Bracelet sizes — less variation than rings
        "xs": 1.05, "s": 1.02, "m": 1.00, "l": 0.98, "xl": 0.95,
        "6": 1.05, "6.5": 1.02, "7": 1.00, "7.5": 0.98, "8": 0.95,
    },
    "necklaces": {
        # Necklace/chain lengths — standard length is baseline
        "16": 1.05, "18": 1.00, "20": 1.00, "22": 0.98, "24": 0.95,
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
    "chrome hearts": {
        "rings": {
            # CH rings — small sizes are significantly rarer and command premiums
            # Most CH rings are produced in sizes 8-11, smaller sizes are special order
            "4": 1.35, "4.5": 1.30, "5": 1.28, "5.5": 1.25,
            "6": 1.22, "6.5": 1.18, "7": 1.12, "7.5": 1.08,
            "8": 1.05, "8.5": 1.02, "9": 1.00, "9.5": 1.00,
            "10": 0.98, "10.5": 0.97, "11": 0.95, "11.5": 0.93,
            "12": 0.88, "13": 0.82,
            # EU ring sizes
            "47": 1.28, "48": 1.25, "49": 1.22, "50": 1.18,
            "51": 1.12, "52": 1.08, "53": 1.05, "54": 1.02,
            "55": 1.00, "56": 1.00, "57": 0.98, "58": 0.97,
            "59": 0.95, "60": 0.93, "61": 0.88,
        },
        "bracelets": {
            # CH bracelets — most are adjustable but specific sizes exist
            "xs": 1.10, "s": 1.05, "m": 1.00, "l": 0.98, "xl": 0.95,
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
    """Map item_type to size adjustment category."""
    item_type = (item_type or "").lower()

    # Direct match for fingerprint-detected types
    DIRECT_MAP = {
        "rings": "rings",
        "bracelets": "bracelets",
        "necklaces": "necklaces",
        "earrings": "necklaces",  # no size adjustments, use necklaces as proxy
        "footwear": "footwear",
        "outerwear": "outerwear",
        "pants": "bottoms",
        "shorts": "bottoms",
        "bags": "tops",         # bags don't have size-based pricing
        "hats": "tops",         # hats are mostly one-size
        "belts": "tops",        # belts have length but not tracked
        "wallets": "tops",      # one-size
        "eyewear": "tops",      # one-size
        "hoodies": "tops",
        "sweaters": "tops",
        "shirts": "tops",
        "t-shirts": "tops",
    }
    if item_type in DIRECT_MAP:
        return DIRECT_MAP[item_type]

    # Keyword fallback for non-fingerprinted types
    if any(kw in item_type for kw in ["ring", "band", "signet"]):
        return "rings"
    if any(kw in item_type for kw in ["bracelet", "cuff", "bangle"]):
        return "bracelets"
    if any(kw in item_type for kw in ["necklace", "pendant", "chain"]):
        return "necklaces"
    if any(kw in item_type for kw in ["boots", "shoes", "sneakers", "sandals", "loafers", "derbies", "mules"]):
        return "footwear"
    if any(kw in item_type for kw in ["pants", "jeans", "trousers", "shorts", "denim", "cargo"]):
        return "bottoms"
    if any(kw in item_type for kw in ["jacket", "coat", "parka", "bomber", "blazer"]):
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

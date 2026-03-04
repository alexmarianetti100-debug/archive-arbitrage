"""
Price Normalizer — Cross-platform fee normalization, auction adjustment,
and bundle detection for comparable sales accuracy.
"""

import re
from typing import Optional


# ══════════════════════════════════════════════════════════════
# PLATFORM FEE STRUCTURES
# ══════════════════════════════════════════════════════════════

# Default shipping estimates when actual shipping is unknown
DEFAULT_SHIPPING = {
    "grailed": 8.0,
    "ebay": 10.0,
    "poshmark": 7.67,   # Flat rate buyer pays
    "mercari": 8.0,
    "vinted": 5.0,
    "depop": 7.0,
    "vestiaire": 15.0,
    "therealreal": 12.0,
}

# Platform audience bias relative to Grailed (the archive fashion baseline)
# Grailed buyers are knowledgeable archive fashion buyers — highest willingness to pay
# Other platforms have less knowledgeable audiences → prices reflect that
PLATFORM_BIAS = {
    "grailed": 1.0,
    "ebay": 0.95,
    "ebay_sold": 0.95,
    "poshmark": 0.85,
    "mercari": 0.90,
    "vinted": 0.88,
    "depop": 0.85,
    "vestiaire": 1.10,    # Premium for authentication
    "therealreal": 1.05,
    "mercari_jp": 0.78,   # Japanese domestic prices significantly lower
    "yahoo_jp": 0.78,
}


class PriceNormalizer:
    """Normalize prices across platforms for accurate comp comparison."""

    @staticmethod
    def normalize_to_buyer_cost(
        price: float,
        shipping: Optional[float] = None,
        platform: str = "grailed",
    ) -> float:
        """
        Normalize to total buyer cost (what someone actually paid).
        Uses platform default shipping when actual shipping unknown.
        """
        if price <= 0:
            return price

        platform = platform.lower().replace(" ", "")

        if shipping is None:
            shipping = DEFAULT_SHIPPING.get(platform, 8.0)

        # Vinted adds ~5% buyer protection fee
        if platform == "vinted":
            return price * 1.05 + shipping

        # Vestiaire adds authentication fee
        if platform == "vestiaire":
            return price + shipping + 15.0

        # Most platforms: buyer pays listed price + shipping
        return price + shipping

    @staticmethod
    def normalize_to_market_value(
        buyer_cost: float,
        platform: str = "grailed",
    ) -> float:
        """
        Adjust for platform audience bias.
        Normalizes all prices to "Grailed-equivalent" market value.

        A $200 sale on Poshmark ≈ $170 on Grailed (0.85 bias).
        To compare: divide Poshmark price by 0.85 to get Grailed-equiv.
        Wait — actually the opposite: a Poshmark sale at $200 means
        the Grailed market value is higher (since Poshmark audience pays less).
        So: market_value = buyer_cost / platform_bias
        """
        platform = platform.lower().replace(" ", "")
        bias = PLATFORM_BIAS.get(platform, 1.0)
        if bias <= 0:
            return buyer_cost
        return buyer_cost / bias

    @staticmethod
    def normalize_price(
        price: float,
        shipping: Optional[float] = None,
        platform: str = "grailed",
    ) -> float:
        """Full normalization: raw price → market value."""
        buyer_cost = PriceNormalizer.normalize_to_buyer_cost(price, shipping, platform)
        return PriceNormalizer.normalize_to_market_value(buyer_cost, platform)

    @staticmethod
    def auction_adjustment(
        price: float,
        is_auction: bool = False,
        num_bids: Optional[int] = None,
    ) -> float:
        """
        Normalize auction prices to fixed-price equivalent.
        Auctions typically sell 10-25% below fixed-price market value.
        """
        if not is_auction:
            return price

        if num_bids is not None:
            if num_bids >= 10:
                return price * 1.05   # Hot auction — close to market
            elif num_bids >= 5:
                return price * 1.10
            elif num_bids >= 3:
                return price * 1.12
            else:
                return price * 1.20   # Low competition — well below market
        
        # Default auction uplift when bid count unknown
        return price * 1.12


# ══════════════════════════════════════════════════════════════
# BUNDLE DETECTION
# ══════════════════════════════════════════════════════════════

BUNDLE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\blot\s+of\b",
        r"\blot\b(?!\s*\d+\b)",   # "lot" but not "lot number"
        r"\bbundle\b",
        r"\bset\s+of\s+\d+\b",
        r"\b\d+\s*(?:pc|piece|item)s?\b",
        r"\bcollection\s+of\b",
        r"\b[2-9]x\b",
        r"\bwith\s+(?:matching|extra|bonus)\b",
        r"\+\s*(?:belt|bag|shoes|hat|scarf)\b",
        r"\band\s+(?:belt|bag|shoes|hat|scarf)\b",
        r"\bpair\s+of\s+\d+\b",
    ]
]

# Exceptions: things that look like bundles but aren't
BUNDLE_EXCEPTIONS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bset\s+of\s+eyes\b",      # product names
        r"\bcollection\s+name\b",
        r"\b(?:ss|aw|fw)\d{2}\b.*\bcollection\b",  # "AW05 collection" = season name
    ]
]


def is_bundle(title: str, description: str = "") -> bool:
    """
    Detect if a listing is a bundle/lot of multiple items.
    These should be excluded from comps as they inflate prices.
    """
    text = f"{title} {description}".strip()
    if not text:
        return False

    # Check exceptions first
    for exc in BUNDLE_EXCEPTIONS:
        if exc.search(text):
            return False

    # Check bundle patterns
    for pattern in BUNDLE_PATTERNS:
        if pattern.search(text):
            return True

    return False

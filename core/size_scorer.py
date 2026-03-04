#!/usr/bin/env python3
"""
Size Scorer — Score items based on size desirability/liquidity.

Popular sizes sell faster and command slightly higher prices. This module
detects sizes from listing titles and returns a demand multiplier.
"""

import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger("size_scorer")

# ══════════════════════════════════════════════════════════════════════
# SIZE DEMAND MULTIPLIERS — Tune these based on sold data
# ══════════════════════════════════════════════════════════════════════

FOOTWEAR_DEMAND_EU = {
    39: 0.85,
    40: 0.85,
    41: 1.1,
    42: 1.1,
    43: 1.1,
    44: 1.1,
    45: 1.0,
    46: 0.8,
    47: 0.8,
    48: 0.8,
}

FOOTWEAR_DEMAND_US = {
    6: 0.80,
    6.5: 0.80,
    7: 0.85,
    7.5: 0.85,
    8: 1.0,
    8.5: 1.1,
    9: 1.1,
    9.5: 1.1,
    10: 1.1,
    10.5: 1.1,
    11: 1.05,
    11.5: 1.0,
    12: 0.95,
    13: 0.85,
    14: 0.8,
}

CLOTHING_DEMAND = {
    "XXS": 0.70,
    "XS": 0.75,
    "S": 0.95,
    "M": 1.15,
    "L": 1.05,
    "XL": 0.85,
    "XXL": 0.70,
    "XXXL": 0.65,
}

# Italian sizing → approximate letter mapping
ITALIAN_TO_LETTER = {
    44: "XS", 46: "S", 48: "M", 50: "L", 52: "XL", 54: "XXL", 56: "XXXL",
}

# ══════════════════════════════════════════════════════════════════════
# SIZE DETECTION PATTERNS
# ══════════════════════════════════════════════════════════════════════

# Shoe size patterns
SHOE_EU_PATTERN = re.compile(r'\b(?:EU|eur?)\s*(\d{2}(?:\.\d)?)\b', re.IGNORECASE)
SHOE_US_PATTERN = re.compile(r'\b(?:US|usa?)\s*(\d{1,2}(?:\.\d)?)\b', re.IGNORECASE)
SHOE_UK_PATTERN = re.compile(r'\b(?:UK)\s*(\d{1,2}(?:\.\d)?)\b', re.IGNORECASE)
SHOE_GENERIC_PATTERN = re.compile(r'\bsize\s+(\d{1,2}(?:\.\d)?)\b', re.IGNORECASE)

# Clothing size patterns
CLOTHING_LETTER_PATTERN = re.compile(
    r'\bsize\s+(XXS|XS|S|M|L|XL|XXL|XXXL)\b', re.IGNORECASE
)
CLOTHING_STANDALONE_PATTERN = re.compile(
    r'\b(XXS|XS|XXL|XXXL)\b'  # Only match unambiguous standalone sizes
    r'|(?<!\w)(XL)(?!\w)',  # XL standalone
    re.IGNORECASE
)
ITALIAN_SIZE_PATTERN = re.compile(r'\b(?:size\s+|IT\s*)?(\d{2})\b', re.IGNORECASE)

# Footwear category keywords
FOOTWEAR_KEYWORDS = [
    r'\bshoes?\b', r'\bsneakers?\b', r'\bboots?\b', r'\brunners?\b',
    r'\btrainers?\b', r'\bloafers?\b', r'\bderby\b', r'\bgeobasket\b',
    r'\bramones?\b', r'\bdunks?\b', r'\btabi\b', r'\bkiss\s+boots?\b',
    r'\bplatform\b', r'\bcreepers?\b', r'\bozweego\b', r'\bsneaker\b',
    r'\bfootwear\b',
]
FOOTWEAR_RE = re.compile('|'.join(FOOTWEAR_KEYWORDS), re.IGNORECASE)


def _is_footwear(title: str, category: str = "") -> bool:
    """Detect if the item is footwear."""
    if category and category.lower() in ("shoes", "boots", "sneakers", "footwear"):
        return True
    return bool(FOOTWEAR_RE.search(title))


def _detect_size(title: str, is_shoe: bool) -> Tuple[Optional[str], Optional[float]]:
    """
    Detect size from title.
    Returns (size_string, numeric_value_for_lookup).
    """
    text = title

    if is_shoe:
        # Try EU first
        match = SHOE_EU_PATTERN.search(text)
        if match:
            val = float(match.group(1))
            return (f"EU {val:.0f}" if val == int(val) else f"EU {val}", val)

        # Try US
        match = SHOE_US_PATTERN.search(text)
        if match:
            val = float(match.group(1))
            return (f"US {val:.1f}" if val != int(val) else f"US {int(val)}", val)

        # Try UK
        match = SHOE_UK_PATTERN.search(text)
        if match:
            val = float(match.group(1))
            # Convert UK to US approximately (UK + 1 = US)
            us_val = val + 1
            return (f"UK {val:.0f}", us_val)

        # Generic "size X" for shoes
        match = SHOE_GENERIC_PATTERN.search(text)
        if match:
            val = float(match.group(1))
            if 35 <= val <= 50:  # Likely EU
                return (f"EU {val:.0f}", val)
            elif 5 <= val <= 15:  # Likely US
                return (f"US {int(val)}", val)

    # Clothing sizes
    # Try "size S/M/L" pattern first
    match = CLOTHING_LETTER_PATTERN.search(text)
    if match:
        size = match.group(1).upper()
        return (size, None)

    # Try standalone unambiguous sizes
    match = CLOTHING_STANDALONE_PATTERN.search(text)
    if match:
        size = (match.group(1) or match.group(2)).upper()
        return (size, None)

    # Try Italian sizing (44, 46, 48, etc.)
    # Only check for known Italian sizes to avoid false positives
    for it_match in ITALIAN_SIZE_PATTERN.finditer(text):
        val = int(it_match.group(1))
        if val in ITALIAN_TO_LETTER:
            letter = ITALIAN_TO_LETTER[val]
            return (f"IT {val} ({letter})", None)

    return (None, None)


def score_size(title: str, brand: str = "", category: str = "") -> Tuple[Optional[str], float, str]:
    """
    Score an item based on its size desirability.

    Args:
        title: Item listing title
        brand: Detected brand name (optional)
        category: Item category (optional)

    Returns:
        (detected_size, demand_multiplier, explanation)
    """
    is_shoe = _is_footwear(title, category)
    size_str, numeric_val = _detect_size(title, is_shoe)

    if not size_str:
        return (None, 1.0, "No size detected — neutral score")

    multiplier = 1.0
    explanation = ""

    if is_shoe and numeric_val is not None:
        # Check EU sizing
        if numeric_val >= 35:  # EU range
            eu_size = int(round(numeric_val))
            multiplier = FOOTWEAR_DEMAND_EU.get(eu_size, 1.0)
            if eu_size < 39:
                multiplier = 0.80
            explanation = f"Footwear {size_str}"
        else:  # US range
            us_size = numeric_val
            # Find closest match
            closest = min(FOOTWEAR_DEMAND_US.keys(), key=lambda k: abs(k - us_size))
            if abs(closest - us_size) <= 0.5:
                multiplier = FOOTWEAR_DEMAND_US[closest]
            explanation = f"Footwear {size_str}"
    else:
        # Clothing
        letter_size = size_str.split("(")[-1].rstrip(")") if "(" in size_str else size_str
        letter_size = letter_size.strip().upper()
        multiplier = CLOTHING_DEMAND.get(letter_size, 1.0)
        explanation = f"Clothing {size_str}"

    # Describe demand level
    if multiplier >= 1.1:
        demand_desc = "high demand"
    elif multiplier >= 1.0:
        demand_desc = "average demand"
    elif multiplier >= 0.85:
        demand_desc = "below average demand"
    else:
        demand_desc = "low demand"

    explanation = f"{explanation} — {demand_desc} ({multiplier:.2f}x)"

    logger.debug(f"Size: {size_str} ({multiplier:.2f}x) for '{title[:50]}'")
    return (size_str, multiplier, explanation)


# ══════════════════════════════════════════════════════════════════════
# TESTS
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        # (title, brand, category, expected_size_contains, expected_mult_range)
        ("Rick Owens Geobasket EU 43", "rick owens", "shoes", "43", (1.05, 1.15)),
        ("Rick Owens Ramones EU 39", "rick owens", "shoes", "39", (0.80, 0.90)),
        ("Rick Owens Dunks Size 46", "rick owens", "shoes", "46", (0.75, 0.85)),
        ("Raf Simons Bomber Jacket Size M", "raf simons", "jacket", "M", (1.10, 1.20)),
        ("Helmut Lang Leather Jacket Size XS", "helmut lang", "jacket", "XS", (0.70, 0.80)),
        ("Chrome Hearts Ring Size L", "chrome hearts", "ring", "L", (1.0, 1.10)),
        ("Undercover Jacket XL", "undercover", "jacket", "XL", (0.80, 0.90)),
        ("Rick Owens Kiss Boots US 10", "rick owens", "boots", "US 10", (1.05, 1.15)),
        ("Margiela Tabi Boots EU 41", "maison margiela", "boots", "41", (1.05, 1.15)),
        ("Number Nine Skull Cashmere Sweater", "number nine", "sweater", None, (0.95, 1.05)),
    ]

    print(f"\n{'='*80}")
    print("SIZE SCORER TEST")
    print(f"{'='*80}\n")

    passed = 0
    failed = 0
    for title, brand, cat, expected_size, (low, high) in tests:
        size_str, mult, explanation = score_size(title, brand, cat)
        ok_size = True
        if expected_size:
            ok_size = expected_size.lower() in (size_str or "").lower()
        else:
            ok_size = size_str is None

        ok_mult = low <= mult <= high
        status = "PASS" if (ok_size and ok_mult) else "FAIL"
        emoji = "✅" if status == "PASS" else "❌"

        if status == "PASS":
            passed += 1
        else:
            failed += 1

        print(f"{emoji} {title[:55]:55s}")
        print(f"   Got: {size_str} ({mult:.2f}x) | Expected: {expected_size} ({low}-{high}x)")
        print(f"   {explanation}")
        if not ok_size:
            print(f"   ⚠ Size mismatch!")
        if not ok_mult:
            print(f"   ⚠ Multiplier out of range!")

    print(f"\n{'='*80}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")

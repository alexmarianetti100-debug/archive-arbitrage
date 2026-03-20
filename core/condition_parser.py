#!/usr/bin/env python3
"""
Condition Parser — Parse condition from title/description and return price adjustment.

Detects condition tiers from listing text and applies appropriate price multipliers.
Accounts for brand-specific design language (distressed, destroyed, etc.) and
category-specific condition sensitivity (white sneakers degrade faster than black leather).
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger("condition_parser")

# ══════════════════════════════════════════════════════════════════════
# CONDITION TIERS & MULTIPLIERS
# ══════════════════════════════════════════════════════════════════════

CONDITION_TIERS = {
    "DEADSTOCK": 1.0,        # New with tags, unworn — 95-100% of market
    "NEAR_DEADSTOCK": 0.90,  # Excellent/like new — 85-94% of market
    "GENTLY_USED": 0.75,     # Very good, minimal wear — 70-84% of market
    "USED": 0.55,            # Good, visible wear — 50-69% of market
    "POOR": 0.35,            # Fair, significant wear/damage — 30-49% of market
}

# Patterns for each tier — checked in order from best to worst.
# First match wins, so more specific patterns should come first.
CONDITION_PATTERNS = {
    "DEADSTOCK": [
        r"\bdeadstock\b", r"\b(?:ds|bnwt)\b", r"\bbrand\s+new\s+with\s+tags\b",
        r"\bnwt\b", r"\bnew\s+with\s+tags\b", r"\bunworn\b", r"\bnever\s+worn\b",
        r"\bbrand\s+new\b", r"\btags\s+attached\b",
    ],
    "NEAR_DEADSTOCK": [
        r"\bvnds\b", r"\bpads\b", r"\blike\s+new\b", r"\bworn\s+once\b",
        r"\btried\s+on\b", r"\bnear\s+mint\b", r"\bmint\s+condition\b",
        r"\bpristine\b", r"\bnwot\b", r"\bnew\s+without\s+tags\b",
        r"\bexcellent\s+condition\b",
    ],
    "GENTLY_USED": [
        r"\bgently\s+used\b", r"\blightly\s+worn\b", r"\bworn\s+a\s+few\s+times\b",
        r"\bvery\s+good\s+condition\b", r"\bgreat\s+condition\b",
        r"\bminor\s+wear\b", r"\b9\s*/\s*10\b", r"\b8\s*/\s*10\b",
        r"\bpre-?owned\b",
    ],
    "USED": [
        r"\bshows\s+wear\b", r"\bnormal\s+wear\b",
        r"\b7\s*/\s*10\b", r"\b6\s*/\s*10\b",
        r"\bused\b",
    ],
    "POOR": [
        r"\bbeater\b", r"\bthrashed\b", r"\bwell\s+loved\b", r"\bheavily\s+worn\b",
        r"\bstained?\b", r"\bstains\b", r"\bdamaged?\b", r"\bripped\b", r"\btorn\b", r"\bholes?\b",
        r"\bcracked\b", r"\bsole\s+separation\b", r"\bfaded\b", r"\bpilling\b",
        r"\bfair\s+condition\b", r"\bpoor\s+condition\b",
        r"\b5\s*/\s*10\b", r"\b4\s*/\s*10\b", r"\b3\s*/\s*10\b",
        r"\bmissing\s+(?:button|zipper|hardware)\b", r"\byellowing\b", r"\bodor\b", r"\bsmell\b",
    ],
}

# Compile all patterns
_COMPILED_PATTERNS = {
    tier: [re.compile(p, re.IGNORECASE) for p in patterns]
    for tier, patterns in CONDITION_PATTERNS.items()
}

# ══════════════════════════════════════════════════════════════════════
# CONTEXT-DEPENDENT TERMS — Don't penalize these as damage
# ══════════════════════════════════════════════════════════════════════

# Brands where "distressed/destroyed" is a design feature
DESIGN_LANGUAGE_BRANDS = {
    "rick owens", "raf simons", "helmut lang", "number nine", "number (n)ine",
    "undercover", "maison margiela", "margiela", "julius",
    "carol christian poell", "boris bidjan saberi",
}

DESIGN_LANGUAGE_TERMS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bdistressed\b", r"\bdestroyed\b", r"\bdeconstructed\b",
        r"\braw\s+hem\b", r"\bwaxed\b", r"\bpatina\b",
    ]
]

# ══════════════════════════════════════════════════════════════════════
# CATEGORY-SPECIFIC CONDITION SENSITIVITY
# ══════════════════════════════════════════════════════════════════════

# HIGH sensitivity: condition matters more (1.3x impact)
HIGH_SENSITIVITY_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bwhite\s+sneakers?\b", r"\bwhite\s+(?:leather|canvas)\b",
        r"\bsuede\b", r"\bsilk\b", r"\bcashmere\b",
        r"\blight\s+(?:colored?|fabric)\b", r"\bcream\b", r"\bivory\b",
    ]
]

# LOW sensitivity: condition matters less (0.7x impact)
LOW_SENSITIVITY_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bblack\s+leather\b", r"\bblack\s+boots?\b",
        r"\bsilver\s+(?:jewelry|ring|pendant|bracelet|chain|necklace)\b",
        r"\bsterling\b", r"\b925\b",
        r"\bchrome\s+hearts\b.*\bring\b", r"\bring\b.*\bchrome\s+hearts\b",
        r"\bdark\s+denim\b", r"\bblack\s+denim\b",
    ]
]

# Items that GAIN value from wear
GAINS_VALUE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\braw\s+denim\b", r"\bselvedge\b.*\bfade", r"\bfade[sd]?\b.*\bdenim\b",
        r"\bleather\b.*\bpatina\b", r"\bpatina\b.*\bleather\b",
    ]
]

# ══════════════════════════════════════════════════════════════════════
# SPECIAL PREMIUMS
# ══════════════════════════════════════════════════════════════════════

SPECIAL_PREMIUM_PATTERNS = {
    "sample": (1.3, [
        re.compile(r"\bsample\b", re.IGNORECASE),
        re.compile(r"\brunway\s+piece\b", re.IGNORECASE),
    ]),
    "friends_and_family": (1.2, [
        re.compile(r"\bfriends\s+and\s+family\b", re.IGNORECASE),
        re.compile(r"\bf\s*&\s*f\b", re.IGNORECASE),
    ]),
}


def parse_condition(title: str, description: str = "", brand: str = "", category: str = "") -> Tuple[str, float, str]:
    """
    Parse condition from title and description.

    Args:
        title: Item listing title
        description: Item description (optional)
        brand: Detected brand name (for design language exceptions)
        category: Item category (for sensitivity adjustments)

    Returns:
        (condition_tier, price_multiplier, explanation)
    """
    text = f"{title} {description}".lower()
    brand_lower = brand.lower().strip()
    full_text = f"{title} {description} {category}".lower()

    # Check for design language terms that should NOT be treated as damage
    is_design_brand = brand_lower in DESIGN_LANGUAGE_BRANDS or any(
        b in brand_lower for b in DESIGN_LANGUAGE_BRANDS
    )
    design_terms_found = []
    if is_design_brand:
        for pattern in DESIGN_LANGUAGE_TERMS:
            match = pattern.search(text)
            if match:
                design_terms_found.append(match.group())

    # Check if item gains value from wear (raw denim fades, leather patina)
    gains_value = any(p.search(full_text) for p in GAINS_VALUE_PATTERNS)

    # Detect condition tier
    detected_tier = None
    matched_term = ""

    for tier in ["DEADSTOCK", "NEAR_DEADSTOCK", "GENTLY_USED", "USED", "POOR"]:
        for pattern in _COMPILED_PATTERNS[tier]:
            match = pattern.search(text)
            if match:
                term = match.group()
                # Skip if this is a design language term for this brand
                if is_design_brand and any(dp.search(term) for dp in DESIGN_LANGUAGE_TERMS):
                    continue
                # Skip POOR-tier terms for items that gain value from wear
                # (e.g., "faded" for raw denim is desirable)
                if gains_value and tier == "POOR" and term.strip() in ("faded", "patina"):
                    continue
                detected_tier = tier
                matched_term = term
                break
        if detected_tier:
            break

    # Default: if nothing detected, assume USED (conservative — unstated condition
    # is a red flag; legitimate sellers state condition explicitly)
    if not detected_tier:
        detected_tier = "USED"
        matched_term = "no condition stated (conservative default)"

    base_multiplier = CONDITION_TIERS[detected_tier]

    if gains_value and detected_tier in ("USED", "GENTLY_USED"):
        base_multiplier = max(base_multiplier, 0.85)
        matched_term += " (gains value from wear)"

    # Apply category sensitivity
    sensitivity = 1.0
    sensitivity_note = ""

    if any(p.search(full_text) for p in HIGH_SENSITIVITY_PATTERNS):
        sensitivity = 1.3
        sensitivity_note = "high condition sensitivity"
    elif any(p.search(full_text) for p in LOW_SENSITIVITY_PATTERNS):
        sensitivity = 0.7
        sensitivity_note = "low condition sensitivity"

    # Adjust multiplier based on sensitivity
    # For items below deadstock, increase the penalty for high-sensitivity items
    # and decrease it for low-sensitivity items
    if detected_tier != "DEADSTOCK":
        condition_penalty = 1.0 - base_multiplier  # How much we're penalizing
        adjusted_penalty = condition_penalty * sensitivity
        final_multiplier = 1.0 - adjusted_penalty
    else:
        final_multiplier = base_multiplier

    # Apply special premiums
    premium_note = ""
    for premium_name, (premium_mult, patterns) in SPECIAL_PREMIUM_PATTERNS.items():
        if any(p.search(text) for p in patterns):
            final_multiplier *= premium_mult
            premium_note = f" + {premium_name} premium ({premium_mult}x)"
            break

    # Clamp
    final_multiplier = max(0.1, min(2.0, final_multiplier))

    # Build explanation
    parts = [f"{detected_tier} ({matched_term})"]
    if design_terms_found:
        parts.append(f"design language ignored: {', '.join(design_terms_found)}")
    if sensitivity_note:
        parts.append(sensitivity_note)
    if premium_note:
        parts.append(premium_note.strip())
    explanation = f"{final_multiplier:.2f}x — {'; '.join(parts)}"

    logger.debug(f"Condition: {explanation} for '{title[:50]}'")
    return (detected_tier, final_multiplier, explanation)


# ══════════════════════════════════════════════════════════════════════
# TESTS
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        # (title, description, brand, category, expected_tier, expected_mult_range)
        ("Rick Owens Geobasket BNWT", "", "rick owens", "shoes", "DEADSTOCK", (0.95, 1.05)),
        ("Raf Simons Bomber Worn Once", "", "raf simons", "jacket", "NEAR_DEADSTOCK", (0.85, 0.95)),
        ("Helmut Lang Jacket Gently Used Minor Wear", "", "helmut lang", "jacket", "GENTLY_USED", (0.65, 0.75)),
        ("Chrome Hearts Ring Used Shows Wear", "", "chrome hearts", "ring", "USED", (0.6, 0.8)),  # low sensitivity for silver
        ("Beater Rick Owens Ramones Thrashed", "", "rick owens", "shoes", "POOR", (0.25, 0.35)),
        # Design language — distressed should NOT penalize for Rick Owens
        ("Rick Owens Distressed Leather Jacket", "", "rick owens", "jacket", "GENTLY_USED", (0.65, 0.75)),
        # Sample premium
        ("Raf Simons Sample Bomber Jacket VNDS", "", "raf simons", "jacket", "NEAR_DEADSTOCK", (1.1, 1.25)),
        # High sensitivity — white sneakers
        ("Rick Owens White Sneakers Used Shows Wear", "", "rick owens", "shoes", "USED", (0.3, 0.45)),
        # Low sensitivity — black leather
        ("Rick Owens Black Leather Jacket Used", "", "rick owens", "jacket", "USED", (0.6, 0.75)),
        # Raw denim gains value
        ("APC Raw Denim Jeans Faded", "", "apc", "pants", "GENTLY_USED", (0.8, 0.95)),
    ]

    print(f"\n{'='*80}")
    print("CONDITION PARSER TEST")
    print(f"{'='*80}\n")

    passed = 0
    failed = 0
    for title, desc, brand, cat, expected_tier, (low, high) in tests:
        tier, mult, explanation = parse_condition(title, desc, brand, cat)
        ok_tier = tier == expected_tier
        ok_mult = low <= mult <= high
        status = "PASS" if (ok_tier and ok_mult) else "FAIL"
        emoji = "✅" if status == "PASS" else "❌"

        if status == "PASS":
            passed += 1
        else:
            failed += 1

        print(f"{emoji} {title[:55]:55s}")
        print(f"   Got: {tier} ({mult:.2f}x) | Expected: {expected_tier} ({low}-{high}x)")
        print(f"   {explanation}")
        if not ok_tier:
            print(f"   ⚠ Tier mismatch!")
        if not ok_mult:
            print(f"   ⚠ Multiplier out of range!")

    print(f"\n{'='*80}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")

#!/usr/bin/env python3
"""
Season Detector — Detect season codes and collection names, return value tier multipliers.

Identifies specific seasons/collections from listing text and applies value multipliers
based on how desirable that season is in the archive market. S-tier collections from
designers like Raf Simons, Rick Owens, and Undercover command significant premiums.
"""

import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger("season_detector")

# ══════════════════════════════════════════════════════════════════════
# SEASON CODE PATTERNS
# ══════════════════════════════════════════════════════════════════════

SEASON_CODE_PATTERNS = [
    # SS06, FW14, AW03, F/W 2006, S/S '14
    re.compile(r'\b(SS|FW|AW|F/W|S/S)\s*[\'"]?\s*(\d{2,4})\b', re.IGNORECASE),
    # Spring Summer 2006, Fall Winter 2003
    re.compile(
        r'\b(spring|summer|fall|autumn|winter)\s*(summer|winter)?\s*[\'"]?(\d{2,4})\b',
        re.IGNORECASE
    ),
    # Pre-fall 2014, Resort 2020, Cruise 2019
    re.compile(r'\b(pre-?fall|resort|cruise)\s*(\d{2,4})\b', re.IGNORECASE),
]

# Map text seasons to standard codes
SEASON_TEXT_MAP = {
    "spring summer": "SS", "spring": "SS", "summer": "SS",
    "fall winter": "FW", "fall": "FW", "autumn": "FW", "winter": "FW",
    "pre-fall": "PF", "prefall": "PF", "resort": "RS", "cruise": "RS",
}


def _normalize_season(raw_season: str, raw_year: str) -> str:
    """Normalize a season string to standard format like 'FW06' or 'SS14'."""
    season_upper = raw_season.upper().replace("/", "").replace("'", "").strip()

    # Handle text seasons
    season_lower = raw_season.lower().strip()
    for text, code in SEASON_TEXT_MAP.items():
        if text in season_lower:
            season_upper = code
            break

    # Normalize year to 2-digit
    year = raw_year.strip().replace("'", "")
    if len(year) == 4:
        year = year[2:]

    return f"{season_upper}{year}"


def _extract_season_code(text: str) -> Optional[str]:
    """Extract the first season code found in text."""
    for pattern in SEASON_CODE_PATTERNS:
        match = pattern.search(text)
        if match:
            groups = match.groups()
            if len(groups) == 2:
                return _normalize_season(groups[0], groups[1])
            elif len(groups) == 3:
                # spring summer 2006 → combine first two
                season_text = f"{groups[0]} {groups[1] or ''}".strip()
                return _normalize_season(season_text, groups[2])
    return None


def _extract_year_from_code(code: str) -> Optional[int]:
    """Extract full year from a season code like FW06 → 2006."""
    match = re.search(r'(\d{2,4})$', code)
    if not match:
        return None
    year_str = match.group(1)
    if len(year_str) == 2:
        year = int(year_str)
        return 2000 + year if year < 50 else 1900 + year
    return int(year_str)


# ══════════════════════════════════════════════════════════════════════
# COLLECTION NAME DETECTION — Verified from Wikipedia/Vogue
# ══════════════════════════════════════════════════════════════════════

# Each entry: (collection_name, multiplier, keyword_patterns, optional_season_code)
# keyword_patterns are checked against the full text (title + description)

BRAND_COLLECTIONS = {
    "rick owens": {
        "s_tier": [  # 1.8x
            ("FW02 Sparrows", "FW02", [r"\bsparrows?\b", r"\bfw\s*0?2\b"]),
            ("FW05 Moog", "FW05", [r"\bmoog\b", r"\bfw\s*0?5\b"]),
            ("FW06 Dustulator", "FW06", [r"\bdustulator\b", r"\bfw\s*0?6\b"]),
            ("FW09 Crust", "FW09", [r"\bcrust\b.*\bfw\s*0?9\b", r"\bfw\s*0?9\b.*\bcrust\b"]),
            ("FW15 Sphinx", "FW15", [r"\bsphinx\b"]),
            ("FW19 Larry", "FW19", [r"\blarry\b.*\bfw\s*19\b", r"\bfw\s*19\b.*\blarry\b"]),
            ("SS14 Adidas", "SS14", [r"\bss\s*14\b.*\badidas\b", r"\bstep\s+dancer\b"]),
        ],
        "a_tier": [  # 1.3x
            ("SS02 Vapor", "SS02", [r"\bvapor\b"]),
            ("SS16 Cyclops", "SS16", [r"\bcyclops\b"]),
            ("SS19 Babel", "SS19", [r"\bbabel\b", r"\bconstructivist\b"]),
            ("FW24 Porterville", "FW24", [r"\bporterville\b"]),
        ],
    },
    "raf simons": {
        "s_tier": [  # 2.0x
            ("FW01 Riot Riot Riot", "FW01", [
                r"\briot\b", r"\bfw\s*0?1\b", r"\bfall\s+winter\s+2001\b",
            ]),
            ("SS02 Woe Onto Those", "SS02", [
                r"\bss\s*0?2\b", r"\bspring\s+summer\s+2002\b",
                r"\bwoe\s+onto\b", r"\bfear\s+generation\b",
            ]),
            ("FW03 Closer", "FW03", [
                r"\bcloser\b", r"\bfw\s*0?3\b", r"\bpeter\s+saville\b",
                r"\bjoy\s+division\b", r"\bunknown\s+pleasures\b",
            ]),
            ("FW98 Radioactivity", "FW98", [
                r"\bradioactivity\b", r"\bfw\s*98\b", r"\bkraftwerk\b",
            ]),
        ],
        "a_tier": [  # 1.5x
            ("AW04 Waves", "AW04", [r"\bwaves\b.*\baw\s*0?4\b", r"\baw\s*0?4\b"]),
            ("SS05 History of My World", "SS05", [r"\bpoltergeist\b", r"\bhistory\s+of\s+my\s+world\b"]),
            ("FW14 Sterling Ruby", "FW14", [r"\bsterling\s+ruby\b"]),
            ("SS17 Mapplethorpe", "SS17", [r"\bmapplethorpe\b"]),
            ("AW05 Virginia Creeper", "AW05", [r"\bvirginia\s+creeper\b"]),
            ("Consumed", None, [r"\bconsumed\b"]),
        ],
    },
    "number nine": {
        "s_tier": [  # 2.0x
            ("AW05 The High Streets", "AW05", [
                r"\bhigh\s+streets?\b", r"\baw\s*0?5\b",
            ]),
            ("Kurt Cobain", None, [r"\bkurt\s+cobain\b"]),
            ("Skull Cashmere", None, [r"\bskull\s+cashmere\b"]),
        ],
    },
    "number (n)ine": {
        "s_tier": [  # 2.0x
            ("AW05 The High Streets", "AW05", [r"\bhigh\s+streets?\b"]),
            ("Kurt Cobain", None, [r"\bkurt\s+cobain\b"]),
            ("Skull Cashmere", None, [r"\bskull\s+cashmere\b"]),
        ],
    },
    "undercover": {
        "s_tier": [  # 1.8x
            ("AW03 Scab", "AW03", [r"\bscab\b"]),
            ("SS03 Less But Better", "SS03", [r"\bless\s+but\s+better\b"]),
            ("AW02 Arts and Crafts", "AW02", [r"\barts\s+and\s+crafts\b"]),
        ],
    },
    "jean paul gaultier": {
        "a_tier": [  # 1.4x-1.5x
            ("Cyberbaba", None, [r"\bcyberbaba\b"]),
        ],
    },
    "gaultier": {
        "a_tier": [
            ("Cyberbaba", None, [r"\bcyberbaba\b"]),
        ],
    },
}

# Multiplier values per tier
TIER_MULTIPLIERS = {
    "s_tier": {
        "rick owens": 1.8,
        "raf simons": 2.0,
        "number nine": 2.0,
        "number (n)ine": 2.0,
        "undercover": 1.8,
    },
    "a_tier": {
        "rick owens": 1.3,
        "raf simons": 1.5,
        "jean paul gaultier": 1.4,
        "gaultier": 1.4,
    },
}

# ══════════════════════════════════════════════════════════════════════
# ERA-BASED VALUE MULTIPLIERS
# ══════════════════════════════════════════════════════════════════════

ERA_MULTIPLIERS = {
    "rick owens": [
        # Pre-2010 Rick Owens = A-tier minimum
        (None, 2009, 1.3, "Pre-2010 Rick Owens"),
    ],
    "raf simons": [
        # FW98-SS02 era
        (1998, 2002, 1.5, "FW98-SS02 era Raf Simons"),
    ],
    "chrome hearts": [
        (None, 1999, 1.4, "1990s Chrome Hearts"),
        (2000, 2009, 1.2, "2000s Chrome Hearts"),
    ],
    "helmut lang": [
        (1996, 2003, 1.5, "Peak Helmut Lang era"),
        (2004, 2005, 1.2, "Final Helmut Lang era"),
    ],
    "jean paul gaultier": [
        (None, 1999, 1.5, "1980s-1990s JPG"),
        (2020, None, 1.2, "Post-retirement JPG (archive premium)"),
    ],
    "gaultier": [
        (None, 1999, 1.5, "1980s-1990s JPG"),
        (2020, None, 1.2, "Post-retirement JPG (archive premium)"),
    ],
}


def detect_season_value(title: str, brand: str, description: str = "") -> Tuple[Optional[str], float, str]:
    """
    Detect season/collection and return a value multiplier.

    Args:
        title: Item listing title
        brand: Detected brand name
        description: Item description (optional)

    Returns:
        (season_code_or_name, value_multiplier, explanation)
    """
    text = f"{title} {description}".lower()
    brand_lower = brand.lower().strip()

    # Extract season code
    season_code = _extract_season_code(text)
    year = None
    if season_code:
        year = _extract_year_from_code(season_code)

    # Also try standalone year extraction for era-based detection
    if year is None:
        year_match = re.search(r'\b(19[89]\d|20[0-2]\d)\b', text)
        if year_match:
            year = int(year_match.group(1))

    best_multiplier = 1.0
    best_name = season_code
    best_explanation = ""

    # Check for named collection matches
    brand_collections = BRAND_COLLECTIONS.get(brand_lower, {})
    if not brand_collections:
        # Try partial match
        for key in BRAND_COLLECTIONS:
            if key in brand_lower or brand_lower in key:
                brand_collections = BRAND_COLLECTIONS[key]
                brand_lower_for_tier = key
                break
        else:
            brand_lower_for_tier = brand_lower
    else:
        brand_lower_for_tier = brand_lower

    collection_matched = False

    for tier_name, collections in brand_collections.items():
        tier_mult = TIER_MULTIPLIERS.get(tier_name, {}).get(brand_lower_for_tier, 1.3)

        for coll_name, coll_season, patterns in collections:
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    if tier_mult > best_multiplier:
                        best_multiplier = tier_mult
                        best_name = coll_name
                        best_explanation = f"{tier_name.replace('_', '-').upper()} collection: {coll_name} ({tier_mult:.1f}x)"
                        collection_matched = True
                    break

    # If a named collection was matched, add the +30% bonus for named reference
    # (already included in the tier multiplier, but log it)

    # Check era-based multipliers if no specific collection matched
    if not collection_matched and year:
        era_configs = ERA_MULTIPLIERS.get(brand_lower, [])
        if not era_configs:
            for key in ERA_MULTIPLIERS:
                if key in brand_lower or brand_lower in key:
                    era_configs = ERA_MULTIPLIERS[key]
                    break

        for start_year, end_year, era_mult, era_desc in era_configs:
            start_ok = start_year is None or year >= start_year
            end_ok = end_year is None or year <= end_year
            if start_ok and end_ok and era_mult > best_multiplier:
                best_multiplier = era_mult
                best_explanation = f"Era premium: {era_desc} ({era_mult:.1f}x)"

    # If we have a season code but no special value, just note it
    if season_code and not best_explanation:
        best_explanation = f"Season: {season_code} (no special premium)"

    if not best_name and not best_explanation:
        best_explanation = "No season/collection detected"

    final_name = best_name or season_code

    logger.debug(f"Season: {final_name} ({best_multiplier:.1f}x) — {best_explanation} for '{title[:50]}'")
    return (final_name, best_multiplier, best_explanation)


# ══════════════════════════════════════════════════════════════════════
# TESTS
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        # (title, brand, expected_name_contains, expected_mult_range)
        ("Raf Simons Riot Riot Riot Bomber FW01", "raf simons", "Riot", (1.8, 2.2)),
        ("Raf Simons Peter Saville Joy Division Sweater FW03", "raf simons", "Closer", (1.8, 2.2)),
        ("Raf Simons Virginia Creeper Parka", "raf simons", "Virginia", (1.3, 1.6)),
        ("Raf Simons Consumed Hoodie", "raf simons", "Consumed", (1.3, 1.6)),
        ("Rick Owens Dustulator Dunk Sneakers FW06", "rick owens", "Dustulator", (1.6, 2.0)),
        ("Rick Owens Sphinx Leather Jacket FW15", "rick owens", "Sphinx", (1.6, 2.0)),
        ("Rick Owens Geobasket SS08", "rick owens", "SS08", (1.2, 1.4)),
        ("Undercover Scab Jacket AW03", "undercover", "Scab", (1.6, 2.0)),
        ("Number Nine Kurt Cobain Grunge Jacket", "number nine", "Kurt", (1.8, 2.2)),
        ("Jean Paul Gaultier Cyberbaba Mesh Top", "jean paul gaultier", "Cyberbaba", (1.3, 1.5)),
        ("Chrome Hearts Ring 1995", "chrome hearts", None, (1.3, 1.5)),
        ("Rick Owens Leather Jacket", "rick owens", None, (0.9, 1.1)),
        ("Raf Simons FW99 Bomber", "raf simons", "FW99", (1.3, 1.6)),
    ]

    print(f"\n{'='*80}")
    print("SEASON DETECTOR TEST")
    print(f"{'='*80}\n")

    passed = 0
    failed = 0
    for title, brand, expected_name, (low, high) in tests:
        name, mult, explanation = detect_season_value(title, brand)
        ok_name = True
        if expected_name:
            ok_name = expected_name.lower() in (name or "").lower()
        else:
            ok_name = True  # No specific name expected

        ok_mult = low <= mult <= high
        status = "PASS" if (ok_name and ok_mult) else "FAIL"
        emoji = "✅" if status == "PASS" else "❌"

        if status == "PASS":
            passed += 1
        else:
            failed += 1

        print(f"{emoji} {title[:55]:55s}")
        print(f"   Got: {name} ({mult:.1f}x) | Expected: {expected_name} ({low}-{high}x)")
        print(f"   {explanation}")
        if not ok_name:
            print(f"   ⚠ Name mismatch!")
        if not ok_mult:
            print(f"   ⚠ Multiplier out of range!")

    print(f"\n{'='*80}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")

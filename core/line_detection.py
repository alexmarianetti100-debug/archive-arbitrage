#!/usr/bin/env python3
"""
Line Detection — Mainline vs Diffusion/Secondary Line Detection.

Detects whether an item is mainline or a diffusion/secondary line for a brand.
Returns a line tier name, price multiplier, and explanation.

Diffusion lines are typically mass-market versions that resell for significantly
less than mainline pieces. Correctly identifying these prevents overvaluing items.
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger("line_detection")

# ══════════════════════════════════════════════════════════════════════
# BRAND → LINE MAPPINGS
# Each brand has a list of (line_name, multiplier, patterns) tuples.
# Order matters: first match wins. Put more specific patterns first.
# ══════════════════════════════════════════════════════════════════════

BRAND_LINES = {
    "rick owens": [
        # Collabs first (most specific)
        ("Rick Owens x Adidas", 1.15, [
            r"rick\s*owens\s*(?:x\s*)?adidas", r"\bro\s*x\s*adidas\b",
        ]),
        # Diffusion lines
        ("DRKSHDW", 0.35, [
            r"\bdrkshdw\b", r"\bdark\s*shadow\b", r"\bdrkshdw\s+by\s+rick\s+owens\b",
        ]),
        ("Lilies", 0.45, [
            r"\blilies\b", r"\brick\s+owens\s+lilies\b",
        ]),
        ("HUNRICKOWENS", 0.40, [
            r"\bhunrickowens\b", r"\bhun\s+rick\s+owens\b", r"\bpalais\s+royal\b",
        ]),
        # Mainline is the fallback
        ("Mainline", 1.0, []),
    ],
    "raf simons": [
        # Collabs
        ("Raf Simons x Fred Perry", 0.5, [
            r"\braf\s+simons\s+fred\s+perry\b", r"\bfred\s+perry\s+raf\b",
        ]),
        ("Raf Simons x Adidas", 0.3, [
            r"\braf\s+simons\s+adidas\b", r"\badidas\s+by\s+raf\b",
            r"\bozweego\b", r"\bstan\s+smith\s+raf\b",
        ]),
        # Diffusion
        ("Raf by Raf Simons", 0.25, [
            r"\braf\s+by\s+raf\b", r"\braf\s+by\s+raf\s+simons\b",
        ]),
        ("Raf Simons 1995", 0.6, [
            r"\braf\s+simons\s+1995\b",
        ]),
        ("Mainline", 1.0, []),
    ],
    "maison margiela": [
        # MM6 FIRST — must check before Martin era since "MM6 Maison Martin Margiela" contains both
        ("MM6", 0.2, [
            r"\bmm6\b", r"\bmm6\s+maison\b",
        ]),
        # Martin era (most valuable — pre-2009)
        ("Martin Margiela Era", 2.5, [
            r"\bmaison\s+martin\s+margiela\b", r"\bmmm\s+vintage\b",
        ]),
        # Artisanal / Line 1
        ("Artisanal (Line 0/1)", 2.5, [
            r"\bartisanal\b", r"\bline\s*[01]\b",
        ]),
        # Numbered lines
        ("Line 10", 1.0, [r"\bline\s*10\b"]),
        ("Line 14", 1.0, [r"\bline\s*14\b"]),
        ("Line 22", 1.0, [r"\bline\s*22\b"]),
        # Galliano era mainline
        ("Mainline", 1.0, []),
    ],
    "margiela": [
        # MM6 FIRST
        ("MM6", 0.2, [
            r"\bmm6\b",
        ]),
        ("Martin Margiela Era", 2.5, [
            r"\bmaison\s+martin\s+margiela\b", r"\bmmm\s+vintage\b",
        ]),
        ("Artisanal (Line 0/1)", 2.5, [
            r"\bartisanal\b", r"\bline\s*[01]\b",
        ]),
        ("Mainline", 1.0, []),
    ],
    "helmut lang": [
        # Original era detection via keywords
        ("Original Era (Archive)", 3.0, [
            r"\bvintage\s+helmut\s+lang\b", r"\bhelmut\s+lang\s+archive\b",
            r"\bmade\s+in\s+italy\b", r"\bhelmut\s+lang\s+austria\b",
        ]),
        ("Contemporary", 1.0, []),
    ],
    "dior": [
        # Hedi era
        ("Dior Homme (Hedi Era)", 2.5, [
            r"\bdior\s+homme\s+hedi\b", r"\bhedi\s+slimane\s+dior\b",
        ]),
        # KVA era
        ("Dior Homme (KVA Era)", 1.3, [
            r"\bkris\s+van\s+assche\b",
        ]),
        # Kim Jones era
        ("Dior Men", 1.0, [
            r"\bdior\s+men\b",
        ]),
        # Generic dior homme — default to mainline
        ("Dior Homme", 1.0, [
            r"\bdior\s+homme\b",
        ]),
        ("Mainline", 1.0, []),
    ],
    "dior homme": [
        ("Hedi Era", 2.5, [
            r"\bhedi\b", r"\bhedi\s+slimane\b",
        ]),
        ("KVA Era", 1.3, [
            r"\bkris\s+van\s+assche\b",
        ]),
        ("Mainline", 1.0, []),
    ],
    "jean paul gaultier": [
        ("JPG Jeans", 0.3, [r"\bjpg\s+jeans\b"]),
        ("Gaultier2", 0.2, [r"\bgaultier\s*2\b", r"\bgaultier[²2]\b"]),
        ("Junior Gaultier", 0.15, [r"\bjunior\s+gaultier\b"]),
        ("Mainline", 1.0, []),
    ],
    "gaultier": [
        ("JPG Jeans", 0.3, [r"\bjpg\s+jeans\b"]),
        ("Gaultier2", 0.2, [r"\bgaultier\s*2\b", r"\bgaultier[²2]\b"]),
        ("Junior Gaultier", 0.15, [r"\bjunior\s+gaultier\b"]),
        ("Mainline", 1.0, []),
    ],
    "comme des garcons": [
        # Play is the lowest — check first since it's most common diffusion
        ("CDG Play", 0.1, [
            r"\bcdg\s+play\b", r"\bcomme\s+des\s+garcons\s+play\b",
            r"\bplay\s+comme\b",
        ]),
        # Homme Plus before Homme (more specific)
        ("Homme Plus", 1.0, [
            r"\bhomme\s+plus\b", r"\bcdg\s+homme\s+plus\b",
            r"\bcomme\s+des\s+garcons\s+homme\s+plus\b",
        ]),
        ("Junya Watanabe", 1.0, [
            r"\bjunya\s+watanabe\b",
        ]),
        ("CDG Homme", 0.7, [
            r"\bcdg\s+homme\b", r"\bcomme\s+des\s+garcons\s+homme\b",
        ]),
        ("CDG Shirt", 0.5, [
            r"\bcdg\s+shirt\b", r"\bcomme\s+des\s+garcons\s+shirt\b",
        ]),
        ("CDG Noir", 0.4, [
            r"\bcdg\s+noir\b", r"\bcomme\s+des\s+garcons\s+noir\b",
        ]),
        ("Mainline", 1.0, []),
    ],
    "cdg": [
        ("CDG Play", 0.1, [
            r"\bcdg\s+play\b", r"\bplay\b",
        ]),
        ("Homme Plus", 1.0, [
            r"\bhomme\s+plus\b",
        ]),
        ("CDG Homme", 0.7, [
            r"\bcdg\s+homme\b", r"\bhomme\b",
        ]),
        ("CDG Shirt", 0.5, [r"\bshirt\b"]),
        ("Mainline", 1.0, []),
    ],
    "vivienne westwood": [
        ("Gold Label", 1.0, [r"\bgold\s+label\b"]),
        ("MAN", 0.5, [r"\bwestwood\s+man\b"]),
        ("Red Label", 0.4, [r"\bred\s+label\b"]),
        ("Anglomania", 0.3, [r"\banglomania\b"]),
        # Licensed generic VW — but keep jewelry at 1.0x
        ("Mainline", 1.0, []),
    ],
    "yohji yamamoto": [
        ("Pour Homme", 1.0, [
            r"\bpour\s+homme\b", r"\byohji\s+yamamoto\s+pour\s+homme\b",
        ]),
        ("Y's", 0.5, [
            r"\by'?s\b", r"\by'?s\s+yohji\b", r"\bys\s+for\s+men\b",
        ]),
        ("Y-3", 0.4, [
            r"\by-?3\b",
        ]),
        ("Ground Y", 0.25, [r"\bground\s+y\b"]),
        ("Regulation", 0.2, [r"\bregulation\b"]),
        ("Mainline", 1.0, []),
    ],
}

# ══════════════════════════════════════════════════════════════════════
# FAST-FASHION COLLAB DETECTION
# These collabs with designer brands are NOT worth archive prices.
# Detected before brand-specific checks. Returns a very low multiplier.
# ══════════════════════════════════════════════════════════════════════

FAST_FASHION_COLLAB_PATTERNS = [
    (r"\bh\s*&\s*m\b", "H&M Collab", 0.05),
    (r"\bhm\b", "H&M Collab", 0.05),
    (r"\buniqlo\b", "Uniqlo Collab", 0.08),
    (r"\btarget\b", "Target Collab", 0.05),
    (r"\bzara\b", "Zara", 0.05),
    (r"\bforever\s*21\b", "Forever 21", 0.03),
    (r"\basos\b", "ASOS", 0.05),
    (r"\bgap\b(?!.*\byeezy\b)", "Gap Collab", 0.05),
]

# Year extraction pattern
YEAR_PATTERN = re.compile(r'\b(19[89]\d|20[0-2]\d)\b')


def _extract_year(title: str, description: str = "") -> int | None:
    """Extract a 4-digit year from title or description."""
    text = f"{title} {description}"
    match = YEAR_PATTERN.search(text)
    if match:
        return int(match.group(1))
    return None


def _is_jewelry_or_accessory(title: str) -> bool:
    """Check if the item is jewelry or an accessory (for VW exception)."""
    keywords = [
        r"\bnecklace\b", r"\bpendant\b", r"\bring\b", r"\bbracelet\b",
        r"\bearring\b", r"\borb\b", r"\bjewelry\b", r"\bbrooch\b",
        r"\bchain\b", r"\bchoker\b",
    ]
    text = title.lower()
    return any(re.search(kw, text) for kw in keywords)


def detect_line(title: str, brand: str, description: str = "") -> Tuple[str, float, str]:
    """
    Detect whether an item is mainline or a diffusion/secondary line.

    Args:
        title: Item listing title
        brand: Detected brand name
        description: Item description (optional)

    Returns:
        (line_name, price_multiplier, explanation)
    """
    brand_lower = brand.lower().strip()
    text = f"{title} {description}".lower()
    year = _extract_year(title, description)

    # ── Fast-fashion collab check (universal, runs first) ──
    for pattern, collab_name, mult in FAST_FASHION_COLLAB_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            explanation = f"{collab_name} (0.05x) — fast-fashion collab, not archive"
            logger.debug(f"Fast-fashion collab detected: {explanation}")
            return (collab_name, mult, explanation)

    # Find matching brand config
    lines = BRAND_LINES.get(brand_lower)
    if not lines:
        # Try partial match
        for key in BRAND_LINES:
            if key in brand_lower or brand_lower in key:
                lines = BRAND_LINES[key]
                break

    if not lines:
        return ("Unknown", 1.0, "Brand not in line detection database")

    # Check each line's patterns (first match wins)
    for line_name, multiplier, patterns in lines:
        if not patterns:
            # This is the fallback/mainline entry
            continue
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                # Apply year-based adjustments
                adjusted_mult, adj_explanation = _apply_year_adjustments(
                    brand_lower, line_name, multiplier, year
                )
                explanation = f"{line_name} ({adjusted_mult:.2f}x)"
                if adj_explanation:
                    explanation += f" — {adj_explanation}"
                logger.debug(f"Line detected: {explanation} for '{title[:50]}'")
                return (line_name, adjusted_mult, explanation)

    # No diffusion pattern matched — it's mainline
    # Apply year-based adjustments for mainline too
    fallback_name = "Mainline"
    fallback_mult = 1.0
    for line_name, multiplier, patterns in lines:
        if not patterns:
            fallback_name = line_name
            fallback_mult = multiplier
            break

    adjusted_mult, adj_explanation = _apply_year_adjustments(
        brand_lower, fallback_name, fallback_mult, year
    )

    # Vivienne Westwood: generic VW without line indicator = licensed (0.1x)
    # EXCEPT for jewelry/accessories which are the main collectible
    if brand_lower == "vivienne westwood":
        has_line_indicator = any(
            re.search(p, text, re.IGNORECASE)
            for _, _, patterns in lines
            for p in patterns
        )
        if not has_line_indicator and not _is_jewelry_or_accessory(title):
            return ("Licensed/Generic", 0.1, "No line indicator — likely licensed product (0.10x)")

    explanation = f"{fallback_name} ({adjusted_mult:.2f}x)"
    if adj_explanation:
        explanation += f" — {adj_explanation}"

    return (fallback_name, adjusted_mult, explanation)


def _apply_year_adjustments(brand: str, line_name: str, multiplier: float, year: int | None) -> Tuple[float, str]:
    """Apply year-based multiplier adjustments."""
    if year is None:
        return (multiplier, "")

    # Rick Owens DRKSHDW: early era (2005-2008) gets 0.6x instead of 0.35x
    if brand == "rick owens" and "DRKSHDW" in line_name and 2005 <= year <= 2008:
        return (0.6, f"Early DRKSHDW ({year})")

    # Helmut Lang: year-based era detection
    if brand == "helmut lang":
        if year <= 2005:
            return (3.0, f"Original Helmut Lang era ({year})")
        else:
            return (1.0, f"Contemporary Helmut Lang ({year})")

    # Dior Homme: era detection by year
    if brand in ("dior", "dior homme"):
        if 2000 <= year <= 2007:
            return (2.5, f"Hedi Slimane era ({year})")
        elif 2007 < year <= 2018:
            return (1.3, f"Kris Van Assche era ({year})")
        elif year > 2018:
            return (1.0, f"Kim Jones era ({year})")

    # Maison Margiela: Martin era pre-2009
    if brand in ("maison margiela", "margiela"):
        if year < 2009 and "MM6" not in line_name:
            return (max(multiplier, 2.0), f"Martin Margiela era ({year})")

    return (multiplier, "")


# ══════════════════════════════════════════════════════════════════════
# TESTS
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        # (title, brand, expected_line_contains, expected_mult_range)
        ("Rick Owens DRKSHDW Ramones Low", "rick owens", "DRKSHDW", (0.3, 0.4)),
        ("Rick Owens Geobasket Black Leather", "rick owens", "Mainline", (0.9, 1.1)),
        ("Rick Owens DRKSHDW Waxed Detroit 2006", "rick owens", "DRKSHDW", (0.55, 0.65)),
        ("Raf Simons Ozweego Bunny Black", "raf simons", "Adidas", (0.25, 0.35)),
        ("Raf by Raf Simons Oversized Shirt", "raf simons", "Raf by", (0.2, 0.3)),
        ("Raf Simons Consumed Hoodie FW03", "raf simons", "Mainline", (0.9, 1.1)),
        ("MM6 Maison Margiela Japanese Tote Bag", "maison margiela", "MM6", (0.15, 0.25)),
        ("Maison Martin Margiela Artisanal Vest 2004", "maison margiela", "Artisanal", (2.0, 3.0)),
        ("Helmut Lang Vintage Bondage Strap Jacket 1998", "helmut lang", "Original", (2.5, 3.5)),
        ("Helmut Lang Modern Crewneck Tee", "helmut lang", "Contemporary", (0.9, 1.1)),
        ("CDG Play Heart Tee", "comme des garcons", "Play", (0.05, 0.15)),
        ("Comme Des Garcons Homme Plus FW05 Jacket", "comme des garcons", "Homme Plus", (0.9, 1.1)),
        ("Jean Paul Gaultier Mesh Top", "jean paul gaultier", "Mainline", (0.9, 1.1)),
        ("Junior Gaultier Polo Shirt", "jean paul gaultier", "Junior", (0.1, 0.2)),
        ("Vivienne Westwood Orb Necklace", "vivienne westwood", "Mainline", (0.9, 1.1)),
        ("Vivienne Westwood Hoodie", "vivienne westwood", "Licensed", (0.05, 0.15)),
        ("Vivienne Westwood Gold Label Corset", "vivienne westwood", "Gold", (0.9, 1.1)),
        ("Yohji Yamamoto Y-3 Sneakers", "yohji yamamoto", "Y-3", (0.35, 0.45)),
        ("Yohji Yamamoto Pour Homme Wool Gabardine Jacket", "yohji yamamoto", "Pour Homme", (0.9, 1.1)),
        ("Dior Homme Hedi Slimane 19cm Jeans 2006", "dior homme", "Hedi", (2.0, 3.0)),
    ]

    print(f"\n{'='*80}")
    print("LINE DETECTION TEST")
    print(f"{'='*80}\n")

    passed = 0
    failed = 0
    for title, brand, expected_line, (low, high) in tests:
        line_name, mult, explanation = detect_line(title, brand)
        ok_line = expected_line.lower() in line_name.lower()
        ok_mult = low <= mult <= high
        status = "PASS" if (ok_line and ok_mult) else "FAIL"
        emoji = "✅" if status == "PASS" else "❌"

        if status == "PASS":
            passed += 1
        else:
            failed += 1

        print(f"{emoji} {title[:55]:55s}")
        print(f"   Got: {line_name} ({mult:.2f}x) | Expected: {expected_line} ({low}-{high}x)")
        if not ok_line:
            print(f"   ⚠ Line mismatch!")
        if not ok_mult:
            print(f"   ⚠ Multiplier out of range!")

    print(f"\n{'='*80}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")

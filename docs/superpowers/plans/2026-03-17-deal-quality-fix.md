# Deal Quality Fix Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate phantom gap alerts caused by bad comp matching, then recover blocked good deals by lowering the fire-level gate.

**Architecture:** Replace soft similarity scoring in `comp_matcher.py` with hard dimension gates (`is_exact_match`) + soft quality ranking (`match_quality`). Add a `comp_validator.py` safety net. Then recalibrate score weights and lower the fire-level gate.

**Tech Stack:** Python 3.11, pytest, existing scraper/core infrastructure.

**Spec:** `docs/superpowers/specs/2026-03-17-deal-quality-fix-design.md`

---

## Phase 1: Exact Comp Matching

### Task 1: Add `is_exact_match()` to comp_matcher

**Files:**
- Modify: `scrapers/comp_matcher.py:277-341`
- Test: `tests/unit/test_exact_matching.py`

- [ ] **Step 1: Write failing tests for `is_exact_match`**

Create `tests/unit/test_exact_matching.py`:

```python
"""Tests for exact comp matching — hard dimension gates."""

import pytest
from scrapers.comp_matcher import parse_title, is_exact_match


class TestIsExactMatch:
    """Hard dimension gate: brand, model, item_type, line, material."""

    def test_identical_items_match(self):
        listing = parse_title("rick owens", "Rick Owens Geobasket Leather Sneakers Black")
        comp = parse_title("rick owens", "Rick Owens Geobasket Leather High Top Black")
        assert is_exact_match(listing, comp) is True

    def test_different_model_rejects(self):
        listing = parse_title("rick owens", "Rick Owens Geobasket Leather")
        comp = parse_title("rick owens", "Rick Owens Ramones Low Canvas")
        assert is_exact_match(listing, comp) is False

    def test_different_line_rejects(self):
        """DRKSHDW listing must NOT match mainline comps."""
        listing = parse_title("rick owens", "Rick Owens DRKSHDW Canvas Low Sneakers")
        comp = parse_title("rick owens", "Rick Owens Geobasket Leather Sneakers")
        assert is_exact_match(listing, comp) is False

    def test_different_material_rejects(self):
        """Canvas listing must NOT match leather comps."""
        listing = parse_title("rick owens", "Rick Owens Geobasket Canvas")
        comp = parse_title("rick owens", "Rick Owens Geobasket Leather")
        assert is_exact_match(listing, comp) is False

    def test_material_skip_when_undetectable(self):
        """If neither title mentions material, skip material check."""
        listing = parse_title("rick owens", "Rick Owens Geobasket Black")
        comp = parse_title("rick owens", "Rick Owens Geobasket Size 43")
        assert is_exact_match(listing, comp) is True

    def test_material_skip_when_one_undetectable(self):
        """If only one title mentions material, skip material check."""
        listing = parse_title("rick owens", "Rick Owens Geobasket Leather Black")
        comp = parse_title("rick owens", "Rick Owens Geobasket Size 43")
        assert is_exact_match(listing, comp) is True

    def test_different_brand_rejects(self):
        listing = parse_title("rick owens", "Rick Owens Geobasket")
        comp = parse_title("balenciaga", "Balenciaga Triple S")
        assert is_exact_match(listing, comp) is False

    def test_different_item_type_rejects(self):
        """Sneakers must NOT match jackets."""
        listing = parse_title("rick owens", "Rick Owens Geobasket Sneakers")
        comp = parse_title("rick owens", "Rick Owens Leather Jacket")
        assert is_exact_match(listing, comp) is False

    def test_no_model_both_sides_passes(self):
        """When neither has a detected model, pass (don't over-filter)."""
        listing = parse_title("rick owens", "Rick Owens Leather Jacket FW08")
        comp = parse_title("rick owens", "Rick Owens Leather Jacket SS09")
        assert is_exact_match(listing, comp) is True

    def test_model_detected_one_side_only_passes(self):
        """If only one side has a model, pass (comp titles are often sparse)."""
        listing = parse_title("rick owens", "Rick Owens Stooges Leather Jacket")
        comp = parse_title("rick owens", "Rick Owens Leather Jacket Black")
        assert is_exact_match(listing, comp) is True

    def test_same_line_both_diffusion_passes(self):
        """Two DRKSHDW items should match."""
        listing = parse_title("rick owens", "Rick Owens DRKSHDW Pods Sneakers Canvas")
        comp = parse_title("rick owens", "Rick Owens DRKSHDW Pods Low Canvas")
        assert is_exact_match(listing, comp) is True

    def test_type_alias_geobasket_boots_vs_sneakers(self):
        """Geobasket classified as boots should match Geobasket classified as sneakers via TYPE_ALIASES."""
        listing = parse_title("rick owens", "Rick Owens Geobasket High Top Sneakers")
        comp = parse_title("rick owens", "Rick Owens Geobasket Boots Leather")
        assert is_exact_match(listing, comp) is True

    def test_type_alias_tabi_boots_vs_loafers(self):
        """Tabi boots should match Tabi loafers via TYPE_ALIASES."""
        listing = parse_title("maison margiela", "Maison Margiela Tabi Boots")
        comp = parse_title("maison margiela", "Maison Margiela Tabi Loafers")
        assert is_exact_match(listing, comp) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/unit/test_exact_matching.py -v --no-header --tb=short 2>&1 | tail -20`
Expected: FAIL — `is_exact_match` not defined

- [ ] **Step 3: Implement `is_exact_match` in comp_matcher.py**

Add after `score_comp_similarity()` (after line 341 in `scrapers/comp_matcher.py`):

```python
def is_exact_match(listing: ParsedTitle, comp: ParsedTitle) -> bool:
    """Hard dimension gate — ALL checks must pass for a comp to be valid.

    Dimensions checked:
        1. Brand: must match exactly
        2. Model: must match if detected on both sides
        3. Item type: must match (broad category level)
        4. Line tier: mainline/diffusion must agree
        5. Material: must match if detectable in both titles
    """
    # 1. Brand — always required
    if listing.brand != comp.brand:
        return False

    # 2. Model — reject only if BOTH detected and different
    if listing.model and comp.model:
        if listing.model.lower() != comp.model.lower():
            return False

    # 3. Item type — reject if both detected and different
    if listing.item_type and comp.item_type:
        if listing.item_type != comp.item_type:
            # Check type aliases for hybrid models (e.g., geobasket = boots OR sneakers)
            listing_types = TYPE_ALIASES.get(listing.model, {listing.item_type})
            comp_types = TYPE_ALIASES.get(comp.model, {comp.item_type})
            if not listing_types & comp_types:
                return False

    # 4. Line tier — mainline vs diffusion must agree
    listing_is_diffusion = bool(listing.sub_brand)
    comp_is_diffusion = bool(comp.sub_brand)
    if listing_is_diffusion != comp_is_diffusion:
        return False
    # If both are diffusion, must be SAME diffusion line
    if listing_is_diffusion and comp_is_diffusion:
        if listing.sub_brand.lower() != comp.sub_brand.lower():
            return False

    # 5. Material — reject only if BOTH detected and different
    if listing.material and comp.material:
        if listing.material.lower() != comp.material.lower():
            return False

    return True
```

Also add the `TYPE_ALIASES` dict near the top of the file (after `MATERIALS` list, ~line 63):

```python
# Hybrid model type aliases — models that span multiple item type categories.
# Used by is_exact_match() to allow valid cross-type comp matching.
# NOTE: Uses post-split category names (sneakers, not shoes). See Task 3.
TYPE_ALIASES: dict[str, set[str]] = {
    "geobasket": {"boots", "sneakers"},
    "geo basket": {"boots", "sneakers"},
    "kiss boot": {"boots", "sneakers"},
    "tractor": {"boots", "sneakers"},
    "ramones": {"boots", "sneakers"},
    "tabi": {"boots", "loafers", "sneakers"},
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/unit/test_exact_matching.py -v --no-header --tb=short 2>&1 | tail -20`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/comp_matcher.py tests/unit/test_exact_matching.py
git commit -m "feat: add is_exact_match() hard dimension gate to comp_matcher"
```

---

### Task 2: Add `match_quality()` soft ranking to comp_matcher

**Files:**
- Modify: `scrapers/comp_matcher.py`
- Test: `tests/unit/test_exact_matching.py`

- [ ] **Step 1: Write failing tests for `match_quality`**

Append to `tests/unit/test_exact_matching.py`:

```python
from scrapers.comp_matcher import match_quality


class TestMatchQuality:
    """Soft ranking: season, size, condition, recency."""

    def test_identical_item_scores_high(self):
        listing = parse_title("rick owens", "Rick Owens Geobasket Leather Black SS24")
        comp = parse_title("rick owens", "Rick Owens Geobasket Leather Black SS24")
        score = match_quality(listing, comp)
        assert score >= 0.8

    def test_different_season_scores_lower(self):
        listing = parse_title("rick owens", "Rick Owens Geobasket Leather SS24")
        comp_same = parse_title("rick owens", "Rick Owens Geobasket Leather SS24")
        comp_diff = parse_title("rick owens", "Rick Owens Geobasket Leather FW18")
        assert match_quality(listing, comp_same) > match_quality(listing, comp_diff)

    def test_returns_0_to_1_range(self):
        listing = parse_title("rick owens", "Rick Owens Geobasket Leather")
        comp = parse_title("rick owens", "Rick Owens Geobasket Leather")
        score = match_quality(listing, comp)
        assert 0.0 <= score <= 1.0

    def test_no_shared_soft_dimensions_still_returns_positive(self):
        """Even with no soft dimension overlap, score should be > 0."""
        listing = parse_title("rick owens", "Rick Owens Geobasket")
        comp = parse_title("rick owens", "Rick Owens Geobasket")
        score = match_quality(listing, comp)
        assert score > 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/unit/test_exact_matching.py::TestMatchQuality -v --no-header --tb=short`
Expected: FAIL — `match_quality` not defined

- [ ] **Step 3: Implement `match_quality` in comp_matcher.py**

Add after `is_exact_match()`:

```python
def match_quality(listing: ParsedTitle, comp: ParsedTitle, comp_sold_date: str = "") -> float:
    """Soft ranking score (0.0-1.0) for comps that passed is_exact_match().

    Higher scores mean the comp is a better reference for pricing.
    Dimensions: season proximity (0.3), size (0.3), condition (0.2), recency (0.2).
    """
    score = 0.0

    # Season proximity (0.3 weight)
    if listing.season and comp.season:
        if listing.season.lower() == comp.season.lower():
            score += 0.3
        else:
            # Partial credit for same decade
            score += 0.1
    else:
        # No season data — give neutral credit
        score += 0.15

    # Size — not in ParsedTitle currently, so give neutral credit
    # (will be enhanced when size is added to ParsedTitle)
    score += 0.15

    # Condition — not in ParsedTitle currently, give neutral credit
    score += 0.10

    # Recency — based on comp_sold_date if provided
    if comp_sold_date:
        try:
            from datetime import datetime, timedelta
            sold_dt = datetime.fromisoformat(comp_sold_date.replace("Z", "+00:00"))
            age_days = (datetime.now(sold_dt.tzinfo) - sold_dt).days
            if age_days <= 30:
                score += 0.20
            elif age_days <= 90:
                score += 0.15
            elif age_days <= 180:
                score += 0.10
            else:
                score += 0.05
        except (ValueError, TypeError):
            score += 0.10
    else:
        score += 0.10

    return min(score, 1.0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/unit/test_exact_matching.py -v --no-header --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/comp_matcher.py tests/unit/test_exact_matching.py
git commit -m "feat: add match_quality() soft ranking for exact-matched comps"
```

---

### Task 3: Refine footwear sub-categories in comp_matcher

**Files:**
- Modify: `scrapers/comp_matcher.py:40-56`
- Test: `tests/unit/test_exact_matching.py`

- [ ] **Step 1: Write failing tests for footwear sub-types**

Append to `tests/unit/test_exact_matching.py`:

```python
class TestFootwearSubTypes:
    """Sneakers and boots should be separate item types."""

    def test_sneakers_vs_boots_rejects(self):
        listing = parse_title("balenciaga", "Balenciaga Triple S Sneakers White")
        comp = parse_title("balenciaga", "Balenciaga Santiago Leather Boots Black")
        assert is_exact_match(listing, comp) is False

    def test_sneakers_vs_sneakers_passes(self):
        listing = parse_title("balenciaga", "Balenciaga Triple S Sneakers")
        comp = parse_title("balenciaga", "Balenciaga Triple S Trainers White")
        assert is_exact_match(listing, comp) is True

    def test_loafers_vs_sneakers_rejects(self):
        listing = parse_title("prada", "Prada Leather Loafers")
        comp = parse_title("prada", "Prada Americas Cup Sneakers")
        assert is_exact_match(listing, comp) is False

    def test_boots_vs_boots_passes(self):
        listing = parse_title("ann demeulemeester", "Ann Demeulemeester Leather Boots")
        comp = parse_title("ann demeulemeester", "Ann Demeulemeester Lace Up Boots Black")
        assert is_exact_match(listing, comp) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/unit/test_exact_matching.py::TestFootwearSubTypes -v --no-header --tb=short`
Expected: FAIL — sneakers/boots currently both map to "shoes" or "boots"

- [ ] **Step 3: Split the `ITEM_TYPES["shoes"]` in comp_matcher.py**

Replace the current `"shoes"` entry in `ITEM_TYPES` (line 51-52):

```python
# Before:
"shoes": ["shoes", "sneakers", "runners", "trainers", "loafers", "derbies", "oxford shoes",
          "slides", "sandals", "mules", "slip on"],

# After:
"sneakers": ["sneakers", "runners", "trainers", "high top", "low top"],
"loafers": ["loafers", "derbies", "oxford shoes", "slip on", "mules"],
"sandals": ["slides", "sandals"],
```

The "boots" entry already exists separately. Items matching generic "shoes" keyword with no sub-type get mapped to "sneakers" as default (most common in this codebase).

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/unit/test_exact_matching.py -v --no-header --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/comp_matcher.py tests/unit/test_exact_matching.py
git commit -m "feat: split footwear into sneakers/boots/loafers/sandals sub-types"
```

---

### Task 4: Build comp_validator.py safety net

**Files:**
- Create: `core/comp_validator.py`
- Test: `tests/unit/test_comp_validator.py`

- [ ] **Step 1: Write failing tests for comp_validator**

Create `tests/unit/test_comp_validator.py`:

```python
"""Tests for core.comp_validator — 5-check comp validation safety net."""

import pytest
from datetime import datetime, timedelta


class TestCategoryParity:
    def test_shoes_vs_jacket_rejects(self):
        from core.comp_validator import check_category_parity
        assert check_category_parity("Rick Owens Geobasket Sneakers", "Rick Owens Leather Jacket") is False

    def test_shoes_vs_shoes_passes(self):
        from core.comp_validator import check_category_parity
        assert check_category_parity("Rick Owens Geobasket", "Rick Owens Dunks") is True

    def test_undetectable_passes(self):
        from core.comp_validator import check_category_parity
        assert check_category_parity("Rick Owens", "Rick Owens Black") is True


class TestLineParity:
    def test_diffusion_vs_mainline_rejects(self):
        from core.comp_validator import check_line_parity
        assert check_line_parity(
            "Rick Owens DRKSHDW Canvas Sneakers", "rick owens",
            "Rick Owens Geobasket Leather", "rick owens"
        ) is False

    def test_mainline_vs_mainline_passes(self):
        from core.comp_validator import check_line_parity
        assert check_line_parity(
            "Rick Owens Geobasket Leather", "rick owens",
            "Rick Owens Ramones Leather", "rick owens"
        ) is True


class TestMaterialParity:
    def test_leather_vs_canvas_rejects(self):
        from core.comp_validator import check_material_parity
        assert check_material_parity("Geobasket Leather Black", "Geobasket Canvas White") is False

    def test_leather_vs_leather_passes(self):
        from core.comp_validator import check_material_parity
        assert check_material_parity("Geobasket Leather Black", "Geobasket Leather White") is True

    def test_no_material_passes(self):
        from core.comp_validator import check_material_parity
        assert check_material_parity("Geobasket Black", "Geobasket White") is True

    def test_one_side_no_material_passes(self):
        from core.comp_validator import check_material_parity
        assert check_material_parity("Geobasket Leather", "Geobasket Black") is True


class TestRecencyGate:
    def test_recent_comp_passes(self):
        from core.comp_validator import check_recency
        recent = datetime.now() - timedelta(days=30)
        assert check_recency(recent.isoformat()) is True

    def test_old_comp_rejects(self):
        from core.comp_validator import check_recency
        old = datetime.now() - timedelta(days=200)
        assert check_recency(old.isoformat()) is False

    def test_archive_brand_extended_window(self):
        from core.comp_validator import check_recency
        old = datetime.now() - timedelta(days=300)
        assert check_recency(old.isoformat(), archive_brand=True) is True

    def test_no_date_passes(self):
        from core.comp_validator import check_recency
        assert check_recency(None) is True


class TestOutlierRemoval:
    def test_removes_extreme_high(self):
        from core.comp_validator import remove_outliers
        prices = [100, 110, 120, 115, 105, 800]
        filtered = remove_outliers(prices)
        assert 800 not in filtered

    def test_removes_extreme_low(self):
        from core.comp_validator import remove_outliers
        prices = [500, 520, 510, 530, 490, 50]
        filtered = remove_outliers(prices)
        assert 50 not in filtered

    def test_keeps_normal_range(self):
        from core.comp_validator import remove_outliers
        prices = [100, 110, 120, 130, 140]
        filtered = remove_outliers(prices)
        assert filtered == prices


class TestValidateComps:
    def test_full_pipeline(self):
        from core.comp_validator import validate_comps, CompValidationResult
        # This is an integration test — just verify it runs and returns the right type
        result = validate_comps(
            listing_title="Rick Owens Geobasket Leather Sneakers",
            listing_brand="rick owens",
            comp_titles=["Rick Owens Geobasket Leather", "Rick Owens Geobasket Black Leather", "Rick Owens Geobasket High"],
            comp_prices=[800, 850, 900],
            comp_sold_dates=[datetime.now().isoformat()] * 3,
        )
        assert isinstance(result, CompValidationResult)
        assert result.surviving_count >= 0
        assert result.confidence in ("full", "reduced", "low", "none")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/unit/test_comp_validator.py -v --no-header --tb=short 2>&1 | tail -20`
Expected: FAIL — module not found

- [ ] **Step 3: Implement comp_validator.py**

Create `core/comp_validator.py`:

```python
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

# Broad category keywords (more aggressive than fingerprinter)
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "footwear": ["shoes", "sneakers", "boots", "boot", "loafers", "sandals", "slides",
                 "trainers", "runners", "derbies", "mules", "heels", "slippers"],
    "outerwear": ["jacket", "coat", "blazer", "bomber", "parka", "vest", "gilet"],
    "tops": ["shirt", "tee", "t-shirt", "hoodie", "sweatshirt", "sweater", "knit",
             "cardigan", "tank", "top", "polo", "henley"],
    "bottoms": ["pants", "jeans", "trousers", "shorts", "skirt", "denim"],
    "jewelry": ["ring", "necklace", "bracelet", "pendant", "earring", "chain", "bangle"],
    "bags": ["bag", "backpack", "tote", "clutch", "wallet", "purse", "pouch"],
    "accessories": ["belt", "scarf", "hat", "cap", "gloves", "sunglasses", "glasses"],
}

MATERIAL_KEYWORDS = [
    "leather", "suede", "canvas", "nylon", "denim", "mesh", "wool",
    "cashmere", "silk", "cotton", "rubber", "patent", "shearling",
    "velvet", "corduroy", "gore-tex", "waxed", "coated", "knit",
]

# Brands with extended recency window (archive pieces sell infrequently)
ARCHIVE_BRANDS = {
    "helmut lang", "number nine", "number (n)ine", "carol christian poell",
    "jean colonna", "walter van beirendonck", "boris bidjan saberi",
}

COMP_MAX_AGE_DAYS = 180
ARCHIVE_MAX_AGE_DAYS = 365


def _extract_category(title: str) -> Optional[str]:
    """Extract broad category from title."""
    title_lower = title.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in sorted(keywords, key=len, reverse=True):
            if kw in title_lower:
                return category
    return None


def _extract_material(title: str) -> Optional[str]:
    """Extract material from title."""
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
    return True  # Skip if undetectable


def check_line_parity(
    listing_title: str, listing_brand: str,
    comp_title: str, comp_brand: str,
) -> bool:
    """Check 2: Mainline vs diffusion must agree.

    Uses asymmetric thresholds per spec:
    - Diffusion = multiplier < 0.5
    - Mainline = multiplier >= 0.8
    - Middle zone (0.5-0.8) = secondary lines, match either side
    """
    from core.line_detection import detect_line
    _, listing_mult, _ = detect_line(listing_title, listing_brand)
    _, comp_mult, _ = detect_line(comp_title, comp_brand)
    # Reject only clear mismatches: diffusion (<0.5) vs mainline (>=0.8)
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
    return True  # Skip if either undetectable


def check_recency(sold_date_str: Optional[str], archive_brand: bool = False) -> bool:
    """Check 4: Comp must be recent enough."""
    if not sold_date_str:
        return True  # No date info — pass
    try:
        sold_dt = datetime.fromisoformat(sold_date_str.replace("Z", "+00:00"))
        max_age = ARCHIVE_MAX_AGE_DAYS if archive_brand else COMP_MAX_AGE_DAYS
        age = (datetime.now(sold_dt.tzinfo) - sold_dt).days
        return age <= max_age
    except (ValueError, TypeError):
        return True  # Unparseable date — pass


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
    """Result of comp validation pipeline."""
    surviving_count: int
    original_count: int
    confidence: str  # "full" (5+), "reduced" (3-4), "low" (1-2), "none" (0)
    score_penalty: int  # Points to subtract from quality score
    surviving_indices: list[int]  # Indices of surviving comps


def validate_comps(
    listing_title: str,
    listing_brand: str,
    comp_titles: list[str],
    comp_prices: list[float],
    comp_sold_dates: list[Optional[str]] = None,
) -> CompValidationResult:
    """Run all 5 validation checks on a comp set.

    Returns which comps survived and the confidence level.
    """
    if comp_sold_dates is None:
        comp_sold_dates = [None] * len(comp_titles)

    is_archive = listing_brand.lower().strip() in ARCHIVE_BRANDS
    surviving = list(range(len(comp_titles)))

    # Check 1: Category parity
    surviving = [
        i for i in surviving
        if check_category_parity(listing_title, comp_titles[i])
    ]

    # Check 2: Line parity
    surviving = [
        i for i in surviving
        if check_line_parity(listing_title, listing_brand, comp_titles[i], listing_brand)
    ]

    # Check 3: Material parity
    surviving = [
        i for i in surviving
        if check_material_parity(listing_title, comp_titles[i])
    ]

    # Check 4: Recency
    surviving = [
        i for i in surviving
        if check_recency(comp_sold_dates[i], archive_brand=is_archive)
    ]

    # Check 5: Outlier removal on surviving prices
    if len(surviving) >= 3:
        surviving_prices = [comp_prices[i] for i in surviving]
        valid_prices = set(remove_outliers(surviving_prices))
        surviving = [i for i in surviving if comp_prices[i] in valid_prices]

    # Determine confidence
    n = len(surviving)
    if n >= 5:
        confidence = "full"
        penalty = 0
    elif n >= 3:
        confidence = "reduced"
        penalty = 10
    elif n >= 1:
        confidence = "low"
        penalty = 0  # Will be rejected by caller (< 3 comps)
    else:
        confidence = "none"
        penalty = 0

    original = len(comp_titles)
    if original > n:
        logger.info(
            f"Comp validator: {original} → {n} comps survived "
            f"({original - n} rejected, confidence={confidence})"
        )

    return CompValidationResult(
        surviving_count=n,
        original_count=original,
        confidence=confidence,
        score_penalty=penalty,
        surviving_indices=surviving,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/unit/test_comp_validator.py -v --no-header --tb=short 2>&1 | tail -25`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add core/comp_validator.py tests/unit/test_comp_validator.py
git commit -m "feat: add comp_validator.py safety net with 5 validation checks"
```

---

### Task 5: Wire exact matching + validator into gap_hunter.py

**Files:**
- Modify: `gap_hunter.py:1162-1182`

- [ ] **Step 1: Replace fingerprint similarity with is_exact_match in gap_hunter.py**

Find the fingerprint filtering block at line ~1162-1182 and replace it:

```python
# BEFORE (lines 1162-1182):
# Pass 2: Fingerprint similarity with strict thresholds
if query_fp.is_complete() and len(sold) >= 3:
    STRICT_TYPES = {"rings", "necklaces", "bracelets", "earrings", "eyewear", "wallets", "bags"}
    sim_threshold = 0.7 if query_fp.item_type in STRICT_TYPES else 0.5
    matched_sold = []
    for s in sold:
        comp_brand = self._detect_brand(s.title) or query_brand
        comp_fp = parse_title_to_fingerprint(comp_brand, s.title)
        similarity = query_fp.similarity_score(comp_fp)
        if similarity >= sim_threshold:
            matched_sold.append(s)
    ...

# AFTER:
# Pass 2: Exact dimension matching (hard gate)
from scrapers.comp_matcher import parse_title, is_exact_match
listing_parsed = parse_title(query_brand, item.title)
if listing_parsed.brand and len(sold) >= 3:
    matched_sold = []
    for s in sold:
        comp_brand = self._detect_brand(s.title) or query_brand
        comp_parsed = parse_title(comp_brand, s.title)
        if is_exact_match(listing_parsed, comp_parsed):
            matched_sold.append(s)
    if len(matched_sold) >= 3:
        removed = len(sold) - len(matched_sold)
        if removed > 0:
            logger.info(f"  🎯 Exact match filter: {len(matched_sold)}/{len(sold)} comps matched")
        sold = matched_sold
        prices = sorted([i.price for i in sold if i.price and i.price > 0])
    elif len(matched_sold) > 0:
        logger.info(f"  ⚠️ Exact match: only {len(matched_sold)} comps (below min {min_comps}), keeping original set")
```

- [ ] **Step 2: Sort surviving comps by match_quality**

After the exact match filter block, add quality-based sorting:

```python
        # Sort exact-matched comps by quality for weighted median
        from scrapers.comp_matcher import match_quality as comp_match_quality
        if len(matched_sold) >= 3:
            # Attach quality scores for later use in weighted median
            for s in matched_sold:
                comp_brand = self._detect_brand(s.title) or query_brand
                comp_parsed = parse_title(comp_brand, s.title)
                s._match_quality = comp_match_quality(listing_parsed, comp_parsed, getattr(s, 'sold_date', ''))
            matched_sold.sort(key=lambda s: s._match_quality, reverse=True)
```

- [ ] **Step 3: Add comp_validator call after comp filtering**

Add after the IQR outlier removal block (~line 1208), before gap calculation:

```python
# ── Comp validation safety net ──
from core.comp_validator import validate_comps
comp_confidence_penalty = 0
if len(sold) >= 3:
    validation = validate_comps(
        listing_title=item.title,
        listing_brand=query_brand,
        comp_titles=[s.title for s in sold],
        comp_prices=[s.price for s in sold if s.price],
        comp_sold_dates=[getattr(s, 'sold_date', None) for s in sold],
    )
    if validation.surviving_count >= 3:
        sold = [sold[i] for i in validation.surviving_indices]
        prices = sorted([s.price for s in sold if s.price and s.price > 0])
        comp_confidence_penalty = validation.score_penalty
    elif validation.surviving_count == 0:
        logger.info(f"  ❌ Comp validator rejected all comps for '{item.title[:50]}'")
        continue
    # If 1-2 survive, keep original set but note low confidence
```

- [ ] **Step 4: Apply comp_confidence_penalty to quality score**

Find the `calculate_deal_quality()` call (~line 2095 and ~2215) and subtract the penalty:

```python
# After the calculate_deal_quality() call:
quality_score, signals = calculate_deal_quality(...)
# Apply comp confidence penalty from validation
quality_score = max(0, quality_score - comp_confidence_penalty)
if comp_confidence_penalty > 0:
    logger.info(f"  📉 Comp confidence penalty: -{comp_confidence_penalty} pts ({validation.surviving_count} comps)")
```

- [ ] **Step 5: Migrate second fingerprint call site (line ~1796)**

Replace the `parse_title_to_fingerprint` category mismatch check at lines 1792-1803:

```python
# BEFORE (lines 1792-1803):
try:
    if detected_brand:
        query_fp = parse_title_to_fingerprint(detected_brand, query)
        item_fp = parse_title_to_fingerprint(detected_brand, item.title)
        if query_fp.item_type and item_fp.item_type and query_fp.item_type != item_fp.item_type:
            ...

# AFTER:
try:
    if detected_brand:
        from scrapers.comp_matcher import parse_title as cm_parse_title
        query_parsed = cm_parse_title(detected_brand, query)
        item_parsed = cm_parse_title(detected_brand, item.title)
        if query_parsed.item_type and item_parsed.item_type and query_parsed.item_type != item_parsed.item_type:
            logger.info(f"    🔍 Category mismatch: query={query_parsed.item_type}, item={item_parsed.item_type} — {item.title[:50]}")
            query_metrics["category_mismatch_skips"] += 1
            continue
except Exception:
    pass
```

- [ ] **Step 6: Run existing tests to verify nothing breaks**

Run: `./venv/bin/python -m pytest tests/unit/ -v --no-header --tb=short 2>&1 | tail -10`
Expected: All existing tests PASS

- [ ] **Step 7: Commit**

```bash
git add gap_hunter.py
git commit -m "feat: wire exact matching + comp validator + penalty into gap_hunter pipeline"
```

---

### Task 6: Clean up product_fingerprint.py

**Files:**
- Modify: `scrapers/product_fingerprint.py`

- [ ] **Step 1: Remove dead `similarity_score()` method**

Delete the `similarity_score()` method (lines 295-327 in `scrapers/product_fingerprint.py`). It is no longer called — `gap_hunter.py` now uses `comp_matcher.is_exact_match()`.

- [ ] **Step 2: Verify no remaining callers**

Run: `grep -rn "similarity_score" scrapers/ core/ gap_hunter.py --include="*.py"`
Expected: No matches (method is dead code)

- [ ] **Step 3: Run tests to verify nothing breaks**

Run: `./venv/bin/python -m pytest tests/unit/ -v --no-header --tb=short 2>&1 | tail -10`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add scrapers/product_fingerprint.py
git commit -m "chore: remove dead similarity_score() from product_fingerprint.py"
```

---

## Phase 2: Score Recalibration (deploy after Phase 1 monitoring)

### Task 7: Reweight score components in deal_quality.py

**Files:**
- Modify: `core/deal_quality.py:26-32`
- Test: `tests/unit/test_deal_quality_weights.py`

- [ ] **Step 1: Write failing test for new weights**

Create `tests/unit/test_deal_quality_weights.py`:

```python
"""Tests for deal_quality.py score weight recalibration."""

from core.deal_quality import (
    WEIGHT_GAP, WEIGHT_LINE, WEIGHT_CONDITION,
    WEIGHT_SEASON, WEIGHT_SIZE, WEIGHT_AUTH, WEIGHT_LIQUIDITY,
)


class TestWeightDistribution:
    def test_weights_sum_to_100(self):
        total = WEIGHT_GAP + WEIGHT_LINE + WEIGHT_CONDITION + WEIGHT_SEASON + WEIGHT_SIZE + WEIGHT_AUTH + WEIGHT_LIQUIDITY
        assert total == 100

    def test_gap_is_dominant_signal(self):
        assert WEIGHT_GAP >= 40

    def test_liquidity_reduced(self):
        assert WEIGHT_LIQUIDITY <= 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/unit/test_deal_quality_weights.py -v --no-header --tb=short`
Expected: FAIL — WEIGHT_GAP is 30, not 40

- [ ] **Step 3: Update weights in deal_quality.py**

Change lines 26-32:

```python
# Before:
WEIGHT_GAP = 30
WEIGHT_LINE = 12
WEIGHT_CONDITION = 12
WEIGHT_SEASON = 12
WEIGHT_SIZE = 8
WEIGHT_AUTH = 10
WEIGHT_LIQUIDITY = 16

# After:
WEIGHT_GAP = 40
WEIGHT_LINE = 12
WEIGHT_CONDITION = 10
WEIGHT_SEASON = 12
WEIGHT_SIZE = 6
WEIGHT_AUTH = 10
WEIGHT_LIQUIDITY = 10
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/unit/test_deal_quality_weights.py -v --no-header --tb=short`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add core/deal_quality.py tests/unit/test_deal_quality_weights.py
git commit -m "feat: reweight deal quality — gap 30→40, liquidity 16→10"
```

---

### Task 8: Lower fire-level gate

**Files:**
- Modify: `.env`

- [ ] **Step 1: Change GAP_MIN_FIRE_LEVEL in .env**

```bash
# In .env, change:
GAP_MIN_FIRE_LEVEL=1
```

- [ ] **Step 2: Verify gap_hunter reads the value**

Run: `grep -n GAP_MIN_FIRE_LEVEL gap_hunter.py`
Expected: Shows the `os.getenv("GAP_MIN_FIRE_LEVEL", "2")` line — confirm it reads from env.

- [ ] **Step 3: Commit**

```bash
git add .env
git commit -m "feat: lower fire-level gate from 2 to 1 (safe with exact comp matching)"
```

---

### Task 9: Run full test suite and verify

**Files:** None (verification only)

- [ ] **Step 1: Run full unit test suite**

Run: `./venv/bin/python -m pytest tests/unit/ -v --tb=short 2>&1 | tail -20`
Expected: All tests PASS, including new tests from tasks 1-7

- [ ] **Step 2: Verify comp_matcher imports work across codebase**

Run: `./venv/bin/python -c "from scrapers.comp_matcher import is_exact_match, match_quality, TYPE_ALIASES; print('OK')""`
Expected: "OK"

- [ ] **Step 3: Verify comp_validator imports work**

Run: `./venv/bin/python -c "from core.comp_validator import validate_comps; print('OK')"`
Expected: "OK"

- [ ] **Step 4: Commit any remaining changes**

```bash
git status
# If clean, no commit needed
```

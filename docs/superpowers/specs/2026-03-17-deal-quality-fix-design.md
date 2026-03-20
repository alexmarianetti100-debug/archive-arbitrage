# Deal Quality Fix — Exact Comp Matching + Score Recalibration

**Date:** 2026-03-17
**Status:** Approved design, pending implementation

## Problem

Two interlocking failures degrade deal quality:

1. **Bad alerts (false positives):** Soft similarity matching in `product_fingerprint.py` and `comp_matcher.py` produces phantom gaps. A $200 DRKSHDW canvas sneaker gets matched against $2,000 mainline leather Geobasket comps, creating a fake "90% gap" that triggers an alert.

2. **Missing good deals (false negatives):** The fire-level gate (`GAP_MIN_FIRE_LEVEL=2`) was raised to compensate for bad comps, but it also blocks 959 legitimate deals with real 80-95% gaps.

**Root cause chain:**
```
Bad comp matching (ignores material/category/season/line)
  → Phantom gaps (fake 80-90% discounts)
  → Fire-level gate raised to compensate
  → Real deals blocked alongside garbage
  → Both problems at once
```

Fix the comp matching, then safely lower the fire-level gate.

## Solution Overview

Three coordinated changes, deployed in order:

1. **Exact comp matching** — Replace soft similarity scoring with hard dimension gates
2. **Comp validation layer** — Safety net catching extraction failures
3. **Score recalibration** — Reweight components and lower fire-level gate (deployed AFTER matching is proven)

## Existing Comp Pipelines

The codebase has two comp-matching systems that must both be addressed:

- **`scrapers/comp_matcher.py`** — Used by `qualify.py`, `api/services/pricing.py`, `volume_tracker.py`, `demand_scorer.py`. Has its own `SUB_BRANDS`, `ITEM_TYPES`, `score_comp_similarity()`, and `weighted_median()`. Called via `find_best_comps()`.
- **`scrapers/product_fingerprint.py`** — Used by `gap_hunter.py` for active-listing-to-comp matching. Has its own `similarity_score()`.

**Decision: Consolidate into `comp_matcher.py`.** The hard dimension matching and weighted median logic belong in `comp_matcher.py` since it's already the primary comp pipeline used across the codebase. `product_fingerprint.py` keeps its fingerprint extraction role but delegates comp matching to `comp_matcher.py`.

## 1. Exact Comp Matching

### Changes to `scrapers/comp_matcher.py`

Add two new methods to the comp matching pipeline:

**`is_exact_match(listing: ParsedTitle, comp: ParsedTitle) -> bool`** — Hard dimension gate. ALL must pass:

| Dimension | Rule | Undetectable behavior | Example |
|---|---|---|---|
| Brand | Exact match | Reject (brand is always present) | Rick Owens = Rick Owens |
| Model | Exact canonical match | Pass (many items have no model) | Geobasket = Geobasket, Ramones ≠ Geobasket |
| Item type | Exact match with refined sub-categories | Pass (generic items allowed) | sneakers↔sneakers, not sneakers↔boots |
| Line tier | Same tier (mainline/diffusion) | Pass (assume mainline) | DRKSHDW ≠ mainline Rick Owens |
| Material | Must match if detectable in BOTH titles | Pass (skip check) | leather↔leather, canvas ≠ leather |

**Key rule for undetectable dimensions:** When a dimension cannot be extracted from either title, the check passes. This prevents over-filtering niche items. When model="" matches model="", the check passes — two Rick Owens jackets without detected models are allowed as comps (the validation layer provides a second line of defense).

**`match_quality(listing: ParsedTitle, comp: ParsedTitle) -> float`** — Soft ranking (0.0-1.0) for surviving comps:

| Dimension | Weight | Notes |
|---|---|---|
| Season/year proximity | 0.3 | Same era ranks higher |
| Size proximity | 0.3 | Same size ranks higher |
| Condition similarity | 0.2 | Similar condition ranks higher |
| Recency | 0.2 | Newer sold date ranks higher |

### Item type refinement

The current `ITEM_TYPES` in `comp_matcher.py` already separates "boots" and "shoes". Refine further:

| Current category | Split into |
|---|---|
| shoes | sneakers, loafers, heels, sandals, slides |
| boots | boots (unchanged) |
| footwear (in product_fingerprint.py) | Map to the comp_matcher categories above |

**Hybrid items (e.g., Geobasket):** Add a `TYPE_ALIASES` dict for known hybrid models:
```python
TYPE_ALIASES = {
    "geobasket": {"sneakers", "boots"},  # Matches either
    "tractor": {"boots", "sneakers"},
    "kiss boots": {"boots"},
}
```
When a model has aliases, the item type check passes if the comp's type is in the alias set.

### Weighted median pricing

Reuse and extend the existing `weighted_median()` in `comp_matcher.py` (line 662). The `match_quality()` score maps to the existing `.similarity` field on `ScoredComp`. No new weighted median function needed — just plug `match_quality()` into the existing infrastructure.

### Caller change in `gap_hunter.py`

Replace the current `product_fingerprint.similarity_score()` calls with:
```python
from scrapers.comp_matcher import is_exact_match, match_quality
comps = [c for c in candidates if is_exact_match(listing_parsed, c)]
comps.sort(key=lambda c: match_quality(listing_parsed, c), reverse=True)
```

### Changes to `scrapers/product_fingerprint.py`

- Remove `similarity_score()` method (replaced by `comp_matcher.is_exact_match()`)
- Keep all fingerprint extraction logic (brand, model, material, line, season, item type)
- Add refined item type extraction for footwear sub-categories
- Export extracted dimensions in a format `comp_matcher` can consume

## 2. Comp Validation Layer

### New module: `core/comp_validator.py`

A **safety net** for cases where fingerprint extraction fails (e.g., material keyword missing from title but obvious from context). Runs after `is_exact_match()` filtering, before gap calculation.

The validator uses broader regex patterns than the fingerprinter — it's intentionally more aggressive about detecting mismatches since it's rejecting comps, not extracting features.

**Check 1: Category parity**
Broad category extraction from titles (footwear, outerwear, tops, bottoms, jewelry, bags, accessories). Reject comps where broad category doesn't match.

**Check 2: Line parity**
Use the existing `detect_line(title, brand, description)` from `core/line_detection.py` (returns `(line_name, multiplier, explanation)`). Compare the multiplier — if listing multiplier is <0.5 (diffusion) and comp multiplier is ≥0.8 (mainline), or vice versa, reject.

No new `classify_line()` function needed — `detect_line()` already provides everything we need. The validator calls it directly.

**Check 3: Material parity**
Extract material keywords (leather, canvas, nylon, suede, denim, mesh, wool, cashmere, silk, cotton, rubber, patent, shearling). If listing has a detectable material and comp has a *conflicting* material, reject. If either title has no detectable material, skip.

**Check 4: Recency gate**
Reject comps with sold dates older than 180 days. Configurable via `COMP_MAX_AGE_DAYS`. For archive/grail brands (Helmut Lang, Number Nine, Carol Christian Poell), extend to 365 days since sales are infrequent.

**Check 5: Outlier removal**
After checks 1-4, compute median comp price. Reject comps more than 2x or less than 0.5x the median.

### Post-validation: Comp confidence tiers

Single, consistent definition:

| Surviving comps | Behavior |
|---|---|
| **5+** | Full confidence — normal scoring |
| **3-4** | Reduced confidence — apply **-10 point** score penalty |
| **1-2** | Low confidence — deal rejected (no alert) |
| **0** | No comps — deal rejected (no alert) |

Minimum 3 comps required for any alert to fire.

### Relationship to existing `core/validation_engine.py`

`validation_engine.py` already has `check_diffusion_match()` and `check_size_parity()`. These overlap with the comp validator's checks 1-2.

**Decision:** Keep `validation_engine.py` as the **deal-level** validator (runs once per deal, checks the deal as a whole). The new `comp_validator.py` is a **comp-level** filter (runs per comp, decides which individual comps to keep/reject). They operate at different granularities:

- `comp_validator.py`: "Is this individual comp a valid match for this listing?" → filters comp list
- `validation_engine.py`: "Given the filtered comps, is this deal legitimate?" → circuit breaker on the deal

The overlap in line-parity checking is intentional defense-in-depth. The comp validator catches bad individual comps; the validation engine catches bad deals that slip through (e.g., all comps are borderline matches that individually pass but collectively produce a misleading average).

## 3. Score Recalibration

**Deploy AFTER exact matching is proven stable (1-2 weeks of monitoring).**

### Weight rebalance in `core/deal_quality.py`

| Component | Current | New | Rationale |
|---|---|---|---|
| Gap | 30 | **40** | Core arbitrage signal — should dominate |
| Liquidity | 16 | **10** | Nice signal, shouldn't kill a 90% gap deal |
| Auth | 10 | 10 | Unchanged |
| Condition | 12 | **10** | Parsing imprecise, reduce influence |
| Line | 12 | 12 | Unchanged — more important now with exact comps |
| Season | 12 | 12 | Unchanged |
| Size | 8 | **6** | Minor signal |
| **Total** | **100** | **100** | |

### Fire-level gate

Lower `GAP_MIN_FIRE_LEVEL` from 2 to **1**. Safe because:
- Exact comp matching eliminates phantom gaps
- Fire level 1 (score 30-49) with clean comps = real 30-50% gaps
- Tier policy still enforces profit/margin minimums per subscriber tier

## Deployment Order

1. **Phase 1:** Ship exact matching (`comp_matcher.py` changes, `product_fingerprint.py` changes, `comp_validator.py`). Keep `GAP_MIN_FIRE_LEVEL=2`. Monitor comp survival rates and alert quality for 1-2 weeks.
2. **Phase 2:** Ship score recalibration and lower fire-level gate to 1. Monitor alert volume and subscriber feedback.

This ensures matching improvements are validated before loosening the gate.

## Files Changed

| File | Change Type | Description |
|---|---|---|
| `core/comp_validator.py` | **New** | 5-check comp validation safety net |
| `scrapers/comp_matcher.py` | **Modified** | Add `is_exact_match()`, `match_quality()`, `TYPE_ALIASES`. Refine `ITEM_TYPES`. |
| `scrapers/product_fingerprint.py` | **Modified** | Remove `similarity_score()`. Add refined footwear sub-type extraction. Keep fingerprint extraction. |
| `gap_hunter.py` | **Modified** | Switch to `is_exact_match()` from `comp_matcher`. Wire in `comp_validator`. |
| `core/deal_quality.py` | **Modified** (Phase 2) | Reweight components. Add comp confidence penalty. |
| `.env` | **Modified** (Phase 2) | `GAP_MIN_FIRE_LEVEL=1` |
| `tests/unit/test_comp_validator.py` | **New** | Tests for all 5 validation checks |
| `tests/unit/test_exact_matching.py` | **New** | Tests for hard dimension matching, match quality ranking, type aliases |
| `tests/unit/test_deal_quality_weights.py` | **New** (Phase 2) | Tests for new weight distribution |

## Files NOT Changed

- Scraper layer — no changes to how listings or comps are fetched
- Alert dispatch — Discord/Telegram routing unchanged
- Tier policy — thresholds stay the same
- Japan pipeline — unaffected (separate pricing path)
- TrendEngine / query rotation — unchanged
- `core/validation_engine.py` — kept as deal-level validator (complementary to comp-level validator)

## Expected Impact

- **Bad alerts eliminated:** Diffusion/material/category mismatches no longer produce phantom gaps
- **Good deals recovered (Phase 2):** Lowering fire-level to 1 recovers legitimate deals from the 959 currently blocked
- **Fewer comps per deal:** Some deals will lose comps and fall below the 3-comp minimum — correct behavior (no alert > wrong alert)
- **Comp confidence visible:** 3-4 comp deals get -10 penalty, <3 comp deals rejected

## Monitoring Metrics

Track these after Phase 1 to validate before Phase 2:

- **comp_survival_rate:** % of raw comps that pass `is_exact_match()` + validation. Should be 30-60% (was ~100% before).
- **deals_with_comps:** % of deals that retain ≥3 comps. If this drops below 20%, matching is too strict.
- **alerts_per_cycle:** Should initially drop (fewer phantom gaps), then recover in Phase 2.
- **false_positive_rate:** Manual spot-check of alerts — are the gaps real?

## Risks

1. **Comp scarcity for niche items:** Archive pieces (Helmut Lang 1998, Number Nine skull cashmere) may not have 3 exact-match comps. Mitigation: undetectable dimensions pass, extended recency for archive brands (365 days), and fire-level 1 gate still allows these through if gap is strong.

2. **Material detection accuracy:** Titles don't always mention material. Mitigation: material check is skip-if-undetectable in both fingerprinter and validator.

3. **Item type splitting edge cases:** Some items blur categories (boot-sneaker hybrids like Geobaskets). Mitigation: `TYPE_ALIASES` dict with per-model overrides.

4. **Two-phase deployment timing:** If Phase 1 is too strict, deal volume drops before Phase 2 recovers it. Mitigation: monitor comp_survival_rate and deals_with_comps; adjust before Phase 2 if needed.

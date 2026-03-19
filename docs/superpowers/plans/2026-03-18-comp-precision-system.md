# Comp Precision System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure every surfaced deal is backed by sold comps that are demonstrably the same product, using similarity-weighted pricing, embedding-based historical comp matching, and a quality feedback loop.

**Architecture:** Three layers built sequentially: (1) similarity-weighted pricing via `score_comp_similarity()` replacing flat median, (2) historical comp DB with sentence-transformer embeddings merged into live results, (3) quality_score feedback from `sold_comps` table feeding back into similarity scoring. All infrastructure exists — this is primarily wiring.

**Tech Stack:** Python 3.11, sentence-transformers (all-MiniLM-L6-v2), SQLite, numpy, pytest

**Spec:** `docs/superpowers/specs/2026-03-18-comp-precision-system-design.md`

---

## File Map

### Modified Files
| File | Responsibility |
|------|---------------|
| `scrapers/comp_matcher.py` | Change `quality_weight()` floor from 0.0 to 0.2 |
| `db/sqlite_models.py` | Add `get_comp_quality_scores()`, add 0.2 floor to `update_sold_comp_rejection()`, modify `link_item_to_sold_comps()` to accept external similarity scores |
| `gap_hunter.py` | Add `compute_weighted_price()`, modify `get_sold_data()` to return raw items and embed on save, modify `get_item_specific_comps()` to merge DB results and apply weighted pricing |
| `tests/unit/test_quality_weight.py` | Update tests for 0.2 floor |
| `tests/unit/test_weighted_pricing.py` | New tests for `compute_weighted_price()` |

---

## Task 1: Quality Score Floor (0.2)

**Files:**
- Modify: `scrapers/comp_matcher.py:23-31`
- Modify: `db/sqlite_models.py:1174`
- Modify: `tests/unit/test_quality_weight.py`

- [ ] **Step 1: Update `quality_weight()` floor to 0.2**

In `scrapers/comp_matcher.py` line 31, change:

```python
# OLD
return max(0.0, min(1.0, quality_score))

# NEW
return max(0.2, min(1.0, quality_score))
```

- [ ] **Step 2: Add 0.2 floor to `update_sold_comp_rejection()`**

In `db/sqlite_models.py` line 1174, change:

```python
# OLD
quality_score = 1.0 - (times_rejected / times_matched)

# NEW
quality_score = max(0.2, 1.0 - (times_rejected / times_matched))
```

- [ ] **Step 3: Update tests for 0.2 floor**

In `tests/unit/test_quality_weight.py`, replace the test class:

```python
"""Tests for the quality_weight function in comp_matcher."""

from scrapers.comp_matcher import quality_weight


class TestQualityWeight:
    def test_none_returns_one(self):
        assert quality_weight(None) == 1.0

    def test_perfect_score(self):
        assert quality_weight(1.0) == 1.0

    def test_zero_score_floors_at_0_2(self):
        assert quality_weight(0.0) == 0.2

    def test_half_score(self):
        assert quality_weight(0.5) == 0.5

    def test_low_score_floors_at_0_2(self):
        assert quality_weight(0.1) == 0.2

    def test_above_floor(self):
        assert quality_weight(0.3) == 0.3

    def test_clamps_above_one(self):
        assert quality_weight(1.5) == 1.0

    def test_clamps_below_zero_to_floor(self):
        assert quality_weight(-0.5) == 0.2

    def test_score_integrated_in_similarity(self):
        """quality_score should reduce the final similarity score."""
        from scrapers.comp_matcher import parse_title, score_comp_similarity
        parsed = parse_title("rick owens", "Rick Owens Geobasket Leather Sneakers")
        comp_title = "Rick Owens Geobasket High Top Sneakers"

        score_good = score_comp_similarity(parsed, comp_title, comp_quality_score=1.0)
        score_bad = score_comp_similarity(parsed, comp_title, comp_quality_score=0.0)

        assert score_good > score_bad
        assert score_bad >= 0.2 * score_good  # floor is 0.2
```

- [ ] **Step 4: Run tests to verify**

Run: `python3 -m pytest tests/unit/test_quality_weight.py -v -o addopts=""`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scrapers/comp_matcher.py db/sqlite_models.py tests/unit/test_quality_weight.py
git commit -m "fix: add 0.2 floor to quality_weight and update_sold_comp_rejection"
```

---

## Task 2: `get_comp_quality_scores()` Batch Lookup

**Files:**
- Modify: `db/sqlite_models.py`
- Create: `tests/unit/test_comp_quality_lookup.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_comp_quality_lookup.py`:

```python
"""Tests for batch quality score lookup."""

import sqlite3
from db.sqlite_models import get_comp_quality_scores, init_db, _get_conn


class TestGetCompQualityScores:
    def setup_method(self):
        """Use in-memory DB for tests."""
        import db.sqlite_models as sm
        sm._conn = sqlite3.connect(":memory:")
        sm._conn.row_factory = sqlite3.Row
        init_db()
        # Seed test data
        c = sm._conn.cursor()
        c.execute(
            "INSERT INTO sold_comps (search_key, brand, title, sold_price, source, source_id, quality_score) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("test", "rick owens", "RO Geobasket", 500, "grailed", "g123", 0.8),
        )
        c.execute(
            "INSERT INTO sold_comps (search_key, brand, title, sold_price, source, source_id, quality_score) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("test", "rick owens", "RO Ramones", 300, "grailed", "g456", 0.3),
        )
        sm._conn.commit()

    def test_returns_known_scores(self):
        scores = get_comp_quality_scores([("grailed", "g123"), ("grailed", "g456")])
        assert scores[("grailed", "g123")] == 0.8
        assert scores[("grailed", "g456")] == 0.3

    def test_returns_1_for_unknown(self):
        scores = get_comp_quality_scores([("grailed", "unknown")])
        assert scores[("grailed", "unknown")] == 1.0

    def test_empty_input(self):
        scores = get_comp_quality_scores([])
        assert scores == {}

    def test_mixed_known_and_unknown(self):
        scores = get_comp_quality_scores([("grailed", "g123"), ("ebay", "e999")])
        assert scores[("grailed", "g123")] == 0.8
        assert scores[("ebay", "e999")] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_comp_quality_lookup.py -v -o addopts=""`
Expected: FAIL — `ImportError: cannot import name 'get_comp_quality_scores'`

- [ ] **Step 3: Implement `get_comp_quality_scores()`**

Add to `db/sqlite_models.py` after `get_sold_comps()` (after line ~970):

```python
def get_comp_quality_scores(source_id_pairs: list) -> dict:
    """Batch lookup quality scores for sold comps by (source, source_id).

    Args:
        source_id_pairs: List of (source, source_id) tuples

    Returns:
        Dict of (source, source_id) -> quality_score. Defaults to 1.0 for unknown comps.
    """
    if not source_id_pairs:
        return {}

    result = {pair: 1.0 for pair in source_id_pairs}

    conn = _get_conn()
    c = conn.cursor()

    # Build query for all pairs
    placeholders = " OR ".join(["(source = ? AND source_id = ?)"] * len(source_id_pairs))
    params = []
    for source, source_id in source_id_pairs:
        params.extend([source, source_id])

    c.execute(
        f"SELECT source, source_id, quality_score FROM sold_comps WHERE {placeholders}",
        params,
    )
    for row in c.fetchall():
        key = (row["source"], row["source_id"])
        result[key] = row["quality_score"] if row["quality_score"] is not None else 1.0

    conn.close()
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/unit/test_comp_quality_lookup.py -v -o addopts=""`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add db/sqlite_models.py tests/unit/test_comp_quality_lookup.py
git commit -m "feat: add get_comp_quality_scores batch lookup"
```

---

## Task 3: `compute_weighted_price()`

**Files:**
- Create: `tests/unit/test_weighted_pricing.py`
- Modify: `gap_hunter.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_weighted_pricing.py`:

```python
"""Tests for similarity-weighted median pricing."""

import sys
from types import SimpleNamespace
from unittest.mock import patch


def _make_comp(title, price, source="grailed", source_id=""):
    """Create a mock sold comp object."""
    return SimpleNamespace(
        title=title, price=price, source=source,
        source_id=source_id or f"id_{price}",
        raw_data={}, url="", size=None, condition=None,
    )


class TestComputeWeightedPrice:
    def _import(self):
        from gap_hunter import compute_weighted_price
        return compute_weighted_price

    def test_drop_gate_removes_low_similarity(self):
        """With 3+ comps above 0.5, comps below 0.5 are dropped."""
        fn = self._import()
        comps = [
            _make_comp("Chrome Hearts Cemetery Cross Ring Silver", 2500),
            _make_comp("Chrome Hearts Cemetery Cross Ring", 2200),
            _make_comp("Chrome Hearts Cemetery Cross Pendant", 2400),
            _make_comp("Chrome Hearts Spacer Ring", 200),  # wrong product
            _make_comp("Chrome Hearts Ring Silver", 400),  # too generic
        ]
        sold_data = SimpleNamespace(
            query="chrome hearts ring", avg_price=1500, median_price=1500, count=5,
            liquidation_anchor=None, downside_anchor=None,
            _confidence="medium", _cv=0.3, _hyper_pricing=False,
            comp_confidence_penalty=0, pricing_confidence="medium",
            comp_titles=[c.title for c in comps],
            comp_prices=[c.price for c in comps],
            comp_urls=[""] * 5,
            timestamp=0,
        )
        with patch("gap_hunter.get_comp_quality_scores", return_value={}):
            result = fn("Chrome Hearts Cemetery Cross Ring Sterling Silver Size 9", "chrome hearts", comps, sold_data)

        assert result is not None
        # Should use Cemetery Cross comps (~$2200-2500), not Spacer ($200)
        assert result.median_price > 1500
        assert result.count <= 4  # Spacer should be dropped

    def test_hard_gate_returns_none_when_no_match(self):
        """If no comps have similarity >= 0.5, return None."""
        fn = self._import()
        comps = [
            _make_comp("Chrome Hearts Trucker Hat", 800),
            _make_comp("Chrome Hearts Hoodie", 600),
        ]
        sold_data = SimpleNamespace(
            query="chrome hearts ring", avg_price=700, median_price=700, count=2,
            liquidation_anchor=None, downside_anchor=None,
            _confidence="medium", _cv=0.3, _hyper_pricing=False,
            comp_confidence_penalty=0, pricing_confidence="medium",
            comp_titles=[c.title for c in comps],
            comp_prices=[c.price for c in comps],
            comp_urls=[""] * 2,
            timestamp=0,
        )
        with patch("gap_hunter.get_comp_quality_scores", return_value={}):
            result = fn("Chrome Hearts Cemetery Cross Ring Silver", "chrome hearts", comps, sold_data)

        assert result is None

    def test_downweight_fallback_when_few_above_threshold(self):
        """If 1-2 above 0.5, keep all but weight by similarity."""
        fn = self._import()
        comps = [
            _make_comp("Rick Owens Geobasket Leather", 900),  # good match
            _make_comp("Rick Owens Sneakers Black", 500),  # partial match
            _make_comp("Rick Owens Pants Cargo", 300),  # bad match
        ]
        sold_data = SimpleNamespace(
            query="rick owens geobasket", avg_price=550, median_price=500, count=3,
            liquidation_anchor=None, downside_anchor=None,
            _confidence="medium", _cv=0.3, _hyper_pricing=False,
            comp_confidence_penalty=0, pricing_confidence="medium",
            comp_titles=[c.title for c in comps],
            comp_prices=[c.price for c in comps],
            comp_urls=[""] * 3,
            timestamp=0,
        )
        with patch("gap_hunter.get_comp_quality_scores", return_value={}):
            result = fn("Rick Owens Geobasket Black Leather EU 43", "rick owens", comps, sold_data)

        # If only 1 comp above 0.5, all are kept but weighted
        # Geobasket comp should have highest weight, pulling price up
        assert result is not None
        assert result.avg_price > 500  # weighted toward geobasket ($900)

    def test_quality_score_reduces_effective_similarity(self):
        """A comp with low quality_score gets its similarity reduced."""
        fn = self._import()
        comps = [
            _make_comp("Chrome Hearts Forever Ring Silver", 400, source_id="good1"),
            _make_comp("Chrome Hearts Forever Ring", 380, source_id="good2"),
            _make_comp("Chrome Hearts Forever Ring 925", 420, source_id="good3"),
            _make_comp("Chrome Hearts Forever Ring Sterling", 350, source_id="bad1"),
        ]
        sold_data = SimpleNamespace(
            query="chrome hearts forever ring", avg_price=390, median_price=390, count=4,
            liquidation_anchor=None, downside_anchor=None,
            _confidence="medium", _cv=0.1, _hyper_pricing=False,
            comp_confidence_penalty=0, pricing_confidence="medium",
            comp_titles=[c.title for c in comps],
            comp_prices=[c.price for c in comps],
            comp_urls=[""] * 4,
            timestamp=0,
        )
        # bad1 has quality_score 0.2 (heavily rejected)
        quality_scores = {("grailed", "bad1"): 0.2}
        with patch("gap_hunter.get_comp_quality_scores", return_value=quality_scores):
            result = fn("Chrome Hearts Forever Ring Sterling Silver", "chrome hearts", comps, sold_data)

        assert result is not None
        # bad1's effective similarity = raw_sim * 0.2, should be downweighted
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/unit/test_weighted_pricing.py -v -o addopts=""`
Expected: FAIL — `ImportError: cannot import name 'compute_weighted_price'`

- [ ] **Step 3: Implement `compute_weighted_price()`**

Add to `gap_hunter.py` before the `GapHunter` class definition (before line ~662). This is a module-level function, not a method:

```python
def compute_weighted_price(
    item_title: str,
    brand: str,
    sold_items: list,
    sold_data: SoldData,
) -> Optional[SoldData]:
    """Score each comp against the listing and compute similarity-weighted pricing.

    Returns a new SoldData with recalculated prices, or None if no comps
    are similar enough (hard gate: 0 comps above 0.5 similarity).
    """
    from scrapers.comp_matcher import parse_title, score_comp_similarity
    from db.sqlite_models import get_comp_quality_scores

    if not sold_items:
        return None

    listing_fp = parse_title(brand, item_title)

    # Look up quality scores for all comps in one batch
    source_pairs = [
        (getattr(c, 'source', 'grailed'), getattr(c, 'source_id', ''))
        for c in sold_items
    ]
    quality_scores = get_comp_quality_scores(source_pairs)

    # Score each comp
    scored = []
    for i, comp in enumerate(sold_items):
        if not comp.price or comp.price <= 0:
            continue
        source = getattr(comp, 'source', 'grailed')
        source_id = getattr(comp, 'source_id', '')
        q_score = quality_scores.get((source, source_id), 1.0)
        similarity = score_comp_similarity(listing_fp, comp.title, comp_quality_score=q_score)
        scored.append((comp, similarity))

    if not scored:
        return None

    # Sort by similarity descending for logging
    scored.sort(key=lambda x: x[1], reverse=True)

    above_threshold = [(c, s) for c, s in scored if s >= 0.5]
    below_threshold = [(c, s) for c, s in scored if s < 0.5]

    # Gate logic
    if len(above_threshold) >= 3:
        # Drop gate: enough good comps, drop the rest
        final = above_threshold
    elif len(above_threshold) == 0:
        # Hard gate: no comps similar enough — skip this item
        logger.info(
            f"    ❌ No comps above 0.5 similarity for '{item_title[:50]}' "
            f"(best: {scored[0][1]:.2f} '{scored[0][0].title[:40]}')"
        )
        return None
    else:
        # Downweight fallback: keep all, weight by similarity
        final = scored

    # Compute weighted median
    final.sort(key=lambda x: x[0].price)
    total_weight = sum(s for _, s in final)
    if total_weight <= 0:
        return None

    # Walk through prices accumulating weight until 50th percentile
    cumulative = 0.0
    weighted_median = final[-1][0].price  # fallback to highest
    for comp, sim in final:
        cumulative += sim
        if cumulative >= total_weight * 0.5:
            weighted_median = comp.price
            break

    # Weighted average
    weighted_avg = sum(c.price * s for c, s in final) / total_weight

    # Build new SoldData
    surviving_comps = [c for c, _ in final]
    similarity_scores = [s for _, s in final]

    result = SoldData(
        query=sold_data.query,
        avg_price=weighted_avg,
        median_price=weighted_median,
        min_price=min(c.price for c in surviving_comps),
        max_price=max(c.price for c in surviving_comps),
        count=len(final),
        timestamp=sold_data.timestamp,
    )
    # Carry over attributes from original
    result.comp_titles = [c.title for c in surviving_comps]
    result.comp_prices = [c.price for c in surviving_comps]
    result.comp_urls = [getattr(c, 'url', None) for c in surviving_comps]
    result.comp_sizes = [getattr(c, 'size', None) for c in surviving_comps]
    result._similarity_scores = similarity_scores
    result._confidence = getattr(sold_data, '_confidence', 'medium')
    result._cv = getattr(sold_data, '_cv', None)
    result._hyper_pricing = getattr(sold_data, '_hyper_pricing', False)
    result.comp_confidence_penalty = getattr(sold_data, 'comp_confidence_penalty', 0)
    result.pricing_confidence = getattr(sold_data, 'pricing_confidence', 'medium')
    result.liquidation_anchor = getattr(sold_data, 'liquidation_anchor', None)
    result.downside_anchor = getattr(sold_data, 'downside_anchor', None)
    result._authenticated_comps = getattr(sold_data, '_authenticated_comps', 0)
    result._auth_confidence = getattr(sold_data, '_auth_confidence', 0.0)

    logger.info(
        f"    📊 Weighted pricing: {len(final)} comps "
        f"(dropped {len(scored) - len(final)}), "
        f"median ${weighted_median:.0f}, avg ${weighted_avg:.0f}, "
        f"best sim={similarity_scores[0]:.2f}"
    )

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/unit/test_weighted_pricing.py -v -o addopts=""`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add gap_hunter.py tests/unit/test_weighted_pricing.py
git commit -m "feat: add compute_weighted_price with similarity scoring and drop/hard gates"
```

---

## Task 4: Wire `get_sold_data()` to Return Raw Items

**Files:**
- Modify: `gap_hunter.py:1042-1391`

- [ ] **Step 1: Modify `get_sold_data()` to return raw items when `return_raw=True`**

The `return_raw` parameter exists in the signature (line 1042) but is never used. Three return paths need updating:

**Path 1 — PricingEngine cache hit (line ~1062):** Skip when `return_raw=True` — raw items aren't available from cache:

```python
        # ── Try PricingEngine first ──
        # Skip PricingEngine cache when caller needs raw items for similarity scoring
        pricing_engine = _get_pricing_engine()
        if pricing_engine and not return_raw:
```

**Path 2 — sold_cache hit (line ~1073):** Store raw items alongside cached SoldData. Add a parallel cache:

After `self.sold_cache: Dict[str, SoldData] = {}` in `__init__`, add:
```python
self._raw_items_cache: Dict[str, list] = {}  # raw sold items parallel to sold_cache
```

Also in `run_cycle()`, add clearing alongside the existing `_item_comp_cache.clear()`:
```python
self._item_comp_cache.clear()
self._raw_items_cache.clear()
```

At the sold_cache return (line ~1076):
```python
        if query in self.sold_cache:
            cached = self.sold_cache[query]
            if time.time() - cached.timestamp < SOLD_CACHE_TTL:
                if return_raw:
                    raw = self._raw_items_cache.get(query, [])
                    return (cached, raw)
                return cached
```

**Path 3 — Fresh data return (line ~1386):** Save raw items to cache and return tuple:

Before `self.sold_cache[query] = data` (line ~1386), add:
```python
            self._raw_items_cache[query] = list(valid_comps)
```

Change the return (line ~1387):
```python
            self.sold_cache[query] = data
            if return_raw:
                return (data, list(valid_comps))
            return data
```

**Error path (line ~1391):** Return tuple on error too:
```python
        except Exception as e:
            logger.debug(f"Sold data failed for '{query}': {e}")
            if return_raw:
                return (None, [])
            return None
```

- [ ] **Step 2: Verify compilation**

Run: `python3 -c "import py_compile; py_compile.compile('gap_hunter.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add gap_hunter.py
git commit -m "feat: get_sold_data returns raw items when return_raw=True"
```

---

## Task 5: Wire `compute_weighted_price()` into `get_item_specific_comps()`

**Files:**
- Modify: `gap_hunter.py:1536-1610`

- [ ] **Step 1: Update `get_item_specific_comps()` to use return_raw and weighted pricing**

In `get_item_specific_comps()`, change the sold data fetch and return logic. Replace the section inside the query loop (the `get_sold_data` call and the success check):

```python
        for query_str, expected_quality in queries_by_specificity[:3]:
            cache_key = query_str.strip().lower()

            # Check per-item comp cache first
            if cache_key in self._item_comp_cache:
                cached = self._item_comp_cache[cache_key]
                if cached is not None and cached.count >= 3:
                    logger.info(
                        f"    🎯 Item comps (cached): '{query_str}' → "
                        f"${cached.avg_price:.0f} ({cached.count} comps)"
                    )
                    return (cached, query_str, True)
                continue

            # Also check the existing sold_cache (populated by generic queries)
            if cache_key in self.sold_cache:
                cached = self.sold_cache[cache_key]
                if time.time() - cached.timestamp < SOLD_CACHE_TTL and cached.count >= 3:
                    # Need raw items for similarity scoring
                    raw = self._raw_items_cache.get(cache_key, [])
                    if raw:
                        weighted = compute_weighted_price(item.title, brand, raw, cached)
                        if weighted is not None:
                            self._item_comp_cache[cache_key] = weighted
                            logger.info(
                                f"    🎯 Item comps (sold_cache+weighted): '{query_str}' → "
                                f"${weighted.avg_price:.0f} ({weighted.count} comps)"
                            )
                            return (weighted, query_str, True)
                    else:
                        # No raw items available — use cached SoldData as-is
                        self._item_comp_cache[cache_key] = cached
                        logger.info(
                            f"    🎯 Item comps (sold_cache): '{query_str}' → "
                            f"${cached.avg_price:.0f} ({cached.count} comps)"
                        )
                        return (cached, query_str, True)

            # Fetch fresh sold data with raw items for similarity scoring
            result = await self.get_sold_data(query_str, return_raw=True)
            if isinstance(result, tuple):
                sold, raw_items = result
            else:
                sold, raw_items = result, []

            self._item_comp_cache[cache_key] = sold

            if sold and sold.count >= 3 and raw_items:
                weighted = compute_weighted_price(item.title, brand, raw_items, sold)
                if weighted is not None:
                    self._item_comp_cache[cache_key] = weighted
                    logger.info(
                        f"    🎯 Item comps (fresh+weighted): '{query_str}' → "
                        f"${weighted.avg_price:.0f} ({weighted.count} comps, "
                        f"quality={expected_quality:.2f})"
                    )
                    return (weighted, query_str, True)
                else:
                    logger.debug(
                        f"    ℹ️ Weighted pricing returned None for '{query_str}' "
                        f"— no comps similar enough"
                    )
            elif sold:
                logger.debug(
                    f"    ℹ️ Specific query '{query_str}' returned only "
                    f"{sold.count} comps (need 3)"
                )
```

- [ ] **Step 2: Verify compilation**

Run: `python3 -c "import py_compile; py_compile.compile('gap_hunter.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add gap_hunter.py
git commit -m "feat: wire compute_weighted_price into get_item_specific_comps"
```

---

## Task 6: Embed Comps on Save

**Files:**
- Modify: `gap_hunter.py:1310-1320` (inside `get_sold_data()` where comps are persisted)

- [ ] **Step 1: Replace `save_sold_comp()` with `save_comp_with_embedding()`**

In `get_sold_data()`, find the comp persistence block (line ~1310-1320). Replace:

```python
            # ── Persist sold comps to DB for reliable retrieval at item persist time ──
            from db.sqlite_models import save_sold_comp
            for vc in valid_comps[:15]:
                try:
                    save_sold_comp(query, {
                        "brand": query_brand,
                        "title": vc.title,
                        "sold_price": vc.price,
                        "size": getattr(vc, 'size', None),
                        "sold_url": getattr(vc, 'url', None),
```

With:

```python
            # ── Persist sold comps to DB with embeddings ──
            from scrapers.title_matcher import get_title_embedding, save_comp_with_embedding
            from scrapers.comp_matcher import parse_title as _cm_parse
            for vc in valid_comps[:15]:
                try:
                    # Generate embedding for semantic search
                    emb = get_title_embedding(vc.title)
                    # Parse structured data for DB enrichment
                    vc_fp = _cm_parse(query_brand, vc.title) if query_brand else None
                    save_comp_with_embedding(
                        search_key=query,
                        title=vc.title,
                        brand=query_brand,
                        sold_price=vc.price,
                        source=getattr(vc, 'source', 'grailed'),
                        source_id=getattr(vc, 'source_id', ''),
                        size=getattr(vc, 'size', None) or '',
                        condition=getattr(vc, 'condition', None) or '',
                        sold_url=getattr(vc, 'url', None) or '',
                        sold_date=str((vc.raw_data or {}).get('sold_at', '')),
                        embedding=emb,
                        platform=getattr(vc, 'source', 'grailed'),
                        item_type=vc_fp.item_type if vc_fp else '',
                        model_name=vc_fp.model if vc_fp else '',
                        sub_brand=vc_fp.sub_brand if vc_fp else '',
                        material=vc_fp.material if vc_fp else '',
                        color=vc_fp.color if vc_fp else '',
                        season=vc_fp.season if vc_fp else '',
                    )
```

Keep the same `except` block that follows.

- [ ] **Step 2: Add backfill warning on startup**

In `gap_hunter.py`, in the `run()` method (line ~3056), after the startup logging, add:

```python
        # Check for comps that need embedding backfill
        try:
            import sqlite3 as _sq
            _c = _sq.connect(str(os.path.join(os.path.dirname(__file__), "data", "archive.db")))
            _missing = _c.execute("SELECT COUNT(*) FROM sold_comps WHERE title_embedding IS NULL").fetchone()[0]
            _c.close()
            if _missing > 100:
                logger.warning(f"  ⚠️ {_missing} comps lack embeddings — run with BACKFILL_EMBEDDINGS=1")
        except Exception:
            pass

        if os.getenv("BACKFILL_EMBEDDINGS", "0") == "1":
            try:
                from scrapers.title_matcher import backfill_embeddings
                count = backfill_embeddings()
                if count > 0:
                    logger.info(f"  📦 Backfilled embeddings for {count} comps")
            except Exception as e:
                logger.warning(f"  ⚠️ Embedding backfill failed: {e}")
```

- [ ] **Step 3: Verify compilation**

Run: `python3 -c "import py_compile; py_compile.compile('gap_hunter.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add gap_hunter.py
git commit -m "feat: embed comps on save via save_comp_with_embedding, add backfill on startup"
```

---

## Task 7: Merge Historical DB Results into `get_item_specific_comps()`

**Files:**
- Modify: `gap_hunter.py:1536` (`get_item_specific_comps()`)

- [ ] **Step 1: Add DB embedding search after the live query loop**

At the end of `get_item_specific_comps()`, before the fallback return, add a DB embedding search that supplements the live results. Insert before `# None of the specific queries returned enough comps`:

```python
        # ── Historical DB search via embeddings ──
        # Even if live search didn't find specific comps, the DB might have
        # matching comps from previous cycles
        try:
            from scrapers.title_matcher import get_title_embedding, search_comps_by_embedding
            listing_emb = get_title_embedding(item.title)
            if listing_emb is not None:
                db_comps = search_comps_by_embedding(listing_emb, brand=brand, limit=20)
                # Filter to reasonable similarity (embedding scale differs from keyword)
                db_comps = [c for c in db_comps if c.get("similarity", 0) >= 0.4]
                if db_comps:
                    # Convert DB results to comp-like objects for compute_weighted_price
                    db_items = []
                    for dc in db_comps:
                        db_items.append(SimpleNamespace(
                            title=dc.get("title", ""),
                            price=dc.get("sold_price", 0),
                            source=dc.get("source", dc.get("platform", "grailed")),
                            source_id=dc.get("source_id", ""),
                            url=dc.get("url", ""),
                            size=dc.get("size"),
                            condition=dc.get("condition"),
                            raw_data={},
                        ))

                    # Deduplicate against any comps we already found
                    seen_ids = set()
                    merged = []
                    for c in db_items:
                        key = f"{c.source}:{c.source_id}"
                        if key not in seen_ids and c.price > 0:
                            seen_ids.add(key)
                            merged.append(c)

                    if len(merged) >= 3:
                        weighted = compute_weighted_price(item.title, brand, merged, generic_sold)
                        if weighted is not None:
                            logger.info(
                                f"    🎯 Item comps (DB embeddings): {len(merged)} comps → "
                                f"${weighted.avg_price:.0f} ({weighted.count} used)"
                            )
                            return (weighted, f"[db:{brand}]", True)
        except Exception as e:
            logger.debug(f"    ⚠️ DB embedding search failed: {e}")
```

Add the `SimpleNamespace` import at the top of `gap_hunter.py` if not already present:
```python
from types import SimpleNamespace
```

- [ ] **Step 2: Verify compilation**

Run: `python3 -c "import py_compile; py_compile.compile('gap_hunter.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add gap_hunter.py
git commit -m "feat: merge historical DB embedding results into item comp lookup"
```

---

## Task 8: Wire Similarity Scores into `link_item_to_sold_comps()`

**Files:**
- Modify: `db/sqlite_models.py:1062-1091`

- [ ] **Step 1: Modify `link_item_to_sold_comps()` to accept external similarity scores**

Change the function signature and logic to use real similarity scores when provided:

```python
def link_item_to_sold_comps(
    item_id: int,
    search_key: str,
    limit: int = 15,
    similarity_scores: Optional[List[float]] = None,
) -> int:
    """Link an item to its sold comps by searching sold_comps table.

    Args:
        item_id: The item to link comps to
        search_key: Query used to find matching comps
        limit: Max comps to link
        similarity_scores: Pre-computed similarity scores from compute_weighted_price().
            If provided, used instead of synthetic rank-based scores.

    Returns number of comps linked.
    """
    comps = get_sold_comps(search_key=search_key, limit=limit)
    if not comps:
        return 0

    entries = []
    for rank, sc in enumerate(comps, start=1):
        # Use provided similarity score if available, otherwise synthetic fallback
        if similarity_scores and rank - 1 < len(similarity_scores):
            sim = similarity_scores[rank - 1]
        else:
            sim = max(0.5, 1.0 - rank * 0.03)

        entries.append({
            "sold_comp_id": sc.get("id"),
            "similarity_score": sim,
            "rank": rank,
            "snapshot_title": sc.get("title"),
            "snapshot_price": sc.get("sold_price"),
            "snapshot_condition": sc.get("condition"),
            "snapshot_source": sc.get("source", "grailed"),
            "snapshot_sold_date": sc.get("sold_date"),
            "snapshot_url": sc.get("sold_url"),
        })

    save_item_comps(item_id, entries)
    return len(entries)
```

- [ ] **Step 2: Pass similarity scores from `find_gaps()` deal persistence**

In `gap_hunter.py`, find where `link_item_to_sold_comps` is called (around line ~2740). Add similarity_scores:

```python
                comp_count_saved = link_item_to_sold_comps(
                    persisted_id, deal.query,
                    similarity_scores=getattr(effective_sold, '_similarity_scores', None),
                )
```

- [ ] **Step 3: Verify compilation**

Run: `python3 -c "import py_compile; py_compile.compile('gap_hunter.py', doraise=True); py_compile.compile('db/sqlite_models.py', doraise=True); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add db/sqlite_models.py gap_hunter.py
git commit -m "feat: pass real similarity scores to link_item_to_sold_comps"
```

---

## Task 9: Integration Test

**Files:**
- No new files — manual verification

- [ ] **Step 1: Run all unit tests**

Run: `python3 -m pytest tests/unit/ -v -o addopts="" 2>&1 | tail -20`
Expected: All tests PASS (including new tests from Tasks 1-3)

- [ ] **Step 2: Run a single-query cycle to verify end-to-end**

```bash
python3 -c "
import asyncio
from gap_hunter import GapHunter

async def test():
    gh = GapHunter()
    await gh.run_cycle(custom_queries=['chrome hearts cemetery cross ring'], max_targets=1)
    print(f'Stats: {dict(gh.stats)}')

asyncio.run(test())
" 2>&1 | grep -E "🎯|📊|❌|Item comp"
```

Expected output should show:
- `🎯 Item comps` lines showing per-item comp lookups
- `📊 Weighted pricing` lines showing similarity scoring
- `item_specific_comp_hits` or `item_specific_comp_misses` in stats
- No `❌ No comps above 0.5 similarity` for correctly-matched items

- [ ] **Step 3: Commit all remaining changes**

```bash
git add -A
git commit -m "feat: comp precision system — similarity-weighted pricing, embeddings, feedback loop"
```

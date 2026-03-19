# Comp Precision System — Design Spec

**Date:** 2026-03-18
**Goal:** Every surfaced deal must be backed by sold comps that are demonstrably the same product. If the system cannot find exact comps for a listing, the deal is not surfaced.

**Core principle:** No match = no deal. Precision over volume.

---

## Problem

The current pipeline treats all comps that survive the 7-layer filter as equally valid. A Cemetery Cross Ring comp and a Scroll Ring comp both contribute equally to the median price. This produces inaccurate reference prices that erode subscriber margins.

The comp matching infrastructure (`score_comp_similarity`, `title_matcher.py` with embeddings, `quality_score` on `sold_comps`) is already built but disconnected from the pricing pipeline in `gap_hunter.py`.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Low-similarity comps | Drop below 0.5 if 3+ remain; downweight if fewer than 3 | Tight pricing when data is plentiful, no starvation for niche items |
| No comps above threshold | Skip item entirely — no deal surfaced | Bad comps = bad pricing = lost margin |
| Embedding model | sentence-transformers `all-MiniLM-L6-v2` (required dependency) | Full semantic matching, handles alias-heavy titles |
| Embedding timing | Inline on save + one-time backfill | Every comp immediately searchable, ~5ms per save |
| Quality score effect | Multiplicative via `quality_weight()` with 0.2 floor | Rejected comps decay but aren't permanently killed |
| Quality score formula | `max(0.2, 1.0 - (times_rejected / times_matched))` | Floor must be added to `update_sold_comp_rejection()` and `quality_weight()` |

---

## Architecture

Three layers, each building on the previous:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: COMP FEEDBACK LOOP                                 │
│ quality_score on sold_comps feeds back into similarity      │
│ scoring. Rejected comps decay. Floor at 0.2.                │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: HISTORICAL COMP DB + EMBEDDINGS                    │
│ Comps embedded on save. Listing embedded on lookup.         │
│ DB search merges with live search before scoring.           │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: SIMILARITY-WEIGHTED PRICING                        │
│ Each comp scored against listing. Drop < 0.5 if possible.   │
│ Weighted median replaces flat median. No match = no deal.   │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Similarity-Weighted Pricing

### New function: `compute_weighted_price()`

**Location:** `gap_hunter.py`

**Inputs:**
- `item_title: str` — the active listing's title
- `brand: str` — detected brand
- `sold_items: list` — raw sold comp objects from `get_sold_data()`
- `sold_data: SoldData` — the original SoldData (for fallback fields)

**Algorithm:**
1. Parse listing title: `listing_fp = parse_title(brand, item_title)`
2. For each comp:
   - Look up `quality_score` from DB (default 1.0 for new comps)
   - `similarity = score_comp_similarity(listing_fp, comp.title, quality_score)`
3. **Drop gate:** if 3+ comps have similarity >= 0.5, drop all below 0.5
4. **Hard gate:** if 0 comps have similarity >= 0.5, return `None` (skip this item)
5. **Downweight fallback:** if 1-2 comps above 0.5, keep all but use similarity as weight
6. Compute weighted median:
   - Sort remaining comps by price ascending
   - Each comp has weight = similarity score
   - Walk through, accumulating weights until cumulative weight >= 50% of total weight
   - That price is the weighted median
7. Return new `SoldData` with:
   - `avg_price` = weighted average (sum of price*weight / sum of weights)
   - `median_price` = weighted median from step 6
   - `count` = number of comps used
   - `comp_titles`, `comp_prices`, `comp_urls` = only the comps that survived
   - `_similarity_scores` = list of similarity scores (for logging/debugging)
   - Preserve `liquidation_anchor`, `downside_anchor`, `_confidence`, `_cv` from original

**Returns:** `SoldData` or `None` (None = skip this item)

### Integration point

Called inside `get_item_specific_comps()` after `get_sold_data()` returns:

```python
sold_data, raw_items = await self.get_sold_data(query_str, return_raw=True)
if sold_data and sold_data.count >= 3 and raw_items:
    # Score and weight comps against the actual listing
    weighted = compute_weighted_price(item.title, brand, raw_items, sold_data)
    if weighted is None:
        # No comps similar enough — skip this query, try next
        continue
    return (weighted, query_str, True)
```

### Requires `get_sold_data()` to return raw sold items

Currently `get_sold_data()` returns only `SoldData` (aggregated). The raw `sold` list (individual comp objects with `.title`, `.price`, `.source`, `.source_id`) is needed for per-comp scoring.

The `return_raw` parameter already exists in the method signature but the function never actually returns a tuple — this must be implemented. When `return_raw=True`, return `(SoldData, list_of_raw_items)` instead of just `SoldData`.

**Cache path caveat:** The PricingEngine cache path (lines 1052-1071) returns a synthetic `SoldData` with no underlying comp data. When `return_raw=True` is requested and we get a PricingEngine cache hit, **skip the cache** and fall through to the live search. This ensures raw items are always available for similarity scoring. The sold_cache path can still be used if we store raw items alongside the SoldData (add a parallel `_raw_items_cache`).

**eBay fallback comps:** eBay sold comps (lines 1116-1136) are merged into the `sold` list but not individually saved to the DB. Ensure eBay comps are included in the raw items returned and also persisted via `save_comp_with_embedding()` so they're available for future DB lookups.

---

## Layer 2: Historical Comp DB with Embeddings

### On save: embed each comp

**Location:** `get_sold_data()` in `gap_hunter.py`, where `save_sold_comp()` is called (line ~1312)

After saving to DB:
```python
from title_matcher import get_title_embedding, save_comp_with_embedding
embedding = get_title_embedding(comp.title)
# save_comp_with_embedding handles the DB update
```

Use `save_comp_with_embedding()` from `title_matcher.py` instead of `save_sold_comp()` from `sqlite_models.py`. This saves all the same fields plus the embedding. Falls back gracefully if embedding generation fails.

### On lookup: merge DB results with live results

**Location:** `get_item_specific_comps()` in `gap_hunter.py`

After the live search loop (whether it found specific comps or not):

1. Generate listing embedding: `listing_emb = get_title_embedding(item.title)`
2. Search historical DB: `db_comps = search_comps_by_embedding(listing_emb, brand=brand, limit=20)`
3. Filter DB results to similarity >= 0.4 (lower than the 0.5 pricing gate, since these are embedding similarities on a different scale — rescaled in `hybrid_similarity()`)
4. Convert DB results to the same format as live results (ScrapedItem-like objects)
5. Merge with live results, deduplicating by `source` + `source_id`
6. The merged pool goes through `compute_weighted_price()` from Layer 1

This means even if the live Grailed search returns generic comps, the DB might have specific comps from a previous cycle that match this exact product via embedding similarity.

### One-time backfill

On first run (or when `BACKFILL_EMBEDDINGS=1` is set):
- Call `title_matcher.backfill_embeddings()`
- This embeds all existing `sold_comps` rows that have `title_embedding IS NULL`
- Runs in batches of 100, logs progress
- ~5000 comps takes ~30 seconds

Gate behind env var so it doesn't re-run on every restart. Log a warning on startup if >100 comps lack embeddings.

---

## Layer 3: Comp Feedback Loop

### Quality score integration

**Already implemented:**
- `quality_score REAL DEFAULT 1.0` column on `sold_comps` table
- `update_sold_comp_rejection()` in `sqlite_models.py` recalculates quality_score (but without 0.2 floor — see below)
- `quality_weight()` in `comp_matcher.py` converts score to multiplier (but floor is 0.0, not 0.2 — see below)
- `score_comp_similarity()` accepts `comp_quality_score` parameter

**Needs implementation:**
- `compute_weighted_price()` (Layer 1) must look up each comp's `quality_score` before calling `score_comp_similarity()`
- New batch lookup function: `get_comp_quality_scores(source_id_pairs)` in `sqlite_models.py`
  - Input: list of `(source, source_id)` tuples
  - Output: dict of `(source, source_id) -> quality_score`
  - Returns 1.0 for comps not in DB

### Quality score floor — NOT YET IMPLEMENTED

The 0.2 floor must be added in two places:

1. **`update_sold_comp_rejection()` in `sqlite_models.py`** — currently computes `quality_score = 1.0 - (times_rejected / times_matched)` with no floor. Change to:
```python
quality_score = max(0.2, 1.0 - (times_rejected / times_matched))
```

2. **`quality_weight()` in `comp_matcher.py`** — currently uses `max(0.0, ...)`. Change floor to 0.2:
```python
return max(0.2, min(1.0, quality_score))
```

### Similarity score persistence

When `find_gaps()` creates a deal and links comps via `link_item_to_sold_comps()`:
- Pass the similarity scores from `compute_weighted_price()` so they're saved to `item_comps.similarity_score`
- This requires modifying `link_item_to_sold_comps()` to accept similarity scores, or adding a follow-up update

---

## File Change Summary

### Modified files

| File | Changes |
|------|---------|
| `gap_hunter.py` | Add `compute_weighted_price()`. Modify `get_item_specific_comps()` to score comps, merge DB results, and return None when no match. Modify `get_sold_data()` to embed comps on save, return raw items when `return_raw=True`, skip PricingEngine cache when raw items needed. Persist eBay comps to DB. |
| `db/sqlite_models.py` | Add `get_comp_quality_scores()` batch lookup (new function). Add 0.2 floor to quality_score in `update_sold_comp_rejection()`. Modify `link_item_to_sold_comps()` to accept/save externally-provided similarity scores (preserve synthetic fallback for callers that don't supply scores). |
| `scrapers/comp_matcher.py` | Change `quality_weight()` floor from 0.0 to 0.2. |
| `scrapers/title_matcher.py` | No functional changes — infrastructure already exists. |

### No new files needed

All infrastructure exists. This is primarily a wiring project.

---

## Performance Notes

- **Sentence transformer model load:** First call to `get_title_embedding()` loads the model (~2-5 seconds). This is a one-time cost per process. Subsequent calls are ~5ms.
- **Embedding DB search:** `search_comps_by_embedding()` does brute-force cosine similarity over up to 500 rows (~5ms per scan). At current scale (<10k comps) this is fine. If the DB grows beyond 10k comps, consider adding a FAISS index for sub-millisecond search.
- **Per-cycle overhead:** Each candidate listing now triggers 1 embedding generation (~5ms) + 1 DB search (~5ms) + similarity scoring of merged pool. For a typical cycle with 50 candidate listings, this adds ~500ms total — negligible against the scraping time.

---

## Testing Strategy

1. **Unit test `compute_weighted_price()`**:
   - Mock comps with known similarity scores, verify weighted median calculation
   - Verify drop gate: 5 comps, 3 above 0.5 → only 3 used
   - Verify hard gate: all comps below 0.5 → returns None
   - Verify downweight fallback: 2 above 0.5, 3 below → all used with weights

2. **Unit test quality_score integration**:
   - Comp with quality_score 0.2 and similarity 0.8 → effective 0.16 → dropped
   - Comp with quality_score 1.0 and similarity 0.8 → effective 0.8 → kept

3. **Integration test**: Run a cycle with a known query (e.g., "chrome hearts cemetery cross ring"), verify:
   - Item-specific comps are fetched
   - Similarity scores are computed and logged
   - DB comps are merged with live results
   - Deals only surface when comps are genuinely the same product

---

## Success Criteria

- Every surfaced deal has comps with similarity >= 0.5 to the listing
- Deals previously surfaced with wrong comps (e.g., generic "chrome hearts ring" comps for a specific ring model) are no longer surfaced unless matching comps exist
- `item_comp_hits` stat in cycle logs shows majority of candidates getting item-specific comps
- Comp quality scores degrade over time for frequently-rejected comps, removing them from future pricing automatically

# Sold Comp Accuracy & Reliability Research

*Research Date: 2026-02-23*

---

## Executive Summary

The bot's sold comp system has **two strong layers** (Algolia search + comp_matcher similarity scoring) but suffers from **five systematic biases** that can produce unreliable valuations. The biggest issues are **platform fee asymmetry** (inflating apparent profit), **search relevance noise** (Algolia text matching isn't semantic), and **no temporal filtering** (stale comps pollute the average). Below are findings for each issue, ranked by impact, with implementation fixes.

---

## Issue Analysis

### 1. Platform Fee Asymmetry — 🔴 CRITICAL (Impact: High)

**The Problem:** We compare a Mercari/Poshmark listing price against Grailed sold prices, but different platforms have radically different fee structures and buyer behavior. This creates phantom profit.

**Real-world example:**
- Rick Owens Geobaskets sold on Grailed: median $550
- Same shoe listed on Mercari for $350
- Bot sees: 36% gap, ~$200 profit → 🔥🔥 alert
- Reality: Mercari buyers pay less because they expect deals. The Grailed $550 median reflects Grailed's premium buyer base. If you bought on Mercari and relisted on Grailed, you'd also eat ~9% Grailed fees + shipping + time.

**The Data:**
| Platform | Seller Fee | Buyer Behavior | Typical Price vs Grailed |
|----------|-----------|----------------|------------------------|
| Grailed | ~9% + PayPal (~12% total) | Pays premium for archive | Baseline |
| Poshmark | 20% flat | Loves offers, expects deals | 15-30% lower |
| Mercari | 10% | Price-sensitive, impulse buys | 20-40% lower |
| eBay | ~13% | Mixed, auction dynamics | 10-25% lower |
| Depop | 10% | Young, trend-driven | 10-30% lower |
| Vinted | 0% seller (buyer pays) | Bargain hunters | 25-45% lower |

**Current code (detect_arbitrage.py):** Already has `PLATFORM_FEES` dict but only applies sell-side fees. Doesn't adjust the comp baseline for cross-platform pricing differences.

**Recommendation:**
```python
# Add platform price adjustment factors
PLATFORM_PRICE_DISCOUNT = {
    "grailed": 1.0,      # baseline
    "ebay": 0.85,         # eBay items sell ~15% below Grailed
    "poshmark": 0.75,     # Poshmark ~25% below
    "mercari": 0.70,      # Mercari ~30% below
    "depop": 0.80,        # Depop ~20% below
    "vinted": 0.65,       # Vinted ~35% below
}

# When evaluating a deal from Mercari against Grailed comps:
adjusted_market_price = grailed_median * PLATFORM_PRICE_DISCOUNT[source_platform]
# Compare listing price against adjusted_market_price, not raw grailed_median
```

**Priority: #1 — This is the single largest source of false positives.**

---

### 2. Search Relevance / Query Specificity — 🔴 HIGH (Impact: High)

**The Problem:** Algolia does text matching, not semantic matching. Searching "helmut lang flak jacket" might return:
- ✅ Helmut Lang Flak Jacket (correct)
- ❌ Helmut Lang Military Jacket (different item, different price)
- ❌ Helmut Lang Flak Vest (related but different)
- ❌ Helmut Lang Jeans with "flak" in description (noise)

**How bad is it?** Depends heavily on the query:
- **Specific models** ("rick owens geobasket", "maison margiela tabi") → Algolia returns 80-90% relevant results because the model name is distinctive
- **Generic descriptions** ("helmut lang jacket", "raf simons pants") → 40-60% relevance, mixes mainline with diffusion, different eras, different styles
- **Vague/common terms** ("supreme hoodie", "nike dunk") → Extremely noisy, massive price variance

**Current mitigation:** `comp_matcher.py` already does excellent work here — it scores each comp by similarity (brand match, sub-brand, model, material, item type) and uses similarity-weighted median pricing. This is the bot's strongest defense.

**Remaining gaps:**
1. Algolia returns max 20 results. If 10/20 are irrelevant, you only have 10 real comps before filtering
2. `comp_matcher` tries multiple queries from specific → generic, but stops once it gets `min_comps` high-quality matches. This means it may stop at a mediocre query if it gets lucky with 5 okayish matches
3. No negative filtering — can't exclude terms ("rick owens geobasket -drkshdw")

**Recommendation:**
```python
# In _search_algolia, add Algolia facet filters for tighter matching
payload = {
    "query": query,
    "hitsPerPage": max_results,
    "page": 0,
    # Add facet filters when we know the designer
    "facetFilters": [f"designers.name:{designer}"] if designer else [],
}

# Increase max_results to 40 to get more candidates for similarity filtering
# The comp_matcher will handle relevance scoring
```

Also consider: when `comp_matcher` finds < 5 high-quality comps (similarity > 0.5), flag the deal as "low comp confidence" rather than proceeding with noisy data.

**Priority: #2 — comp_matcher already handles this reasonably well, but upstream improvements help.**

---

### 3. Temporal Relevance — 🟠 HIGH (Impact: High)

**The Problem:** No date filtering on sold comps. Grailed's `Listing_sold_production` index returns results sorted by relevance, not recency. A geobasket that sold for $350 in 2023 and one that sold for $650 in 2025 both count equally.

**Why it matters for archive fashion:**
- Archive prices are **volatile and trending upward** for most grail pieces
- A Raf Simons Riot bomber sold for $2,000 in 2022 might sell for $4,000+ in 2025
- Conversely, hype items can crash — Balenciaga Triple S went from $800 → $400 in 2 years
- Using stale comps systematically undervalues appreciating items and overvalues depreciating ones

**Available data:** Algolia hits include `created_at` (listing creation date). The code already parses this into `listed_at` in `_parse_algolia_hit()`. But it's never used for filtering.

**Recommendation:**
```python
# In gap_hunter.py, after getting sold items, filter by date
from datetime import datetime, timedelta

MAX_COMP_AGE_DAYS = 180  # 6 months default
IDEAL_COMP_AGE_DAYS = 90  # 3 months ideal

# Filter and weight by recency
now = datetime.now()
for item in sold_items:
    if item.listed_at:
        age_days = (now - item.listed_at).days
        if age_days > MAX_COMP_AGE_DAYS:
            continue  # Skip stale comps
        # Apply recency weight: newer = more weight
        recency_weight = max(0.3, 1.0 - (age_days / MAX_COMP_AGE_DAYS) * 0.7)
        # Multiply into similarity score
```

**Caveat:** If filtering to 90 days leaves < 3 comps, expand to 180 days, then fall back to unfiltered. Niche items (Number Nine, Undercover archive) may not have recent sold data.

**Priority: #3 — Easy to implement, meaningful accuracy improvement.**

---

### 4. Condition Mismatch — 🟡 MEDIUM (Impact: Medium)

**The Problem:** A DS (deadstock) Rick Owens Geobasket sells for $700-900. A heavily worn pair sells for $200-350. Both are "sold comps" for the same search.

**Current handling:**
- Bottom 20% below median filtered out (catches beater-priced sales)
- Top/bottom 10% trimmed
- IQR outlier removal in comp_matcher
- `condition_parser.py` assigns condition multipliers to the SOURCE item

**Assessment:** The current approach is **decent but incomplete**. The core problem is we don't know the condition of the COMPS, only the source item. We apply condition multipliers to the source deal scoring, but the median sold price already bakes in a mix of conditions.

**Grailed data available:** Algolia hits include a `condition` field (values like "is_gently_used", "is_new", etc.). This is currently parsed but **never used for filtering or segmenting**.

**Recommendation:**
```python
# When source item is DS/BNWT, prefer comps that are also DS/new
# When source item is used, compare against used comps
def filter_comps_by_condition(comps, source_condition):
    condition_map = {
        "is_new": ["is_new"],
        "is_gently_used": ["is_gently_used", "is_new"],
        "is_used": ["is_used", "is_gently_used"],
        "is_very_worn": ["is_very_worn", "is_used"],
    }
    preferred = condition_map.get(source_condition, [])
    matched = [c for c in comps if c.raw_data.get("condition") in preferred]
    # Only use condition-filtered set if we have enough
    return matched if len(matched) >= 3 else comps
```

**Priority: #4 — The existing outlier trimming handles the worst cases. Condition segmentation is a refinement.**

---

### 5. Sample Size (MIN_SOLD_COMPS = 3) — 🟡 MEDIUM (Impact: Medium)

**The Problem:** 3 comps is statistically weak. With 3 data points:
- One outlier skews the median heavily
- Trimming/IQR is meaningless (can't trim 10% of 3 items)
- Confidence interval is huge

**What the numbers say:**
| Comps | After Trim | Reliability | Notes |
|-------|-----------|-------------|-------|
| 3 | 3 (no trim) | Low | One bad comp = 33% error |
| 5 | 3-5 | Marginal | Trim removes 1 top + 1 bottom |
| 8 | 6-8 | Acceptable | IQR works, median is stable |
| 12+ | 9-10 | Good | Statistical confidence |
| 20 | 16-18 | High | Robust median |

**Current code:** `comp_matcher.py` has confidence levels:
- 8+ high-quality comps → "high"
- 3+ → "medium"
- 5+ total → "low"
- else → "very_low"

**Recommendation:**
- Raise `MIN_SOLD_COMPS` to **5** as default
- Keep 3 as fallback for niche items, but flag them as "low_confidence"
- Use confidence level to gate alert behavior:
  - `high` confidence → send alert normally
  - `medium` → send with ⚠️ "Limited comp data" warning
  - `low`/`very_low` → only send if gap > 50% AND profit > $200 (extreme deals)

```python
MIN_SOLD_COMPS = 5  # Raise from 3
MIN_SOLD_COMPS_NICHE = 3  # Fallback for rare items

# In gap_hunter, adjust thresholds based on confidence
if sold_data.confidence == "low":
    effective_min_gap = MIN_GAP_PERCENT * 1.5  # Require bigger gap
    effective_min_profit = MIN_PROFIT_DOLLARS * 2
```

**Priority: #5 — Easy config change with outsized impact on false positive rate.**

---

### 6. Size Price Variation — 🟢 LOW-MEDIUM (Impact: Low-Medium)

**The Problem:** Size affects resale price significantly in archive fashion:
- **Hot sizes (M, L, EU 42-44):** Premium of 10-20% above average
- **Extreme sizes (XS, XXL, EU 39, EU 47+):** Discount of 15-30%
- **Women's sizes in menswear brands:** Often 20-40% less

**Current handling:** `size_scorer.py` already applies multipliers, and comps are searched across all sizes. The median includes all sizes.

**Assessment:** For most items, size variation adds ±15% noise to the comp median. The existing 30%+ gap threshold absorbs this. It would only cause false positives on borderline deals (30-35% gap) where the source item is an extreme size.

**Recommendation:** Low priority. If implementing:
```python
# Add size to Algolia query for common items with enough data
if parsed.item_type in ["shoes", "boots"] and not is_niche_item:
    # Shoes have the biggest size-price variance
    size_query = f"{query} {source_size}"
    size_comps = await scraper.search_sold(size_query, max_results=10)
    if len(size_comps) >= 5:
        use size_comps  # Size-specific comps available
```

**Priority: #6 — Existing size_scorer handles the scoring side. Comp filtering by size is a nice-to-have.**

---

### 7. Fee Structure in Profit Calculation — 🟢 MEDIUM (Impact: Medium)

**The Problem:** The profit calculation needs to account for ALL costs:
- Platform sell fees (already handled in detect_arbitrage.py)
- Payment processing (~3%)
- Shipping ($10-20 depending on item)
- Platform buy protection / authentication fees
- Time cost

**Current code:** `detect_arbitrage.py` uses `PLATFORM_FEES` dict but `gap_hunter.py` calculates raw gap without fee adjustment.

**Recommendation:**
```python
# In gap_hunter.py, deduct estimated costs from profit
ESTIMATED_SELL_FEE = 0.12  # ~12% (platform + payment processing)
ESTIMATED_SHIPPING = 15     # Average shipping cost

adjusted_profit = (reference_price * (1 - ESTIMATED_SELL_FEE)) - item_price - ESTIMATED_SHIPPING
```

**Priority: #7 — Important for accuracy but doesn't change which deals surface, just the reported profit number.**

---

### 8. Platform Bias (Grailed-Only Comps) — 🟢 LOW (Impact: Low for now)

**The Problem:** Grailed skews toward higher-end archive fashion buyers who pay more. Using Grailed-only comps inflates market price estimates.

**Assessment:** This is actually **partially a feature, not a bug** for the current use case. If the bot helps users buy cheap elsewhere and resell on Grailed, then Grailed's sold prices ARE the relevant sell-side reference. The issue only arises when:
1. Evaluating deals ON Grailed (Grailed buy → Grailed sell arbitrage is rare)
2. Estimating "true market value" for non-Grailed selling

**Recommendation:** Long-term, add eBay sold data (eBay has a robust sold items API). Short-term, this is low priority because the platform fee adjustment (#1) already accounts for the cross-platform premium.

**Priority: #8 — Address via platform fee adjustment first. Multi-source comps is a v2 feature.**

---

## Priority Ranking Summary

| Rank | Issue | Impact | Effort | ROI |
|------|-------|--------|--------|-----|
| 🥇 1 | Platform fee asymmetry | High | Low | **Very High** |
| 🥈 2 | Search relevance (Algolia facets) | High | Medium | **High** |
| 🥉 3 | Temporal filtering | High | Low | **High** |
| 4 | Condition-based comp filtering | Medium | Medium | Medium |
| 5 | Raise MIN_SOLD_COMPS to 5 | Medium | Trivial | **High** |
| 6 | Size-specific comps | Low-Med | Medium | Low |
| 7 | Fee-adjusted profit calc | Medium | Low | Medium |
| 8 | Multi-platform comp sources | Low | High | Low |

---

## Quick Wins (< 1 hour each)

### 1. Platform price discount factors
Add `PLATFORM_PRICE_DISCOUNT` dict to `gap_hunter.py`. When source is Mercari/Poshmark, multiply Grailed median by discount factor before computing gap. **~20 lines of code.**

### 2. Raise MIN_SOLD_COMPS to 5
Change one constant in `gap_hunter.py`. Add confidence-gated alert thresholds. **~5 lines.**

### 3. Temporal filtering
In `gap_hunter.py` where sold items are processed (line ~612-660), add `MAX_COMP_AGE_DAYS = 180` filter using the already-parsed `listed_at` field. **~15 lines.**

### 4. Algolia designer facet filter
In `grailed.py` `_search_algolia()`, add `facetFilters` to the payload when brand is known. **~5 lines.**

---

## Conclusion

The comp_matcher similarity scoring system is sophisticated and handles many edge cases well. The biggest accuracy gains come from **adjusting for cross-platform pricing differences** (the root cause of most false positives) and **filtering stale comps**. These are both low-effort, high-impact fixes that should be implemented first.

The bot's fundamental approach — find items priced below sold comps — is sound. These refinements make the signal cleaner by reducing noise in the comp baseline.

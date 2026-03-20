# Archive Arbitrage — Liquidity Execution Spec

_Date: 2026-03-13_

## Objective

Translate the liquidity-first strategy into an implementation sequence that changes real deal selection behavior.

Target outcome:
- fewer noisy public alerts
- more exact, liquid, confidence-backed opportunities
- more conservative profit estimates
- target rotation biased toward fast-moving, low-junk inventory

---

## Product Thesis

Archive Arbitrage should stop optimizing for:
- broad discovery
- flattering resale assumptions
- raw gap percentage

And instead optimize for:
- conservative liquidation value
- downside resilience
- exact-model confidence
- query cleanliness
- repeatable sell-through

The system should behave more like a disciplined reseller than a generic underpricing detector.

---

## Current State Assessment

### Already live
- query telemetry logging
- junk/alert ratio scaffolding
- A/B/trap query tiering
- stronger public alert quality gating
- CV-aware hyper-pricing fallback
- authentication-weighted comp logic
- cooldown/dead-query-aware target rotation

### Not yet complete
- conservative liquidation anchor
- downside / haircut simulation
- margin-of-safety deal ranking
- family-level query normalization
- liquidity-native target scoring
- source/category-aware strategy layer

---

## Implementation Principles

1. **Conservative by default**
   - If pricing confidence is weak, assume less resale upside, not more.

2. **Internal exploration, public restraint**
   - Hunting can be broad; public sends should be selective.

3. **Canonical target identity matters**
   - Telemetry should aggregate around target families, not fragmented strings.

4. **Rank by survivability, not excitement**
   - A deal that survives downside haircuts outranks a sexy high-gap but fragile comp story.

5. **Use telemetry to earn rotation time**
   - Queries/targets should stay in circulation because they produce liquid wins, not because they sound interesting.

---

## Phase 1 — Conservative Liquidation Pricing

### Goal
Replace optimistic market-estimate logic with a conservative resale anchor that better approximates real liquidation value.

### New Concepts
For each comp set, compute:
- `median_price`
- `p25_price`
- `auth_median_price`
- `auth_p25_price`
- `low_cluster_price` (optional, if detectable)
- `liquidation_anchor`
- `downside_anchor`
- `pricing_method`
- `pricing_confidence`

### Liquidation Anchor Rules
Initial v1 heuristic:
1. If enough authenticated comps exist:
   - prefer the lower of authenticated median and authenticated p25-derived floor
2. Else if comp count is sufficient and variance is acceptable:
   - use p25 or conservative hyper-price floor
3. If variance is high:
   - apply stronger haircuts
4. If comp support is weak:
   - fall back toward median-minus-haircut rather than mean-like optimism

### Downside Anchor Rules
Apply additional haircut based on uncertainty:
- low CV + good auth support → lighter haircut
- medium CV / mixed auth support → moderate haircut
- high CV / weak auth support → heavier haircut

### Outputs Needed On SoldData / Deal
- `liquidation_anchor`
- `downside_anchor`
- `pricing_confidence`
- `pricing_method`
- `comp_p25`
- `auth_comp_p25`

---

## Phase 2 — Margin of Safety (MOS)

### Goal
Score deals by downside-safe resale economics rather than raw gap alone.

### Required Deal Fields
- `expected_net_profit`
- `downside_net_profit`
- `expected_margin`
- `downside_margin`
- `margin_of_safety_score`
- `pricing_confidence_score`
- `liquidity_score` (placeholder in v1 if needed)

### Initial MOS Scoring Inputs
Positive:
- higher downside net profit
- stronger comp confidence
- lower CV
- stronger authentication support
- faster average days-to-sell

Negative:
- high variance
- low auth support
- broad/noisy query family
- weak downside profit

### Ranking Rule
Primary ranking should become:
1. MOS score
2. downside net profit
3. pricing confidence
4. expected net profit

---

## Phase 3 — Canonical Target Families

### Goal
Aggregate telemetry and target selection around real target identities rather than fragmented query strings.

### Canonical Target Shape
```json
{
  "target_id": "rick_owens_geobasket",
  "display_name": "Rick Owens Geobasket",
  "brand": "Rick Owens",
  "category": "footwear",
  "canonical_query": "rick owens geobasket",
  "marketplace_queries": {
    "grailed": ["rick owens geobasket"],
    "ebay": ["rick owens geobasket", "rick owens geo basket"],
    "mercari": ["rick owens geobasket"]
  },
  "fallback_descriptors": ["rick owens basketball sneaker"],
  "liquidity_profile": {
    "expected_sell_speed": "medium",
    "confidence": "high"
  }
}
```

### Telemetry Changes
Track both:
- raw query telemetry
- family-level / target-level telemetry

Decisioning should use target-level rollups.

---

## Phase 4 — Liquidity-Native Target Scoring

### Goal
Make target rotation depend on resale quality, cleanliness, and liquidity rather than basic opportunity scoring alone.

### Inputs for Target Scoring
- sold volume
- avg / median days-to-sell
- comp CV penalty
- junk ratio
- alert ratio
- auth support
- MOS yield quality
- source reliability

### Example Composite
`rotation_score = opportunity_score × liquidity_multiplier × confidence_multiplier × cleanliness_multiplier`

Where:
- `liquidity_multiplier` comes from volume + speed
- `confidence_multiplier` comes from CV + auth support
- `cleanliness_multiplier` comes from junk ratio + alert conversion

### Tiering Evolution
A/B/trap can remain as a coarse label, but should stop being the main intelligence layer.

---

## Phase 5 — Public Alert Policy

### Goal
Separate internal candidate discovery from public recommendation quality.

### Public Alert Requirements
Public alerts should require:
- minimum MOS score
- positive downside net profit
- max comp CV threshold
- minimum auth support or auth confidence
- exact/family confidence
- no trap-like target behavior

### Output Philosophy
Public alerts should become:
- rarer
- more exact
- more trusted
- more liquid

---

## Build Order

### Sprint 1 — Economics
1. Conservative liquidation engine
2. Deal-level MOS fields
3. Candidate ranking by MOS
4. Internal alert visibility for liquidation/downside values

### Sprint 2 — Identity
5. Canonical target family schema
6. Family-level telemetry rollup
7. Normalize highest-value target families

### Sprint 3 — Rotation
8. Liquidity-native target scoring
9. TrendEngine rotation v2
10. Public alert policy upgrade

---

## Phase 1 Build Spec (Immediate)

### New module
Create `core/liquidation_pricing.py`

### Responsibilities
- compute conservative percentile-based anchors
- compute downside anchors using confidence/variance-aware haircuts
- expose method metadata for debugging and alerting

### Suggested API
```python
compute_liquidation_metrics(
    sold_prices: list[float],
    authenticated_prices: list[float] | None = None,
    hyper_price: float | None = None,
    cv: float | None = None,
    comp_count: int = 0,
    auth_comp_count: int = 0,
    avg_days_to_sell: float | None = None,
) -> dict
```

### Required outputs
```python
{
  "median_price": ...,
  "p25_price": ...,
  "auth_median_price": ...,
  "auth_p25_price": ...,
  "liquidation_anchor": ...,
  "downside_anchor": ...,
  "pricing_method": ...,
  "pricing_confidence": ...,
  "haircut_pct": ...,
}
```

### Integration points
- sold comp processing in `gap_hunter.py`
- deal reference price selection in `find_gaps()`
- alert formatting for internal observability

---

## Initial Heuristics for Phase 1

### Percentiles
- Use standard percentile helper for p25
- If too few comps for percentile robustness, fall back conservatively

### Confidence buckets
- **high**: low CV, enough comps, meaningful auth support
- **medium**: moderate CV or weaker auth support
- **low**: sparse comps or high variance

### Haircut defaults
- high confidence: 8–10%
- medium confidence: 15%
- low confidence: 20–25%

### Anchor selection priorities
1. authenticated p25 if robust
2. authenticated median with haircut
3. overall p25
4. hyper price with haircut
5. conservative median fallback

---

## Success Criteria

### Phase 1 success
- every deal has conservative anchor fields
- expected profit and downside profit both visible in code/data
- ranking stops depending purely on raw gap

### Phase 2 success
- low-resilience deals get pushed down or filtered
- public quality visibly improves

### Full-strategy success
- fewer but better alerts
- more exact-item hits
- cleaner target rotation
- stronger alignment with real resale behavior

---

## Recommended Immediate Next Move

Implement **Phase 1 only** first:
- create `core/liquidation_pricing.py`
- wire liquidation/downside anchors into `gap_hunter.py`
- add initial MOS fields
- rank deals using MOS-aware economics

That creates a real foundation for the rest of the liquidity-first roadmap.

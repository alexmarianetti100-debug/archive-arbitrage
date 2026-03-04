# Archive Arbitrage — Backlog

This backlog is derived from the deep-dive summary and the 12-week improvement plan. It’s organized by epics, with prioritized user stories, acceptance criteria, and rough sizing.

Conventions:
- **Priority**: P0 (must), P1 (should), P2 (nice)
- **Size**: S / M / L (rough effort)
- **DoD** (Definition of Done): implemented + documented + basic test / manual verification steps included

---

## Epic A — Multi-source Sold Data + Price Consensus (Phase 3)

### A1 — Define sold-data contract + normalization rules
- Priority: P0 | Size: S
- Story: As the pricing engine, I need a normalized “sold comp” record across platforms so I can compute market price consistently.
- Acceptance criteria:
  - A `SoldComp` schema exists (fields: platform, item_id/url, sold_price, currency, sold_at, title, brand/model fingerprint (optional), condition, size, confidence).
  - Currency normalization rules documented (FX source + caching, acceptable staleness).
  - Platform-specific quirks documented (fees included/excluded, shipping handling).
  - Stored in docs (`docs/sold-data-contract.md`) or similar.

### A2 — Implement Poshmark sold comps ingestion (MVP)
- Priority: P0 | Size: M
- Story: As the pricer, I want Poshmark sold comps for a query so I can reduce dependence on Grailed and detect spreads.
- Acceptance criteria:
  - A function/module returns recent sold comps for a query (with throttling and retry).
  - Data saved locally (SQLite table or JSON cache) with TTL.
  - Basic quality filters: min comps threshold, outlier trimming, stale comp filtering.

### A3 — Implement eBay sold comps ingestion (MVP)
- Priority: P1 (P0 if keys available) | Size: M
- Story: As the pricer, I want eBay sold comps (completed/sold) to anchor market price using high-volume data.
- Acceptance criteria:
  - Works with production keys OR a clearly documented fallback path.
  - Normalized comps stored and queryable.
  - Rate limiting and error handling in place.

### A4 — Price consensus module (weighted fusion)
- Priority: P0 | Size: M
- Story: As a user, I want the app to compute a “consensus market price” across sold sources with transparent weighting.
- Acceptance criteria:
  - Consensus price computed from Grailed + Poshmark (+ eBay when available).
  - Weighting configurable via `.env`.
  - Output includes provenance: which sources were used, counts, median/avg, spread.

### A5 — Pricing provenance logging
- Priority: P0 | Size: S
- Story: As a developer/operator, I need to see *why* the system priced an item a certain way to debug and trust it.
- Acceptance criteria:
  - Each priced item stores a structured provenance blob (sources used, comp counts, season multiplier, demand score, filters triggered).
  - Viewable via API or CLI output.

---

## Epic B — Product Catalog Expansion + Days-to-Sell + Risk/Confidence (Phase 2 completion)

### B1 — Expand product catalog generation pipeline
- Priority: P0 | Size: M
- Story: As the deal engine, I want broader canonical product coverage so more listings can be exact-matched.
- Acceptance criteria:
  - Catalog build can be re-run idempotently.
  - Target: expand to 250+ canonical products (initial milestone) from sold comps.
  - Clustering quality measured (manual spot-check doc + error modes).

### B2 — Implement days-to-sell estimation and integrate into grading
- Priority: P0 | Size: M
- Story: As a buyer/reseller, I want to know expected liquidity (days-to-sell) so I can prefer faster flips.
- Acceptance criteria:
  - Days-to-sell computed per product (or comp cluster) using sold history.
  - Deal grade logic incorporates days-to-sell and confidence bands.
  - CLI `pipeline.py deals` prints it consistently.

### B3 — Confidence bands and low-risk gating for alerts
- Priority: P0 | Size: S
- Story: As an operator, I want alerts to focus on low-risk items to reduce time wasted on false positives.
- Acceptance criteria:
  - A-grade alerts require: high velocity AND tight price band AND sufficient comp count.
  - Configurable thresholds in `.env`.

---

## Epic C — Cross-Platform Arbitrage Verifier (Phase 4)

### C1 — Net-profit calculator module (fees + shipping)
- Priority: P0 | Size: S
- Story: As the arbitrage detector, I need consistent fee + shipping handling to compute true net profit.
- Acceptance criteria:
  - Central fee calculator with platform fee schedules.
  - Unit-tested with example values.

### C2 — Minimal arbitrage verifier (fingerprint → prices → decision)
- Priority: P0 | Size: M
- Story: As a user, I want “verified” cross-platform arbitrage opportunities with confidence and provenance.
- Acceptance criteria:
  - Given a fingerprint/canonical product, fetch current active listings on cheaper platform(s) and compare to sold consensus.
  - Outputs: expected sell price, fees, net profit, confidence score.
  - Guardrails: min net profit, min comp confidence, rep/auth risk gate.

### C3 — Image similarity matching (optional MVP)
- Priority: P2 | Size: L
- Story: As the arbitrage detector, I want image similarity matching to find the same item cross-posted with different titles.
- Acceptance criteria:
  - Uses perceptual hashing or embeddings.
  - Produces matches with explainable thresholds.

---

## Epic D — Real-time Monitor + Gap Hunter Hardening

### D1 — Make monitor + gap hunter share the same core decision pipeline
- Priority: P1 | Size: M
- Story: As a developer, I want one canonical scoring/decision path so behavior is consistent across batch and real-time modes.
- Acceptance criteria:
  - Shared module for: desirability → authenticity → pricing → decision.
  - Reduced duplicated logic.

### D2 — Reduce false positives from low-trust sellers / poor query matches
- Priority: P0 | Size: S
- Story: As a user, I want fewer junk alerts and fewer irrelevant matches.
- Acceptance criteria:
  - Enforced brand/qualifier matching in off-platform results.
  - Seller trust thresholds documented and configurable.

---

## Epic E — Frontend + UX (Phase 5)

### E1 — Add “Guaranteed only / Low risk” filters
- Priority: P1 | Size: S
- Story: As a user, I want a single toggle that shows only high-velocity, high-confidence deals.
- Acceptance criteria:
  - Filter exists in React UI.
  - Backed by API query params.

### E2 — Product detail page shows sold history + velocity + confidence
- Priority: P1 | Size: M
- Story: As a user, I want to see why the product is liquid and what it sells for historically.
- Acceptance criteria:
  - Price chart + basic stats.
  - Shows comp count and time window.

---

## Epic F — Testing, Reliability, Ops

### F1 — Minimal regression test harness for core flows
- Priority: P0 | Size: S
- Story: As a developer, I want fast checks that scraping/pricing/grading didn’t break.
- Acceptance criteria:
  - At least smoke tests for pricing + grading modules.
  - A reproducible “offline” fixture-based test for the pricer.

### F2 — Secrets hygiene and environment validation
- Priority: P1 | Size: S
- Story: As an operator, I want startup validation that required env vars are present and safe.
- Acceptance criteria:
  - `python pipeline.py doctor` (or equivalent) prints missing keys and exits non-zero.

---

## Suggested execution order (first 4 weeks)
1. A1, A4, A5 (contract + consensus + provenance)
2. B2, B3 (days-to-sell + low-risk gating)
3. A2 (Poshmark sold MVP) then A3 (eBay sold MVP if keys)
4. C1, C2 (arbitrage verifier)
5. F1 (smoke tests) to stabilize

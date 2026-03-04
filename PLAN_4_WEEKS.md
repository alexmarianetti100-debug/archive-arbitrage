# Archive Arbitrage — 4-Week Plan (Execution Plan)

This is a focused 4-week plan derived from the backlog. It targets the highest leverage items: multi-source sold data, completing Phase 2 (days-to-sell + confidence gating), provenance, and a minimal arbitrage verifier.

Assumptions
- You want incremental wins while keeping the existing pipeline stable.
- eBay production keys may be blockers; plan includes a parallel path that still delivers value without them.

---

## Week 1 — Specs + Provenance + Consensus Skeleton

### Goals
- Lock the data contract and make pricing decisions explainable.
- Implement the scaffolding for multi-source pricing even before all sources exist.

### Deliverables
- `docs/sold-data-contract.md` (or similar) describing normalized sold comps.
- Price provenance logging (persisted per item or per pricing run).
- Consensus price module (works with Grailed-only initially, but supports multiple inputs).

### Tasks
- A1: Define `SoldComp` normalized schema + normalization rules.
- A4 (partial): Implement consensus aggregator API:
  - Inputs: list of sold comps grouped by platform
  - Output: consensus_price, confidence, per-source stats, spread
- A5: Add provenance blob:
  - comps sources used, comp counts
  - filters applied (stale/outlier)
  - season multiplier, demand level
  - final recommended_price + margin math
- F1 (partial): Add 1–2 fixture-based tests for consensus and provenance outputs.

### Acceptance criteria / “done”
- A priced item can print a one-screen breakdown of *why* it was priced as it was.

---

## Week 2 — Poshmark Sold MVP + Days-to-Sell Integration

### Goals
- First real multi-source input (Poshmark sold).
- Liquidity signal (days-to-sell) is computed and used in grading.

### Deliverables
- Poshmark sold comps retrieval working for a subset of queries/brands.
- Days-to-sell estimation wired into qualification and deal grading.
- Low-risk gating for alerts (A/B) based on comp confidence + velocity + spread.

### Tasks
- A2: Build `poshmark_sold.py` (or equivalent) + caching.
- B2: Days-to-sell estimation:
  - per product / per comp cluster
  - stored in DB and displayed in `pipeline.py deals`
- B3: Alert gating:
  - A-grade requires high velocity + min comp count + tight band
  - config via `.env`
- F1: Add smoke tests for grading decisions with fixtures.

### Acceptance criteria / “done”
- Running qualification updates days-to-sell and reduces noisy alerts.

---

## Week 3 — eBay Sold (if possible) + Arbitrage Verifier MVP

### Goals
- If eBay keys are available: add eBay sold comps.
- Regardless: ship the arbitrage verifier using whatever sold sources exist.

### Deliverables
- Arbitrage verifier that outputs a ranked list of opportunities with net profit after fees.
- Optional: eBay sold comps integrated into consensus.

### Tasks
- A3: eBay sold comps integration (conditional path):
  - If keys present: integrate via API.
  - If keys not present: stub adapter + documented “ready-to-enable” path.
- C1: Central fee calculator module.
- C2: Minimal arbitrage verifier:
  - input: canonical product / fingerprint
  - output: net profit, confidence, source breakdown
- Add CLI entry point (e.g., `python pipeline.py arbitrage --limit 50`).

### Acceptance criteria / “done”
- You can run one command and get a ranked set of arbitrage candidates with clear justification.

---

## Week 4 — Hardening + UX Surface + Reliability

### Goals
- Reduce false positives further and expose the new signals in UI/UX.
- Ensure the core loop is stable with minimal regression coverage.

### Deliverables
- “Guaranteed only / low risk” toggle in frontend.
- Product detail surfaces velocity + confidence + sold ranges.
- Basic `doctor`/env validation and expanded smoke tests.

### Tasks
- E1: Add low-risk toggle to React UI + API params.
- E2: Product detail page shows:
  - comp count, time window, median/avg, band
  - velocity + days-to-sell
- D2: Tighten query matching and seller trust thresholds where needed (configurable).
- F2: Add environment validation command (or startup checks).
- F1: Expand smoke tests for consensus + grading + fee calc.

### Acceptance criteria / “done”
- Users can filter to high-confidence deals; operationally, fewer junk alerts; basic regression harness exists.

---

## Risks / Dependencies
- eBay keys: may block A3 (but does not block consensus scaffolding, Poshmark sold, days-to-sell, or arbitrage verifier MVP).
- Platform scraping stability: Poshmark/eBay HTML may require throttling, proxies, or browser automation.
- Data correctness: must log provenance so you can debug quickly when a platform changes markup.

## Metrics to track (start now)
- Deals sent per day
- % deals that are A-grade vs B/C
- Median comp count per priced item
- False positive rate (manual sample) for authenticity and relevance
- Average expected profit and margin of surfaced deals

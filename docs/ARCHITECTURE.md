# Archive Arbitrage — Architecture

## High-Level Flow

The canonical runtime is `gap_hunter.py`.

At a high level, one cycle looks like this:

1. **Select targets**
   - `trend_engine.py` produces a cooldown-aware, opportunity-weighted target set
   - if needed, static target lists are used as fallback

2. **Fetch sold comps**
   - sold pricing is gathered and normalized
   - hyper-pricing logic can refine reference pricing using condition / size / time decay

3. **Search active listings**
   - active items are fetched from multiple marketplaces
   - item-level filters reject bad matches, replica-like pricing, implausible gaps, etc.

4. **Validate deals**
   - deal quality, authenticity, desirability, and validation checks run before alerting

5. **Send alerts**
   - Telegram
   - Discord
   - Whop

6. **Persist state**
   - seen IDs
   - sold cache
   - image hashes
   - seller blocklist
   - query performance

7. **Optional Japan sweep**
   - Japan arbitrage scan runs after the main target loop unless skipped with `--skip-japan`

---

## Main Runtime Modules

### `gap_hunter.py`
The main entrypoint.

Responsibilities:
- dependency/config validation on startup
- cycle orchestration
- sold-comp lookup
- active listing search
- deal filtering
- state persistence
- alert dispatch
- Japan integration trigger

### `trend_engine.py`
Selects what the service hunts each cycle.

Current model includes:
- global opportunity-score ranking
- cooldown-aware selection
- long-tail rotation
- dead-query exclusion
- fallback target behavior if catalog/velocity data is unavailable

### `core/`
Holds most business logic, including:
- alerting
- pricing
- authenticity / desirability / validation
- data management
- seller management
- Japan integration
- hyper-pricing helpers

### `scrapers/`
Marketplace integrations for sold and active listing retrieval.

---

## Runtime Data

State and local artifacts live under `data/`.

Important categories include:
- DB files
- sold cache
- seen-id state
- image hash dedupe state
- seller blocklist state
- trend / query-performance history
- Japan opportunity logs

---

## Primary vs Legacy Paths

### Canonical path
- `gap_hunter.py`

### Still present but not canonical
- `pipeline.py`
- older unified/integrated runner experiments

Those older paths may still import successfully, but they should not be mistaken for the main service.

---

## Operational Notes

### Bounded smoke test
Use:

```bash
source venv/bin/activate
python gap_hunter.py --once --max-targets 1 --skip-japan
```

### Full behavior
Without `--skip-japan`, the cycle can continue into the Japan scan after the main target loop finishes.

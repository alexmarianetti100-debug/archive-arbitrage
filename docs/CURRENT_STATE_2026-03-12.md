# Archive Arbitrage — Current State Audit (2026-03-12)

## Canonical Runtime

The project's real runtime is the local virtualenv:

```bash
source venv/bin/activate
```

Verified inside venv:
- Python: `3.11.0`
- Main runner imports cleanly
- `python core/dependencies.py --critical-only` passes
- `python gap_hunter.py --help` works

Outside the venv, the project appears broken due to missing dependencies. This is expected and should be documented clearly.

---

## What Is Actually Working

### Main runtime path
- `gap_hunter.py` is the real entrypoint.
- It imports and starts correctly inside the venv.
- The main loop is wired to:
  - dynamic target selection via `trend_engine.py`
  - hyper-pricing / sold comp logic
  - multi-platform active listing search
  - deal validation
  - Telegram / Discord / Whop alerting
  - Japan arbitrage scan

### Trend engine
- `TrendEngine().get_cycle_targets()` returns live targets successfully.
- Current rotation model includes:
  - global opp-score ranking
  - cooldown-aware query selection
  - long-tail pool injection
  - dead-query exclusion

### Integrations verified by import/startup
- `gap_hunter`
- `trend_engine`
- `core.whop_alerts`
- `core.discord_alerts`
- `telegram_bot`
- `core.japan_integration`

---

## Live Runtime Findings

### Smoke test result
Command run:

```bash
source venv/bin/activate
python gap_hunter.py --once --max-targets 1
```

Observed:
- startup succeeds
- dependency check succeeds
- target rotation succeeds
- sold-comp query executes
- Japan arbitrage scan starts successfully
- Yahoo Auctions JP and Mercari direct API both return live results

### Important operational issue found
`--max-targets 1` limits the main archive/luxury target loop, **but does not limit the Japan sweep**.

Even with `--max-targets 1`, the process proceeded into a full Japan scan with:
- `106` Japan targets
- Yahoo Auctions requests
- Mercari direct API requests
- long runtime after the main loop effectively finished

This makes smoke testing much slower and riskier than it should be.

**Recommendation:** add a CLI flag or config to disable / limit Japan scans during smoke tests.

---

## Repo Weak Points

### 1. Root directory sprawl
The repo root currently contains too many top-level files:
- many debug scripts
- many one-off test scripts
- many verification scripts
- many stale status/plan/summary markdown files
- multiple alternate runners / integration attempts

This makes it hard to tell what is production-critical versus experimental.

### 2. Documentation drift
Documentation does not consistently match runtime reality.
Examples:
- some docs imply older Japan limitations that no longer match current direct-API behavior
- some docs read as if the whole system is production-ready in a cleaner sense than the repo/environment currently support

### 3. Too many test-like entrypoints
At root level there are many files matching patterns like:
- `debug_*.py` (17)
- `test_*.py` (31)
- `verify_*.py` (4)

Some may be useful, but the current organization obscures which are:
- real tests
- manual probes
- one-off experiments
- obsolete leftovers

### 4. Cache/state hygiene
Current pricing cache stats show:
- 32 cache entries
- 30 expired entries
- 0% hit rate

This suggests current cache maintenance / observability needs attention.

### 5. Repo is very dirty
There are many modified tracked files plus many untracked files. Cleanup should preserve working paths while reducing ambiguity.

---

## Immediate Cleanup Priorities

### Priority A — Stabilize smoke testing
1. Add a `--skip-japan` or `--japan-max-targets` flag to `gap_hunter.py`
2. Make smoke tests fast and bounded
3. Preserve current default production behavior unless intentionally changed

### Priority B — Classify the repo
Create three buckets:
1. **Production-critical**
2. **Support / operations**
3. **Experimental / archive**

Targets for likely review:
- alternate runner files
- root-level debug scripts
- root-level one-off verification scripts
- markdown status/plan dump files

### Priority C — Restructure without breaking runtime
Likely moves:
- `debug_*.py` → `scripts/debug/`
- manual verify files → `scripts/verify/`
- stale markdowns → `docs/archive/`

### Priority D — Documentation reset
Create a small, trustworthy doc set:
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/OPERATIONS.md`
- `docs/STATUS.md`

---

## Proposed Next Steps

1. Implement bounded smoke-test controls in `gap_hunter.py`
2. Build a keep/archive/delete inventory for root-level scripts and docs
3. Move non-critical clutter out of root
4. Rewrite core docs around actual runtime behavior
5. Run smoke test again after cleanup

---

## Baseline Conclusion

The project is **not fundamentally broken**.

It has a working canonical runtime inside `venv`, and the main service starts successfully there.

The real problems are:
- repo sprawl
- stale/inconsistent documentation
- poor separation between production paths and experiments
- unbounded smoke-test behavior due to the Japan sweep

So cleanup should proceed from a known-good baseline, not from panic.

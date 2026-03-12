# Archive Arbitrage — Status

_Last updated: 2026-03-12_

## Canonical Runtime

Use the local virtualenv:

```bash
source venv/bin/activate
```

Run the main service with:

```bash
python gap_hunter.py
```

Verified on 2026-03-12:
- the venv is the intended runtime
- critical dependency check passes inside the venv
- `gap_hunter.py` imports and starts successfully inside the venv
- the main runner works for bounded smoke tests with `--skip-japan`

---

## What Is Primary vs Secondary

### Primary
- `gap_hunter.py` — main runner
- `trend_engine.py` — dynamic target rotation
- `core/` + `scrapers/` — actual runtime modules

### Secondary / legacy
- `pipeline.py` — older pipeline path, still present
- assorted unified runner experiments — not the canonical runtime

---

## Working / Verified

### Verified directly in the venv
- dependency validation
- `gap_hunter.py --help`
- imports for:
  - `gap_hunter`
  - `trend_engine`
  - `core.whop_alerts`
  - `core.discord_alerts`
  - `telegram_bot`
  - `core.japan_integration`

### Verified by smoke test
- `python gap_hunter.py --once --max-targets 1 --skip-japan`
  - startup succeeds
  - target rotation runs
  - sold-comp query executes
  - cycle exits cleanly

### Verified by live run behavior
- Japan scan starts successfully when enabled
- Yahoo Auctions JP returns live results
- Mercari direct API returns live results

---

## Partially Working / Needs Attention

### Repo structure
The working runtime exists, but the repo still has cleanup debt:
- root-level `test_*.py` probe scripts still need reorganization
- docs outside the new core doc set are still uneven in quality
- several alternate runner files still exist and need explicit keep/archive decisions

### Cache hygiene
Recent cache stats showed:
- 32 entries
- 30 expired entries
- 0% hit rate

This is not a blocker, but it suggests cache maintenance and observability need follow-up.

---

## Known Current Realities

### Smoke testing
Use this command for a quick bounded check:

```bash
source venv/bin/activate
python gap_hunter.py --once --max-targets 1 --skip-japan
```

### Japan behavior
Without `--skip-japan`, even a small one-cycle run can become long because the Japan scan adds a large target sweep after the main target loop.

---

## In Progress Cleanup

Completed on 2026-03-12:
- documented current runtime baseline
- added `--skip-japan` for bounded smoke tests
- moved debug scripts to `scripts/debug/`
- moved verification scripts to `scripts/verify/`
- archived historical implementation docs into `docs/archive/`

Next likely cleanup items:
- move root-level `test_*.py` live probes out of root
- review alternate / unified runners
- continue tightening docs around the actual runtime path

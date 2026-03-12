# Archive Arbitrage

Archive Arbitrage is a fashion resale arbitrage tool for finding underpriced archive and luxury items, estimating real resale value from sold comps, and sending deal alerts.

## Canonical Runtime

The real runtime for this project is the local virtualenv:

```bash
source venv/bin/activate
```

Inside that venv, the main service is:

```bash
python gap_hunter.py
```

Outside the venv, the project may appear broken because required dependencies are not available globally. That is expected.

---

## What To Run

### Main service
```bash
source venv/bin/activate
python gap_hunter.py
```

### Fast smoke test
This is the safest way to verify the runner without triggering the full Japan sweep:

```bash
source venv/bin/activate
python gap_hunter.py --once --max-targets 1 --skip-japan
```

### One cycle with Japan enabled
```bash
source venv/bin/activate
python gap_hunter.py --once --max-targets 3
```

### Legacy pipeline
Still present, but not the primary runtime:

```bash
source venv/bin/activate
python pipeline.py run
```

---

## Current Project Shape

### Primary path
- `gap_hunter.py` — canonical runtime
- `trend_engine.py` — dynamic target selection / rotation
- `core/` — pricing, validation, alerting, Japan integration, state helpers
- `scrapers/` — marketplace scrapers
- `data/` — local state, caches, DB files, trend history

### Secondary / legacy
- `pipeline.py` — older pipeline path, still real but no longer the center of gravity
- `api/` — API-related work
- `frontend-react/` — frontend work
- `archive/legacy-runners/` — archived experimental/unified runner attempts

### Support tooling
- `scripts/debug/` — debug helpers
- `scripts/verify/` — manual verification / one-off operational checks
- `tests/` — actual pytest-style test suite
- `docs/archive/` — historical plans, status docs, and implementation notes

---

## Setup

### 1. Activate the venv
```bash
source venv/bin/activate
```

### 2. Verify dependencies
```bash
python core/dependencies.py --critical-only
```

### 3. Validate config
```bash
python gap_hunter.py --help-config
```

### 4. Install / update deps if needed
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

---

## Core Commands

### Main runner
```bash
python gap_hunter.py
```

### Useful flags
```bash
python gap_hunter.py --once
python gap_hunter.py --brand "rick owens"
python gap_hunter.py --query "rick owens dunks,raf simons bomber"
python gap_hunter.py --max-targets 10
python gap_hunter.py --skip-japan
```

### Cache / data helpers
```bash
python gap_hunter.py --cache-stats
python gap_hunter.py --cache-flush
python gap_hunter.py --cache-clear
python gap_hunter.py --data-metrics
python gap_hunter.py --data-prune
```

### Blocklist helpers
```bash
python gap_hunter.py --blocklist-list
python gap_hunter.py --blocklist-block SELLER_NAME
python gap_hunter.py --blocklist-unblock SELLER_NAME
python gap_hunter.py --blocklist-stats
```

---

## Integrations

Wired into the current `gap_hunter.py` path:
- Telegram alerts
- Discord alerts
- Whop alerts
- Japan arbitrage scan

For current reality, see:
- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/OPERATIONS.md`

---

## Notes

- The repo has been through several generations. Not every top-level file represents the current path.
- `gap_hunter.py` is the current source of truth for the live arbitrage runner.
- Historical implementation docs have been moved into `docs/archive/` to reduce noise.

# Archive Arbitrage — Root Cleanup Plan (2026-03-12)

## Purpose

This document classifies the current root-level files into:
- **KEEP at root**
- **MOVE out of root**
- **ARCHIVE / de-emphasize**
- **DELETE later if confirmed redundant**

The goal is to preserve the working `gap_hunter.py` path while making the repo readable again.

---

## 1. KEEP AT ROOT

These appear to be legitimate top-level project files or active operational entrypoints.

### Core runtime / product
- `gap_hunter.py` — canonical runtime
- `pipeline.py` — legacy but still real
- `trend_engine.py`
- `telegram_bot.py`
- `models.py`
- `auction_snipe.py`
- `detect_arbitrage.py`
- `realtime_monitor.py`
- `scan_for_replicas.py`
- `stripe_billing.py`

### Packaging / setup / config
- `requirements.txt`
- `requirements-dev.txt`
- `setup.py`
- `pytest.ini`
- `alembic.ini`
- `vercel.json`
- `.env.example`
- `.gitignore`
- `README.md`
- `validate_setup.sh`
- `run.sh`
- `stop.sh`

### Potentially useful top-level operational tools
Keep for now, revisit after docs cleanup:
- `health_check.py`
- `status_dashboard.py`
- `backtest_pricing.py`

---

## 2. KEEP, BUT MOVE OUT OF ROOT

These are probably useful, but they do not belong in the root directory.

### Debug scripts → `scripts/debug/`
- `debug_cycles.py`
- `debug_detailed.py`
- `debug_discord.py`
- `debug_ebay.py`
- `debug_ebay_detailed.py`
- `debug_ebay_scraper.py`
- `debug_fetch.py`
- `debug_gap_hunter.py`
- `debug_grailed_sold.py`
- `debug_parse_items.py`
- `debug_pipeline.py`
- `debug_sold_data.py`
- `debug_targets.py`
- `debug_vinted.py`
- `debug_vinted2.py`
- `debug_vinted3.py`
- `debug_whop.py`

### Manual verification scripts → `scripts/verify/`
- `verify_fix.py`
- `verify_fixes.py`
- `verify_phase2.py`
- `verify_whop.py`
- `final_verification.py`
- `final_integration_test.py`
- `simple_test.py`
- `pipe_health.py`
- `health_check_all.py`

### Root-level ad hoc test runners → probably `scripts/manual-tests/`
These are not pytest-style tests under `tests/`, and they clutter the root.

- `test_alerts.py`
- `test_all_scrapers.py`
- `test_american_markets.py`
- `test_archive_fix.py`
- `test_autoblock.py`
- `test_config.py`
- `test_db_pool.py`
- `test_depop.py`
- `test_discord_alert.py`
- `test_ebay_phase3_3.py`
- `test_ebay_trace.py`
- `test_full_cycle.py`
- `test_hyper_integration.py`
- `test_japan_fix.py`
- `test_live_cycle.py`
- `test_monitoring.py`
- `test_phase2.py`
- `test_phase3.py`
- `test_pricing_fix.py`
- `test_process_deal.py`
- `test_profitable.py`
- `test_quick.py`
- `test_regular_deals.py`
- `test_system.py`
- `test_vinted_cookie.py`
- `test_vinted_fix.py`
- `test_vinted_fixed.py`
- `test_whop.py`
- `test_whop_functionality.py`
- `test_whop_integration.py`
- `test_whop_integration_now.py`

**Important:** these should be moved, not deleted blindly. Some may still be useful as manual live probes.

---

## 3. ARCHIVE / DE-EMPHASIZE

These look like historical planning / progress / implementation dump docs that should not dominate root.
Move to `docs/archive/` unless one is still actively maintained.

- `FIXES_COMPLETE.md`
- `FIXES_SUMMARY.md`
- `FIX_PLAN.md`
- `HYPER_PRICING_COMPLETE.md`
- `HYPER_PRICING_IMPLEMENTED.md`
- `HYPER_PRICING_PLAN.md`
- `ISSUES_FIXED.md`
- `JAPAN_ARBITRAGE_COMPLETE.md`
- `JAPAN_ARBITRAGE_ISSUES.md`
- `JAPAN_ARBITRAGE_STATUS.md`
- `JAPAN_ARBITRAGE_UPDATE.md`
- `PLAN_4_WEEKS.md`
- `detailed_unified_plan.md`
- `gap_hunter_final_integration.md`
- `gap_hunter_integration_plan.md`
- `gap_hunter_whop_integration.md`
- `unified_archive_arbitrage_plan.md`
- `troubleshooting_notes.md`

Potentially keep visible, but likely should move under docs too:
- `BACKLOG.md`
- `BACKLOG.csv`
- `CLI_GUIDE.md`
- `PROXY_SETUP.md`

---

## 4. HIGH-SUSPICION / PROBABLY REDUNDANT RUNTIMES

These import fine, but they look like alternate / incomplete runners rather than canonical paths.
They should be reviewed and likely moved to `archive/legacy-runners/` or removed later.

### Very likely non-canonical
- `archive_arbitrage_unified.py`
- `integrated_archive_system.py`
- `unified_runner.py`

Reason:
- they present themselves as unified entrypoints
- they contain placeholder / simulated logic
- they do not appear to be the real production path
- they increase confusion about "what actually runs"

### Needs specific review
- `run.py`

Reason:
- appears to be a Flask app bootstrap for DB/web usage
- may still be needed, but is not part of the main arbitrage runner path
- should be renamed or documented more clearly if retained

---

## 5. GENERATED / LOCAL ARTIFACTS THAT SHOULD NOT BE PROMINENT

These should be ignored, removed from git if tracked, or relocated if intentionally preserved locally.

- `.DS_Store`
- `.coverage`
- `server.log`
- `mercari_debug.png`
- `vinted_debug.png`
- `vinted_health.json`
- `archive_arbitrage.db`
- `gap_hunter.py.bak`

---

## 6. RECOMMENDED CLEANUP ORDER

### Step 1 — Safe structural cleanup
- create:
  - `scripts/debug/`
  - `scripts/verify/`
  - `scripts/manual-tests/`
  - `docs/archive/`
  - `archive/legacy-runners/`
- move obvious clutter first
- do **not** change imports or behavior yet unless a move requires it

### Step 2 — Rewrite root docs around reality
- keep one clean `README.md`
- add `docs/STATUS.md`
- add `docs/ARCHITECTURE.md`
- add `docs/OPERATIONS.md`
- archive historical doc dumps

### Step 3 — Review alternate runners
- confirm whether anything still depends on:
  - `archive_arbitrage_unified.py`
  - `integrated_archive_system.py`
  - `unified_runner.py`
  - `run.py`
- if not needed, archive them

### Step 4 — Rationalize tests
- keep real pytest tests under `tests/`
- move root live probes out of root
- optionally convert valuable ones into proper pytest or ops scripts later

---

## 7. Immediate Recommendation

The first physical cleanup pass should be:
1. move debug / verify / manual test scripts out of root
2. move historical markdown dump files into `docs/archive/`
3. leave canonical runtime files in place
4. do not touch `gap_hunter.py`, `pipeline.py`, or `trend_engine.py` during the first structural pass

This gives a cleaner repo quickly with low risk.

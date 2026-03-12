# Legacy Runners

This directory contains older or exploratory runner entrypoints that are **not** the canonical Archive Arbitrage runtime.

Archived here on 2026-03-12 to reduce confusion at the repo root.

## Archived files
- `archive_arbitrage_unified.py`
- `integrated_archive_system.py`
- `unified_runner.py`

## Why they were archived
These files were importable, but they were not the real production path:
- they mostly contained placeholder or simulated orchestration
- they created ambiguity about what should actually be run
- the canonical runtime is `gap_hunter.py`

## Current guidance
Use:

```bash
source venv/bin/activate
python gap_hunter.py
```

If you are working on the older pipeline path, use `pipeline.py` explicitly.

`run.py` remains at root for now because it appears to be a separate Flask/bootstrap path rather than one of the placeholder unified runners.

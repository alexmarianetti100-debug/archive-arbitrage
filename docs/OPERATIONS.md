# Archive Arbitrage — Operations

## Canonical Runtime

Always start by activating the project virtualenv:

```bash
source venv/bin/activate
```

Use the venv's `python`, not global system Python.

---

## Daily Commands

### Fast smoke test
Use this before larger changes, after dependency changes, or when checking whether the runner still boots:

```bash
python gap_hunter.py --once --max-targets 1 --skip-japan
```

### Normal one-cycle test
```bash
python gap_hunter.py --once --max-targets 3
```

### Continuous run
```bash
python gap_hunter.py
```

### Brand-scoped run
```bash
python gap_hunter.py --brand "rick owens"
```

### Custom query run
```bash
python gap_hunter.py --query "rick owens dunks,raf simons bomber"
```

---

## Health / Inspection

### Dependency check
```bash
python core/dependencies.py --critical-only
```

### Config help
```bash
python gap_hunter.py --help-config
```

### Cache stats
```bash
python gap_hunter.py --cache-stats
```

### Data metrics
```bash
python gap_hunter.py --data-metrics
```

### Blocklist stats
```bash
python gap_hunter.py --blocklist-stats
```

---

## Recommended Smoke-Test Sequence

When validating the service after changes:

1. Activate venv
   ```bash
   source venv/bin/activate
   ```

2. Verify dependencies
   ```bash
   python core/dependencies.py --critical-only
   ```

3. Run bounded smoke test
   ```bash
   python gap_hunter.py --once --max-targets 1 --skip-japan
   ```

4. If that passes, run a slightly larger one-cycle test
   ```bash
   python gap_hunter.py --once --max-targets 3
   ```

---

## Japan Sweep Notes

By default, `gap_hunter.py` can continue into a Japan arbitrage sweep after the main target loop.

For fast validation, prefer:

```bash
python gap_hunter.py --once --max-targets 1 --skip-japan
```

Use Japan-enabled runs when you actually want to test that integration.

---

## Troubleshooting

### "Project looks broken" outside the venv
That usually means you are not in the canonical runtime.

Fix:
```bash
source venv/bin/activate
```

### Dependency errors
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Then rerun:
```bash
python core/dependencies.py --critical-only
```

### Cache/state oddities
Inspect:
```bash
python gap_hunter.py --cache-stats
python gap_hunter.py --data-metrics
```

If needed:
```bash
python gap_hunter.py --cache-flush
python gap_hunter.py --cache-clear
```

### Alert path checks
Useful manual probes now live under:
- `scripts/debug/`
- `scripts/verify/`

---

## Cleanup-Aware Notes

- The main service is `gap_hunter.py`.
- `pipeline.py` still exists, but treat it as secondary unless you are specifically working on that path.
- Historical plans and implementation notes have been moved to `docs/archive/`.

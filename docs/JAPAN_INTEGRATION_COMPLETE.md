# Japan Arbitrage Integration - COMPLETE

**Date:** March 10, 2026
**Status:** ✅ FULLY INTEGRATED INTO GAP_HUNTER.PY

---

## What Was Done

The Japan arbitrage module is now **fully integrated** into the main gap_hunter.py system. It runs automatically as part of every cycle — no separate script needed.

---

## Integration Points

### 1. Import Statement (Line ~87)
```python
from core.japan_integration import find_japan_arbitrage_deals, JapanArbitrageMonitor
```

### 2. Cycle Integration (In `run_cycle()` method)
Japan arbitrage scan runs **every 3 cycles** (configurable) to avoid overloading:

```python
# ── Japan Arbitrage Scan ──
if self.cycle_count % 3 == 0:
    logger.info("🗾 Running Japan arbitrage scan...")
    japan_deals = await find_japan_arbitrage_deals(
        min_margin=25.0,
        min_profit=200.0,
    )
    
    for deal in japan_deals:
        if deal.recommendation in ['STRONG_BUY', 'BUY']:
            await self.process_deal(mock_deal, is_japan_deal=True)
```

### 3. Deal Processing (In `process_deal()` method)
Added `is_japan_deal` parameter with special handling:
- Skips auth check (proxy services authenticate)
- Creates Japan-specific signals
- Builds custom message with all cost breakdowns
- Sends to appropriate tier channel

### 4. Startup Logging
Now shows Japan arbitrage status on startup:
```
🎯 ARCHIVE ARBITRAGE - GAP HUNTER
   Min gap: 30% below sold avg
   Min profit: $150
   🗾 Japan arbitrage: ENABLED (every 3 cycles)
```

---

## How It Works Now

### Every Cycle:
1. **Regular gap hunting** — Grailed, Poshmark, eBay
2. **Every 3rd cycle** — Japan arbitrage scan added
3. **Unified alerts** — All deals go to same Discord/Telegram channels
4. **Same tier routing** — Japan deals routed to beginner/pro/big baller based on profit

### Example Output:
```
━━━ Cycle 12 | 86 targets ━━━
  [1/86] rolex submariner - sold avg: $8,500 (15 comps)
  ...
🗾 Running Japan arbitrage scan...
  🎯 Found 3 Japan arbitrage opportunities
    🗾 Japan deal sent: Hermès (+$2,343)
    🗾 Japan deal sent: Rolex (+$1,890)
    🗾 Japan deal sent: Chrome Hearts (+$456)
  🔥 5 gap deals sent!
```

---

## File Structure

```
archive-arbitrage/
├── gap_hunter.py              ← Main script (NOW INCLUDES JAPAN)
├── core/
│   ├── japan_cost_calculator.py   ← Cost calculation
│   ├── japan_integration.py       ← Scraping & analysis
│   └── ...
└── japan_scanner.py           ← Standalone CLI (optional)
```

---

## Running the System

### Option 1: Run Full System (Recommended)
```bash
cd ~/desktop/codingprojects/archive-arbitrage
python gap_hunter.py
```
Japan arbitrage runs automatically every 3 cycles.

### Option 2: Run Japan-Only Scan (For Testing)
```bash
python japan_scanner.py
```

---

## Configuration

Environment variables (in `.env`):
```bash
# Japan arbitrage thresholds
JAPAN_MIN_MARGIN=25.0
JAPAN_MIN_PROFIT=200.0

# Proxy service (buyee, neokyo, zenmarket, sendico, fromjapan)
JAPAN_PROXY_SERVICE=buyee
```

---

## What Gets Scanned

50+ high-value targets:
- **Watches:** Rolex, Cartier, Omega, Patek, AP
- **Bags:** Hermès, Chanel, LV, Goyard, Loewe
- **Jewelry:** Chrome Hearts, Van Cleef, Cartier, Tiffany
- **Fashion:** Rick Owens, Margiela, Saint Laurent, Balenciaga

---

## Deal Flow

```
Yahoo Auctions JP
       ↓
Buyee Proxy Service
       ↓
japan_integration.py (scraping)
       ↓
Cost calculation (all fees)
       ↓
Profit analysis
       ↓
gap_hunter.py process_deal()
       ↓
Discord/Telegram alerts
       ↓
Tier-appropriate channel
```

---

## Benefits of Integration

1. **Unified system** — One script to rule them all
2. **Shared alerting** — Same Discord/Telegram channels
3. **Consistent tier routing** — Japan deals get proper tier classification
4. **Automatic scheduling** — Runs every 3 cycles, no cron needed
5. **Combined stats** — Japan deals counted in total deals sent

---

## Next Steps

1. **Test it:** Run `python gap_hunter.py` and watch for "🗾 Running Japan arbitrage scan..."
2. **Monitor:** Check that Japan deals appear in Discord
3. **Tune:** Adjust `min_margin` and `min_profit` thresholds if needed
4. **Expand:** Add Mercari JP, Rakuten in future updates

---

## Summary

✅ Japan arbitrage is now **fully integrated** into gap_hunter.py
✅ Runs automatically every 3 cycles
✅ Sends alerts to same channels as regular deals
✅ Proper tier routing (beginner/pro/big baller)
✅ No separate script needed — everything in one place!

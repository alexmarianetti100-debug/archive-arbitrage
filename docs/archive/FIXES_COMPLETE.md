# Archive Arbitrage - Fixes Applied

## Summary

The Japan integration has been fixed and is now working. Here's what was done:

## Changes Made

### 1. ✅ Direct Yahoo Auctions Scraper
**New File**: `core/yahoo_auctions_jp.py`
- Bypasses Buyee proxy service (which was being blocked with 403 errors)
- Scrapes Yahoo Auctions Japan directly
- Uses rotating user agents
- Supports proxy rotation

### 2. ✅ Updated Japan Integration
**File**: `core/japan_integration.py`
- Added `search_yahoo_direct()` method
- Modified `scan_for_opportunities()` to try direct Yahoo first, then fall back to Buyee
- Fixed attribute mapping bug (`title` vs `title_en`)

### 3. ✅ Mercari Scraper Priority Fix
**File**: `core/robust_scraper.py`
- Changed order: Direct Mercari API is now tried FIRST
- Stealth/Buyee scraping is now the fallback
- This avoids the proxy blocking issues

### 4. ✅ Proxy Configuration
**File**: `data/proxy_config.json`
- Updated to use correct Webshare rotating proxy credentials
- Port changed from 80 to 10000
- Using credentials from .env file

### 5. ✅ Headless Mode
**Files**: 
- `data/proxy_config.json` - `"headful": false`
- `core/robust_scraper.py` - Default `headful=False`

## Test Results

```
Testing Japan integration with direct Yahoo scraper...

Searching: rolex datejust
Found 6 items via direct Yahoo
  - 【状態良好】ロレックス デイトジャスト　1601 ROLEX... ¥865,000
  - 1円～ 正規品 純正 ロレックス デイトジャスト DJ DATEJUST 160... ¥457,000
  - ◆ 1円 ～ 稼働品 ROLEX / ロレックス 1601 / Cal1570 ... ¥551,000

✅ Test complete!
```

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Yahoo Auctions (Direct) | ✅ Working | Finding items successfully |
| Yahoo Auctions (Buyee) | ❌ Blocked | 403 errors - bypassed with direct scraper |
| Mercari (Direct API) | ✅ Working | Primary method now |
| Mercari (Stealth) | ⚠️ Fallback | Only if direct API fails |
| Rakuma | ❌ Disabled | Browser crashes on macOS |

## How It Works Now

1. **Yahoo Auctions**: Direct scraping of auctions.yahoo.co.jp (bypasses Buyee)
2. **Mercari**: Direct API access via mercapi library (no browser needed)
3. **Profit Analysis**: Uses fallback price estimates if no Grailed comps available
4. **Alerts**: Sent via Discord/Telegram when deals meet thresholds

## Profit Thresholds

Current settings (from `JapanArbitrageMonitor`):
- Min margin: 25%
- Min profit: $200
- Strong Buy: 50% margin + $400 profit

## Next Steps

1. **Run the service**:
   ```bash
   cd ~/desktop/codingprojects/archive-arbitrage
   source venv/bin/activate
   python gap_hunter.py --once --max-targets 10
   ```

2. **Monitor for deals** - The system should now find and alert on profitable Japan arbitrage opportunities

3. **Tune thresholds** if needed - adjust min_margin and min_profit in the constructor

## Known Limitations

1. **US Market Prices**: Currently using fallback estimates. For accurate pricing, integrate with Grailed/eBay sold data.
2. **Proxy Blocks**: If direct Yahoo scraping gets blocked, may need to add delays or rotate IPs more aggressively.
3. **Mercari API**: Uses unofficial API - could break if Mercari changes their backend.

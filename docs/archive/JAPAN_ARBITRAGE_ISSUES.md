# Japan Arbitrage - Critical Fixes Required

## Issues Identified

### 1. **CRITICAL: asyncio.run() in Async Context (BREAKING)**
**Location**: `core/japan_integration.py`
**Problem**: Multiple methods call `asyncio.run()` from within already-running async context:
- `_analyze_mercari_item()` 
- `_analyze_mercari_direct_item()`
- `_analyze_mercari_robust_item()`
- `_analyze_buyee_item()`

**Error**: `asyncio.run() cannot be called from a running event loop`

**Impact**: Japan arbitrage scanning completely broken for Mercari and partially for Yahoo

**Fix Required**: 
- Convert all `_analyze_*` methods to async
- Change `asyncio.run(self.get_us_market_price(...))` to `await self.get_us_market_price(...)`
- Update all callers to use `await`

### 2. **Proxy Connection Refused**
**Location**: `core/proxy_pool.py` / `data/proxy_config.json`
**Problem**: Webshare proxy credentials not configured
**Error**: `NS_ERROR_PROXY_CONNECTION_REFUSED`
**Impact**: Stealth scraper fails, falls back to direct API (works but not ideal)
**Fix**: Add valid Webshare credentials to `data/proxy_config.json`

### 3. **Rakuma Browser Crashes**
**Location**: `core/rakuma_scraper.py`
**Problem**: Chromium crashes on macOS (SIGSEGV)
**Error**: `Target page, context or browser has been closed`
**Impact**: Rakuma scanning completely broken
**Fix Options**:
- Use Firefox instead of Chromium
- Disable Rakuma until fixed
- Find alternative API approach

### 4. **Mercari Direct API - Partially Working**
**Status**: API calls succeed (found 15 items) but analysis fails due to Issue #1
**Logs show**: `[Mercari Direct] Found 15 items` then `asyncio.run() cannot be called`

---

## Fix Plan

### Phase 1: Fix asyncio Issue (CRITICAL)
1. Make all `_analyze_*` methods async
2. Update `get_us_market_price()` calls to use `await`
3. Update all callers to use `await`

### Phase 2: Disable Broken Rakuma
1. Set `include_rakuma=False` by default
2. Log warning that Rakuma is disabled pending fix

### Phase 3: Proxy Configuration (Optional)
1. Get valid Webshare credentials
2. Update `data/proxy_config.json`

---

## Current Status Summary

| Platform | Status | Issue |
|----------|--------|-------|
| Yahoo Auctions | ✅ Working | Finds deals correctly |
| Mercari Direct API | ⚠️ Partial | API works, analysis broken (Issue #1) |
| Mercari Stealth | ❌ Broken | Proxy refused, falls back to API |
| Rakuma | ❌ Broken | Browser crashes (Issue #3) |

---

## Quick Fix Commands

```bash
# 1. Stop current process
Ctrl+C

# 2. Edit japan_integration.py to fix asyncio issues
# (See detailed edits below)

# 3. Restart
cd ~/desktop/codingprojects/archive-arbitrage
source venv/bin/activate
python gap_hunter.py
```

## Detailed Code Fixes Required

### Fix 1: Make `_analyze_mercari_robust_item` async
```python
async def _analyze_mercari_robust_item(self, item: dict) -> Optional[JapanDealAlert]:
    """Analyze Mercari item from robust scraper."""
    
    # Get US market price - USE await NOT asyncio.run
    us_price_result = await self.get_us_market_price(item['title_en'], item['category'])
    if not us_price_result:
        return None
    # ... rest of method
```

### Fix 2: Make `_analyze_buyee_item` async
```python
async def _analyze_buyee_item(self, item: dict) -> Optional[JapanDealAlert]:
    """Analyze Buyee item for arbitrage opportunity."""
    
    # Get US market price - USE await NOT asyncio.run
    us_price_result = await self.get_us_market_price(item['title_en'], item['category'])
    if not us_price_result:
        return None
    # ... rest of method
```

### Fix 3: Update caller in Yahoo scan
```python
for item in items:
    opportunity = await self._analyze_buyee_item(item)  # Add await
    if opportunity:
        # ...
```

### Fix 4: Update caller in Mercari scan
```python
for item in items:
    opportunity = await self._analyze_mercari_robust_item(item)  # Add await
    if opportunity:
        # ...
```

### Fix 5: Disable Rakuma by default
```python
async def scan_for_opportunities(
    self, 
    include_mercari: bool = True,
    include_rakuma: bool = False,  # Change to False
) -> List[JapanDealAlert]:
```

# Japan Arbitrage - Current Status

## ✅ Working: Yahoo Auctions JP
- **Status**: Fully functional
- **Method**: Server-side rendered HTML (easy to parse)
- **Results**: 10-20 items per search query
- **Speed**: Fast (~2-3 seconds per search)

## ⚠️ Blocked: Mercari JP & Rakuten Rakuma

### The Problem
Buyee (the proxy service) implements **anti-bot protection**:
- Detects headless browsers (Playwright, Selenium)
- Returns **403 Forbidden** for automated requests
- Uses JavaScript challenges to verify real browsers

### Evidence
```
Status: 403
Content length: 118  (blocked page)
```

### Attempted Solutions
1. ✅ **Playwright with Firefox** - Browser launches but site blocks
2. ✅ **Playwright with Chromium** - Crashes on macOS, blocked anyway
3. ❌ **Stealth plugins** - Would require undetected-playwright
4. ❌ **Direct Mercari scraping** - Would need Japanese IP/account

## Recommendation

**Use Yahoo Auctions JP for now.** It's working well and finding deals.

### Yahoo Auctions Coverage
- 106 optimized search targets
- All major luxury brands (Rolex, Hermès, Chanel, etc.)
- Japanese brands (Visvim, Neighborhood, WTAPS, etc.)
- Watches, bags, jewelry, fashion

### Alternative Approaches (Future)

#### Option 1: Direct Mercari API
Mercari has an unofficial API that could be used directly:
```python
# Would need Japanese IP and authentication
https://api.mercari.jp/v1/search
```

#### Option 2: Buyee Account + Cookies
If you have a Buyee account:
1. Login manually
2. Export cookies
3. Use cookies with scraper
4. May bypass bot detection

#### Option 3: Proxy Rotation + Stealth
Use residential proxies + stealth browser:
```python
# undetected-playwright or similar
from undetected_playwright import sync_playwright
```

#### Option 4: Focus on Yahoo Auctions
Yahoo Auctions has the largest inventory anyway:
- More sellers than Mercari
- Better for rare/vintage items
- Auction format = potential for below-market deals

## Current Implementation

The code is ready for all three platforms:
- `core/japan_integration.py` - Yahoo Auctions (✅ working)
- `core/mercari_scraper.py` - Mercari (⚠️ blocked)
- `core/rakuma_scraper.py` - Rakuma (⚠️ blocked)

If you want to enable Mercari/Rakuma in the future, the scrapers just need to bypass Buyee's bot detection.

## Testing Yahoo Auctions

```bash
cd ~/Desktop/codingprojects/archive-arbitrage
source venv/bin/activate

python3 -c "
from core.japan_integration import JapanArbitrageMonitor
import asyncio

async def test():
    monitor = JapanArbitrageMonitor()
    targets = [
        {'jp': 'ロレックス デイトジャスト', 'en': 'rolex datejust', 'category': 'watch', 'brand': 'Rolex', 'weight': 0.3},
        {'jp': 'エルメス バーキン', 'en': 'hermes birkin', 'category': 'bag', 'brand': 'Hermès', 'weight': 0.8},
    ]
    
    for target in targets:
        items = await monitor.search_buyee_yahoo(target)
        print(f'{target[\"en\"]}: {len(items)} items')
        for item in items[:2]:
            print(f'  - ¥{item[\"price_jpy\"]:,} - {item[\"title_jp\"][:40]}...')

asyncio.run(test())
"
```

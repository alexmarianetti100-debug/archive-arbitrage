# Mercari Japan Scraper — Implementation Plan

## Why This Matters
Mercari Japan is where Japanese archive pieces (Number Nine, Undercover, Hysteric Glamour, Kapital, Wacko Maria, NEIGHBORHOOD, WTAPS, Yohji, CDG, Issey) get listed at **domestic Japanese prices** — typically 30-50% below Grailed/eBay prices for the same items. This is the single biggest untapped arbitrage source for our bot.

## Architecture Overview

```
gap_hunter.py
  └── scrapers/mercari_jp.py (NEW)
        ├── Playwright-based (same pattern as mercari.py)
        ├── Japanese brand name mapping
        ├── JPY → USD price conversion
        ├── Shipping cost estimation (JP → US)
        └── Margin calculation with fees + shipping baked in
```

## Implementation Phases

### Phase 1: Core Scraper (~2-3 hours)
**File:** `scrapers/mercari_jp.py`

**What it does:**
- Extends `BaseScraper` (same as `mercari.py`)
- Uses Playwright to scrape `jp.mercari.com/search?keyword=X&status=on_sale`
- Extracts: title, price (JPY), images, condition, seller, listing URL
- Converts JPY → USD using a cached exchange rate

**Key differences from US Mercari scraper:**
- `BASE_URL = "https://jp.mercari.com"`
- Locale set to `ja-JP` in Playwright context
- Price parsing handles ¥ symbol and no decimal (¥15,000 format)
- Search uses Japanese keywords (see Phase 2)
- Items returned as `ScrapedItem` with `currency="JPY"` and converted `price` in USD

**Search URL format:**
```
https://jp.mercari.com/search?keyword=ナンバーナイン&status=on_sale&category_id=1
```
- `status=on_sale` = active listings only
- `category_id=1` = メンズ (Men's) — optional filter
- `sort=created_time&order=desc` = newest first

**DOM extraction targets** (Playwright selectors):
```
Item cards:  [data-testid="item-cell"]  or  .merItemThumbnail
Title:       item name from aria-label or inner text
Price:       ¥XX,XXX format, parse to integer
URL:         href from the card link → https://jp.mercari.com/item/mXXXXXXXXXX
Image:       img src within the card
Condition:   from item detail page (optional, skip in v1)
```

### Phase 2: Brand Name Mapping (~1 hour)
**File:** `scrapers/mercari_jp_brands.py`

Japanese sellers use a mix of English and Japanese brand names. We need a mapping table:

```python
JP_BRAND_QUERIES = {
    # brand_key: [list of JP search queries]
    "number nine": ["ナンバーナイン", "number nine", "NUMBER(N)INE"],
    "undercover": ["アンダーカバー", "undercover"],
    "hysteric glamour": ["ヒステリックグラマー", "hysteric glamour"],
    "kapital": ["キャピタル", "kapital"],
    "wacko maria": ["ワコマリア", "wacko maria"],
    "neighborhood": ["ネイバーフッド", "neighborhood"],
    "wtaps": ["ダブルタップス", "wtaps"],
    "yohji yamamoto": ["ヨウジヤマモト", "yohji yamamoto"],
    "comme des garcons": ["コムデギャルソン", "comme des garcons"],
    "issey miyake": ["イッセイミヤケ", "issey miyake"],
    "visvim": ["ビズビム", "visvim"],
    "bape": ["ア ベイシング エイプ", "bape", "A BATHING APE"],
    "julius": ["ユリウス", "julius"],
    "junya watanabe": ["ジュンヤワタナベ", "junya watanabe"],
    "sacai": ["サカイ", "sacai"],
    "human made": ["ヒューマンメイド", "human made"],
    "rick owens": ["リックオウエンス", "rick owens"],
    "chrome hearts": ["クロムハーツ", "chrome hearts"],
    "raf simons": ["ラフシモンズ", "raf simons"],
    "helmut lang": ["ヘルムートラング", "helmut lang"],
    "maison margiela": ["マルジェラ", "maison margiela"],
    "roen": ["ロエン", "roen"],
    "mihara yasuhiro": ["ミハラヤスヒロ", "mihara yasuhiro"],
    "soloist": ["ソロイスト", "soloist"],
}
```

**For gap_hunter integration:** When searching for a target like `"number nine skull cashmere"`, the JP scraper would:
1. Detect the brand → "number nine"
2. Look up JP queries → ["ナンバーナイン", "number nine"]
3. Translate key item words → "skull cashmere" → "スカル カシミヤ" (or just search English — many JP sellers use English titles)
4. Search both: `ナンバーナイン スカル` and `number nine skull cashmere`

### Phase 3: Price Normalization & Margin Calculation (~1 hour)
**File:** Update `scrapers/price_normalizer.py`

The margin calc needs to account for JP → US costs:

```python
# Constants
MERCARI_JP_FEE = 0.10          # 10% seller fee (already reflected in price)
BUYEE_SERVICE_FEE = 500        # ¥500 per item (~$3.30)
BUYEE_SHIPPING_ESTIMATE = {
    "small": 2000,             # ¥2,000 (~$13) - tees, accessories
    "medium": 3500,            # ¥3,500 (~$23) - jackets, pants
    "large": 5000,             # ¥5,000 (~$33) - heavy leather, boots
}
IMPORT_TAX_RATE = 0.0          # Under $800 = no US import duty (de minimis)
JPY_TO_USD_DEFAULT = 0.0066    # ~150 JPY = $1 (update via API)

def calculate_landed_cost_jp(price_jpy: int, size_category: str = "medium") -> float:
    """Calculate total cost to get a Mercari JP item to the US."""
    shipping = BUYEE_SHIPPING_ESTIMATE.get(size_category, 3500)
    total_jpy = price_jpy + BUYEE_SERVICE_FEE + shipping
    return total_jpy * get_exchange_rate()
```

**Exchange rate:** Cache from a free API (exchangerate-api.com) once per day.

**Proxy service consideration:** Most buyers use **Buyee** (buyee.jp) or **Zenmarket** as a proxy service to purchase from Mercari JP. The fees are:
- Buyee: ¥500/item service fee + shipping
- Zenmarket: ¥300/item + shipping
- Both handle packaging and international shipping

### Phase 4: Gap Hunter Integration (~1 hour)
**File:** Update `gap_hunter.py`

```python
# In find_gaps(), add Mercari JP as a source:
async def find_gaps(self, query, sold_data):
    gaps = []
    
    # Existing sources
    grailed_items = await self.search_grailed(query)
    posh_items = await self.search_poshmark(query)
    mercari_items = await self.search_mercari(query)
    
    # NEW: Mercari Japan
    mercari_jp_items = await self.search_mercari_jp(query)
    
    all_items = grailed_items + posh_items + mercari_items + mercari_jp_items
    # ... rest of gap calculation
```

**Source discount factor:**
```python
SOURCE_DISCOUNTS = {
    "grailed": 0.85,
    "poshmark": 0.80,
    "mercari": 0.70,
    "mercari_jp": 0.55,    # JP prices are typically 45% below Grailed
    "vinted": 0.80,
}
```

### Phase 5: Alert Formatting (~30 min)
Update alert messages to show Mercari JP items with:
- 🇯🇵 flag emoji for JP listings
- Price in both JPY and USD
- Estimated landed cost (with proxy fees + shipping)
- "Buy via Buyee" link: `https://buyee.jp/mercari/item/mXXXXXXXXXX`
- Note about proxy service requirement

Example alert:
```
🇯🇵 MERCARI JP GAP DEAL

Number (N)ine Skull Cashmere Sweater
¥25,000 ($165) + ~$25 shipping = $190 landed

Grailed avg sold: $450 (24 comps)
Gap: 58% below market
Profit est: $220+

🔗 https://buyee.jp/mercari/item/m12345678
⚠️ Requires proxy service (Buyee/Zenmarket)
```

## Technical Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Mercari JP blocks Playwright | Medium | Use JP-locale headers, rotate user agents, add delays (5-10s between requests) |
| Need JP proxy/VPN | Low | Initial tests show `jp.mercari.com` is accessible from US IPs |
| Exchange rate fluctuation | Low | Cache rate daily, use conservative estimate |
| Shipping cost varies wildly | Medium | Use category-based estimates, flag items over 5kg |
| Japanese title matching | Medium | Search both EN + JP terms, use brand name mapping |
| Sold data unavailable on JP | High | Use Grailed/eBay sold data as the "market price" benchmark (this is the arbitrage) |

## Dependencies
- Playwright (already installed)
- Exchange rate API (free tier, no key needed)
- No new pip packages required

## Estimated Total Effort
- Phase 1: 2-3 hours (core scraper)
- Phase 2: 1 hour (brand mapping)
- Phase 3: 1 hour (price normalization)
- Phase 4: 1 hour (gap hunter integration)
- Phase 5: 30 min (alert formatting)
- **Total: ~6 hours**

## File Changes Summary
```
NEW FILES:
  scrapers/mercari_jp.py           — Core JP scraper
  scrapers/mercari_jp_brands.py    — JP brand name mapping

MODIFIED FILES:
  gap_hunter.py                    — Add mercari_jp source
  scrapers/price_normalizer.py     — Add JP landed cost calc
  scrapers/__init__.py             — Export MercariJPScraper
  core/alerts.py                   — JP-specific alert format
```

## Priority
**HIGH** — This is the single biggest arbitrage opportunity. Japanese domestic prices for archive pieces are consistently 30-50% below US/EU resale. With 15+ Japanese brands in our targets, this scraper alone could double our deal flow.

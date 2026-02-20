# Archive Arbitrage

Automated archive fashion arbitrage platform. Scrapes multiple marketplaces for underpriced designer pieces, calculates real market pricing using live sold comps, detects iconic collections, and surfaces profitable opportunities.

## Quick Start

```bash
cd projects/archive-arbitrage
source venv/bin/activate

# Initialize database and scrape items
python pipeline.py scrape

# Run scheduled scrape (rotates brands, live comps)
python scheduled_scrape.py

# Run auction sniper (needs eBay API keys)
python auction_snipe.py

# Start the API server
python pipeline.py serve
# → http://localhost:8000
```

## Current Status

### ✅ Working
- **Scrapers** — Grailed (Algolia active + sold) and Poshmark active listings
- **Smart Pricing Engine** — Comp matcher (title similarity scoring), demand scorer (hot/warm/cold/dead), season detection (100+ iconic collections), 15-min price caching
- **SQLite Database** — 3,243 items across 183 brands, avg 48.7% margin
- **REST API** (FastAPI) — Full CRUD with filters, stats, market data, brand listing
- **Web Frontend** — 2,872-line SPA (dark/light mode, filters, search, favorites, keyboard shortcuts, item detail modal with market data & cross-platform compare)
- **Discord Alerts** — Rich embeds with tiers (💰→🔥→🏆), rate limiting, dedup, daily summaries, demand filtering
- **Scheduled Scraping** — Rotates through 270+ brands (20/run), tracks state between runs
- **Demand Scoring** — Supply/demand ratio analysis, sold velocity tracking, price pressure detection

### ✅ Phase 2: Exact Product Matching — COMPLETE
- **Product Fingerprinting** — `scrapers/product_fingerprint.py` extracts canonical product identity from messy titles
  - Brand → Sub-brand → Model → Item Type → Material → Color
  - Example: "Rick Owens DRKSHDW Black Geobasket" → `rick owens|drkshdw|geobasket|footwear|leather|black`
- **Product Catalog** — 21 canonical products from 896 sold comps
  - 10 high-velocity products (5+ sales/30 days)
  - Auto-clustered from sold comp titles
  - Price bands per product (min/avg/max)
- **Exact Product Comps** — Match items to exact products, not fuzzy text search
- **Velocity-Based Grading** — A-grade requires high-velocity product + tight price confidence
- **Database Schema** — `products` table + `product_prices` table for sale history

### 🚧 Phase 3: Multi-Platform Sold Data — IN PROGRESS
- **eBay Sold Scraper** — `scrapers/multi_platform.py` HTML fallback for sold listings
- **Multi-Platform Pricer** — Aggregates pricing from Grailed + eBay + Poshmark
  - Weighted consensus pricing (Grailed 50%, eBay 40%, Poshmark 10%)
  - Cross-platform spread detection
- **eBay API Integration** — Code ready, needs Production API keys
  - Webhook endpoint: `ebay_webhook.py` (deploy for account deletion compliance)
  - Get keys at: https://developer.ebay.com/

### ✅ Phase 4: Cross-Platform Arbitrage — COMPLETE
- **Arbitrage Detector** — `detect_arbitrage.py` finds same item on multiple platforms
  - Buy low on Poshmark → Sell high on Grailed/eBay
  - Platform fee calculator (Grailed 9%, Poshmark 20%, eBay 13%)
  - Net profit after fees
  - Confidence scoring (high/medium/low based on velocity)
- **Results**: Found 28 opportunities in first run, including:
  - Helmut Lang outerwear: $45 Poshmark → $473 Grailed = $364 profit

### ✅ Phase 5: Frontend Rebuild — COMPLETE
- **React + TypeScript Frontend** — `frontend-react/` modern SPA
  - Dashboard with real-time stats, grade distribution, velocity charts
  - Deals browser with grid/list views, filters, sorting
  - Arbitrage opportunities page with profit breakdown
  - Product catalog with velocity data
  - Built with Vite, Tailwind CSS, TanStack Query
- **API Integration** — RESTful endpoints for all features
  - `/api/items` — Filterable item listing
  - `/api/products` — Product catalog
  - `/api/arbitrage` — Cross-platform opportunities
  - `/api/stats` — Dashboard statistics

### ⚠️ Partially Built / Needs Work
- **Auction Sniping** — Code exists (`auction_snipe.py`, `scrapers/auction_sniper.py`) but needs Production eBay API keys
- **Additional scrapers** — eBay HTML, Depop, Mercari, ShopGoodwill, Gem, NoBids all coded but most get 403'd without residential proxies or browser automation
- **`api/routes/`** — Empty directory (routes are all inline in `api/main.py`)
- **`workers/`** — Empty directory (planned for background jobs)

### ⬜ Phase 6-10: Future (See ROADMAP.md)
- **Phase 6**: Auto-Listing / Resale Pipeline — one-click cross-list to Grailed/eBay/Poshmark
- **Phase 7**: Watchlist & Price Tracking — price drop alerts, stale listing detection
- **Phase 8**: Profit Analytics Dashboard — actual vs. predicted profits
- **Phase 9**: Mobile PWA — iOS/Android app
- **Phase 10**: Production Scale — PostgreSQL, cloud deployment

## Commands

### 🚀 Full Pipeline (Recommended)

```bash
# Run complete pipeline: scrape → qualify → Discord alerts → site updated
python pipeline.py run

# Options
python pipeline.py run --brand "rick owens"           # Scrape specific brand
python pipeline.py run --sources grailed,poshmark     # Specific sources
python pipeline.py run --max 15                       # 15 items per source
python pipeline.py run --min-grade A                  # Only alert on A-grade (guaranteed flips)
python pipeline.py run --dry-run                      # Test without saving/sending
```

### Individual Commands

```bash
# === SCRAPING ===

# Scrape priority brands with live pricing
python pipeline.py scrape

# Scrape a specific brand
python pipeline.py scrape --brand "rick owens"

# Scrape all tracked brands (slow, 270+ brands)
python pipeline.py scrape --all-brands

# Scheduled scrape (20 brands per run, rotates through all)
python scheduled_scrape.py

# Auction sniper (eBay auctions ending soon, low bids)
python auction_snipe.py
python auction_snipe.py --brand "raf simons" --hours 6

# === DATABASE ===

# List items in database
python pipeline.py list
python pipeline.py list --brand "raf simons"

# Show statistics
python pipeline.py stats

# === SERVER ===

# Start API server + frontend
python pipeline.py serve

# Frontend Access:
# - New React frontend: http://localhost:8000 (auto-served if built)
# - Legacy frontend: http://localhost:8000/frontend/index.html
# - API docs: http://localhost:8000/docs

# === FRONTEND DEVELOPMENT ===

# Build new React frontend
cd frontend-react
npm install
npm run build

# Dev mode (hot reload)
npm run dev  # Runs on http://localhost:3000

# === QUALIFICATION (Pass 2) ===

# Deep-qualify scraped items (selling volume, days-to-sell estimate, deal grades)
python pipeline.py qualify
python pipeline.py qualify --alert              # Send Discord alerts for A/B deals
python pipeline.py qualify --brand "helmut lang" # Qualify specific brand
python pipeline.py qualify --requalify          # Re-grade all items

# === DEALS ===

# View qualified deals by grade
python pipeline.py deals --grade A              # Guaranteed flips
python pipeline.py deals --grade B              # Likely flips
python pipeline.py deals --limit 50

# === ALERTS ===

# Send a test alert to Discord
python alerts.py --test

# Send daily summary to Discord
python alerts.py --summary
```

## Architecture

```
archive-arbitrage/
├── scrapers/                # Marketplace scrapers
│   ├── base.py              # Base scraper with HTTP client, proxy support
│   ├── grailed.py           # ✅ Grailed (Algolia API — active + sold)
│   ├── poshmark.py          # ✅ Poshmark
│   ├── ebay_api.py          # eBay Browse API (needs production keys)
│   ├── auction_sniper.py    # eBay auction sniping module
│   ├── nobids.py            # NoBids.net (eBay auctions, no bids)
│   ├── depop.py             # Depop (often 403s)
│   ├── mercari.py           # Mercari (often 403s)
│   ├── shopgoodwill.py      # ShopGoodwill (API unreliable)
│   ├── gem.py               # Gem (Japanese consignment)
│   ├── ebay.py              # eBay HTML scraper (legacy)
│   ├── brands.py            # 270+ brands, priority lists, keywords
│   ├── seasons.py           # 🔥 Iconic season/collection detection
│   ├── comp_matcher.py      # Smart title-based comp matching
│   ├── demand_scorer.py     # Supply/demand velocity scoring
│   └── proxy_manager.py     # Proxy rotation (Webshare)
├── api/                     # FastAPI backend
│   ├── main.py              # API endpoints + frontend serving
│   └── services/
│       └── pricing.py       # Live comps + season boost + margin calc
├── db/
│   ├── sqlite_models.py     # SQLite: items, price history, sold comps
│   └── models.py            # PostgreSQL models (future)
├── frontend/
│   └── index.html           # Full SPA (dark/light, filters, modals)
├── data/
│   ├── archive.db           # SQLite database
│   ├── price_cache.json     # Live comp price cache (15min TTL)
│   ├── scrape_state.json    # Brand rotation state
│   └── alert_state.json     # Discord alert dedup + rate limit state
├── pipeline.py              # Main CLI (scrape/list/stats/serve)
├── scheduled_scrape.py      # Cron-friendly brand rotation scraper
├── auction_snipe.py         # eBay auction opportunity finder
├── alerts.py                # Discord alert system
├── ebay_webhook.py          # eBay account deletion webhook (API compliance)
├── run_scraper.py           # Original scraper CLI (advanced)
└── setup_proxies.py         # Webshare proxy setup
```

## Pricing Engine

### How It Works

1. **Smart Comp Matching** — Parses item titles, extracts brand/sub-brand/model/material/season, searches with increasingly specific queries, scores each comp by similarity
2. **Live Sold Comps** — Fetches 20 recently sold items from Grailed for the brand + category
3. **Season Detection** — Checks title for iconic collections, applies multiplier (1.2x–4.0x)
4. **Demand Scoring** — Measures sold velocity vs. active supply to determine HOT/WARM/COLD/DEAD
5. **Price Calculation** — Sets sell price 10% below adjusted market, enforces 25% min margin
6. **Decision** — Save if profitable ($20+ profit), skip if margin too thin

### Season Multipliers (Examples)

| Brand | Collection | Multiplier |
|-------|-----------|------------|
| Raf Simons | AW01 Riot Riot Riot | 3.5x |
| Helmut Lang | Astro Biker Jacket | 4.0x |
| Number (N)ine | AW05 The High Streets | 3.5x |
| Undercover | SS03 Scab | 3.5x |
| Dior Homme | Clawmark (Hedi era) | 3.0x |
| Margiela | Artisanal / Line 0 | 3.0x |
| CDG | SS97 Lumps & Bumps | 3.5x |

Full list in `scrapers/seasons.py` — 100+ patterns across 15+ brands.

### Pricing Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Min margin | 25% | Below this = skip |
| Target margin | 35% | Ideal sweet spot |
| Market discount | 10% | Price below market for quick sales |
| Max markup | 2.5x | Cap to avoid overpricing |
| Min profit | $20 | Below this = not worth the effort |

### Alert Thresholds

| Parameter | Value | Notes |
|-----------|-------|-------|
| Min profit to alert | $150 | Only notify on serious deals |
| Min margin to alert | 40% | High-confidence flips only |
| 🔥 Hot Deal | $300+ profit | Orange-red embed |
| 🏆 Grail Alert | $500+ profit | Gold embed |
| Rate limit | 15/hour | 30s cooldown between alerts |

## API Endpoints

Server: `http://localhost:8000` | Docs: `http://localhost:8000/docs`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Frontend SPA |
| `/api/items` | GET | List items (filters: brand, price, sort, pagination) |
| `/api/items/{id}` | GET | Item detail |
| `/api/items/{id}/price-history` | GET | Price change history |
| `/api/items/{id}/market-data` | GET | Live Grailed market data |
| `/api/stats` | GET | DB statistics |
| `/api/brands` | GET | All brands in database |

## Environment Variables

```bash
# .env file

# Proxy (Webshare)
PROXY_SERVICE=webshare
PROXY_HOST=p.webshare.io
PROXY_PORT=10000
PROXY_USERNAME=xxx
PROXY_PASSWORD=xxx
PROXY_API_KEY=xxx

# eBay API (for auction sniping)
EBAY_APP_ID=xxx          # Production App ID (Client ID)
EBAY_CERT_ID=xxx         # Production Cert ID (Client Secret)

# Discord Alerts
DISCORD_WEBHOOK_URL=xxx  # Webhook URL for deal alerts
```

## Tracked Brands (270+)

**Japanese Archive:** Number (N)ine, Undercover, CDG (all lines), Yohji Yamamoto, Issey Miyake, Kapital, Visvim, WTAPS, Neighborhood, BAPE, Sacai, Junya Watanabe, Julius, Wacko Maria, Cav Empt...

**European Archive:** Rick Owens, Raf Simons, Helmut Lang, Maison Margiela, Ann Demeulemeester, Dries Van Noten, Haider Ackermann, Carol Christian Poell, Boris Bidjan Saberi, Guidi...

**Luxury/Designer:** Dior Homme, Saint Laurent, Celine, Prada, Gucci, Bottega Veneta, Balenciaga, Jean Paul Gaultier, Vivienne Westwood, Alexander McQueen, Thierry Mugler...

**Streetwear:** Supreme, Palace, Off-White, Vetements, Fear of God, Chrome Hearts, Gallery Dept, Rhude, Amiri...

Full list in `scrapers/brands.py`

---

## To-Do / Roadmap

### Phase 1: Quick Wins & Polish ✅ DONE
- [x] Wire `alert_if_profitable()` into scrape pipeline (`pipeline.py` + `scheduled_scrape.py`)
- [x] Add configurable alert thresholds via `.env` (min profit, min margin, brand watchlist)
- [x] Season detection expanded to 62 brands, 570 patterns, 93 aliases
- [x] Fix season multiplier double-counting (smart comps absorb premium)
- [x] Add timeouts to all async pricing calls (comps, demand, cache warming)
- [ ] Set up daily summary cron (`alerts.py --summary`)

### Phase 2: Exact Product Matching & Guaranteed Resale ← ACTIVE

The #1 priority. Current comp matching is fuzzy (brand + category + keywords). For guaranteed resale, we need to identify **the exact product** and only surface items with **proven, high-velocity sales**.

#### 2A: Exact Product Identification ✅ DONE
- [x] **Product fingerprinting** — `scrapers/product_fingerprint.py` extracts canonical identity:
  - Brand → Sub-brand/Line → Model → Colorway → Material
  - Example: `"Rick Owens DRKSHDW | Geobasket | Leather | Black"`
  - Unique fingerprint hash for clustering
- [x] **Product catalog** — 69 products from 952 sold comps
  - `build_product_catalog.py` clusters titles into canonical products
  - `products` table stores brand, model, item_type, velocity metrics
- [x] **Database schema** — `products` + `product_prices` tables
- [ ] **Match incoming listings** — integrate into qualification pipeline

#### 2B: Sell-Through Velocity ✅ DONE
- [x] **Track sales velocity per product** — sales_30d, sales_90d in products table
- [x] **Volume threshold** — `is_high_velocity` flag (5+ sales/30d)
- [x] **Velocity trends** — accelerating/steady/decelerating tracking
- [ ] **Days-to-sell estimate** — calculate from sales velocity
- [ ] **Filter mode: "guaranteed only"** — frontend filter for high-velocity products

#### 2C: Price Confidence Bands 🚧 IN PROGRESS
- [x] **Price bands** — min/max/median per product from sale history
- [x] **Confidence scoring** — based on comp count + price spread
- [ ] **Risk rating integration** — update deal grades based on exact product risk
- [ ] **Only alert on Low Risk items** — filter A-grade alerts to high-confidence matches

### Phase 3: Multi-Platform Sold Data
- [ ] **eBay completed/sold listings** — huge volume, real market data
  - Get Production API keys approved (deploy `ebay_webhook.py` first)
  - eBay Browse API `item_summary/search` with `filter=buyingOptions:{FIXED_PRICE|AUCTION},conditions:{USED}` + sold items
- [ ] **Poshmark sold prices** — they expose sold data in listings
- [ ] **Cross-platform price consensus** — if it sells for $400 on Grailed AND $400 on eBay, that's a real price
  - Weight by platform volume (eBay has more data, Grailed is more archive-specific)
  - Flag divergences ("$200 on Poshmark but $500 on Grailed" = arbitrage opportunity)
- [ ] **Aggregate sold database** — store all sold comps in a local DB for faster lookups and historical analysis
- [ ] Integrate NoBids scraper into pipeline (auction deals with no bids)
- [ ] Add Playwright browser automation fallback for Depop/Mercari/ShopGoodwill

### Phase 4: Cross-Platform Arbitrage
- [ ] Detect same item listed on multiple platforms at different prices
- [ ] Image-based matching (same item, different titles/photos)
  - Perceptual hashing or CLIP embeddings for image similarity
  - "This jacket on Poshmark for $200 is the same one that sold 3x on Grailed for $500"
- [ ] Price gap alerts with net profit after platform fees
- [ ] Platform fee calculator (Grailed 9%, Poshmark 20%, eBay ~13%)
- [ ] Net profit comparison across platforms

### Phase 5: Frontend Rebuild
- [ ] Migrate from monolithic HTML to React/Vue/Svelte components
- [ ] Profit analytics charts (brand performance, margin distribution, trends)
- [ ] **Resellability dashboard** — sort by velocity, confidence, risk
- [ ] Watchlist feature (save items, track price drops)
- [ ] Full-text search with saved filters
- [ ] Product detail page with full sold history, price chart, velocity graph

### Phase 6: Auto-Listing & Resale Pipeline
- [ ] Auto-generate optimized listing titles (SEO for Grailed/eBay)
- [ ] Smart description templates per brand/category
- [ ] One-click cross-list to Grailed, eBay, Depop
- [ ] Inventory sync — mark sold when source item disappears
- [ ] Profit/loss tracking per listed item

### Phase 7: Watchlist & Price Tracking
- [ ] Track specific items over time
- [ ] Price drop alerts (seller dropped 20%+ = negotiation opportunity)
- [ ] Stale listing detection (listed 30+ days = lowball opportunity)
- [ ] Auto-offer suggestions (Poshmark/Grailed offer system)

### Phase 8: Mobile & Scaling
- [ ] Progressive Web App (PWA) for mobile
- [ ] Push notifications
- [ ] PostgreSQL migration
- [ ] Cloud deployment (Railway/Fly.io) for 24/7 operation
- [ ] Yahoo Japan Auctions via Buyee proxy

## Known Issues

1. **Comp matching is fuzzy** — ✅ FIXED by product fingerprinting (Phase 2A). Now clusters exact products.
2. **No sell-through velocity** — ✅ FIXED by product catalog with sales_30d tracking (Phase 2B).
3. **Single data source for comps** — only Grailed sold data. Adding eBay sold will dramatically improve pricing accuracy. Phase 3 fixes this.
4. **eBay API**: Sandbox credentials don't return real data. Need Production keys (requires account deletion webhook endpoint).
5. **Depop/Mercari**: Frequently return 403s. Need residential proxies or browser automation.
6. **Frontend**: Single 2,872-line HTML file — functional but needs component architecture for maintainability.
7. **Product catalog coverage** — Only 69 products from 952 comps. Need more sold data for broader coverage.

## License

Private — not for distribution.

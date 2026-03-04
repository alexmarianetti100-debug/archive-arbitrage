# Platform Research: Expanding Archive Arbitrage

*Research Date: February 23, 2026*

## Current State

| Platform | Method | Status |
|----------|--------|--------|
| Grailed | Algolia API (direct) | ✅ Production |
| Poshmark | HTTP scraping | ✅ Production |
| Depop | Playwright browser | 🟡 Built, untested |
| Mercari | Playwright browser | 🟡 Built, untested |

---

## Platform Analysis

### 1. Depop

**Technical Feasibility: Medium**

- **No Algolia backend** — Depop uses a custom GraphQL API and internal REST endpoints
- **API endpoint**: `https://webapi.depop.com/api/v2/search/products/` — accessible via HTTP with proper headers, but rate-limited and requires session tokens
- The Depop mobile app uses `webapi.depop.com` — interceptable with mitmproxy for endpoint discovery
- **Anti-bot**: Moderate. CloudFlare protection on web. API endpoints require valid session cookies. Rate limiting present but not aggressive
- **Existing scrapers**: `Gertje823/Vinted-Scraper` (121★) scrapes both Vinted and Depop via their APIs. `scraper-bank/Depop.com-Scrapers` offers production-ready Playwright scrapers
- **Our existing scraper**: `depop_playwright.py` — Playwright-based, should work. Consider also trying direct API calls to `webapi.depop.com/api/v2/search/products/` with intercepted headers before falling back to Playwright

**Archive Fashion Scene**: Mixed. Depop skews younger (Gen Z) and is strong for vintage but weaker for high-end archive. Good for: Helmut Lang, early Margiela, Raf Simons (younger sellers who don't know prices). Weak for: Chrome Hearts, heavy hitters. Volume is moderate.

**Price Competitiveness**: **HIGH deal potential**. Depop sellers are often young, fashion-aware but not price-savvy on specific archive pieces. Mispriced items common, especially Japanese designers and 90s/early 2000s pieces.

**Implementation Effort**: LOW — we already have the Playwright scraper built. Just needs testing and integration.

**Priority: 🔴 HIGH (#1) — Already built, just test and deploy**

---

### 2. Mercari (US)

**Technical Feasibility: Medium-Hard**

- **API**: Mercari uses internal GraphQL API at `https://www.mercari.com/v1/api` with anti-bot protections
- Returns 403 on direct HTTP requests (why we built Playwright scraper)
- `kevinxo328/mercari-scraper` (3★) — TypeScript monorepo using Playwright + Prisma + Next.js, well-architected reference
- Mercari has gotten more aggressive with bot detection: browser fingerprinting, CAPTCHA challenges
- **Workaround**: Playwright with stealth plugin (`playwright-extra` + `stealth` plugin) or residential proxies
- Their search API can sometimes be accessed by replicating the exact headers/cookies from a browser session

**Archive Fashion Scene**: Decent. More mainstream than Grailed but significant archive inventory. Sellers range from casual (great for deals) to professional resellers.

**Price Competitiveness**: **VERY HIGH deal potential**. Mercari's fee structure encourages quick sales. Many non-collector sellers list archive pieces at garage-sale prices. Probably the single best platform for finding underpriced archive after Facebook Marketplace.

**Implementation Effort**: LOW — already built, needs testing. May need stealth plugin additions.

**Priority: 🔴 HIGH (#2) — Already built, test immediately**

---

### 3. eBay

**Technical Feasibility: HIGH (official API)**

- **Browse API** (`/buy/browse/v1/item_summary/search`): Best fit for our use case. Supports keyword search, category filtering, price ranges, item condition, sorting by newest. Returns up to 10,000 items per result set.
- **Feed API** (Beta, Limited Release): Provides daily/hourly feed files of new listings by category. Would be ideal for monitoring new archive fashion listings. Requires eBay approval.
- **Finding API** (Legacy): Still works, supports saved searches and filtering. `findItemsAdvanced` with aspect filters for brand.
- **No webhook/push notifications for new listings** — must poll. Browse API is best for polling.
- **Rate limits**: 5,000 calls/day for Browse API (sufficient for our needs)
- We already have `EBAY_PRODUCTION_SETUP.md` and `scrapers/ebay_api.py` — need to deploy the deletion webhook endpoint to get production keys
- **eBay Feed SDK** (official, Java): Can download entire category feeds and filter offline

**Recommended Approach**:
1. Deploy Vercel webhook endpoint (already documented in EBAY_PRODUCTION_SETUP.md)
2. Get production keys
3. Use Browse API `search` endpoint with brand-specific queries
4. Poll every 5-15 minutes for new listings sorted by `newlyListed`
5. Filter by: Men's Clothing category, specific brands, price ranges below market

**Archive Fashion Scene**: **MASSIVE** inventory. eBay is the largest resale marketplace globally. Deep archive inventory across all brands. Both auction and BIN formats.

**Price Competitiveness**: **HIGH**. Auctions ending at odd hours go cheap. BIN listings from estate sales, non-collectors, and international sellers frequently underpriced. The volume means more deals in absolute numbers even if the percentage is lower.

**Implementation Effort**: MEDIUM — API is well-documented, we have partial setup. Main work is deploying webhook + writing Browse API integration.

**Priority: 🔴 HIGH (#3) — Biggest inventory, official API, partially set up**

---

### 4. Vestiaire Collective

**Technical Feasibility: Medium**

- **No public API**
- Website uses a React frontend with internal REST API endpoints
- Search endpoint: `https://www.vestiairecollective.com/api/search/catalog/` — returns JSON, accessible with proper headers
- **Anti-bot**: Moderate. Uses DataDome (bot detection service). Will block automated requests without proper browser fingerprints.
- Playwright with stealth would be needed, or rotating residential proxies with browser-like headers
- No notable open-source scrapers found

**Archive Fashion Scene**: **EXCELLENT for luxury archive**. Strong in: Margiela, Rick Owens, Helmut Lang, Raf Simons, CDG. European platform means access to EU-based sellers with different pricing.

**Price Competitiveness**: MODERATE. Vestiaire has authentication fees and higher seller awareness. Deals exist but are less frequent than Mercari/Depop. Best deals come from EU sellers pricing in EUR (currency arbitrage) and consignment pieces priced to move quickly.

**Implementation Effort**: HIGH — DataDome is a significant anti-bot challenge. Would need Playwright + stealth + residential proxies.

**Priority: 🟡 MEDIUM (#6) — Good inventory but hard to scrape and fewer deals**

---

### 5. The RealReal

**Technical Feasibility: Medium**

- **No public API**
- Internal API at `https://www.therealreal.com/api/` — JSON responses from search
- **Anti-bot**: Moderate to high. Uses Akamai Bot Manager. Known to block scrapers.
- Playwright approach would work but needs stealth measures
- Their search is filterable by designer, category, size — good for targeted monitoring
- New consignment items appear daily and are often priced by TRR staff (not the seller), leading to consistent underpricing of niche archive pieces

**Archive Fashion Scene**: **EXCELLENT**. TRR gets high-quality consignment pieces from wealthy clients. Archive Raf, Helmut Lang, Margiela, Rick Owens regularly appear. Their authenticators know luxury but sometimes miss archive-specific premium pricing.

**Price Competitiveness**: **VERY HIGH deal potential**. TRR prices based on general market value, not archive-collector premiums. A FW02 Raf Simons piece might be priced as "used Raf Simons" rather than at its true archive value. This is where the biggest dollar-value arbitrage opportunities exist.

**Implementation Effort**: HIGH — Akamai bot protection, need stealth Playwright + proxies.

**Priority: 🟡 MEDIUM-HIGH (#5) — Excellent arbitrage potential, challenging technically**

---

### 6. Yahoo Japan Auctions (via Buyee/Zenmarket)

**Technical Feasibility: Medium**

- **Yahoo Auctions Japan** shut down public API access years ago
- **Access via proxy services**: Buyee (`buyee.jp`) and Zenmarket (`zenmarket.jp`) provide English-language frontends
- Buyee has no public API. Their site is scrapable via Playwright
- Zenmarket has a slightly more accessible interface
- **Alternative**: Use `auctions.yahoo.co.jp` directly — Japanese site, scrapable with proper locale headers. Search results return JSON via internal API
- **fromjapan.co.jp** is another proxy service worth considering
- No significant open-source scrapers found for Yahoo Japan Auctions

**Recommended Approach**: 
1. Scrape Buyee search results (easier English interface) via Playwright
2. OR intercept Yahoo Japan's internal search API (more data, Japanese language — would need translation layer)
3. Set up saved searches on Buyee for key terms (リックオウエンス, ラフシモンズ, etc.)

**Archive Fashion Scene**: **LEGENDARY**. Japan is THE market for archive fashion. CDG, Yohji Yamamoto, Undercover, Number (N)ine, WTAPS, Visvim, Kapital — all at domestic prices. Also excellent for western archive (Raf, Helmut, Margiela) at below-global-market prices because Japanese sellers price for domestic market.

**Price Competitiveness**: **HIGHEST of any platform**. Japanese domestic prices are often 30-60% below global resale. Number (N)ine pieces that sell for $800+ on Grailed go for ¥20,000-30,000 ($130-200) on Yahoo Auctions. Similar patterns for Undercover, CDG, early Yohji.

**Implementation Effort**: HIGH — language barrier, proxy service complexity, shipping/customs considerations. But the ROI is enormous.

**Priority: 🔴 HIGH (#4) — Best deals in the entire resale ecosystem, worth the effort**

---

### 7. Mercari Japan

**Technical Feasibility: Medium**

- **Mercari Japan** (`jp.mercari.com`) has a different tech stack from US Mercari
- Internal API accessible but returns Japanese content
- Accessible through Buyee's Mercari integration (buyee.jp/mercari)
- Can be scraped via Playwright on the Buyee frontend or directly on jp.mercari.com
- Rate limiting and bot detection present but less aggressive than US Mercari

**Rakuten/Rakuma**: Rakuma (Rakuten's flea market app) is accessible via Buyee. Lower volume than Yahoo Auctions or Mercari Japan but occasional gems. Lower priority.

**Archive Fashion Scene**: Excellent — same Japanese market advantages as Yahoo Auctions. Mercari Japan skews slightly younger/more casual than Yahoo Auctions.

**Price Competitiveness**: **VERY HIGH** — same Japanese domestic pricing advantage.

**Implementation Effort**: MEDIUM — if we build Yahoo Japan via Buyee, extending to Mercari Japan via Buyee is incremental.

**Priority: 🟡 MEDIUM-HIGH (#7) — Bundle with Yahoo Japan Auctions work**

---

### 8. Facebook Marketplace

**Technical Feasibility: VERY LOW**

- **No public API** for Marketplace (Facebook deprecated the Marketplace API in 2018)
- **Extremely aggressive anti-bot**: Meta's anti-scraping is best-in-class. Account bans, IP bans, CAPTCHA walls
- Playwright scraping is possible but requires logged-in Facebook accounts that get banned quickly
- Some services use rotating residential proxies + account farms but this is against ToS and unreliable
- **Meta's Graph API** does not expose Marketplace data
- The few GitHub scrapers that exist are all broken/archived

**Archive Fashion Scene**: HUGE untapped potential. Non-collectors list archive pieces at absurd prices because they don't know what they have. The "grandma's closet" factor is real.

**Price Competitiveness**: **HIGHEST individual-item deal potential** — $20 Helmut Lang bondage pieces, $50 Raf Simons from people cleaning out closets. But impossible to systematically scrape.

**Implementation Effort**: VERY HIGH and unreliable. Would need account farms, constant maintenance, high ban rate.

**Priority: 🔴 SKIP — Not technically feasible for automated scraping. Consider manual monitoring or a future browser extension approach.**

---

### 9. Vinted

**Technical Feasibility: HIGH**

- **Well-documented internal API**: `https://www.vinted.{tld}/api/v2/catalog/items` — returns JSON search results
- **Excellent open-source tooling**: `Giglium/vinted_scraper` (49★) — pip-installable Python package with sync/async support, automatic cookie management. Just `pip install vinted_scraper` and go.
- Anti-bot: Low-moderate. Cookie-based session management, occasional 403s on item detail pages but search works well
- Supports multiple European domains: vinted.fr, vinted.de, vinted.co.uk, vinted.es, vinted.it, etc.
- **Rate limiting**: Present but manageable with delays

**Archive Fashion Scene**: Growing rapidly. Vinted is Europe's largest secondhand platform. Good for: Margiela (especially from French/Belgian sellers near the maisons), Helmut Lang, Raf Simons, European archive. Weaker for: American streetwear, Japanese designers.

**Price Competitiveness**: **HIGH**. Vinted has zero seller fees (buyer pays), so sellers price lower. European sellers often don't know US archive market prices. Currency differences (EUR→USD) can create additional arbitrage. Strong for Margiela, Dries Van Noten, Ann Demeulemeester at below-Grailed prices.

**Implementation Effort**: **VERY LOW** — pip install an existing package, write integration layer. Could be production-ready in a day.

**Priority: 🔴 HIGH (#5) — Easiest new platform to add, good deals, existing pip package**

---

### 10. Other Platforms

**ShopGoodwill** (`shopgoodwill.com`)
- We already have `scrapers/shopgoodwill.py`! Online Goodwill auction site. Occasional archive gems at charity-store prices.
- Priority: Already have it, ensure it's integrated.

**Hardly Ever Worn It** (`hardlyeverworni.com`)
- Luxury resale, UK-based. Small inventory, high-end. No public API. Playwright scrapable.
- Priority: LOW — small inventory, high prices.

**Heresy** — Very small niche platform. Not worth the effort.

**Grailed alternatives**:
- **Curtsy** (women's focused) — small, not worth it
- **Kidizen** (kids) — irrelevant

**Etsy** — Has vintage clothing category. API available (public, well-documented). Some archive pieces but mixed in with actual vintage. Could be worth exploring with targeted brand searches.
- Priority: LOW-MEDIUM — API is easy but signal-to-noise ratio is poor.

**StockX** — Has apparel but focused on new/hype, not archive. Not relevant.

---

## Cross-Platform Aggregators & Tools

### Existing Tools
- **Gertje823/Vinted-Scraper** (121★) — Scrapes Vinted + Depop, stores in SQLite. Good reference implementation.
- **Giglium/vinted_scraper** (49★) — Clean Python package for Vinted. Pip installable. Use this.
- **kevinxo328/mercari-scraper** (3★) — Full Playwright + Prisma monorepo for Mercari. Good architecture reference.
- **arjunmahendra14/depop-grailed-scraper** — Personal scraper that monitors Depop + Grailed for specific items. Closest to what we're building.

### Commercial Services
- **Oxylabs/Bright Data** — Offer pre-built scraper APIs for many platforms. Expensive ($500+/mo) but handle anti-bot. Worth considering if a platform is too hard to scrape ourselves.
- **ScraperAPI/Scraping Fish** — Proxy services that handle fingerprinting. $50-150/mo for moderate volume.

### No True Multi-Platform Aggregator Exists
There is no open-source tool that searches across all resale platforms simultaneously. This is actually our competitive advantage — **Archive Arbitrage IS the aggregator**. The closest things are:
- Google Shopping (doesn't include most resale platforms)
- Lyst (fashion search engine, but retail-focused)
- **SearchJungle** — Claims to search Grailed, eBay, Poshmark, etc. but is a basic redirect tool, not a real scraper.

---

## Priority Ranking & Implementation Roadmap

### Phase 1: Quick Wins (1-2 weeks)
| # | Platform | Effort | Why |
|---|----------|--------|-----|
| 1 | **Depop** | Test existing scraper | Already built, just test + integrate |
| 2 | **Mercari US** | Test existing scraper | Already built, add stealth plugin |
| 3 | **Vinted** | `pip install vinted_scraper` | Easiest new platform, good EU deals |

### Phase 2: High-Value Builds (2-4 weeks)
| # | Platform | Effort | Why |
|---|----------|--------|-----|
| 4 | **eBay** | Deploy webhook + Browse API | Biggest inventory, official API, partially built |
| 5 | **Yahoo Japan (Buyee)** | New Playwright scraper | Best deals in the entire market |

### Phase 3: Premium Platforms (4-8 weeks)
| # | Platform | Effort | Why |
|---|----------|--------|-----|
| 6 | **The RealReal** | Playwright + stealth + proxies | High-value arbitrage opportunities |
| 7 | **Mercari Japan (Buyee)** | Extend Buyee scraper | Bundle with Yahoo Japan work |
| 8 | **Vestiaire Collective** | Playwright + DataDome bypass | Good inventory but harder to scrape |

### Skip / Deprioritize
- **Facebook Marketplace** — Not feasible for automated scraping
- **Hardly Ever Worn It** — Too small
- **Heresy** — Too small
- **Etsy** — Poor signal-to-noise

---

## Key Recommendations

1. **Test Depop + Mercari scrapers THIS WEEK** — they're already built and represent two massive platforms we're leaving money on the table by not using.

2. **Add Vinted in a day** — `pip install vinted_scraper`, write a thin integration layer matching our `BaseScraper` interface. Instant access to all of Europe.

3. **Deploy eBay production** — Follow the existing `EBAY_PRODUCTION_SETUP.md`. The Browse API is the cleanest integration path we have for any platform.

4. **Yahoo Japan via Buyee is the sleeper pick** — The price differentials are staggering. A Number (N)ine tee at ¥5,000 ($33) on Yahoo Japan sells for $400+ on Grailed. Build this and it pays for itself immediately.

5. **For anti-bot platforms (TRR, Vestiaire)** — Consider budgeting $50-100/mo for a residential proxy service (Bright Data Residential, IPRoyal). Makes Playwright scraping 10x more reliable.

6. **Our multi-platform aggregation IS the product** — No one else is doing this comprehensively for archive fashion. Each platform we add compounds the value.

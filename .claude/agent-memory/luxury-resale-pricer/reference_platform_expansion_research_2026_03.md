---
name: Platform Expansion Research March 2026
description: Comprehensive research on new scraping platforms for archive arbitrage — current coverage audit, 14 platform recommendations ranked by ROI, technical feasibility, arbitrage potential, and implementation roadmap
type: reference
---

# Platform Expansion Research — March 2026

## Current Platform Coverage

**Active scrapers (deal-finding / active listings):**
- Grailed (primary — Algolia API + HTML fallback, sold + active)
- eBay (HTML scraping via curl_cffi, active BIN + sold comps)
- Poshmark (HTML scraping, active listings)
- Depop (Playwright browser automation, API interception)
- Mercari US (Playwright + Webshare proxy)
- Mercari Japan (Playwright via jp.mercari.com)
- Vinted (cookie factory auth, multi-domain EU/US/UK)
- ShopGoodwill (API + HTML, currently disabled due to 500 errors)
- NoBids.net (eBay no-bid auction aggregator)
- Gem.app (Japanese consignment)

**Japan-specific scrapers (core/japan_integration.py):**
- Yahoo Auctions Japan (direct scraping + Buyee proxy)
- Mercari Japan (Buyee proxy + direct via Playwright)
- Rakuma/Rakuten (Buyee proxy via Playwright)

**Comp/pricing sources:**
- Grailed sold (primary comp source, 50% weight)
- eBay sold (40% weight)
- Poshmark active (10% weight, supply indicator)

**Total: 10 active listing sources + 3 Japan sources + 3 comp sources**

## Gap Analysis: What's Missing

The system has strong coverage on peer-to-peer platforms but is missing:
1. **Consignment platforms** (TheRealReal, Fashionphile) — institutional sellers who markdown aggressively
2. **European luxury platforms** (Vestiaire Collective) — the biggest luxury-specific marketplace outside Grailed
3. **Japanese retail chains** (2nd STREET, ZOZO Used) — corporate-priced inventory below market
4. **Auction houses** (Heritage, Catawiki) — occasional deep value on archival pieces
5. **Social/unstructured** (Facebook Marketplace, Instagram) — highest arbitrage but hardest to scrape
6. **Estate sale aggregators** (EstateSales.NET, MaxSold) — uninformed sellers, massive price gaps

# Archive Arbitrage - Fix Plan

## Current Issues

1. **Buyee 403 Errors** - Buyee is blocking all proxy traffic
2. **Mercari Direct API** - May have rate limiting or IP blocks
3. **Yahoo Auctions** - Working but limited to Buyee proxy
4. **No Results** - System not finding deals due to scraper failures

## Proposed Fixes

### Phase 1: Bypass Buyee (Immediate)
- [ ] Use direct Yahoo Auctions API/scraper instead of Buyee proxy
- [ ] Implement native Mercari Japan API (not through Buyee)
- [ ] Add request rotation with different user agents
- [ ] Implement exponential backoff for rate limiting

### Phase 2: Diversify Sources
- [ ] Add direct Yahoo Auctions JP scraping
- [ ] Add Suruga-ya for vintage items
- [ ] Add Mandarake for archive fashion
- [ ] Add Japanese eBay scraping

### Phase 3: Anti-Detection
- [ ] Rotate residential proxies more aggressively
- [ ] Add browser fingerprint randomization
- [ ] Implement session management
- [ ] Add human-like delays between requests

### Phase 4: Fallback Strategy
- [ ] Cache recent results to show when live scraping fails
- [ ] Alert on system health issues
- [ ] Manual deal entry capability

## Implementation Priority

**HIGH (Do Now):**
1. Fix Yahoo Auctions to not use Buyee
2. Ensure Mercari direct API works
3. Add better error handling

**MEDIUM (Next):**
4. Add more Japan sources
5. Improve proxy rotation
6. Add caching layer

**LOW (Later):**
7. Advanced anti-detection
8. Manual deal entry
9. System health dashboard

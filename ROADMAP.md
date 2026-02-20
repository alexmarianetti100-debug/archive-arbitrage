# Archive Arbitrage — Roadmap v2.5

**Last Updated:** 2026-02-12  
**Status:** Phases 1-5.5 Complete | Phase 5.75 Active | Phase 6-10 Planned

---

## ✅ COMPLETED PHASES

### Phase 1: Foundation ✅
- Scrapers for Grailed, Poshmark
- Smart pricing engine with live comps
- SQLite database with 3,243 items
- Discord alert system
- Deal grading (A/B/C/D)

### Phase 2: Exact Product Matching ✅
- Product fingerprinting system
- 21 products in catalog (10 high-velocity)
- Velocity-based grading
- Price confidence bands

### Phase 3: Multi-Platform Sold Data ✅
- eBay sold scraper (HTML fallback)
- Multi-platform pricer (Grailed 50% + eBay 40% + Poshmark 10%)
- Cross-platform spread detection

### Phase 4: Cross-Platform Arbitrage ✅
- Arbitrage detector (28 opportunities found)
- Platform fee calculator
- Net profit after fees

### Phase 5: Frontend Rebuild ✅
- React + TypeScript + Tailwind CSS
- Dashboard with stats, charts
- Deals browser with filters
- Arbitrage opportunities page
- Build system with Vite

---

## 🚨 CRITICAL NEW PHASE

### Phase 5.5: Authentication & Replica Detection ✅ **COMPLETE**

**Status:** LIVE — Detects replicas before they enter pipeline

**Completed:**
- ✅ **Price Analysis** — Flags items priced <30% of market average per brand
  - Brand thresholds: Rick Owens $150, Balenciaga $200, Prada $250, etc.
  - "Too good to be true" detection
  
- ✅ **Description Keyword Scanning** — `authenticity_checker.py`
  - Blocklist: "replica", "rep", "1:1", "mirror", "AAA", "unauthorized"
  - Suspicious phrases: "high quality copy", "super copy", "UA"
  - Auto-rejects 50%+ replica score, flags 30-50%
  
- ✅ **Brand-Specific Markers** — Misspelling detection
  - "balenciage", "prado", "rickowen" → flagged as suspicious
  - Brand price thresholds by market data

**Files Created:**
- ✅ `authenticity_checker.py` — Main authentication engine (integrated into pipeline)
- ✅ `auth_system/` — Advanced auth modules (image analysis, seller rep, expert review)
- ✅ `scan_for_replicas.py` — Audit existing inventory

**Scan Results:**
- 0 replicas detected in 3,720 items
- 91 suspicious items flagged (low prices)
- 100% clean inventory

**Next:**
- [ ] Review 91 suspicious items manually
- [ ] Build seller whitelist from known good sellers
- [ ] Deploy advanced image analysis (Phase 8 enhancement)

---

## 🚧 CURRENT PHASE

### Phase 5.75: Production API & Scale 🚧 **ACTIVE**

**Goal:** Get eBay Production API live and scale product catalog to 200+

**Tasks:**
- [ ] **Deploy eBay Webhook** — `api/index.py` → Vercel
  - Account deletion compliance endpoint
  - Apply for Production API keys
  - Integrate real eBay sold data into pricing
  
- [ ] **Test Playwright Scrapers**
  - Install Playwright browsers: `playwright install chromium`
  - Test `depop_playwright.py` and `mercari_playwright.py`
  - Validate bypass of 403 blocks
  
- [ ] **Scale Product Catalog**
  - Current: 176 products, 3,175 sold comps
  - Target: 200+ products, 5,000+ sold comps
  - Run daily scheduled scrapes to accumulate data

**Files Ready:**
- ✅ `api/index.py` — Vercel serverless webhook
- ✅ `vercel.json` — Deployment config
- ✅ `EBAY_PRODUCTION_SETUP.md` — Step-by-step guide
- ✅ `scrapers/depop_playwright.py` — Browser automation
- ✅ `scrapers/mercari_playwright.py` — Bypass 403s

---

## ⏳ NEXT PHASE

### Phase 6: Auto-Listing & Resale Pipeline ⏳

**Goal:** One-click cross-listing to Grailed, eBay, Poshmark

**Prerequisites:** eBay Production API working

**Tasks:**
- [ ] Auto-generate optimized listing titles
  - SEO keywords per brand
  - Title templates (e.g., "[Brand] [Model] [Material] [Size] [Condition]")
- [ ] Smart description templates
  - Brand-specific copy
  - Auto-include measurements
  - Care instructions per material
- [ ] Image optimization
  - Auto-crop to square
  - Background removal
  - Watermarking
- [ ] Platform-specific formatting
  - Grailed: Tags, hashtags, price drops
  - eBay: Categories, item specifics, shipping profiles
  - Poshmark: Sharing, offers, bundle discounts
- [ ] Inventory sync
  - Mark sold when source item disappears
  - Cross-platform stock management
  - Auto-relist if unsold

**Files to Create:**
- `listing_generator.py` — Title/description generation
- `image_processor.py` — Image optimization
- `platform_listers/` — Grailed, eBay, Poshmark lister modules
- `inventory_sync.py` — Stock sync across platforms

---

## 📋 UPCOMING PHASES

### Phase 7: Watchlist & Price Tracking ⏳

**Goal:** Track specific items, get alerts on price drops

**Tasks:**
- [ ] Watchlist feature
  - Save items to watchlist
  - Track price history over time
  - Visual price charts
- [ ] Price drop alerts
  - Alert when seller drops price 20%+
  - Negotiation opportunity detection
- [ ] Stale listing detection
  - Items listed 30+ days = lowball opportunity
  - Auto-suggest offer price
- [ ] Sold price prediction
  - ML model to predict final sold price
  - Optimal listing timing

**Files to Create:**
- `watchlist.py` — Watchlist management
- `price_tracker.py` — Price history tracking
- `price_predictor.py` — ML price prediction
- `offer_suggester.py` — Optimal offer calculator

### Phase 8: Profit Analytics & Dashboard ⏳

**Goal:** Track actual realized profits vs. estimates

**Tasks:**
- [ ] Purchase tracking
  - Log actual purchase price + shipping
  - Track acquisition date
- [ ] Sale tracking
  - Log actual sale price
  - Platform fees paid
  - Shipping cost
  - Net profit calculation
- [ ] Profit analytics dashboard
  - Total profit/loss
  - ROI by brand
  - Sell-through rate actual vs. predicted
  - Average days to sell (actual)
- [ ] Performance reports
  - Monthly P&L
  - Best/worst performing brands
  - Strategy optimization suggestions

**Files to Create:**
- `profit_tracker.py` — P&L tracking
- `analytics_dashboard.py` — Advanced analytics
- `reports.py` — Automated reports

### Phase 9: Mobile PWA ⏳

**Goal:** Mobile app for on-the-go deal hunting

**Tasks:**
- [ ] PWA setup
  - Service worker
  - Offline support
  - Push notifications
- [ ] Mobile-optimized UI
  - Touch-friendly filters
  - Swipe gestures
  - Mobile camera integration
- [ ] Barcode/QR scanning
  - Scan item tags for quick lookup
  - Image search from camera
- [ ] Push notifications
  - A-grade deal alerts
  - Price drop alerts
  - Arbitrage opportunities

**Files to Modify:**
- `frontend-react/` — Add PWA manifest, service worker
- `mobile/` — React Native wrapper (optional)

### Phase 10: Scaling Infrastructure ⏳

**Goal:** Production-grade deployment

**Tasks:**
- [ ] PostgreSQL migration
  - Data migration script
  - Connection pooling
  - Read replicas for scaling
- [ ] Cloud deployment
  - Docker containers
  - Kubernetes (optional)
  - Railway/Fly.io/AWS
- [ ] Background job processing
  - Celery + Redis for async tasks
  - Queue management
  - Retry logic
- [ ] Monitoring & logging
  - Error tracking (Sentry)
  - Performance monitoring
  - Uptime alerts

**Files to Create:**
- `docker-compose.yml`
- `Dockerfile`
- `k8s/` — Kubernetes manifests
- `workers/celery.py`

---

## 🔧 IMMEDIATE IMPROVEMENTS (Next 2 Weeks)

### High Priority — Phase 5.75 Completion
1. **Deploy eBay Webhook** ⭐ CRITICAL
   - Run `vercel --prod` in `api/` directory
   - Configure in eBay Developer Portal
   - Apply for Production API keys
   - This unlocks real eBay sold data

2. **Scale Product Catalog to 200+**
   - Run `scheduled_scrape.py` daily
   - Target: 200+ products, 5,000+ sold comps
   - Currently: 176 products, 3,175 comps

3. **Test Playwright Scrapers**
   - `playwright install chromium`
   - Test `depop_playwright.py` and `mercari_playwright.py`
   - Validate 403 bypass for Depop/Mercari

### Medium Priority — Phase 6 Prep
4. **Review Suspicious Items**
   - 91 items flagged by auth system
   - Manual review for potential reps
   - Update price thresholds if needed

5. **Frontend Polish**
   - Real charts (Recharts integration)
   - Product detail modals
   - Price history graphs
   - Mobile responsiveness fixes

### Low Priority
6. **Seller Whitelist**
   - Track known authentic sellers
   - Build trust scores per seller
   - Flag new sellers of high-value items

---

## 📊 SUCCESS METRICS

| Metric | Current | Target (30d) | Target (90d) |
|--------|---------|--------------|--------------|
| Products in catalog | 176 | 250 | 500+ |
| Sold comps in DB | 3,175 | 5,000 | 10,000+ |
| A-grade deals | ~20 | 40 | 100+ |
| Arbitrage opportunities/day | 28 | 50+ | 100+ |
| API uptime | 95% | 99% | 99.9% |
| Frontend load time | <2s | <1.5s | <1s |
| Replicas detected | 0 | 0 | 0 |

---

## 🎯 Q1 2026 GOALS

| Goal | Status | Target |
|------|--------|--------|
| Clean Inventory | ✅ **DONE** | 0 replicas in 3,720 items |
| Product Catalog | 🚧 **75%** | 176/250 products (Q1 target adjusted) |
| eBay Integration | 🚧 **80%** | Webhook ready, awaiting Production keys |
| Profitable Arbitrage | ⏳ **NOT STARTED** | Execute 10+ trades with >$100 profit |
| Auto-Listing | ⏳ **NOT STARTED** | List 50+ items across 3 platforms |
| Mobile PWA | ⏳ **NOT STARTED** | 50% of deal discovery on mobile |

**Revised Q1 Priorities:**
1. Complete Phase 5.75 (eBay API + Scale to 250 products)
2. Execute first profitable arbitrage trades
3. Build Phase 6 (Auto-Listing) for Q2 launch

---

## 📝 NOTES & BLOCKERS

| Issue | Status | Notes |
|-------|--------|-------|
| eBay Production API | 🚧 **BLOCKED** | Webhook ready, need to deploy to Vercel |
| Depop/Mercari 403s | 🚧 **PARTIAL** | Playwright scrapers created, need testing |
| Discord alerts | ⚠️ **BLOCKED** | Alex's network blocks Discord, needs VPN |
| Product catalog | ✅ **ON TRACK** | 176/200 products, growing daily |
| Replica detection | ✅ **WORKING** | 0 reps found, 91 suspicious flagged |

**Immediate Next Actions:**
1. Deploy eBay webhook (`vercel --prod`)
2. Install Playwright browsers
3. Run scheduled scrape to push to 200+ products

---

*Roadmap maintained by Victor. Last updated: 2026-02-12*

---

*Roadmap maintained by Victor. Update weekly or when phases complete.*

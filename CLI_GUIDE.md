# Archive Arbitrage — Complete CLI Reference

## Setup

```bash
cd ~/Desktop/CodingProjects/archive-arbitrage
source venv/bin/activate
```

Or use the shortcut script: `./run.sh [command]` (auto-activates venv)

---

## MAIN PIPELINE — `pipeline.py`

The central command hub. All core operations run through this.

---

### `pipeline.py run`

**What it does:** Runs the full pipeline end-to-end: scrape → qualify deals → send alerts for top finds.

```bash
# Default run (scrapes grailed + poshmark, qualifies, alerts on B+ deals)
python pipeline.py run

# Scrape only Rick Owens from eBay, max 20 items
python pipeline.py run --brand "rick owens" --sources ebay --max 20

# Scrape all brands from multiple sources
python pipeline.py run --all-brands --sources ebay,grailed,depop --max 15

# Only alert on A-grade deals
python pipeline.py run --min-grade A

# Preview mode — nothing saved, no alerts sent
python pipeline.py run --dry-run
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--brand BRAND` | all configured | Scrape only this brand |
| `--sources SOURCES` | `grailed,poshmark` | Comma-separated list of platforms |
| `--max N` | `10` | Max items to pull per source per brand |
| `--all-brands` | off | Scrape every configured brand (slow) |
| `--qualify-limit N` | `200` | Max items to run through qualification |
| `--min-grade {A,B,C}` | `B` | Minimum deal grade to trigger an alert |
| `--dry-run` | off | Preview only — no DB writes, no alerts |

---

### `pipeline.py scrape`

**What it does:** Pulls listings from resale platforms and saves them to the database. Does NOT qualify or alert — just collects data.

```bash
# Default scrape
python pipeline.py scrape

# Scrape Chrome Hearts from eBay only, max 50 items
python pipeline.py scrape --brand "chrome hearts" --source ebay --max 50

# Scrape from multiple sources
python pipeline.py scrape --sources ebay,depop,mercari

# Scrape everything from everywhere (slow)
python pipeline.py scrape --all-brands --all-sources
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--brand BRAND` | all configured | Specific brand to scrape |
| `--source SOURCE` | — | Single source: `grailed`, `poshmark`, `ebay`, `depop`, `mercari`, `shopgoodwill`, `nobids`, `gem` |
| `--sources SOURCES` | — | Comma-separated list of sources |
| `--all-sources` | off | Use every available source |
| `--max N` | — | Max items per source per brand |
| `--all-brands` | off | Scrape all configured brands |

**Available sources:** grailed, poshmark, ebay, depop, mercari, shopgoodwill, nobids, gem

---

### `pipeline.py qualify`

**What it does:** Runs deal qualification (Pass 2) on scraped items. Scores each item by profit margin, desirability, condition, authenticity, and assigns a grade (A/B/C).

```bash
# Qualify new items
python pipeline.py qualify

# Qualify only Raf Simons items and send alerts for good ones
python pipeline.py qualify --brand "raf simons" --alert

# Re-score everything with stricter thresholds
python pipeline.py qualify --requalify --min-margin 0.30 --min-profit 50

# Preview without saving
python pipeline.py qualify --dry-run
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--brand BRAND` | all | Filter by brand |
| `--min-margin N` | `0.20` | Minimum profit margin (0.20 = 20%) |
| `--min-profit N` | `$20` | Minimum dollar profit |
| `--limit N` | — | Max items to qualify |
| `--dry-run` | off | Don't update the database |
| `--alert` | off | Send Discord alerts for A/B grade deals |
| `--requalify` | off | Re-score ALL items, not just new ones |

---

### `pipeline.py deals`

**What it does:** Displays qualified deals from the database, sorted by grade. Use this to see what's been found.

```bash
# Show all deals
python pipeline.py deals

# Show only A-grade deals
python pipeline.py deals --grade A

# Show Rick Owens deals, top 20
python pipeline.py deals --brand "rick owens" --limit 20
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--grade {A,B,C}` | all | Show only this grade |
| `--brand BRAND` | all | Filter by brand |
| `--limit N` | — | Number of deals to display |

---

### `pipeline.py list`

**What it does:** Shows raw items in the database (not just qualified deals — everything that's been scraped).

```bash
python pipeline.py list
python pipeline.py list --brand "margiela" --limit 50
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--brand BRAND` | all | Filter by brand |
| `--limit N` | — | Number of items to show |

---

### `pipeline.py stats`

**What it does:** Displays database statistics — total items, brand breakdown, source breakdown, average margins.

```bash
python pipeline.py stats
```

No parameters.

---

### `pipeline.py init`

**What it does:** Creates or resets the database tables. Run this once on a fresh setup, or to start over.

```bash
python pipeline.py init
```

No parameters. **Warning:** This resets your database.

---

### `pipeline.py fingerprint`

**What it does:** Generates perceptual image hashes for items in the database. Used for duplicate detection and replica scanning.

```bash
python pipeline.py fingerprint
python pipeline.py fingerprint --brand "rick owens" --limit 100
python pipeline.py fingerprint --dry-run
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--brand BRAND` | all | Filter by brand |
| `--limit N` | — | Max items to process |
| `--dry-run` | off | Don't update the database |

---

### `pipeline.py serve`

**What it does:** Starts the Flask API server that powers the web frontend.

```bash
python pipeline.py serve
```

No parameters. Runs on the default Flask port (5000).

---

## STANDALONE TOOLS

These are independent scripts in the project root. Each does one specific job.

---

### `auction_snipe.py`

**What it does:** Finds eBay auctions ending soon where the current bid is low — potential snipe opportunities on archive pieces.

```bash
# Default: all brands, ending within 12 hours, under $500
python auction_snipe.py

# Rick Owens auctions ending in 6 hours, under $300
python auction_snipe.py --brand "rick owens" --hours 6 --max-price 300

# Limit results per brand
python auction_snipe.py --max-per-brand 5
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--brand BRAND` | all configured | Specific brand to search |
| `--hours N` | `12` | Only auctions ending within N hours |
| `--max-price N` | `$500` | Max current bid to include |
| `--max-per-brand N` | — | Cap results per brand |

---

### `detect_arbitrage.py`

**What it does:** Finds cross-platform arbitrage — the same item (or very similar) listed on different platforms at different prices.

```bash
# Default scan
python detect_arbitrage.py

# Chrome Hearts only, at least $50 profit
python detect_arbitrage.py --brand "chrome hearts" --min-profit 50

# Only authenticated items, high margin
python detect_arbitrage.py --authenticated-only --min-margin 0.40
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--brand BRAND` | all | Filter by brand |
| `--min-profit N` | — | Minimum dollar profit to flag |
| `--min-margin N` | — | Minimum percentage margin to flag |
| `--max-items N` | — | Max items to analyze |
| `--authenticated-only` | off | Only include items with authentication |

---

### `gap_hunter.py`

**What it does:** Continuously hunts for pricing gaps — items listed significantly below their market value. Scrapes, scores, and sends alerts to Telegram/Discord when it finds deals.

```bash
# Run continuously (loops forever)
python gap_hunter.py

# Single pass then exit
python gap_hunter.py --once
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--once` | off | Run one cycle then exit (instead of looping) |

---

### `realtime_monitor.py`

**What it does:** Real-time monitoring loop. Continuously checks sources for new listings, scores them, and alerts on finds.

```bash
# Run continuously
python realtime_monitor.py

# Single cycle then exit
python realtime_monitor.py --once

# Limit brands per cycle (faster cycles)
python realtime_monitor.py --brands 5
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--once` | off | Run one cycle then exit |
| `--brands N` | — | Max brands to check per cycle |

---

### `scan_for_replicas.py`

**What it does:** Scans all items in the database and flags potential replicas/fakes based on pricing anomalies and authenticity signals.

```bash
python scan_for_replicas.py
```

No parameters. Runs and outputs results immediately.

---

### `telegram_bot.py`

**What it does:** Starts the @ArchiveArbitrageBot Telegram bot. Handles subscriber management, payment verification, and deal delivery to paying subscribers.

```bash
python telegram_bot.py
```

No parameters. Runs continuously — keep it running in a terminal or background process.

---

### `trend_engine.py`

**What it does:** Analyzes market trends by pulling signals from Grailed velocity, Reddit, Google Trends, and editorial sources. Used internally by gap_hunter.

```bash
python trend_engine.py
```

No parameters.

---

### `stripe_billing.py`

**What it does:** Handles Stripe webhook events for subscription billing. Usually runs as part of the API server, not standalone.

```bash
# Typically not run standalone — it's imported by telegram_bot.py
```

---

## UTILITY SCRIPTS (in `tools/`)

```bash
# Generate product catalog
python tools/build_product_catalog.py

# Set up proxy configuration
python tools/setup_proxies.py

# Update volume metrics for items
python tools/update_volume_metrics.py

# Debug scraping issues
python tools/debug_scrape.py

# Re-qualify items with exact matching
python tools/requalify_exact.py

# Monitor Twitter/X for signals
python tools/twitter_monitor.py

# Handle eBay webhook events
python tools/ebay_webhook.py
```

---

## MOVED SCRAPERS (in `scrapers/`)

```bash
# Full scrape (all brands, all sources)
python scrapers/full_scrape.py

# Scheduled scrape (stateful, remembers where it left off)
python scrapers/scheduled_scrape.py

# Smart scrape (auto brand/category detection)
python scrapers/smart_scrape.py

# Reddit scraper
python scrapers/reddit_scraper.py

# Generic scrape runner
python scrapers/run_scraper.py
```

---

## QUICK REFERENCE

| I want to... | Command |
|--------------|---------|
| Run everything (scrape + qualify + alert) | `python pipeline.py run` |
| Just scrape eBay for Rick Owens | `python pipeline.py scrape --brand "rick owens" --source ebay` |
| See the best deals found | `python pipeline.py deals --grade A` |
| Check database stats | `python pipeline.py stats` |
| Find auctions ending soon | `python auction_snipe.py --hours 6` |
| Find cross-platform price gaps | `python detect_arbitrage.py` |
| Run the deal hunter (continuous) | `python gap_hunter.py` |
| Run real-time monitoring | `python realtime_monitor.py` |
| Scan for fakes in the DB | `python scan_for_replicas.py` |
| Start the Telegram bot | `python telegram_bot.py` |
| Start the web API | `python pipeline.py serve` |
| Initialize fresh database | `python pipeline.py init` |
| Preview without saving anything | `python pipeline.py run --dry-run` |
| Send a test alert | `python core/alerts.py --test` |
| Send daily summary | `python core/alerts.py --summary` |

---

## PROJECT STRUCTURE

```
archive-arbitrage/
├── pipeline.py              # Main CLI (all pipeline commands)
├── run.py                   # Flask app entry point
├── run.sh                   # Shell runner (auto-activates venv)
├── models.py                # Database models
├── telegram_bot.py          # Telegram bot
├── gap_hunter.py            # Deal hunter (continuous)
├── realtime_monitor.py      # Real-time monitor
├── auction_snipe.py         # eBay auction sniper
├── detect_arbitrage.py      # Cross-platform arbitrage finder
├── scan_for_replicas.py     # Fake/replica scanner
├── trend_engine.py          # Market trend analysis
├── stripe_billing.py        # Stripe webhook handler
│
├── core/                    # Business logic library
│   ├── alerts.py            # Alert system
│   ├── qualify.py           # Deal qualification engine
│   ├── deal_quality.py      # Deal scoring
│   ├── desirability.py      # Desirability scoring
│   ├── authenticity_checker.py  # Auth v1
│   ├── authenticity_v2.py   # Auth v2
│   ├── condition_parser.py  # Condition parsing
│   ├── season_detector.py   # Season detection
│   ├── size_scorer.py       # Size scoring
│   ├── line_detection.py    # Product line detection
│   └── discord_alerts.py    # Discord alert delivery
│
├── scrapers/                # All scraping logic
├── api/                     # REST API routes & services
├── db/                      # Database layer
├── ml/                      # Machine learning models
├── auth_system/             # Full auth system
├── tools/                   # Utility scripts
├── tests/                   # Test files
├── docs/                    # Planning & research docs
├── marketing/               # Marketing assets & posts
├── frontend-react/          # React frontend (current)
├── frontend-dist/           # Built frontend
├── frontend-legacy/         # Old frontend
├── trend_sources/           # Trend data sources
├── workers/                 # Background workers
├── data/                    # Data files
├── logs/                    # Log files
└── migrations/              # DB migrations
```

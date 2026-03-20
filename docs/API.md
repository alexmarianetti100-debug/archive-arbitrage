# Archive Arbitrage API Documentation

## Overview

Archive Arbitrage is a fashion resale arbitrage tool that helps resellers find underpriced archive/luxury items across multiple platforms.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Gap Hunter    │────▶│  Pricing Engine │────▶│  Alert Manager  │
│   (Main Loop)   │     │  (Cache/Comps)  │     │ (Discord/Whop)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Scrapers     │     │   Data Manager  │     │  Health Monitor │
│ (Multi-platform)│     │(Compression/Pool)│     │  (Metrics/Alerts)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Core Modules

### gap_hunter.py
Main execution loop that coordinates scraping, pricing, and alerting.

**Key Functions:**
- `run_cycle()` - Execute one scraping cycle
- `process_target()` - Process a single target
- `send_deal_alert()` - Send deal notifications

**CLI Arguments:**
```bash
python gap_hunter.py --once          # Run single cycle
python gap_hunter.py --cache-stats   # Show cache statistics
python gap_hunter.py --cache-flush   # Flush expired cache entries
```

### core/pricing_engine.py
Manages sold price caching and statistics.

**Classes:**
- `PricingEngine` - Main pricing cache manager
- `CacheEntry` - Individual cache entry
- `CacheStats` - Cache statistics

**Usage:**
```python
from core.pricing_engine import PricingEngine

engine = PricingEngine()
price = engine.get_sold_price("nike air max")
engine.set_price("nike air max", 120.0, source="ebay")
```

### core/monitoring.py
Health monitoring and metrics tracking.

**Functions:**
- `record_scraper_request()` - Record scraper performance
- `get_health_status()` - Get overall health
- `print_dashboard()` - Display health dashboard

**Usage:**
```python
from core.monitoring import record_scraper_request, print_dashboard

record_scraper_request("ebay", success=True, latency=1.2)
print_dashboard()
```

### core/exceptions.py
Custom exception classes for error handling.

**Exception Types:**
- `NetworkError` - Connection issues (retryable)
- `TimeoutError` - Request timeouts (retryable)
- `RateLimitError` - Rate limiting (retryable)
- `ParseError` - HTML/JSON parsing errors
- `AuthError` - Authentication failures

## Scrapers

### Base Scraper
All scrapers inherit from `BaseScraper` in `scrapers/base.py`.

**Common Interface:**
```python
async with ScraperClass() as scraper:
    items = await scraper.search("query", max_results=10)
```

### Available Scrapers

| Scraper | File | Status | Features |
|---------|------|--------|----------|
| Grailed | `grailed.py` | ✅ Active | API + fallback, health tracking |
| Poshmark | `poshmark.py` | ✅ Active | Multi-selector, health tracking |
| eBay | `ebay.py` | ✅ Active | 45s timeout, rate limiting |
| Vinted | `vinted_fixed.py` | ✅ Active | Cookie factory, domain rotation |
| Depop | `depop.py` | ⚠️ Limited | Playwright (macOS issues) |

### Health Status

Each scraper provides health status:
```python
from scrapers.ebay import EbayScraper

health = EbayScraper.get_health_status()
print(health["healthy"])  # True/False
print(health["success_rate"])  # 0.0-1.0
```

## Configuration

### Environment Variables

Create `.env` file:
```bash
# Required
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=-100...

# Optional
GRAILED_ALGOLIA_API_KEY=a3a4de2e05d9e9b463911705fb6323ad
PROXY_HOST=p.webshare.io
PROXY_PORT=10000
PROXY_USERNAME=...
PROXY_PASSWORD=...

# Feature Flags
ENABLE_VINTED=true
ENABLE_EBAY=true
ENABLE_POSHMARK=true
```

### Database

SQLite database auto-created in `data/`:
- `gaps.db` - Discovered price gaps
- `listings.db` - Cached listings
- `sold_cache.json` - Sold price cache

## Monitoring

### Health Dashboard

Run health check:
```bash
python health_check.py
```

Output:
```
📊 SCRAPER HEALTH DASHBOARD
============================
Overall Status: HEALTHY
Healthy: 4/4 scrapers

✅ GRAILED
   Success Rate: 100.0%
   Requests: 50 (✓50 ✗0)
   Avg Latency: 550ms

✅ EBAY
   Success Rate: 95.0%
   Requests: 20 (✓19 ✗1)
   Avg Latency: 1200ms
```

### Metrics

Metrics saved to `data/metrics/`:
- Rotated every 24 hours
- JSON format
- Includes all scraper performance

### Alerts

Alerts trigger on:
- 5 consecutive failures
- 50% failure rate
- Configurable thresholds

## Troubleshooting

### Common Issues

**Issue: Scraper returns 0 items**
- Check health status: `python health_check.py`
- Verify proxy settings in `.env`
- Check scraper-specific logs in `logs/`

**Issue: Database locked**
- Restart service
- Check for zombie processes
- Verify connection pool settings

**Issue: Memory usage high**
- Run data pruning: `python gap_hunter.py --prune`
- Check cache size: `python gap_hunter.py --cache-stats`
- Restart service if needed

### Log Locations

- `logs/archive_arbitrage.log` - All logs
- `logs/errors.log` - Errors only
- `logs/scrapers.log` - Scraper-specific

## API Reference

See module docstrings for detailed API documentation:
```bash
python -m pydoc core.pricing_engine
python -m pydoc scrapers.ebay
```

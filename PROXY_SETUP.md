# Japan Arbitrage - Proxy Setup Guide

## Quick Start

### 1. Configure Your Webshare Proxies

Edit `data/proxy_config.json` with your Webshare credentials:

```json
{
  "proxies": [
    {
      "id": "webshare-1",
      "host": "p.webshare.io",
      "port": 80,
      "username": "YOUR_USERNAME",
      "password": "YOUR_PASSWORD",
      "country": "JP",
      "type": "http"
    }
  ],
  "rotation_mode": "per_domain",
  "max_concurrent": 2,
  "headful": true,
  "retry_attempts": 3
}
```

Get your credentials from Webshare dashboard:
- Go to https://dashboard.webshare.io/
- Copy your proxy credentials
- Paste into the JSON file

### 2. Test the Setup

```bash
cd ~/Desktop/codingprojects/archive-arbitrage
source venv/bin/activate

# Test proxy connection
python3 -c "
from core.proxy_pool import get_proxy_pool
pool = get_proxy_pool()
print(f'Loaded {len(pool.proxies)} proxies')
print(pool.get_stats())
"

# Test Mercari scraping
python3 core/robust_scraper.py
```

### 3. Update Japan Integration

The system will automatically use:
1. **Yahoo Auctions** - No proxy needed (works great)
2. **Mercari** - Stealth + proxy first, fallback to direct API
3. **Rakuma** - Stealth + proxy (when implemented)

## How It Works

### Proxy Rotation
- Proxies rotate per-domain (consistent for same site)
- On failure, automatically tries next proxy
- Tracks success/failure rates per proxy

### Stealth Features
- Headful browser (visible window) - harder to detect
- Randomized user agents and viewports
- Human-like delays and scrolling
- Blocks heavy resources (images, fonts) for speed

### Fallback Strategy
1. Try stealth scraping with proxy
2. If blocked, try next proxy (up to 3 retries)
3. If all proxies fail, fallback to direct Mercari API
4. If all methods fail, skip and continue

## Cost Optimization

### Current Usage
- **Yahoo Auctions**: Free, no proxy needed
- **Mercari Stealth**: Uses proxy only when needed
- **Mercari Direct API**: Free, no proxy needed (fallback)

### Proxy Budget Tips
- Start with 3-5 proxies from Webshare
- Use rotation to distribute load
- Monitor success rates and disable failing proxies
- Scale up only if you're hitting rate limits

## Monitoring

Check proxy stats:
```python
from core.proxy_pool import get_proxy_pool
pool = get_proxy_pool()
print(pool.get_stats())
```

Expected output:
```python
{
  'total': 3,
  'active': 3,
  'proxies': [
    {'id': 'webshare-1', 'country': 'JP', 'success': 15, 'failures': 2, 'active': True},
    {'id': 'webshare-2', 'country': 'JP', 'success': 12, 'failures': 1, 'active': True},
    ...
  ]
}
```

## Troubleshooting

### "All proxies marked inactive"
- Check your Webshare credentials
- Verify proxy IPs are not blocked
- Try rotating to new proxy IPs

### "Playwright not available"
```bash
pip install playwright
python3 -m playwright install firefox
```

### "mercapi not available"
```bash
pip install mercapi
```

### Browser crashes on macOS
- Use Firefox (more stable than Chromium on macOS)
- Ensure you have enough RAM (close other apps)
- Try headful mode (set `"headful": true` in config)

## Next Steps

1. Add your Webshare credentials to `data/proxy_config.json`
2. Run a test to verify everything works
3. Start the main gap_hunter to begin scanning
4. Monitor logs for proxy performance

## Architecture

```
Japan Arbitrage System
├── Yahoo Auctions (direct, no proxy)
├── Mercari
│   ├── Stealth + Proxy (primary)
│   └── Direct API (fallback)
└── Rakuma (stealth + proxy)

Proxy Pool
├── Rotates per domain
├── Retries on failure
└── Tracks performance
```

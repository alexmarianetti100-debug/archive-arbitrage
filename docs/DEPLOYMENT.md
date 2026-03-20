# Archive Arbitrage Deployment Guide

## Prerequisites

- Python 3.11+
- macOS or Linux (Windows partially supported)
- 4GB RAM minimum
- 10GB disk space

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd archive-arbitrage
```

### 2. Create Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright (Optional)

For Depop scraper:
```bash
playwright install chromium
```

Note: Playwright may have issues on macOS Sonoma with Apple Silicon.

## Configuration

### 1. Environment Variables

Copy example file:
```bash
cp .env.example .env
```

Edit `.env` with your settings:
```bash
# Required for alerts
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=-100...

# Required for Whop (if using)
WHOP_API_KEY=your_whop_key
WHOP_EXPERIENCE_ID=your_experience_id

# Proxy (recommended)
PROXY_HOST=p.webshare.io
PROXY_PORT=10000
PROXY_USERNAME=your_username
PROXY_PASSWORD=your_password

# Grailed API (optional, has defaults)
GRAILED_ALGOLIA_API_KEY=a3a4de2e05d9e9b463911705fb6323ad

# Feature flags
ENABLE_VINTED=true
ENABLE_EBAY=true
ENABLE_POSHMARK=true
ENABLE_DEPOP=false  # Set true if Playwright works
```

### 2. Validate Setup

Run validation script:
```bash
./validate_setup.sh
```

Or manually:
```bash
python -c "from core.dependencies import check_all; check_all()"
```

### 3. Database Setup

Database files auto-create on first run:
```bash
mkdir -p data
python gap_hunter.py --once
```

## Running the Service

### Development Mode

Single cycle:
```bash
python gap_hunter.py --once
```

Continuous mode:
```bash
python gap_hunter.py
```

### Production Mode

Using nohup:
```bash
nohup python gap_hunter.py > logs/service.log 2>&1 &
echo $! > gap_hunter.pid
```

Using systemd (Linux):
```bash
sudo cp systemd/archive-arbitrage.service /etc/systemd/system/
sudo systemctl enable archive-arbitrage
sudo systemctl start archive-arbitrage
sudo systemctl status archive-arbitrage
```

### Docker (Optional)

Build:
```bash
docker build -t archive-arbitrage .
```

Run:
```bash
docker run -d \
  --name archive-arbitrage \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  archive-arbitrage
```

## Health Monitoring

### Check Status

```bash
python health_check.py
```

### View Dashboard

```bash
python status_dashboard.py
```

### Check Logs

```bash
tail -f logs/archive_arbitrage.log
tail -f logs/errors.log
```

## Maintenance

### Daily

- Check health dashboard
- Review error logs
- Monitor disk space

### Weekly

- Run cache flush:
  ```bash
  python gap_hunter.py --cache-flush
  ```
- Review metrics
- Check for updates

### Monthly

- Prune old data:
  ```bash
  python gap_hunter.py --prune
  ```
- Archive old logs
- Review performance

## Backup

### Data Backup

```bash
# Backup data directory
tar -czf backup-$(date +%Y%m%d).tar.gz data/

# Backup specific files
cp data/gaps.db backups/gaps-$(date +%Y%m%d).db
```

### Automated Backup

Add to crontab:
```bash
0 2 * * * cd /path/to/archive-arbitrage && tar -czf backups/data-$(date +\%Y\%m\%d).tar.gz data/
```

## Troubleshooting

### Service Won't Start

1. Check Python version:
   ```bash
   python --version  # Should be 3.11+
   ```

2. Check dependencies:
   ```bash
   pip list | grep -E "httpx|bs4|pytest"
   ```

3. Check .env file exists:
   ```bash
   ls -la .env
   ```

### High Memory Usage

1. Check cache size:
   ```bash
   python gap_hunter.py --cache-stats
   ```

2. Flush cache:
   ```bash
   python gap_hunter.py --cache-flush
   ```

3. Restart service

### Database Locked

1. Find and kill processes:
   ```bash
   lsof data/*.db
   kill -9 <pid>
   ```

2. Restart service

### Scraper Failures

1. Check health:
   ```bash
   python health_check.py
   ```

2. Test individual scraper:
   ```bash
   python -c "
   import asyncio
   from scrapers.ebay import EbayScraper
   async def test():
       async with EbayScraper() as s:
           items = await s.search('nike', max_results=3)
           print(f'Found {len(items)} items')
   asyncio.run(test())
   "
   ```

## Updates

### Update Code

```bash
git pull origin main
```

### Update Dependencies

```bash
pip install -r requirements.txt --upgrade
```

### Database Migrations

If schema changes:
```bash
python scripts/migrate_db.py
```

## Security

### File Permissions

```bash
chmod 600 .env
chmod 700 data/
chmod 755 logs/
```

### Secrets Management

Never commit:
- `.env` file
- `data/` directory
- `*.key` files
- `secrets.json`

Add to `.gitignore`:
```
.env
.env.local
data/
*.key
secrets.json
```

## Support

For issues:
1. Check logs in `logs/`
2. Run health check: `python health_check.py`
3. Review documentation in `docs/`
4. Create issue with logs attached

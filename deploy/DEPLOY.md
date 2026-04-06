# Archive Arbitrage — VPS Deployment Guide

## Prerequisites

- VPS with 2+ GB RAM (Hetzner CX22 or DigitalOcean Basic $12/mo recommended)
- Ubuntu 22.04+ or Debian 12+
- SSH access

## 1. Install Docker

```bash
# Install Docker + Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in for group change to take effect
```

## 2. Clone and configure

```bash
cd /opt
git clone <your-repo-url> archive-arbitrage
cd archive-arbitrage

# Create .env from template
cp .env.example .env
nano .env  # Fill in your secrets:
           # TELEGRAM_BOT_TOKEN, STRIPE_SECRET_KEY,
           # DISCORD_BOT_TOKEN, proxy creds, etc.
```

## 3. Build and start

```bash
# Build images (first time takes ~5 min for Playwright/Chromium)
docker compose build

# Start all services
docker compose up -d

# Check status
docker compose ps
docker compose logs -f gap-hunter
```

## 4. Install systemd service (auto-start on boot)

```bash
sudo cp deploy/archive-arbitrage.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable archive-arbitrage
sudo systemctl start archive-arbitrage
```

## 5. Verify

```bash
# Check gap-hunter is running
docker compose logs --tail 50 gap-hunter

# Check API health
curl http://localhost:8000/api/stats

# Check scheduler cron jobs
docker compose exec scheduler crontab -l

# View cron output
docker compose exec scheduler tail -f /app/logs/cron.log
```

## Common Operations

```bash
# View live logs
docker compose logs -f gap-hunter

# Run a one-shot gap hunt
docker compose run --rm gap-hunter gap_hunter.py

# Run pipeline manually
docker compose run --rm gap-hunter pipeline.py run

# Restart after code update
git pull
docker compose build
docker compose up -d

# Backup database
docker compose cp gap-hunter:/app/data/archive.db ./backup-$(date +%Y%m%d).db

# Shell into container for debugging
docker compose exec gap-hunter bash
```

## Resource Usage

| Service     | RAM    | CPU  | Disk         |
|-------------|--------|------|--------------|
| gap-hunter  | ~512MB | Low  | Minimal      |
| scheduler   | ~256MB | Low  | Minimal      |
| api         | ~128MB | Low  | Minimal      |
| **Image**   |        |      | ~1.5GB (Chromium) |
| **Data vol**|        |      | ~100MB (grows) |

## Alternative: Host-Level Cron (simpler)

Instead of running the scheduler container, use the host's crontab to trigger one-shot runs:

```bash
# Stop the scheduler container
docker compose stop scheduler

# Edit host crontab
crontab -e
```

Add these lines:
```cron
# Gap hunter: every 2 hours
0 */2 * * * cd /opt/archive-arbitrage && docker compose run --rm gap-hunter gap_hunter.py >> /var/log/archive-cron.log 2>&1

# Scheduled scrape: every 4 hours
30 1,5,9,13,17,21 * * * cd /opt/archive-arbitrage && docker compose run --rm gap-hunter scrapers/scheduled_scrape.py >> /var/log/archive-cron.log 2>&1

# Trend engine: daily at 3 AM UTC
0 3 * * * cd /opt/archive-arbitrage && docker compose run --rm gap-hunter trend_engine.py >> /var/log/archive-cron.log 2>&1
```

This approach is easier to debug (`/var/log/archive-cron.log`) and doesn't require the env-passthrough workaround that container cron needs.

## Monitoring

Check that deals are flowing:
```bash
# Recent deal count
docker compose exec api curl -s localhost:8000/api/stats | python3 -m json.tool

# Disk usage
docker system df
```

Set up a simple uptime check by hitting `http://<your-vps-ip>:8000/api/stats` from an external monitor (UptimeRobot, etc.).

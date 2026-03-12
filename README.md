# Archive Arbitrage

Automated archive fashion arbitrage platform. Scrapes multiple marketplaces for underpriced designer pieces, calculates real market pricing using live sold comps, detects iconic collections, and surfaces profitable opportunities.

## 🚀 Quick Start (New Setup)

```bash
# 1. Clone and enter directory
cd archive-arbitrage

# 2. Run setup validation
./validate_setup.sh

# 3. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 4. Configure environment
cp .env.example .env
# Edit .env with your actual credentials

# 5. Run dependency check
python3 core/dependencies.py

# 6. Test with single cycle
python3 gap_hunter.py --once
```

## 📋 Prerequisites

- Python 3.11+
- pip
- Virtual environment (recommended)
- Playwright browsers (auto-installed)

## 🔧 Installation

### Option 1: Standard Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Verify installation
python3 core/dependencies.py
```

### Option 2: Development Installation

```bash
# Install with development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Or install as editable package
pip install -e ".[dev]"
```

## ⚙️ Configuration

### Quick Setup

1. Copy the example environment file:
   ```bash
   cp .env.example .env.local
   ```

2. Edit `.env.local` and fill in your credentials (see below for details)

3. **Never commit `.env.local` to git!** It's already in `.gitignore`.

### Required Configuration

| Variable | Source | Description |
|----------|--------|-------------|
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/botfather) | Telegram bot token for alerts |
| `DATABASE_URL` | Default provided | SQLite database path |

### Optional Configuration

| Variable | Source | Description |
|----------|--------|-------------|
| `STRIPE_SECRET_KEY` | [Stripe Dashboard](https://dashboard.stripe.com) | Payment processing |
| `STRIPE_PRICE_ID` | Stripe Dashboard | Subscription price ID |
| `DISCORD_WEBHOOK_URL` | Discord Channel Settings | Discord alerts |
| `WHOP_API_KEY` | [Whop Dashboard](https://whop.com/dashboard) | Community posts |
| `PROXY_USERNAME/PASSWORD` | [Webshare](https://www.webshare.io/) | Vinted proxy |

### Configuration Validation

Validate your configuration:
```bash
# Check all environment variables
python3 -c "from core.config import ConfigValidator; ConfigValidator().validate()"

# Show configuration help
python3 gap_hunter.py --help-config
```

### Security Notes

- **Never commit `.env.local` to git** - it contains secrets
- Use `.env.example` as a template only
- Rotate secrets regularly
- Use Stripe test keys for development (`sk_test_...`)
- Use separate Telegram bot for testing

## 🎯 Running the Service

### Gap Hunter (Main Service)

```bash
# Run one cycle (good for testing)
python3 gap_hunter.py --once

# Run continuously (production)
python3 gap_hunter.py

# Filter by brand
python3 gap_hunter.py --brand "rick owens"

# Custom queries
python3 gap_hunter.py --query "rick owens dunks,raf simons bomber"

# Limit targets per cycle
python3 gap_hunter.py --max-targets 10
```

### Legacy Pipeline

```bash
# Full pipeline: scrape → qualify → alerts
python pipeline.py run

# Just scrape
python pipeline.py scrape

# Start API server
python pipeline.py serve
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/test_auth_system.py

# Validate dependencies
python3 core/dependencies.py

# Run setup validation
./validate_setup.sh
```

## 📁 Project Structure

```
archive-arbitrage/
├── gap_hunter.py           # Main service (new)
├── pipeline.py             # Legacy pipeline
├── requirements.txt        # Production dependencies
├── requirements-dev.txt    # Development dependencies
├── setup.py               # Package setup
├── .env.example           # Environment template
├── validate_setup.sh      # Setup validator
│
├── core/                  # Core business logic
│   ├── dependencies.py    # Dependency validation
│   ├── authenticity_v2.py # Authentication system
│   ├── deal_quality.py    # Deal scoring
│   ├── pricing_engine.py  # Price calculations
│   └── whop_alerts.py     # Whop integration
│
├── scrapers/              # Marketplace scrapers
│   ├── grailed.py         # Grailed (working)
│   ├── poshmark.py        # Poshmark (working)
│   ├── ebay.py            # eBay (working)
│   ├── depop.py           # Depop (Playwright)
│   ├── vinted.py          # Vinted (needs fix)
│   └── base.py            # Base scraper class
│
├── db/                    # Database models
├── api/                   # REST API
├── frontend-react/        # Web frontend
├── tests/                 # Test suite
└── data/                  # Local data storage
```

## 🔍 Dependency Validation

The service validates dependencies on startup. If something is missing:

```bash
# Check all dependencies
python3 core/dependencies.py

# Check only critical (required) dependencies
python3 core/dependencies.py --critical-only

# Check development dependencies too
python3 core/dependencies.py --dev
```

## 🐛 Troubleshooting

### Missing Dependencies

```bash
# If you see "❌ CRITICAL DEPENDENCIES MISSING"
pip install -r requirements.txt
playwright install chromium
```

### Vinted Not Working

Vinted scraper is currently broken. The service will skip it automatically.
See `BACKLOG.md` for planned fixes.

### Database Issues

```bash
# Reset database
rm data/archive.db
python3 -c "from db.sqlite_models import init_db; init_db()"
```

### Permission Errors

```bash
# Make scripts executable
chmod +x validate_setup.sh
chmod +x run.sh
chmod +x stop.sh
```

## 📊 Current Status

### ✅ Working
- **Grailed Scraper** - Active listings + sold comps via Algolia API
- **Poshmark Scraper** - HTML scraping with CSS selectors
- **eBay Scraper** - API + HTML fallback
- **Depop Scraper** - Playwright browser automation
- **Authentication System** - Multi-signal fake detection
- **Deal Quality Scoring** - 0-100 score with fire levels
- **Telegram Alerts** - Subscriber management + deal alerts
- **Discord Alerts** - Rich embeds with tiers
- **Whop Integration** - Deal posting to community

### ⚠️ Partially Working
- **Vinted Scraper** - All domains returning 0 items (needs fix)

### ❌ Removed
- **Mercari** - Blocked by Cloudflare Enterprise
- **ShopGoodwill** - API consistently returns 500

## 🛠️ Development

### Code Quality

```bash
# Format code
black .

# Lint
flake8 .

# Type check
mypy .

# Run all checks
black . && flake8 . && mypy .
```

### Adding New Dependencies

1. Add to `requirements.txt` with pinned version
2. Update `core/dependencies.py` REQUIRED_DEPENDENCIES list
3. Document in README
4. Test with `python3 core/dependencies.py`

## 📚 Documentation

- `CLI_GUIDE.md` - Command-line interface guide
- `BACKLOG.md` - Feature backlog and roadmap
- `FIX_PLAN.md` - Current fix plan (Phase 1-6)
- `docs/` - Additional documentation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Run linting: `black . && flake8 .`
6. Submit a pull request

## 📝 License

Private - All rights reserved.

## 🆘 Support

For issues or questions:
1. Check `BACKLOG.md` for known issues
2. Run `python3 core/dependencies.py` to verify setup
3. Check logs in `data/` directory
4. Review `.env` configuration

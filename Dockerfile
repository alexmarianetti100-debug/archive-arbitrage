# Archive Arbitrage - Scraping Pipeline
# Multi-stage build: deps layer cached, app layer fast to rebuild

FROM python:3.11-slim AS base

# Playwright system deps + common build requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Playwright Chromium deps
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdbus-1-3 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libasound2 libatspi2.0-0 libwayland-client0 \
    # General utilities
    curl cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Dependency layer (cached unless requirements.txt changes) ---
FROM base AS deps

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium only (skip Firefox/WebKit to save ~800MB)
RUN playwright install chromium

# --- App layer ---
FROM deps AS app

# Copy application code
COPY core/ core/
COPY scrapers/ scrapers/
COPY api/ api/
COPY db/ db/
COPY trend_sources/ trend_sources/
COPY trend_engine.py .
COPY gap_hunter.py .
COPY pipeline.py .
COPY telegram_bot.py .
COPY stripe_billing.py .
COPY config/ config/
COPY ml/ ml/
COPY marketing/ marketing/
COPY auth_system/ auth_system/

# Ensure data + logs dirs exist (volumes mount over these)
RUN mkdir -p /app/data /app/data/trends /app/data/logs /app/logs

# Non-root user for runtime
RUN groupadd -r scraper && useradd -r -g scraper -d /app scraper \
    && chown -R scraper:scraper /app
USER scraper

# Default: run the gap hunter pipeline
ENTRYPOINT ["python", "-u"]
CMD ["gap_hunter.py"]

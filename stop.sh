#!/bin/bash
# Stop Archive Arbitrage server and scraper

echo "Stopping Archive Arbitrage..."

# Kill server on port 8000
lsof -t -i:8000 | xargs kill -9 2>/dev/null

# Kill any running scrapers
pkill -f "pipeline.py" 2>/dev/null

echo "✅ Stopped"

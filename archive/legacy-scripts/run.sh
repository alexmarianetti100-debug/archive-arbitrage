#!/bin/bash
# Archive Arbitrage Runner
# Usage: ./run.sh [command]
#   ./run.sh run              # Full pipeline: scrape → qualify → alerts
#   ./run.sh scrape           # Scrape only
#   ./run.sh qualify --alert  # Qualify + Discord alerts
#   ./run.sh deals --grade A  # Show A-grade deals
#   ./run.sh serve            # Start API server
#   ./run.sh list             # List items
#   ./run.sh stats            # Show stats

cd "$(dirname "$0")"
source venv/bin/activate
python pipeline.py "$@"

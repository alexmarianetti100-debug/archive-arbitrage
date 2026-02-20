#!/usr/bin/env python3
"""Debug wrapper for scheduled_scrape.py"""

import sys
import os

# Force unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'

print("DEBUG: Starting wrapper", flush=True)

import asyncio
from datetime import datetime

print(f"DEBUG: Starting scrape at {datetime.now()}", flush=True)

# Import the main function
from scheduled_scrape import run_scheduled_scrape

print("DEBUG: Imported run_scheduled_scrape", flush=True)

# Run it
asyncio.run(run_scheduled_scrape())

print("DEBUG: Complete!", flush=True)

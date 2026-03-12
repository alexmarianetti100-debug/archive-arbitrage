#!/usr/bin/env python3
import os
import sys
import asyncio
from pathlib import Path

# Attempt to configure path to sibling modules
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def check_env():
    print("=== ENVIRONMENT HEALTH ===")
    print("WHOP_ENABLED:", os.getenv("WHOP_ENABLED", "Not set"))
    print("WHOP_DRY_RUN:", os.getenv("WHOP_DRY_RUN", "Not set"))
    print("WHOP_API_KEY:", "SET" if os.getenv("WHOP_API_KEY") else "Not set")
    print("WHOP_EXPERIENCE_ID:", os.getenv("WHOP_EXPERIENCE_ID", "Not set"))
    print("DISCORD_WEBHOOK:", "SET" if os.getenv("DISCORD_WEBHOOK_URL") else "Not set")

def check_scrapers():
    print("\n=== SCRAPER REGISTRY HEALTH ===")
    try:
        from pipeline import ALL_SOURCES, ACTIVE_SOURCES
        print("ALL_SOURCES mapped:")
        for name, cls in ALL_SOURCES.items():
            print(f"  [{name}]: {type(cls)}")
        print("ACTIVE_SOURCES mapped:")
        for name, cls in ACTIVE_SOURCES.items():
            print(f"  [{name}]: {type(cls)}")
    except Exception as e:
        print("FAIL loading pipeline sources:", e)

def check_db():
    print("\n=== DB HEALTH ===")
    db_path = Path(__file__).parent / "data" / "archive.db"
    print("DB exists:", db_path.exists())

if __name__ == "__main__":
    check_env()
    check_scrapers()
    check_db()

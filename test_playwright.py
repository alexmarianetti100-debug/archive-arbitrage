#!/usr/bin/env python3
"""Test Playwright scrapers for Depop and Mercari."""

import asyncio
import sys
sys.path.insert(0, '.')

from scrapers.depop_playwright import DepopPlaywrightScraper
from scrapers.mercari_playwright import MercariPlaywrightScraper

async def test_depop():
    print("\n🧪 Testing Depop Playwright scraper...")
    try:
        scraper = DepopPlaywrightScraper()
        items = await scraper.search("rick owens", max_results=3)
        print(f"✅ Found {len(items)} items")
        for item in items[:2]:
            print(f"   - {item.title[:50]}... ${item.price}")
        await scraper.close()
        return True
    except Exception as e:
        print(f"❌ Depop failed: {e}")
        return False

async def test_mercari():
    print("\n🧪 Testing Mercari Playwright scraper...")
    try:
        scraper = MercariPlaywrightScraper()
        items = await scraper.search("prada", max_results=3)
        print(f"✅ Found {len(items)} items")
        for item in items[:2]:
            print(f"   - {item.title[:50]}... ${item.price}")
        await scraper.close()
        return True
    except Exception as e:
        print(f"❌ Mercari failed: {e}")
        return False

async def main():
    print("=" * 50)
    print("Testing Playwright Scrapers")
    print("=" * 50)
    
    depop_ok = await test_depop()
    mercari_ok = await test_mercari()
    
    print("\n" + "=" * 50)
    if depop_ok and mercari_ok:
        print("✅ All scrapers working!")
    else:
        print("⚠️  Some scrapers failed")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())

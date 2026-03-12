#!/usr/bin/env python3
"""Test Depop scraper."""

import asyncio
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scrapers.depop import DepopScraper

async def test_depop():
    print("Testing Depop Scraper")
    print("=" * 50)
    
    scraper = DepopScraper()
    
    try:
        print("Searching for nike...")
        items = await scraper.search("nike", max_results=5)
        
        print(f"Found {len(items)} items")
        
        if items:
            print("\nFirst 3 items:")
            for i, item in enumerate(items[:3], 1):
                print(f"  {i}. {item.title[:50]}...")
                print(f"     Price: ${item.price}")
                print(f"     Brand: {item.brand or 'N/A'}")
        
        return len(items) > 0
        
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await scraper.close()

if __name__ == "__main__":
    result = asyncio.run(test_depop())
    print(f"\n{'PASS' if result else 'FAIL'}")
    sys.exit(0 if result else 1)

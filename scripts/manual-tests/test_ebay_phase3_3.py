#!/usr/bin/env python3
"""Test eBay scraper with proper environment loading."""

import asyncio
import sys
import os

# Add project to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from scrapers.ebay import EbayScraper

async def test_ebay():
    print('Testing eBay Scraper (Phase 3.3)')
    print('=' * 60)
    
    # Check environment
    print('\nEnvironment:')
    print(f'  PROXY_HOST: {os.getenv("PROXY_HOST", "NOT SET")}')
    print(f'  PROXY_USERNAME: {"SET" if os.getenv("PROXY_USERNAME") else "NOT SET"}')
    
    async with EbayScraper() as scraper:
        # Check health before
        health = EbayScraper.get_health_status()
        print(f'\nHealth (before):')
        print(f'  Status: {"✅ Healthy" if health["healthy"] else "❌ Unhealthy"}')
        print(f'  Success rate: {health["success_rate"]:.1%}')
        print(f'  Success count: {health["success_count"]}')
        print(f'  Failure count: {health["failure_count"]}')
        print(f'  Rate limit hits: {health["rate_limit_hits"]}')
        print(f'  Timeout: {health["timeout_seconds"]}s')
        
        try:
            print('\nSearching for "nike" (max 5 results)...')
            items = await scraper.search('nike', max_results=5)
            
            print(f'\nResults:')
            print(f'  Found {len(items)} items')
            
            if items:
                print('\nFirst 3 items:')
                for i, item in enumerate(items[:3], 1):
                    print(f'  {i}. {item.title[:50]}...')
                    print(f'     Price: ${item.price}')
                    print(f'     Condition: {item.condition or "N/A"}')
            else:
                print('\n  ⚠️  No items found - checking parsing...')
            
            # Check health after
            health = EbayScraper.get_health_status()
            print(f'\nHealth (after):')
            print(f'  Status: {"✅ Healthy" if health["healthy"] else "❌ Unhealthy"}')
            print(f'  Success count: {health["success_count"]}')
            print(f'  Failure count: {health["failure_count"]}')
            
            return len(items) > 0
            
        except Exception as e:
            print(f'\n❌ Error: {type(e).__name__}: {e}')
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    result = asyncio.run(test_ebay())
    print(f'\n{"✅ PASS" if result else "❌ FAIL"}')
    sys.exit(0 if result else 1)

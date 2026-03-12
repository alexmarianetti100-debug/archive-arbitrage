#!/usr/bin/env python3
"""Test eBay scraper with detailed tracing."""

import asyncio
import sys
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from scrapers.ebay import EbayScraper

async def test_with_trace():
    print('Testing eBay Scraper with Tracing')
    print('=' * 60)
    
    scraper = EbayScraper()
    print(f'Created scraper: {scraper}')
    print(f'Proxy: {scraper._proxy[:40]}...' if scraper._proxy else 'No proxy')
    
    # Don't use async context manager - call methods directly
    print('\nCalling search directly...')
    items = await scraper.search('nike', max_results=5)
    
    print(f'Returned {len(items)} items')
    
    if items:
        for i, item in enumerate(items[:3], 1):
            print(f'  {i}. {item.title[:50]}... - ${item.price}')
    
    health = EbayScraper.get_health_status()
    print(f'\nHealth: {health}')

if __name__ == '__main__':
    asyncio.run(test_with_trace())

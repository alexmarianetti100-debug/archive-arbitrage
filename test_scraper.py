#!/usr/bin/env python3
"""Quick scraper test."""
import asyncio
from scrapers import GrailedScraper

async def test():
    print('Testing Grailed scraper...')
    async with GrailedScraper(use_proxies=False) as scraper:
        print('Scraper initialized, searching...')
        items = await scraper.search('raf simons', max_results=3)
        print(f'Found {len(items)} items')
        for item in items[:2]:
            print(f'  - {item.title[:50]}... ${item.price}')

asyncio.run(test())

#!/usr/bin/env python3
"""Debug eBay scraper with full exception tracing."""

import asyncio
import sys
import os
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from scrapers.ebay import EbayScraper

async def debug():
    print('Debugging eBay Scraper')
    print('=' * 60)
    
    scraper = EbayScraper()
    print(f'Proxy: {scraper._proxy[:40]}...' if scraper._proxy else 'No proxy')
    
    # Manually call _fetch to see what happens
    params = {
        "_nkw": 'nike',
        "_sacat": "11450",
        "LH_BIN": "1",
        "LH_Auction": "0",
        "_sop": "10",
        "_ipg": "60",
    }
    
    print('\nCalling _fetch...')
    try:
        soup = await scraper._fetch(params)
        if soup:
            cards = soup.select("li.s-card, li.s-item")
            print(f'✅ _fetch returned soup with {len(cards)} cards')
        else:
            print('❌ _fetch returned None')
    except Exception as e:
        print(f'❌ _fetch exception: {type(e).__name__}: {e}')
        traceback.print_exc()
    
    # Now call search
    print('\nCalling search...')
    try:
        items = await scraper.search('nike', max_results=5)
        print(f'✅ search returned {len(items)} items')
    except Exception as e:
        print(f'❌ search exception: {type(e).__name__}: {e}')
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(debug())

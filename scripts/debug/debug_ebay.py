#!/usr/bin/env python3
"""Debug eBay parsing."""

import asyncio
import re
from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup

async def test():
    print('Testing eBay parsing...')
    async with AsyncSession(impersonate='chrome120') as session:
        url = 'https://www.ebay.com/sch/i.html?_nkw=nike&_sacat=11450&LH_BIN=1'
        resp = await session.get(url, timeout=30)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Test the selectors
        cards = soup.select('li.s-card, li.s-item')
        print(f'Total cards: {len(cards)}')
        
        valid_items = 0
        
        # Skip first (ad) and check next few
        for i, card in enumerate(cards[1:10], 1):
            # Title
            title_el = card.select_one('[class*="title"], h3')
            title = title_el.get_text(strip=True) if title_el else ''
            
            # Skip shop on ebay
            if 'shop on ebay' in title.lower():
                continue
            
            # Price
            price_el = card.select_one('.s-item__price') or card.select_one('[itemprop="price"]') or card.select_one('[class*="price"]')
            price_text = price_el.get_text(strip=True) if price_el else ''
            
            # Parse price
            price_matches = [float(n.replace(',', '')) for n in re.findall(r'[\d,]+\.?\d*', price_text) if float(n.replace(',', '')) >= 30.0]
            price = max(price_matches) if price_matches else 0.0
            
            if title and price > 0:
                valid_items += 1
                print(f'\nItem {valid_items}:')
                print(f'  Title: {title[:50]}...')
                print(f'  Price: ${price}')
        
        print(f'\nTotal valid items: {valid_items}')

if __name__ == "__main__":
    asyncio.run(test())

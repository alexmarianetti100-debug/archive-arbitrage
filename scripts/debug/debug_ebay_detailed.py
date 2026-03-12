#!/usr/bin/env python3
"""Debug eBay parsing in detail."""

import asyncio
import sys
import os
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup

async def debug():
    print('Debugging eBay Parsing')
    print('=' * 60)
    
    # Build proxy URL
    host = os.getenv('PROXY_HOST', 'p.webshare.io')
    port = os.getenv('PROXY_PORT', '10000')
    user = os.getenv('PROXY_USERNAME', '')
    pwd = os.getenv('PROXY_PASSWORD', '')
    proxy = f'http://{user}:{pwd}@{host}:{port}' if user and pwd else None
    
    print(f'Proxy: {proxy[:40]}...' if proxy else 'No proxy')
    
    proxies = {'https': proxy} if proxy else None
    
    async with AsyncSession(impersonate='chrome120') as session:
        url = 'https://www.ebay.com/sch/i.html?_nkw=nike&_sacat=11450&LH_BIN=1'
        print(f'\nFetching: {url}')
        
        resp = await session.get(url, proxies=proxies, timeout=45)
        print(f'Status: {resp.status_code}')
        print(f'Final URL: {resp.url}')
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Find cards
        cards = soup.select('li.s-card, li.s-item')
        print(f'\nTotal cards found: {len(cards)}')
        
        # Check first few cards in detail
        valid_items = 0
        MIN_PRICE = 30.0
        
        print('\n--- Parsing first 10 cards ---')
        for i, card in enumerate(cards[1:11], 1):  # Skip first (ad)
            print(f'\nCard {i}:')
            
            # Title
            title_el = card.select_one("[class*='title'], h3")
            title = title_el.get_text(strip=True) if title_el else ''
            print(f'  Title: {title[:60] if title else "NOT FOUND"}')
            
            if not title:
                print('  -> SKIP: No title')
                continue
            
            if 'shop on ebay' in title.lower():
                print('  -> SKIP: Shop on eBay')
                continue
            
            # Check for auction
            card_text = card.get_text(' ', strip=True).lower()
            if any(kw in card_text for kw in ('place bid', 'bid now', 'bids', 'time left')):
                print('  -> SKIP: Auction card')
                continue
            
            # Price
            price_el = (
                card.select_one('.s-item__price')
                or card.select_one("[itemprop='price']")
                or card.select_one("[class*='price']")
            )
            price_text = price_el.get_text(strip=True) if price_el else ''
            print(f'  Price text: {price_text}')
            
            # Parse price
            price_matches = [float(n.replace(',', '')) for n in re.findall(r'[\d,]+\.?\d*', price_text) if float(n.replace(',', '')) >= MIN_PRICE]
            price = max(price_matches) if price_matches else 0.0
            print(f'  Parsed price: ${price}')
            
            if price <= 0:
                print(f'  -> SKIP: Price <= 0 (MIN_PRICE={MIN_PRICE})')
                continue
            
            # URL
            link_el = card.select_one("a[href*='/itm/'], a[href*='ebay.com/itm']")
            url = link_el['href'].split('?')[0] if link_el else ''
            if not url:
                print('  -> SKIP: No URL')
                continue
            
            print(f'  URL: {url[:60]}...')
            valid_items += 1
            print(f'  -> VALID ITEM #{valid_items}')
        
        print(f'\n=== Total valid items: {valid_items} ===')

if __name__ == '__main__':
    asyncio.run(debug())

#!/usr/bin/env python3
"""Debug eBay _parse_items."""

import asyncio
import sys
import os
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from urllib.parse import urlencode

SEARCH_URL = "https://www.ebay.com/sch/i.html"
MIN_PRICE = 30.0

async def debug_parse():
    print('Debugging eBay _parse_items')
    print('=' * 60)
    
    # Fetch HTML
    host = os.getenv('PROXY_HOST', 'p.webshare.io')
    port = os.getenv('PROXY_PORT', '10000')
    user = os.getenv('PROXY_USERNAME', '')
    pwd = os.getenv('PROXY_PASSWORD', '')
    proxy = f'http://{user}:{pwd}@{host}:{port}' if user and pwd else None
    proxies = {'https': proxy} if proxy else None
    
    params = {
        "_nkw": 'nike',
        "_sacat": "11450",
        "LH_BIN": "1",
        "LH_Auction": "0",
        "_sop": "10",
        "_ipg": "60",
    }
    
    from curl_cffi.requests import AsyncSession
    session = AsyncSession(impersonate="chrome120")
    
    try:
        url = SEARCH_URL + "?" + urlencode(params)
        resp = await session.get(url, proxies=proxies, timeout=45)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        print(f'Fetched {len(resp.text)} bytes')
        card_selector = "li.s-card, li.s-item"
        print(f'Found {len(soup.select(card_selector))} cards')
        
        # Now parse like _parse_items does
        items = []
        cards = soup.select("li.s-card, li.s-item")[1:5+6]  # [1:] skips first ad card
        
        print(f'\nProcessing {len(cards)} cards...')
        
        for i, card in enumerate(cards):
            print(f'\nCard {i+1}:')
            
            try:
                title_el = card.select_one("[class*='title'], h3")
                if not title_el:
                    print('  No title element')
                    continue
                
                title = title_el.get_text(strip=True)
                print(f'  Title: {title[:50]}...')
                
                if "shop on ebay" in title.lower():
                    print('  -> SKIP: shop on ebay')
                    continue
                
                # Check for auction
                card_text = card.get_text(" ", strip=True).lower()
                auction_keywords = ("place bid", "bid now", "bids", "time left", "se abre en")
                if any(kw in card_text for kw in auction_keywords):
                    print(f'  -> SKIP: auction card')
                    continue
                
                # URL
                link_el = card.select_one("a[href*='/itm/'], a[href*='ebay.com/itm']")
                if not link_el:
                    print('  No link element')
                    continue
                    
                url = link_el["href"].split("?")[0] if link_el else ""
                print(f'  URL: {url[:50]}...')
                
                item_id_match = re.search(r"/itm/(\d+)", url)
                item_id = item_id_match.group(1) if item_id_match else url
                if not item_id or not url:
                    print('  No item_id or url')
                    continue
                
                # Price
                price_el = (
                    card.select_one(".s-item__price")
                    or card.select_one("[itemprop='price']")
                    or card.select_one("[class*='price']")
                )
                price_text = price_el.get_text(strip=True) if price_el else ""
                print(f'  Price text: {price_text}')
                
                price_matches = [float(n.replace(",", "")) for n in re.findall(r"[\d,]+\.?\d*", price_text) if float(n.replace(",", "")) >= MIN_PRICE]
                price = max(price_matches) if price_matches else 0.0
                print(f'  Parsed price: ${price}')
                
                if price <= 0:
                    print(f'  -> SKIP: price <= 0')
                    continue
                
                print(f'  -> VALID ITEM!')
                items.append({"title": title, "price": price})
                
            except Exception as e:
                print(f'  Error: {e}')
                continue
        
        print(f'\n\nTotal items: {len(items)}')
        
    finally:
        await session.close()

if __name__ == '__main__':
    asyncio.run(debug_parse())

#!/usr/bin/env python3
"""Debug eBay _fetch method."""

import asyncio
import sys
import os
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
from urllib.parse import urlencode

SEARCH_URL = "https://www.ebay.com/sch/i.html"
REQUEST_TIMEOUT = 45.0

async def _proxy_url():
    host = os.getenv("PROXY_HOST", "p.webshare.io")
    port = os.getenv("PROXY_PORT", "10000")
    user = os.getenv("PROXY_USERNAME", "")
    pwd  = os.getenv("PROXY_PASSWORD", "")
    if user and pwd:
        return f"http://{user}:{pwd}@{host}:{port}"
    return None

async def debug_fetch():
    print('Debugging eBay _fetch')
    print('=' * 60)
    
    proxy = await _proxy_url()
    print(f'Proxy: {proxy[:40]}...' if proxy else 'No proxy')
    
    proxies = {"https": proxy} if proxy else None
    
    params = {
        "_nkw": 'nike',
        "_sacat": "11450",
        "LH_BIN": "1",
        "LH_Auction": "0",
        "_sop": "10",
        "_ipg": "60",
    }
    
    try:
        print('\nCreating AsyncSession with chrome120...')
        async with AsyncSession(impersonate="chrome120") as session:
            url = SEARCH_URL + "?" + urlencode(params)
            print(f'URL: {url[:80]}...')
            
            print('Sending request...')
            resp = await session.get(url, proxies=proxies, timeout=REQUEST_TIMEOUT)
            
            print(f'Response status: {resp.status_code}')
            print(f'Response URL: {resp.url}')
            
            if resp.status_code != 200:
                print(f'ERROR: Non-200 status: {resp.status_code}')
                return None
            
            if "splashui/challenge" in str(resp.url):
                print('ERROR: Bot challenge detected!')
                return None
            
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("li.s-card, li.s-item")
            print(f'Success! Found {len(cards)} cards')
            
            return soup
            
    except asyncio.TimeoutError:
        print(f'ERROR: Timeout after {REQUEST_TIMEOUT}s')
        return None
    except Exception as e:
        print(f'ERROR: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    result = asyncio.run(debug_fetch())
    status = "Success" if result else "Failed"
    print(f'\nResult: {status}')
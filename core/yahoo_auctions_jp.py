"""
Direct Yahoo Auctions Japan Scraper

Bypasses Buyee proxy and scrapes Yahoo Auctions Japan directly.
Uses rotating user agents and proxy rotation to avoid blocks.
"""

import asyncio
import logging
import random
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("yahoo_auctions_jp")


@dataclass
class YahooAuctionItem:
    """Yahoo Auctions Japan listing."""
    title: str
    title_jp: str
    price_jpy: int
    auction_id: str
    auction_url: str
    image_url: Optional[str]
    bids: int
    end_time: Optional[datetime]
    seller_rating: Optional[float]
    category: str
    brand: str
    weight_kg: float
    is_buy_now: bool = False  # True = fixed price (即決), safe to feature


class YahooAuctionsScraper:
    """Scrape Yahoo Auctions Japan directly."""
    
    BASE_URL = "https://auctions.yahoo.co.jp/search/search"
    
    # Rotating user agents
    USER_AGENTS = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    def __init__(self, use_proxies: bool = True):
        self.use_proxies = use_proxies
        self.client: Optional[httpx.AsyncClient] = None
        self.seen_items: set = set()
    
    async def __aenter__(self):
        # Create client with random user agent
        headers = {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        
        # Add proxy if configured
        proxy = None
        if self.use_proxies:
            try:
                from core.proxy_pool import get_proxy_pool
                pool = get_proxy_pool()
                if pool and pool.proxies:
                    p = random.choice(pool.proxies)
                    proxy = f"http://{p.username}:{p.password}@{p.host}:{p.port}"
                    logger.debug(f"Using proxy: {p.host}:{p.port}")
            except Exception as e:
                logger.debug(f"No proxy available: {e}")
        
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers=headers,
            proxy=proxy,
            follow_redirects=True,
        )
        return self
    
    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()
    
    async def search(
        self,
        query_jp: str,
        query_en: str,
        category: str,
        brand: str,
        weight_kg: float,
        max_results: int = 20,
        min_price_jpy: int = 10000,
        buy_now_only: bool = True,
    ) -> List[YahooAuctionItem]:
        """Search Yahoo Auctions Japan.

        Args:
            buy_now_only: If True, only return listings with a fixed buy-now price
                         (即決価格). Auction-only listings are excluded because the
                         final price is unpredictable and profit can't be guaranteed.
        """

        items = []

        try:
            # Build search URL
            # Yahoo Auctions uses p={query} for search
            encoded_query = quote(query_jp)
            url = f"{self.BASE_URL}?p={encoded_query}&va={encoded_query}&exflg=1&b=1&n={max_results}"

            # fixed=2 → only listings with buy-now price (即決価格あり)
            if buy_now_only:
                url += "&fixed=2"

            # Add price filter
            if min_price_jpy:
                url += f"&aucminprice={min_price_jpy}"
            
            logger.info(f"[Yahoo JP] Searching: {query_jp}")
            logger.debug(f"[Yahoo JP] URL: {url}")
            
            response = await self.client.get(url)
            
            if response.status_code != 200:
                logger.warning(f"[Yahoo JP] Returned {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Parse auction items
            # Yahoo Auctions uses different selectors
            for item_el in soup.select('.Product')[:max_results]:
                try:
                    item = self._parse_item(item_el, query_jp, query_en, category, brand, weight_kg)
                    if item and item.auction_id not in self.seen_items:
                        self.seen_items.add(item.auction_id)
                        items.append(item)
                except Exception as e:
                    logger.debug(f"Error parsing item: {e}")
                    continue
            
            logger.info(f"[Yahoo JP] Found {len(items)} items")
            
        except Exception as e:
            logger.error(f"[Yahoo JP] Search failed: {e}")
        
        return items
    
    def _parse_item(
        self,
        item_el,
        query_jp: str,
        query_en: str,
        category: str,
        brand: str,
        weight_kg: float,
    ) -> Optional[YahooAuctionItem]:
        """Parse a Yahoo Auctions item element."""
        
        try:
            # Title
            title_el = item_el.select_one('.Product__title a')
            if not title_el:
                return None
            
            title = title_el.get_text(strip=True)
            href = title_el.get('href', '')
            
            # Extract auction ID from URL
            auction_id = ''
            if 'auction' in href:
                # URL format: https://page.auctions.yahoo.co.jp/jp/auction/{id}
                auction_id = href.split('/')[-1].split('?')[0]
            
            if not auction_id:
                return None
            
            # Price
            price_el = item_el.select_one('.Product__price')
            if not price_el:
                return None
            
            price_text = price_el.get_text()
            # Parse price like "¥12,345" or "12,345円"
            price_str = ''.join(c for c in price_text if c.isdigit())
            if not price_str:
                return None
            
            price_jpy = int(price_str)
            
            if price_jpy < 10000:  # Skip items under ¥10,000
                return None
            
            # Image
            img_el = item_el.select_one('.Product__image img')
            image_url = img_el.get('src') if img_el else None
            
            # Bids
            bids = 0
            bid_el = item_el.select_one('.Product__bid')
            if bid_el:
                bid_text = bid_el.get_text()
                bids = int(''.join(c for c in bid_text if c.isdigit()) or 0)

            # Buy-now price (即決価格) — look for the dedicated element
            is_buy_now = False
            buynow_el = item_el.select_one('.Product__buynow, .Product__priceValue--buynow')
            if buynow_el:
                buynow_text = buynow_el.get_text()
                buynow_str = ''.join(c for c in buynow_text if c.isdigit())
                if buynow_str:
                    # Use the buy-now price instead of current bid
                    price_jpy = int(buynow_str)
                    is_buy_now = True
            # Also check for 即決 in the item text as a fallback signal
            if not is_buy_now:
                item_text = item_el.get_text()
                if '即決' in item_text:
                    is_buy_now = True

            # Time remaining
            end_time = None
            time_el = item_el.select_one('.Product__time')
            if time_el:
                time_text = time_el.get_text()
                end_time = self._parse_time_remaining(time_text)

            return YahooAuctionItem(
                title=query_en,  # Use English query as title
                title_jp=title,
                price_jpy=price_jpy,
                auction_id=auction_id,
                auction_url=href if href.startswith('http') else f"https://auctions.yahoo.co.jp{href}",
                image_url=image_url,
                bids=bids,
                end_time=end_time,
                seller_rating=None,  # Would need to fetch seller page
                category=category,
                brand=brand,
                weight_kg=weight_kg,
                is_buy_now=is_buy_now,
            )
            
        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None
    
    def _parse_time_remaining(self, time_text: str) -> Optional[datetime]:
        """Parse time remaining text like '2日 5時間' or '5時間 30分'."""
        import re
        
        days = 0
        hours = 0
        minutes = 0
        
        # Match days
        day_match = re.search(r'(\d+)\s*日', time_text)
        if day_match:
            days = int(day_match.group(1))
        
        # Match hours
        hour_match = re.search(r'(\d+)\s*時間', time_text)
        if hour_match:
            hours = int(hour_match.group(1))
        
        # Match minutes
        min_match = re.search(r'(\d+)\s*分', time_text)
        if min_match:
            minutes = int(min_match.group(1))
        
        if days or hours or minutes:
            return datetime.now() + timedelta(days=days, hours=hours, minutes=minutes)
        
        return None


# Convenience function
async def search_yahoo_auctions_jp(**kwargs) -> List[YahooAuctionItem]:
    """Search Yahoo Auctions Japan."""
    async with YahooAuctionsScraper() as scraper:
        return await scraper.search(**kwargs)


if __name__ == "__main__":
    async def test():
        print("Testing Yahoo Auctions Japan scraper...")
        
        items = await search_yahoo_auctions_jp(
            query_jp='ロレックス デイトジャスト',
            query_en='rolex datejust',
            category='watch',
            brand='Rolex',
            weight_kg=0.3,
            max_results=10,
        )
        
        print(f"Found {len(items)} items")
        for item in items[:5]:
            print(f"  - {item.title_jp[:40]}... ¥{item.price_jpy:,} ({item.bids} bids)")
            print(f"    URL: {item.auction_url}")
    
    asyncio.run(test())

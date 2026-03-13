"""
Mercari Japan Scraper via Buyee with Playwright

Uses Playwright to render JavaScript and scrape Mercari listings.
Mercari is C2C fixed-price, often cheaper than Yahoo Auctions.
"""

import asyncio
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from core.mercari_urls import mercari_item_url

logger = logging.getLogger("mercari_japan")

# Playwright import - optional dependency
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    logger.warning("Playwright not installed. Mercari scraping disabled.")


@dataclass
class MercariItem:
    """Mercari Japan listing."""
    title_jp: str
    title_en: str  # Translated/expected English title
    price_jpy: int
    item_id: str
    item_url: str
    image_url: Optional[str]
    seller_rating: Optional[float]
    likes: int  # Mercari "likes" = interest level
    condition: str  # Mercari condition grading
    shipping_payer: str  # "seller" or "buyer"
    created_at: Optional[datetime]
    category: str
    brand: str
    weight_kg: float


class MercariJapanScraper:
    """Scrape Mercari Japan via Buyee proxy service using Playwright."""
    
    BASE_URL = "https://buyee.jp/mercari/search"
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.seen_items: set = set()
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,ja;q=0.8',
            }
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
        min_price_jpy: int = 10000,  # ~$67
        max_price_jpy: Optional[int] = None,
        use_playwright: bool = True,
    ) -> List[MercariItem]:
        """Search Mercari Japan via Buyee."""
        
        if not HAS_PLAYWRIGHT:
            logger.warning("Playwright not available, skipping Mercari search")
            return []
        
        if use_playwright:
            return await self._search_with_playwright(
                query_jp, query_en, category, brand, weight_kg, max_results, min_price_jpy, max_price_jpy
            )
        else:
            return await self._search_static(
                query_jp, query_en, category, brand, weight_kg, max_results, min_price_jpy, max_price_jpy
            )
    
    async def _search_with_playwright(
        self,
        query_jp: str,
        query_en: str,
        category: str,
        brand: str,
        weight_kg: float,
        max_results: int = 20,
        min_price_jpy: int = 10000,
        max_price_jpy: Optional[int] = None,
    ) -> List[MercariItem]:
        """Search using Playwright to render JavaScript."""
        
        items = []
        
        try:
            # Build search URL
            params = {
                'keyword': query_jp,
                'sort': 'created_time',
                'order': 'desc',
            }
            
            if min_price_jpy:
                params['price_min'] = min_price_jpy
            if max_price_jpy:
                params['price_max'] = max_price_jpy
            
            # Build URL manually
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            url = f"{self.BASE_URL}?{query_string}"
            
            logger.info(f"[Playwright] Searching Mercari: {query_jp}")
            
            async with async_playwright() as p:
                # Launch browser (firefox is more stable on macOS)
                browser = await p.firefox.launch(headless=True)
                page = await browser.new_page()
                
                # Navigate to page with shorter timeout
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=20000)
                except Exception as e:
                    logger.debug(f"Page load timeout/error: {e}")
                    await browser.close()
                    return []
                
                # Wait a bit for JS to execute
                await asyncio.sleep(2)
                
                # Wait for items to load
                try:
                    await page.wait_for_selector('.itemCard', timeout=8000)
                except Exception:
                    logger.debug(f"No items found for {query_jp}")
                    await browser.close()
                    return []
                
                # Get page content after JavaScript execution
                html = await page.content()
                
                await browser.close()
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                
                # Parse items
                for item_el in soup.select('.itemCard')[:max_results]:
                    try:
                        item = self._parse_item(
                            item_el,
                            query_en=query_en,
                            category=category,
                            brand=brand,
                            weight_kg=weight_kg,
                        )
                        if item:
                            items.append(item)
                    except Exception as e:
                        logger.debug(f"Error parsing Mercari item: {e}")
                        continue
                
                logger.info(f"[Playwright] Found {len(items)} Mercari items for {query_en}")
                
        except Exception as e:
            logger.error(f"[Playwright] Mercari search error: {e}")
        
        return items
    
    async def _search_static(
        self,
        query_jp: str,
        query_en: str,
        category: str,
        brand: str,
        weight_kg: float,
        max_results: int = 20,
        min_price_jpy: int = 10000,
        max_price_jpy: Optional[int] = None,
    ) -> List[MercariItem]:
        """Fallback static search (won't work for Mercari)."""
        
        items = []
        
        try:
            params = {
                'keyword': query_jp,
                'sort': 'created_time',
                'order': 'desc',
            }
            
            if min_price_jpy:
                params['price_min'] = min_price_jpy
            if max_price_jpy:
                params['price_max'] = max_price_jpy
            
            url = f"{self.BASE_URL}"
            
            logger.info(f"[Static] Searching Mercari: {query_jp}")
            response = await self.client.get(url, params=params)
            
            if response.status_code != 200:
                logger.warning(f"Mercari search failed: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check if page has itemCard elements
            item_cards = soup.select('.itemCard')
            
            if not item_cards:
                logger.debug(f"Mercari items loaded via JavaScript - use Playwright for {query_en}")
                return []
            
            for item_el in item_cards[:max_results]:
                try:
                    item = self._parse_item(
                        item_el,
                        query_en=query_en,
                        category=category,
                        brand=brand,
                        weight_kg=weight_kg,
                    )
                    if item:
                        items.append(item)
                except Exception as e:
                    logger.debug(f"Error parsing Mercari item: {e}")
                    continue
            
            logger.info(f"[Static] Found {len(items)} Mercari items for {query_en}")
            
        except Exception as e:
            logger.error(f"[Static] Mercari search error: {e}")
        
        return items
    
    def _parse_item(
        self,
        item_el,
        query_en: str,
        category: str,
        brand: str,
        weight_kg: float,
    ) -> Optional[MercariItem]:
        """Parse a single Mercari item from HTML."""
        
        # Title - inside itemCard__itemName
        title_el = item_el.select_one('.itemCard__itemName a')
        if not title_el:
            return None
        title_jp = title_el.get_text(strip=True)
        
        # Price - inside g-price
        price_el = item_el.select_one('.g-price')
        if not price_el:
            return None
        
        price_text = price_el.get_text()
        price_jpy = self._parse_jpy_price(price_text)
        
        if not price_jpy or price_jpy < 10000:
            return None
        
        # Item ID and URL
        item_id = ""
        item_url = ""
        if title_el and title_el.get('href'):
            href = title_el['href']
            item_id = href.split('/')[-1].split('?')[0]
            item_url = mercari_item_url(item_id or href)
        
        if item_id in self.seen_items:
            return None
        
        self.seen_items.add(item_id)
        
        # Image - inside g-thumbnail__image
        img_el = item_el.select_one('.g-thumbnail__image')
        image_url = img_el.get('data-src') if img_el else None
        
        # Likes (Mercari's "いいね" count) - look in itemCard__infoList
        likes = 0
        info_list = item_el.select_one('.itemCard__infoList')
        if info_list:
            info_text = info_list.get_text()
            # Look for heart/like indicators
            if 'いいね' in info_text or 'like' in info_text.lower():
                likes = self._extract_number(info_text) or 0
        
        # Condition (if available)
        condition = "unknown"
        condition_el = item_el.select_one('.itemCard__infoItem')
        if condition_el:
            condition_text = condition_el.get_text()
            if '新品' in condition_text:
                condition = "new"
            elif '未使用' in condition_text:
                condition = "unused"
            elif '中古' in condition_text:
                condition = "used"
        
        # Shipping payer - check itemCard__infoList for shipping info
        shipping_payer = "unknown"
        if info_list:
            info_text = info_list.get_text()
            if '送料込' in info_text or '出品者' in info_text:
                shipping_payer = "seller"
            elif '送料別' in info_text or '購入者' in info_text:
                shipping_payer = "buyer"
        
        return MercariItem(
            title_jp=title_jp,
            title_en=query_en,
            price_jpy=price_jpy,
            item_id=item_id,
            item_url=item_url,
            image_url=image_url,
            seller_rating=None,
            likes=likes,
            condition=condition,
            shipping_payer=shipping_payer,
            created_at=None,
            category=category,
            brand=brand,
            weight_kg=weight_kg,
        )
    
    def _parse_jpy_price(self, price_text: str) -> Optional[int]:
        """Parse JPY price from text."""
        import re
        cleaned = re.sub(r'[^\d,]', '', price_text)
        cleaned = cleaned.replace(',', '')
        if cleaned:
            try:
                return int(cleaned)
            except:
                pass
        return None
    
    def _extract_number(self, text: str) -> Optional[int]:
        """Extract number from text."""
        import re
        numbers = re.findall(r'\d+', text)
        if numbers:
            try:
                return int(numbers[0])
            except:
                pass
        return None


# Convenience function
async def search_mercari_japan(
    query_jp: str,
    query_en: str,
    category: str,
    brand: str,
    weight_kg: float = 0.5,
    max_results: int = 20,
) -> List[MercariItem]:
    """Quick search Mercari Japan."""
    async with MercariJapanScraper() as scraper:
        return await scraper.search(
            query_jp=query_jp,
            query_en=query_en,
            category=category,
            brand=brand,
            weight_kg=weight_kg,
            max_results=max_results,
        )


if __name__ == "__main__":
    # Test the scraper
    async def test():
        if not HAS_PLAYWRIGHT:
            print("Playwright not installed. Install with: pip install playwright")
            return
        
        # Test search for Chrome Hearts ring
        items = await search_mercari_japan(
            query_jp="クロムハーツ リング",
            query_en="chrome hearts ring",
            category="jewelry",
            brand="Chrome Hearts",
            weight_kg=0.1,
            max_results=10,
        )
        
        print(f"Found {len(items)} items")
        for item in items[:5]:
            print(f"\n{item.title_jp}")
            print(f"  Price: ¥{item.price_jpy:,}")
            print(f"  Likes: {item.likes}")
            print(f"  Condition: {item.condition}")
            print(f"  URL: {item.item_url}")
    
    asyncio.run(test())

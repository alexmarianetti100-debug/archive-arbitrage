"""
Japan Arbitrage - Mercari/Rakuma Scrapers with Playwright

Robust implementation with fallback strategies.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from bs4 import BeautifulSoup

from core.mercari_urls import mercari_item_url

logger = logging.getLogger("japan_scrapers")

# Optional Playwright import
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


@dataclass
class JapanItem:
    """Generic Japan marketplace item."""
    title_jp: str
    title_en: str
    price_jpy: int
    item_id: str
    item_url: str
    image_url: Optional[str]
    platform: str  # 'mercari', 'rakuma', 'yahoo'
    category: str
    brand: str
    weight_kg: float
    extra_data: Dict[str, Any] = None


class PlaywrightScraper:
    """Base scraper using Playwright with robust error handling."""
    
    def __init__(self):
        self.seen_items: set = set()
    
    async def fetch_with_playwright(
        self,
        url: str,
        wait_selector: str = '.itemCard',
        timeout: int = 30,
    ) -> Optional[str]:
        """Fetch page using Playwright with Firefox (more stable on macOS)."""
        
        if not HAS_PLAYWRIGHT:
            logger.warning("Playwright not available")
            return None
        
        html = None
        
        try:
            async with async_playwright() as p:
                # Use Firefox - more stable on macOS
                browser = await p.firefox.launch(
                    headless=True,
                    args=['--width=1280', '--height=800']
                )
                
                # Create context with realistic settings
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
                    locale='ja-JP',
                    timezone_id='Asia/Tokyo',
                )
                
                page = await context.new_page()
                
                # Navigate with shorter timeout
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=timeout * 1000)
                except Exception as e:
                    logger.debug(f"Navigation timeout: {e}")
                
                # Wait for JavaScript to execute
                await asyncio.sleep(3)
                
                # Try to wait for items
                try:
                    await page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    logger.debug(f"Selector {wait_selector} not found, continuing anyway")
                
                # Get content
                html = await page.content()
                
                await browser.close()
                
        except Exception as e:
            logger.error(f"Playwright error: {e}")
        
        return html
    
    def parse_item_card(self, item_el, query_en: str, platform: str, **kwargs) -> Optional[JapanItem]:
        """Parse a Buyee item card element."""
        
        try:
            # Title
            title_el = item_el.select_one('.itemCard__itemName a')
            if not title_el:
                return None
            title_jp = title_el.get_text(strip=True)
            
            # Price
            price_el = item_el.select_one('.g-price')
            if not price_el:
                return None
            
            price_text = price_el.get_text()
            price_jpy = self._parse_price(price_text)
            
            if not price_jpy or price_jpy < 10000:
                return None
            
            # URL and ID
            item_id = ""
            item_url = ""
            if title_el.get('href'):
                href = title_el['href']
                item_id = href.split('/')[-1].split('?')[0]
                item_url = mercari_item_url(item_id or href) if platform == 'mercari' else (f"https://buyee.jp{href}" if not href.startswith('http') else href)
            
            if item_id in self.seen_items:
                return None
            
            self.seen_items.add(item_id)
            
            # Image
            img_el = item_el.select_one('.g-thumbnail__image')
            image_url = img_el.get('data-src') if img_el else None
            
            return JapanItem(
                title_jp=title_jp,
                title_en=query_en,
                price_jpy=price_jpy,
                item_id=item_id,
                item_url=item_url,
                image_url=image_url,
                platform=platform,
                extra_data=kwargs,
                **{k: v for k, v in kwargs.items() if k in ['category', 'brand', 'weight_kg']}
            )
            
        except Exception as e:
            logger.debug(f"Parse error: {e}")
            return None
    
    def _parse_price(self, price_text: str) -> Optional[int]:
        """Parse JPY price."""
        import re
        cleaned = re.sub(r'[^\d,]', '', price_text)
        cleaned = cleaned.replace(',', '')
        if cleaned:
            try:
                return int(cleaned)
            except:
                pass
        return None


class MercariScraper(PlaywrightScraper):
    """Scraper for Mercari Japan via Buyee."""
    
    async def search(
        self,
        query_jp: str,
        query_en: str,
        category: str,
        brand: str,
        weight_kg: float,
        max_results: int = 20,
        min_price: int = 10000,
    ) -> List[JapanItem]:
        """Search Mercari."""
        
        items = []
        
        try:
            url = f"https://buyee.jp/mercari/search?keyword={query_jp}&sort=created_time&order=desc&price_min={min_price}"
            
            logger.info(f"[Mercari] Searching: {query_jp}")
            
            html = await self.fetch_with_playwright(url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            
            for item_el in soup.select('.itemCard')[:max_results]:
                item = self.parse_item_card(
                    item_el,
                    query_en=query_en,
                    platform='mercari',
                    category=category,
                    brand=brand,
                    weight_kg=weight_kg,
                )
                if item:
                    items.append(item)
            
            logger.info(f"[Mercari] Found {len(items)} items for {query_en}")
            
        except Exception as e:
            logger.error(f"[Mercari] Search error: {e}")
        
        return items


class RakumaScraper(PlaywrightScraper):
    """Scraper for Rakuten Rakuma via Buyee."""
    
    async def search(
        self,
        query_jp: str,
        query_en: str,
        category: str,
        brand: str,
        weight_kg: float,
        max_results: int = 20,
        min_price: int = 10000,
    ) -> List[JapanItem]:
        """Search Rakuma."""
        
        items = []
        
        try:
            url = f"https://buyee.jp/rakuma/search?keyword={query_jp}&sort=created_time&order=desc&price_min={min_price}"
            
            logger.info(f"[Rakuma] Searching: {query_jp}")
            
            html = await self.fetch_with_playwright(url)
            if not html:
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            
            for item_el in soup.select('.itemCard')[:max_results]:
                item = self.parse_item_card(
                    item_el,
                    query_en=query_en,
                    platform='rakuma',
                    category=category,
                    brand=brand,
                    weight_kg=weight_kg,
                )
                if item:
                    items.append(item)
            
            logger.info(f"[Rakuma] Found {len(items)} items for {query_en}")
            
        except Exception as e:
            logger.error(f"[Rakuma] Search error: {e}")
        
        return items


# Convenience functions
async def search_mercari(**kwargs) -> List[JapanItem]:
    """Search Mercari."""
    scraper = MercariScraper()
    return await scraper.search(**kwargs)


async def search_rakuma(**kwargs) -> List[JapanItem]:
    """Search Rakuma."""
    scraper = RakumaScraper()
    return await scraper.search(**kwargs)


if __name__ == "__main__":
    async def test():
        if not HAS_PLAYWRIGHT:
            print("Playwright not installed")
            return
        
        # Test Mercari
        print("Testing Mercari...")
        items = await search_mercari(
            query_jp='クロムハーツ リング',
            query_en='chrome hearts ring',
            category='jewelry',
            brand='Chrome Hearts',
            weight_kg=0.1,
            max_results=5,
        )
        print(f"Found {len(items)} items")
        for item in items[:3]:
            print(f"  - {item.title_jp[:40]}... ¥{item.price_jpy:,}")
    
    asyncio.run(test())

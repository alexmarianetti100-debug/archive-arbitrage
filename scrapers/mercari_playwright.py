"""
Playwright-based scraper for Mercari - bypasses 403 errors with real browser automation.
"""

import asyncio
import re
from typing import Optional, List
from urllib.parse import urlencode

try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("  Playwright not installed. Run: pip install playwright && playwright install chromium")

from .base import BaseScraper, ScrapedItem


class MercariPlaywrightScraper(BaseScraper):
    """Scrape Mercari using Playwright (real browser)."""
    
    SOURCE_NAME = "mercari"
    BASE_URL = "https://www.mercari.com"
    
    MIN_DELAY = 4.0
    MAX_DELAY = 8.0
    
    def __init__(self, proxy_manager=None):
        super().__init__(proxy_manager)
        self.browser = None
        self.context = None
        self.page = None
    
    async def _init_browser(self):
        """Initialize Playwright browser."""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright not installed")
        
        if self.browser:
            return
        
        p = await async_playwright().start()
        
        self.browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/Los_Angeles',
        )
        
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            window.chrome = { runtime: {} };
        """)
        
        self.page = await self.context.new_page()
    
    async def search(
        self,
        query: str,
        max_results: int = 50,
    ) -> List[ScrapedItem]:
        """Search Mercari using Playwright."""
        items = []
        
        try:
            await self._init_browser()
            
            params = {
                "keyword": query,
                "status": "on_sale",
                "sortBy": "created_time",
                "order": "desc",
            }
            search_url = f"{self.BASE_URL}/search/?{urlencode(params)}"
            
            print(f"  Mercari: Navigating to search...")
            await self.page.goto(search_url, wait_until='networkidle', timeout=30000)
            
            # Wait for items to load
            await asyncio.sleep(3)
            
            # Scroll for more results
            for _ in range(3):
                await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(2)
            
            # Extract items using data-testid
            item_elements = await self.page.query_selector_all('[data-testid="ItemCell"], a[href*="/item/"]')
            
            for element in item_elements[:max_results]:
                try:
                    item = await self._parse_element(element)
                    if item:
                        items.append(item)
                except Exception as e:
                    continue
            
            print(f"  Mercari: Found {len(items)} items")
            
        except Exception as e:
            print(f"  Mercari search failed: {e}")
        
        return items
    
    async def _parse_element(self, element) -> Optional[ScrapedItem]:
        """Parse a product element."""
        # Get href
        href = await element.get_attribute('href')
        if not href:
            # Try finding link inside
            link = await element.query_selector('a[href*="/item/"]')
            if link:
                href = await link.get_attribute('href')
        
        if not href or '/item/' not in href:
            return None
        
        # Extract item ID
        item_id_match = re.search(r'/item/m(\d+)', href)
        if not item_id_match:
            return None
        item_id = item_id_match.group(1)
        
        url = f"{self.BASE_URL}/us/item/m{item_id}"
        
        # Get title
        title = ""
        try:
            title_el = await element.query_selector('[data-testid="ItemName"], p[class*="ItemName"]')
            if title_el:
                title = await title_el.inner_text()
            else:
                # Try img alt
                img = await element.query_selector('img')
                if img:
                    title = await img.get_attribute('alt') or f"Mercari Item {item_id}"
        except:
            title = f"Mercari Item {item_id}"
        
        # Get price
        price = 0.0
        try:
            price_el = await element.query_selector('[data-testid="ItemPrice"], span[class*="Price"]')
            if price_el:
                price_text = await price_el.inner_text()
                price = self.parse_price(price_text)
        except:
            pass
        
        # Get image
        images = []
        try:
            img = await element.query_selector('img[src*="mercari"], img[data-src*="mercari"]')
            if img:
                img_url = await img.get_attribute('src') or await img.get_attribute('data-src')
                if img_url:
                    images.append(img_url)
        except:
            pass
        
        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=item_id,
            url=url,
            title=title or f"Mercari Item {item_id}",
            price=price,
            currency="USD",
            size=self.extract_size(title),
            images=images,
            is_auction=False,
        )
    
    async def close(self):
        """Close browser."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
    
    async def __aenter__(self):
        await self._init_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        """Get full details for a specific item."""
        # For now, return None - can be implemented if needed
        return None
    
    async def check_availability(self, item_id: str) -> bool:
        """Check if item is still available."""
        try:
            await self._init_browser()
            url = f"{self.BASE_URL}/us/item/m{item_id}"
            await self.page.goto(url, timeout=10000)
            # Check for sold indicators
            sold_indicator = await self.page.query_selector('text=/sold/i')
            return sold_indicator is None
        except:
            return False

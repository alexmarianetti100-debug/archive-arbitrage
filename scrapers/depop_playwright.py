"""
Playwright-based scraper for Depop - bypasses 403 errors with real browser automation.
"""

import asyncio
import re
from typing import Optional, List
from urllib.parse import quote

try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("  Playwright not installed. Run: pip install playwright && playwright install chromium")

from .base import BaseScraper, ScrapedItem


class DepopPlaywrightScraper(BaseScraper):
    """Scrape Depop using Playwright (real browser)."""
    
    SOURCE_NAME = "depop"
    BASE_URL = "https://www.depop.com"
    
    # Longer delays for browser automation
    MIN_DELAY = 5.0
    MAX_DELAY = 10.0
    
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
        
        # Launch with stealth options
        self.browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        
        # Create context with realistic viewport and user agent
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/Los_Angeles',
        )
        
        # Inject stealth script to hide automation
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
        """Search Depop using Playwright."""
        items = []
        
        try:
            await self._init_browser()
            
            # Navigate to search page
            search_url = f"{self.BASE_URL}/search/?q={quote(query)}"
            print(f"  Depop: Navigating to {search_url[:80]}...")
            
            await self.page.goto(search_url, wait_until='networkidle', timeout=30000)
            
            # Wait for content to load
            await asyncio.sleep(3)
            
            # Scroll to load more items
            for _ in range(3):
                await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(2)
            
            # Extract items
            item_elements = await self.page.query_selector_all('a[href*="/products/"]')
            
            seen_ids = set()
            for element in item_elements[:max_results * 2]:
                try:
                    item = await self._parse_element(element)
                    if item and item.source_id not in seen_ids:
                        seen_ids.add(item.source_id)
                        items.append(item)
                        if len(items) >= max_results:
                            break
                except Exception as e:
                    continue
            
            print(f"  Depop: Found {len(items)} items")
            
        except Exception as e:
            print(f"  Depop search failed: {e}")
        
        return items
    
    async def _parse_element(self, element) -> Optional[ScrapedItem]:
        """Parse a product element."""
        # Get href
        href = await element.get_attribute('href')
        if not href or '/products/' not in href:
            return None
        
        # Extract slug/ID
        match = re.search(r'/products/([^/?]+)', href)
        if not match:
            return None
        slug = match.group(1)
        
        url = f"{self.BASE_URL}/products/{slug}"
        
        # Try to get title from parent
        title = ""
        try:
            parent = await element.query_selector('xpath=..')
            if parent:
                title_el = await parent.query_selector('p, span[class*="title"], span[class*="description"]')
                if title_el:
                    title = await title_el.inner_text()
        except:
            pass
        
        # Get from image alt if no title
        if not title:
            try:
                img = await element.query_selector('img')
                if img:
                    title = await img.get_attribute('alt') or slug.replace('-', ' ')
            except:
                title = slug.replace('-', ' ')
        
        # Get price
        price = 0.0
        try:
            if parent:
                price_el = await parent.query_selector('span[class*="price"], p[class*="price"]')
                if price_el:
                    price_text = await price_el.inner_text()
                    price = self.parse_price(price_text)
        except:
            pass
        
        # Get image
        images = []
        try:
            img = await element.query_selector('img')
            if img:
                img_url = await img.get_attribute('src')
                if img_url:
                    images.append(img_url)
        except:
            pass
        
        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=slug,
            url=url,
            title=title[:200] or f"Depop Item",
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
            url = f"{self.BASE_URL}/products/{item_id}"
            await self.page.goto(url, timeout=10000)
            # Check for sold/unavailable indicators
            sold_indicator = await self.page.query_selector('text=/sold/i')
            return sold_indicator is None
        except:
            return False

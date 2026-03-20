"""
Stealth Browser Scraper for Buyee

Uses playwright-stealth + residential proxies to bypass bot detection.
Robust implementation with retries, fingerprint rotation, and human-like behavior.
"""

import asyncio
import logging
import random
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from bs4 import BeautifulSoup

logger = logging.getLogger("stealth_scraper")

# Playwright imports
try:
    from playwright.async_api import async_playwright, Route, Request
    from playwright_stealth import Stealth
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    logger.warning("Playwright not installed. Stealth scraping disabled.")


@dataclass
class StealthConfig:
    """Configuration for stealth browser."""
    headless: bool = True
    proxy_server: Optional[str] = None  # e.g., "http://user:pass@host:port"
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    timeout_ms: int = 30000
    wait_for_selector: str = ".itemCard"
    wait_timeout_ms: int = 15000
    human_like_delays: bool = True
    block_resources: List[str] = None  # ['image', 'stylesheet', 'font']
    
    def __post_init__(self):
        if self.block_resources is None:
            self.block_resources = ['image', 'stylesheet', 'font', 'media']


class StealthBrowser:
    """Robust stealth browser for scraping JavaScript-rendered pages."""
    
    # Rotating user agents
    USER_AGENTS = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    ]
    
    # Viewport sizes
    VIEWPORTS = [
        {'width': 1280, 'height': 800},
        {'width': 1366, 'height': 768},
        {'width': 1440, 'height': 900},
        {'width': 1920, 'height': 1080},
    ]
    
    def __init__(self, config: Optional[StealthConfig] = None):
        self.config = config or StealthConfig()
        self.browser = None
        self.context = None
        self.page = None
    
    async def __aenter__(self):
        if not HAS_PLAYWRIGHT:
            raise ImportError("Playwright not installed")
        return self
    
    async def __aexit__(self, *args):
        await self.close()
    
    async def close(self):
        """Clean up browser resources."""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.context = None
            self.page = None
    
    async def init_browser(self):
        """Initialize browser with stealth settings."""
        
        async with async_playwright() as p:
            # Browser launch options
            launch_options = {
                'headless': self.config.headless,
                'args': [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                    '--window-size=1280,800',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                ]
            }
            
            # Add proxy if configured
            if self.config.proxy_server:
                launch_options['proxy'] = {
                    'server': self.config.proxy_server,
                }
                if self.config.proxy_username:
                    launch_options['proxy']['username'] = self.config.proxy_username
                if self.config.proxy_password:
                    launch_options['proxy']['password'] = self.config.proxy_password
            
            # Launch browser (Firefox is more stable on macOS)
            try:
                self.browser = await p.firefox.launch(**launch_options)
            except Exception as e:
                logger.warning(f"Firefox launch failed: {e}, trying Chromium")
                self.browser = await p.chromium.launch(**launch_options)
            
            # Randomize viewport
            viewport = random.choice(self.VIEWPORTS)
            user_agent = random.choice(self.USER_AGENTS)
            
            # Create context with stealth settings
            context_options = {
                'viewport': viewport,
                'user_agent': user_agent,
                'locale': 'ja-JP',
                'timezone_id': 'Asia/Tokyo',
                'permissions': ['geolocation'],
                'geolocation': {'latitude': 35.6762, 'longitude': 139.6503},  # Tokyo
                'color_scheme': 'light',
                'reduced_motion': 'no-preference',
            }
            
            self.context = await self.browser.new_context(**context_options)
            
            # Create page
            self.page = await self.context.new_page()
            
            # Apply stealth patches
            stealth = Stealth()
            await stealth.apply_stealth_async(self.page)
            
            # Block unnecessary resources for speed
            if self.config.block_resources:
                await self.page.route(
                    "**/*",
                    lambda route, request: self._block_resources(route, request)
                )
            
            logger.debug(f"Browser initialized with viewport {viewport}")
    
    async def _block_resources(self, route: Route, request: Request):
        """Block unnecessary resources to speed up loading."""
        if request.resource_type in self.config.block_resources:
            await route.abort()
        else:
            await route.continue_()
    
    async def human_like_delay(self, min_ms: int = 500, max_ms: int = 2000):
        """Add random delay to mimic human behavior."""
        if self.config.human_like_delays:
            delay = random.randint(min_ms, max_ms)
            await asyncio.sleep(delay / 1000)
    
    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch page content with stealth and retries."""
        
        if not self.browser:
            await self.init_browser()
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Random delay before navigation
                await self.human_like_delay(1000, 3000)
                
                # Navigate to page
                response = await self.page.goto(
                    url,
                    wait_until='domcontentloaded',
                    timeout=self.config.timeout_ms
                )
                
                if response.status >= 400:
                    logger.warning(f"HTTP {response.status} for {url}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    return None
                
                # Wait for content to load
                await self.human_like_delay(1000, 2000)
                
                # Wait for specific selector
                try:
                    await self.page.wait_for_selector(
                        self.config.wait_for_selector,
                        timeout=self.config.wait_timeout_ms
                    )
                except Exception:
                    logger.debug(f"Selector {self.config.wait_for_selector} not found")
                
                # Scroll down to trigger lazy loading
                await self._scroll_page()
                
                # Get page content
                html = await self.page.content()
                
                return html
                
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return None
        
        return None
    
    async def _scroll_page(self):
        """Scroll page to mimic human behavior and trigger lazy loading."""
        try:
            # Scroll down in increments
            for _ in range(3):
                await self.page.evaluate("window.scrollBy(0, 300)")
                await self.human_like_delay(300, 800)
        except Exception:
            pass


class BuyeeStealthScraper:
    """Stealth scraper specifically for Buyee platforms."""
    
    def __init__(self, proxy_server: Optional[str] = None):
        self.config = StealthConfig(
            headless=True,
            proxy_server=proxy_server,
            wait_for_selector='.itemCard',
            wait_timeout_ms=15000,
        )
    
    async def search_mercari(
        self,
        query_jp: str,
        query_en: str,
        category: str,
        brand: str,
        weight_kg: float,
        max_results: int = 20,
        min_price_jpy: int = 10000,
    ) -> List[Dict[str, Any]]:
        """Search Mercari via Buyee using stealth browser."""
        
        items = []
        
        try:
            # Build URL
            params = f"keyword={query_jp}&sort=created_time&order=desc"
            if min_price_jpy:
                params += f"&price_min={min_price_jpy}"
            url = f"https://buyee.jp/mercari/search?{params}"
            
            logger.info(f"[Stealth] Searching Mercari: {query_jp}")
            
            async with StealthBrowser(self.config) as browser:
                html = await browser.fetch_page(url)
                
                if not html:
                    logger.warning(f"Failed to fetch Mercari page for {query_en}")
                    return []
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                
                for item_el in soup.select('.itemCard')[:max_results]:
                    try:
                        item = self._parse_item_card(
                            item_el,
                            query_en=query_en,
                            category=category,
                            brand=brand,
                            weight_kg=weight_kg,
                        )
                        if item:
                            items.append(item)
                    except Exception as e:
                        logger.debug(f"Error parsing item: {e}")
                        continue
                
                logger.info(f"[Stealth] Found {len(items)} Mercari items for {query_en}")
                
        except Exception as e:
            logger.error(f"[Stealth] Mercari search error: {e}")
        
        return items
    
    async def search_rakuma(
        self,
        query_jp: str,
        query_en: str,
        category: str,
        brand: str,
        weight_kg: float,
        max_results: int = 20,
        min_price_jpy: int = 10000,
    ) -> List[Dict[str, Any]]:
        """Search Rakuma via Buyee using stealth browser."""
        
        items = []
        
        try:
            # Build URL
            params = f"keyword={query_jp}&sort=created_time&order=desc"
            if min_price_jpy:
                params += f"&price_min={min_price_jpy}"
            url = f"https://buyee.jp/rakuma/search?{params}"
            
            logger.info(f"[Stealth] Searching Rakuma: {query_jp}")
            
            async with StealthBrowser(self.config) as browser:
                html = await browser.fetch_page(url)
                
                if not html:
                    logger.warning(f"Failed to fetch Rakuma page for {query_en}")
                    return []
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                
                for item_el in soup.select('.itemCard')[:max_results]:
                    try:
                        item = self._parse_item_card(
                            item_el,
                            query_en=query_en,
                            category=category,
                            brand=brand,
                            weight_kg=weight_kg,
                        )
                        if item:
                            items.append(item)
                    except Exception as e:
                        logger.debug(f"Error parsing item: {e}")
                        continue
                
                logger.info(f"[Stealth] Found {len(items)} Rakuma items for {query_en}")
                
        except Exception as e:
            logger.error(f"[Stealth] Rakuma search error: {e}")
        
        return items
    
    def _parse_item_card(
        self,
        item_el,
        query_en: str,
        category: str,
        brand: str,
        weight_kg: float,
    ) -> Optional[Dict[str, Any]]:
        """Parse an item card element."""
        
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
        price_jpy = self._parse_jpy_price(price_text)
        
        if not price_jpy or price_jpy < 10000:
            return None
        
        # URL and ID
        item_id = ""
        item_url = ""
        if title_el.get('href'):
            href = title_el['href']
            item_id = href.split('/')[-1].split('?')[0]
            item_url = f"https://buyee.jp{href}" if not href.startswith('http') else href
        
        # Image
        img_el = item_el.select_one('.g-thumbnail__image')
        image_url = img_el.get('data-src') if img_el else None
        
        return {
            'title_jp': title_jp,
            'title_en': query_en,
            'price_jpy': price_jpy,
            'item_id': item_id,
            'item_url': item_url,
            'image_url': image_url,
            'category': category,
            'brand': brand,
            'weight_kg': weight_kg,
        }
    
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


# Convenience function for testing
async def test_stealth_scraper(proxy: Optional[str] = None):
    """Test the stealth scraper."""
    scraper = BuyeeStealthScraper(proxy_server=proxy)
    
    # Test Mercari
    items = await scraper.search_mercari(
        query_jp='クロムハーツ リング',
        query_en='chrome hearts ring',
        category='jewelry',
        brand='Chrome Hearts',
        weight_kg=0.1,
        max_results=5,
    )
    
    print(f"Found {len(items)} items")
    for item in items[:3]:
        print(f"  - {item['title_jp'][:40]}... ¥{item['price_jpy']:,}")
    
    return items


if __name__ == "__main__":
    if not HAS_PLAYWRIGHT:
        print("Playwright not installed. Install with: pip install playwright")
        exit(1)
    
    # Test without proxy first
    print("Testing without proxy...")
    asyncio.run(test_stealth_scraper())

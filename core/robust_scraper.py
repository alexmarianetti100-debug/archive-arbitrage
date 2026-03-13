"""
Robust Stealth Scraper for Japan Sites

Uses Playwright with Webshare proxies, headful mode, and mercapi fallback.
Designed for reliability and cost-effectiveness.
"""

import asyncio
import logging
import random
from typing import List, Optional, Dict, Any
from datetime import datetime

from bs4 import BeautifulSoup

from core.mercari_urls import mercari_item_url
from core.proxy_pool import get_proxy_pool, Proxy

logger = logging.getLogger("robust_stealth")

# Playwright imports
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    logger.warning("Playwright not installed")

# Mercari direct API fallback
try:
    from core.mercari_direct import MercariDirectScraper, HAS_MERCAPI
except ImportError:
    HAS_MERCAPI = False


class RobustStealthScraper:
    """Robust scraper with proxy rotation and fallback strategies."""
    
    # Rotating user agents (desktop browsers)
    USER_AGENTS = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    ]
    
    VIEWPORTS = [
        {'width': 1280, 'height': 800},
        {'width': 1366, 'height': 768},
        {'width': 1440, 'height': 900},
    ]
    
    def __init__(self, use_proxies: bool = True, headful: bool = False):
        self.use_proxies = use_proxies
        self.headful = headful
        self.proxy_pool = get_proxy_pool() if use_proxies else None
        self.seen_items: set = set()
    
    async def fetch_with_stealth(
        self,
        url: str,
        domain: str = "default",
        wait_selector: str = '.itemCard',
        timeout: int = 30,
    ) -> Optional[str]:
        """
        Fetch page using Playwright with proxy rotation.
        Retries with different proxies on failure.
        """
        
        if not HAS_PLAYWRIGHT:
            logger.warning("Playwright not available")
            return None
        
        max_retries = self.proxy_pool.retry_attempts if self.proxy_pool else 2
        
        for attempt in range(max_retries):
            proxy = None
            
            try:
                # Get proxy for this attempt
                if self.proxy_pool:
                    proxy = self.proxy_pool.get_proxy_for_domain(domain)
                    if proxy:
                        logger.debug(f"Using proxy {proxy.id} for {domain}")
                
                # Try to fetch
                html = await self._fetch_single(
                    url=url,
                    proxy=proxy,
                    wait_selector=wait_selector,
                    timeout=timeout,
                )
                
                if html:
                    # Success
                    if proxy:
                        self.proxy_pool.mark_success(proxy.id)
                    return html
                
                # Empty result, try next proxy
                if proxy:
                    self.proxy_pool.mark_failure(proxy.id)
                
            except Exception as e:
                logger.error(f"Fetch attempt {attempt + 1} failed: {e}")
                if proxy:
                    # Check if it's a blocking error
                    is_blocking = '403' in str(e) or '429' in str(e)
                    self.proxy_pool.mark_failure(proxy.id, is_blocking)
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        logger.error(f"All {max_retries} fetch attempts failed for {url}")
        return None
    
    async def _fetch_single(
        self,
        url: str,
        proxy: Optional[Proxy],
        wait_selector: str,
        timeout: int,
    ) -> Optional[str]:
        """Single fetch attempt with Playwright."""
        
        async with async_playwright() as p:
            # Browser launch options
            launch_options = {
                'headless': not self.headful,  # Headful mode preferred
                'args': [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--window-size=1280,800',
                ]
            }
            
            # Add proxy if available
            if proxy:
                launch_options['proxy'] = {
                    'server': f"{proxy.type}://{proxy.host}:{proxy.port}",
                    'username': proxy.username,
                    'password': proxy.password,
                }
            
            # Launch browser (Firefox is more stable)
            try:
                browser = await p.firefox.launch(**launch_options)
            except Exception as e:
                logger.warning(f"Firefox failed: {e}, trying Chromium")
                browser = await p.chromium.launch(**launch_options)
            
            try:
                # Randomize viewport and user agent
                viewport = random.choice(self.VIEWPORTS)
                user_agent = random.choice(self.USER_AGENTS)
                
                # Create context
                context = await browser.new_context(
                    viewport=viewport,
                    user_agent=user_agent,
                    locale='ja-JP',
                    timezone_id='Asia/Tokyo',
                )
                
                page = await context.new_page()
                
                # Block unnecessary resources for speed
                await page.route(
                    "**/*",
                    lambda route, request: self._block_resources(route, request)
                )
                
                # Navigate
                logger.debug(f"Navigating to {url}")
                response = await page.goto(
                    url,
                    wait_until='domcontentloaded',
                    timeout=timeout * 1000
                )
                
                if response.status >= 400:
                    raise Exception(f"HTTP {response.status}")
                
                # Wait for JavaScript
                await asyncio.sleep(3)
                
                # Wait for content
                try:
                    await page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    logger.debug(f"Selector {wait_selector} not found, continuing")
                
                # Scroll to trigger lazy loading
                await self._scroll_page(page)
                
                # Get content
                html = await page.content()
                
                return html
                
            finally:
                await browser.close()
    
    async def _block_resources(self, route, request):
        """Block heavy resources to speed up loading."""
        resource_type = request.resource_type
        if resource_type in ['image', 'stylesheet', 'font', 'media']:
            await route.abort()
        else:
            await route.continue_()
    
    async def _scroll_page(self, page):
        """Scroll page to mimic human behavior."""
        try:
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 300)")
                await asyncio.sleep(random.uniform(0.3, 0.8))
        except Exception:
            pass


class MercariRobustScraper:
    """Mercari scraper with stealth + mercapi fallback."""
    
    def __init__(self, use_proxies: bool = True):
        self.stealth = RobustStealthScraper(use_proxies=use_proxies, headful=False)
        self.seen_items: set = set()
    
    async def search(
        self,
        query_jp: str,
        query_en: str,
        category: str,
        brand: str,
        weight_kg: float,
        max_results: int = 20,
        min_price_jpy: int = 10000,
    ) -> List[Dict[str, Any]]:
        """
        Search Mercari with fallback strategy:
        1. Try direct Mercari API first (most reliable)
        2. Fallback to stealth scraping via Buyee if needed
        """

        items = []

        # Try 1: Direct Mercari API (bypasses Buyee proxy blocking issues)
        if HAS_MERCAPI:
            try:
                logger.info(f"[Mercari] Trying direct API for: {query_jp}")

                async with MercariDirectScraper() as scraper:
                    direct_items = await scraper.search(
                        query_jp=query_jp,
                        query_en=query_en,
                        category=category,
                        brand=brand,
                        weight_kg=weight_kg,
                        max_results=max_results,
                        min_price_jpy=min_price_jpy,
                    )

                    for item in direct_items:
                        if item.item_id not in self.seen_items:
                            self.seen_items.add(item.item_id)
                            items.append({
                                'title_jp': item.title_jp,
                                'title_en': item.title_en,
                                'price_jpy': item.price_jpy,
                                'item_id': item.item_id,
                                'item_url': item.item_url,
                                'image_url': item.image_url,
                                'category': item.category,
                                'brand': item.brand,
                                'weight_kg': item.weight_kg,
                                'platform': 'mercari_direct',
                            })

                    if items:
                        logger.info(f"[Mercari] Direct API found {len(items)} items")
                        return items

            except Exception as e:
                logger.warning(f"[Mercari] Direct API failed: {e}")

        # Try 2: Stealth scraping via Buyee (fallback)
        try:
            logger.info(f"[Mercari] Trying stealth for: {query_jp}")

            url = f"https://buyee.jp/mercari/search?keyword={query_jp}&sort=created_time&order=desc&price_min={min_price_jpy}"

            html = await self.stealth.fetch_with_stealth(
                url=url,
                domain='buyee-mercari',
                wait_selector='.itemCard',
            )

            if html:
                soup = BeautifulSoup(html, 'html.parser')

                for item_el in soup.select('.itemCard')[:max_results]:
                    item = self._parse_item(item_el, query_en, category, brand, weight_kg)
                    if item and item['item_id'] not in self.seen_items:
                        self.seen_items.add(item['item_id'])
                        items.append(item)

                if items:
                    logger.info(f"[Mercari] Stealth found {len(items)} items")
                    return items

        except Exception as e:
            logger.warning(f"[Mercari] Stealth failed: {e}")
        
        # Try 2: Direct Mercari API fallback
        if HAS_MERCAPI:
            try:
                logger.info(f"[Mercari] Falling back to direct API for: {query_jp}")
                
                async with MercariDirectScraper() as scraper:
                    direct_items = await scraper.search(
                        query_jp=query_jp,
                        query_en=query_en,
                        category=category,
                        brand=brand,
                        weight_kg=weight_kg,
                        max_results=max_results,
                        min_price_jpy=min_price_jpy,
                    )
                    
                    for item in direct_items:
                        if item.item_id not in self.seen_items:
                            self.seen_items.add(item.item_id)
                            items.append({
                                'title_jp': item.title_jp,
                                'title_en': item.title_en,
                                'price_jpy': item.price_jpy,
                                'item_id': item.item_id,
                                'item_url': item.item_url,
                                'image_url': item.image_url,
                                'category': item.category,
                                'brand': item.brand,
                                'weight_kg': item.weight_kg,
                                'platform': 'mercari_direct',
                            })
                    
                    if items:
                        logger.info(f"[Mercari] Direct API found {len(items)} items")
                        return items
                    
            except Exception as e:
                logger.error(f"[Mercari] Direct API failed: {e}")
        
        logger.warning(f"[Mercari] All methods failed for {query_en}")
        return []
    
    def _parse_item(self, item_el, query_en, category, brand, weight_kg) -> Optional[Dict]:
        """Parse item from HTML."""
        try:
            title_el = item_el.select_one('.itemCard__itemName a')
            if not title_el:
                return None
            
            price_el = item_el.select_one('.g-price')
            if not price_el:
                return None
            
            price_text = price_el.get_text()
            price_jpy = int(''.join(c for c in price_text if c.isdigit()))
            
            if price_jpy < 10000:
                return None
            
            href = title_el.get('href', '')
            item_id = href.split('/')[-1].split('?')[0]
            
            img_el = item_el.select_one('.g-thumbnail__image')
            image_url = img_el.get('data-src') if img_el else None
            
            return {
                'title_jp': title_el.get_text(strip=True),
                'title_en': query_en,
                'price_jpy': price_jpy,
                'item_id': item_id,
                'item_url': mercari_item_url(item_id or href),
                'image_url': image_url,
                'category': category,
                'brand': brand,
                'weight_kg': weight_kg,
                'platform': 'mercari_stealth',
            }
        except Exception:
            return None


# Convenience function
async def search_mercari_robust(**kwargs) -> List[Dict[str, Any]]:
    """Search Mercari with robust fallback."""
    scraper = MercariRobustScraper(use_proxies=True)
    return await scraper.search(**kwargs)


if __name__ == "__main__":
    async def test():
        print("Testing robust Mercari scraper...")
        
        items = await search_mercari_robust(
            query_jp='クロムハーツ リング',
            query_en='chrome hearts ring',
            category='jewelry',
            brand='Chrome Hearts',
            weight_kg=0.1,
            max_results=10,
        )
        
        print(f"Found {len(items)} items")
        for item in items[:5]:
            print(f"  - {item['title_jp'][:40]}... ¥{item['price_jpy']:,} ({item['platform']})")
    
    asyncio.run(test())

"""
Mercari scraper using Playwright with DOM extraction.
Mercari blocks direct HTTP requests (403) but Playwright with domcontentloaded works.
"""

import asyncio
import re
import logging
from typing import List, Optional
from urllib.parse import urlencode

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .base import BaseScraper, ScrapedItem

logger = logging.getLogger("scraper.mercari")


class MercariScraper(BaseScraper):
    """Scrape Mercari using Playwright DOM extraction."""

    SOURCE_NAME = "mercari"
    BASE_URL = "https://www.mercari.com"
    MIN_DELAY = 4.0
    MAX_DELAY = 8.0

    def __init__(self, proxy_manager=None):
        super().__init__(proxy_manager)
        self._playwright = None
        self._browser = None

    async def _ensure_browser(self):
        if self._browser:
            return
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright not installed. Run: pip install playwright && playwright install chromium")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
            ]
        )

    async def _new_page(self):
        ctx = await self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
        )
        await ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            window.chrome = { runtime: {} };
        """)
        return await ctx.new_page()

    async def search(self, query: str, max_results: int = 20) -> List[ScrapedItem]:
        """Search Mercari and extract items from DOM."""
        items = []
        try:
            await self._ensure_browser()
            page = await self._new_page()

            url = f"{self.BASE_URL}/search/?keyword={query.replace(' ', '+')}"
            logger.info(f"  Mercari: Navigating to search...")

            await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            # Wait for items to render
            await asyncio.sleep(4)

            # Scroll to load more
            for _ in range(2):
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(2)

            # Extract items via DOM - find all item links
            raw_items = await page.evaluate('''() => {
                const results = [];
                // Find all links to item pages
                const links = document.querySelectorAll('a[href*="/item/"]');
                const seen = new Set();
                
                for (const link of links) {
                    const href = link.getAttribute('href') || '';
                    const match = href.match(/\\/item\\/([a-zA-Z0-9]+)/);
                    if (!match) continue;
                    const itemId = match[1];
                    if (seen.has(itemId)) continue;
                    seen.add(itemId);
                    
                    // Get the card container (walk up to find a reasonable parent)
                    let container = link;
                    for (let i = 0; i < 5; i++) {
                        if (container.parentElement) container = container.parentElement;
                    }
                    
                    const text = link.innerText || container.innerText || '';
                    
                    // Extract price - look for $ pattern
                    const priceMatch = text.match(/\\$([\\d,.]+)/);
                    const price = priceMatch ? parseFloat(priceMatch[1].replace(',', '')) : 0;
                    
                    // Extract title - first meaningful line
                    const lines = text.split('\\n').map(l => l.trim()).filter(l => l.length > 5 && !l.startsWith('$'));
                    const title = lines[0] || '';
                    
                    // Get image
                    const img = link.querySelector('img') || container.querySelector('img');
                    const imgSrc = img ? (img.getAttribute('src') || img.getAttribute('data-src') || '') : '';
                    
                    if (title || price > 0) {
                        results.push({
                            id: itemId,
                            title: title.substring(0, 200),
                            price: price,
                            image: imgSrc,
                            href: href,
                        });
                    }
                }
                return results;
            }''')

            for raw in raw_items[:max_results]:
                item_id = raw.get('id', '')
                title = raw.get('title', '')
                price = raw.get('price', 0)
                image = raw.get('image', '')
                href = raw.get('href', '')

                if not title and not price:
                    continue

                url = f"{self.BASE_URL}/us/item/{item_id}/" if item_id else f"{self.BASE_URL}{href}"

                items.append(ScrapedItem(
                    source=self.SOURCE_NAME,
                    source_id=item_id,
                    url=url,
                    title=title or f"Mercari Item {item_id}",
                    price=float(price) if price else 0.0,
                    currency="USD",
                    images=[image] if image else [],
                    raw_data={'mercari_id': item_id},
                ))

            logger.info(f"  Mercari: Found {len(items)} items for '{query}'")
            await page.context.close()

        except Exception as e:
            logger.warning(f"  Mercari search failed: {e}")

        return items

    async def search_sold(self, query: str, max_results: int = 20) -> List[ScrapedItem]:
        """Search sold items on Mercari."""
        items = []
        try:
            await self._ensure_browser()
            page = await self._new_page()

            url = f"{self.BASE_URL}/search/?keyword={query.replace(' ', '+')}&status=sold_out"
            await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(4)

            raw_items = await page.evaluate('''() => {
                const results = [];
                const links = document.querySelectorAll('a[href*="/item/"]');
                const seen = new Set();
                for (const link of links) {
                    const href = link.getAttribute('href') || '';
                    const match = href.match(/\\/item\\/([a-zA-Z0-9]+)/);
                    if (!match) continue;
                    const itemId = match[1];
                    if (seen.has(itemId)) continue;
                    seen.add(itemId);
                    const text = link.innerText || '';
                    const priceMatch = text.match(/\\$([\\d,.]+)/);
                    const price = priceMatch ? parseFloat(priceMatch[1].replace(',', '')) : 0;
                    const lines = text.split('\\n').map(l => l.trim()).filter(l => l.length > 5 && !l.startsWith('$'));
                    const title = lines[0] || '';
                    const img = link.querySelector('img');
                    const imgSrc = img ? (img.getAttribute('src') || '') : '';
                    if (title || price > 0) {
                        results.push({ id: itemId, title: title.substring(0, 200), price, image: imgSrc });
                    }
                }
                return results;
            }''')

            for raw in raw_items[:max_results]:
                items.append(ScrapedItem(
                    source=self.SOURCE_NAME,
                    source_id=raw.get('id', ''),
                    url=f"{self.BASE_URL}/us/item/{raw.get('id', '')}/",
                    title=raw.get('title', ''),
                    price=float(raw.get('price', 0)),
                    currency="USD",
                    images=[raw['image']] if raw.get('image') else [],
                    raw_data={'mercari_id': raw.get('id', '')},
                ))

            logger.info(f"  Mercari: Found {len(items)} sold items for '{query}'")
            await page.context.close()

        except Exception as e:
            logger.warning(f"  Mercari sold search failed: {e}")

        return items

    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        return None

    async def check_availability(self, item_id: str) -> bool:
        return True

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

"""
Depop scraper using Playwright API interception.
Depop's DOM is heavily React-based and hard to parse, but we can intercept
the internal API calls the frontend makes and extract structured data.
"""

import asyncio
import json
import logging
import re
from typing import List, Optional

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .base import BaseScraper, ScrapedItem

logger = logging.getLogger("scraper.depop")


class DepopScraper(BaseScraper):
    """Scrape Depop by intercepting API responses via Playwright."""

    SOURCE_NAME = "depop"
    BASE_URL = "https://www.depop.com"
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
            raise ImportError("Playwright not installed")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled'],
        )

    async def _new_context(self):
        ctx = await self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
        )
        await ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
        """)
        return ctx

    async def search(self, query: str, max_results: int = 20) -> List[ScrapedItem]:
        """Search Depop by intercepting API responses."""
        items = []
        api_products = []

        try:
            await self._ensure_browser()
            ctx = await self._new_context()
            page = await ctx.new_page()

            # Intercept API responses containing product data
            async def capture_response(response):
                url = response.url
                try:
                    if any(x in url for x in ['search/products', 'search', '/api/v2/', '/api/v3/']):
                        ct = response.headers.get('content-type', '')
                        if 'json' in ct:
                            data = await response.json()
                            if isinstance(data, dict):
                                products = data.get('products', data.get('items', data.get('data', [])))
                                if isinstance(products, list):
                                    api_products.extend(products)
                except:
                    pass

            page.on('response', capture_response)

            search_url = f"{self.BASE_URL}/search/?q={query.replace(' ', '+')}"
            logger.info(f"  Depop: Navigating to search...")

            await page.goto(search_url, wait_until='domcontentloaded', timeout=20000)
            await asyncio.sleep(4)

            # Scroll to trigger more API loads
            for _ in range(2):
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(2)

            # If API intercept worked, parse those
            if api_products:
                for p in api_products[:max_results]:
                    item = self._parse_api_product(p)
                    if item:
                        items.append(item)
                logger.info(f"  Depop: Found {len(items)} items via API intercept for '{query}'")
            else:
                # Fallback: try to extract from __NEXT_DATA__ or page script tags
                next_data = await page.evaluate('''() => {
                    const el = document.getElementById('__NEXT_DATA__');
                    if (el) return el.textContent;
                    // Also try window.__INITIAL_STATE__
                    if (window.__INITIAL_STATE__) return JSON.stringify(window.__INITIAL_STATE__);
                    return null;
                }''')

                if next_data:
                    try:
                        data = json.loads(next_data)
                        products = self._extract_products_from_next_data(data)
                        for p in products[:max_results]:
                            item = self._parse_api_product(p)
                            if item:
                                items.append(item)
                        logger.info(f"  Depop: Found {len(items)} items via __NEXT_DATA__ for '{query}'")
                    except json.JSONDecodeError:
                        pass

                if not items:
                    # Last resort: DOM extraction
                    items = await self._extract_from_dom(page, max_results)
                    logger.info(f"  Depop: Found {len(items)} items via DOM for '{query}'")

            await ctx.close()

        except Exception as e:
            logger.warning(f"  Depop search failed: {e}")

        return items

    def _parse_api_product(self, product: dict) -> Optional[ScrapedItem]:
        """Parse a product from Depop's API response."""
        try:
            product_id = str(product.get('id', product.get('slug', '')))
            if not product_id:
                return None

            # Price
            price_data = product.get('price', {})
            if isinstance(price_data, dict):
                price = float(price_data.get('priceAmount', price_data.get('amount', 0)))
                currency = price_data.get('currencyName', price_data.get('currency', 'USD'))
            elif isinstance(price_data, (int, float)):
                price = float(price_data)
                currency = "USD"
            else:
                price = 0.0
                currency = "USD"

            # Title/description
            title = product.get('description', product.get('title', product.get('slug', '')))
            if isinstance(title, str) and len(title) > 200:
                title = title[:200]

            # Images
            images = []
            preview = product.get('preview', {})
            if isinstance(preview, dict):
                for size_key in ['960', '640', '320', 'url']:
                    if preview.get(size_key):
                        images.append(preview[size_key])
                        break
            pictures = product.get('pictures', product.get('images', []))
            for pic in pictures[:5]:
                if isinstance(pic, dict):
                    url = pic.get('url') or pic.get('960') or pic.get('640', '')
                    if url:
                        images.append(url)
                elif isinstance(pic, str):
                    images.append(pic)

            # Slug for URL
            slug = product.get('slug', product_id)
            seller = product.get('seller', {})
            seller_slug = ''
            if isinstance(seller, dict):
                seller_slug = seller.get('slug', seller.get('username', ''))

            url = f"{self.BASE_URL}/products/{slug}"

            # Size
            size = product.get('size', '')
            if isinstance(size, dict):
                size = size.get('name', size.get('value', ''))

            # Brand
            brand = product.get('brand', '')
            if isinstance(brand, dict):
                brand = brand.get('name', '')

            return ScrapedItem(
                source=self.SOURCE_NAME,
                source_id=str(product_id),
                url=url,
                title=title or f"Depop Item {product_id}",
                price=price,
                currency=currency,
                brand=brand if isinstance(brand, str) else '',
                size=str(size) if size else None,
                images=images[:5],
                seller=seller_slug,
                raw_data=product,
            )
        except Exception as e:
            logger.debug(f"Error parsing Depop product: {e}")
            return None

    def _extract_products_from_next_data(self, data: dict) -> list:
        """Recursively find product arrays in __NEXT_DATA__."""
        products = []

        def _search(obj, depth=0):
            if depth > 8:
                return
            if isinstance(obj, dict):
                # Look for product-like keys
                if 'products' in obj:
                    val = obj['products']
                    if isinstance(val, list):
                        products.extend(val)
                elif 'items' in obj and isinstance(obj['items'], list):
                    for item in obj['items']:
                        if isinstance(item, dict) and ('price' in item or 'slug' in item):
                            products.append(item)
                else:
                    for v in obj.values():
                        _search(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    _search(item, depth + 1)

        _search(data)
        return products

    async def _extract_from_dom(self, page, max_results: int) -> List[ScrapedItem]:
        """Last resort: extract whatever we can from the DOM."""
        items = []
        raw = await page.evaluate('''() => {
            const results = [];
            document.querySelectorAll('a[href*="/products/"]').forEach(el => {
                const href = el.getAttribute('href') || '';
                const match = href.match(/\\/products\\/([^/?]+)/);
                if (!match) return;
                const slug = match[1];
                
                // Walk up to find price/title context
                let container = el.closest('li') || el.parentElement?.parentElement || el;
                const text = container.innerText || '';
                
                const priceMatch = text.match(/[£$€]([\\d,.]+)/);
                const price = priceMatch ? parseFloat(priceMatch[1].replace(',', '')) : 0;
                
                const img = el.querySelector('img');
                const imgSrc = img ? (img.src || img.dataset.src || '') : '';
                
                results.push({
                    slug: slug,
                    text: text.substring(0, 200),
                    price: price,
                    image: imgSrc,
                });
            });
            return results;
        }''')

        seen = set()
        for r in raw[:max_results]:
            slug = r.get('slug', '')
            if not slug or slug in seen:
                continue
            seen.add(slug)
            items.append(ScrapedItem(
                source=self.SOURCE_NAME,
                source_id=slug,
                url=f"{self.BASE_URL}/products/{slug}",
                title=r.get('text', slug.replace('-', ' '))[:200],
                price=float(r.get('price', 0)),
                currency="USD",
                images=[r['image']] if r.get('image') else [],
            ))

        return items

    async def search_sold(self, query: str, max_results: int = 20) -> List[ScrapedItem]:
        """Depop doesn't easily expose sold items - return empty."""
        return []

    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        return None

    async def check_availability(self, item_id: str) -> bool:
        return True

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

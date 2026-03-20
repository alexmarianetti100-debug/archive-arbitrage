"""
2nd STREET Japan scraper — corporate secondhand chain via Playwright.

2nd STREET has 900+ physical stores in Japan feeding one online inventory.
Corporate pricing formulas don't understand archive value, creating massive
arbitrage opportunities. JPY weakness adds 20-30% structural discount.

Uses Playwright browser for the English site (en.2ndstreet.jp) since it
uses Akamai anti-bot that blocks standard HTTP requests.
"""

import asyncio
import logging
import re
from typing import Optional

from .base import BaseScraper, ScrapedItem

logger = logging.getLogger("secondstreet_scraper")

CONDITION_MAP = {
    "s": "NEW_WITH_TAGS",
    "a": "LIKE_NEW",
    "b": "GENTLY_USED",
    "c": "WELL_WORN",
    "d": "WELL_WORN",
}


class SecondStreetScraper(BaseScraper):
    """Scraper for 2nd STREET Japan (English site) via Playwright."""

    SOURCE_NAME = "2ndstreet"
    BASE_URL = "https://en.2ndstreet.jp"

    MIN_DELAY = 2.0
    MAX_DELAY = 4.0

    def __init__(self, headless: bool = True, use_proxies: bool = False):
        super().__init__(headless=headless, use_proxies=use_proxies)
        self._browser = None
        self._context = None
        self._playwright = None

    async def setup(self):
        """Launch Playwright browser."""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.firefox.launch(headless=self.headless)
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1440, "height": 900},
                locale="en-US",
            )
        except ImportError:
            logger.warning("Playwright not installed — 2ndSTREET scraper disabled")
            self._browser = None
        except Exception as e:
            logger.error(f"2ndSTREET Playwright setup error: {e}")
            self._browser = None

    async def teardown(self):
        """Close browser."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def search(self, query: str, max_results: int = 50) -> list[ScrapedItem]:
        """Search 2nd STREET using Playwright browser."""
        if not self._browser:
            logger.debug("2ndSTREET: Browser not available, skipping")
            return []

        url = f"{self.BASE_URL}/search?keyword={query.replace(' ', '+')}"
        logger.info(f"2ndSTREET: Searching '{query}' via Playwright")

        try:
            page = await self._context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Wait for product content
            try:
                await page.wait_for_selector(".itemCard, a[href*='/goods/detail/']", timeout=10000)
            except Exception:
                logger.debug("2ndSTREET: No product cards found")
                await page.close()
                return []

            # Extract product data — 2nd STREET uses .itemCard with /goods/detail/ links
            items = await page.evaluate("""() => {
                const products = [];
                const cards = document.querySelectorAll('.itemCard');

                cards.forEach(card => {
                    try {
                        const link = card.querySelector('a[href*="/goods/detail/"]');
                        if (!link) return;
                        const href = link.getAttribute('href') || '';

                        // Full card text: "CHROME HEARTS Long sleeve.../M/Cotton/... Size M Item Condition: Used D ¥54,890"
                        const fullText = card.textContent.trim().replace(/\\s+/g, ' ');

                        const imgEl = card.querySelector('img');
                        const image = imgEl?.src || imgEl?.getAttribute('data-src') || '';

                        // Price (¥XX,XXX)
                        const priceMatch = fullText.match(/¥([\\d,]+)/);
                        const price = priceMatch ? priceMatch[1] : '';

                        // Condition (Used S/A/B/C/D)
                        const condMatch = fullText.match(/(?:Condition)[:\\s]*(?:Used\\s*)?([SABCD])/i);
                        const condition = condMatch ? condMatch[1] : '';

                        // Size
                        const sizeMatch = fullText.match(/Size[\\s:]*([A-Z0-9]+)/i);
                        const size = sizeMatch ? sizeMatch[1] : '';

                        // Brand — first segment before /
                        const brand = fullText.split('/')[0].trim();

                        products.push({
                            url: href,
                            text: fullText.slice(0, 200),
                            brand: brand,
                            price: price,
                            image: image,
                            condition: condition,
                            size: size,
                        });
                    } catch(e) {}
                });
                return products;
            }""")

            await page.close()

            parsed = []
            for raw in items[:max_results]:
                item = self._parse_browser_item(raw)
                if item and item.price > 0:
                    parsed.append(item)

            logger.info(f"2ndSTREET: Found {len(parsed)} items for '{query}'")
            return parsed

        except Exception as e:
            logger.error(f"2ndSTREET search error: {type(e).__name__}: {e}")
            try:
                await page.close()
            except Exception:
                pass
            return []

    def _parse_browser_item(self, raw: dict) -> Optional[ScrapedItem]:
        """Parse a product dict from browser DOM."""
        href = raw.get("url", "")
        if not href:
            return None

        url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        # Source ID from URL (/goods/detail/goodsId/XXXX/shopsId/YYYY)
        id_match = re.search(r'goodsId/(\d+)', href)
        source_id = id_match.group(1) if id_match else href.split("/")[-1].split("?")[0]

        # Use full card text as title (brand + product description)
        title = raw.get("text", "") or raw.get("title", "")
        brand = raw.get("brand", "")

        # Parse price (remove commas)
        price_text = raw.get("price", "")
        price_cleaned = re.sub(r'[,\s]', '', price_text)
        try:
            price = float(price_cleaned)
        except ValueError:
            price = 0.0

        # Condition
        condition = "GENTLY_USED"
        cond_text = raw.get("condition", "").lower().strip()
        for grade, mapped in CONDITION_MAP.items():
            if grade in cond_text:
                condition = mapped
                break

        # Image
        images = []
        img = raw.get("image", "")
        if img and img.startswith("http"):
            images = [img]

        size = raw.get("size", "") or None

        if not title or price <= 0:
            return None

        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=source_id,
            url=url,
            title=title.strip(),
            price=price,
            currency="JPY",
            brand=brand,
            size=size,
            condition=condition,
            images=images,
            is_auction=False,
            raw_data=raw,
        )

    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        return None

    async def check_availability(self, item_id: str) -> bool:
        return True

    @staticmethod
    def get_health_status() -> dict:
        return {
            "name": "2nd STREET Japan",
            "type": "playwright_browser",
            "currency": "JPY",
            "auth": "store-inspected",
            "rate_limit": "2-4s delay",
            "note": "Requires Playwright + Chromium",
        }

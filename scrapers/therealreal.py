"""
TheRealReal scraper — authenticated luxury consignment via Playwright.

TRR uses PerimeterX anti-bot which blocks all programmatic HTTP requests.
Must use a real browser (Playwright) to bypass. All items are pre-authenticated.

Scraping approach: Playwright browser → search page → extract product data from DOM.
"""

import asyncio
import json
import logging
import re
from typing import Optional

from .base import BaseScraper, ScrapedItem

logger = logging.getLogger("therealreal_scraper")

CONDITION_MAP = {
    "pristine": "NEW_WITH_TAGS",
    "excellent": "LIKE_NEW",
    "very good": "GENTLY_USED",
    "good": "GENTLY_USED",
    "fair": "WELL_WORN",
}


class TheRealRealScraper(BaseScraper):
    """Scraper for TheRealReal via Playwright browser automation."""

    SOURCE_NAME = "therealreal"
    BASE_URL = "https://www.therealreal.com"

    MIN_DELAY = 3.0
    MAX_DELAY = 6.0

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
            # Use Firefox — Chromium SEGV crashes on macOS with this Playwright version
            self._browser = await self._playwright.firefox.launch(headless=self.headless)
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1440, "height": 900},
            )
        except ImportError:
            logger.warning("Playwright not installed — TRR scraper disabled. Install with: pip install playwright && playwright install chromium")
            self._browser = None
        except Exception as e:
            logger.error(f"TRR Playwright setup error: {e}")
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
        """Search TRR using Playwright browser."""
        if not self._browser:
            logger.debug("TRR: Browser not available, skipping")
            return []

        url = f"{self.BASE_URL}/shop?query={query.replace(' ', '+')}"
        logger.info(f"TRR: Searching '{query}' via Playwright")

        try:
            page = await self._context.new_page()

            # Navigate and wait for product content to load
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Wait for product grid to appear
            try:
                await page.wait_for_selector("[data-testid='product-card'], .product-card, .pdp-link, a[href*='/products/']", timeout=10000)
            except Exception:
                logger.debug("TRR: No product cards found on page")
                await page.close()
                return []

            # Extract product data from the DOM
            items = await page.evaluate("""() => {
                const products = [];
                // Try multiple selector patterns
                const cards = document.querySelectorAll('[data-testid="product-card"], .product-card, a[href*="/products/"]');

                cards.forEach(card => {
                    try {
                        const link = card.querySelector('a[href*="/products/"]') || card.closest('a[href*="/products/"]') || card;
                        const href = link?.getAttribute('href') || '';
                        if (!href.includes('/products/')) return;

                        const nameEl = card.querySelector('[data-testid="product-name"], .product-name, .product-title, h3, h2');
                        const designerEl = card.querySelector('[data-testid="designer-name"], .designer-name, .product-designer');
                        const priceEl = card.querySelector('[data-testid="product-price"], .product-price, .sale-price, .price');
                        const imgEl = card.querySelector('img');
                        const conditionEl = card.querySelector('[data-testid="condition"], .condition');
                        const sizeEl = card.querySelector('[data-testid="size"], .size');

                        products.push({
                            url: href,
                            title: nameEl?.textContent?.trim() || '',
                            designer: designerEl?.textContent?.trim() || '',
                            price: priceEl?.textContent?.trim() || '',
                            image: imgEl?.src || imgEl?.getAttribute('data-src') || '',
                            condition: conditionEl?.textContent?.trim() || '',
                            size: sizeEl?.textContent?.trim() || '',
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

            logger.info(f"TRR: Found {len(parsed)} items for '{query}'")
            return parsed

        except Exception as e:
            logger.error(f"TRR search error: {type(e).__name__}: {e}")
            try:
                await page.close()
            except Exception:
                pass
            return []

    def _parse_browser_item(self, raw: dict) -> Optional[ScrapedItem]:
        """Parse a product dict extracted from the browser DOM."""
        href = raw.get("url", "")
        if not href:
            return None

        url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
        slug = href.split("/products/")[-1].split("?")[0] if "/products/" in href else ""

        title = raw.get("title", "")
        designer = raw.get("designer", "")
        if designer and designer.lower() not in title.lower():
            title = f"{designer} {title}"

        price_text = raw.get("price", "")
        price = self._extract_price(price_text)

        condition_raw = raw.get("condition", "").lower().strip()
        condition = CONDITION_MAP.get(condition_raw, "GENTLY_USED")

        images = []
        img = raw.get("image", "")
        if img:
            images = [img]

        size = raw.get("size", "") or None

        if not title or price <= 0:
            return None

        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=slug,
            url=url,
            title=title.strip(),
            price=price,
            currency="USD",
            brand=designer,
            size=size,
            condition=condition,
            images=images,
            is_auction=False,
            raw_data=raw,
        )

    def _extract_price(self, text: str) -> float:
        """Extract numeric price from text like '$1,234' or '1234'."""
        if not text:
            return 0.0
        cleaned = re.sub(r'[^\d.]', '', text.replace(',', ''))
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        return None

    async def check_availability(self, item_id: str) -> bool:
        return True

    @staticmethod
    def get_health_status() -> dict:
        return {
            "name": "TheRealReal",
            "type": "playwright_browser",
            "auth": "pre-authenticated",
            "rate_limit": "3-6s delay",
            "note": "Requires Playwright + Chromium",
        }

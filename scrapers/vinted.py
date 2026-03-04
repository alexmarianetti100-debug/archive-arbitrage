"""
Vinted scraper using Playwright for full browser-based scraping.
Bypasses Cloudflare and API restrictions by rendering the actual search page.
"""

import asyncio
import json
import logging
import re
from typing import Dict, List, Optional
from datetime import datetime
from urllib.parse import quote_plus

from .base import BaseScraper, ScrapedItem

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger("scraper.vinted")

DEFAULT_DOMAINS = [
    "https://www.vinted.com",
    "https://www.vinted.fr",
]

# Shared browser instance
_browser = None
_playwright = None


async def _ensure_browser():
    """Launch a shared browser instance."""
    global _browser, _playwright
    if _browser:
        return _browser

    if not PLAYWRIGHT_AVAILABLE:
        raise ImportError("Playwright not installed")

    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security',
        ]
    )
    return _browser


async def _new_context(domain: str):
    """Create a new browser context for a domain."""
    browser = await _ensure_browser()

    # Use locale based on domain
    locale = "en-US"
    if ".fr" in domain:
        locale = "fr-FR"
    elif ".de" in domain:
        locale = "de-DE"
    elif ".it" in domain:
        locale = "it-IT"
    elif ".co.uk" in domain:
        locale = "en-GB"

    context = await browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        locale=locale,
    )
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        window.chrome = { runtime: {} };
    """)
    return context


class VintedScraperWrapper(BaseScraper):
    """Scrape Vinted using Playwright browser automation."""

    SOURCE_NAME = "vinted"
    MIN_DELAY = 3.0
    MAX_DELAY = 6.0

    def __init__(self, domains: Optional[List[str]] = None, proxy_manager=None):
        super().__init__(proxy_manager)
        self.domains = domains or DEFAULT_DOMAINS

    async def _search_domain(self, domain: str, query: str, max_results: int = 10) -> List[ScrapedItem]:
        """Search a single Vinted domain using Playwright.
        
        Strategy: Intercept the API response that the page makes internally,
        which gives us clean JSON data.
        """
        items = []
        api_responses = []

        try:
            context = await _new_context(domain)
            page = await context.new_page()

            # Intercept API calls to capture search results
            async def capture_api(response):
                if "/api/v2/catalog/items" in response.url:
                    try:
                        data = await response.json()
                        api_responses.append(data)
                    except Exception:
                        pass

            page.on("response", capture_api)

            # Navigate to search page
            search_url = f"{domain}/catalog?search_text={quote_plus(query)}&order=newest_first"
            await page.goto(search_url, wait_until="networkidle", timeout=30000)

            # Wait for results to load
            await page.wait_for_timeout(3000)

            # Try API interception first (cleanest data)
            if api_responses:
                for response_data in api_responses:
                    items_data = response_data.get("items", [])
                    for item_data in items_data[:max_results]:
                        item = self._parse_api_item(item_data, domain)
                        if item and item.price > 0:
                            items.append(item)

            # Fallback: extract from DOM if API interception didn't work
            if not items:
                items = await self._extract_from_dom(page, domain, max_results)

            await context.close()

        except Exception as e:
            logger.warning(f"  Vinted ({domain}): search error: {e}")

        return items

    def _parse_api_item(self, item_data: dict, domain: str) -> Optional[ScrapedItem]:
        """Parse item from intercepted API response."""
        try:
            # Price
            price = 0.0
            price_raw = item_data.get("price") or item_data.get("total_item_price")
            if isinstance(price_raw, dict):
                price = float(price_raw.get("amount", 0))
            elif isinstance(price_raw, str):
                price = float(re.sub(r'[^\d.]', '', price_raw.replace(",", ".")))
            elif price_raw:
                price = float(price_raw)

            # Images
            images = []
            photo = item_data.get("photo")
            if isinstance(photo, dict):
                url = photo.get("url") or photo.get("full_size_url", "")
                if url:
                    images.append(url)
            photos = item_data.get("photos", [])
            for p in (photos if isinstance(photos, list) else []):
                if isinstance(p, dict):
                    url = p.get("url") or p.get("full_size_url", "")
                    if url and url not in images:
                        images.append(url)

            # Brand
            brand = item_data.get("brand_title") or ""

            # Currency
            currency = "USD"
            if ".fr" in domain or ".de" in domain or ".it" in domain:
                currency = "EUR"
            elif ".co.uk" in domain:
                currency = "GBP"

            # URL
            item_id = item_data.get("id", "")
            url = item_data.get("url") or ""
            if url and not url.startswith("http"):
                url = f"{domain}{url}" if url.startswith("/") else f"{domain}/{url}"
            if not url:
                url = f"{domain}/items/{item_id}"

            title = item_data.get("title") or ""
            if brand and brand.lower() not in title.lower():
                title = f"{brand} {title}"

            return ScrapedItem(
                source=self.SOURCE_NAME,
                source_id=str(item_id),
                url=url,
                title=title,
                price=price,
                currency=currency,
                brand=brand,
                size=str(item_data.get("size_title", "")) or None,
                images=images[:5],
                description=item_data.get("description") or "",
            )
        except Exception as e:
            logger.debug(f"Error parsing Vinted API item: {e}")
            return None

    async def _extract_from_dom(self, page, domain: str, max_results: int) -> List[ScrapedItem]:
        """Fallback: extract items directly from the page DOM."""
        items = []
        try:
            # Vinted uses various card selectors
            cards = await page.query_selector_all('[data-testid*="item"], .feed-grid__item, .ItemBox_container__')

            if not cards:
                # Try broader selector
                cards = await page.query_selector_all('a[href*="/items/"]')

            for card in cards[:max_results]:
                try:
                    # Title
                    title_el = await card.query_selector('[data-testid*="title"], .ItemBox_title__, .web_ui__Text__subtitle')
                    title = await title_el.inner_text() if title_el else ""

                    # Price
                    price_el = await card.query_selector('[data-testid*="price"], .ItemBox_price__, .web_ui__Text__bold')
                    price_text = await price_el.inner_text() if price_el else "0"
                    price = float(re.sub(r'[^\d.]', '', price_text.replace(",", "."))) if price_text else 0.0

                    # URL
                    href = await card.get_attribute("href") or ""
                    if not href:
                        link = await card.query_selector("a[href*='/items/']")
                        href = await link.get_attribute("href") if link else ""
                    if href and not href.startswith("http"):
                        href = f"{domain}{href}"

                    # Image
                    img_el = await card.query_selector("img")
                    img_src = await img_el.get_attribute("src") if img_el else ""

                    # Extract ID from URL
                    id_match = re.search(r'/items/(\d+)', href)
                    item_id = id_match.group(1) if id_match else ""

                    # Currency
                    currency = "USD"
                    if ".fr" in domain or ".de" in domain or ".it" in domain:
                        currency = "EUR"
                    elif ".co.uk" in domain:
                        currency = "GBP"

                    if title and price > 0 and href:
                        items.append(ScrapedItem(
                            source=self.SOURCE_NAME,
                            source_id=item_id,
                            url=href,
                            title=title.strip(),
                            price=price,
                            currency=currency,
                            images=[img_src] if img_src else [],
                        ))
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"DOM extraction failed: {e}")

        return items

    async def search(self, query: str, max_results: int = 20) -> List[ScrapedItem]:
        """Search across configured Vinted domains."""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not available, skipping Vinted")
            return []

        all_items = []
        per_domain = max(5, max_results // len(self.domains))

        for domain in self.domains:
            try:
                domain_items = await self._search_domain(domain, query, per_domain)
                all_items.extend(domain_items)
                logger.info(f"  Vinted ({domain}): {len(domain_items)} results for '{query}'")
                await self._random_delay()
            except Exception as e:
                logger.warning(f"  Vinted ({domain}) search failed: {e}")
                continue

        # Deduplicate
        seen_titles = set()
        unique_items = []
        for item in all_items:
            key = item.title.lower().strip()[:50]
            if key not in seen_titles:
                seen_titles.add(key)
                unique_items.append(item)

        return unique_items[:max_results]

    async def search_sold(self, query: str, max_results: int = 20) -> List[ScrapedItem]:
        return []

    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        return None

    async def check_availability(self, item_id: str) -> bool:
        return True

"""
Shared base class for scraping Next.js sites via __NEXT_DATA__ extraction.

Used by TheRealReal and Fashionphile scrapers. Both sites embed product data
in a <script id="__NEXT_DATA__"> tag that contains the full page props as JSON.
"""

import json
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapedItem

logger = logging.getLogger("nextjs_scraper")


class NextJsScraper(BaseScraper):
    """Base class for scraping Next.js sites via __NEXT_DATA__ extraction."""

    SOURCE_NAME: str = "nextjs"
    BASE_URL: str = ""
    SEARCH_PATH: str = ""
    SEARCH_PARAM: str = "q"

    async def _fetch_next_data(self, url: str) -> Optional[dict]:
        """Fetch a page and extract the __NEXT_DATA__ JSON payload."""
        try:
            response = await self.fetch(url)
            if response.status_code != 200:
                logger.warning(f"{self.SOURCE_NAME}: HTTP {response.status_code} for {url}")
                return None

            soup = BeautifulSoup(response.text, "html.parser")
            script_tag = soup.find("script", id="__NEXT_DATA__")
            if not script_tag or not script_tag.string:
                logger.debug(f"{self.SOURCE_NAME}: No __NEXT_DATA__ found at {url}")
                return None

            data = json.loads(script_tag.string)
            return data.get("props", {}).get("pageProps", {})

        except json.JSONDecodeError as e:
            logger.warning(f"{self.SOURCE_NAME}: JSON decode error in __NEXT_DATA__: {e}")
            return None
        except Exception as e:
            logger.warning(f"{self.SOURCE_NAME}: Error fetching {url}: {type(e).__name__}: {e}")
            return None

    async def _fetch_html(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a page and return parsed HTML (fallback when __NEXT_DATA__ unavailable)."""
        try:
            response = await self.fetch(url)
            if response.status_code != 200:
                return None
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            logger.warning(f"{self.SOURCE_NAME}: Error fetching HTML {url}: {e}")
            return None

    def _extract_listings_from_props(self, page_props: dict) -> list[dict]:
        """Subclasses override: navigate pageProps to find the listing array."""
        raise NotImplementedError

    def _parse_listing(self, listing: dict) -> Optional[ScrapedItem]:
        """Subclasses override: convert a single listing dict to ScrapedItem."""
        raise NotImplementedError

    async def search(self, query: str, max_results: int = 50) -> list[ScrapedItem]:
        """Search the platform and return ScrapedItem list."""
        url = f"{self.BASE_URL}{self.SEARCH_PATH}?{self.SEARCH_PARAM}={query.replace(' ', '+')}"
        logger.info(f"{self.SOURCE_NAME}: Searching '{query}' -> {url}")

        page_props = await self._fetch_next_data(url)
        if not page_props:
            # Fallback: try HTML-based extraction
            return await self._search_html_fallback(url, query, max_results)

        raw_listings = self._extract_listings_from_props(page_props)
        items = []
        for listing in raw_listings[:max_results]:
            try:
                item = self._parse_listing(listing)
                if item and item.price > 0:
                    items.append(item)
            except Exception as e:
                logger.debug(f"{self.SOURCE_NAME}: Failed to parse listing: {e}")
                continue

        logger.info(f"{self.SOURCE_NAME}: Found {len(items)} items for '{query}'")
        return items

    async def _search_html_fallback(self, url: str, query: str, max_results: int) -> list[ScrapedItem]:
        """Fallback HTML-based search when __NEXT_DATA__ is not available."""
        logger.debug(f"{self.SOURCE_NAME}: Trying HTML fallback for '{query}'")
        return []

    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        """Fetch full details for a single item."""
        url = f"{self.BASE_URL}/{item_id}"
        page_props = await self._fetch_next_data(url)
        if not page_props:
            return None
        return self._parse_listing(page_props)

    async def check_availability(self, item_id: str) -> bool:
        """Check if an item is still available."""
        try:
            url = f"{self.BASE_URL}/{item_id}"
            response = await self.fetch(url)
            return response.status_code == 200
        except Exception:
            return False

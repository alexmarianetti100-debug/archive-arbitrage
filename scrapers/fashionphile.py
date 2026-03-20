"""
Fashionphile scraper — authenticated luxury accessories via Algolia API.

Fashionphile uses Algolia for search. We query their API directly, bypassing
all anti-bot measures. All items are pre-authenticated by Fashionphile staff.

Key categories: Chrome Hearts jewelry/accessories, LV bags, Chanel bags,
Prada bags, Bottega Veneta bags, Balenciaga bags.
"""

import logging
from typing import Optional

import httpx

from .base import BaseScraper, ScrapedItem

logger = logging.getLogger("fashionphile_scraper")

# Fashionphile Algolia credentials (public, embedded in their frontend JS)
ALGOLIA_APP_ID = "NSJAZ0QG7K"
ALGOLIA_API_KEY = "e545a3cf82cf7dbc5ff39f49c214863e"
ALGOLIA_INDEX = "shopify_products"
ALGOLIA_URL = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/*/queries"


class FashionphileScraper(BaseScraper):
    """Scraper for Fashionphile via Algolia search API."""

    SOURCE_NAME = "fashionphile"
    BASE_URL = "https://www.fashionphile.com"

    # No rate limiting needed — Algolia API is fast and permissive
    MIN_DELAY = 0.5
    MAX_DELAY = 1.0

    async def search(self, query: str, max_results: int = 50) -> list[ScrapedItem]:
        """Search Fashionphile via Algolia API."""
        logger.info(f"Fashionphile: Searching '{query}' via Algolia")

        try:
            payload = {
                "requests": [{
                    "indexName": ALGOLIA_INDEX,
                    "params": f"query={query}&hitsPerPage={max_results}&filters=inventory_available:true",
                }]
            }

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    ALGOLIA_URL,
                    json=payload,
                    headers={
                        "x-algolia-application-id": ALGOLIA_APP_ID,
                        "x-algolia-api-key": ALGOLIA_API_KEY,
                        "Content-Type": "application/json",
                    },
                )

            if resp.status_code != 200:
                logger.warning(f"Fashionphile Algolia returned {resp.status_code}")
                return []

            data = resp.json()
            hits = data.get("results", [{}])[0].get("hits", [])
            items = []

            for hit in hits:
                try:
                    item = self._parse_hit(hit)
                    if item and item.price > 0:
                        items.append(item)
                except Exception as e:
                    logger.debug(f"Fashionphile parse error: {e}")
                    continue

            logger.info(f"Fashionphile: Found {len(items)} items for '{query}'")
            return items

        except Exception as e:
            logger.error(f"Fashionphile search error: {type(e).__name__}: {e}")
            return []

    def _parse_hit(self, hit: dict) -> Optional[ScrapedItem]:
        """Convert an Algolia hit to ScrapedItem."""
        title = hit.get("title", "")
        vendor = hit.get("vendor", "")
        price = hit.get("price", 0)
        handle = hit.get("handle", "")
        sku = str(hit.get("sku", "") or hit.get("id", ""))
        image = hit.get("image", "")
        product_type = hit.get("product_type", "")
        available = hit.get("inventory_available", True)

        if not title or not price or not handle:
            return None

        # Build full title with vendor
        full_title = f"{vendor} {title}" if vendor and vendor.lower() not in title.lower() else title

        # URL
        url = f"{self.BASE_URL}/p/{handle}"

        # Images — Fashionphile uses Shopify CDN
        images = []
        if image:
            images.append(image)
        # Additional images from the images dict
        images_dict = hit.get("images", {})
        if isinstance(images_dict, dict):
            for key in sorted(images_dict.keys()):
                img_url = images_dict[key]
                if img_url and img_url not in images:
                    images.append(img_url)

        # Compare at price (original/retail reference)
        compare_at = hit.get("compare_at_price", 0) or 0

        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=sku,
            url=url,
            title=full_title.strip(),
            price=float(price),
            currency="USD",
            brand=vendor,
            category=product_type,
            images=images[:5],
            is_auction=False,
            raw_data={
                "compare_at_price": compare_at,
                "tags": hit.get("tags", []),
                "handle": handle,
            },
        )

    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        """Fetch details for a single item by SKU/handle."""
        results = await self.search(item_id, max_results=1)
        return results[0] if results else None

    async def check_availability(self, item_id: str) -> bool:
        """Check if item is still available via Algolia."""
        try:
            payload = {
                "requests": [{
                    "indexName": ALGOLIA_INDEX,
                    "params": f"query={item_id}&hitsPerPage=1",
                }]
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    ALGOLIA_URL,
                    json=payload,
                    headers={
                        "x-algolia-application-id": ALGOLIA_APP_ID,
                        "x-algolia-api-key": ALGOLIA_API_KEY,
                    },
                )
            hits = resp.json().get("results", [{}])[0].get("hits", [])
            if hits:
                return hits[0].get("inventory_available", False)
            return False
        except Exception:
            return False

    @staticmethod
    def get_health_status() -> dict:
        return {
            "name": "Fashionphile",
            "type": "algolia_api",
            "auth": "pre-authenticated",
            "rate_limit": "minimal (API)",
        }

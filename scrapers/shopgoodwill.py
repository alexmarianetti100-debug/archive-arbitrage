"""
ShopGoodwill.com scraper - auction site for Goodwill items.

NOTE: ShopGoodwill's API is unreliable (returns 500 errors frequently).
This scraper requires Playwright browser automation for reliable results.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapedItem

logger = logging.getLogger("scraper.shopgoodwill")


class ShopGoodwillScraper(BaseScraper):
    """Scrape ShopGoodwill auction listings."""
    
    SOURCE_NAME = "shopgoodwill"
    BASE_URL = "https://shopgoodwill.com"
    API_URL = "https://buyerapi.shopgoodwill.com/api"
    
    # Category IDs on ShopGoodwill
    CATEGORIES = {
        "mens_clothing": 103,
        "womens_clothing": 104,
        "shoes": 106,
        "accessories": 102,
    }
    
    async def search(
        self,
        query: str,
        max_results: int = 50,
        category_id: Optional[int] = None,
    ) -> list[ScrapedItem]:
        """Search ShopGoodwill for items."""
        items = []
        
        # ShopGoodwill has an internal API - try it first
        search_data = {
            "searchText": query,
            "selectedCategoryIds": [category_id] if category_id else [],
            "selectedSellerIds": [],
            "lowPrice": 0,
            "highPrice": 999999,
            "searchBuyNowOnly": False,
            "searchPickupOnly": False,
            "searchNoPickupOnly": False,
            "searchDescriptions": True,
            "searchClosedAuctions": False,
            "page": 1,
            "pageSize": min(max_results, 120),
            "sortColumn": 1,  # End time soonest
            "sortDescending": False,
        }
        
        try:
            response = await self.client.post(
                f"{self.API_URL}/Search/ItemListing",
                json=search_data,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Origin": "https://shopgoodwill.com",
                    "Referer": "https://shopgoodwill.com/",
                    "User-Agent": self._get_user_agent(),
                },
            )
            
            if response.status_code != 200:
                raise Exception(f"API returned {response.status_code}")
                
            data = response.json()
            
            for item_data in data.get("searchResults", {}).get("items", []):
                try:
                    item = self._parse_api_item(item_data)
                    if item:
                        items.append(item)
                except Exception as e:
                    logger.debug(f"Error parsing ShopGoodwill item: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"ShopGoodwill API unavailable ({e}), skipping.")
            
        return items
    
    def _parse_api_item(self, data: dict) -> Optional[ScrapedItem]:
        """Parse item from API response."""
        item_id = str(data.get("itemId", ""))
        if not item_id:
            return None
            
        title = data.get("title", "")
        current_price = float(data.get("currentPrice", 0))
        
        # Parse end time
        ends_at = None
        end_time_str = data.get("endTime")
        if end_time_str:
            try:
                ends_at = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
            except Exception:
                pass
        
        # Image
        images = []
        image_url = data.get("imageUrl")
        if image_url:
            if not image_url.startswith("http"):
                image_url = f"{self.BASE_URL}{image_url}"
            images.append(image_url)
        
        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=item_id,
            url=f"{self.BASE_URL}/item/{item_id}",
            title=title,
            price=current_price,
            currency="USD",
            images=images,
            ends_at=ends_at,
            is_auction=True,
            size=self.extract_size(title),
            raw_data=data,
        )
    
    async def _search_scrape(self, query: str, max_results: int) -> list[ScrapedItem]:
        """Fallback scraping method if API fails."""
        items = []
        
        params = {
            "searchText": query,
            "catId": "",
            "lowPrice": "",
            "highPrice": "",
            "sortBy": "endTime",
            "sortOrder": "asc",
        }
        url = f"{self.BASE_URL}/search?{urlencode(params)}"
        
        page = await self.get_page()
        try:
            await page.goto(url, wait_until="networkidle")
            content = await page.content()
            soup = BeautifulSoup(content, "lxml")
            
            listings = soup.select("div.product-card")
            
            for listing in listings[:max_results]:
                try:
                    item = self._parse_listing_html(listing)
                    if item:
                        items.append(item)
                except Exception as e:
                    print(f"Error parsing listing: {e}")
                    continue
                    
        finally:
            await page.close()
            
        return items
    
    def _parse_listing_html(self, listing) -> Optional[ScrapedItem]:
        """Parse listing from HTML."""
        # Get link and extract ID
        link_el = listing.select_one("a.product-card__link")
        if not link_el:
            return None
            
        href = link_el.get("href", "")
        item_id_match = re.search(r'/item/(\d+)', href)
        if not item_id_match:
            return None
        item_id = item_id_match.group(1)
        
        # Title
        title_el = listing.select_one("h2.product-card__title")
        title = title_el.text.strip() if title_el else ""
        
        # Price
        price_el = listing.select_one("span.product-card__price")
        price = self.parse_price(price_el.text) if price_el else 0.0
        
        # Image
        images = []
        img_el = listing.select_one("img.product-card__image")
        if img_el:
            img_url = img_el.get("src") or img_el.get("data-src")
            if img_url:
                images.append(img_url)
        
        # Time remaining
        time_el = listing.select_one("span.product-card__time")
        ends_at = None
        if time_el:
            time_text = time_el.text.lower()
            # Parse relative time (e.g., "2d 3h", "5h 30m")
            days = hours = minutes = 0
            day_match = re.search(r'(\d+)d', time_text)
            hour_match = re.search(r'(\d+)h', time_text)
            min_match = re.search(r'(\d+)m', time_text)
            if day_match:
                days = int(day_match.group(1))
            if hour_match:
                hours = int(hour_match.group(1))
            if min_match:
                minutes = int(min_match.group(1))
            ends_at = datetime.utcnow() + timedelta(days=days, hours=hours, minutes=minutes)
        
        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=item_id,
            url=f"{self.BASE_URL}/item/{item_id}",
            title=title,
            price=price,
            currency="USD",
            images=images,
            ends_at=ends_at,
            is_auction=True,
            size=self.extract_size(title),
        )
    
    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        """Get full item details."""
        url = f"{self.BASE_URL}/item/{item_id}"
        
        page = await self.get_page()
        try:
            await page.goto(url, wait_until="networkidle")
            content = await page.content()
            soup = BeautifulSoup(content, "lxml")
            
            # Title
            title_el = soup.select_one("h1.product-title")
            title = title_el.text.strip() if title_el else ""
            
            # Current bid
            price_el = soup.select_one("span.current-price")
            price = self.parse_price(price_el.text) if price_el else 0.0
            
            # Images
            images = []
            img_els = soup.select("div.product-gallery img")
            for img in img_els:
                src = img.get("src") or img.get("data-src")
                if src:
                    images.append(src)
            
            # Description
            desc_el = soup.select_one("div.product-description")
            description = desc_el.text.strip() if desc_el else None
            
            # Seller/location
            seller_el = soup.select_one("a.seller-link")
            seller = seller_el.text.strip() if seller_el else None
            
            # Shipping
            shipping_el = soup.select_one("span.shipping-cost")
            shipping_cost = None
            if shipping_el:
                shipping_text = shipping_el.text
                if "pickup" in shipping_text.lower():
                    shipping_cost = None  # Pickup only
                else:
                    shipping_cost = self.parse_price(shipping_text)
            
            return ScrapedItem(
                source=self.SOURCE_NAME,
                source_id=item_id,
                url=url,
                title=title,
                price=price,
                currency="USD",
                images=images,
                description=description,
                seller=seller,
                shipping_cost=shipping_cost,
                is_auction=True,
                size=self.extract_size(title),
            )
            
        finally:
            await page.close()
    
    async def check_availability(self, item_id: str) -> bool:
        """Check if auction is still active."""
        try:
            response = await self.client.get(
                f"{self.API_URL}/ItemDetail/GetItemDetailModelFromItemId/{item_id}"
            )
            data = response.json()
            
            # Check if auction has ended
            is_closed = data.get("isClosed", True)
            return not is_closed
            
        except Exception:
            return False

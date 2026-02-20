"""
eBay Browse API scraper - uses official API (no blocking issues).

Setup:
1. Go to https://developer.ebay.com/
2. Sign in and create an application (Production)
3. Get App ID (Client ID) and Cert ID (Client Secret)
4. Add to .env:
   EBAY_APP_ID=your_app_id
   EBAY_CERT_ID=your_cert_id

Free tier: 5000 calls/day - plenty for scraping!
"""

import os
import base64
from datetime import datetime, timedelta
from typing import Optional, List

import httpx

from .base import ScrapedItem


class EbayApiScraper:
    """Scrape eBay using the official Browse API."""
    
    SOURCE_NAME = "ebay"
    AUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    
    def __init__(self):
        self.app_id = os.getenv("EBAY_APP_ID")
        self.cert_id = os.getenv("EBAY_CERT_ID")
        self.access_token = None
        self.token_expires = None
        
        if not self.app_id or not self.cert_id:
            raise ValueError(
                "eBay API credentials not found. Set EBAY_APP_ID and EBAY_CERT_ID in .env\n"
                "Get credentials at: https://developer.ebay.com/"
            )
    
    async def __aenter__(self):
        await self._get_token()
        return self
    
    async def __aexit__(self, *args):
        pass
    
    async def _get_token(self):
        """Get OAuth access token."""
        if self.access_token and self.token_expires and datetime.utcnow() < self.token_expires:
            return  # Token still valid
        
        credentials = base64.b64encode(f"{self.app_id}:{self.cert_id}".encode()).decode()
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.AUTH_URL,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {credentials}",
                },
                data={
                    "grant_type": "client_credentials",
                    "scope": "https://api.ebay.com/oauth/api_scope"
                }
            )
            
            if resp.status_code != 200:
                raise Exception(f"eBay OAuth failed: {resp.status_code} - {resp.text}")
            
            data = resp.json()
            self.access_token = data["access_token"]
            # Token expires in ~2 hours, refresh a bit early
            self.token_expires = datetime.utcnow() + timedelta(seconds=data["expires_in"] - 300)
    
    async def search(
        self,
        query: str,
        max_results: int = 50,
        category_id: str = None,  # eBay category ID
        min_price: float = None,
        max_price: float = None,
        condition: str = None,  # NEW, USED
    ) -> List[ScrapedItem]:
        """Search eBay for items using Browse API."""
        await self._get_token()
        
        items = []
        offset = 0
        limit = min(max_results, 200)  # API max is 200
        
        # Build filter string
        filters = []
        if condition:
            filters.append(f"conditions:{{{condition}}}")
        if min_price:
            filters.append(f"price:[{min_price}]")
        if max_price:
            filters.append(f"price:[..{max_price}]")
        
        params = {
            "q": query,
            "limit": limit,
            "offset": offset,
        }
        
        if category_id:
            params["category_ids"] = category_id
        if filters:
            params["filter"] = ",".join(filters)
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                self.BROWSE_URL,
                params=params,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                }
            )
            
            if resp.status_code != 200:
                print(f"  eBay API error: {resp.status_code}")
                return items
            
            data = resp.json()
            summaries = data.get("itemSummaries", [])
            
            for item_data in summaries[:max_results]:
                try:
                    item = self._parse_item(item_data)
                    if item:
                        items.append(item)
                except Exception as e:
                    print(f"  Error parsing item: {e}")
                    continue
        
        return items
    
    def _parse_item(self, data: dict) -> Optional[ScrapedItem]:
        """Parse item from API response."""
        item_id = data.get("itemId", "").split("|")[-1]  # Extract numeric ID
        if not item_id:
            return None
        
        # Title
        title = data.get("title", "")
        
        # Price
        price_data = data.get("price", {})
        price = float(price_data.get("value", 0))
        currency = price_data.get("currency", "USD")
        
        # Convert to USD if needed
        if currency != "USD":
            # Rough conversions
            rates = {"GBP": 1.27, "EUR": 1.09, "CAD": 0.74, "AUD": 0.66}
            price *= rates.get(currency, 1.0)
        
        # Images
        images = []
        image_data = data.get("image", {})
        if image_data.get("imageUrl"):
            images.append(image_data["imageUrl"])
        thumb = data.get("thumbnailImages", [])
        for t in thumb[:3]:
            if t.get("imageUrl"):
                images.append(t["imageUrl"])
        
        # URL
        url = data.get("itemWebUrl", f"https://www.ebay.com/itm/{item_id}")
        
        # Condition
        condition = None
        cond_data = data.get("condition")
        if cond_data:
            condition = cond_data  # e.g. "New", "Pre-Owned"
        
        # Auction vs Buy It Now
        is_auction = data.get("buyingOptions", []) == ["AUCTION"]
        
        # Shipping
        shipping_cost = None
        shipping = data.get("shippingOptions", [{}])[0]
        if shipping:
            ship_cost = shipping.get("shippingCost", {})
            if ship_cost.get("value"):
                shipping_cost = float(ship_cost["value"])
        
        # Size from title
        size = self._extract_size(title)
        
        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=item_id,
            url=url,
            title=title,
            price=price,
            currency="USD",
            condition=condition,
            size=size,
            images=images,
            shipping_cost=shipping_cost,
            is_auction=is_auction,
        )
    
    def _extract_size(self, text: str) -> Optional[str]:
        """Extract size from text."""
        import re
        text_upper = text.upper()
        patterns = [
            r'\b(XXS|XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL)\b',
            r'\bSIZE\s*(\d{1,2})\b',
            r'\b(\d{1,2})\s*(US|EU|UK|IT|FR)\b',
        ]
        for pattern in patterns:
            match = re.search(pattern, text_upper)
            if match:
                return match.group(1)
        return None
    
    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        """Get full item details."""
        await self._get_token()
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.ebay.com/buy/browse/v1/item/v1|{item_id}|0",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                }
            )
            
            if resp.status_code != 200:
                return None
            
            return self._parse_item(resp.json())
    
    async def check_availability(self, item_id: str) -> bool:
        """Check if item is still available."""
        item = await self.get_item_details(item_id)
        return item is not None

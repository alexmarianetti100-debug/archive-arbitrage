"""
Auction Sniper - Finds eBay auctions ending soon with low/no bids.

These are often the highest-margin opportunities because:
1. Sellers use auctions hoping for bidding wars that don't happen
2. Items ending at odd hours get less attention
3. Poor titles/photos = less competition = better deals
"""

import os
import re
import base64
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass

import httpx

from .base import ScrapedItem
from .brands import ARCHIVE_BRANDS, PRIORITY_BRANDS


@dataclass
class AuctionItem(ScrapedItem):
    """Extended item with auction-specific fields."""
    bid_count: int = 0
    time_left_hours: float = 0
    ends_at: Optional[datetime] = None


class AuctionSniper:
    """
    Find underpriced eBay auctions ending soon.
    
    Strategy:
    - Search for archive brands on eBay auctions
    - Filter to auctions ending within 6-24 hours
    - Prioritize items with 0-2 bids (less competition)
    - Apply same pricing logic to find profitable opportunities
    """
    
    SOURCE_NAME = "ebay_auction"
    AUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    
    # eBay category IDs
    CATEGORIES = {
        "mens_clothing": "1059",
        "womens_clothing": "15724",
        "mens_shoes": "93427",
        "mens_accessories": "4250",
        "coats_jackets": "57988",
    }
    
    def __init__(self):
        self.app_id = os.getenv("EBAY_APP_ID")
        self.cert_id = os.getenv("EBAY_CERT_ID")
        self.access_token = None
        self.token_expires = None
        
        # Track if credentials are available
        self.enabled = bool(self.app_id and self.cert_id)
    
    async def __aenter__(self):
        if self.enabled:
            await self._get_token()
        return self
    
    async def __aexit__(self, *args):
        pass
    
    async def _get_token(self):
        """Get OAuth access token."""
        if not self.enabled:
            return
            
        if self.access_token and self.token_expires and datetime.utcnow() < self.token_expires:
            return
        
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
                raise Exception(f"eBay OAuth failed: {resp.status_code}")
            
            data = resp.json()
            self.access_token = data["access_token"]
            self.token_expires = datetime.utcnow() + timedelta(seconds=data["expires_in"] - 300)
    
    async def search_auctions(
        self,
        query: str,
        max_results: int = 50,
        ending_within_hours: int = 24,
        max_bids: int = 3,
        category: str = None,
        max_price: float = None,
    ) -> List[AuctionItem]:
        """
        Search for auctions ending soon with few bids.
        
        Args:
            query: Search query (brand name, etc.)
            max_results: Maximum items to return
            ending_within_hours: Only auctions ending within this time
            max_bids: Maximum number of bids (0-3 is ideal)
            category: eBay category (mens_clothing, etc.)
            max_price: Maximum current price
        """
        if not self.enabled:
            print("  ⚠ eBay API not configured (set EBAY_APP_ID and EBAY_CERT_ID)")
            return []
        
        await self._get_token()
        
        items = []
        
        # Build filters
        filters = ["buyingOptions:{AUCTION}"]  # Only auctions
        
        if max_price:
            filters.append(f"price:[..{max_price}]")
        
        # eBay condition IDs: 1000=New, 3000=Pre-owned
        filters.append("conditions:{3000}")  # Pre-owned (where the deals are)
        
        params = {
            "q": query,
            "limit": min(max_results * 2, 200),  # Fetch extra since we'll filter
            "sort": "endingSoonest",  # Critical: get auctions ending soonest first
            "filter": ",".join(filters),
        }
        
        if category and category in self.CATEGORIES:
            params["category_ids"] = self.CATEGORIES[category]
        
        async with httpx.AsyncClient(timeout=30) as client:
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
            
            now = datetime.utcnow()
            
            for item_data in summaries:
                try:
                    item = self._parse_auction(item_data)
                    if not item:
                        continue
                    
                    # Filter by time remaining
                    if item.time_left_hours > ending_within_hours:
                        continue
                    
                    # Filter by bid count
                    if item.bid_count > max_bids:
                        continue
                    
                    items.append(item)
                    
                    if len(items) >= max_results:
                        break
                        
                except Exception as e:
                    continue
        
        return items
    
    def _parse_auction(self, data: dict) -> Optional[AuctionItem]:
        """Parse auction item from API response."""
        item_id = data.get("itemId", "").split("|")[-1]
        if not item_id:
            return None
        
        # Must be an auction
        buying_options = data.get("buyingOptions", [])
        if "AUCTION" not in buying_options:
            return None
        
        # Title
        title = data.get("title", "")
        
        # Current bid price
        price_data = data.get("price", {})
        price = float(price_data.get("value", 0))
        currency = price_data.get("currency", "USD")
        
        if currency != "USD":
            rates = {"GBP": 1.27, "EUR": 1.09, "CAD": 0.74, "AUD": 0.66}
            price *= rates.get(currency, 1.0)
        
        # Bid count
        bid_count = data.get("bidCount", 0)
        
        # Time remaining
        ends_at = None
        time_left_hours = 999
        
        end_str = data.get("itemEndDate")
        if end_str:
            try:
                # Parse ISO format: 2024-01-15T14:30:00.000Z
                ends_at = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                now = datetime.now(ends_at.tzinfo) if ends_at.tzinfo else datetime.utcnow()
                delta = ends_at.replace(tzinfo=None) - now.replace(tzinfo=None)
                time_left_hours = delta.total_seconds() / 3600
            except:
                pass
        
        # Images
        images = []
        image_data = data.get("image", {})
        if image_data.get("imageUrl"):
            images.append(image_data["imageUrl"])
        
        # URL
        url = data.get("itemWebUrl", f"https://www.ebay.com/itm/{item_id}")
        
        # Condition
        condition = data.get("condition", "Pre-Owned")
        
        # Shipping
        shipping_cost = None
        shipping = data.get("shippingOptions", [{}])[0] if data.get("shippingOptions") else {}
        if shipping:
            ship_cost = shipping.get("shippingCost", {})
            if ship_cost.get("value"):
                shipping_cost = float(ship_cost["value"])
        
        # Size
        size = self._extract_size(title)
        
        return AuctionItem(
            source="ebay",
            source_id=item_id,
            url=url,
            title=title,
            price=price,
            currency="USD",
            condition=condition,
            size=size,
            images=images,
            shipping_cost=shipping_cost,
            is_auction=True,
            bid_count=bid_count,
            time_left_hours=time_left_hours,
            ends_at=ends_at,
        )
    
    def _extract_size(self, text: str) -> Optional[str]:
        """Extract size from text."""
        text_upper = text.upper()
        patterns = [
            r'\b(XXS|XS|S|M|L|XL|XXL|XXXL|2XL|3XL)\b',
            r'\bSIZE\s*(\d{1,2})\b',
            r'\bSZ\s*(\d{1,2})\b',
            r'\b(\d{1,2})\s*(US|EU|UK|IT|FR)\b',
        ]
        for pattern in patterns:
            match = re.search(pattern, text_upper)
            if match:
                return match.group(1)
        return None
    
    async def snipe_brands(
        self,
        brands: List[str] = None,
        max_per_brand: int = 10,
        ending_within_hours: int = 12,
        max_price: float = 500,
    ) -> List[AuctionItem]:
        """
        Search for auction opportunities across multiple brands.
        
        Args:
            brands: List of brands to search (default: PRIORITY_BRANDS)
            max_per_brand: Max auctions per brand
            ending_within_hours: How soon auctions must be ending
            max_price: Maximum current bid price
        """
        if not self.enabled:
            return []
        
        if brands is None:
            # Use priority brands for auction sniping
            brands = PRIORITY_BRANDS[:20]
        
        all_items = []
        
        for brand in brands:
            try:
                items = await self.search_auctions(
                    query=brand,
                    max_results=max_per_brand,
                    ending_within_hours=ending_within_hours,
                    max_bids=2,  # Focus on low-bid auctions
                    max_price=max_price,
                )
                
                if items:
                    all_items.extend(items)
                    
            except Exception as e:
                print(f"  Error searching {brand}: {e}")
                continue
        
        # Sort by time remaining (most urgent first)
        all_items.sort(key=lambda x: x.time_left_hours)
        
        return all_items


# Quick test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        async with AuctionSniper() as sniper:
            if not sniper.enabled:
                print("eBay API not configured. Set EBAY_APP_ID and EBAY_CERT_ID in .env")
                return
            
            print("Searching for auctions ending soon...")
            items = await sniper.search_auctions(
                query="raf simons",
                max_results=5,
                ending_within_hours=24,
            )
            
            print(f"\nFound {len(items)} auctions:\n")
            for item in items:
                print(f"${item.price:.0f} ({item.bid_count} bids) - {item.time_left_hours:.1f}h left")
                print(f"  {item.title[:60]}...")
                print(f"  {item.url}")
                print()
    
    asyncio.run(test())

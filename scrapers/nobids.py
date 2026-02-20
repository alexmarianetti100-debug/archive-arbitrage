"""
NoBids.net scraper - finds eBay auctions ending soon with no bids.
Great for finding underpriced archive pieces.
"""

import re
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote, urlencode

from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapedItem


class NoBidsScraper(BaseScraper):
    """Scrape NoBids.net for eBay auctions ending soon with no bids."""
    
    SOURCE_NAME = "nobids"
    BASE_URL = "https://www.nobids.net"
    
    MIN_DELAY = 1.5
    MAX_DELAY = 3.0
    
    # NoBids category mappings
    CATEGORIES = {
        "clothing": "clothing-shoes-accessories",
        "mens": "clothing-shoes-accessories/mens-clothing",
        "womens": "clothing-shoes-accessories/womens-clothing",
    }
    
    async def search(
        self,
        query: str,
        max_results: int = 50,
        category: str = "clothing",
        ending_within_hours: int = 24,
    ) -> list[ScrapedItem]:
        """Search NoBids for eBay auctions with no bids."""
        items = []
        
        # Build search URL
        cat_path = self.CATEGORIES.get(category, "clothing-shoes-accessories")
        
        # NoBids search format
        search_url = f"{self.BASE_URL}/search/{quote(query)}"
        
        try:
            response = await self.fetch(search_url)
            
            if response.status_code != 200:
                print(f"  NoBids returned {response.status_code}")
                # Try alternate URL format
                search_url = f"{self.BASE_URL}/?q={quote(query)}"
                response = await self.fetch(search_url)
                if response.status_code != 200:
                    return items
            
            soup = BeautifulSoup(response.text, "lxml")
            
            # Find auction listings
            listings = soup.select('div.auction-item, div.item, tr.item-row, .listing')
            
            if not listings:
                # Try finding eBay links directly
                listings = soup.select('a[href*="ebay.com/itm"]')
            
            if not listings:
                # Try broader selectors
                listings = soup.select('[class*="item"], [class*="listing"], [class*="auction"]')
            
            for listing in listings[:max_results]:
                try:
                    item = self._parse_listing(listing)
                    if item:
                        items.append(item)
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"  NoBids search failed: {e}")
            
        return items
    
    def _parse_listing(self, listing) -> Optional[ScrapedItem]:
        """Parse a NoBids listing."""
        # Find eBay link
        link = listing if listing.name == 'a' else listing.select_one('a[href*="ebay.com/itm"]')
        if not link:
            link = listing.select_one('a[href*="ebay"]')
        if not link:
            return None
        
        href = link.get("href", "")
        if "ebay.com" not in href:
            return None
        
        # Extract eBay item ID
        item_id_match = re.search(r'/itm/(\d+)', href) or re.search(r'item=(\d+)', href)
        if not item_id_match:
            return None
        item_id = item_id_match.group(1)
        
        # Normalize eBay URL
        url = f"https://www.ebay.com/itm/{item_id}"
        
        # Title
        title = ""
        title_el = listing.select_one('.title, .item-title, h3, h4, [class*="title"]')
        if title_el:
            title = title_el.get_text(strip=True)
        if not title:
            title = link.get_text(strip=True)
        if not title:
            img = listing.select_one('img')
            title = img.get('alt', '') if img else f"eBay Item {item_id}"
        
        # Price (starting bid)
        price = 0.0
        price_el = listing.select_one('.price, .bid, [class*="price"]')
        if price_el:
            price = self.parse_price(price_el.get_text())
        else:
            price_match = listing.find(string=re.compile(r'\$[\d,]+\.?\d*'))
            if price_match:
                price = self.parse_price(str(price_match))
        
        # Time remaining
        ends_at = None
        time_el = listing.select_one('.time, .ends, [class*="time"], [class*="ending"]')
        if time_el:
            time_text = time_el.get_text().lower()
            ends_at = self._parse_time_remaining(time_text)
        
        # Image
        images = []
        img_el = listing.select_one('img[src*="ebayimg"], img')
        if img_el:
            img_url = img_el.get('src') or img_el.get('data-src')
            if img_url:
                # Get higher res eBay image
                img_url = re.sub(r's-l\d+', 's-l500', img_url)
                images.append(img_url)
        
        return ScrapedItem(
            source="ebay",  # Mark as eBay since that's the actual source
            source_id=item_id,
            url=url,
            title=title[:500],
            price=price,
            currency="USD",
            images=images,
            ends_at=ends_at,
            is_auction=True,
            size=self.extract_size(title),
            raw_data={"via": "nobids", "no_bids": True},
        )
    
    def _parse_time_remaining(self, time_text: str) -> Optional[datetime]:
        """Parse time remaining string into datetime."""
        now = datetime.utcnow()
        
        # Match patterns like "2h 30m", "1d 5h", "45m"
        days = hours = minutes = 0
        
        day_match = re.search(r'(\d+)\s*d', time_text)
        hour_match = re.search(r'(\d+)\s*h', time_text)
        min_match = re.search(r'(\d+)\s*m', time_text)
        
        if day_match:
            days = int(day_match.group(1))
        if hour_match:
            hours = int(hour_match.group(1))
        if min_match:
            minutes = int(min_match.group(1))
        
        if days or hours or minutes:
            return now + timedelta(days=days, hours=hours, minutes=minutes)
        
        return None
    
    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        """Get item details from eBay directly."""
        # Delegate to eBay scraper
        return None
    
    async def check_availability(self, item_id: str) -> bool:
        """Check if auction is still active on eBay."""
        return True  # Would need eBay scraper

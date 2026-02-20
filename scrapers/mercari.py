"""
Mercari scraper - good for streetwear and archive finds.
Uses their public web interface.
"""

import re
from typing import Optional
from urllib.parse import quote, urlencode

from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapedItem


class MercariScraper(BaseScraper):
    """Scrape Mercari listings."""
    
    SOURCE_NAME = "mercari"
    BASE_URL = "https://www.mercari.com"
    
    MIN_DELAY = 2.0
    MAX_DELAY = 5.0
    
    async def search(
        self,
        query: str,
        max_results: int = 50,
    ) -> list[ScrapedItem]:
        """Search Mercari for items."""
        items = []
        
        # Mercari search URL
        params = {
            "keyword": query,
            "status": "on_sale",  # Only items for sale
            "sortBy": "created_time",
            "order": "desc",
        }
        search_url = f"{self.BASE_URL}/search/?{urlencode(params)}"
        
        try:
            response = await self.fetch(search_url)
            
            if response.status_code != 200:
                print(f"  Mercari returned {response.status_code}")
                return items
            
            soup = BeautifulSoup(response.text, "lxml")
            
            # Find product cards
            product_cards = soup.select('[data-testid="SearchResults"] [data-testid="ItemCell"]')
            
            if not product_cards:
                # Try alternate selectors
                product_cards = soup.select('div[class*="ItemCell"]')
            
            if not product_cards:
                # Try finding links to items
                product_cards = soup.select('a[href*="/item/"]')
            
            for card in product_cards[:max_results]:
                try:
                    item = self._parse_card(card)
                    if item:
                        items.append(item)
                except Exception as e:
                    print(f"  Error parsing Mercari item: {e}")
                    continue
                    
        except Exception as e:
            print(f"  Mercari search failed: {e}")
            
        return items
    
    def _parse_card(self, card) -> Optional[ScrapedItem]:
        """Parse a product card."""
        # Get link
        link = card if card.name == 'a' else card.select_one('a[href*="/item/"]')
        if not link:
            return None
        
        href = link.get("href", "")
        if not href or "/item/" not in href:
            return None
        
        # Extract item ID
        item_id_match = re.search(r'/item/m(\d+)', href)
        if not item_id_match:
            return None
        item_id = item_id_match.group(1)
        
        # Build full URL
        url = f"{self.BASE_URL}/item/m{item_id}"
        
        # Title
        title_el = card.select_one('[class*="ItemName"], [data-testid="ItemName"]')
        title = title_el.get_text(strip=True) if title_el else ""
        
        if not title:
            # Try getting from image alt
            img = card.select_one('img')
            if img:
                title = img.get('alt', f"Mercari Item {item_id}")
        
        # Price
        price = 0.0
        price_el = card.select_one('[class*="Price"], [data-testid="ItemPrice"]')
        if price_el:
            price = self.parse_price(price_el.get_text())
        else:
            # Try finding any price-like text
            price_match = card.find(string=re.compile(r'\$[\d,]+'))
            if price_match:
                price = self.parse_price(price_match)
        
        # Image
        images = []
        img_el = card.select_one('img[src*="mercari"], img[data-src*="mercari"]')
        if img_el:
            img_url = img_el.get('src') or img_el.get('data-src')
            if img_url:
                images.append(img_url)
        
        # Size from title
        size = self.extract_size(title)
        
        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=item_id,
            url=url,
            title=title or f"Mercari Item {item_id}",
            price=price,
            currency="USD",
            size=size,
            images=images,
            is_auction=False,
        )
    
    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        """Get full item details."""
        url = f"{self.BASE_URL}/item/m{item_id}"
        
        try:
            response = await self.fetch(url)
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, "lxml")
            
            # Title
            title_el = soup.select_one('h1, [data-testid="ItemName"]')
            title = title_el.get_text(strip=True) if title_el else ""
            
            # Price
            price = 0.0
            price_el = soup.select_one('[data-testid="ItemPrice"], [class*="Price"]')
            if price_el:
                price = self.parse_price(price_el.get_text())
            
            # Images
            images = []
            img_els = soup.select('img[src*="mercari-images"]')
            for img in img_els[:10]:
                src = img.get('src')
                if src:
                    images.append(src)
            
            # Description
            desc_el = soup.select_one('[data-testid="ItemDescription"]')
            description = desc_el.get_text(strip=True) if desc_el else None
            
            # Seller
            seller_el = soup.select_one('[data-testid="SellerName"]')
            seller = seller_el.get_text(strip=True) if seller_el else None
            
            # Condition
            condition_el = soup.select_one('[data-testid="ItemCondition"]')
            condition = condition_el.get_text(strip=True) if condition_el else None
            
            return ScrapedItem(
                source=self.SOURCE_NAME,
                source_id=item_id,
                url=url,
                title=title,
                price=price,
                currency="USD",
                size=self.extract_size(title),
                condition=condition,
                images=images,
                description=description,
                seller=seller,
                is_auction=False,
            )
            
        except Exception as e:
            print(f"  Error getting Mercari item: {e}")
            return None
    
    async def check_availability(self, item_id: str) -> bool:
        """Check if item is still available."""
        try:
            url = f"{self.BASE_URL}/item/m{item_id}"
            response = await self.fetch(url)
            
            if response.status_code != 200:
                return False
            
            soup = BeautifulSoup(response.text, "lxml")
            
            # Check for sold indicator
            sold = soup.select_one('[class*="Sold"], [data-testid="SoldLabel"]')
            if sold:
                return False
            
            # Check for buy button
            buy_btn = soup.select_one('[data-testid="BuyButton"], button[class*="Buy"]')
            return buy_btn is not None
            
        except Exception:
            return False

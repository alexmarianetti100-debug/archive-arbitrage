"""
Gem.app scraper - Japanese consignment marketplace.
Great source for Japanese archive brands (CDG, Yohji, Undercover, etc.)
"""

import re
from typing import Optional
from urllib.parse import quote, urlencode

from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapedItem


class GemScraper(BaseScraper):
    """Scrape Gem.app (ゲオマート) for Japanese fashion items."""
    
    SOURCE_NAME = "gem"
    BASE_URL = "https://gem.app"
    API_URL = "https://api.gem.app"
    
    MIN_DELAY = 2.0
    MAX_DELAY = 4.0
    
    # JPY to USD conversion (approximate)
    JPY_TO_USD = 0.0067
    
    async def search(
        self,
        query: str,
        max_results: int = 50,
    ) -> list[ScrapedItem]:
        """Search Gem.app for items."""
        items = []
        
        # Gem.app search URL
        search_url = f"{self.BASE_URL}/search?q={quote(query)}"
        
        try:
            response = await self.fetch(search_url)
            
            if response.status_code != 200:
                print(f"  Gem.app returned {response.status_code}")
                return items
            
            soup = BeautifulSoup(response.text, "lxml")
            
            # Find product cards
            cards = soup.select('[class*="ProductCard"], [class*="product-card"], .item-card')
            
            if not cards:
                cards = soup.select('a[href*="/items/"]')
            
            if not cards:
                # Try finding any item links
                cards = soup.select('[class*="item"], [class*="listing"]')
            
            for card in cards[:max_results]:
                try:
                    item = self._parse_card(card)
                    if item:
                        items.append(item)
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"  Gem.app search failed: {e}")
            
        return items
    
    def _parse_card(self, card) -> Optional[ScrapedItem]:
        """Parse a product card."""
        # Get link
        link = card if card.name == 'a' else card.select_one('a[href*="/items/"]')
        if not link:
            link = card.select_one('a')
        if not link:
            return None
        
        href = link.get("href", "")
        
        # Extract item ID
        item_id_match = re.search(r'/items?/([a-zA-Z0-9-]+)', href)
        if not item_id_match:
            return None
        item_id = item_id_match.group(1)
        
        # Build URL
        url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
        
        # Title
        title = ""
        title_el = card.select_one('[class*="title"], [class*="name"], h3, h4')
        if title_el:
            title = title_el.get_text(strip=True)
        if not title:
            title = link.get_text(strip=True)
        
        # Price (usually in JPY)
        price = 0.0
        price_el = card.select_one('[class*="price"]')
        if price_el:
            price_text = price_el.get_text()
            # Extract number from ¥12,345 or 12345円
            price_match = re.search(r'[\d,]+', price_text.replace(',', ''))
            if price_match:
                jpy_price = float(price_match.group().replace(',', ''))
                price = jpy_price * self.JPY_TO_USD
        
        # Brand
        brand = None
        brand_el = card.select_one('[class*="brand"]')
        if brand_el:
            brand = brand_el.get_text(strip=True)
        
        # Size
        size = None
        size_el = card.select_one('[class*="size"]')
        if size_el:
            size = size_el.get_text(strip=True)
        if not size:
            size = self.extract_size(title)
        
        # Image
        images = []
        img_el = card.select_one('img')
        if img_el:
            img_url = img_el.get('src') or img_el.get('data-src')
            if img_url:
                if not img_url.startswith('http'):
                    img_url = f"{self.BASE_URL}{img_url}"
                images.append(img_url)
        
        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=item_id,
            url=url,
            title=title or f"Gem Item {item_id}",
            price=price,
            currency="USD",
            brand=brand,
            size=size,
            images=images,
            is_auction=False,
        )
    
    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        """Get full item details."""
        url = f"{self.BASE_URL}/items/{item_id}"
        
        try:
            response = await self.fetch(url)
            
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.text, "lxml")
            
            # Title
            title_el = soup.select_one('h1, [class*="title"]')
            title = title_el.get_text(strip=True) if title_el else ""
            
            # Price
            price = 0.0
            price_el = soup.select_one('[class*="price"]')
            if price_el:
                price_text = price_el.get_text()
                price_match = re.search(r'[\d,]+', price_text.replace(',', ''))
                if price_match:
                    jpy_price = float(price_match.group().replace(',', ''))
                    price = jpy_price * self.JPY_TO_USD
            
            # Images
            images = []
            img_els = soup.select('[class*="gallery"] img, [class*="image"] img')
            for img in img_els[:10]:
                src = img.get('src') or img.get('data-src')
                if src:
                    if not src.startswith('http'):
                        src = f"{self.BASE_URL}{src}"
                    images.append(src)
            
            # Description
            desc_el = soup.select_one('[class*="description"]')
            description = desc_el.get_text(strip=True) if desc_el else None
            
            # Brand
            brand = None
            brand_el = soup.select_one('[class*="brand"]')
            if brand_el:
                brand = brand_el.get_text(strip=True)
            
            # Condition
            condition = None
            cond_el = soup.select_one('[class*="condition"]')
            if cond_el:
                condition = cond_el.get_text(strip=True)
            
            return ScrapedItem(
                source=self.SOURCE_NAME,
                source_id=item_id,
                url=url,
                title=title,
                price=price,
                currency="USD",
                brand=brand,
                size=self.extract_size(title),
                condition=condition,
                images=images,
                description=description,
                is_auction=False,
            )
            
        except Exception as e:
            print(f"  Error getting Gem.app item: {e}")
            return None
    
    async def check_availability(self, item_id: str) -> bool:
        """Check if item is still available."""
        try:
            url = f"{self.BASE_URL}/items/{item_id}"
            response = await self.fetch(url)
            
            if response.status_code != 200:
                return False
            
            soup = BeautifulSoup(response.text, "lxml")
            
            # Check for sold indicator
            sold = soup.select_one('[class*="sold"], [class*="unavailable"]')
            return sold is None
            
        except Exception:
            return False

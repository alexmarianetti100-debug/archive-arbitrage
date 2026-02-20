"""
Depop scraper - popular for archive fashion.
Uses web scraping as their API blocks automated access.
"""

import re
from typing import Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapedItem


class DepopScraper(BaseScraper):
    """Scrape Depop listings."""
    
    SOURCE_NAME = "depop"
    BASE_URL = "https://www.depop.com"
    
    MIN_DELAY = 3.0
    MAX_DELAY = 6.0
    
    async def search(
        self,
        query: str,
        max_results: int = 50,
    ) -> list[ScrapedItem]:
        """Search Depop for items via web scraping."""
        items = []
        
        # Use web search URL instead of API
        search_url = f"{self.BASE_URL}/search/?q={quote(query)}"
        
        try:
            response = await self.fetch(search_url)
            
            if response.status_code != 200:
                print(f"  Depop returned {response.status_code}")
                return items
            
            soup = BeautifulSoup(response.text, "lxml")
            
            # Find product links
            product_links = soup.select('a[href*="/products/"]')
            
            seen_ids = set()
            for link in product_links[:max_results * 2]:
                try:
                    item = self._parse_product_link(link)
                    if item and item.source_id not in seen_ids:
                        seen_ids.add(item.source_id)
                        items.append(item)
                        if len(items) >= max_results:
                            break
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"  Depop search failed: {e}")
            
        return items
    
    def _parse_product_link(self, link) -> Optional[ScrapedItem]:
        """Parse a product from a link element."""
        href = link.get("href", "")
        if "/products/" not in href:
            return None
        
        # Extract product slug/ID
        match = re.search(r'/products/([^/?]+)', href)
        if not match:
            return None
        slug = match.group(1)
        
        # Build URL
        url = f"{self.BASE_URL}/products/{slug}"
        
        # Try to find parent card for more info
        card = link.find_parent('li') or link.find_parent('div')
        
        # Title
        title = ""
        if card:
            title_el = card.select_one('[class*="title"], [class*="description"]')
            if title_el:
                title = title_el.get_text(strip=True)
        if not title:
            img = link.select_one('img')
            title = img.get('alt', '') if img else slug.replace('-', ' ')
        
        # Price
        price = 0.0
        if card:
            price_el = card.select_one('[class*="price"]')
            if price_el:
                price = self.parse_price(price_el.get_text())
        
        # Image
        images = []
        img_el = link.select_one('img') or (card.select_one('img') if card else None)
        if img_el:
            img_url = img_el.get('src') or img_el.get('data-src')
            if img_url:
                images.append(img_url)
        
        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=slug,
            url=url,
            title=title[:200] or f"Depop Item",
            price=price,
            currency="USD",
            size=self.extract_size(title),
            images=images,
            is_auction=False,
        )
    
    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        """Get full item details."""
        url = f"{self.API_URL}/products/{item_id}"
        
        try:
            response = await self.fetch(url)
            if response.status_code != 200:
                return None
            
            data = response.json()
            return self._parse_product(data)
            
        except Exception as e:
            print(f"  Error getting Depop item: {e}")
            return None
    
    async def check_availability(self, item_id: str) -> bool:
        """Check if item is still available."""
        try:
            url = f"{self.API_URL}/products/{item_id}"
            response = await self.fetch(url)
            
            if response.status_code != 200:
                return False
            
            data = response.json()
            return data.get("status") == "ONSALE"
            
        except Exception:
            return False

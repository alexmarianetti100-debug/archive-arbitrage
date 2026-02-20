"""
Poshmark scraper - lots of designer and streetwear.
"""

import re
from typing import Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapedItem


class PoshmarkScraper(BaseScraper):
    """Scrape Poshmark listings."""
    
    SOURCE_NAME = "poshmark"
    BASE_URL = "https://poshmark.com"
    
    MIN_DELAY = 2.0
    MAX_DELAY = 4.0
    
    async def search(
        self,
        query: str,
        max_results: int = 50,
        gender: str = "Men",
    ) -> list[ScrapedItem]:
        """Search Poshmark for items."""
        items = []
        seen_ids = set()
        
        search_url = f"{self.BASE_URL}/search?query={quote(query)}&department={gender}&type=listings"
        
        try:
            response = await self.fetch(search_url)
            
            if response.status_code != 200:
                print(f"  Poshmark returned {response.status_code}")
                return items
            
            soup = BeautifulSoup(response.text, "lxml")
            
            # Get all cards
            cards = soup.select('.card')
            
            for card in cards[:max_results]:
                try:
                    # Get listing ID from data attribute
                    link = card.select_one('a[data-et-prop-listing_id]')
                    if not link:
                        continue
                    
                    item_id = link.get('data-et-prop-listing_id', '')
                    if not item_id or item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)
                    
                    # URL
                    href = link.get('href', '')
                    url = f"{self.BASE_URL}{href}" if href.startswith('/') else href
                    
                    # Title
                    title_el = card.select_one('.tile__title')
                    title = title_el.get_text(strip=True) if title_el else ""
                    if not title:
                        img = card.select_one('img')
                        title = img.get('alt', '') if img else ""
                    
                    # Price (bold span)
                    price = 0.0
                    price_el = card.select_one('span.fw--bold')
                    if price_el:
                        price = self.parse_price(price_el.get_text())
                    
                    # Size
                    size = None
                    size_el = card.select_one('.tile__details__pipe__size')
                    if size_el:
                        size_text = size_el.get_text(strip=True)
                        size = size_text.replace('Size:', '').strip()
                    if not size:
                        size = self.extract_size(title)
                    
                    # Brand
                    brand = None
                    brand_el = card.select_one('.tile__details__pipe__brand')
                    if brand_el:
                        brand = brand_el.get_text(strip=True)
                    
                    # Image
                    images = []
                    img_el = card.select_one('img[src]')
                    if img_el:
                        src = img_el.get('src', '')
                        if src:
                            # Get larger image
                            src = src.replace('/s_', '/m_')
                            images.append(src)
                    
                    if title and price > 0:
                        items.append(ScrapedItem(
                            source=self.SOURCE_NAME,
                            source_id=item_id,
                            url=url,
                            title=title[:200],
                            price=price,
                            currency="USD",
                            brand=brand,
                            size=size,
                            images=images,
                            is_auction=False,
                        ))
                    
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"  Poshmark search failed: {e}")
            
        return items
    
    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        """Get full item details."""
        return None
    
    async def check_availability(self, item_id: str) -> bool:
        """Check if item is still available."""
        return True

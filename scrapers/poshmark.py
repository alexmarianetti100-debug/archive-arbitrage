"""
Poshmark scraper - lots of designer and streetwear.

Hardened implementation with multiple selector strategies and health tracking.
"""

import json
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import quote

from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapedItem


class PoshmarkScraper(BaseScraper):
    """Scrape Poshmark listings with multiple fallback strategies."""
    
    SOURCE_NAME = "poshmark"
    BASE_URL = "https://poshmark.com"
    
    MIN_DELAY = 2.0
    MAX_DELAY = 4.0
    
    # Health tracking
    _success_count = 0
    _failure_count = 0
    _last_failure = None
    _selector_version = "2024-03"  # Update when selectors change
    
    # Multiple selector strategies (primary, secondary, fallback)
    SELECTOR_STRATEGIES = {
        "primary": {
            "card": ".card",
            "link": "a[data-et-prop-listing_id]",
            "title": ".tile__title",
            "price": "span.fw--bold",
            "size": ".tile__details__pipe__size",
            "brand": ".tile__details__pipe__brand",
            "image": "img[src]",
        },
        "secondary": {
            "card": "[data-testid='listing-card']",
            "link": "a[href*='/listing/']",
            "title": "[data-testid='listing-title']",
            "price": "[data-testid='listing-price']",
            "size": "[data-testid='listing-size']",
            "brand": "[data-testid='listing-brand']",
            "image": "img[data-testid='listing-image']",
        },
        "fallback": {
            "card": ".item",
            "link": "a[href*='/listing/']",
            "title": ".title, h3, h4",
            "price": ".price, [class*='price']",
            "size": ".size, [class*='size']",
            "brand": ".brand, [class*='brand']",
            "image": "img",
        }
    }
    
    async def search(
        self,
        query: str,
        max_results: int = 50,
        gender: str = "Men",
    ) -> list[ScrapedItem]:
        """Search Poshmark for items with multiple fallback strategies."""
        items = []
        seen_ids = set()
        
        search_url = f"{self.BASE_URL}/search?query={quote(query)}&department={gender}&type=listings"
        
        try:
            response = await self.fetch(search_url)
            
            if response.status_code != 200:
                print(f"  Poshmark returned {response.status_code}")
                self._record_failure(f"HTTP {response.status_code}")
                return items
            
            html = response.text
            soup = BeautifulSoup(html, "lxml")
            
            # Try multiple selector strategies
            items = await self._parse_with_strategies(soup, html, max_results, seen_ids)
            
            if items:
                self._record_success()
            else:
                self._record_failure("No items parsed")
                    
        except Exception as e:
            print(f"  Poshmark search failed: {e}")
            self._record_failure(str(e))
            
        return items
    
    async def _parse_with_strategies(
        self, 
        soup: BeautifulSoup, 
        html: str,
        max_results: int,
        seen_ids: set
    ) -> list[ScrapedItem]:
        """Try multiple parsing strategies until one works."""
        items = []
        
        # Strategy 1: CSS Selectors (primary, secondary, fallback)
        for strategy_name, selectors in self.SELECTOR_STRATEGIES.items():
            items = self._parse_with_selectors(soup, selectors, max_results, seen_ids)
            if items:
                if strategy_name != "primary":
                    print(f"  Poshmark: Used {strategy_name} selectors")
                return items
        
        # Strategy 2: JSON-LD structured data
        items = self._parse_json_ld(html, max_results, seen_ids)
        if items:
            print("  Poshmark: Used JSON-LD structured data")
            return items
        
        # Strategy 3: Generic parsing
        items = self._parse_generic(soup, max_results, seen_ids)
        if items:
            print("  Poshmark: Used generic parsing")
            return items
        
        # No strategy worked - log for debugging
        self._log_parse_failure(soup)
        return []
    
    def _parse_with_selectors(
        self, 
        soup: BeautifulSoup, 
        selectors: dict,
        max_results: int,
        seen_ids: set
    ) -> list[ScrapedItem]:
        """Parse using CSS selectors."""
        items = []
        cards = soup.select(selectors["card"])
        
        for card in cards[:max_results]:
            try:
                item = self._parse_card(card, selectors, seen_ids)
                if item:
                    items.append(item)
            except Exception:
                continue
        
        return items
    
    def _parse_card(
        self, 
        card: BeautifulSoup, 
        selectors: dict,
        seen_ids: set
    ) -> Optional[ScrapedItem]:
        """Parse a single card using selectors."""
        # Get listing ID from link
        link = card.select_one(selectors["link"])
        if not link:
            return None
        
        # Try to get ID from various attributes
        item_id = (
            link.get('data-et-prop-listing_id') or
            link.get('data-listing-id') or
            self._extract_id_from_href(link.get('href', ''))
        )
        
        if not item_id or item_id in seen_ids:
            return None
        seen_ids.add(item_id)
        
        # URL
        href = link.get('href', '')
        url = f"{self.BASE_URL}{href}" if href.startswith('/') else href
        
        # Title
        title_el = card.select_one(selectors["title"])
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            img = card.select_one(selectors["image"])
            title = img.get('alt', '') if img else ""
        
        # Price
        price = 0.0
        price_el = card.select_one(selectors["price"])
        if price_el:
            price = self.parse_price(price_el.get_text())
        
        # Size
        size = None
        size_el = card.select_one(selectors["size"])
        if size_el:
            size_text = size_el.get_text(strip=True)
            size = size_text.replace('Size:', '').replace('Size', '').strip()
        if not size:
            size = self.extract_size(title)
        
        # Brand
        brand = None
        brand_el = card.select_one(selectors["brand"])
        if brand_el:
            brand = brand_el.get_text(strip=True)
        
        # Image
        images = []
        img_el = card.select_one(selectors["image"])
        if img_el:
            src = img_el.get('src', '')
            if src:
                src = src.replace('/s_', '/m_')
                images.append(src)
        
        if title and price > 0:
            return ScrapedItem(
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
            )
        
        return None
    
    def _extract_id_from_href(self, href: str) -> str:
        """Extract listing ID from URL."""
        match = re.search(r'/listing/([^/]+)', href)
        return match.group(1) if match else ""
    
    def _parse_json_ld(self, html: str, max_results: int, seen_ids: set) -> list[ScrapedItem]:
        """Parse JSON-LD structured data."""
        items = []
        
        # Find all JSON-LD scripts
        pattern = r'<script type="application/ld\+json">(.*?)</script>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match)
                
                # Look for Product or ItemList
                if isinstance(data, dict):
                    if data.get('@type') == 'Product':
                        item = self._parse_json_ld_product(data, seen_ids)
                        if item:
                            items.append(item)
                    elif data.get('@type') == 'ItemList' and 'itemListElement' in data:
                        for element in data['itemListElement']:
                            if isinstance(element, dict):
                                product = element.get('item', {})
                                if product.get('@type') == 'Product':
                                    item = self._parse_json_ld_product(product, seen_ids)
                                    if item:
                                        items.append(item)
                
                if len(items) >= max_results:
                    break
                    
            except json.JSONDecodeError:
                continue
        
        return items
    
    def _parse_json_ld_product(self, data: dict, seen_ids: set) -> Optional[ScrapedItem]:
        """Parse a single JSON-LD Product."""
        try:
            item_id = str(data.get('sku', data.get('@id', '')))
            if not item_id or item_id in seen_ids:
                return None
            seen_ids.add(item_id)
            
            title = data.get('name', '')
            url = data.get('url', '')
            
            # Price
            price = 0.0
            offers = data.get('offers', {})
            if isinstance(offers, dict):
                price_str = offers.get('price', '0')
                price = float(price_str) if price_str else 0.0
            
            # Brand
            brand = None
            brand_data = data.get('brand', {})
            if isinstance(brand_data, dict):
                brand = brand_data.get('name')
            
            # Image
            images = []
            image_data = data.get('image', [])
            if isinstance(image_data, list) and image_data:
                images.append(image_data[0])
            elif isinstance(image_data, str):
                images.append(image_data)
            
            if title and price > 0:
                return ScrapedItem(
                    source=self.SOURCE_NAME,
                    source_id=item_id,
                    url=url,
                    title=title[:200],
                    price=price,
                    currency="USD",
                    brand=brand,
                    images=images,
                    is_auction=False,
                )
        except Exception:
            pass
        
        return None
    
    def _parse_generic(self, soup: BeautifulSoup, max_results: int, seen_ids: set) -> list[ScrapedItem]:
        """Generic parsing as last resort."""
        items = []
        
        # Find all links to listings
        for link in soup.find_all('a', href=re.compile(r'/listing/')):
            try:
                href = link.get('href', '')
                item_id = self._extract_id_from_href(href)
                if not item_id or item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                
                url = f"{self.BASE_URL}{href}" if href.startswith('/') else href
                
                # Try to find title and price in parent or siblings
                parent = link.find_parent()
                title = ""
                price = 0.0
                
                if parent:
                    # Look for title
                    for tag in ['h3', 'h4', '.title', '[class*="title"]']:
                        title_el = parent.select_one(tag)
                        if title_el:
                            title = title_el.get_text(strip=True)
                            break
                    
                    # Look for price
                    text = parent.get_text()
                    price_match = re.search(r'\$([\d,]+\.?\d*)', text)
                    if price_match:
                        price = self.parse_price(price_match.group(0))
                
                if title and price > 0:
                    items.append(ScrapedItem(
                        source=self.SOURCE_NAME,
                        source_id=item_id,
                        url=url,
                        title=title[:200],
                        price=price,
                        currency="USD",
                        is_auction=False,
                    ))
                
                if len(items) >= max_results:
                    break
                    
            except Exception:
                continue
        
        return items
    
    def _log_parse_failure(self, soup: BeautifulSoup):
        """Log HTML structure for debugging when all strategies fail."""
        # Get page title and first 500 chars of body
        title = soup.find('title')
        title_text = title.get_text() if title else "No title"
        
        body = soup.find('body')
        body_preview = body.get_text()[:500] if body else "No body"
        
        print(f"  Poshmark: All parsing strategies failed")
        print(f"    Page title: {title_text[:100]}")
        print(f"    Body preview: {body_preview[:200]}...")
    
    def _record_success(self):
        """Record successful scrape."""
        self._success_count += 1
    
    def _record_failure(self, reason: str):
        """Record failed scrape."""
        self._failure_count += 1
        self._last_failure = datetime.now()
        print(f"  Poshmark failure: {reason}")
    
    @classmethod
    def get_health_status(cls) -> dict:
        """Get scraper health status."""
        total = cls._success_count + cls._failure_count
        success_rate = cls._success_count / total if total > 0 else 1.0
        
        return {
            "success_count": cls._success_count,
            "failure_count": cls._failure_count,
            "success_rate": success_rate,
            "last_failure": cls._last_failure.isoformat() if cls._last_failure else None,
            "healthy": success_rate > 0.8 and cls._failure_count < 10,
            "selector_version": cls._selector_version,
        }
    
    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        """Get full item details."""
        return None
    
    async def check_availability(self, item_id: str) -> bool:
        """Check if item is still available."""
        return True

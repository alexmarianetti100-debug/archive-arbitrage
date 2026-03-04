"""
Grailed scraper - for price reference on sold items.

Uses Grailed's internal API when possible, with HTML fallback.
"""

import json
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode, quote

from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapedItem


class GrailedScraper(BaseScraper):
    """Scrape Grailed for sold price reference."""
    
    SOURCE_NAME = "grailed"
    BASE_URL = "https://www.grailed.com"
    API_URL = "https://www.grailed.com/api"
    
    # Grailed's Algolia search params (extracted from their frontend)
    ALGOLIA_APP_ID = "MNRWEFSS2Q"
    ALGOLIA_API_KEY = "a3a4de2e05d9e9b463911705fb6323ad"  # Public search key
    
    async def search_sold(
        self,
        query: str,
        max_results: int = 20,
    ) -> list[ScrapedItem]:
        """Search for sold items to get market pricing."""
        items = []
        
        # Try Algolia API first (faster and more reliable)
        try:
            items = await self._search_algolia(query, max_results, sold=True)
            if items:
                return items
        except Exception as e:
            print(f"Algolia search failed: {e}")
        
        # Fallback to HTTP scraping
        try:
            items = await self._search_http(query, max_results, sold=True)
            if items:
                return items
        except Exception as e:
            print(f"HTTP scraping failed: {e}")
        
        # Last resort: Playwright if available
        if False:  # Playwright disabled
            try:
                items = await self._search_playwright(query, max_results, sold=True)
            except Exception as e:
                print(f"Playwright scraping failed: {e}")
            
        return items
    
    # Designer names for Algolia facet filtering (must match Grailed's designer index values)
    ALGOLIA_DESIGNERS = {
        "rick owens": "Rick Owens", "raf simons": "Raf Simons",
        "maison margiela": "Maison Margiela", "maison martin margiela": "Maison Margiela",
        "helmut lang": "Helmut Lang", "chrome hearts": "Chrome Hearts",
        "dior homme": "Dior", "dior men": "Dior", "christian dior": "Dior",
        "jean paul gaultier": "Jean Paul Gaultier", "gaultier": "Jean Paul Gaultier",
        "comme des garcons": "Comme des Garcons", "cdg": "Comme des Garcons",
        "junya watanabe": "Junya Watanabe", "yohji yamamoto": "Yohji Yamamoto",
        "vivienne westwood": "Vivienne Westwood", "issey miyake": "Issey Miyake",
        "undercover": "Undercover", "number (n)ine": "Number (N)ine",
        "enfants riches deprimes": "Enfants Riches Déprimés",
        "ann demeulemeester": "Ann Demeulemeester",
        "boris bidjan saberi": "Boris Bidjan Saberi", "julius": "Julius",
        "carol christian poell": "Carol Christian Poell",
        "haider ackermann": "Haider Ackermann",
        "hysteric glamour": "Hysteric Glamour", "kapital": "Kapital",
        "alexander mcqueen": "Alexander McQueen", "thierry mugler": "Thierry Mugler",
    }

    async def _search_algolia(self, query: str, max_results: int, sold: bool = False) -> list[ScrapedItem]:
        """Search using Grailed's Algolia backend."""
        items = []
        
        # Use separate index for sold items
        index_name = "Listing_sold_production" if sold else "Listing_production"
        algolia_url = f"https://{self.ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{index_name}/query"
        
        payload = {
            "query": query,
            "hitsPerPage": max_results,
            "page": 0,
        }

        # Try to extract designer for facet filtering (tighter results)
        query_lower = query.lower()
        for key, designer_name in self.ALGOLIA_DESIGNERS.items():
            if key in query_lower:
                payload["facetFilters"] = [f"designers.name:{designer_name}"]
                break
        
        headers = {
            "X-Algolia-Application-Id": self.ALGOLIA_APP_ID,
            "X-Algolia-API-Key": self.ALGOLIA_API_KEY,
            "Content-Type": "application/json",
        }
        
        # Retry Algolia with backoff on rate limits (429) or server errors (5xx)
        response = None
        for _attempt in range(3):
            response = await self.client.post(algolia_url, json=payload, headers=headers)
            if response.status_code == 200:
                break
            if response.status_code in (429, 500, 502, 503):
                import asyncio as _aio
                await _aio.sleep(1.5 * (_attempt + 1))
                continue
            raise Exception(f"Algolia returned {response.status_code}")
        
        if response is None or response.status_code != 200:
            raise Exception(f"Algolia failed after retries (last status: {response.status_code if response else 'none'})")
        
        data = response.json()
        
        for hit in data.get("hits", []):
            try:
                item = self._parse_algolia_hit(hit)
                if item:
                    items.append(item)
            except Exception as e:
                print(f"Error parsing Algolia hit: {e}")
                continue
        
        return items
    
    def _parse_algolia_hit(self, hit: dict) -> Optional[ScrapedItem]:
        """Parse an Algolia search hit."""
        item_id = str(hit.get("id", ""))
        if not item_id:
            return None
        
        title = hit.get("title", "")
        
        # Designer can be in 'designers' (array) or 'designer' (object/string)
        designer = ""
        designers = hit.get("designers", [])
        if designers and isinstance(designers, list) and len(designers) > 0:
            first_designer = designers[0]
            if isinstance(first_designer, dict):
                designer = first_designer.get("name", "")
            elif isinstance(first_designer, str):
                designer = first_designer
        elif hit.get("designer"):
            d = hit.get("designer")
            designer = d.get("name", "") if isinstance(d, dict) else str(d)
        
        # Get price (sold_price for sold items, price for active)
        price = hit.get("sold_price") or hit.get("price", 0)
        if isinstance(price, str):
            price = self.parse_price(price)
        
        # Size
        size = hit.get("size")
        
        # Image
        images = []
        if hit.get("cover_photo"):
            images.append(hit["cover_photo"].get("url", ""))
        elif hit.get("photos"):
            for photo in hit["photos"][:3]:
                if isinstance(photo, dict):
                    images.append(photo.get("url", ""))
                elif isinstance(photo, str):
                    images.append(photo)
        
        # Parse listing date
        listed_at = None
        created_str = hit.get("created_at")
        if created_str:
            try:
                from datetime import datetime
                listed_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # Preserve full raw_data including liquidity signals
        raw = dict(hit)

        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=item_id,
            url=f"{self.BASE_URL}/listings/{item_id}",
            title=f"{designer} {title}".strip(),
            price=float(price) if price else 0.0,
            currency="USD",
            brand=designer,
            size=size,
            condition=hit.get("condition"),
            images=images,
            listed_at=listed_at,
            raw_data=raw,
        )
    
    async def _search_http(self, query: str, max_results: int, sold: bool = False) -> list[ScrapedItem]:
        """Fallback HTTP scraping."""
        items = []
        
        # Try to get the page and extract data from __NEXT_DATA__
        path = "sold" if sold else "shop"
        search_url = f"{self.BASE_URL}/{path}/{quote(query)}"
        
        response = await self.fetch(search_url)
        soup = BeautifulSoup(response.text, "lxml")
        
        # Look for Next.js data
        script_el = soup.select_one("script#__NEXT_DATA__")
        if script_el:
            try:
                data = json.loads(script_el.string)
                # Navigate to listings in the data structure
                props = data.get("props", {}).get("pageProps", {})
                listings = props.get("listings", []) or props.get("initialData", {}).get("listings", [])
                
                for listing in listings[:max_results]:
                    item = self._parse_nextjs_listing(listing)
                    if item:
                        items.append(item)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Could not parse Next.js data: {e}")
        
        # If no Next.js data, try HTML parsing
        if not items:
            items = self._parse_html_listings(soup, max_results)
        
        return items
    
    def _parse_nextjs_listing(self, listing: dict) -> Optional[ScrapedItem]:
        """Parse listing from Next.js data."""
        item_id = str(listing.get("id", ""))
        if not item_id:
            return None
        
        designer = listing.get("designer", {}).get("name", "") if isinstance(listing.get("designer"), dict) else ""
        title = listing.get("title", "")
        price = listing.get("sold_price") or listing.get("price", 0)
        
        images = []
        for photo in listing.get("photos", [])[:3]:
            if isinstance(photo, dict):
                images.append(photo.get("url", ""))
        
        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=item_id,
            url=f"{self.BASE_URL}/listings/{item_id}",
            title=f"{designer} {title}".strip(),
            price=float(price) if price else 0.0,
            currency="USD",
            brand=designer,
            size=listing.get("size"),
            images=images,
        )
    
    def _parse_html_listings(self, soup: BeautifulSoup, max_results: int) -> list[ScrapedItem]:
        """Parse listings from HTML."""
        items = []
        
        # Multiple selectors for different page layouts
        listings = soup.select("div[data-testid='feed-item']") or soup.select("div.feed-item") or soup.select("a[href*='/listings/']")
        
        for listing in listings[:max_results]:
            try:
                item = self._parse_sold_listing(listing)
                if item:
                    items.append(item)
            except Exception as e:
                continue
        
        return items
    
    async def _search_playwright(self, query: str, max_results: int, sold: bool = False) -> list[ScrapedItem]:
        """Search using Playwright browser automation."""
        items = []
        
        page = await self.get_page()
        try:
            path = "sold" if sold else "shop"
            search_url = f"{self.BASE_URL}/{path}/{quote(query)}"
            await page.goto(search_url, wait_until="networkidle")
            await page.wait_for_timeout(2000)
            
            # Scroll to load more
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)
            
            content = await page.content()
            soup = BeautifulSoup(content, "lxml")
            
            items = self._parse_html_listings(soup, max_results)
        finally:
            await page.close()
        
        return items
    
    def _parse_sold_listing(self, listing) -> Optional[ScrapedItem]:
        """Parse a sold listing for price reference."""
        # Handle both BeautifulSoup elements and link elements
        if hasattr(listing, 'name') and listing.name == 'a':
            link_el = listing
        else:
            link_el = listing.select_one("a[href*='/listings/']")
        
        if not link_el:
            return None
        
        href = link_el.get("href", "")
        item_id_match = re.search(r'/listings/(\d+)', href)
        if not item_id_match:
            return None
        item_id = item_id_match.group(1)
        
        # Get the container (either the listing itself or find parent)
        container = listing
        
        # Title/designer - try multiple selectors
        designer = ""
        item_name = ""
        
        for selector in ["p.listing-designer", "[class*='designer']", "h2"]:
            title_el = container.select_one(selector)
            if title_el:
                designer = title_el.get_text(strip=True)
                break
        
        for selector in ["p.listing-title", "[class*='title']", "h3"]:
            name_el = container.select_one(selector)
            if name_el:
                item_name = name_el.get_text(strip=True)
                break
        
        title = f"{designer} {item_name}".strip()
        if not title:
            title = link_el.get_text(strip=True)
        
        # Sold price - try multiple selectors
        price = 0.0
        for selector in ["span.sold-price", "[class*='sold']", "[class*='price']", "p.sub-title"]:
            price_el = container.select_one(selector)
            if price_el:
                price = self.parse_price(price_el.get_text())
                if price > 0:
                    break
        
        # Size
        size = None
        for selector in ["p.listing-size", "[class*='size']"]:
            size_el = container.select_one(selector)
            if size_el:
                size = size_el.get_text(strip=True)
                break
        if not size:
            size = self.extract_size(title)
        
        # Image
        images = []
        img_el = container.select_one("img")
        if img_el:
            src = img_el.get("src") or img_el.get("data-src") or img_el.get("srcset", "").split()[0]
            if src:
                images.append(src)
        
        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=item_id,
            url=f"{self.BASE_URL}/listings/{item_id}",
            title=title,
            price=price,
            currency="USD",
            brand=designer,
            size=size,
            images=images,
        )
    
    async def get_market_price(
        self,
        brand: str,
        item_type: Optional[str] = None,
        size: Optional[str] = None,
    ) -> dict:
        """Get average market price for an item type."""
        query = brand
        if item_type:
            query += f" {item_type}"
        if size:
            query += f" {size}"
            
        sold_items = await self.search_sold(query, max_results=20)
        
        if not sold_items:
            return {
                "query": query,
                "sample_size": 0,
                "avg_price": None,
                "min_price": None,
                "max_price": None,
                "median_price": None,
            }
        
        prices = [item.price for item in sold_items if item.price > 0]
        
        if not prices:
            return {
                "query": query,
                "sample_size": 0,
                "avg_price": None,
                "min_price": None,
                "max_price": None,
                "median_price": None,
            }
        
        prices.sort()
        median_idx = len(prices) // 2
        
        return {
            "query": query,
            "sample_size": len(prices),
            "avg_price": sum(prices) / len(prices),
            "min_price": min(prices),
            "max_price": max(prices),
            "median_price": prices[median_idx],
            "items": sold_items[:5],  # Return top 5 as examples
        }
    
    async def search(self, query: str, max_results: int = 50) -> list[ScrapedItem]:
        """Search active listings (for reference, not for sourcing)."""
        items = []
        
        # Try Algolia API first
        try:
            items = await self._search_algolia(query, max_results, sold=False)
            if items:
                return items
        except Exception as e:
            print(f"Algolia search failed: {e}")
        
        # Fallback to HTTP
        try:
            items = await self._search_http(query, max_results, sold=False)
            if items:
                return items
        except Exception as e:
            print(f"HTTP scraping failed: {e}")
        
        # Last resort: Playwright
        if False:  # Playwright disabled
            try:
                items = await self._search_playwright(query, max_results, sold=False)
            except Exception as e:
                print(f"Playwright failed: {e}")
        
        return items
    
    def _parse_active_listing(self, listing) -> Optional[ScrapedItem]:
        """Parse an active listing."""
        # Reuse the sold listing parser - structure is similar
        return self._parse_sold_listing(listing)
    
    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        """Get full item details."""
        url = f"{self.BASE_URL}/listings/{item_id}"
        
        try:
            response = await self.fetch(url)
            soup = BeautifulSoup(response.text, "lxml")
            
            # Try to get data from __NEXT_DATA__
            script_el = soup.select_one("script#__NEXT_DATA__")
            if script_el:
                try:
                    data = json.loads(script_el.string)
                    listing = data.get("props", {}).get("pageProps", {}).get("listing", {})
                    if listing:
                        return self._parse_nextjs_listing(listing)
                except (json.JSONDecodeError, KeyError):
                    pass
            
            # Fallback to basic HTML parsing
            title = ""
            title_el = soup.select_one("h1")
            if title_el:
                title = title_el.get_text(strip=True)
            
            price = 0.0
            for selector in ["[class*='price']", "span[class*='Price']"]:
                price_el = soup.select_one(selector)
                if price_el:
                    price = self.parse_price(price_el.get_text())
                    if price > 0:
                        break
            
            return ScrapedItem(
                source=self.SOURCE_NAME,
                source_id=item_id,
                url=url,
                title=title,
                price=price,
            )
            
        except Exception as e:
            print(f"Error getting item details: {e}")
            return None
    
    async def check_availability(self, item_id: str) -> bool:
        """Grailed items - not for purchasing through us."""
        return True

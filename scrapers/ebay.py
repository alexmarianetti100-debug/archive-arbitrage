"""
eBay scraper - uses Browse API + scraping fallback.
"""

import os
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode, quote_plus

from bs4 import BeautifulSoup

from .base import BaseScraper, ScrapedItem


class EbayScraper(BaseScraper):
    """Scrape eBay listings for archive fashion."""
    
    SOURCE_NAME = "ebay"
    BASE_URL = "https://www.ebay.com"
    
    # Slower rate limiting for eBay without residential proxies
    MIN_DELAY = 5.0
    MAX_DELAY = 10.0
    
    # eBay category IDs
    CATEGORIES = {
        "mens_clothing": 1059,
        "womens_clothing": 15724,
        "mens_shoes": 93427,
        "womens_shoes": 3034,
    }
    
    def __init__(self, headless: bool = True, use_api: bool = False, use_proxies: bool = False):
        # Disable proxies by default - datacenter proxies get blocked by eBay's Akamai CDN
        # Enable only if you have residential proxies (SmartProxy/BrightData)
        super().__init__(headless, use_proxies=use_proxies)
        self.use_api = use_api
        self.app_id = os.getenv("EBAY_APP_ID")
    
    def _is_challenge_page(self, soup) -> bool:
        """Check if eBay served a bot detection / challenge page."""
        page_text = soup.get_text().lower()
        
        # Common indicators of bot detection (must be explicit)
        challenge_indicators = [
            "please verify you're a human",
            "robot or human",
            "captcha",
            "unusual traffic",
            "automated access",
            "pardon our interruption",
            "access denied",
            "blocked",
        ]
        
        for indicator in challenge_indicators:
            if indicator in page_text:
                return True
        
        # Check for very short pages (likely error/challenge) - but not TOO aggressive
        if len(page_text) < 200:
            return True
        
        # Only flag as challenge if we explicitly see eBay branding but NO results structure at all
        # This handles the case where results simply don't exist vs blocked
        has_ebay = "ebay" in page_text
        has_results = (
            soup.select_one("ul.srp-results") or 
            soup.select("li.s-item") or 
            soup.select("a[href*='/itm/']") or
            "no exact matches found" in page_text or  # Legit empty results
            "0 results" in page_text or
            "did not match any" in page_text
        )
        
        # If it's an eBay page with no results structure AND no "no results" message, suspicious
        if has_ebay and not has_results and len(page_text) < 2000:
            return True
        
        return False
        
    def _build_search_url(
        self,
        query: str,
        category_id: Optional[int] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        condition: Optional[str] = None,  # "new", "used"
        buy_it_now: bool = False,
        sort: str = "newly_listed",
    ) -> str:
        """Build eBay search URL with filters."""
        params = {
            "_nkw": query,
            "_sop": {
                "newly_listed": 10,
                "ending_soonest": 1,
                "price_low": 15,
                "price_high": 16,
            }.get(sort, 10),
        }
        
        if category_id:
            params["_sacat"] = category_id
        
        if min_price:
            params["_udlo"] = min_price
        
        if max_price:
            params["_udhi"] = max_price
            
        if buy_it_now:
            params["LH_BIN"] = 1
            
        if condition == "used":
            params["LH_ItemCondition"] = 3000
        elif condition == "new":
            params["LH_ItemCondition"] = 1000
            
        return f"{self.BASE_URL}/sch/i.html?{urlencode(params)}"
    
    async def search(
        self,
        query: str,
        max_results: int = 50,
        category_id: Optional[int] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> list[ScrapedItem]:
        """Search eBay for items."""
        items = []
        url = self._build_search_url(
            query=query,
            category_id=category_id or self.CATEGORIES["mens_clothing"],
            min_price=min_price,
            max_price=max_price,
        )
        
        # Try up to 3 times with longer delays if we hit bot detection
        max_attempts = 3
        for attempt in range(max_attempts):
            response = await self.fetch(url)
            soup = BeautifulSoup(response.text, "lxml")
            
            # Check for bot detection page
            if self._is_challenge_page(soup):
                if attempt < max_attempts - 1:
                    import asyncio
                    import random
                    delay = random.uniform(5, 10) * (attempt + 1)
                    print(f"eBay bot detection triggered, waiting {delay:.1f}s before retry...")
                    await asyncio.sleep(delay)
                    # Rotate user agent
                    self.client.headers["User-Agent"] = self._get_user_agent()
                    continue
                else:
                    print("eBay bot detection: Max retries exceeded. Try again later or use a different network.")
                    return []
            break
        
        # Multiple strategies to find listings (eBay changes their HTML frequently)
        listings = []
        
        # Strategy 1: New eBay structure with ul.srp-results
        results_container = soup.select_one("ul.srp-results")
        if results_container:
            listings = results_container.select("li.s-item")
        
        # Strategy 2: Alternate new structure
        if not listings:
            listings = soup.select("li.s-item")
        
        # Strategy 3: Card-based layout
        if not listings:
            listings = soup.select("div.s-item__wrapper")
        
        # Strategy 4: Search by data attributes
        if not listings:
            listings = soup.select("[data-viewport]")
        
        # Strategy 5: Find all links to items and work backwards
        if not listings:
            item_links = soup.select("a[href*='/itm/']")
            # Get parent containers
            for link in item_links:
                parent = link.find_parent("li") or link.find_parent("div", class_=lambda x: x and 's-item' in str(x))
                if parent and parent not in listings:
                    listings.append(parent)
        
        parsed_ids = set()  # Avoid duplicates
        for listing in listings[:max_results * 2]:  # Parse more to account for skips
            if len(items) >= max_results:
                break
            try:
                item = self._parse_listing(listing)
                if item and item.source_id not in parsed_ids:
                    parsed_ids.add(item.source_id)
                    items.append(item)
            except Exception as e:
                # Log but continue
                print(f"Error parsing listing: {e}")
                continue
                
        return items
    
    def _parse_listing(self, listing) -> Optional[ScrapedItem]:
        """Parse a single listing element."""
        # Get link - try multiple selectors
        link_el = None
        for selector in [
            "a[href*='/itm/']",
            "a.s-item__link",
            "a.s-card__link",
            "div.s-card a",
        ]:
            link_el = listing.select_one(selector)
            if link_el:
                break
        
        if not link_el:
            return None
            
        url = link_el.get("href", "")
        
        # Extract item ID from URL
        item_id_match = re.search(r'/itm/(\d+)', url)
        if not item_id_match:
            return None
        item_id = item_id_match.group(1)
        
        # Get title - try multiple selectors
        title = ""
        for selector in [
            "div.s-item__title span",
            "h3.s-item__title",
            "div.s-card__title",
            ".s-item__title",
            "h3",
            ".title",
        ]:
            title_el = listing.select_one(selector)
            if title_el:
                title = title_el.get_text(strip=True)
                break
        
        # Fallback: get text from the link itself
        if not title:
            title = link_el.get_text(strip=True)
        
        # Skip promotional/placeholder items
        if not title or "Shop on eBay" in title or len(title) < 5:
            return None
        
        # Clean up title (remove "Opens in new window" etc)
        title = re.sub(r'Opens in a new (window|tab).*$', '', title, flags=re.IGNORECASE).strip()
        title = re.sub(r'New Listing', '', title, flags=re.IGNORECASE).strip()
        
        # Get price - multiple strategies
        price = 0.0
        
        # Strategy 1: Find span with price class
        for selector in [
            "span.s-item__price",
            ".s-item__price",
            "span.s-card__price",
            "[class*='price']",
        ]:
            price_el = listing.select_one(selector)
            if price_el:
                price_text = price_el.get_text(strip=True)
                # Handle price ranges (take the lower price)
                if " to " in price_text:
                    price_text = price_text.split(" to ")[0]
                price = self.parse_price(price_text)
                if price > 0:
                    break
        
        # Strategy 2: Look for dollar amount pattern in all text
        if price == 0:
            listing_text = listing.get_text()
            price_matches = re.findall(r'\$[\d,]+\.?\d{0,2}', listing_text)
            if price_matches:
                # Take the first reasonable price (not shipping usually)
                for match in price_matches:
                    parsed = self.parse_price(match)
                    if parsed > 0:
                        price = parsed
                        break
        
        # Get image
        images = []
        for selector in [
            "img[src*='ebayimg']",
            "img.s-item__image-img",
            "img.s-card__image",
            "img",
        ]:
            img_el = listing.select_one(selector)
            if img_el:
                img_url = img_el.get("src") or img_el.get("data-src")
                if img_url and "ebayimg" in img_url:
                    # Try to get higher res version
                    img_url = re.sub(r's-l\d+', 's-l500', img_url)
                    images.append(img_url)
                    break
        
        # Get shipping
        shipping_cost = None
        for selector in ["span.s-item__shipping", ".s-item__shipping", "[class*='shipping']"]:
            shipping_el = listing.select_one(selector)
            if shipping_el:
                shipping_text = shipping_el.get_text()
                if "Free" in shipping_text:
                    shipping_cost = 0.0
                else:
                    shipping_cost = self.parse_price(shipping_text)
                break
        
        # Check if auction (look for bid-related text)
        is_auction = False
        listing_text = listing.get_text().lower()
        if "bid" in listing_text or "auction" in listing_text:
            is_auction = True
        
        # Extract size from title
        size = self.extract_size(title)
        
        return ScrapedItem(
            source=self.SOURCE_NAME,
            source_id=item_id,
            url=url,
            title=title,
            price=price,
            currency="USD",
            size=size,
            images=images,
            shipping_cost=shipping_cost,
            is_auction=is_auction,
        )
    
    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        """Get full item details from listing page."""
        url = f"{self.BASE_URL}/itm/{item_id}"
        
        page = await self.get_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)  # Let JS render
            
            content = await page.content()
            soup = BeautifulSoup(content, "lxml")
            
            # Title
            title_el = soup.select_one("h1.x-item-title__mainTitle span")
            title = title_el.text.strip() if title_el else ""
            
            # Price
            price_el = soup.select_one("div.x-price-primary span.ux-textspans")
            price = self.parse_price(price_el.text) if price_el else 0.0
            
            # Images
            images = []
            img_els = soup.select("div.ux-image-carousel-item img")
            for img in img_els:
                src = img.get("src") or img.get("data-src")
                if src and "s-l" in src:
                    # Get higher res version
                    src = re.sub(r's-l\d+', 's-l1600', src)
                    images.append(src)
            
            # Description
            desc_el = soup.select_one("div.x-item-description iframe")
            description = None
            # Note: Description is in iframe, would need to fetch separately
            
            # Condition
            condition_el = soup.select_one("div.x-item-condition-text span")
            condition = condition_el.text.strip() if condition_el else None
            
            # Seller
            seller_el = soup.select_one("div.x-sellercard-atf__info a span")
            seller = seller_el.text.strip() if seller_el else None
            
            return ScrapedItem(
                source=self.SOURCE_NAME,
                source_id=item_id,
                url=url,
                title=title,
                price=price,
                currency="USD",
                condition=condition,
                images=images,
                description=description,
                seller=seller,
                size=self.extract_size(title),
            )
            
        finally:
            await page.close()
    
    async def check_availability(self, item_id: str) -> bool:
        """Check if item is still available."""
        url = f"{self.BASE_URL}/itm/{item_id}"
        
        try:
            response = await self.fetch(url)
            soup = BeautifulSoup(response.text, "lxml")
            
            # Check for sold/ended indicators
            ended_el = soup.select_one("div.vi-notify-msg")
            if ended_el and ("ended" in ended_el.text.lower() or "sold" in ended_el.text.lower()):
                return False
            
            # Check for buy button
            buy_btn = soup.select_one("a.ux-call-to-action--primary")
            return buy_btn is not None
            
        except Exception:
            return False

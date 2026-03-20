"""
Vinted Scraper - Fixed Implementation

Uses the "Cookie Factory" approach to obtain authentication tokens.
Falls back to disabled state if Vinted is unreachable.

As of March 2025, Vinted requires:
1. Valid access_token_web cookie
2. Proper User-Agent
3. Session management

This implementation:
- Fetches fresh cookies via Vinted's cookie endpoint
- Rotates through working domains
- Implements health checks
- Gracefully degrades if blocked
"""

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import quote_plus, urljoin

import httpx

# Handle imports - works both as module and direct execution
try:
    from .base import BaseScraper, ScrapedItem
except ImportError:
    # When run directly
    sys.path.insert(0, str(Path(__file__).parent))
    from base import BaseScraper, ScrapedItem

logger = logging.getLogger("scraper.vinted")

# Domains known to work (reduced from 20 to most reliable)
WORKING_DOMAINS = [
    "https://www.vinted.com",       # US / global - most reliable
    "https://www.vinted.co.uk",     # UK
    "https://www.vinted.fr",        # France
    "https://www.vinted.de",        # Germany
]

# Health tracking
HEALTH_FILE = Path(__file__).parent.parent / "data" / "vinted_health.json"


class VintedHealthTracker:
    """Track Vinted scraper health and auto-disable if consistently failing."""
    
    def __init__(self):
        self.failures = 0
        self.last_success = None
        self.consecutive_failures = 0
        self.disabled_until = None
        self._load()
    
    def _load(self):
        """Load health state from file."""
        if HEALTH_FILE.exists():
            try:
                import json
                with open(HEALTH_FILE) as f:
                    data = json.load(f)
                    self.failures = data.get("failures", 0)
                    self.last_success = data.get("last_success")
                    self.consecutive_failures = data.get("consecutive_failures", 0)
                    disabled_until = data.get("disabled_until")
                    if disabled_until:
                        self.disabled_until = datetime.fromisoformat(disabled_until)
            except Exception:
                pass
    
    def _save(self):
        """Save health state to file."""
        try:
            import json
            HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(HEALTH_FILE, "w") as f:
                json.dump({
                    "failures": self.failures,
                    "last_success": self.last_success,
                    "consecutive_failures": self.consecutive_failures,
                    "disabled_until": self.disabled_until.isoformat() if self.disabled_until else None,
                    "updated_at": datetime.now().isoformat(),
                }, f, indent=2)
        except Exception:
            pass
    
    def record_success(self):
        """Record a successful scrape."""
        self.consecutive_failures = 0
        self.last_success = datetime.now().isoformat()
        self.disabled_until = None
        self._save()
    
    def record_failure(self):
        """Record a failed scrape."""
        self.failures += 1
        self.consecutive_failures += 1
        
        # Disable for 1 hour after 5 consecutive failures
        if self.consecutive_failures >= 5:
            self.disabled_until = datetime.now() + timedelta(hours=1)
            logger.warning(f"Vinted disabled until {self.disabled_until} due to {self.consecutive_failures} consecutive failures")
        
        self._save()
    
    def is_disabled(self) -> bool:
        """Check if Vinted is currently disabled."""
        if self.disabled_until and datetime.now() < self.disabled_until:
            return True
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current health status."""
        return {
            "healthy": self.consecutive_failures == 0,
            "consecutive_failures": self.consecutive_failures,
            "total_failures": self.failures,
            "last_success": self.last_success,
            "disabled": self.is_disabled(),
            "disabled_until": self.disabled_until.isoformat() if self.disabled_until else None,
        }


class VintedCookieFactory:
    """Factory for obtaining Vinted authentication cookies."""
    
    def __init__(self, domain: str = "https://www.vinted.com"):
        self.domain = domain
        self._cookies: Dict[str, str] = {}
        self._expires: Optional[datetime] = None
    
    async def get_cookies(self) -> Dict[str, str]:
        """Get fresh cookies, fetching new ones if expired."""
        if self._is_valid():
            return self._cookies
        
        await self._fetch_fresh()
        return self._cookies
    
    def _is_valid(self) -> bool:
        """Check if current cookies are still valid."""
        if not self._cookies.get("access_token_web"):
            return False
        if self._expires and datetime.now() >= self._expires:
            return False
        return True
    
    async def _fetch_fresh(self):
        """Fetch fresh cookies from Vinted."""
        logger.debug(f"Fetching fresh cookies from {self.domain}")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                # First, get the main page to establish session
                response = await client.get(
                    self.domain,
                    headers=headers,
                )
                
                # Extract cookies from response
                cookies = {}
                if "set-cookie" in response.headers:
                    cookie_header = response.headers["set-cookie"]
                    # Parse simple cookies
                    for cookie in cookie_header.split(","):
                        if "=" in cookie:
                            key, value = cookie.split("=", 1)
                            key = key.strip()
                            value = value.split(";")[0].strip()
                            cookies[key] = value
                
                # Also check cookies from client jar
                for cookie in client.cookies.jar:
                    cookies[cookie.name] = cookie.value
                
                if "access_token_web" in cookies:
                    self._cookies = cookies
                    # Cookies typically valid for ~2 hours
                    self._expires = datetime.now() + timedelta(hours=1, minutes=30)
                    logger.debug(f"✅ Got fresh cookies, expires at {self._expires}")
                else:
                    logger.warning("❌ No access_token_web in cookies")
                    self._cookies = {}
                    
        except Exception as e:
            logger.error(f"Failed to fetch cookies: {e}")
            self._cookies = {}


class VintedScraperFixed(BaseScraper):
    """
    Fixed Vinted scraper with cookie factory and health tracking.
    
    Features:
    - Automatic cookie management
    - Health tracking with auto-disable
    - Domain rotation
    - Graceful degradation
    """

    SOURCE_NAME = "vinted"
    
    def __init__(self, domains: Optional[List[str]] = None, proxy_manager=None):
        super().__init__(proxy_manager)
        self.domains = domains or WORKING_DOMAINS
        self.health = VintedHealthTracker()
        self.cookie_factories = {domain: VintedCookieFactory(domain) for domain in self.domains}
        self._proxy = self._build_proxy()
    
    def _build_proxy(self) -> Optional[str]:
        """Build proxy URL from environment."""
        host = os.getenv("PROXY_HOST", "p.webshare.io")
        port = os.getenv("PROXY_PORT", "10000")
        user = os.getenv("PROXY_USERNAME", "")
        pwd = os.getenv("PROXY_PASSWORD", "")
        if user and pwd:
            return f"http://{user}:{pwd}@{host}:{port}"
        return None
    
    async def search(self, query: str, max_results: int = 20) -> List[ScrapedItem]:
        """
        Search Vinted with health tracking and fallback.
        """
        # Check if disabled
        if self.health.is_disabled():
            logger.debug("Vinted is temporarily disabled due to failures")
            return []
        
        all_items: List[ScrapedItem] = []
        domains_attempted = 0
        domains_succeeded = 0
        
        for domain in self.domains:
            try:
                items = await self._search_domain(domain, query, max_results // len(self.domains) + 5)
                domains_attempted += 1
                
                if items:
                    all_items.extend(items)
                    domains_succeeded += 1
                    logger.info(f"✅ Vinted ({domain}): {len(items)} items for '{query}'")
                else:
                    logger.debug(f"⚠️  Vinted ({domain}): 0 items for '{query}'")
                    
            except Exception as e:
                domains_attempted += 1
                logger.warning(f"❌ Vinted ({domain}): {type(e).__name__}: {e}")
        
        # Update health status
        if domains_succeeded > 0:
            self.health.record_success()
        elif domains_attempted > 0:
            self.health.record_failure()
        
        # Deduplicate by title + price
        seen: set = set()
        unique: List[ScrapedItem] = []
        for item in all_items:
            key = f"{item.title.lower().strip()[:40]}|{item.price}"
            if key not in seen:
                seen.add(key)
                unique.append(item)
        
        return unique[:max_results]
    
    async def _search_domain(self, domain: str, query: str, max_results: int) -> List[ScrapedItem]:
        """Search a single Vinted domain."""
        
        # Get fresh cookies
        cookie_factory = self.cookie_factories.get(domain)
        if not cookie_factory:
            return []
        
        cookies = await cookie_factory.get_cookies()
        if not cookies.get("access_token_web"):
            logger.warning(f"No valid cookies for {domain}")
            return []
        
        # Build API URL
        api_url = f"{domain}/api/v2/catalog/items"
        params = {
            "search_text": query,
            "per_page": max_results,
            "order": "newest_first",
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",  # Don't request brotli (br) - causes issues
            "DNT": "1",
            "Connection": "keep-alive",
            "Referer": f"{domain}/catalog?search_text={quote_plus(query)}",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        
        # Build cookie header
        cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        headers["Cookie"] = cookie_header
        
        try:
            client_kwargs = {
                "timeout": 30.0,
                "headers": headers,
            }
            if self._proxy:
                client_kwargs["proxy"] = self._proxy
            
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.get(api_url, params=params)
                
                if response.status_code == 401:
                    logger.warning(f"Vinted 401 - cookies expired for {domain}")
                    # Clear cookies to force refresh
                    cookie_factory._cookies = {}
                    return []
                
                if response.status_code == 403:
                    logger.warning(f"Vinted 403 - blocked for {domain}")
                    return []
                
                if response.status_code != 200:
                    logger.warning(f"Vinted HTTP {response.status_code} for {domain}")
                    return []
                
                data = response.json()
                items_data = data.get("items", [])
                
                return self._parse_items(items_data, domain)
                
        except httpx.TimeoutException:
            logger.warning(f"Vinted timeout for {domain}")
            return []
        except Exception as e:
            logger.warning(f"Vinted error for {domain}: {e}")
            return []
    
    def _parse_items(self, items_data: List[Dict], domain: str) -> List[ScrapedItem]:
        """Parse Vinted API items into ScrapedItem objects."""
        items: List[ScrapedItem] = []
        
        for item_data in items_data:
            try:
                # Extract fields
                item_id = str(item_data.get("id", ""))
                title = item_data.get("title", "")
                price = item_data.get("price", {}).get("amount", 0)
                currency = item_data.get("price", {}).get("currency_code", "USD")
                brand = item_data.get("brand_title", "")
                size = item_data.get("size_title", "")
                description = item_data.get("description", "")
                
                # Build URL
                item_url = f"{domain}/items/{item_id}"
                
                # Extract images
                photos = item_data.get("photos", [])
                images = []
                for photo in photos:
                    if isinstance(photo, dict):
                        img_url = photo.get("url", photo.get("full_size_url", ""))
                        if img_url:
                            images.append(img_url)
                
                # Parse timestamp
                created_at = item_data.get("created_at_ts")
                listed_at = None
                if created_at:
                    try:
                        from datetime import datetime
                        listed_at = datetime.fromtimestamp(created_at)
                    except:
                        pass
                
                if title and price > 0:
                    items.append(ScrapedItem(
                        source=self.SOURCE_NAME,
                        source_id=item_id,
                        url=item_url,
                        title=title.strip(),
                        price=float(price),
                        currency=currency,
                        brand=brand or None,
                        size=size or None,
                        images=images[:5],
                        description=description,
                        listed_at=listed_at,
                    ))
                    
            except Exception as e:
                logger.debug(f"Failed to parse Vinted item: {e}")
                continue
        
        return items
    
    async def search_sold(self, query: str, max_results: int = 20) -> List[ScrapedItem]:
        """Vinted doesn't expose sold data publicly."""
        return []
    
    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        """Get full item details (not implemented)."""
        return None
    
    async def check_availability(self, item_id: str) -> bool:
        """Check if item is still available (not implemented)."""
        return True
    
    async def close(self):
        """Cleanup (not needed for this implementation)."""
        pass
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status for monitoring."""
        return self.health.get_status()


# Backwards compatibility - use the fixed implementation
VintedScraperWrapper = VintedScraperFixed

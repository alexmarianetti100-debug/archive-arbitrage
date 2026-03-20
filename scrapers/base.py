"""
Base scraper class with proxy rotation support and advanced anti-detection.
"""

import asyncio
import hashlib
import random
import re
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .proxy_manager import ProxyManager, get_proxy_manager

# Expanded realistic user agents (Chrome 120-122, Firefox 122-123, Safari 17)
USER_AGENTS = [
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Firefox on macOS/Windows
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]

# Referer chains to simulate natural navigation
REFERER_CHAINS = {
    "ebay": [
        "https://www.google.com/",
        "https://www.google.com/search?q=ebay",
        "https://www.ebay.com/",
    ],
    "grailed": [
        "https://www.google.com/",
        "https://www.google.com/search?q=grailed",
        "https://www.grailed.com/",
    ],
    "therealreal": [
        "https://www.google.com/",
        "https://www.google.com/search?q=therealreal",
        "https://www.therealreal.com/",
    ],
    "fashionphile": [
        "https://www.google.com/",
        "https://www.google.com/search?q=fashionphile",
        "https://www.fashionphile.com/",
    ],
    "2ndstreet": [
        "https://www.google.com/",
        "https://www.google.com/search?q=2nd+street+japan",
        "https://en.2ndstreet.jp/",
    ],
    "default": [
        "https://www.google.com/",
    ],
}


@dataclass
class ScrapedItem:
    """Represents a scraped listing."""
    source: str
    source_id: str
    url: str
    title: str
    price: float
    currency: str = "USD"
    brand: Optional[str] = None
    category: Optional[str] = None
    size: Optional[str] = None
    condition: Optional[str] = None
    images: list[str] = field(default_factory=list)
    description: Optional[str] = None
    seller: Optional[str] = None
    seller_sales: Optional[int] = None
    seller_rating: Optional[float] = None
    shipping_cost: Optional[float] = None
    listed_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_auction: bool = False
    raw_data: dict = field(default_factory=dict)
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def unique_id(self) -> str:
        return hashlib.md5(f"{self.source}:{self.source_id}".encode()).hexdigest()


class BaseScraper(ABC):
    """Abstract base class for all scrapers with proxy support."""
    
    SOURCE_NAME: str = "base"
    BASE_URL: str = ""
    
    # Rate limiting
    MIN_DELAY = 0.5
    MAX_DELAY = 1.5
    
    def __init__(self, headless: bool = True, use_proxies: bool = True):
        self.headless = headless
        self.use_proxies = use_proxies
        self.browser = None
        self.client: Optional[httpx.AsyncClient] = None
        self.proxy_manager: Optional[ProxyManager] = None
        self._request_count = 0
        
    async def __aenter__(self):
        await self.setup()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.teardown()
    
    async def setup(self):
        """Initialize HTTP client with optional proxy support."""
        if self.use_proxies:
            self.proxy_manager = get_proxy_manager()
        
        self.client = await self._create_client()
    
    async def _create_client(self, proxy_url: str = None) -> httpx.AsyncClient:
        """Create an HTTP client, optionally with proxy."""
        client_kwargs = {
            "headers": self._get_headers(),
            "timeout": 30.0,
            "follow_redirects": True,
        }
        if proxy_url:
            client_kwargs["proxy"] = proxy_url
        return httpx.AsyncClient(**client_kwargs)
    
    def _get_headers(self, referer: str = None) -> dict:
        """Get realistic browser headers with dynamic sec-ch-ua matching User-Agent."""
        ua = random.choice(USER_AGENTS)
        
        # Extract Chrome version from UA for consistent sec-ch-ua
        chrome_match = re.search(r'Chrome/(\d+)', ua)
        chrome_ver = chrome_match.group(1) if chrome_match else "122"
        
        # Determine platform from UA
        if "Macintosh" in ua:
            platform = '"macOS"'
        elif "Windows" in ua:
            platform = '"Windows"'
        else:
            platform = '"Linux"'
        
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            # Don't request brotli (br) - httpx doesn't always decompress it properly
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none" if not referer else "same-origin",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
            "sec-ch-ua": f'"Not_A Brand";v="8", "Chromium";v="{chrome_ver}", "Google Chrome";v="{chrome_ver}"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": platform,
        }
        
        if referer:
            headers["Referer"] = referer
        
        return headers
    
    def _get_user_agent(self) -> str:
        return random.choice(USER_AGENTS)
    
    def _get_referer(self, url: str) -> str:
        """Get appropriate referer based on target URL."""
        for site, chain in REFERER_CHAINS.items():
            if site in url.lower():
                return random.choice(chain)
        return random.choice(REFERER_CHAINS["default"])
    
    async def _random_delay(self):
        """Add human-like delay between requests using normal distribution."""
        # Mean delay at midpoint, with some variance
        mean = (self.MIN_DELAY + self.MAX_DELAY) / 2
        std_dev = (self.MAX_DELAY - self.MIN_DELAY) / 4
        
        # Use normal distribution for more natural timing
        delay = random.gauss(mean, std_dev)
        delay = max(self.MIN_DELAY, min(delay, self.MAX_DELAY * 1.5))  # Clamp
        
        # Occasionally add longer "thinking" pauses (5% chance)
        if random.random() < 0.05:
            delay += random.uniform(2, 5)
        
        await asyncio.sleep(delay)
    
    async def teardown(self):
        """Cleanup resources."""
        if self.client:
            await self.client.aclose()
        if self.browser:
            await self.browser.close()
    
    async def fetch(self, url: str, max_retries: int = 3) -> httpx.Response:
        """Fetch URL with proxy rotation, cookies, referer simulation, and retries."""
        await self._random_delay()
        self._request_count += 1
        
        last_error = None
        referer = self._get_referer(url)
        
        for attempt in range(max_retries):
            # Get a proxy if available
            proxy_url = None
            current_proxy = None
            if self.use_proxies and self.proxy_manager and self.proxy_manager.count > 0:
                current_proxy = self.proxy_manager.get_proxy()
                proxy_url = current_proxy.url if current_proxy else None
            
            try:
                # Create client with cookies enabled for session persistence
                async with httpx.AsyncClient(
                    headers=self._get_headers(referer=referer),
                    timeout=20.0,
                    follow_redirects=True,
                    proxy=proxy_url,
                    cookies=httpx.Cookies(),  # Enable cookie jar
                ) as client:
                    response = await client.get(url)
                    
                    # Check for bot detection status codes
                    if response.status_code == 503:
                        raise httpx.HTTPStatusError("503 Service Unavailable - likely bot detection", request=response.request, response=response)
                    if response.status_code == 429:
                        raise httpx.HTTPStatusError("429 Too Many Requests - rate limited", request=response.request, response=response)
                    if response.status_code == 403:
                        raise httpx.HTTPStatusError("403 Forbidden - blocked", request=response.request, response=response)
                    
                    return response
                    
            except Exception as e:
                last_error = e
                
                # Mark proxy as failed if using proxies
                if current_proxy and self.proxy_manager:
                    self.proxy_manager.mark_failed(current_proxy)
                
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    base_wait = 3 * (2 ** attempt)  # 3s, 6s, 12s
                    jitter = random.uniform(0, base_wait * 0.5)
                    wait_time = base_wait + jitter
                    print(f"  ⏳ Retry {attempt + 1}/{max_retries} in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
        
        raise last_error or Exception("Max retries exceeded")
    
    def parse_price(self, price_str: str) -> float:
        """Extract numeric price from string."""
        if not price_str:
            return 0.0
        cleaned = re.sub(r'[^\d.]', '', price_str)
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    
    def extract_size(self, text: str) -> Optional[str]:
        """Try to extract size from text."""
        text_upper = text.upper()
        patterns = [
            r'\b(XXS|XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL)\b',
            r'\bSIZE\s*(\d{1,2})\b',
            r'\b(\d{1,2})\s*(US|EU|UK|IT|FR)\b',
            r'\b(OS|ONE SIZE|OSFA|O/S)\b',
            r'\b(\d{2})\b(?=\s|$|[^\d])',
        ]
        for pattern in patterns:
            match = re.search(pattern, text_upper)
            if match:
                return match.group(1)
        return None
    
    @abstractmethod
    async def search(self, query: str, max_results: int = 50) -> list[ScrapedItem]:
        pass
    
    @abstractmethod
    async def get_item_details(self, item_id: str) -> Optional[ScrapedItem]:
        pass
    
    @abstractmethod
    async def check_availability(self, item_id: str) -> bool:
        pass

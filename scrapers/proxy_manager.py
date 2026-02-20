"""
Proxy Manager for rotating proxies to avoid bot detection.

Supports:
1. Free proxy lists (less reliable)
2. Paid proxy services (Bright Data, Oxylabs, SmartProxy)
3. Custom proxy lists

Usage:
    # With free proxies
    manager = ProxyManager()
    await manager.load_free_proxies()
    
    # With paid service (Bright Data example)
    manager = ProxyManager(
        service="brightdata",
        username="your_username",
        password="your_password",
        host="brd.superproxy.io",
        port=22225
    )
"""

import asyncio
import random
import os
from typing import Optional, List
from dataclasses import dataclass
import httpx


@dataclass
class Proxy:
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"
    
    @property
    def url(self) -> str:
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"
    
    def __str__(self):
        return f"{self.host}:{self.port}"


class ProxyManager:
    """Manages proxy rotation for scraping."""
    
    # Free proxy list sources
    FREE_PROXY_URLS = [
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    ]
    
    def __init__(
        self,
        service: Optional[str] = None,  # brightdata, oxylabs, smartproxy, custom
        username: Optional[str] = None,
        password: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        country: str = "us",
    ):
        self.service = service
        self.username = username or os.getenv("PROXY_USERNAME")
        self.password = password or os.getenv("PROXY_PASSWORD")
        self.host = host or os.getenv("PROXY_HOST")
        self.port = port or int(os.getenv("PROXY_PORT", "0")) or None
        self.country = country
        
        self.proxies: List[Proxy] = []
        self.failed_proxies: set = set()
        self._index = 0
    
    def configure_brightdata(self, username: str, password: str, country: str = "us"):
        """Configure Bright Data (formerly Luminati) rotating proxies."""
        self.service = "brightdata"
        self.username = username
        self.password = password
        self.host = "brd.superproxy.io"
        self.port = 22225
        self.country = country
        
        # Bright Data handles rotation server-side
        self.proxies = [Proxy(
            host=self.host,
            port=self.port,
            username=f"{username}-country-{country}",
            password=password,
        )]
    
    def configure_oxylabs(self, username: str, password: str, country: str = "us"):
        """Configure Oxylabs rotating proxies."""
        self.service = "oxylabs"
        self.username = username
        self.password = password
        self.host = "pr.oxylabs.io"
        self.port = 7777
        self.country = country
        
        self.proxies = [Proxy(
            host=self.host,
            port=self.port,
            username=f"customer-{username}-cc-{country}",
            password=password,
        )]
    
    def configure_smartproxy(self, username: str, password: str, country: str = "us"):
        """Configure SmartProxy rotating proxies."""
        self.service = "smartproxy"
        self.username = username
        self.password = password
        self.host = "gate.smartproxy.com"
        self.port = 7000
        self.country = country
        
        self.proxies = [Proxy(
            host=self.host,
            port=self.port,
            username=f"user-{username}-country-{country}",
            password=password,
        )]
    
    def configure_webshare(self, api_key: str):
        """Configure Webshare.io proxies (affordable option)."""
        self.service = "webshare"
        # Webshare provides a list of proxies via API
        # You'd fetch from: https://proxy.webshare.io/api/v2/proxy/list/
        pass
    
    async def load_free_proxies(self, test: bool = True) -> int:
        """Load free proxies from public lists."""
        print("Loading free proxies...")
        
        async with httpx.AsyncClient(timeout=10) as client:
            for url in self.FREE_PROXY_URLS:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        lines = resp.text.strip().split("\n")
                        for line in lines:
                            line = line.strip()
                            if ":" in line:
                                parts = line.split(":")
                                if len(parts) >= 2:
                                    self.proxies.append(Proxy(
                                        host=parts[0],
                                        port=int(parts[1]),
                                    ))
                except Exception as e:
                    print(f"  Failed to load from {url}: {e}")
        
        print(f"  Loaded {len(self.proxies)} proxies")
        
        if test and self.proxies:
            await self.test_proxies(sample_size=20)
        
        return len(self.proxies)
    
    async def test_proxies(self, sample_size: int = 10) -> int:
        """Test a sample of proxies and remove dead ones."""
        if not self.proxies:
            return 0
        
        sample = random.sample(self.proxies, min(sample_size, len(self.proxies)))
        working = []
        
        print(f"  Testing {len(sample)} proxies...")
        
        async def test_one(proxy: Proxy) -> bool:
            try:
                async with httpx.AsyncClient(
                    proxies=proxy.url,
                    timeout=10,
                ) as client:
                    resp = await client.get("https://httpbin.org/ip")
                    return resp.status_code == 200
            except:
                return False
        
        tasks = [test_one(p) for p in sample]
        results = await asyncio.gather(*tasks)
        
        for proxy, works in zip(sample, results):
            if works:
                working.append(proxy)
            else:
                self.failed_proxies.add(str(proxy))
        
        # Keep only proxies not in failed set
        self.proxies = [p for p in self.proxies if str(p) not in self.failed_proxies]
        
        print(f"  {len(working)}/{len(sample)} working, {len(self.proxies)} total remaining")
        return len(working)
    
    def add_proxy(self, host: str, port: int, username: str = None, password: str = None):
        """Add a custom proxy."""
        self.proxies.append(Proxy(host, port, username, password))
    
    def get_proxy(self) -> Optional[Proxy]:
        """Get next proxy in rotation."""
        if not self.proxies:
            return None
        
        proxy = self.proxies[self._index % len(self.proxies)]
        self._index += 1
        return proxy
    
    def get_random_proxy(self) -> Optional[Proxy]:
        """Get a random proxy."""
        if not self.proxies:
            return None
        return random.choice(self.proxies)
    
    def mark_failed(self, proxy: Proxy):
        """Mark a proxy as failed."""
        self.failed_proxies.add(str(proxy))
        self.proxies = [p for p in self.proxies if str(p) != str(proxy)]
    
    def get_httpx_proxies(self) -> Optional[str]:
        """Get proxy URL for httpx client."""
        proxy = self.get_proxy()
        return proxy.url if proxy else None
    
    @property
    def count(self) -> int:
        return len(self.proxies)
    
    def __len__(self):
        return len(self.proxies)


# Singleton instance
_proxy_manager: Optional[ProxyManager] = None

def get_proxy_manager() -> ProxyManager:
    """Get or create the global proxy manager, auto-configuring from env if available."""
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()
        
        # Auto-configure from environment variables
        service = os.getenv("PROXY_SERVICE")
        host = os.getenv("PROXY_HOST")
        port = os.getenv("PROXY_PORT")
        username = os.getenv("PROXY_USERNAME")
        password = os.getenv("PROXY_PASSWORD")
        
        if service and host and port and username and password:
            # Webshare or similar rotating proxy service
            _proxy_manager.proxies = [Proxy(
                host=host,
                port=int(port),
                username=username,
                password=password,
            )]
            _proxy_manager.service = service
            print(f"  📡 Loaded {service} proxy: {host}:{port}")
    
    return _proxy_manager

def configure_proxies(service: str, **kwargs):
    """Configure the global proxy manager."""
    global _proxy_manager
    _proxy_manager = ProxyManager()
    
    if service == "brightdata":
        _proxy_manager.configure_brightdata(**kwargs)
    elif service == "oxylabs":
        _proxy_manager.configure_oxylabs(**kwargs)
    elif service == "smartproxy":
        _proxy_manager.configure_smartproxy(**kwargs)
    elif service == "free":
        asyncio.run(_proxy_manager.load_free_proxies())
    
    return _proxy_manager

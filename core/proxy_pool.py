"""
Proxy Pool Manager for Japan Scrapers

Simple, cost-effective proxy rotation for Webshare and similar providers.
"""

import json
import logging
import random
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("proxy_pool")


@dataclass
class Proxy:
    """Proxy configuration."""
    id: str
    host: str
    port: int
    username: str
    password: str
    country: str
    type: str = "http"
    # Stats
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[str] = None
    is_active: bool = True


class ProxyPool:
    """Simple rotating proxy pool."""
    
    def __init__(self, config_path: str = "data/proxy_config.json"):
        self.config_path = Path(config_path)
        self.proxies: List[Proxy] = []
        self.current_index = 0
        self.max_concurrent = 2
        self.rotation_mode = "per_domain"
        self.headful = True
        self.retry_attempts = 3
        
        self._load_config()
    
    def _load_config(self):
        """Load proxy configuration."""
        try:
            if not self.config_path.exists():
                logger.warning(f"Proxy config not found at {self.config_path}")
                return
            
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Load proxies
            for p in config.get('proxies', []):
                self.proxies.append(Proxy(
                    id=p['id'],
                    host=p['host'],
                    port=p['port'],
                    username=p['username'],
                    password=p['password'],
                    country=p['country'],
                    type=p.get('type', 'http'),
                ))
            
            # Load settings
            self.rotation_mode = config.get('rotation_mode', 'per_domain')
            self.max_concurrent = config.get('max_concurrent', 2)
            self.headful = config.get('headful', True)
            self.retry_attempts = config.get('retry_attempts', 3)
            
            logger.info(f"Loaded {len(self.proxies)} proxies from config")
            
        except Exception as e:
            logger.error(f"Error loading proxy config: {e}")
    
    def get_next_proxy(self) -> Optional[Proxy]:
        """Get next available proxy (round-robin)."""
        if not self.proxies:
            return None
        
        # Find next active proxy
        attempts = 0
        while attempts < len(self.proxies):
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            
            if proxy.is_active:
                return proxy
            
            attempts += 1
        
        # All proxies inactive
        logger.warning("All proxies marked inactive")
        return None
    
    def get_proxy_for_domain(self, domain: str) -> Optional[Proxy]:
        """Get a proxy for specific domain (consistent per domain)."""
        if not self.proxies:
            return None
        
        # Use domain hash to pick consistent proxy
        domain_hash = hash(domain) % len(self.proxies)
        proxy = self.proxies[domain_hash]
        
        if proxy.is_active:
            return proxy
        
        # Fallback to next available
        return self.get_next_proxy()
    
    def mark_success(self, proxy_id: str):
        """Mark proxy as successful."""
        for p in self.proxies:
            if p.id == proxy_id:
                p.success_count += 1
                break
    
    def mark_failure(self, proxy_id: str, is_blocking: bool = False):
        """Mark proxy failure. Temporarily disable if blocking detected."""
        for p in self.proxies:
            if p.id == proxy_id:
                p.failure_count += 1
                
                # If blocking detected, temporarily disable
                if is_blocking and p.failure_count > 3:
                    logger.warning(f"Disabling proxy {p.id} due to repeated blocks")
                    p.is_active = False
                
                break
    
    def get_stats(self) -> Dict[str, Any]:
        """Get proxy pool statistics."""
        return {
            'total': len(self.proxies),
            'active': sum(1 for p in self.proxies if p.is_active),
            'proxies': [
                {
                    'id': p.id,
                    'country': p.country,
                    'success': p.success_count,
                    'failures': p.failure_count,
                    'active': p.is_active,
                }
                for p in self.proxies
            ]
        }
    
    def get_playwright_proxy(self, proxy: Proxy) -> Dict[str, str]:
        """Get proxy config for Playwright."""
        server = f"{proxy.type}://{proxy.host}:{proxy.port}"
        
        return {
            'server': server,
            'username': proxy.username,
            'password': proxy.password,
        }


# Global proxy pool instance
_proxy_pool: Optional[ProxyPool] = None


def get_proxy_pool(config_path: str = "data/proxy_config.json") -> ProxyPool:
    """Get or create global proxy pool."""
    global _proxy_pool
    if _proxy_pool is None:
        _proxy_pool = ProxyPool(config_path)
    return _proxy_pool

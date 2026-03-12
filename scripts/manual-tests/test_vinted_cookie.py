#!/usr/bin/env python3
"""
Standalone Vinted Cookie Test
Tests cookie fetching without importing the full scraper chain.
"""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import quote_plus

import httpx


class SimpleVintedCookieFactory:
    """Simplified cookie factory for testing."""
    
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
        print(f"Fetching fresh cookies from {self.domain}...")
        
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
        
        # Build proxy if configured
        proxy = None
        proxy_host = os.getenv("PROXY_HOST")
        proxy_port = os.getenv("PROXY_PORT")
        proxy_user = os.getenv("PROXY_USERNAME")
        proxy_pass = os.getenv("PROXY_PASSWORD")
        
        if proxy_user and proxy_pass:
            proxy = f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
            print(f"Using proxy: {proxy_host}:{proxy_port}")
        else:
            print("No proxy configured")
        
        try:
            client_kwargs = {
                "timeout": 30.0,
                "follow_redirects": True,
            }
            if proxy:
                client_kwargs["proxy"] = proxy
            
            async with httpx.AsyncClient(**client_kwargs) as client:
                print("Sending request...")
                response = await client.get(
                    self.domain,
                    headers=headers,
                )
                
                print(f"Response status: {response.status_code}")
                print(f"Response headers: {dict(response.headers)}")
                
                # Extract cookies from response
                cookies = {}
                
                # Get cookies from response headers
                if "set-cookie" in response.headers:
                    cookie_header = response.headers["set-cookie"]
                    print(f"\nSet-Cookie header: {cookie_header[:200]}...")
                    
                    # Parse simple cookies
                    for cookie in cookie_header.split(","):
                        if "=" in cookie:
                            parts = cookie.split(";", 1)[0]  # Get just the name=value part
                            if "=" in parts:
                                key, value = parts.split("=", 1)
                                key = key.strip()
                                value = value.strip()
                                cookies[key] = value
                
                # Also check cookies from client jar
                for cookie in client.cookies.jar:
                    cookies[cookie.name] = cookie.value
                
                print(f"\nCookies found: {list(cookies.keys())}")
                
                if "access_token_web" in cookies:
                    self._cookies = cookies
                    self._expires = datetime.now() + timedelta(hours=1, minutes=30)
                    print(f"✅ Got access_token_web: {cookies['access_token_web'][:30]}...")
                else:
                    print("❌ No access_token_web in cookies")
                    self._cookies = {}
                    
        except Exception as e:
            print(f"❌ Failed to fetch cookies: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            self._cookies = {}


async def test_api_with_cookies():
    """Test API call with obtained cookies."""
    print("\n" + "="*60)
    print("Testing Vinted API with Cookies")
    print("="*60)
    
    # Get cookies
    factory = SimpleVintedCookieFactory()
    cookies = await factory.get_cookies()
    
    if not cookies.get("access_token_web"):
        print("❌ No valid cookies - cannot test API")
        return False
    
    # Build API request
    domain = "https://www.vinted.com"
    api_url = f"{domain}/api/v2/catalog/items"
    params = {
        "search_text": "nike",
        "per_page": 5,
        "order": "newest_first",
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Referer": f"{domain}/catalog?search_text=nike",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    
    # Add cookies to header
    cookie_header = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    headers["Cookie"] = cookie_header
    
    print(f"\nRequesting: {api_url}")
    print(f"With cookies: {cookie_header[:100]}...")
    
    try:
        # Don't request brotli encoding
        headers["Accept-Encoding"] = "gzip, deflate"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(api_url, params=params, headers=headers)
            
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            print(f"Content-Encoding: {response.headers.get('content-encoding', 'none')}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    items = data.get("items", [])
                    print(f"✅ Success! Found {len(items)} items")
                except Exception as e:
                    print(f"❌ JSON parse error: {e}")
                    return False
                
                if items:
                    print(f"\nFirst item:")
                    item = items[0]
                    print(f"  Title: {item.get('title', 'N/A')}")
                    print(f"  Price: {item.get('price', {}).get('amount', 'N/A')}")
                
                return True
            else:
                print(f"❌ API returned {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return False
                
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        return False


async def main():
    print("🔍 Vinted Cookie & API Test")
    print("Testing authentication approach...")
    
    # Test cookie factory
    print("\n" + "="*60)
    print("Step 1: Fetch Cookies")
    print("="*60)
    
    factory = SimpleVintedCookieFactory()
    cookies = await factory.get_cookies()
    
    cookie_ok = "access_token_web" in cookies
    
    if cookie_ok:
        print("\n✅ Cookie factory works!")
    else:
        print("\n❌ Cookie factory failed")
    
    # Test API
    api_ok = await test_api_with_cookies()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Cookie Factory: {'✅ PASS' if cookie_ok else '❌ FAIL'}")
    print(f"API Access: {'✅ PASS' if api_ok else '❌ FAIL'}")
    
    if api_ok:
        print("\n🎉 Vinted authentication approach works!")
    elif cookie_ok:
        print("\n⚠️  Cookies work but API blocked - may need additional headers")
    else:
        print("\n🔴 Vinted is blocking cookie fetching - may need proxy")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    asyncio.run(main())

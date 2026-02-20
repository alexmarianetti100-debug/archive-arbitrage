#!/usr/bin/env python3
"""
Quick proxy setup for Archive Arbitrage.

Supported services (in order of recommendation):
1. Webshare.io - $2.99/mo for 10 proxies, good for testing
2. SmartProxy - ~$8/GB, rotating residential
3. Bright Data - ~$10/GB, premium quality
4. Oxylabs - ~$10/GB, enterprise grade

Usage:
    # Set up Webshare (cheapest)
    python setup_proxies.py webshare YOUR_API_KEY
    
    # Set up SmartProxy
    python setup_proxies.py smartproxy USERNAME PASSWORD
    
    # Set up Bright Data
    python setup_proxies.py brightdata USERNAME PASSWORD
    
    # Test current proxy setup
    python setup_proxies.py test
"""

import os
import sys
import asyncio

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.proxy_manager import ProxyManager, configure_proxies


def save_config(service: str, **kwargs):
    """Save proxy config to .env file."""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    
    lines = []
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = [l for l in f.readlines() if not l.startswith('PROXY_')]
    
    lines.append(f"\n# Proxy Configuration ({service})\n")
    lines.append(f"PROXY_SERVICE={service}\n")
    
    for key, value in kwargs.items():
        lines.append(f"PROXY_{key.upper()}={value}\n")
    
    with open(env_path, 'w') as f:
        f.writelines(lines)
    
    print(f"✅ Saved proxy config to .env")


async def test_proxies():
    """Test current proxy configuration."""
    from scrapers.proxy_manager import get_proxy_manager
    import httpx
    
    pm = get_proxy_manager()
    
    if pm.count == 0:
        print("No proxies configured. Run setup first.")
        return
    
    print(f"Testing {pm.count} proxies...")
    
    for i in range(min(3, pm.count)):
        proxy = pm.get_proxy()
        print(f"\nProxy {i+1}: {proxy.host}:{proxy.port}")
        
        try:
            async with httpx.AsyncClient(proxies=proxy.url, timeout=15) as client:
                # Test basic connectivity
                resp = await client.get("https://httpbin.org/ip")
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"  ✅ IP: {data.get('origin', 'unknown')}")
                    
                    # Test eBay
                    resp2 = await client.get("https://www.ebay.com")
                    print(f"  ✅ eBay: {resp2.status_code}")
                else:
                    print(f"  ❌ HTTP {resp.status_code}")
        except Exception as e:
            print(f"  ❌ Error: {e}")


def setup_webshare(api_key: str):
    """Set up Webshare.io proxies."""
    import httpx
    
    print("Fetching Webshare proxy list...")
    
    # Try backbone mode first (residential proxies), then direct (datacenter)
    for mode in ["backbone", "direct"]:
        resp = httpx.get(
            "https://proxy.webshare.io/api/v2/proxy/list/",
            headers={"Authorization": f"Token {api_key}"},
            params={"mode": mode, "page_size": 100},
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("count", 0) > 0:
                print(f"✅ Found {data['count']} proxies (mode: {mode})")
                break
    else:
        print(f"❌ Failed to fetch proxies: {resp.status_code}")
        print(f"   Get your API key from https://proxy.webshare.io/")
        return
    
    results = data.get("results", [])
    if not results:
        print("❌ No proxies found in account")
        return
    
    # For backbone/residential proxies, use the gateway
    proxies = []
    gateway_host = "p.webshare.io"  # Webshare rotating gateway
    
    for proxy in results:
        proxies.append({
            "host": gateway_host,
            "port": str(proxy["port"]),
            "username": proxy["username"],
            "password": proxy["password"],
        })
    
    print(f"✅ Configured {len(proxies)} proxies via {gateway_host}")
    
    # Save config
    if proxies:
        save_config("webshare", 
            host=gateway_host,
            port=proxies[0]["port"],
            username=proxies[0]["username"],
            password=proxies[0]["password"],
            api_key=api_key,
            mode=mode,
            count=str(len(proxies)),
        )
    
    return proxies


def setup_smartproxy(username: str, password: str):
    """Set up SmartProxy rotating proxies."""
    save_config("smartproxy",
        host="gate.smartproxy.com",
        port="7000",
        username=username,
        password=password,
    )
    
    pm = ProxyManager()
    pm.configure_smartproxy(username, password)
    print(f"✅ SmartProxy configured")
    print(f"   Proxy: gate.smartproxy.com:7000")
    return pm


def setup_brightdata(username: str, password: str):
    """Set up Bright Data rotating proxies."""
    save_config("brightdata",
        host="brd.superproxy.io",
        port="22225",
        username=username,
        password=password,
    )
    
    pm = ProxyManager()
    pm.configure_brightdata(username, password)
    print(f"✅ Bright Data configured")
    print(f"   Proxy: brd.superproxy.io:22225")
    return pm


def setup_oxylabs(username: str, password: str):
    """Set up Oxylabs rotating proxies."""
    save_config("oxylabs",
        host="pr.oxylabs.io",
        port="7777",
        username=username,
        password=password,
    )
    
    pm = ProxyManager()
    pm.configure_oxylabs(username, password)
    print(f"✅ Oxylabs configured")
    print(f"   Proxy: pr.oxylabs.io:7777")
    return pm


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n📋 Quick Start:")
        print("   1. Sign up at https://www.webshare.io/ ($2.99/mo)")
        print("   2. Get your API key from dashboard")
        print("   3. Run: python setup_proxies.py webshare YOUR_API_KEY")
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == "test":
        asyncio.run(test_proxies())
    
    elif cmd == "webshare":
        if len(sys.argv) < 3:
            print("Usage: python setup_proxies.py webshare API_KEY")
            print("Get your API key from https://proxy.webshare.io/")
            return
        setup_webshare(sys.argv[2])
    
    elif cmd == "smartproxy":
        if len(sys.argv) < 4:
            print("Usage: python setup_proxies.py smartproxy USERNAME PASSWORD")
            return
        setup_smartproxy(sys.argv[2], sys.argv[3])
    
    elif cmd == "brightdata":
        if len(sys.argv) < 4:
            print("Usage: python setup_proxies.py brightdata USERNAME PASSWORD")
            return
        setup_brightdata(sys.argv[2], sys.argv[3])
    
    elif cmd == "oxylabs":
        if len(sys.argv) < 4:
            print("Usage: python setup_proxies.py oxylabs USERNAME PASSWORD")
            return
        setup_oxylabs(sys.argv[2], sys.argv[3])
    
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()

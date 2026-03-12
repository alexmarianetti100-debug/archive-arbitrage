#!/usr/bin/env python3
"""
Quick test of Japan integration fixes
"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("test_japan")

async def test_japan_integration():
    """Test the Japan integration to verify fixes work."""
    from core.japan_integration import find_japan_arbitrage_deals, JapanArbitrageMonitor

    logger.info("Testing Japan integration...")

    # Test 1: Create monitor
    try:
        monitor = JapanArbitrageMonitor()
        logger.info("✅ JapanArbitrageMonitor created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create monitor: {e}")
        return False

    # Test 2: Check proxy config
    try:
        import json
        with open('data/proxy_config.json') as f:
            config = json.load(f)
        proxies = config.get('proxies', [])
        logger.info(f"✅ Proxy config loaded: {len(proxies)} proxies configured")
        for p in proxies[:2]:
            username = p.get('username', 'N/A')[:10] + '...' if len(p.get('username', '')) > 10 else p.get('username', 'N/A')
            logger.info(f"   - {p['id']}: {p['host']}:{p['port']} (user: {username})")
    except Exception as e:
        logger.error(f"❌ Proxy config issue: {e}")

    # Test 3: Run a limited scan (just 2 targets to test)
    logger.info("\n🗾 Running limited Japan scan (2 targets)...")
    try:
        # Override search targets for quick test
        monitor.SEARCH_TARGETS = monitor.SEARCH_TARGETS[:2]

        opportunities = await monitor.scan_for_opportunities(
            include_mercari=True,
            include_rakuma=False  # Should be disabled on macOS
        )

        logger.info(f"✅ Scan completed. Found {len(opportunities)} opportunities")

        if opportunities:
            for opp in opportunities[:3]:
                logger.info(f"   - {opp.recommendation}: {opp.brand} ({opp.platform}) - ${opp.net_profit:.0f} profit")

        return True

    except Exception as e:
        logger.error(f"❌ Scan failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = asyncio.run(test_japan_integration())
    exit(0 if success else 1)

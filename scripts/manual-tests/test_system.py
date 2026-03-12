#!/usr/bin/env python3
"""
Quick test to verify Japan integration and alerts are working
"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("test_system")

async def test_full_pipeline():
    """Test the full pipeline including Japan integration."""

    print("=" * 60)
    print("Testing Archive Arbitrage System")
    print("=" * 60)

    # Test 1: Imports
    print("\n1. Testing imports...")
    try:
        from core.japan_integration import find_japan_arbitrage_deals, JapanArbitrageMonitor
        from core.discord_alerts import send_discord_alert, DISCORD_ENABLED
        import telegram_bot
        print("   ✅ All imports successful")
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        return False

    # Test 2: Proxy config
    print("\n2. Checking proxy config...")
    try:
        import json
        with open('data/proxy_config.json') as f:
            config = json.load(f)
        print(f"   ✅ {len(config.get('proxies', []))} proxies configured")
        print(f"   ✅ Headful mode: {config.get('headful', True)}")
    except Exception as e:
        print(f"   ❌ Proxy config error: {e}")

    # Test 3: Environment variables
    print("\n3. Checking environment...")
    import os
    from dotenv import load_dotenv
    load_dotenv()

    checks = [
        ('TELEGRAM_BOT_TOKEN', bool(os.getenv('TELEGRAM_BOT_TOKEN'))),
        ('TELEGRAM_CHANNEL_ID', bool(os.getenv('TELEGRAM_CHANNEL_ID'))),
        ('DISCORD_WEBHOOK_BEGINNER', bool(os.getenv('DISCORD_WEBHOOK_BEGINNER'))),
        ('DISCORD_WEBHOOK_PRO', bool(os.getenv('DISCORD_WEBHOOK_PRO'))),
        ('DISCORD_WEBHOOK_BIG_BALLER', bool(os.getenv('DISCORD_WEBHOOK_BIG_BALLER'))),
    ]

    for name, present in checks:
        status = "✅" if present else "❌"
        print(f"   {status} {name}")

    # Test 4: Japan scan (limited)
    print("\n4. Testing Japan integration (2 targets)...")
    try:
        monitor = JapanArbitrageMonitor()
        # Limit to 2 targets for quick test
        monitor.SEARCH_TARGETS = [t for t in monitor.SEARCH_TARGETS if 'rolex' in t['en'].lower() or 'cartier' in t['en'].lower()][:2]

        opportunities = await monitor.scan_for_opportunities(
            include_mercari=False,  # Skip for quick test
            include_rakuma=False
        )

        print(f"   ✅ Found {len(opportunities)} opportunities")

        if opportunities:
            for opp in opportunities[:2]:
                print(f"   📊 {opp.recommendation}: {opp.brand} - ${opp.net_profit:.0f} profit ({opp.margin_percent:.1f}%)")

    except Exception as e:
        print(f"   ❌ Japan scan failed: {e}")
        import traceback
        print(traceback.format_exc())

    print("\n" + "=" * 60)
    print("Test complete")
    print("=" * 60)

    return True

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())

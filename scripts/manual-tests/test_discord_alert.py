#!/usr/bin/env python3
"""
Test Discord alerts to verify they're working
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_discord_alert():
    """Send a test Discord alert to verify configuration."""
    from core.discord_alerts import send_discord_alert, DISCORD_ENABLED

    print(f"Discord enabled: {DISCORD_ENABLED}")
    print(f"Beginner webhook: {os.getenv('DISCORD_WEBHOOK_BEGINNER', 'NOT SET')[:50]}...")
    print(f"Pro webhook: {os.getenv('DISCORD_WEBHOOK_PRO', 'NOT SET')[:50]}...")
    print(f"Big Baller webhook: {os.getenv('DISCORD_WEBHOOK_BIG_BALLER', 'NOT SET')[:50]}...")

    # Create a mock item
    class MockItem:
        def __init__(self):
            self.title = "Test Alert - Rolex Submariner"
            self.price = 8500
            self.source = "japan_buyee"
            self.url = "https://buyee.jp/item/test"
            self.images = ["https://via.placeholder.com/400x300"]
            self.brand = "Rolex"

    # Create mock signals
    class MockSignals:
        def __init__(self):
            self.quality_score = 75
            self.fire_level = 3
            self.gap_percent = 0.35
            self.profit_estimate = 2500
            self.line_name = "Japan Import"
            self.season_name = "Watch"
            self.condition_tier = "NEW"

    item = MockItem()
    signals = MockSignals()

    message = """🗾 JAPAN ARBITRAGE TEST

<b>Rolex Submariner</b>
Test alert to verify Discord integration

💵 <b>Japan Price:</b> ¥1,200,000 ($8,000)
📦 <b>Landed Cost:</b> $8,500
📊 <b>US Market:</b> $11,000
💰 <b>Net Profit:</b> $2,500
📈 <b>Margin:</b> 29.4%

🚢 <b>Proxy:</b> Buyee
📮 <b>Shipping:</b> EMS
⏰ <b>Ends:</b> 2026-03-11 20:00
🔥 <b>Bids:</b> 5

<a href='https://buyee.jp'>🔗 Bid on Buyee</a>"""

    print("\nSending test alert to Discord...")

    try:
        success = await send_discord_alert(
            item=item,
            message=message,
            fire_level=3,
            signals=signals,
            auth_result=None,
            tier="pro",  # Test with pro tier
        )

        if success:
            print("✅ Discord alert sent successfully!")
        else:
            print("❌ Discord alert failed to send")

    except Exception as e:
        print(f"❌ Error sending Discord alert: {e}")
        import traceback
        print(traceback.format_exc())

    # Debug: Print the actual webhook URLs being used
    from core.discord_alerts import DISCORD_WEBHOOK_BEGINNER, DISCORD_WEBHOOK_PRO, DISCORD_WEBHOOK_BIG_BALLER
    print(f"\nDebug - Webhooks from module:")
    print(f"  Beginner: {DISCORD_WEBHOOK_BEGINNER[:60] if DISCORD_WEBHOOK_BEGINNER else 'None'}...")
    print(f"  Pro: {DISCORD_WEBHOOK_PRO[:60] if DISCORD_WEBHOOK_PRO else 'None'}...")
    print(f"  Big Baller: {DISCORD_WEBHOOK_BIG_BALLER[:60] if DISCORD_WEBHOOK_BIG_BALLER else 'None'}...")

if __name__ == "__main__":
    asyncio.run(test_discord_alert())

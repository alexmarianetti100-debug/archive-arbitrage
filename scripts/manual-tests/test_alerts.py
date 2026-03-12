#!/usr/bin/env python3
"""Test Japan deal alert sending"""
import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("test_alert")

async def test_alerts():
    """Test that Japan deal alerts are sent properly."""
    
    print("="*60)
    print("Testing Japan Deal Alert Sending")
    print("="*60)
    
    # Check environment
    print("\n1. Checking environment...")
    print(f"   TELEGRAM_BOT_TOKEN: {'✅ Set' if os.getenv('TELEGRAM_BOT_TOKEN') else '❌ Not set'}")
    print(f"   TELEGRAM_CHANNEL_ID: {'✅ Set' if os.getenv('TELEGRAM_CHANNEL_ID') else '❌ Not set'}")
    print(f"   DISCORD_WEBHOOK_BEGINNER: {'✅ Set' if os.getenv('DISCORD_WEBHOOK_BEGINNER') else '❌ Not set'}")
    
    # Test Telegram
    print("\n2. Testing Telegram...")
    try:
        import telegram_bot
        print(f"   BOT_TOKEN: {'✅' if telegram_bot.BOT_TOKEN else '❌'}")
        print(f"   CHANNEL_ID: {telegram_bot.TELEGRAM_CHANNEL_ID}")
        
        if telegram_bot.BOT_TOKEN and telegram_bot.TELEGRAM_CHANNEL_ID:
            test_message = """🗾 JAPAN ARBITRAGE TEST

<b>Rolex Submariner</b>
Test alert to verify Telegram integration

💵 <b>Japan Price:</b> ¥1,200,000 ($8,000)
📦 <b>Landed Cost:</b> $8,500
📊 <b>US Market:</b> $11,000
💰 <b>Net Profit:</b> $2,500
📈 <b>Margin:</b> 29.4%

🚢 <b>Proxy:</b> Buyee
📮 <b>Shipping:</b> EMS

<a href='https://buyee.jp'>🔗 Bid on Buyee</a>"""
            
            await telegram_bot.send_message(
                chat_id=int(telegram_bot.TELEGRAM_CHANNEL_ID),
                text=test_message,
                parse_mode="HTML",
                disable_preview=False
            )
            print("   ✅ Telegram test message sent!")
        else:
            print("   ❌ Telegram not configured")
    except Exception as e:
        print(f"   ❌ Telegram error: {e}")
        import traceback
        print(traceback.format_exc())
    
    # Test Discord
    print("\n3. Testing Discord...")
    try:
        from core.discord_alerts import DISCORD_ENABLED, send_discord_alert
        print(f"   DISCORD_ENABLED: {DISCORD_ENABLED}")
        
        if DISCORD_ENABLED:
            # Create mock item
            class MockItem:
                def __init__(self):
                    self.title = "Test Rolex"
                    self.price = 8500
                    self.source = "japan_buyee"
                    self.url = "https://buyee.jp/item/test"
                    self.images = ["https://via.placeholder.com/400x300"]
                    self.brand = "Rolex"
            
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
            
            message = "Test Japan arbitrage alert"
            
            success = await send_discord_alert(
                item=item,
                message=message,
                fire_level=3,
                signals=signals,
                auth_result=None,
                tier="pro",
            )
            
            if success:
                print("   ✅ Discord test message sent!")
            else:
                print("   ❌ Discord failed to send")
        else:
            print("   ❌ Discord not enabled")
    except Exception as e:
        print(f"   ❌ Discord error: {e}")
        import traceback
        print(traceback.format_exc())
    
    print("\n" + "="*60)
    print("Test complete")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_alerts())

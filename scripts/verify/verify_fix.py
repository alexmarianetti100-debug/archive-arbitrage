#!/usr/bin/env python3
"""Verify Japan deal alert fix"""
import asyncio
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MockJapanData:
    recommendation: str
    brand: str
    title: str
    title_jp: str
    item_price_jpy: int
    item_price_usd: float
    total_landed_cost: float
    us_market_price: float
    net_profit: float
    margin_percent: float
    proxy_service: str
    shipping_method: str
    auction_url: str
    image_url: str
    category: str
    bids: int
    end_time: datetime

async def verify_fix():
    """Verify the DealSignals fix works for Discord alerts."""
    
    print("="*60)
    print("Verifying Japan Deal Alert Fix")
    print("="*60)
    
    # Create mock Japan deal
    japan_data = MockJapanData(
        recommendation='STRONG_BUY',
        brand='Cartier',
        title='Tank Watch',
        title_jp='カルティエ タンク',
        item_price_jpy=150000,
        item_price_usd=1000.0,
        total_landed_cost=1200.0,
        us_market_price=5000.0,
        net_profit=3500.0,
        margin_percent=291.7,
        proxy_service='Buyee',
        shipping_method='EMS',
        auction_url='https://buyee.jp/item/test',
        image_url='https://example.com/image.jpg',
        category='watch',
        bids=5,
        end_time=datetime.now()
    )
    
    class MockItem:
        def __init__(self, japan_deal):
            self.title = f"{japan_deal.brand} {japan_deal.title}"
            self.price = japan_deal.total_landed_cost
            self.source = 'japan_buyee'
            self.url = japan_deal.auction_url
            self.images = [japan_deal.image_url] if japan_deal.image_url else []
            self._japan_data = japan_deal
    
    item = MockItem(japan_data)
    
    # Test creating DealSignals (this was failing before)
    print("\n1. Testing DealSignals creation...")
    try:
        from core.deal_quality import DealSignals
        signals = DealSignals(
            fire_level=3 if japan_data.recommendation == 'STRONG_BUY' else 2,
            gap_percent=japan_data.margin_percent / 100,
            profit_estimate=japan_data.net_profit,
            line_name='Japan Import',
            season_name=japan_data.category,
            condition_tier='NEW',
            detected_size='',
            liquidity_score=8,
        )
        print("   ✅ DealSignals created successfully")
    except Exception as e:
        print(f"   ❌ DealSignals failed: {e}")
        return False
    
    # Test Discord alert
    print("\n2. Testing Discord alert...")
    try:
        from core.discord_alerts import send_discord_alert, determine_tier
        
        tier = determine_tier(item, japan_data.net_profit, japan_data.margin_percent / 100)
        print(f"   Tier: {tier}")
        
        message = f"🗾 JAPAN ARBITRAGE\n\n{japan_data.title_jp}\n{japan_data.title}"
        
        success = await send_discord_alert(
            item=item,
            message=message,
            fire_level=signals.fire_level,
            signals=signals,
            auth_result=None,
            tier=tier,
        )
        
        if success:
            print("   ✅ Discord alert sent successfully")
        else:
            print("   ❌ Discord alert failed")
            return False
    except Exception as e:
        print(f"   ❌ Discord error: {e}")
        import traceback
        print(traceback.format_exc())
        return False
    
    print("\n" + "="*60)
    print("✅ Fix verified - Japan deals will send Discord alerts!")
    print("="*60)
    return True

if __name__ == "__main__":
    success = asyncio.run(verify_fix())
    exit(0 if success else 1)

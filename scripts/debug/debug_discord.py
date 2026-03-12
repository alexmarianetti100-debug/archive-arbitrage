#!/usr/bin/env python3
"""Debug Japan deal Discord alert flow"""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("debug_japan")

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

async def debug_discord_flow():
    """Debug the exact flow of a Japan deal to Discord."""
    
    print("="*60)
    print("Debugging Japan Deal Discord Alert Flow")
    print("="*60)
    
    # Create a realistic Japan deal (similar to what we're seeing in logs)
    japan_data = MockJapanData(
        recommendation='STRONG_BUY',
        brand='Cartier',
        title='Tank Watch',
        title_jp='カルティエ タンク',
        item_price_jpy=150000,
        item_price_usd=1000.0,
        total_landed_cost=1200.0,  # This is what item.price will be
        us_market_price=5000.0,
        net_profit=3500.0,  # High profit
        margin_percent=291.7,  # High margin
        proxy_service='Buyee',
        shipping_method='EMS',
        auction_url='https://buyee.jp/item/test',
        image_url='https://example.com/image.jpg',
        category='watch',
        bids=5,
        end_time=datetime.now()
    )
    
    # Create mock item (exactly as gap_hunter does)
    class MockItem:
        def __init__(self, japan_deal):
            self.title = f"{japan_deal.brand} {japan_deal.title}"
            self.price = japan_deal.total_landed_cost  # $1200
            self.source = 'japan_buyee'
            self.url = japan_deal.auction_url
            self.images = [japan_deal.image_url] if japan_deal.image_url else []
            self._japan_data = japan_deal
    
    item = MockItem(japan_data)
    
    print(f"\n1. MockItem created:")
    print(f"   Title: {item.title}")
    print(f"   Price (landed cost): ${item.price}")
    print(f"   Net Profit: ${japan_data.net_profit}")
    print(f"   Margin: {japan_data.margin_percent}%")
    
    # Test determine_tier
    print(f"\n2. Testing determine_tier:")
    from core.discord_alerts import determine_tier
    
    tier = determine_tier(item, japan_data.net_profit, japan_data.margin_percent / 100)
    print(f"   Tier determined: {tier}")
    
    # Check tier criteria manually
    print(f"\n3. Tier criteria check:")
    print(f"   Profit ${japan_data.net_profit} >= $500 (Big Baller): {japan_data.net_profit >= 500}")
    print(f"   Margin {japan_data.margin_percent/100:.2f} >= 0.20: {japan_data.margin_percent/100 >= 0.20}")
    print(f"   Price ${item.price} >= $5000: {item.price >= 5000}")
    print(f"   -> Big Baller: {japan_data.net_profit >= 500 and japan_data.margin_percent/100 >= 0.20 and item.price >= 5000}")
    
    print(f"   Profit ${japan_data.net_profit} >= $300 (Pro): {japan_data.net_profit >= 300}")
    print(f"   Margin {japan_data.margin_percent/100:.2f} >= 0.25: {japan_data.margin_percent/100 >= 0.25}")
    print(f"   Price ${item.price} >= $1000: {item.price >= 1000}")
    print(f"   Price ${item.price} < $10000: {item.price < 10000}")
    print(f"   -> Pro: {japan_data.net_profit >= 300 and japan_data.margin_percent/100 >= 0.25 and item.price >= 1000 and item.price < 10000}")
    
    print(f"   Profit ${japan_data.net_profit} >= $150 (Beginner): {japan_data.net_profit >= 150}")
    print(f"   Margin {japan_data.margin_percent/100:.2f} >= 0.30: {japan_data.margin_percent/100 >= 0.30}")
    print(f"   -> Beginner: {japan_data.net_profit >= 150 and japan_data.margin_percent/100 >= 0.30}")
    
    # Test actual Discord send
    print(f"\n4. Testing Discord send:")
    from core.discord_alerts import send_discord_alert, DISCORD_ENABLED
    from core.deal_quality import DealSignals
    
    print(f"   DISCORD_ENABLED: {DISCORD_ENABLED}")
    
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
    
    message = f"🗾 JAPAN ARBITRAGE TEST\n\n{japan_data.title_jp}\n{japan_data.title}"
    
    if DISCORD_ENABLED:
        success = await send_discord_alert(
            item=item,
            message=message,
            fire_level=signals.fire_level,
            signals=signals,
            auth_result=None,
            tier=tier,
        )
        print(f"   Discord send result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    else:
        print(f"   ❌ Discord not enabled")
    
    print("\n" + "="*60)
    print("Debug complete")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(debug_discord_flow())

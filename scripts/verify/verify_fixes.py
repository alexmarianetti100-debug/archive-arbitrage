#!/usr/bin/env python3
"""Verification test for Japan arbitrage fixes"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')

async def verify():
    from core.japan_integration import find_japan_arbitrage_deals
    
    print('='*60)
    print('VERIFICATION TEST - Japan Arbitrage')
    print('='*60)
    
    deals = await find_japan_arbitrage_deals(min_margin=25.0, min_profit=200.0, include_mercari=True)
    
    print(f'\n✅ Found {len(deals)} total opportunities')
    
    if deals:
        for d in deals[:3]:
            print(f'\n{d.recommendation}: {d.brand}')
            print(f'  Japan: ¥{d.item_price_jpy:,} → US: ${d.us_market_price:,.0f}')
            print(f'  Profit: ${d.net_profit:,.0f} ({d.margin_percent:.1f}% margin)')
            print(f'  Platform: {d.platform}')
    else:
        print('\n⚠️ No deals met thresholds (this is normal if no profitable items found)')
    
    print('\n' + '='*60)
    print('VERIFICATION COMPLETE')
    print('='*60)

if __name__ == "__main__":
    asyncio.run(verify())

#!/usr/bin/env python3
"""
Quick test to verify Whop integration without running full pipeline
"""
import os
import sys
import asyncio
from pathlib import Path

# Add the project directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.whop_alerts import send_whop_alert, format_whop_deal_content
from collections import namedtuple

async def test_whop_integration():
    print("Testing Whop integration directly...")
    
    # Mock item data
    Item = namedtuple('Item', ['title', 'brand', 'price', 'url'])
    item = Item(title="Test Rick Owens Geobasket", brand="Rick Owens", price=250.0, url="https://grailed.com/test")
    
    # Mock price record
    PriceRec = namedtuple('PriceRec', ['recommended_price', 'confidence', 'comps_count', 'demand_level', 'margin_percent', 'profit_estimate', 'deal_grade'])
    price_rec = PriceRec(
        recommended_price=450.0, 
        confidence='high', 
        comps_count=12, 
        demand_level='hot',
        margin_percent=0.44,
        profit_estimate=200.0,
        deal_grade='A'
    )
    
    # Format content
    title, content = format_whop_deal_content(item, price_rec, margin=0.44, profit=200.0)
    print(f"Title: {title}")
    print(f"Content preview: {content[:100]}...")
    
    # Send
    print("\nSending to Whop...")
    success = await send_whop_alert(title, content)
    
    if success:
        print("✅ Whop alert sent successfully!")
    else:
        print("❌ Failed to send Whop alert.")

if __name__ == "__main__":
    asyncio.run(test_whop_integration())
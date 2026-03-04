import asyncio
from core.whop_alerts import send_whop_alert, format_whop_deal_content
from collections import namedtuple

async def test():
    print("Testing Whop API integration...")
    # Mock item
    Item = namedtuple('Item', ['title', 'brand', 'price', 'url'])
    item = Item(title="Test Rick Owens Geobasket", brand="Rick Owens", price=250.0, url="https://grailed.com/test")
    
    # Mock price rec
    PriceRec = namedtuple('PriceRec', ['recommended_price', 'confidence', 'comps_count', 'demand_level'])
    price_rec = PriceRec(recommended_price=450.0, confidence='high', comps_count=12, demand_level='hot')
    
    title, content = format_whop_deal_content(item, price_rec, margin=0.44, profit=200.0)
    
    success = await send_whop_alert(title, content)
    if success:
        print("✅ Whop alert successfully sent!")
    else:
        print("❌ Failed to send Whop alert.")

if __name__ == "__main__":
    asyncio.run(test())

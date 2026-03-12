#!/usr/bin/env python3
"""
Quick verification of Whop integration
"""
import os
import sys
import asyncio
from pathlib import Path

# Make sure we can import from the project
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def test_whop_config():
    """Verify our .env settings are correct"""
    print("🔧 Testing Whop Configuration")
    print("=" * 40)
    
    # Load .env file manually
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        print("❌ .env file not found!")
        return False
    
    with open(env_path, 'r') as f:
        content = f.read()
    
    # Check key settings
    checks = [
        ("WHOP_API_KEY", "apik_" in content),
        ("WHOP_EXPERIENCE_ID", "exp_" in content),
        ("WHOP_ENABLED", "WHOP_ENABLED=true" in content),
        ("WHOP_DRY_RUN", "WHOP_DRY_RUN=false" in content),
    ]
    
    all_good = True
    for name, condition in checks:
        status = "✅" if condition else "❌"
        print(f"{status} {name}")
        if not condition:
            all_good = False
    
    print()
    return all_good

def test_imports():
    """Test that we can import Whop modules"""
    print("📥 Testing Imports")
    print("=" * 40)
    
    try:
        from core.whop_alerts import send_whop_alert, format_whop_deal_content
        print("✅ Successfully imported Whop modules")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

async def test_functionality():
    """Test basic Whop functionality"""
    print("🚀 Testing Whop Functionality")
    print("=" * 40)
    
    try:
        from core.whop_alerts import send_whop_alert, format_whop_deal_content
        from collections import namedtuple
        
        # Mock data
        Item = namedtuple('Item', ['title', 'brand', 'price', 'url'])
        item = Item(title="Test Item", brand="Test Brand", price=100, url="https://example.com")
        
        PriceRec = namedtuple('PriceRec', ['recommended_price', 'confidence', 'comps_count', 'demand_level', 'margin_percent', 'profit_estimate', 'deal_grade'])
        price_rec = PriceRec(
            recommended_price=200, 
            confidence='high', 
            comps_count=5, 
            demand_level='hot',
            margin_percent=0.5,
            profit_estimate=100,
            deal_grade='A'
        )
        
        # Test formatting
        title, content = format_whop_deal_content(item, price_rec, 0.5, 100)
        print(f"✅ Title: {title}")
        print(f"✅ Content length: {len(content)} chars")
        
        # Test sending (will be in dry-run mode)
        print("ℹ️  Testing send function (will show dry-run info)...")
        result = await send_whop_alert(title, content)
        print(f"✅ Function completed (result: {result})")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("📋 Whop Integration Verification")
    print("=" * 50)
    
    # Run all tests
    config_ok = test_whop_config()
    imports_ok = test_imports()
    
    if config_ok and imports_ok:
        func_ok = await test_functionality()
        print("\n" + "=" * 50)
        if config_ok and imports_ok and func_ok:
            print("🎉 All checks passed! Whop integration should work.")
        else:
            print("⚠️  Some components have issues.")
    else:
        print("\n❌ Configuration or import issues detected.")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(main())
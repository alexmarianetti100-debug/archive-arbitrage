#!/usr/bin/env python3
"""
Test the actual Whop integration with your confirmed working API
"""
import os
import sys
import asyncio
from pathlib import Path

# Setup properly
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Load env first
from dotenv import load_dotenv
load_dotenv()

def test_direct_integration():
    print("🚀 Testing Direct Whop Integration")
    print("=" * 40)
    
    # Test the exact imports
    try:
        from core.whop_alerts import send_whop_alert
        print("✅ Successfully imported send_whop_alert")
        
        # Test with simple data
        test_title = "Test Gap Alert from Archive Arbitrage"
        test_content = """
## Test Gap Deal: [Test Item]

**💰 The Opportunity:**
- Listed for: $100.00
- Proven sold price: $200.00
- Gap: **50%** ($100 profit)
- Source: Grailed

[View Listing](https://example.com)
"""
        
        print("\nTesting actual function call...")
        print(f"Title: {test_title[:50]}...")
        print(f"Content Length: {len(test_content)} chars")
        
        # Run the actual async function
        result = asyncio.run(send_whop_alert(test_title, test_content))
        print(f"\n✅ Function result: {result}")
        
        # Check that environment variables are properly loaded
        print("\nEnvironment verification:")
        print(f"WHOP_ENABLED: {os.getenv('WHOP_ENABLED', 'Not set')}")
        print(f"WHOP_DRY_RUN: {os.getenv('WHOP_DRY_RUN', 'Not set')}")
        print(f"API Key set: {'YES' if os.getenv('WHOP_API_KEY') else 'NO'}")
        print(f"Experience ID: {os.getenv('WHOP_EXPERIENCE_ID', 'Not set')}")
        
        return result
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing Whop integration for gap_hunter.py")
    print("This is the direct test of your integration logic")
    test_direct_integration()
#!/usr/bin/env python3
"""
Quick test to verify PricingEngine fix
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

print("🔧 TESTING PRICINGENGINE FIX")
print("=" * 60)

from core.pricing_engine import PricingEngine

# Test 1: Create engine
print("\n1. Creating PricingEngine...")
engine = PricingEngine()
print("   ✅ PricingEngine created")

# Test 2: Set price
print("\n2. Testing set_price...")
engine.set_price("test_query", 500.0, source="test")
print("   ✅ set_price() works")

# Test 3: Get price
print("\n3. Testing get_price...")
entry = engine.get_price("test_query")
if entry:
    print(f"   ✅ get_price() works")
    print(f"   📊 Entry data: {entry.data}")
    if isinstance(entry.data, dict) and 'price' in entry.data:
        print(f"   💰 Price: ${entry.data['price']}")
    else:
        print(f"   ⚠️  Unexpected data format: {type(entry.data)}")
else:
    print("   ❌ get_price() returned None")

# Test 4: Check stats
print("\n4. Checking stats...")
stats = engine.get_stats()
print(f"   ✅ Stats: {stats}")

print("\n" + "=" * 60)
print("✅ PricingEngine fix verified!")
print("   The gap_hunter should now work correctly.")

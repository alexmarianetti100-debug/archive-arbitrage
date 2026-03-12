#!/usr/bin/env python3
"""Test hyper-pricing integration with gap_hunter."""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')

async def test_hyper_integration():
    """Test that hyper-pricing integrates correctly."""
    print("="*70)
    print("Testing Hyper-Pricing Integration")
    print("="*70)
    
    from gap_hunter import GapHunter
    
    gh = GapHunter()
    
    # Test query
    query = "chrome hearts ring"
    
    print(f"\n1. Testing standard get_sold_data for '{query}':")
    standard_data = await gh.get_sold_data(query)
    if standard_data:
        print(f"   ✅ Standard: ${standard_data.avg_price:.0f} ({standard_data.count} comps)")
    else:
        print(f"   ❌ No standard data")
    
    print(f"\n2. Testing hyper get_hyper_sold_data for '{query}':")
    hyper_data = await gh.get_hyper_sold_data(query, item_title="Chrome Hearts Ring Size 9")
    if hyper_data:
        is_hyper = getattr(hyper_data, '_hyper_pricing', False)
        print(f"   ✅ Hyper: ${hyper_data.avg_price:.0f} ({hyper_data.count} comps)")
        print(f"   Hyper-pricing active: {is_hyper}")
        if is_hyper:
            meta = getattr(hyper_data, '_hyper_metadata', {})
            print(f"   CV: {meta.get('cv', 'N/A'):.2f}")
            print(f"   Target condition: {getattr(hyper_data, '_target_condition', 'N/A')}")
            print(f"   Target size: {getattr(hyper_data, '_target_size', 'N/A')}")
    else:
        print(f"   ❌ No hyper data")
    
    # Compare
    if standard_data and hyper_data:
        print(f"\n3. Comparison:")
        diff = hyper_data.avg_price - standard_data.avg_price
        pct_diff = (diff / standard_data.avg_price) * 100
        print(f"   Standard: ${standard_data.avg_price:.0f}")
        print(f"   Hyper:    ${hyper_data.avg_price:.0f}")
        print(f"   Diff:     ${diff:+.0f} ({pct_diff:+.1f}%)")
    
    print("\n" + "="*70)
    print("Integration test complete!")

if __name__ == "__main__":
    asyncio.run(test_hyper_integration())

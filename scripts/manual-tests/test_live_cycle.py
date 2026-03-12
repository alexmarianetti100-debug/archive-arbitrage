#!/usr/bin/env python3
"""
Live test: Run one cycle of gap_hunter to verify deals are flowing.
"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')

async def test_cycle():
    """Run one cycle and report results."""
    print("="*80)
    print("LIVE CYCLE TEST - Verifying American & Japanese Deals")
    print("="*80)
    print()
    
    from gap_hunter import GapHunter
    
    gh = GapHunter()
    
    # Run one cycle with limited targets
    print("Running one cycle (max 5 targets)...")
    print()
    
    await gh.run_cycle(max_targets=5, use_blue_chip=True)
    
    print()
    print("="*80)
    print("CYCLE COMPLETE")
    print("="*80)
    print()
    print(f"Stats:")
    print(f"  Cycles run: {gh.cycle_count}")
    print(f"  Deals sent: {gh.stats.get('deals_sent', 0)}")
    print(f"  Auth blocked: {gh.stats.get('auth_blocked', 0)}")
    print(f"  Quality filtered: {gh.stats.get('quality_filtered', 0)}")
    print()
    
    # Check Japan deals
    japan_deals = gh.stats.get('japan_deals_sent', 0)
    print(f"  Japan deals sent: {japan_deals}")
    
    if gh.stats.get('deals_sent', 0) > 0:
        print()
        print("✅ SUCCESS: Deals are being sent!")
    else:
        print()
        print("⚠️  No deals sent this cycle (may be normal if no gaps found)")

if __name__ == "__main__":
    asyncio.run(test_cycle())

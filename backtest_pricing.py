#!/usr/bin/env python3
"""
Backtest: Compare standard pricing vs hyper-pricing on real queries.

This runs both pricing methods on the same set of queries and compares:
- Number of comps found
- Price estimates
- Gap detection rates
- Deal quality
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("backtest")

# Test queries covering different categories
TEST_QUERIES = [
    # Sneakers
    ("jordan 1 high", "sneakers"),
    ("dunk low", "sneakers"),
    ("yeezy 350", "sneakers"),
    
    # Streetwear
    ("supreme box logo", "streetwear"),
    ("bape shark hoodie", "streetwear"),
    
    # Luxury/Designer
    ("chrome hearts ring", "luxury"),
    ("rick owens ramones", "luxury"),
    ("maison margiela tabi", "luxury"),
    
    # Watches
    ("rolex submariner", "watches"),
    ("cartier tank", "watches"),
    
    # Vintage/Archive
    ("raf simons archive", "vintage"),
    ("helmut lang vintage", "vintage"),
]


async def run_backtest():
    """Run backtest comparing pricing methods."""
    print("="*80)
    print("HYPER-PRICING BACKTEST")
    print("="*80)
    print(f"Testing {len(TEST_QUERIES)} queries across multiple categories")
    print()
    
    from gap_hunter import GapHunter
    
    gh = GapHunter()
    results = []
    
    for i, (query, category) in enumerate(TEST_QUERIES, 1):
        print(f"\n[{i}/{len(TEST_QUERIES)}] Testing: '{query}' ({category})")
        print("-"*80)
        
        result = {
            "query": query,
            "category": category,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Test 1: Standard pricing
        print("  Standard pricing...")
        try:
            standard_data = await gh.get_sold_data(query)
            if standard_data:
                result["standard"] = {
                    "price": standard_data.avg_price,
                    "comps": standard_data.count,
                    "success": True,
                }
                print(f"    ✅ ${standard_data.avg_price:.0f} ({standard_data.count} comps)")
            else:
                result["standard"] = {"success": False, "error": "No data"}
                print(f"    ❌ No data")
        except Exception as e:
            result["standard"] = {"success": False, "error": str(e)}
            print(f"    ❌ Error: {e}")
        
        # Test 2: Hyper pricing
        print("  Hyper pricing...")
        try:
            # Use a sample item title for condition/size parsing
            sample_title = f"{query.title()} Item"
            hyper_data = await gh.get_hyper_sold_data(query, item_title=sample_title, item_category=category)
            if hyper_data:
                is_hyper = getattr(hyper_data, '_hyper_pricing', False)
                meta = getattr(hyper_data, '_hyper_metadata', {})
                result["hyper"] = {
                    "price": hyper_data.avg_price,
                    "comps": hyper_data.count,
                    "success": True,
                    "is_hyper": is_hyper,
                    "cv": meta.get('cv', 0),
                    "target_condition": getattr(hyper_data, '_target_condition', None),
                    "target_size": getattr(hyper_data, '_target_size', None),
                }
                hyper_type = "💎" if is_hyper else "std"
                print(f"    ✅ {hyper_type} ${hyper_data.avg_price:.0f} ({hyper_data.count} comps, CV={meta.get('cv', 0):.2f})")
            else:
                result["hyper"] = {"success": False, "error": "No data"}
                print(f"    ❌ No data")
        except Exception as e:
            result["hyper"] = {"success": False, "error": str(e)}
            print(f"    ❌ Error: {e}")
        
        # Calculate comparison
        if result.get("standard", {}).get("success") and result.get("hyper", {}).get("success"):
            std_price = result["standard"]["price"]
            hyper_price = result["hyper"]["price"]
            diff = hyper_price - std_price
            pct_diff = (diff / std_price) * 100 if std_price > 0 else 0
            result["comparison"] = {
                "price_diff": diff,
                "price_diff_pct": pct_diff,
            }
            print(f"    Diff: ${diff:+.0f} ({pct_diff:+.1f}%)")
        
        results.append(result)
        
        # Small delay to be nice to APIs
        await asyncio.sleep(0.5)
    
    # Summary
    print("\n" + "="*80)
    print("BACKTEST SUMMARY")
    print("="*80)
    
    successful_standard = sum(1 for r in results if r.get("standard", {}).get("success"))
    successful_hyper = sum(1 for r in results if r.get("hyper", {}).get("success"))
    hyper_active = sum(1 for r in results if r.get("hyper", {}).get("is_hyper", False))
    
    print(f"\nSuccess Rates:")
    print(f"  Standard pricing: {successful_standard}/{len(results)} ({successful_standard/len(results)*100:.0f}%)")
    print(f"  Hyper pricing:    {successful_hyper}/{len(results)} ({successful_hyper/len(results)*100:.0f}%)")
    print(f"  Hyper active:     {hyper_active}/{len(results)} ({hyper_active/len(results)*100:.0f}%)")
    
    # Price comparison for successful pairs
    comparisons = [r for r in results if "comparison" in r]
    if comparisons:
        diffs = [r["comparison"]["price_diff_pct"] for r in comparisons]
        avg_diff = sum(diffs) / len(diffs)
        max_diff = max(diffs, key=abs)
        
        print(f"\nPrice Differences (where both succeeded):")
        print(f"  Average difference: {avg_diff:+.1f}%")
        print(f"  Largest difference: {max_diff:+.1f}%")
        print(f"  Hyper higher: {sum(1 for d in diffs if d > 0)}/{len(diffs)}")
        print(f"  Hyper lower:  {sum(1 for d in diffs if d < 0)}/{len(diffs)}")
    
    # Comp count comparison
    std_comps = [r["standard"]["comps"] for r in results if r.get("standard", {}).get("success")]
    hyper_comps = [r["hyper"]["comps"] for r in results if r.get("hyper", {}).get("success")]
    
    if std_comps and hyper_comps:
        avg_std_comps = sum(std_comps) / len(std_comps)
        avg_hyper_comps = sum(hyper_comps) / len(hyper_comps)
        
        print(f"\nComp Count:")
        print(f"  Standard average: {avg_std_comps:.1f} comps")
        print(f"  Hyper average:    {avg_hyper_comps:.1f} comps")
        print(f"  Improvement:      {((avg_hyper_comps/avg_std_comps-1)*100):+.0f}%")
    
    # Category breakdown
    print(f"\nCategory Breakdown:")
    categories = set(r["category"] for r in results)
    for cat in sorted(categories):
        cat_results = [r for r in results if r["category"] == cat]
        cat_success = sum(1 for r in cat_results if r.get("hyper", {}).get("success"))
        print(f"  {cat}: {cat_success}/{len(cat_results)} successful")
    
    # Save results
    output_file = f"data/backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: {output_file}")
    
    print("\n" + "="*80)
    return results


if __name__ == "__main__":
    results = asyncio.run(run_backtest())

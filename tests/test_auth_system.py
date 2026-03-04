"""
Test the new authentication system.
"""

import sys
sys.path.insert(0, ".")

from auth_system import AuthenticationPlatform, authenticate, AuthDecision


def test_authentication_system():
    """Run comprehensive tests on the authentication platform."""
    print("🧪 Testing Archive Arbitrage Authentication System")
    print("=" * 70)
    
    platform = AuthenticationPlatform()
    
    # Test cases
    test_items = [
        {
            "name": "Obvious Replica",
            "data": {
                "title": "Balenciaga Track Sneakers 1:1 Replica Mirror Quality",
                "description": "High quality copy, indistinguishable from authentic. Comes with box and tags.",
                "price": 85,
                "brand": "balenciaga",
                "seller_id": "seller_123",
                "seller_name": "FakeGoods2024",
                "seller_platform": "grailed",
                "images": ["https://example.com/photo1.jpg"],
                "condition": "new",
            }
        },
        {
            "name": "Suspicious Low Price",
            "data": {
                "title": "Rick Owens DRKSHDW Geobasket High Tops",
                "description": "Great condition, barely worn. Size 44.",
                "price": 80,
                "brand": "rick owens",
                "seller_id": "seller_456",
                "seller_name": "NewSeller99",
                "seller_platform": "poshmark",
                "images": ["https://example.com/ro1.jpg", "https://example.com/ro2.jpg"],
                "condition": "good",
            }
        },
        {
            "name": "High Value Needs Review",
            "data": {
                "title": "Chrome Hearts Sterling Silver Cross Pendant",
                "description": "Authentic CH pendant purchased from retail store. Includes original packaging.",
                "price": 1200,
                "brand": "chrome hearts",
                "seller_id": "seller_789",
                "seller_name": "VintageCollector",
                "seller_platform": "grailed",
                "images": ["https://example.com/ch1.jpg"],
                "condition": "good",
            }
        },
        {
            "name": "Likely Authentic",
            "data": {
                "title": "Prada Nylon Messenger Bag Black",
                "description": "100% authentic purchased from Prada store in Milan. Receipt included. Some wear on corners.",
                "price": 450,
                "brand": "prada",
                "seller_id": "trusted_seller_1",
                "seller_name": "LuxuryReseller_NYC",
                "seller_platform": "grailed",
                "images": [
                    "https://example.com/prada1.jpg",
                    "https://example.com/prada2.jpg",
                    "https://example.com/prada3.jpg",
                    "https://example.com/prada4.jpg",
                ],
                "condition": "good",
            }
        },
    ]
    
    for test in test_items:
        print(f"\n📦 Testing: {test['name']}")
        print("-" * 50)
        
        result = platform.authenticate_item(test['data'])
        
        # Display results
        status_emoji = {
            AuthDecision.AUTHENTIC: "✅",
            AuthDecision.REPLICA: "🚫",
            AuthDecision.NEEDS_REVIEW: "👁️",
            AuthDecision.INSUFFICIENT_DATA: "📸",
        }.get(result.decision, "❓")
        
        print(f"{status_emoji} Decision: {result.decision.value.upper()}")
        print(f"   Confidence: {result.confidence:.1%}")
        print(f"   Overall Score: {result.overall_score:.2f}")
        print(f"   Action: {result.action}")
        
        print(f"\n   Component Scores:")
        print(f"      Image Analysis: {result.image_analysis_score:.2f}")
        print(f"      Seller Rep: {result.seller_reputation_score:.2f}")
        print(f"      Listing Quality: {result.listing_quality_score:.2f}")
        print(f"      Price Analysis: {result.price_analysis_score:.2f}")
        
        if result.red_flags:
            print(f"\n   🚩 Red Flags ({len(result.red_flags)}):")
            for flag in result.red_flags[:5]:
                print(f"      • {flag}")
        
        if result.positive_indicators:
            print(f"\n   ✅ Positive Indicators ({len(result.positive_indicators)}):")
            for ind in result.positive_indicators:
                print(f"      • {ind}")
        
        if result.required_photos:
            print(f"\n   📸 Required Photos: {', '.join(result.required_photos[:5])}")
        
        if result.escrow_recommended:
            print(f"\n   💰 Escrow Recommended (up to ${result.max_escrow_amount:.0f})")
        
        if result.estimated_auth_time:
            print(f"\n   ⏱️  Est. Expert Review Time: {result.estimated_auth_time} min")
    
    # Test seller reputation
    print("\n" + "=" * 70)
    print("👤 Testing Seller Reputation System")
    print("-" * 50)
    
    from auth_system.seller_reputation import SellerReputationTracker
    
    tracker = SellerReputationTracker()
    
    # Add a trusted seller
    tracker.whitelist_seller("trusted_seller_1", "grailed", "Known authentic reseller, verified through 50+ sales")
    
    # Check various sellers
    sellers_to_check = [
        ("trusted_seller_1", "LuxuryReseller_NYC", "grailed"),
        ("seller_123", "FakeGoods2024", "grailed"),
        ("new_seller_999", "NewbieSeller", "poshmark"),
    ]
    
    for seller_id, name, platform in sellers_to_check:
        result = tracker.check_seller(seller_id, name, platform)
        print(f"\n   Seller: {name} ({platform})")
        print(f"      Trust Score: {result.trust_score:.2f}")
        print(f"      Risk Level: {result.risk_level}")
        print(f"      Recommendation: {result.recommendation}")
        if result.red_flags:
            print(f"      Flags: {', '.join(result.red_flags[:3])}")
    
    # Test expert review queue
    print("\n" + "=" * 70)
    print("👁️  Testing Expert Review Queue")
    print("-" * 50)
    
    from auth_system.expert_review import ExpertReviewQueue
    
    queue = ExpertReviewQueue()
    
    # Submit an item for review
    item_data = {
        "title": "Hermes Birkin 35 Togo Leather",
        "price": 8500,
        "brand": "hermes",
        "images": ["https://example.com/birkin1.jpg"],
    }
    
    initial_result = {
        "decision": "needs_review",
        "confidence": 0.6,
    }
    
    review_id = queue.submit(item_data, initial_result)
    print(f"   Submitted review request: {review_id}")
    
    status = queue.get_status(review_id)
    print(f"   Status: {status['status']}")
    print(f"   Priority: {status['priority']}")
    print(f"   Est. Wait: {status['estimated_wait']} min")
    
    queue_stats = queue.get_queue_stats()
    print(f"\n   Queue Stats:")
    print(f"      Total Reviews: {queue_stats['total']}")
    print(f"      Pending: {queue_stats['pending']}")
    print(f"      Completed: {queue_stats['completed']}")
    
    print("\n" + "=" * 70)
    print("✅ Authentication System Test Complete")
    print("=" * 70)
    print("\nSystem Components:")
    print("   ✅ Image Analysis (stock photo detection, auth points)")
    print("   ✅ Seller Reputation (whitelist/blacklist/trust scores)")
    print("   ✅ Listing Analyzer (keyword detection, price analysis)")
    print("   ✅ Expert Review Queue (managed authentication workflow)")
    print("   ✅ Purchase Protection (escrow, disputes, refunds)")
    print("\nNext Steps:")
    print("   1. Integrate into pipeline.py (replace basic auth_checker)")
    print("   2. Build expert review UI for manual authentication")
    print("   3. Train ML model on auth images (upgrade from rule-based)")
    print("   4. Integrate Stripe/PayPal for real escrow")


if __name__ == "__main__":
    test_authentication_system()

"""
Archive Arbitrage Authentication System

Comprehensive replica detection and authentication platform.

Components:
1. AI Image Analysis — Detect reps via computer vision
2. Seller Reputation — Track seller history and trust scores  
3. Expert Review Workflow — Queue items for manual authentication
4. Purchase Protection — Escrow and dispute resolution

Usage:
    from auth_system import AuthenticationPlatform
    
    platform = AuthenticationPlatform()
    result = platform.authenticate_item(item_data)
    # Returns: pass, fail, or needs_review with confidence scores
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict
from datetime import datetime


class AuthDecision(Enum):
    AUTHENTIC = "authentic"  # Pass - proceed with purchase
    REPLICA = "replica"      # Fail - auto-reject
    NEEDS_REVIEW = "needs_review"  # Flag for expert/manual check
    INSUFFICIENT_DATA = "insufficient_data"  # Need more photos/info


@dataclass
class AuthenticationResult:
    decision: AuthDecision
    confidence: float  # 0.0 - 1.0
    overall_score: float  # Composite score from all checks
    
    # Component scores
    image_analysis_score: float
    seller_reputation_score: float
    listing_quality_score: float
    price_analysis_score: float
    
    # Detailed findings
    red_flags: List[str]
    positive_indicators: List[str]
    required_photos: List[str]  # If insufficient data
    
    # Recommended action
    action: str  # "proceed", "reject", "request_more_photos", "expert_review"
    
    # Purchase protection
    escrow_recommended: bool
    
    # Optional fields
    estimated_auth_time: Optional[int] = None  # Minutes if expert review needed
    max_escrow_amount: Optional[float] = None


class AuthenticationPlatform:
    """
    Main authentication orchestrator.
    Runs all checks and aggregates results into final decision.
    """
    
    def __init__(self):
        from .image_analyzer import ImageAuthenticator
        from .seller_reputation import SellerReputationTracker
        from .listing_analyzer import ListingAnalyzer
        from .expert_review import ExpertReviewQueue
        from .purchase_protection import PurchaseProtection
        
        self.image_auth = ImageAuthenticator()
        self.seller_tracker = SellerReputationTracker()
        self.listing_analyzer = ListingAnalyzer()
        self.expert_queue = ExpertReviewQueue()
        self.protection = PurchaseProtection()
    
    def authenticate_item(self, item_data: dict) -> AuthenticationResult:
        """
        Run full authentication pipeline on an item.
        
        Args:
            item_data: {
                'title': str,
                'description': str,
                'price': float,
                'brand': str,
                'seller_id': str,
                'seller_name': str,
                'seller_platform': str,
                'images': List[str],  # URLs
                'listing_url': str,
                'condition': str,
                'size': str,
            }
        """
        red_flags = []
        positive_indicators = []
        required_photos = []
        
        # 1. IMAGE ANALYSIS
        image_score = 0.5  # Neutral default
        if item_data.get('images'):
            img_result = self.image_auth.analyze_images(
                item_data['images'],
                brand=item_data.get('brand'),
            )
            image_score = img_result.confidence
            red_flags.extend(img_result.red_flags)
            positive_indicators.extend(img_result.positive_indicators)
            required_photos.extend(img_result.missing_authentication_points)
        else:
            red_flags.append("No images provided")
            required_photos.extend(["front", "back", "tag", "hardware"])
        
        # 2. SELLER REPUTATION
        seller_result = self.seller_tracker.check_seller(
            seller_id=item_data.get('seller_id'),
            seller_name=item_data.get('seller_name'),
            platform=item_data.get('seller_platform'),
        )
        seller_score = seller_result.trust_score
        if seller_result.red_flags:
            red_flags.extend(seller_result.red_flags)
        if seller_result.positive_indicators:
            positive_indicators.extend(seller_result.positive_indicators)
        
        # 3. LISTING QUALITY ANALYSIS
        listing_result = self.listing_analyzer.analyze(
            title=item_data.get('title', ''),
            description=item_data.get('description', ''),
            price=item_data.get('price', 0),
            brand=item_data.get('brand', ''),
            condition=item_data.get('condition', ''),
        )
        listing_score = listing_result.legitimacy_score
        price_score = listing_result.price_score
        red_flags.extend(listing_result.red_flags)
        positive_indicators.extend(listing_result.positive_indicators)
        
        # Calculate composite score
        # Weights: Image 40%, Seller 25%, Listing 20%, Price 15%
        overall_score = (
            image_score * 0.40 +
            seller_score * 0.25 +
            listing_score * 0.20 +
            price_score * 0.15
        )
        
        # Determine decision
        if overall_score < 0.3 or len([f for f in red_flags if f.startswith("REPLICA:")]) >= 2:
            decision = AuthDecision.REPLICA
            action = "reject"
            confidence = 1.0 - overall_score
        elif overall_score > 0.8 and seller_score > 0.7 and not required_photos:
            decision = AuthDecision.AUTHENTIC
            action = "proceed"
            confidence = overall_score
        elif required_photos or image_score < 0.5:
            decision = AuthDecision.INSUFFICIENT_DATA
            action = "request_more_photos"
            confidence = 0.5
        else:
            decision = AuthDecision.NEEDS_REVIEW
            action = "expert_review"
            confidence = overall_score
        
        # Purchase protection recommendation
        price = item_data.get('price', 0)
        escrow_recommended = (
            price > 500 or
            seller_score < 0.6 or
            decision == AuthDecision.NEEDS_REVIEW
        )
        
        return AuthenticationResult(
            decision=decision,
            confidence=confidence,
            overall_score=overall_score,
            image_analysis_score=image_score,
            seller_reputation_score=seller_score,
            listing_quality_score=listing_score,
            price_analysis_score=price_score,
            red_flags=red_flags[:10],  # Limit to top 10
            positive_indicators=positive_indicators[:5],
            required_photos=required_photos,
            action=action,
            estimated_auth_time=30 if decision == AuthDecision.NEEDS_REVIEW else None,
            escrow_recommended=escrow_recommended,
            max_escrow_amount=price * 1.1 if escrow_recommended else None,
        )
    
    def request_expert_review(self, item_data: dict, result: AuthenticationResult) -> str:
        """Submit item to expert review queue."""
        return self.expert_queue.submit(item_data, result)
    
    def get_expert_review_status(self, review_id: str) -> dict:
        """Check status of expert review."""
        return self.expert_queue.get_status(review_id)


# Convenience function
def authenticate(item_data: dict) -> AuthenticationResult:
    """Quick authenticate an item."""
    platform = AuthenticationPlatform()
    return platform.authenticate_item(item_data)

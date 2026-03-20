"""
Authentication-based comp filtering for luxury items.

Uses Grailed authentication status to ensure comps represent true market value.
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger("auth_filter")


@dataclass
class CompAuthStatus:
    """Authentication status for a sold comp."""
    is_authenticated: bool
    auth_service: Optional[str]  # 'grailed', 'realreal', 'entupy', etc.
    confidence_score: float  # 0-1


def filter_authenticated_comps(sold_items: List) -> List:
    """
    Filter sold items to prioritize authenticated comps.
    
    Strategy:
    1. If >= 5 authenticated comps exist, use only those
    2. Otherwise, weight authenticated comps 2x in price calc
    3. Never use unauthenticated comps for high-value items (>$2000)
    """
    if not sold_items:
        return []
    
    # Separate authenticated vs unauthenticated
    authenticated = []
    unauthenticated = []
    
    for item in sold_items:
        auth_status = get_auth_status(item)
        if auth_status.is_authenticated:
            authenticated.append(item)
        else:
            unauthenticated.append(item)
    
    # For high-value items, require authentication
    avg_price = sum(i.price for i in sold_items) / len(sold_items)
    
    if avg_price > 2000:
        # High-value: only use authenticated
        if len(authenticated) >= 3:
            logger.info(f"Using {len(authenticated)} authenticated comps (high-value item)")
            return authenticated
        else:
            logger.warning(f"Only {len(authenticated)} authenticated comps for high-value item")
            # Fall back to all comps but flag for review
            return sold_items
    
    # For lower-value items, prefer authenticated but allow mix
    if len(authenticated) >= 5:
        # Plenty of authenticated comps
        logger.info(f"Using {len(authenticated)} authenticated comps only")
        return authenticated
    elif len(authenticated) >= 3:
        # Some authenticated, supplement with unauthenticated
        logger.info(f"Using {len(authenticated)} auth + {len(unauthenticated)//2} unauth comps")
        return authenticated + unauthenticated[:len(authenticated)]
    else:
        # Few authenticated, use all but weight them
        logger.info(f"Only {len(authenticated)} authenticated, using all comps")
        return sold_items


def get_auth_status(item) -> CompAuthStatus:
    """Extract authentication status from sold item."""
    raw_data = getattr(item, 'raw_data', {}) or {}
    
    # Check Grailed authentication
    grailed_auth = raw_data.get('authentication_status') == 'authenticated'
    
    # Check for authentication badge in title/description
    title = getattr(item, 'title', '').lower()
    desc = raw_data.get('description', '').lower()
    
    auth_keywords = [
        'authenticated', 'grailed authenticated', 'real authentication',
        'entupy', 'legit app', 'authenticate first'
    ]
    
    has_auth_keyword = any(kw in title or kw in desc for kw in auth_keywords)
    
    # Check seller reputation as proxy
    seller_rating = raw_data.get('seller_rating', 0)
    seller_feedback = raw_data.get('seller_feedback_count', 0)
    
    # High-rep sellers more likely to sell authentic
    trusted_seller = seller_rating >= 4.9 and seller_feedback >= 50
    
    # Determine confidence
    if grailed_auth:
        confidence = 1.0
        service = 'grailed'
    elif has_auth_keyword and trusted_seller:
        confidence = 0.8
        service = 'seller_claimed'
    elif trusted_seller:
        confidence = 0.6
        service = 'trusted_seller'
    else:
        confidence = 0.3
        service = None
    
    return CompAuthStatus(
        is_authenticated=(confidence >= 0.6),
        auth_service=service,
        confidence_score=confidence
    )


def calculate_weighted_price(sold_items: List) -> Optional[float]:
    """Calculate price weighted by authentication confidence."""
    if not sold_items:
        return None
    
    total_weight = 0
    weighted_sum = 0
    
    for item in sold_items:
        auth_status = get_auth_status(item)
        
        # Weight: authenticated = 2x, unauthenticated = 1x
        weight = 2.0 if auth_status.is_authenticated else 1.0
        weight *= auth_status.confidence_score
        
        weighted_sum += item.price * weight
        total_weight += weight
    
    if total_weight == 0:
        return None
    
    return weighted_sum / total_weight


def get_auth_confidence_score(sold_items: List) -> float:
    """Get overall authentication confidence for a set of comps."""
    if not sold_items:
        return 0.0
    
    total_confidence = sum(
        get_auth_status(item).confidence_score 
        for item in sold_items
    )
    
    return total_confidence / len(sold_items)


class AuthenticationPipeline:
    """Full authentication pipeline for deal verification."""
    
    def __init__(self):
        self.min_auth_comps = 3
        self.min_auth_confidence = 0.6
        self.high_value_threshold = 2000
    
    def process_comps(self, sold_items: List, item_price: float) -> Dict:
        """Process comps and return authentication analysis."""
        if not sold_items:
            return {
                'usable': False,
                'reason': 'No sold comps',
                'authenticated_comps': 0,
                'confidence': 0.0,
            }
        
        # Filter to authenticated
        auth_comps = filter_authenticated_comps(sold_items)
        
        # Calculate confidence
        confidence = get_auth_confidence_score(auth_comps)
        
        # Count authenticated
        auth_count = sum(
            1 for item in auth_comps 
            if get_auth_status(item).is_authenticated
        )
        
        # Determine if usable
        if item_price > self.high_value_threshold:
            # High-value requires strong authentication
            usable = (
                auth_count >= self.min_auth_comps and 
                confidence >= self.min_auth_confidence
            )
            reason = 'High-value item requires authentication' if not usable else 'OK'
        else:
            # Lower-value more flexible
            usable = auth_count >= 2 or confidence >= 0.5
            reason = 'OK' if usable else 'Insufficient authentication'
        
        return {
            'usable': usable,
            'reason': reason,
            'authenticated_comps': auth_count,
            'total_comps': len(auth_comps),
            'confidence': confidence,
            'weighted_price': calculate_weighted_price(auth_comps),
        }


# Convenience function
def authenticate_comps(sold_items: List, item_price: float = 0) -> Dict:
    """Main entry point for comp authentication."""
    pipeline = AuthenticationPipeline()
    return pipeline.process_comps(sold_items, item_price)

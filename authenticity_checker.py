"""
Authenticity Checker — Detect replicas and fakes before they enter the pipeline.

This is CRITICAL for maintaining trust and avoiding platform bans.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Dict
from enum import Enum


class AuthStatus(Enum):
    AUTHENTIC = "authentic"
    SUSPICIOUS = "suspicious"  # Flag for manual review
    REPLICA = "replica"  # Auto-reject


@dataclass
class AuthCheckResult:
    status: AuthStatus
    confidence: float  # 0.0 - 1.0
    reasons: List[str]
    action: str  # "proceed", "review", "reject"


# Keywords that strongly indicate replicas
REPLICA_KEYWORDS = [
    # Direct replica terms
    r'\breplica\b',
    r'\brep\b',
    r'\b1:1\b',
    r'\b1 to 1\b',
    r'\bone to one\b',
    r'\bunauthorized\b',
    r'\bua\b',
    r'\bmirror\b',
    r'\bhigh quality copy\b',
    r'\bsuper copy\b',
    r'\bAAA\b',
    r'\bperfect copy\b',
    r'\bexact copy\b',
    r'\bidentical\b',
    r'\bindistinguishable\b',
    
    # Chinese wholesale terms
    r'\btop quality\b',
    r'\bfactory direct\b',
    r'\boem\b',
    r'\boriginal equipment\b',
    r'\bgrade\s*[A-Z]\+?\b',  # "Grade A", "Grade AAA"
    r'\bbest version\b',
    r'\blatest batch\b',
    
    # Suspicious phrases
    r'\bcomes with everything\b',
    r'\bbox tags dust bag\b',
    r'\ball accessories\b',
    r'\bpremium quality\b',
    r'\bmasterpiece\b',
]

# Suspicious but not definitive (flag for review)
SUSPICIOUS_KEYWORDS = [
    r'\bhigh quality\b',
    r'\bpremium\b',
    r'\bexcellent quality\b',
    r'\b1:1 quality\b',
    r'\bperfect condition\b.*\bnever worn\b',
    r'\bwholesale\b',
    r'\bbulk\b',
    r'\bmultiple available\b',
    r'\bmore colors\b',
    r'\bdm for pics\b',
    r'\bdm for more\b',
    r'\bwhatsapp\b',
    r'\bwechat\b',
    r'\bins\b.*\bgram\b',
    r'\bfollow\s+for\s+more\b',
]

# Brand-specific authentication markers
BRAND_AUTH_MARKERS = {
    "rick owens": {
        "authentic_tags": ["rick owens", "drkshdw", "darkshadow"],
        "common_rep_misspellings": ["rickowens", "drkshaw", "darkshdw"],
        "hardware_details": ["exposed zipper", "milk zipper"],
        "suspicious_low_price": 150,  # Under $150 for mainline is suspicious
    },
    "balenciaga": {
        "authentic_tags": ["balenciaga", "paris"],
        "common_rep_misspellings": ["balenciage", "balanciaga"],
        "logo_checks": ["font weight", "letter spacing"],
        "suspicious_low_price": 200,
    },
    "prada": {
        "authentic_tags": ["prada", "milano", "made in italy"],
        "common_rep_misspellings": ["prado", "milian", "milan"],
        "hardware_checks": ["triangle plaque", " Milano spelling"],
        "suspicious_low_price": 250,
    },
    "saint laurent": {
        "authentic_tags": ["saint laurent", "ysl", "paris"],
        "common_rep_misspellings": ["st laurent", "saint laurant"],
        "suspicious_low_price": 200,
    },
    "chrome hearts": {
        "authentic_tags": ["chrome hearts", "925", "sterling"],
        "suspicious_low_price": 300,  # CH is expensive
    },
    "helmut lang": {
        "authentic_tags": ["helmut lang"],
        "suspicious_low_price": 100,
    },
}

# Price thresholds by brand (under this = suspicious)
PRICE_THRESHOLDS = {
    "rick owens": 150,
    "balenciaga": 200,
    "prada": 250,
    "saint laurent": 200,
    "chrome hearts": 300,
    "maison margiela": 200,
    "vetements": 150,
    "helmut lang": 100,
    "number nine": 150,
    "undercover": 100,
    "comme des garcons": 80,
    "yohji yamamoto": 150,
    "issey miyake": 100,
}


class AuthenticityChecker:
    """Check items for authenticity markers."""
    
    def __init__(self):
        self.replica_patterns = [re.compile(kw, re.IGNORECASE) for kw in REPLICA_KEYWORDS]
        self.suspicious_patterns = [re.compile(kw, re.IGNORECASE) for kw in SUSPICIOUS_KEYWORDS]
    
    def check_item(
        self,
        title: str,
        description: str = "",
        price: float = 0,
        brand: str = "",
        seller_name: str = "",
        seller_rating: Optional[float] = None,
        seller_sales: int = 0,
        images: List[str] = None,
    ) -> AuthCheckResult:
        """
        Check an item for authenticity.
        
        Returns AuthCheckResult with status and action recommendation.
        """
        reasons = []
        replica_score = 0.0
        suspicious_score = 0.0
        
        text_to_check = f"{title} {description}".lower()
        brand_lower = brand.lower()
        
        # 1. Check for replica keywords
        for pattern in self.replica_patterns:
            if pattern.search(text_to_check):
                replica_score += 0.3
                match = pattern.search(text_to_check).group()
                reasons.append(f"Replica keyword: '{match}'")
        
        # 2. Check for suspicious keywords
        for pattern in self.suspicious_patterns:
            if pattern.search(text_to_check):
                suspicious_score += 0.1
                match = pattern.search(text_to_check).group()
                reasons.append(f"Suspicious phrase: '{match}'")
        
        # 3. Price analysis
        if brand_lower in PRICE_THRESHOLDS:
            threshold = PRICE_THRESHOLDS[brand_lower]
            if price > 0 and price < threshold:
                # Price too low for authentic
                price_ratio = price / threshold
                if price_ratio < 0.3:
                    replica_score += 0.4
                    reasons.append(f"Price ${price} is {price_ratio:.0%} of typical minimum (${threshold})")
                elif price_ratio < 0.5:
                    suspicious_score += 0.2
                    reasons.append(f"Price ${price} suspiciously low for {brand} (typical min: ${threshold})")
        
        # 4. Brand-specific checks
        if brand_lower in BRAND_AUTH_MARKERS:
            markers = BRAND_AUTH_MARKERS[brand_lower]
            
            # Check for misspellings
            for misspelling in markers.get("common_rep_misspellings", []):
                if misspelling in text_to_check:
                    replica_score += 0.25
                    reasons.append(f"Common rep misspelling: '{misspelling}'")
        
        # 5. Seller reputation
        if seller_sales == 0 and price > 100:
            suspicious_score += 0.15
            reasons.append("New seller with high-value item")
        
        if seller_rating is not None and seller_rating < 3.0:
            suspicious_score += 0.1
            reasons.append(f"Low seller rating: {seller_rating}")
        
        # 6. Image analysis (basic checks)
        if images:
            # Stock photo detection (simplified - would use reverse image search)
            stock_photo_indicators = [
                "stockx", "goat", "grailed", "ebay", "poshmark"
            ]
            for img in images:
                img_lower = img.lower()
                for indicator in stock_photo_indicators:
                    if indicator in img_lower and "user" not in img_lower:
                        suspicious_score += 0.15
                        reasons.append(f"Possible stock photo source: {indicator}")
                        break
        
        # Determine final status
        if replica_score >= 0.5:
            return AuthCheckResult(
                status=AuthStatus.REPLICA,
                confidence=min(replica_score, 1.0),
                reasons=reasons,
                action="reject"
            )
        elif replica_score >= 0.3 or suspicious_score >= 0.4:
            return AuthCheckResult(
                status=AuthStatus.SUSPICIOUS,
                confidence=min(replica_score + suspicious_score, 1.0),
                reasons=reasons,
                action="review"
            )
        else:
            return AuthCheckResult(
                status=AuthStatus.AUTHENTIC,
                confidence=1.0 - (replica_score + suspicious_score),
                reasons=reasons or ["No red flags detected"],
                action="proceed"
            )
    
    def batch_check(self, items: List[dict]) -> List[AuthCheckResult]:
        """Check multiple items."""
        results = []
        for item in items:
            result = self.check_item(
                title=item.get("title", ""),
                description=item.get("description", ""),
                price=item.get("price", 0),
                brand=item.get("brand", ""),
                seller_name=item.get("seller_name", ""),
                seller_rating=item.get("seller_rating"),
                seller_sales=item.get("seller_sales", 0),
                images=item.get("images", []),
            )
            results.append(result)
        return results


# Convenience function
def check_authenticity(**kwargs) -> AuthCheckResult:
    """Quick check an item."""
    checker = AuthenticityChecker()
    return checker.check_item(**kwargs)


if __name__ == "__main__":
    # Test examples
    test_cases = [
        {
            "title": "Rick Owens DRKSHDW Geobasket High Tops",
            "price": 120,
            "brand": "rick owens",
            "description": "Great condition, comes with box and tags",
        },
        {
            "title": "Balenciaga Track Sneakers 1:1 Replica",
            "price": 80,
            "brand": "balenciaga",
            "description": "High quality mirror copy, indistinguishable from authentic",
        },
        {
            "title": "Prada Nylon Bag - Wholesale Price",
            "price": 45,
            "brand": "prada",
            "description": "Multiple available, DM for more pics. Premium quality AAA grade",
        },
    ]
    
    checker = AuthenticityChecker()
    for test in test_cases:
        result = checker.check_item(**test)
        print(f"\n📝 {test['title'][:50]}...")
        print(f"   Status: {result.status.value.upper()}")
        print(f"   Confidence: {result.confidence:.1%}")
        print(f"   Action: {result.action}")
        print(f"   Reasons: {', '.join(result.reasons[:3])}")

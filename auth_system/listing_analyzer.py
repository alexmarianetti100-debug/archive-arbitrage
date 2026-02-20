"""
Listing Quality Analyzer

Analyzes listing text for authenticity markers.
Checks: title, description, price, keywords.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class ListingAnalysisResult:
    legitimacy_score: float  # 0.0 - 1.0
    price_score: float
    red_flags: List[str]
    positive_indicators: List[str]


class ListingAnalyzer:
    """Analyze listing text for authenticity markers."""
    
    # Suspicious keywords
    REPLICA_KEYWORDS = [
        r'\breplica\b', r'\brep\b', r'\b1:1\b', r'\bmirror\b',
        r'\bunauthorized\b', r'\bua\b', r'\bhigh quality copy\b',
        r'\bperfect copy\b', r'\bexact copy\b', r'\bsuper copy\b',
        r'\bAAA\b', r'\bgrade [A-Z]\+?\b', r'\bfactory\b.*\bdirect\b',
        r'\bwholesale\b', r'\bbulk\b', r'\boem\b',
    ]
    
    SUSPICIOUS_PHRASES = [
        r'\bcomes with everything\b',
        r'\bbox tags dust bag\b',
        r'\bdm for\b',
        r'\bdm me\b',
        r'\bwhatsapp\b',
        r'\bwechat\b',
        r'\bins\s*gram\b',
        r'\bfollow for more\b',
        r'\bmultiple available\b',
        r'\bmore colors\b',
        r'\bvintage\s*inspired\b',
        r'\bstyle\b',  # "Gucci style" not actual Gucci
    ]
    
    # Positive authenticity indicators
    AUTHENTIC_INDICATORS = [
        r'\bauthentic\b', r'\b100%\s*authentic\b', r'\bguaranteed authentic\b',
        r'\boriginal\b', r'\bretail\b', r'\bpurchased from\b',
        r'\breceipt\b', r'\bproof of purchase\b',
        r'\bdust bag\b', r'\bbox included\b',
    ]
    
    # Brand price minimums (suspicious if under)
    PRICE_MINIMUMS = {
        'rick owens': 100,
        'balenciaga': 150,
        'prada': 200,
        'saint laurent': 150,
        'chrome hearts': 250,
        'maison margiela': 150,
        'vetements': 100,
        'helmut lang': 80,
        'number nine': 120,
        'undercover': 80,
        'comme des garcons': 60,
        'yohji yamamoto': 120,
        'issey miyake': 80,
    }
    
    def analyze(
        self,
        title: str,
        description: str,
        price: float,
        brand: str,
        condition: str,
    ) -> ListingAnalysisResult:
        """
        Analyze a listing for authenticity markers.
        """
        red_flags = []
        positive = []
        
        text = f"{title} {description}".lower()
        
        # 1. Check for replica keywords
        for pattern in self.REPLICA_KEYWORDS:
            if re.search(pattern, text, re.IGNORECASE):
                match = re.search(pattern, text, re.IGNORECASE).group()
                red_flags.append(f"REPLICA: Keyword '{match}' detected")
        
        # 2. Check for suspicious phrases
        for pattern in self.SUSPICIOUS_PHRASES:
            if re.search(pattern, text, re.IGNORECASE):
                match = re.search(pattern, text, re.IGNORECASE).group()
                red_flags.append(f"Suspicious phrase: '{match}'")
        
        # 3. Check for positive indicators
        for pattern in self.AUTHENTIC_INDICATORS:
            if re.search(pattern, text, re.IGNORECASE):
                match = re.search(pattern, text, re.IGNORECASE).group()
                positive.append(f"Authenticity claim: '{match}'")
        
        # 4. Price analysis
        price_score = self._analyze_price(price, brand, condition)
        
        if price > 0:
            brand_lower = brand.lower()
            if brand_lower in self.PRICE_MINIMUMS:
                min_price = self.PRICE_MINIMUMS[brand_lower]
                if price < min_price * 0.3:
                    red_flags.append(f"Price ${price} is extremely low for {brand} (typical min: ${min_price})")
                elif price < min_price * 0.5:
                    red_flags.append(f"Price ${price} is suspiciously low for {brand}")
        
        # 5. Title quality
        if len(title) < 10:
            red_flags.append("Title is very short - minimal effort listing")
        
        if not any(word in title.lower() for word in [brand.lower()]):
            red_flags.append("Brand not mentioned in title")
        
        # 6. Description quality
        if len(description) < 20:
            red_flags.append("Description is very short")
        
        # Calculate legitimacy score
        legitimacy = 0.5
        
        # Penalize for replica flags (heavy)
        replica_flags = [f for f in red_flags if f.startswith("REPLICA:")]
        legitimacy -= len(replica_flags) * 0.3
        
        # Penalize for other red flags
        legitimacy -= (len(red_flags) - len(replica_flags)) * 0.08
        
        # Boost for positive indicators
        legitimacy += len(positive) * 0.05
        
        # Price factor
        legitimacy += (price_score - 0.5) * 0.2
        
        legitimacy = max(0.0, min(1.0, legitimacy))
        
        return ListingAnalysisResult(
            legitimacy_score=legitimacy,
            price_score=price_score,
            red_flags=red_flags,
            positive_indicators=positive,
        )
    
    def _analyze_price(self, price: float, brand: str, condition: str) -> float:
        """
        Score price legitimacy.
        Returns 0.0 - 1.0 (higher = more legitimate pricing)
        """
        if price <= 0:
            return 0.0
        
        score = 0.5
        brand_lower = brand.lower()
        
        # Check against brand minimums
        if brand_lower in self.PRICE_MINIMUMS:
            min_price = self.PRICE_MINIMUMS[brand_lower]
            
            if price < min_price * 0.2:
                score -= 0.4
            elif price < min_price * 0.4:
                score -= 0.2
            elif price >= min_price:
                score += 0.2
        
        # Condition adjustment
        condition_lower = condition.lower() if condition else ""
        if 'new' in condition_lower or 'nwt' in condition_lower:
            # New should be close to retail
            score += 0.1
        elif 'worn' in condition_lower or 'used' in condition_lower:
            # Used at low price is normal
            score += 0.05
        
        return max(0.0, min(1.0, score))
    
    def extract_authenticity_claims(self, text: str) -> List[str]:
        """Extract all authenticity-related claims from text."""
        claims = []
        
        patterns = [
            r'100%\s*authentic',
            r'guaranteed\s*authentic',
            r'purchased\s*(from|at)\s*[^.]+',
            r'original\s*owner',
            r'receipt\s*(included|available)',
            r'dust\s*bag\s*(and\s*)?box',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                claims.append(match.group())
        
        return claims

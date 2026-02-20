"""
Seller Reputation Tracker

Tracks seller history across platforms to identify:
- Trusted authentic sellers (whitelist)
- Known replica sellers (blacklist)
- New/unproven sellers (requires extra scrutiny)
- Suspicious patterns (multiple accounts, rapid listings)
"""

import json
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict


@dataclass
class SellerProfile:
    """Complete seller reputation profile."""
    seller_id: str
    platform: str
    seller_name: str
    
    # Reputation scores (0.0 - 1.0)
    trust_score: float = 0.5  # Overall trust
    authenticity_score: float = 0.5  # Track record of selling authentic
    communication_score: float = 0.5  # Response rate, professionalism
    
    # Stats
    total_sales: int = 0
    total_listings: int = 0
    authenticated_sales: int = 0  # Sales verified authentic
    disputed_sales: int = 0
    replica_claims: int = 0  # Times accused of selling reps
    
    # Account info
    account_age_days: int = 0
    first_seen: Optional[str] = None
    last_active: Optional[str] = None
    
    # Flags
    is_whitelisted: bool = False
    is_blacklisted: bool = False
    blacklist_reason: Optional[str] = None
    
    # Notes
    notes: List[str] = None
    
    def __post_init__(self):
        if self.notes is None:
            self.notes = []


@dataclass
class SellerCheckResult:
    trust_score: float
    risk_level: str  # "low", "medium", "high", "critical"
    red_flags: List[str]
    positive_indicators: List[str]
    recommendation: str  # "proceed", "caution", "avoid"


class SellerReputationTracker:
    """
    Track and query seller reputation across platforms.
    
    Stores data in JSON file (upgrade to database for scale).
    """
    
    DATA_FILE = Path(__file__).parent.parent / "data" / "seller_reputation.json"
    
    def __init__(self):
        self.sellers: Dict[str, SellerProfile] = {}
        self._load_data()
    
    def _get_key(self, seller_id: str, platform: str) -> str:
        """Generate unique key for seller+platform combo."""
        return hashlib.md5(f"{platform}:{seller_id}".encode()).hexdigest()
    
    def _load_data(self):
        """Load seller data from disk."""
        if self.DATA_FILE.exists():
            try:
                with open(self.DATA_FILE, 'r') as f:
                    data = json.load(f)
                    for key, profile_data in data.items():
                        self.sellers[key] = SellerProfile(**profile_data)
            except Exception as e:
                print(f"Error loading seller data: {e}")
    
    def _save_data(self):
        """Save seller data to disk."""
        self.DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.DATA_FILE, 'w') as f:
            data = {k: asdict(v) for k, v in self.sellers.items()}
            json.dump(data, f, indent=2)
    
    def check_seller(
        self,
        seller_id: Optional[str],
        seller_name: Optional[str],
        platform: str,
    ) -> SellerCheckResult:
        """
        Check a seller's reputation.
        
        Returns trust score and risk assessment.
        """
        if not seller_id:
            # Anonymous/untraceable seller
            return SellerCheckResult(
                trust_score=0.3,
                risk_level="high",
                red_flags=["Unable to verify seller identity"],
                positive_indicators=[],
                recommendation="caution",
            )
        
        key = self._get_key(seller_id, platform)
        
        # Create new profile if not exists
        if key not in self.sellers:
            self.sellers[key] = SellerProfile(
                seller_id=seller_id,
                platform=platform,
                seller_name=seller_name or "Unknown",
                first_seen=datetime.now().isoformat(),
            )
        
        profile = self.sellers[key]
        red_flags = []
        positive_indicators = []
        
        # Check blacklist first
        if profile.is_blacklisted:
            return SellerCheckResult(
                trust_score=0.0,
                risk_level="critical",
                red_flags=[f"BLACKLISTED: {profile.blacklist_reason}"],
                positive_indicators=[],
                recommendation="avoid",
            )
        
        # Check whitelist
        if profile.is_whitelisted:
            return SellerCheckResult(
                trust_score=0.95,
                risk_level="low",
                red_flags=[],
                positive_indicators=["Verified authentic seller"],
                recommendation="proceed",
            )
        
        # Analyze account age
        if profile.account_age_days < 30:
            red_flags.append("Account less than 30 days old")
        elif profile.account_age_days > 365:
            positive_indicators.append("Established seller (1+ year)")
        
        # Analyze sales history
        if profile.total_sales == 0:
            red_flags.append("No sales history")
        elif profile.total_sales < 5:
            red_flags.append("Minimal sales history (< 5 sales)")
        else:
            positive_indicators.append(f"{profile.total_sales} sales on record")
        
        # Check authenticity track record
        if profile.authenticated_sales > 10:
            positive_indicators.append(f"{profile.authenticated_sales} verified authentic sales")
        
        if profile.replica_claims > 0:
            red_flags.append(f"{profile.replica_claims} replica claim(s) against seller")
        
        if profile.disputed_sales > 3:
            red_flags.append("Multiple disputes - exercise caution")
        
        # Check listing patterns
        if profile.total_listings > 100 and profile.total_sales < 10:
            red_flags.append("High listings but low sales - possible rep seller")
        
        # Calculate risk level
        trust_score = self._calculate_trust_score(profile)
        
        if trust_score >= 0.8:
            risk_level = "low"
            recommendation = "proceed"
        elif trust_score >= 0.5:
            risk_level = "medium"
            recommendation = "caution"
        elif trust_score >= 0.3:
            risk_level = "high"
            recommendation = "caution"
        else:
            risk_level = "critical"
            recommendation = "avoid"
        
        # Update last seen
        profile.last_active = datetime.now().isoformat()
        self._save_data()
        
        return SellerCheckResult(
            trust_score=trust_score,
            risk_level=risk_level,
            red_flags=red_flags,
            positive_indicators=positive_indicators,
            recommendation=recommendation,
        )
    
    def _calculate_trust_score(self, profile: SellerProfile) -> float:
        """Calculate composite trust score."""
        score = 0.5  # Start neutral
        
        # Account age factor
        if profile.account_age_days > 365:
            score += 0.15
        elif profile.account_age_days > 180:
            score += 0.1
        elif profile.account_age_days < 30:
            score -= 0.2
        
        # Sales volume factor
        if profile.total_sales > 50:
            score += 0.15
        elif profile.total_sales > 10:
            score += 0.1
        elif profile.total_sales == 0:
            score -= 0.15
        
        # Authenticity track record
        if profile.authenticated_sales > 0:
            auth_ratio = profile.authenticated_sales / max(profile.total_sales, 1)
            score += auth_ratio * 0.2
        
        # Penalize for issues
        score -= profile.replica_claims * 0.15
        score -= profile.disputed_sales * 0.05
        
        # Whitelist/blacklist override
        if profile.is_whitelisted:
            score = 0.95
        if profile.is_blacklisted:
            score = 0.0
        
        return max(0.0, min(1.0, score))
    
    def whitelist_seller(self, seller_id: str, platform: str, reason: str):
        """Mark seller as trusted authentic source."""
        key = self._get_key(seller_id, platform)
        if key in self.sellers:
            self.sellers[key].is_whitelisted = True
            self.sellers[key].notes.append(f"Whitelisted: {reason}")
            self._save_data()
    
    def blacklist_seller(self, seller_id: str, platform: str, reason: str):
        """Mark seller as replica seller."""
        key = self._get_key(seller_id, platform)
        if key in self.sellers:
            self.sellers[key].is_blacklisted = True
            self.sellers[key].blacklist_reason = reason
            self.sellers[key].notes.append(f"Blacklisted: {reason}")
            self._save_data()
    
    def record_authenticated_sale(self, seller_id: str, platform: str):
        """Record that a sale was verified authentic."""
        key = self._get_key(seller_id, platform)
        if key in self.sellers:
            self.sellers[key].authenticated_sales += 1
            self.sellers[key].total_sales += 1
            self._save_data()
    
    def record_replica_claim(self, seller_id: str, platform: str, details: str):
        """Record a claim that seller sold replicas."""
        key = self._get_key(seller_id, platform)
        if key in self.sellers:
            self.sellers[key].replica_claims += 1
            self.sellers[key].notes.append(f"Replica claim: {details}")
            self._save_data()
    
    def get_trusted_sellers(self, platform: Optional[str] = None) -> List[SellerProfile]:
        """Get list of whitelisted/trusted sellers."""
        trusted = [s for s in self.sellers.values() if s.is_whitelisted]
        if platform:
            trusted = [s for s in trusted if s.platform == platform]
        return sorted(trusted, key=lambda s: s.authenticated_sales, reverse=True)
    
    def get_flagged_sellers(self) -> List[SellerProfile]:
        """Get sellers with red flags."""
        flagged = []
        for seller in self.sellers.values():
            if seller.is_blacklisted:
                flagged.append(seller)
            elif seller.replica_claims > 0:
                flagged.append(seller)
            elif seller.total_sales > 0 and seller.authenticated_sales / seller.total_sales < 0.5:
                flagged.append(seller)
        return flagged

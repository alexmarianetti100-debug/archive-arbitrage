"""ML-powered deal scoring using XGBoost."""

from __future__ import annotations

import json
import pickle
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

@dataclass
class DealFeatures:
    """Features extracted from a deal for ML scoring."""
    # Price features
    list_price: float
    market_price: float
    gap_percent: float
    profit_estimate: float
    
    # Item features
    brand: str
    category: str
    condition: str
    has_box: bool
    has_dustbag: bool
    
    # Seller features
    seller_rating: float
    seller_sales: int
    seller_country: str
    
    # Market features
    days_since_last_sale: int
    comps_count: int
    price_trend: float  # -1 to 1 (down to up)
    
    # Image features (from CLIP)
    image_quality_score: float  # 0-1
    condition_score: float  # 0-1 (ML predicted)
    
    # Temporal features
    day_of_week: int  # 0-6
    hour_of_day: int  # 0-23
    is_weekend: bool

class MLDealScorer:
    """XGBoost-based deal scoring."""
    
    def __init__(self, model_path: Optional[str] = None):
        self.model: Optional[xgb.XGBClassifier] = None
        self.model_path = model_path or "data/models/deal_scorer.pkl"
        self.feature_names = [
            "list_price", "market_price", "gap_percent", "profit_estimate",
            "has_box", "has_dustbag", "seller_rating", "seller_sales",
            "days_since_last_sale", "comps_count", "price_trend",
            "image_quality_score", "condition_score", "day_of_week",
            "hour_of_day", "is_weekend",
        ]
        self._brand_encoder: Dict[str, int] = {}
        self._category_encoder: Dict[str, int] = {}
        self._load_model()
    
    def _load_model(self):
        """Load trained model if exists."""
        if not XGBOOST_AVAILABLE:
            return
        
        path = Path(self.model_path)
        if path.exists():
            try:
                with open(path, 'rb') as f:
                    data = pickle.load(f)
                    self.model = data.get('model')
                    self._brand_encoder = data.get('brand_encoder', {})
                    self._category_encoder = data.get('category_encoder', {})
                print(f"Loaded ML model from {self.model_path}")
            except Exception as e:
                print(f"Failed to load model: {e}")
    
    def _encode_categorical(self, brand: str, category: str) -> tuple:
        """Encode categorical features."""
        # Simple hash encoding for now
        brand_enc = hash(brand.lower()) % 1000
        cat_enc = hash(category.lower()) % 100
        return brand_enc, cat_enc
    
    def _extract_features(self, features: DealFeatures) -> List[float]:
        """Convert DealFeatures to model input."""
        brand_enc, cat_enc = self._encode_categorical(features.brand, features.category)
        
        return [
            features.list_price,
            features.market_price,
            features.gap_percent,
            features.profit_estimate,
            float(features.has_box),
            float(features.has_dustbag),
            features.seller_rating,
            features.seller_sales,
            features.days_since_last_sale,
            features.comps_count,
            features.price_trend,
            features.image_quality_score,
            features.condition_score,
            features.day_of_week,
            features.hour_of_day,
            float(features.is_weekend),
            brand_enc,
            cat_enc,
        ]
    
    def score(self, features: DealFeatures) -> Dict[str, Any]:
        """Score a deal. Returns dict with score and explanation."""
        if not XGBOOST_AVAILABLE or self.model is None:
            # Fallback to rule-based
            return self._rule_based_score(features)
        
        try:
            X = [self._extract_features(features)]
            score = self.model.predict_proba(X)[0][1]  # Probability of good deal
            
            return {
                "score": float(score),
                "confidence": "high" if score > 0.8 or score < 0.2 else "medium",
                "method": "ml",
                "features_used": len(self.feature_names),
            }
        except Exception as e:
            return self._rule_based_score(features)
    
    def _rule_based_score(self, features: DealFeatures) -> Dict[str, Any]:
        """Fallback rule-based scoring."""
        score = 0.5
        
        # Gap-based scoring
        if features.gap_percent > 0.5:
            score += 0.2
        elif features.gap_percent > 0.3:
            score += 0.1
        
        # Profit-based
        if features.profit_estimate > 200:
            score += 0.15
        
        # Seller quality
        if features.seller_rating > 4.5:
            score += 0.1
        
        # Market liquidity
        if features.comps_count > 10:
            score += 0.05
        
        return {
            "score": min(1.0, score),
            "confidence": "low",
            "method": "rule_based",
            "features_used": 0,
        }
    
    def train(self, X: List[List[float]], y: List[int]) -> bool:
        """Train model on historical data."""
        if not XGBOOST_AVAILABLE:
            print("XGBoost not available, cannot train")
            return False
        
        try:
            self.model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                objective='binary:logistic',
            )
            self.model.fit(X, y)
            
            # Save model
            Path(self.model_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'brand_encoder': self._brand_encoder,
                    'category_encoder': self._category_encoder,
                }, f)
            
            print(f"Trained and saved model to {self.model_path}")
            return True
        except Exception as e:
            print(f"Training failed: {e}")
            return False

# Global scorer instance
_scorer_instance: Optional[MLDealScorer] = None

def get_scorer() -> MLDealScorer:
    """Get or create global scorer instance."""
    global _scorer_instance
    if _scorer_instance is None:
        _scorer_instance = MLDealScorer()
    return _scorer_instance

#!/usr/bin/env python3
"""
Deal Performance Tracker - Track accuracy of price predictions vs actual outcomes.

This module tracks:
1. Predicted prices vs actual sale prices
2. Deal performance (did flipped items sell? at what price?)
3. CV-based confidence validation
4. Model accuracy over time
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger("deal_tracker")

# Data file for tracking deal performance
DEAL_TRACKER_FILE = Path(__file__).parent.parent / "data" / "deal_performance.jsonl"


@dataclass
class DealPrediction:
    """Record of a price prediction for tracking accuracy."""
    timestamp: str
    query: str
    item_title: str
    item_url: str
    predicted_price: float
    prediction_method: str  # "standard" or "hyper"
    cv: Optional[float]  # Coefficient of variation (for hyper pricing)
    confidence_level: Optional[str]  # "high", "medium", "low"
    num_comps: int

    # Execution context
    buy_price: Optional[float] = None
    buy_platform: Optional[str] = None
    sell_platform: Optional[str] = None
    estimated_profit: Optional[float] = None
    estimated_fees: Optional[float] = None
    deal_status: str = "alerted"  # alerted | purchased | listed | sold | expired | returned

    # Actual outcome (filled in later)
    actual_sale_price: Optional[float] = None
    actual_profit: Optional[float] = None
    sale_date: Optional[str] = None
    days_to_sell: Optional[int] = None

    # Performance metrics
    prediction_error_pct: Optional[float] = None
    within_10pct: Optional[bool] = None
    within_20pct: Optional[bool] = None


class DealTracker:
    """Track and analyze deal prediction accuracy."""
    
    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = data_file or DEAL_TRACKER_FILE
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
    
    def record_prediction(self, prediction: DealPrediction):
        """Record a new price prediction."""
        record = asdict(prediction)
        with open(self.data_file, 'a') as f:
            f.write(json.dumps(record) + '\n')
        logger.debug(f"Recorded prediction for '{prediction.item_title[:40]}': ${prediction.predicted_price:.0f}")
    
    def record_sale(self, item_url: str, actual_price: float, sale_date: str = None):
        """Update a prediction with actual sale price."""
        if not self.data_file.exists():
            logger.warning("No predictions to update")
            return
        
        # Read all records
        records = []
        updated = False
        
        with open(self.data_file, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                
                # Find matching prediction
                if record.get('item_url') == item_url and record.get('actual_sale_price') is None:
                    # Calculate metrics
                    predicted = record['predicted_price']
                    error_pct = ((actual_price - predicted) / predicted) * 100
                    
                    record['actual_sale_price'] = actual_price
                    record['sale_date'] = sale_date or datetime.now().isoformat()
                    record['prediction_error_pct'] = error_pct
                    record['within_10pct'] = abs(error_pct) <= 10
                    record['within_20pct'] = abs(error_pct) <= 20
                    
                    # Calculate days to sell
                    pred_date = datetime.fromisoformat(record['timestamp'])
                    sell_date = datetime.fromisoformat(record['sale_date'])
                    record['days_to_sell'] = (sell_date - pred_date).days
                    
                    updated = True
                    logger.info(f"Updated sale for '{record['item_title'][:40]}': "
                               f"predicted ${predicted:.0f}, sold ${actual_price:.0f}, "
                               f"error {error_pct:+.1f}%")
                
                records.append(record)
        
        # Write back
        if updated:
            with open(self.data_file, 'w') as f:
                for record in records:
                    f.write(json.dumps(record) + '\n')
    
    def get_accuracy_report(self, days: int = 30) -> Dict:
        """Generate accuracy report for recent predictions."""
        if not self.data_file.exists():
            return {"error": "No data available"}
        
        cutoff = datetime.now() - timedelta(days=days)
        
        # Load predictions
        predictions = []
        with open(self.data_file, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                pred_date = datetime.fromisoformat(record['timestamp'])
                if pred_date >= cutoff:
                    predictions.append(record)
        
        # Separate by method
        standard_preds = [p for p in predictions if p['prediction_method'] == 'standard']
        hyper_preds = [p for p in predictions if p['prediction_method'] == 'hyper']
        
        # Calculate metrics
        report = {
            'period_days': days,
            'total_predictions': len(predictions),
            'standard': self._calc_metrics(standard_preds),
            'hyper': self._calc_metrics(hyper_preds),
        }
        
        # CV-based analysis for hyper predictions
        hyper_with_cv = [p for p in hyper_preds if p.get('cv') is not None]
        if hyper_with_cv:
            high_conf = [p for p in hyper_with_cv if p.get('confidence_level') == 'high']
            med_conf = [p for p in hyper_with_cv if p.get('confidence_level') == 'medium']
            low_conf = [p for p in hyper_with_cv if p.get('confidence_level') == 'low']
            
            report['hyper_by_confidence'] = {
                'high_cv<0.5': self._calc_metrics(high_conf),
                'medium_cv0.5-1': self._calc_metrics(med_conf),
                'low_cv>1': self._calc_metrics(low_conf),
            }
        
        return report
    
    def _calc_metrics(self, predictions: List[Dict]) -> Dict:
        """Calculate accuracy metrics for a set of predictions."""
        if not predictions:
            return {'count': 0}
        
        # Only include predictions with actual outcomes
        completed = [p for p in predictions if p.get('actual_sale_price') is not None]
        
        if not completed:
            return {
                'count': len(predictions),
                'completed': 0,
                'pending': len(predictions),
            }
        
        errors = [p['prediction_error_pct'] for p in completed]
        abs_errors = [abs(e) for e in errors]
        
        return {
            'count': len(predictions),
            'completed': len(completed),
            'pending': len(predictions) - len(completed),
            'mae': sum(abs_errors) / len(abs_errors),  # Mean Absolute Error
            'rmse': (sum(e**2 for e in errors) / len(errors)) ** 0.5,  # Root Mean Square Error
            'mpe': sum(errors) / len(errors),  # Mean Percentage Error (bias)
            'within_10pct': sum(1 for p in completed if p.get('within_10pct')) / len(completed),
            'within_20pct': sum(1 for p in completed if p.get('within_20pct')) / len(completed),
            'avg_days_to_sell': sum(p['days_to_sell'] for p in completed if p.get('days_to_sell')) / len(completed) if any(p.get('days_to_sell') for p in completed) else None,
        }
    
    def print_report(self, days: int = 30):
        """Print formatted accuracy report."""
        report = self.get_accuracy_report(days)
        
        print(f"\n{'='*70}")
        print(f"DEAL PREDICTION ACCURACY REPORT (Last {days} days)")
        print(f"{'='*70}")
        
        if 'error' in report:
            print(f"\n{report['error']}")
            return
        
        print(f"\nTotal Predictions: {report['total_predictions']}")
        
        # Standard pricing
        std = report.get('standard', {})
        if std.get('count', 0) > 0:
            print(f"\n📊 STANDARD PRICING:")
            print(f"  Predictions: {std['count']}")
            if std.get('completed', 0) > 0:
                print(f"  Completed:   {std['completed']}")
                print(f"  MAE:         {std['mae']:.1f}%")
                print(f"  Within 10%:  {std['within_10pct']*100:.0f}%")
                print(f"  Within 20%:  {std['within_20pct']*100:.0f}%")
        
        # Hyper pricing
        hyp = report.get('hyper', {})
        if hyp.get('count', 0) > 0:
            print(f"\n💎 HYPER PRICING:")
            print(f"  Predictions: {hyp['count']}")
            if hyp.get('completed', 0) > 0:
                print(f"  Completed:   {hyp['completed']}")
                print(f"  MAE:         {hyp['mae']:.1f}%")
                print(f"  Within 10%:  {hyp['within_10pct']*100:.0f}%")
                print(f"  Within 20%:  {hyp['within_20pct']*100:.0f}%")
            
            # By confidence level
            by_conf = report.get('hyper_by_confidence', {})
            if by_conf:
                print(f"\n  By Confidence Level:")
                for level, metrics in by_conf.items():
                    if metrics.get('completed', 0) > 0:
                        print(f"    {level}: {metrics['completed']} deals, MAE={metrics['mae']:.1f}%")
        
        print(f"\n{'='*70}")


# Singleton instance
tracker = DealTracker()


# Convenience functions
def record_prediction(*args, **kwargs):
    """Record a prediction."""
    tracker.record_prediction(*args, **kwargs)

def record_sale(*args, **kwargs):
    """Record an actual sale."""
    tracker.record_sale(*args, **kwargs)

def print_accuracy_report(*args, **kwargs):
    """Print accuracy report."""
    tracker.print_report(*args, **kwargs)


if __name__ == "__main__":
    # Demo/test
    print("Deal Tracker Test")
    print("="*70)
    
    # Create test predictions
    test_tracker = DealTracker()
    
    # Record some test predictions
    from datetime import datetime, timedelta
    
    for i in range(5):
        pred = DealPrediction(
            timestamp=(datetime.now() - timedelta(days=i)).isoformat(),
            query="chrome hearts ring",
            item_title=f"Test Chrome Hearts Ring {i}",
            item_url=f"https://example.com/item{i}",
            predicted_price=500 + i * 100,
            prediction_method="hyper" if i % 2 == 0 else "standard",
            cv=0.6 if i % 2 == 0 else None,
            confidence_level="medium" if i % 2 == 0 else None,
            num_comps=20,
        )
        test_tracker.record_prediction(pred)
    
    # Record some sales
    test_tracker.record_sale("https://example.com/item0", 520)
    test_tracker.record_sale("https://example.com/item1", 480)
    test_tracker.record_sale("https://example.com/item2", 650)
    
    # Print report
    test_tracker.print_report(days=30)
    
    print("\nTest complete!")

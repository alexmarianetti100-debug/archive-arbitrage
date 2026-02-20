"""
Purchase Protection & Escrow System

Provides buyer protection for high-risk transactions:
- Escrow service for high-value items
- Return/dispute workflow
- Insurance integration (future)
"""

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict


class TransactionStatus(Enum):
    PENDING_PAYMENT = "pending_payment"
    IN_ESCROW = "in_escrow"
    SHIPPED_TO_BUYER = "shipped_to_buyer"
    DELIVERED = "delivered"
    AUTHENTICATED = "authenticated"
    DISPUTED = "disputed"
    COMPLETED = "completed"
    REFUNDED = "refunded"


class DisputeReason(Enum):
    NOT_AUTHENTIC = "not_authentic"
    NOT_AS_DESCRIBED = "not_as_described"
    DAMAGED = "damaged"
    NEVER_RECEIVED = "never_received"
    WRONG_ITEM = "wrong_item"


@dataclass
class PurchaseTransaction:
    """A protected purchase transaction."""
    id: str
    item_id: str
    item_title: str
    item_price: float
    platform: str
    seller_id: str
    seller_name: str
    
    # Financials
    purchase_price: float
    escrow_amount: float
    fees: float
    
    # Status
    status: str
    created_at: str
    
    # Authentication
    auth_required: bool
    auth_result: Optional[str] = None
    auth_confidence: Optional[float] = None
    
    # Shipping
    tracking_number: Optional[str] = None
    shipped_at: Optional[str] = None
    delivered_at: Optional[str] = None
    
    # Dispute
    disputed: bool = False
    dispute_reason: Optional[str] = None
    dispute_notes: Optional[str] = None
    resolved_at: Optional[str] = None
    resolution: Optional[str] = None
    
    # Timestamps
    completed_at: Optional[str] = None
    refunded_at: Optional[str] = None


class PurchaseProtection:
    """
    Manage purchase protection and escrow workflow.
    
    For MVP, tracks transactions locally. Integrate with Stripe/PayPal for real escrow.
    """
    
    DATA_FILE = Path(__file__).parent.parent / "data" / "protected_transactions.json"
    
    # Escrow thresholds
    ESCROW_THRESHOLD = 500  # $500+
    REQUIRED_AUTH_THRESHOLD = 1000  # $1000+ requires auth
    
    # Holding periods
    AUTHENTICATION_PERIOD_DAYS = 3  # Days to authenticate after receipt
    DISPUTE_WINDOW_DAYS = 7  # Days to dispute after delivery
    
    def __init__(self):
        self.transactions: Dict[str, PurchaseTransaction] = {}
        self._load_data()
    
    def _load_data(self):
        """Load transaction data from disk."""
        if self.DATA_FILE.exists():
            try:
                with open(self.DATA_FILE, 'r') as f:
                    data = json.load(f)
                    for txn_id, txn_data in data.items():
                        self.transactions[txn_id] = PurchaseTransaction(**txn_data)
            except Exception as e:
                print(f"Error loading transaction data: {e}")
    
    def _save_data(self):
        """Save transaction data to disk."""
        self.DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.DATA_FILE, 'w') as f:
            data = {k: asdict(v) for k, v in self.transactions.items()}
            json.dump(data, f, indent=2)
    
    def should_use_escrow(self, price: float, seller_trust_score: float) -> bool:
        """
        Determine if escrow is recommended for this purchase.
        
        Args:
            price: Item price
            seller_trust_score: 0.0 - 1.0
        """
        # Always escrow high-value
        if price >= self.ESCROW_THRESHOLD:
            return True
        
        # Escrow if seller is untrusted
        if seller_trust_score < 0.5:
            return True
        
        # Escrow if price is moderate and seller is new
        if price >= 200 and seller_trust_score < 0.7:
            return True
        
        return False
    
    def requires_authentication(self, price: float, brand: str) -> bool:
        """Determine if item must be authenticated before completing purchase."""
        if price >= self.REQUIRED_AUTH_THRESHOLD:
            return True
        
        # High-risk brands always authenticated
        high_risk_brands = ["chrome hearts", "hermes", "chanel", "louis vuitton"]
        if any(b in brand.lower() for b in high_risk_brands):
            return True
        
        return False
    
    def create_transaction(
        self,
        item_data: dict,
        seller_trust_score: float,
        auth_result: Optional[dict] = None,
    ) -> tuple[str, dict]:
        """
        Create a protected purchase transaction.
        
        Returns (transaction_id, instructions).
        """
        txn_id = str(uuid.uuid4())[:8]
        
        price = item_data.get('price', 0)
        brand = item_data.get('brand', '')
        
        # Determine protection level
        use_escrow = self.should_use_escrow(price, seller_trust_score)
        requires_auth = self.requires_authentication(price, brand)
        
        # If auth required but not done, don't allow purchase
        if requires_auth and (not auth_result or auth_result.get('decision') != 'authentic'):
            return None, {
                "allowed": False,
                "reason": "Authentication required for this item",
                "next_step": "Submit for expert review",
            }
        
        txn = PurchaseTransaction(
            id=txn_id,
            item_id=item_data.get('source_id', ''),
            item_title=item_data.get('title', ''),
            item_price=price,
            platform=item_data.get('source', ''),
            seller_id=item_data.get('seller_id', ''),
            seller_name=item_data.get('seller', ''),
            purchase_price=price,
            escrow_amount=price if use_escrow else 0,
            fees=price * 0.05 if use_escrow else 0,  # 5% escrow fee
            status=TransactionStatus.PENDING_PAYMENT.value,
            created_at=datetime.now().isoformat(),
            auth_required=requires_auth,
            auth_result=auth_result.get('decision') if auth_result else None,
            auth_confidence=auth_result.get('confidence') if auth_result else None,
        )
        
        self.transactions[txn_id] = txn
        self._save_data()
        
        instructions = {
            "allowed": True,
            "transaction_id": txn_id,
            "use_escrow": use_escrow,
            "escrow_amount": txn.escrow_amount if use_escrow else 0,
            "fees": txn.fees,
            "next_steps": [],
        }
        
        if use_escrow:
            instructions["next_steps"] = [
                "1. Send payment to escrow",
                "2. Seller ships item to you",
                f"3. You have {self.AUTHENTICATION_PERIOD_DAYS} days to authenticate",
                "4. Release funds to seller or dispute",
            ]
        else:
            instructions["next_steps"] = [
                "1. Purchase directly from platform",
                f"2. You have {self.DISPUTE_WINDOW_DAYS} days to dispute if issues",
            ]
        
        return txn_id, instructions
    
    def record_payment(self, txn_id: str):
        """Record that buyer has sent payment."""
        if txn_id in self.transactions:
            txn = self.transactions[txn_id]
            txn.status = TransactionStatus.IN_ESCROW.value
            self._save_data()
    
    def record_shipment(self, txn_id: str, tracking_number: str):
        """Record that seller has shipped."""
        if txn_id in self.transactions:
            txn = self.transactions[txn_id]
            txn.tracking_number = tracking_number
            txn.shipped_at = datetime.now().isoformat()
            txn.status = TransactionStatus.SHIPPED_TO_BUYER.value
            self._save_data()
    
    def record_delivery(self, txn_id: str):
        """Record that item was delivered."""
        if txn_id in self.transactions:
            txn = self.transactions[txn_id]
            txn.delivered_at = datetime.now().isoformat()
            txn.status = TransactionStatus.DELIVERED.value
            self._save_data()
    
    def authenticate_received(self, txn_id: str, is_authentic: bool, notes: str = ""):
        """Record buyer's authentication of received item."""
        if txn_id not in self.transactions:
            return
        
        txn = self.transactions[txn_id]
        
        if is_authentic:
            txn.status = TransactionStatus.AUTHENTICATED.value
            txn.auth_result = "authentic"
            txn.completed_at = datetime.now().isoformat()
            # In real system, release escrow to seller here
        else:
            txn.disputed = True
            txn.dispute_reason = DisputeReason.NOT_AUTHENTIC.value
            txn.dispute_notes = notes
            txn.status = TransactionStatus.DISPUTED.value
        
        self._save_data()
    
    def open_dispute(
        self,
        txn_id: str,
        reason: str,
        notes: str,
        evidence_photos: List[str] = None,
    ) -> dict:
        """
        Open a dispute on a transaction.
        
        Returns dispute info and next steps.
        """
        if txn_id not in self.transactions:
            return {"error": "Transaction not found"}
        
        txn = self.transactions[txn_id]
        
        # Check dispute window
        if txn.delivered_at:
            delivered = datetime.fromisoformat(txn.delivered_at)
            window_end = delivered + timedelta(days=self.DISPUTE_WINDOW_DAYS)
            if datetime.now() > window_end:
                return {
                    "error": f"Dispute window closed ({self.DISPUTE_WINDOW_DAYS} days from delivery)",
                }
        
        txn.disputed = True
        txn.dispute_reason = reason
        txn.dispute_notes = notes
        txn.status = TransactionStatus.DISPUTED.value
        self._save_data()
        
        return {
            "dispute_id": f"DSP-{txn_id}",
            "status": "opened",
            "next_steps": [
                "1. Gather evidence (photos, screenshots)",
                "2. Contact seller through platform",
                "3. If unresolved, escalate to platform dispute resolution",
                "4. For escrow: funds held pending resolution",
            ],
            "estimated_resolution": "3-5 business days",
        }
    
    def resolve_dispute(self, txn_id: str, resolution: str, refund_amount: float = 0):
        """Resolve a dispute."""
        if txn_id not in self.transactions:
            return
        
        txn = self.transactions[txn_id]
        txn.resolution = resolution
        txn.resolved_at = datetime.now().isoformat()
        
        if resolution == "refund":
            txn.status = TransactionStatus.REFUNDED.value
            txn.refunded_at = datetime.now().isoformat()
        elif resolution == "partial_refund":
            txn.status = TransactionStatus.COMPLETED.value
            # Record partial refund details
        elif resolution == "no_refund":
            txn.status = TransactionStatus.COMPLETED.value
            txn.completed_at = datetime.now().isoformat()
        
        self._save_data()
    
    def get_transaction(self, txn_id: str) -> Optional[dict]:
        """Get transaction details."""
        if txn_id not in self.transactions:
            return None
        
        txn = self.transactions[txn_id]
        return {
            "id": txn.id,
            "item": txn.item_title,
            "price": txn.purchase_price,
            "status": txn.status,
            "escrow": txn.escrow_amount > 0,
            "disputed": txn.disputed,
            "days_in_escrow": self._days_in_status(txn),
        }
    
    def _days_in_status(self, txn: PurchaseTransaction) -> int:
        """Calculate days since status change."""
        created = datetime.fromisoformat(txn.created_at)
        return (datetime.now() - created).days
    
    def get_buyer_dashboard(self) -> dict:
        """Get summary of all buyer transactions."""
        active = []
        completed = []
        disputed = []
        
        total_spent = 0
        total_refunded = 0
        
        for txn in self.transactions.values():
            summary = {
                "id": txn.id,
                "item": txn.item_title[:50],
                "price": txn.purchase_price,
                "status": txn.status,
            }
            
            if txn.status in [TransactionStatus.COMPLETED.value, TransactionStatus.AUTHENTICATED.value]:
                completed.append(summary)
                total_spent += txn.purchase_price
            elif txn.status == TransactionStatus.DISPUTED.value:
                disputed.append(summary)
            else:
                active.append(summary)
        
        return {
            "active_purchases": active,
            "completed_purchases": completed,
            "disputed": disputed,
            "total_spent": total_spent,
            "total_refunded": total_refunded,
            "protection_rate": len([t for t in self.transactions.values() if t.escrow_amount > 0]) / len(self.transactions) if self.transactions else 0,
        }
    
    def calculate_protection_recommendation(
        self,
        price: float,
        brand: str,
        seller_trust: float,
    ) -> dict:
        """Generate protection recommendation for a potential purchase."""
        
        risk_factors = []
        protection_methods = []
        
        # Price risk
        if price > 1000:
            risk_factors.append("High-value item ($1000+)")
            protection_methods.append("Escrow required")
            protection_methods.append("Expert authentication mandatory")
        elif price > 500:
            risk_factors.append("Moderate-high value ($500+)")
            protection_methods.append("Escrow recommended")
        
        # Brand risk
        high_risk_brands = ["chrome hearts", "hermes", "chanel", "louis vuitton", "gucci"]
        if any(b in brand.lower() for b in high_risk_brands):
            risk_factors.append("High-fraud brand")
            protection_methods.append("Expert authentication")
        
        # Seller risk
        if seller_trust < 0.4:
            risk_factors.append("Unverified seller")
            protection_methods.append("Escrow mandatory")
        elif seller_trust < 0.7:
            risk_factors.append("Limited seller history")
            protection_methods.append("Escrow recommended")
        
        # Calculate overall risk
        risk_score = len(risk_factors) * 0.2
        if price > 1000:
            risk_score += 0.3
        if seller_trust < 0.5:
            risk_score += 0.3
        
        risk_level = "low"
        if risk_score > 0.7:
            risk_level = "high"
        elif risk_score > 0.4:
            risk_level = "medium"
        
        return {
            "risk_level": risk_level,
            "risk_score": min(1.0, risk_score),
            "risk_factors": risk_factors,
            "recommended_protection": protection_methods,
            "escrow_recommended": price > 500 or seller_trust < 0.6,
            "auth_recommended": price > 200 or any(b in brand.lower() for b in high_risk_brands),
        }

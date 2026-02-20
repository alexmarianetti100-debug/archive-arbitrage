"""
Expert Review Workflow

Queue items for manual authentication when automated checks are inconclusive.

Features:
- Submit items for expert review
- Track review status
- Manage reviewer assignments
- Photo request workflows
- Integration with Legit Check API (future)
"""

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict


class ReviewStatus(Enum):
    PENDING = "pending"
    PHOTOS_REQUESTED = "photos_requested"
    IN_REVIEW = "in_review"
    AUTHENTIC = "authentic"
    REPLICA = "replica"
    UNABLE_TO_VERIFY = "unable_to_verify"


class ReviewPriority(Enum):
    LOW = 1      # < $200
    MEDIUM = 2   # $200-500
    HIGH = 3     # $500-1000
    URGENT = 4   # > $1000


@dataclass
class ExpertReview:
    """An expert review request."""
    id: str
    item_data: dict
    initial_result: dict  # Automated check results
    
    # Status
    status: str
    priority: int
    
    # Timestamps
    created_at: str
    assigned_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # Assignment
    assigned_to: Optional[str] = None
    
    # Review details
    reviewer_notes: Optional[str] = None
    verification_points: List[str] = None
    requested_photos: List[str] = None
    submitted_photos: List[str] = None
    
    # Result
    final_decision: Optional[str] = None
    confidence: Optional[float] = None
    
    def __post_init__(self):
        if self.verification_points is None:
            self.verification_points = []
        if self.requested_photos is None:
            self.requested_photos = []
        if self.submitted_photos is None:
            self.submitted_photos = []


class ExpertReviewQueue:
    """
    Manage queue of items awaiting expert authentication.
    
    For MVP, stores in JSON file. Scale to database later.
    """
    
    DATA_FILE = Path(__file__).parent.parent / "data" / "expert_reviews.json"
    
    # Authentication points by category
    VERIFICATION_CHECKLIST = {
        "footwear": [
            "Overall shape and proportions",
            "Toe box stitching pattern",
            "Heel counter construction",
            "Insole branding and font",
            "Size tag placement and text",
            "Sole texture and branding",
            "Lace quality and aglets",
            "Box label and SKU",
        ],
        "bags": [
            "Logo placement and font",
            "Hardware engraving quality",
            "Stitching pattern and consistency",
            "Interior label and date code",
            "Zipper brand and smoothness",
            "Leather texture and smell",
            "Dust bag quality",
            "Authentication card",
        ],
        "clothing": [
            "Neck tag stitching and font",
            "Wash tag text and symbols",
            "Hem stitching pattern",
            "Hardware (buttons, zippers)",
            "Material texture",
            "Interior labels",
            "Season/collection tags",
        ],
        "accessories": [
            "Engraving clarity and depth",
            "Material weight and feel",
            "Packaging quality",
            "Certificate of authenticity",
            "Serial numbers",
        ],
    }
    
    def __init__(self):
        self.reviews: Dict[str, ExpertReview] = {}
        self._load_data()
    
    def _load_data(self):
        """Load review data from disk."""
        if self.DATA_FILE.exists():
            try:
                with open(self.DATA_FILE, 'r') as f:
                    data = json.load(f)
                    for review_id, review_data in data.items():
                        self.reviews[review_id] = ExpertReview(**review_data)
            except Exception as e:
                print(f"Error loading review data: {e}")
    
    def _save_data(self):
        """Save review data to disk."""
        self.DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.DATA_FILE, 'w') as f:
            data = {k: asdict(v) for k, v in self.reviews.items()}
            json.dump(data, f, indent=2)
    
    def submit(self, item_data: dict, initial_result: dict) -> str:
        """
        Submit an item for expert review.
        
        Returns review ID for tracking.
        """
        review_id = str(uuid.uuid4())[:8]
        
        # Determine priority based on price
        price = item_data.get('price', 0)
        if price > 1000:
            priority = ReviewPriority.URGENT.value
        elif price > 500:
            priority = ReviewPriority.HIGH.value
        elif price > 200:
            priority = ReviewPriority.MEDIUM.value
        else:
            priority = ReviewPriority.LOW.value
        
        # Determine required photos
        category = self._detect_category(item_data.get('title', ''))
        required_photos = self._get_required_photos(category)
        
        # Check if photos already provided
        existing_photos = item_data.get('images', [])
        missing_photos = self._identify_missing_photos(existing_photos, required_photos)
        
        # Set initial status
        if missing_photos:
            status = ReviewStatus.PHOTOS_REQUESTED.value
        else:
            status = ReviewStatus.PENDING.value
        
        review = ExpertReview(
            id=review_id,
            item_data=item_data,
            initial_result=initial_result,
            status=status,
            priority=priority,
            created_at=datetime.now().isoformat(),
            requested_photos=missing_photos,
            submitted_photos=existing_photos,
        )
        
        self.reviews[review_id] = review
        self._save_data()
        
        return review_id
    
    def get_status(self, review_id: str) -> Optional[dict]:
        """Get status of a review."""
        if review_id not in self.reviews:
            return None
        
        review = self.reviews[review_id]
        return {
            "id": review.id,
            "status": review.status,
            "priority": review.priority,
            "created_at": review.created_at,
            "assigned_to": review.assigned_to,
            "requested_photos": review.requested_photos,
            "final_decision": review.final_decision,
            "estimated_wait": self._estimate_wait_time(review),
        }
    
    def _estimate_wait_time(self, review: ExpertReview) -> int:
        """Estimate minutes until review completion."""
        if review.status in [ReviewStatus.AUTHENTIC.value, ReviewStatus.REPLICA.value]:
            return 0
        
        # Base estimate on priority and queue position
        base_time = 30  # 30 min base
        
        if review.priority == ReviewPriority.URGENT.value:
            base_time = 15
        elif review.priority == ReviewPriority.LOW.value:
            base_time = 120
        
        # Add time for photo requests
        if review.status == ReviewStatus.PHOTOS_REQUESTED.value:
            base_time += 60  # Extra hour for seller to respond
        
        return base_time
    
    def assign_to_expert(self, review_id: str, expert_id: str):
        """Assign a review to an expert."""
        if review_id in self.reviews:
            review = self.reviews[review_id]
            review.assigned_to = expert_id
            review.assigned_at = datetime.now().isoformat()
            review.status = ReviewStatus.IN_REVIEW.value
            self._save_data()
    
    def submit_photos(self, review_id: str, photo_urls: List[str]):
        """Submit additional photos for review."""
        if review_id in self.reviews:
            review = self.reviews[review_id]
            review.submitted_photos.extend(photo_urls)
            
            # Check if all required photos now provided
            still_missing = self._identify_missing_photos(
                review.submitted_photos,
                review.requested_photos
            )
            
            if not still_missing:
                review.status = ReviewStatus.PENDING.value
                review.requested_photos = []
            
            self._save_data()
    
    def complete_review(
        self,
        review_id: str,
        decision: str,
        confidence: float,
        notes: str,
        verification_points: List[str],
    ):
        """Mark review as complete with final decision."""
        if review_id in self.reviews:
            review = self.reviews[review_id]
            review.status = decision
            review.final_decision = decision
            review.confidence = confidence
            review.reviewer_notes = notes
            review.verification_points = verification_points
            review.completed_at = datetime.now().isoformat()
            self._save_data()
    
    def get_pending_reviews(self, priority_min: int = 1) -> List[ExpertReview]:
        """Get all pending reviews above priority threshold."""
        pending = [
            r for r in self.reviews.values()
            if r.status in [ReviewStatus.PENDING.value, ReviewStatus.PHOTOS_REQUESTED.value]
            and r.priority >= priority_min
        ]
        return sorted(pending, key=lambda r: (-r.priority, r.created_at))
    
    def get_queue_stats(self) -> dict:
        """Get statistics about the review queue."""
        stats = {
            "total": len(self.reviews),
            "pending": 0,
            "in_review": 0,
            "completed": 0,
            "avg_review_time_minutes": 0,
        }
        
        total_time = 0
        completed_count = 0
        
        for review in self.reviews.values():
            if review.status == ReviewStatus.PENDING.value:
                stats["pending"] += 1
            elif review.status == ReviewStatus.IN_REVIEW.value:
                stats["in_review"] += 1
            elif review.status in [ReviewStatus.AUTHENTIC.value, ReviewStatus.REPLICA.value]:
                stats["completed"] += 1
                if review.assigned_at and review.completed_at:
                    assigned = datetime.fromisoformat(review.assigned_at)
                    completed = datetime.fromisoformat(review.completed_at)
                    total_time += (completed - assigned).total_seconds() / 60
                    completed_count += 1
        
        if completed_count > 0:
            stats["avg_review_time_minutes"] = total_time / completed_count
        
        return stats
    
    def _detect_category(self, title: str) -> str:
        """Detect item category from title."""
        title_lower = title.lower()
        
        if any(word in title_lower for word in ["shoe", "sneaker", "boot", "footwear"]):
            return "footwear"
        elif any(word in title_lower for word in ["bag", "tote", "backpack", "purse"]):
            return "bags"
        elif any(word in title_lower for word in ["shirt", "jacket", "pants", "hoodie", "sweater"]):
            return "clothing"
        else:
            return "accessories"
    
    def _get_required_photos(self, category: str) -> List[str]:
        """Get list of required photos for category."""
        return self.VERIFICATION_CHECKLIST.get(category, self.VERIFICATION_CHECKLIST["accessories"])
    
    def _identify_missing_photos(self, existing: List[str], required: List[str]) -> List[str]:
        """Identify which required photos are missing."""
        # Simplified - in production, would analyze actual image content
        if len(existing) >= 5:
            return []  # Assume sufficient if 5+ photos
        elif len(existing) >= 3:
            return required[3:]  # Missing detailed shots
        else:
            return required[1:]  # Missing most details
    
    def generate_review_request_message(self, review_id: str) -> str:
        """Generate message to seller requesting review/photos."""
        if review_id not in self.reviews:
            return ""
        
        review = self.reviews[review_id]
        item = review.item_data
        
        message = f"""Hi! I'm interested in your {item.get('title', 'item')}. 

To ensure authenticity before purchasing, could you please provide a few additional photos?

Specifically, I need to see:
"""
        for photo in review.requested_photos[:5]:
            message += f"- {photo}\n"
        
        message += """
These photos help verify the item is authentic. I'm ready to purchase once verified!

Thanks!
"""
        return message

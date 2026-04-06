"""
Content queue manager for auto-generated marketing posts.

Manages the lifecycle: pending → approved → posted
Stores metadata alongside images for scheduling and tracking.

Queue structure:
    queue/pending/   — Auto-generated, awaiting review
    queue/approved/  — Reviewed and approved for posting
    queue/posted/    — Archive of posted content

Each post is a pair: {id}.jpg + {id}.json (metadata)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("auto_content.queue")

QUEUE_ROOT = Path(__file__).parent / "queue"
PENDING_DIR = QUEUE_ROOT / "pending"
APPROVED_DIR = QUEUE_ROOT / "approved"
POSTED_DIR = QUEUE_ROOT / "posted"

for d in [PENDING_DIR, APPROVED_DIR, POSTED_DIR]:
    d.mkdir(parents=True, exist_ok=True)


@dataclass
class PostMetadata:
    """Metadata stored alongside each queued post."""
    id: str                              # Unique post ID (matches filename)
    post_type: str                       # "deal", "weekly_recap", "market_intel", "editorial"
    caption: str                         # Ready-to-post caption
    image_path: str                      # Path to the image file
    status: str = "pending"              # pending, approved, posted, skipped
    created_at: str = ""                 # ISO timestamp
    scheduled_for: Optional[str] = None  # ISO timestamp for scheduled posting
    posted_at: Optional[str] = None      # ISO timestamp when actually posted
    platform: str = "instagram"          # Target platform

    # Deal-specific metadata (for tracking)
    brand: str = ""
    profit: float = 0.0
    fire_level: int = 0
    source_url: str = ""
    tier: str = ""

    # Posting hints
    hashtag_set: int = 0                 # Which hashtag rotation was used
    content_pillar: str = ""             # "deal_breakdown", "market_intel", "educational", "social_proof"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PostMetadata":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in known_fields}
        return cls(**filtered)


def _meta_path(image_path: str) -> str:
    """Get the metadata JSON path for an image."""
    return str(Path(image_path).with_suffix(".json"))


def save_to_queue(
    image_path: str,
    caption: str,
    post_type: str = "deal",
    brand: str = "",
    profit: float = 0.0,
    fire_level: int = 0,
    source_url: str = "",
    tier: str = "",
    content_pillar: str = "deal_breakdown",
    scheduled_for: Optional[str] = None,
) -> PostMetadata:
    """Save a generated post to the pending queue with metadata."""
    post_id = Path(image_path).stem
    meta = PostMetadata(
        id=post_id,
        post_type=post_type,
        caption=caption,
        image_path=image_path,
        status="pending",
        created_at=datetime.now().isoformat(),
        scheduled_for=scheduled_for,
        brand=brand,
        profit=profit,
        fire_level=fire_level,
        source_url=source_url,
        tier=tier,
        content_pillar=content_pillar,
    )

    meta_file = _meta_path(image_path)
    with open(meta_file, "w") as f:
        json.dump(meta.to_dict(), f, indent=2)

    logger.info(f"Queued post: {post_id} ({post_type}, {brand})")
    return meta


def list_queue(status: str = "pending") -> List[PostMetadata]:
    """List all posts in a given status queue."""
    dir_map = {"pending": PENDING_DIR, "approved": APPROVED_DIR, "posted": POSTED_DIR}
    target_dir = dir_map.get(status, PENDING_DIR)

    posts = []
    for json_file in sorted(target_dir.glob("*.json")):
        try:
            with open(json_file) as f:
                data = json.load(f)
            posts.append(PostMetadata.from_dict(data))
        except Exception as e:
            logger.warning(f"Failed to load queue entry {json_file}: {e}")

    return posts


def approve_post(post_id: str) -> Optional[PostMetadata]:
    """Move a post from pending to approved."""
    return _move_post(post_id, PENDING_DIR, APPROVED_DIR, "approved")


def mark_posted(post_id: str) -> Optional[PostMetadata]:
    """Move a post from approved to posted."""
    return _move_post(post_id, APPROVED_DIR, POSTED_DIR, "posted")


def skip_post(post_id: str) -> Optional[PostMetadata]:
    """Mark a pending post as skipped (delete from queue)."""
    for ext in [".jpg", ".png", ".json"]:
        path = PENDING_DIR / f"{post_id}{ext}"
        if path.exists():
            path.unlink()
    logger.info(f"Skipped and removed post: {post_id}")
    return None


def _move_post(post_id: str, from_dir: Path, to_dir: Path, new_status: str) -> Optional[PostMetadata]:
    """Move a post between queue directories."""
    moved_meta = None

    for ext in [".jpg", ".png", ".json"]:
        src = from_dir / f"{post_id}{ext}"
        dst = to_dir / f"{post_id}{ext}"
        if src.exists():
            shutil.move(str(src), str(dst))

            if ext == ".json":
                with open(dst) as f:
                    data = json.load(f)
                data["status"] = new_status
                data["image_path"] = str(to_dir / f"{post_id}.jpg")
                if new_status == "posted":
                    data["posted_at"] = datetime.now().isoformat()
                with open(dst, "w") as f:
                    json.dump(data, f, indent=2)
                moved_meta = PostMetadata.from_dict(data)

    if moved_meta:
        logger.info(f"Moved post {post_id} to {new_status}")
    return moved_meta


def get_queue_stats() -> dict:
    """Get counts for each queue status."""
    return {
        "pending": len(list(PENDING_DIR.glob("*.json"))),
        "approved": len(list(APPROVED_DIR.glob("*.json"))),
        "posted": len(list(POSTED_DIR.glob("*.json"))),
    }


def get_next_approved() -> Optional[PostMetadata]:
    """Get the next approved post ready for publishing (oldest first)."""
    posts = list_queue("approved")
    if not posts:
        return None

    # Sort by created_at (oldest first)
    posts.sort(key=lambda p: p.created_at)

    # If any are scheduled, check if it's time
    now = datetime.now().isoformat()
    for post in posts:
        if post.scheduled_for and post.scheduled_for > now:
            continue
        return post

    # Fall back to first post if none are due yet
    return posts[0] if posts else None

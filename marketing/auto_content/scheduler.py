"""
Social media posting scheduler.

Manages the cadence of auto-generated content:
- Max 2 posts per day (IG algorithm penalizes overposting)
- Optimal posting windows (archive fashion audience)
- Approval queue — nothing posts without review
- Content variety enforcement (don't post 3 deal cards in a row)
- Supports manual and auto-approve modes

Posting flow:
    Pipeline → deal_card.py → queue/pending/
    You review → approve → queue/approved/
    Scheduler picks from approved → posts → queue/posted/

The scheduler does NOT directly post to Instagram (that requires
Meta Graph API credentials). Instead, it manages the queue and
outputs ready-to-post bundles (image + caption) that can be:
  1. Manually uploaded (copy-paste caption)
  2. Pushed via Meta Graph API (when credentials are configured)
  3. Pushed via Buffer/Later API (third-party scheduler)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, List

import httpx

from .content_queue import (
    PostMetadata,
    list_queue,
    get_next_approved,
    mark_posted,
    get_queue_stats,
    APPROVED_DIR,
)

logger = logging.getLogger("auto_content.scheduler")

# ── Config ──
MAX_POSTS_PER_DAY = int(os.getenv("CONTENT_MAX_POSTS_DAY", "2"))

# Optimal posting times for archive fashion audience (EST)
# Peak engagement: 12-1pm (lunch scroll), 7-9pm (evening browse)
OPTIMAL_HOURS_EST = [12, 13, 19, 20, 21]

# Meta Graph API (Instagram Business Account)
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_IG_USER_ID = os.getenv("META_IG_USER_ID", "")
META_API_ENABLED = bool(META_ACCESS_TOKEN and META_IG_USER_ID)

# Buffer API (alternative scheduler)
BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN", "")
BUFFER_PROFILE_ID = os.getenv("BUFFER_PROFILE_ID", "")
BUFFER_API_ENABLED = bool(BUFFER_ACCESS_TOKEN and BUFFER_PROFILE_ID)

# State tracking
_SCHEDULER_STATE_FILE = Path(__file__).parent / "queue" / "scheduler_state.json"


def _load_scheduler_state() -> dict:
    try:
        if _SCHEDULER_STATE_FILE.exists():
            return json.loads(_SCHEDULER_STATE_FILE.read_text())
    except Exception:
        pass
    return {"today": "", "posts_today": 0, "last_post_time": None, "post_history": []}


def _save_scheduler_state(state: dict) -> None:
    _SCHEDULER_STATE_FILE.write_text(json.dumps(state, indent=2))


def can_post_now() -> bool:
    """Check if we're within posting limits and optimal window."""
    state = _load_scheduler_state()
    today = date.today().isoformat()

    # Reset daily counter
    if state.get("today") != today:
        state = {"today": today, "posts_today": 0, "last_post_time": None, "post_history": state.get("post_history", [])}
        _save_scheduler_state(state)

    if state["posts_today"] >= MAX_POSTS_PER_DAY:
        return False

    # Minimum 4 hours between posts
    if state.get("last_post_time"):
        last = datetime.fromisoformat(state["last_post_time"])
        if (datetime.now() - last).total_seconds() < 4 * 3600:
            return False

    return True


def is_optimal_time() -> bool:
    """Check if current time is in an optimal posting window."""
    current_hour = datetime.now().hour
    return current_hour in OPTIMAL_HOURS_EST


def record_post(post_id: str, platform: str = "instagram") -> None:
    """Record that a post was published."""
    state = _load_scheduler_state()
    today = date.today().isoformat()

    if state.get("today") != today:
        state = {"today": today, "posts_today": 0, "last_post_time": None, "post_history": state.get("post_history", [])}

    state["posts_today"] = state.get("posts_today", 0) + 1
    state["last_post_time"] = datetime.now().isoformat()

    history = state.get("post_history", [])
    history.append({
        "post_id": post_id,
        "platform": platform,
        "posted_at": datetime.now().isoformat(),
    })
    state["post_history"] = history[-100:]  # Keep last 100
    _save_scheduler_state(state)


def get_next_post() -> Optional[PostMetadata]:
    """Get the next post that should be published.

    Returns None if:
    - No approved posts in queue
    - Already hit daily post limit
    - Too soon after last post
    """
    if not can_post_now():
        return None

    return get_next_approved()


def get_posting_status() -> dict:
    """Get current posting status for display."""
    state = _load_scheduler_state()
    queue_stats = get_queue_stats()

    return {
        "posts_today": state.get("posts_today", 0),
        "max_per_day": MAX_POSTS_PER_DAY,
        "can_post_now": can_post_now(),
        "is_optimal_time": is_optimal_time(),
        "last_post_time": state.get("last_post_time"),
        "queue": queue_stats,
        "meta_api_enabled": META_API_ENABLED,
        "buffer_api_enabled": BUFFER_API_ENABLED,
    }


# ── Posting backends ──

async def post_to_instagram_graph_api(post: PostMetadata) -> bool:
    """Post to Instagram via Meta Graph API.

    Requires:
    - META_ACCESS_TOKEN: Long-lived page token
    - META_IG_USER_ID: Instagram Business Account ID
    - Image must be hosted at a public URL (upload to hosting first)

    Instagram Graph API flow:
    1. Upload image → get creation_id
    2. Publish creation_id → get media_id
    """
    if not META_API_ENABLED:
        logger.warning("Meta Graph API not configured — set META_ACCESS_TOKEN and META_IG_USER_ID")
        return False

    # The Graph API requires a public URL for the image.
    # For now, log what would be posted.
    logger.info(
        f"[META API] Would post: {post.id}\n"
        f"  Image: {post.image_path}\n"
        f"  Caption: {post.caption[:100]}..."
    )

    # TODO: Implement when you have Meta API credentials:
    # 1. Upload image to a hosting service (S3, Cloudinary, etc.)
    # 2. POST to /{ig_user_id}/media with image_url + caption
    # 3. POST to /{ig_user_id}/media_publish with creation_id
    # See: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/content-publishing

    return False


async def post_to_buffer(post: PostMetadata) -> bool:
    """Post to Instagram via Buffer API (third-party scheduler).

    Buffer handles image upload and scheduling natively.
    """
    if not BUFFER_API_ENABLED:
        logger.warning("Buffer API not configured — set BUFFER_ACCESS_TOKEN and BUFFER_PROFILE_ID")
        return False

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Buffer expects multipart form with the image file
            with open(post.image_path, "rb") as img_file:
                resp = await client.post(
                    "https://api.bufferapp.com/1/updates/create.json",
                    data={
                        "access_token": BUFFER_ACCESS_TOKEN,
                        "profile_ids[]": BUFFER_PROFILE_ID,
                        "text": post.caption,
                        "now": "false",  # Queue it, don't post immediately
                    },
                    files={"media[photo]": ("post.jpg", img_file, "image/jpeg")},
                )

            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    logger.info(f"Queued to Buffer: {post.id}")
                    return True
                else:
                    logger.warning(f"Buffer API error: {data}")
            else:
                logger.warning(f"Buffer API returned {resp.status_code}: {resp.text[:200]}")

    except Exception as e:
        logger.error(f"Buffer post failed: {e}")

    return False


async def publish_next() -> Optional[str]:
    """Attempt to publish the next approved post.

    Tries backends in order: Meta Graph API → Buffer → manual flag.
    Returns the post_id if published, None otherwise.
    """
    post = get_next_post()
    if not post:
        return None

    posted = False

    if META_API_ENABLED:
        posted = await post_to_instagram_graph_api(post)

    if not posted and BUFFER_API_ENABLED:
        posted = await post_to_buffer(post)

    if posted:
        mark_posted(post.id)
        record_post(post.id)
        logger.info(f"Published: {post.id}")
        return post.id

    # No API configured — just report what's ready
    logger.info(
        f"Ready to post (manual upload needed): {post.id}\n"
        f"  Image: {post.image_path}\n"
        f"  Caption available in queue metadata"
    )
    return None


def export_for_manual_posting(post_id: Optional[str] = None) -> Optional[dict]:
    """Export a post's image path + caption for manual upload.

    If no post_id given, exports the next approved post.
    Returns dict with 'image_path' and 'caption', or None.
    """
    if post_id:
        posts = list_queue("approved")
        post = next((p for p in posts if p.id == post_id), None)
    else:
        post = get_next_approved()

    if not post:
        return None

    return {
        "post_id": post.id,
        "image_path": post.image_path,
        "caption": post.caption,
        "brand": post.brand,
        "profit": post.profit,
        "fire_level": post.fire_level,
    }

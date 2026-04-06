"""
Autonomous content scheduler — zero manual intervention.

Replaces the manual approve → upload workflow with:
1. Auto-approve content based on quality rules
2. Maintain a daily posting cadence (1 image + 1 video)
3. Enforce content variety (don't post 3 deal cards in a row)
4. Track what's been posted to avoid repeats
5. Export ready-to-post bundles for each platform

Run hourly via cron. Each run:
- Scans pending queue for new content
- Auto-approves qualifying items
- Selects today's posts based on variety rules
- Exports to platform-specific ready folders

Content variety rules:
- Never post same content type twice in a row
- Rotate: deal_card → video → market_intel → video → deal_card
- Prioritize higher-profit deals and fire-level content
- Cap at 2 posts/day for Instagram, 3/day for TikTok
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Optional

from .content_queue import (
    PostMetadata, list_queue, approve_post, mark_posted,
    get_queue_stats, PENDING_DIR, APPROVED_DIR, POSTED_DIR,
)

logger = logging.getLogger("auto_content.auto_scheduler")

STATE_FILE = Path(__file__).parent / "queue" / "auto_scheduler_state.json"
EXPORT_DIR = Path(__file__).parent / "ready_to_post"
EXPORT_IG = EXPORT_DIR / "instagram"
EXPORT_TIKTOK = EXPORT_DIR / "tiktok"

for d in [EXPORT_IG, EXPORT_TIKTOK]:
    d.mkdir(parents=True, exist_ok=True)

# ── Config ──
MAX_IG_PER_DAY = 2
MAX_TIKTOK_PER_DAY = 3
MIN_PROFIT_FOR_AUTO_APPROVE = 150
MIN_FIRE_FOR_AUTO_APPROVE = 1

# Content type rotation order
CONTENT_ROTATION = ["deal", "video", "market_intel", "video", "weekly_recap", "deal"]


def _load_state() -> dict:
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except Exception:
        pass
    return {
        "today": "",
        "ig_posted_today": 0,
        "tiktok_posted_today": 0,
        "last_content_type": "",
        "posted_ids": [],
        "history": [],
    }


def _save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _reset_daily(state: dict) -> dict:
    today = date.today().isoformat()
    if state.get("today") != today:
        state["today"] = today
        state["ig_posted_today"] = 0
        state["tiktok_posted_today"] = 0
    return state


def auto_approve_pending() -> int:
    """Auto-approve content from pending queue based on quality rules.

    Rules:
    - Deal cards: auto-approve if profit >= $150 or fire_level >= 1
    - Videos: auto-approve all (already filtered by pipeline)
    - Market intel / weekly recaps: auto-approve all
    - Explainer videos: auto-approve all

    Returns count of newly approved items.
    """
    pending = list_queue("pending")
    approved_count = 0

    for post in pending:
        should_approve = False

        if post.post_type in ("market_intel", "weekly_recap", "video"):
            should_approve = True
        elif post.post_type == "deal":
            if post.profit >= MIN_PROFIT_FOR_AUTO_APPROVE or post.fire_level >= MIN_FIRE_FOR_AUTO_APPROVE:
                should_approve = True

        if should_approve:
            approve_post(post.id)
            approved_count += 1
            logger.info(f"Auto-approved: {post.id} ({post.post_type}, ${post.profit:.0f})")

    return approved_count


def select_next_posts() -> dict:
    """Select today's posts based on variety rules and daily limits.

    Returns dict with 'instagram' and 'tiktok' lists of PostMetadata.
    """
    state = _reset_daily(_load_state())
    approved = list_queue("approved")

    if not approved:
        return {"instagram": [], "tiktok": []}

    # Sort by quality: fire_level desc, profit desc
    approved.sort(key=lambda p: (-p.fire_level, -p.profit))

    # Separate by type
    images = [p for p in approved if not p.image_path.endswith(".mp4")]
    videos = [p for p in approved if p.image_path.endswith(".mp4")]

    last_type = state.get("last_content_type", "")

    ig_picks = []
    tiktok_picks = []

    # Instagram: 1 image + 1 video (if available)
    ig_remaining = MAX_IG_PER_DAY - state["ig_posted_today"]
    if ig_remaining > 0 and images:
        # Pick an image that's different from last content type
        for img in images:
            if img.post_type != last_type or len(images) == 1:
                ig_picks.append(img)
                break
        if not ig_picks and images:
            ig_picks.append(images[0])

    if ig_remaining > 1 and videos:
        ig_picks.append(videos[0])

    # TikTok: videos only
    tiktok_remaining = MAX_TIKTOK_PER_DAY - state["tiktok_posted_today"]
    for v in videos[:tiktok_remaining]:
        if v not in ig_picks:  # Don't double-pick
            tiktok_picks.append(v)

    # If we had no unique tiktok picks, allow overlap
    if not tiktok_picks and videos:
        tiktok_picks = videos[:tiktok_remaining]

    return {"instagram": ig_picks, "tiktok": tiktok_picks}


def export_for_platform(post: PostMetadata, platform: str) -> Optional[str]:
    """Export a post's image/video + caption file to a platform-ready folder.

    Creates:
      ready_to_post/{platform}/{post_id}.jpg (or .mp4)
      ready_to_post/{platform}/{post_id}_caption.txt

    Returns the export directory path.
    """
    target_dir = EXPORT_IG if platform == "instagram" else EXPORT_TIKTOK
    target_dir.mkdir(parents=True, exist_ok=True)

    src = Path(post.image_path)
    if not src.exists():
        logger.warning(f"Source file missing: {src}")
        return None

    # Copy media file
    dst_media = target_dir / src.name
    shutil.copy2(str(src), str(dst_media))

    # Write caption file
    dst_caption = target_dir / f"{post.id}_caption.txt"
    dst_caption.write_text(post.caption)

    logger.info(f"Exported to {platform}: {src.name}")
    return str(target_dir)


def record_post_sent(post_id: str, platform: str):
    """Record that a post was sent to a platform."""
    state = _reset_daily(_load_state())

    if platform == "instagram":
        state["ig_posted_today"] = state.get("ig_posted_today", 0) + 1
    elif platform == "tiktok":
        state["tiktok_posted_today"] = state.get("tiktok_posted_today", 0) + 1

    # Track content type for variety
    approved = list_queue("approved")
    post = next((p for p in approved if p.id == post_id), None)
    if post:
        state["last_content_type"] = post.post_type

    # Move to posted
    mark_posted(post_id)

    # History
    history = state.get("history", [])
    history.append({
        "post_id": post_id,
        "platform": platform,
        "posted_at": datetime.now().isoformat(),
    })
    state["history"] = history[-200:]
    state["posted_ids"] = list(set(state.get("posted_ids", []) + [post_id]))[-200:]

    _save_state(state)


def run_daily_cycle() -> dict:
    """Run the full daily content cycle.

    1. Auto-approve pending content
    2. Select today's posts
    3. Export to platform-ready folders
    4. Return summary

    Call this from cron every morning (e.g., 8am).
    """
    results = {
        "approved": 0,
        "ig_exported": 0,
        "tiktok_exported": 0,
        "ig_posts": [],
        "tiktok_posts": [],
    }

    # Step 1: Auto-approve
    results["approved"] = auto_approve_pending()

    # Step 2: Select posts
    picks = select_next_posts()

    # Step 3: Export
    for post in picks.get("instagram", []):
        path = export_for_platform(post, "instagram")
        if path:
            results["ig_exported"] += 1
            results["ig_posts"].append(post.id)

    for post in picks.get("tiktok", []):
        path = export_for_platform(post, "tiktok")
        if path:
            results["tiktok_exported"] += 1
            results["tiktok_posts"].append(post.id)

    logger.info(
        f"Daily cycle: {results['approved']} approved, "
        f"{results['ig_exported']} IG exports, "
        f"{results['tiktok_exported']} TikTok exports"
    )

    return results


def get_status() -> dict:
    """Get current scheduler status."""
    state = _reset_daily(_load_state())
    queue = get_queue_stats()

    return {
        "queue": queue,
        "ig_posted_today": state.get("ig_posted_today", 0),
        "tiktok_posted_today": state.get("tiktok_posted_today", 0),
        "ig_remaining": MAX_IG_PER_DAY - state.get("ig_posted_today", 0),
        "tiktok_remaining": MAX_TIKTOK_PER_DAY - state.get("tiktok_posted_today", 0),
        "last_content_type": state.get("last_content_type", ""),
        "total_posted_all_time": len(state.get("posted_ids", [])),
        "ready_to_post": {
            "instagram": len(list(EXPORT_IG.glob("*.*"))) // 2,  # media + caption pairs
            "tiktok": len(list(EXPORT_TIKTOK.glob("*.*"))) // 2,
        },
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    if "--status" in sys.argv:
        status = get_status()
        print(f"Queue: {status['queue']}")
        print(f"IG posted today: {status['ig_posted_today']}/{MAX_IG_PER_DAY}")
        print(f"TikTok posted today: {status['tiktok_posted_today']}/{MAX_TIKTOK_PER_DAY}")
        print(f"Ready to post: {status['ready_to_post']}")
        print(f"All-time posted: {status['total_posted_all_time']}")
    else:
        print("Running daily content cycle...\n")
        results = run_daily_cycle()
        print(f"Approved: {results['approved']}")
        print(f"IG exports: {results['ig_exported']} — {results['ig_posts']}")
        print(f"TikTok exports: {results['tiktok_exported']} — {results['tiktok_posts']}")
        print(f"\nCheck ready_to_post/instagram/ and ready_to_post/tiktok/")

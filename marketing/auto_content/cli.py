#!/usr/bin/env python3
"""
CLI for managing auto-generated marketing content.

Usage:
    python -m marketing.auto_content.cli test          # Generate a test deal card
    python -m marketing.auto_content.cli queue          # Show queue status
    python -m marketing.auto_content.cli list           # List pending posts
    python -m marketing.auto_content.cli approve <id>   # Approve a pending post
    python -m marketing.auto_content.cli skip <id>      # Skip/delete a pending post
    python -m marketing.auto_content.cli caption <id>   # Show caption for a post
    python -m marketing.auto_content.cli preview        # Open the latest pending post
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def cmd_test(args):
    """Generate a test deal card with sample data."""
    from marketing.auto_content.deal_card import DealCardData, generate_deal_card

    sample = DealCardData(
        title="Leather Geobasket High Top Sneakers",
        brand="Rick Owens",
        source="grailed",
        source_url="https://grailed.com/listings/example",
        buy_price=280,
        market_price=650,
        profit=370,
        margin=0.57,
        fire_level=3,
        quality_score=78,
        comp_count=8,
        auth_confidence=0.87,
        size="42",
        condition="Gently Used",
        season_name="FW08",
        demand_level="hot",
        tier="pro",
    )

    img, path = generate_deal_card(sample, listing_img=None, save=True)
    print(f"Generated test deal card: {path}")

    # Also generate caption
    from marketing.auto_content.caption import generate_deal_caption
    caption = generate_deal_caption(sample)
    print(f"\n--- Caption ---\n{caption}\n--- End ---")

    # Save caption to queue
    from marketing.auto_content.content_queue import save_to_queue
    save_to_queue(
        image_path=path,
        caption=caption,
        post_type="deal",
        brand=sample.brand,
        profit=sample.profit,
        fire_level=sample.fire_level,
        content_pillar="deal_breakdown",
    )

    # Try to open the image
    if sys.platform == "darwin":
        subprocess.run(["open", path], check=False)

    return path


def cmd_queue(args):
    """Show queue status."""
    from marketing.auto_content.content_queue import get_queue_stats
    stats = get_queue_stats()
    print(f"Content Queue:")
    print(f"  Pending:  {stats['pending']}")
    print(f"  Approved: {stats['approved']}")
    print(f"  Posted:   {stats['posted']}")


def cmd_list(args):
    """List posts in a queue."""
    from marketing.auto_content.content_queue import list_queue
    status = args.status or "pending"
    posts = list_queue(status)
    if not posts:
        print(f"No {status} posts.")
        return

    for p in posts:
        fire = "🔥" * p.fire_level if p.fire_level else ""
        print(f"  [{p.id}] {fire} {p.brand} — ${p.profit:.0f} profit — {p.post_type}")
        if args.verbose:
            print(f"    Created: {p.created_at}")
            print(f"    Image: {p.image_path}")


def cmd_approve(args):
    """Approve a pending post."""
    from marketing.auto_content.content_queue import approve_post
    result = approve_post(args.post_id)
    if result:
        print(f"Approved: {args.post_id}")
    else:
        print(f"Post not found: {args.post_id}")


def cmd_skip(args):
    """Skip/delete a pending post."""
    from marketing.auto_content.content_queue import skip_post
    skip_post(args.post_id)
    print(f"Skipped: {args.post_id}")


def cmd_caption(args):
    """Show the caption for a post."""
    from marketing.auto_content.content_queue import PENDING_DIR, APPROVED_DIR, POSTED_DIR

    for d in [PENDING_DIR, APPROVED_DIR, POSTED_DIR]:
        meta_file = d / f"{args.post_id}.json"
        if meta_file.exists():
            data = json.loads(meta_file.read_text())
            print(f"--- Caption ({data.get('status', '?')}) ---")
            print(data.get("caption", "(no caption)"))
            print("--- End ---")
            return

    print(f"Post not found: {args.post_id}")


def cmd_preview(args):
    """Open the latest pending post image."""
    from marketing.auto_content.content_queue import list_queue
    posts = list_queue("pending")
    if not posts:
        print("No pending posts.")
        return

    latest = posts[-1]
    print(f"Opening: {latest.image_path}")
    if sys.platform == "darwin":
        subprocess.run(["open", latest.image_path], check=False)


def main():
    parser = argparse.ArgumentParser(description="Auto-content CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("test", help="Generate a test deal card")

    sub.add_parser("queue", help="Show queue status")

    list_p = sub.add_parser("list", help="List posts")
    list_p.add_argument("--status", default="pending", choices=["pending", "approved", "posted"])
    list_p.add_argument("-v", "--verbose", action="store_true")

    approve_p = sub.add_parser("approve", help="Approve a pending post")
    approve_p.add_argument("post_id")

    skip_p = sub.add_parser("skip", help="Skip a pending post")
    skip_p.add_argument("post_id")

    caption_p = sub.add_parser("caption", help="Show caption for a post")
    caption_p.add_argument("post_id")

    sub.add_parser("preview", help="Open the latest pending post")

    args = parser.parse_args()

    commands = {
        "test": cmd_test,
        "queue": cmd_queue,
        "list": cmd_list,
        "approve": cmd_approve,
        "skip": cmd_skip,
        "caption": cmd_caption,
        "preview": cmd_preview,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

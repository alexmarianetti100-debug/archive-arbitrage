"""
Cross-platform content syndication.

Takes a single piece of generated content (image + caption) and
distributes it to multiple platforms simultaneously:

- Instagram (Meta Graph API or manual queue)
- Twitter/X (API v2)
- Threads (Meta Graph API)
- TikTok (manual queue — no auto-post API for images)
- Reddit (API)

Each platform gets a slightly adapted version:
- Instagram: full caption + hashtags (2200 char limit)
- Twitter/X: condensed to 280 chars + image
- Threads: medium-length + no hashtags
- Reddit: title + body for self-post

Usage:
    from marketing.auto_content.syndication import syndicate_content
    await syndicate_content(post_metadata)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

from .content_queue import PostMetadata

load_dotenv()

logger = logging.getLogger("auto_content.syndication")

# ── Platform API credentials ──
# Twitter/X
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")
TWITTER_ENABLED = bool(TWITTER_API_KEY and TWITTER_ACCESS_TOKEN)

# Threads (uses Meta Graph API — same creds as Instagram)
THREADS_USER_ID = os.getenv("THREADS_USER_ID", "")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
THREADS_ENABLED = bool(THREADS_USER_ID and META_ACCESS_TOKEN)

# Reddit
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME", "")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD", "")
REDDIT_SUBREDDIT = os.getenv("REDDIT_SUBREDDIT", "archivefashion")
REDDIT_ENABLED = bool(REDDIT_CLIENT_ID and REDDIT_USERNAME)


def _adapt_for_twitter(caption: str) -> str:
    """Condense caption to 280 chars for Twitter/X."""
    # Strip hashtags
    lines = [l for l in caption.split("\n") if not l.strip().startswith("#")]
    text = "\n".join(lines).strip()

    # Take first meaningful sentence + profit callout
    sentences = text.split("\n\n")
    tweet = sentences[0] if sentences else text

    # Add link CTA
    suffix = "\n\nReal-time alerts → link in bio"

    if len(tweet) + len(suffix) > 280:
        tweet = tweet[:280 - len(suffix) - 3] + "..."

    return tweet + suffix


def _adapt_for_threads(caption: str) -> str:
    """Adapt caption for Threads (500 char limit, no hashtags)."""
    lines = [l for l in caption.split("\n") if not l.strip().startswith("#")]
    text = "\n".join(lines).strip()
    if len(text) > 500:
        text = text[:497] + "..."
    return text


def _adapt_for_reddit(caption: str, brand: str = "") -> tuple[str, str]:
    """Adapt caption for Reddit. Returns (title, body)."""
    lines = caption.split("\n")
    # First non-empty line as title
    title = next((l.strip() for l in lines if l.strip() and not l.startswith("#")), "Deal Alert")
    if brand:
        title = f"{brand} — {title}"

    # Body: keep deal breakdown, strip hashtags and CTA
    body_lines = []
    for line in lines[1:]:
        if line.strip().startswith("#"):
            continue
        if "link in bio" in line.lower():
            continue
        body_lines.append(line)

    body = "\n".join(body_lines).strip()
    body += "\n\n---\n*Found by Archive Arbitrage — archive fashion deal alerts across 7 platforms*"

    return title[:300], body


# ── Platform posting functions ──

async def post_to_twitter(caption: str, image_path: str) -> bool:
    """Post to Twitter/X with image."""
    if not TWITTER_ENABLED:
        logger.debug("Twitter API not configured")
        return False

    try:
        # Twitter API v2 requires OAuth 1.0a for media upload
        # Using tweepy-style approach with httpx
        from requests_oauthlib import OAuth1
        import requests

        # Step 1: Upload media
        auth = OAuth1(
            TWITTER_API_KEY, TWITTER_API_SECRET,
            TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET,
        )

        with open(image_path, "rb") as f:
            media_resp = requests.post(
                "https://upload.twitter.com/1.1/media/upload.json",
                auth=auth,
                files={"media": f},
            )

        if media_resp.status_code != 200:
            logger.warning(f"Twitter media upload failed: {media_resp.status_code}")
            return False

        media_id = media_resp.json()["media_id_string"]

        # Step 2: Create tweet with media
        tweet_text = _adapt_for_twitter(caption)
        tweet_resp = requests.post(
            "https://api.twitter.com/2/tweets",
            auth=auth,
            json={
                "text": tweet_text,
                "media": {"media_ids": [media_id]},
            },
        )

        if tweet_resp.status_code in (200, 201):
            logger.info(f"Posted to Twitter: {tweet_text[:50]}...")
            return True
        else:
            logger.warning(f"Twitter tweet failed: {tweet_resp.status_code} {tweet_resp.text[:200]}")
            return False

    except ImportError:
        logger.warning("requests-oauthlib not installed — pip install requests-oauthlib")
        return False
    except Exception as e:
        logger.error(f"Twitter post failed: {e}")
        return False


async def post_to_threads(caption: str, image_path: str) -> bool:
    """Post to Threads via Meta Graph API."""
    if not THREADS_ENABLED:
        logger.debug("Threads API not configured")
        return False

    # Threads API requires a public URL for the image
    # For now, log what would be posted
    threads_text = _adapt_for_threads(caption)
    logger.info(f"[THREADS] Would post: {threads_text[:100]}...")

    # TODO: When image hosting is set up:
    # 1. Upload image to hosting (S3/Cloudinary)
    # 2. POST /{threads_user_id}/threads with image_url + text
    # 3. POST /{threads_user_id}/threads_publish with creation_id

    return False


async def post_to_reddit(caption: str, image_path: str, brand: str = "") -> bool:
    """Post to Reddit with image."""
    if not REDDIT_ENABLED:
        logger.debug("Reddit API not configured")
        return False

    try:
        # Get OAuth token
        async with httpx.AsyncClient(timeout=15) as client:
            auth_resp = await client.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET),
                data={
                    "grant_type": "password",
                    "username": REDDIT_USERNAME,
                    "password": REDDIT_PASSWORD,
                },
                headers={"User-Agent": "ArchiveArbitrage/1.0"},
            )

            if auth_resp.status_code != 200:
                logger.warning(f"Reddit auth failed: {auth_resp.status_code}")
                return False

            token = auth_resp.json()["access_token"]

            title, body = _adapt_for_reddit(caption, brand)

            # Submit self-post
            submit_resp = await client.post(
                "https://oauth.reddit.com/api/submit",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "ArchiveArbitrage/1.0",
                },
                data={
                    "sr": REDDIT_SUBREDDIT,
                    "kind": "self",
                    "title": title,
                    "text": body,
                },
            )

            if submit_resp.status_code == 200:
                logger.info(f"Posted to Reddit r/{REDDIT_SUBREDDIT}: {title[:50]}...")
                return True
            else:
                logger.warning(f"Reddit submit failed: {submit_resp.status_code}")
                return False

    except Exception as e:
        logger.error(f"Reddit post failed: {e}")
        return False


async def syndicate_content(post: PostMetadata) -> dict:
    """Syndicate a post to all configured platforms.

    Returns dict of {platform: success_bool}.
    """
    results = {}

    # Instagram — handled by scheduler.py (Meta Graph API or manual)
    # We don't double-post here

    # Twitter/X
    if TWITTER_ENABLED:
        results["twitter"] = await post_to_twitter(post.caption, post.image_path)
    else:
        results["twitter"] = False

    # Threads
    if THREADS_ENABLED:
        results["threads"] = await post_to_threads(post.caption, post.image_path)
    else:
        results["threads"] = False

    # Reddit (only for market intel and weekly recaps, not individual deals)
    if REDDIT_ENABLED and post.post_type in ("market_intel", "weekly_recap"):
        results["reddit"] = await post_to_reddit(post.caption, post.image_path, post.brand)
    else:
        results["reddit"] = False

    posted = [p for p, ok in results.items() if ok]
    if posted:
        logger.info(f"Syndicated {post.id} to: {', '.join(posted)}")
    else:
        logger.debug(f"No syndication targets configured or available for {post.id}")

    return results

"""
Pipeline hook — connects the deal alert system to content auto-generation.

Call on_deal_alert() from the alert dispatch path (core/alerts.py or
gap_hunter.py) to automatically generate Instagram content for qualifying deals.

Qualification criteria for auto-content:
- fire_level >= 2 (hot deal or fire deal)
- OR profit >= $300 (significant flip)
- Rate limited to max 3 posts/day to avoid content spam
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("auto_content.pipeline_hook")

# Rate limiting state
_STATE_FILE = Path(__file__).parent / "queue" / "generation_state.json"
_MAX_POSTS_PER_DAY = 3
_MIN_FIRE_LEVEL = 2
_MIN_PROFIT_OVERRIDE = 300  # Generate content even for fire_level < 2 if profit is this high


def _load_state() -> dict:
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text())
    except Exception:
        pass
    return {"today": "", "count": 0, "generated_urls": []}


def _save_state(state: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, indent=2))


def _check_rate_limit() -> bool:
    """Check if we can generate another post today."""
    state = _load_state()
    today = date.today().isoformat()

    if state.get("today") != today:
        # New day — reset
        state = {"today": today, "count": 0, "generated_urls": []}
        _save_state(state)
        return True

    return state["count"] < _MAX_POSTS_PER_DAY


def _record_generation(source_url: str) -> None:
    state = _load_state()
    today = date.today().isoformat()

    if state.get("today") != today:
        state = {"today": today, "count": 0, "generated_urls": []}

    state["count"] += 1
    urls = state.get("generated_urls", [])
    urls.append(source_url)
    state["generated_urls"] = urls[-50:]  # Keep last 50
    _save_state(state)


def _already_generated(source_url: str) -> bool:
    state = _load_state()
    return source_url in state.get("generated_urls", [])


def should_generate_content(
    fire_level: int = 0,
    profit: float = 0,
    source_url: str = "",
) -> bool:
    """Determine if a deal qualifies for auto content generation."""
    if not _check_rate_limit():
        return False

    if source_url and _already_generated(source_url):
        return False

    if fire_level >= _MIN_FIRE_LEVEL:
        return True

    if profit >= _MIN_PROFIT_OVERRIDE:
        return True

    return False


async def on_deal_alert(
    item: Any,
    signals: Any = None,
    auth_result: Any = None,
    tier: str = "beginner",
) -> Optional[str]:
    """Hook called when a deal alert is dispatched.

    Checks if the deal qualifies for content generation, and if so,
    generates a deal card + caption and queues it.

    Args:
        item: ScrapedItem or AlertItem from the pipeline.
        signals: DealSignals with quality_score, fire_level, etc.
        auth_result: AuthResult with confidence score.
        tier: Deal tier (beginner/pro/whale).

    Returns:
        Path to the generated image, or None if skipped.
    """
    from .deal_card import DealCardData, generate_deal_card_async
    from .caption import generate_deal_caption
    from .content_queue import save_to_queue

    fire_level = int(getattr(signals, "fire_level", 0) or 0) if signals else 0
    profit = float(getattr(item, "profit", 0) or getattr(signals, "profit_estimate", 0) or 0)
    source_url = getattr(item, "source_url", "") or getattr(item, "url", "") or ""

    if not should_generate_content(fire_level, profit, source_url):
        return None

    try:
        # Build card data
        card_data = DealCardData.from_alert_item(item, signals, auth_result, tier)

        # Generate image via HTML renderer (Chrome-quality)
        try:
            from .html_renderer import render_from_deal_data
            _, image_path = await render_from_deal_data(card_data)
        except Exception as e:
            logger.warning(f"HTML renderer failed, falling back to PIL: {e}")
            img, image_path = await generate_deal_card_async(card_data, fetch_image=True, save=True)

        if not image_path:
            logger.warning("Deal card generation returned no path")
            return None

        # Generate caption
        caption = generate_deal_caption(card_data)

        # Queue it
        save_to_queue(
            image_path=image_path,
            caption=caption,
            post_type="deal",
            brand=card_data.brand,
            profit=card_data.profit,
            fire_level=card_data.fire_level,
            source_url=source_url,
            tier=tier,
            content_pillar="deal_breakdown",
        )

        _record_generation(source_url)
        logger.info(f"Auto-generated content for {card_data.brand} deal (${profit:.0f} profit)")

        # Also generate viral video for fire deals (fire_level >= 3 or profit >= $400)
        if fire_level >= 3 or profit >= 400:
            try:
                from .video_gen_v3 import generate_find_video
                from .deal_card import _fetch_listing_image_sync
                listing_img = _fetch_listing_image_sync(card_data.image_url)
                video_path, thumb_path = generate_find_video(card_data, listing_img=listing_img)
                if video_path:
                    save_to_queue(
                        image_path=video_path,
                        caption=caption,
                        post_type="video",
                        brand=card_data.brand,
                        profit=card_data.profit,
                        fire_level=card_data.fire_level,
                        source_url=source_url,
                        tier=tier,
                        content_pillar="deal_breakdown",
                    )
                    logger.info(f"Auto-generated VIDEO for {card_data.brand} deal")
            except Exception as e:
                logger.warning(f"Video generation skipped: {e}")

        return image_path

    except Exception as e:
        logger.error(f"Content generation failed: {e}", exc_info=True)
        return None


def on_deal_alert_sync(
    item: Any,
    signals: Any = None,
    auth_result: Any = None,
    tier: str = "beginner",
) -> Optional[str]:
    """Synchronous version of on_deal_alert for non-async contexts."""
    from .deal_card import DealCardData, generate_deal_card, _fetch_listing_image_sync
    from .caption import generate_deal_caption
    from .content_queue import save_to_queue

    fire_level = int(getattr(signals, "fire_level", 0) or 0) if signals else 0
    profit = float(getattr(item, "profit", 0) or getattr(signals, "profit_estimate", 0) or 0)
    source_url = getattr(item, "source_url", "") or getattr(item, "url", "") or ""

    if not should_generate_content(fire_level, profit, source_url):
        return None

    try:
        card_data = DealCardData.from_alert_item(item, signals, auth_result, tier)

        # Generate image via HTML renderer (Chrome-quality)
        try:
            import asyncio
            from .html_renderer import render_from_deal_data
            _, image_path = asyncio.run(render_from_deal_data(card_data))
        except Exception as e:
            logger.warning(f"HTML renderer failed, falling back to PIL: {e}")
            listing_img = _fetch_listing_image_sync(card_data.image_url)
            img, image_path = generate_deal_card(card_data, listing_img=listing_img, save=True)

        if not image_path:
            return None

        caption = generate_deal_caption(card_data)

        save_to_queue(
            image_path=image_path,
            caption=caption,
            post_type="deal",
            brand=card_data.brand,
            profit=card_data.profit,
            fire_level=card_data.fire_level,
            source_url=source_url,
            tier=tier,
            content_pillar="deal_breakdown",
        )

        _record_generation(source_url)
        logger.info(f"Auto-generated content for {card_data.brand} deal (${profit:.0f} profit)")
        return image_path

    except Exception as e:
        logger.error(f"Content generation failed: {e}", exc_info=True)
        return None

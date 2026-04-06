"""
Auto-generate Instagram deal cards from pipeline data.

Produces a single-image deal card (1080x1350) with:
- Listing photo (darkened background or inset)
- Brand + item title
- Price comparison (listed vs market)
- Profit callout
- Comp count + auth confidence
- Fire level badge
- @archivearbitrage branding

Hook point: call generate_deal_card() from the alert dispatch path
after a deal qualifies for posting (fire_level >= 2, or weekly "best of").
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import httpx
from PIL import Image, ImageDraw

from .design import (
    INSTAGRAM_PORTRAIT,
    BLACK, DARK_BG, CARD_BG, MID_GREY, LIGHT_GREY, BODY_TEXT, OFF_WHITE,
    GOLD, BRIGHT_GOLD, GREEN, PROFIT_GREEN, RED, FIRE_ORANGE,
    FIRE_COLORS,
    load_font, new_canvas, finalize, wrap_text,
    draw_text_centered, draw_hline, draw_hline_centered,
    draw_pill_badge, get_brand_accent, composite_listing_image,
    add_scanlines,
)

logger = logging.getLogger("auto_content.deal_card")

QUEUE_DIR = Path(__file__).parent / "queue" / "pending"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class DealCardData:
    """Data needed to generate a deal card image.

    This is the bridge between the pipeline's deal objects and the
    image generator. Build one from a GapDeal + DealSignals + AuthResult,
    or directly from an AlertItem.
    """
    title: str
    brand: str
    source: str                    # "grailed", "poshmark", etc.
    source_url: str
    buy_price: float
    market_price: float
    profit: float
    margin: float                  # 0.0-1.0
    fire_level: int = 0            # 0-3
    quality_score: float = 0.0     # 0-100
    comp_count: int = 0
    auth_confidence: float = 0.0   # 0.0-1.0
    image_url: Optional[str] = None
    size: Optional[str] = None
    condition: Optional[str] = None
    season_name: Optional[str] = None
    demand_level: str = "unknown"  # hot, warm, cold
    tier: str = "beginner"         # beginner, pro, whale

    @classmethod
    def from_alert_item(cls, item, signals=None, auth_result=None, tier: str = "beginner") -> "DealCardData":
        """Build from an AlertItem (core/alerts.py) or ScrapedItem + signals."""
        return cls(
            title=getattr(item, "title", "") or "",
            brand=getattr(item, "brand", "") or "",
            source=getattr(item, "source", "") or "",
            source_url=getattr(item, "source_url", "") or getattr(item, "url", "") or "",
            buy_price=float(getattr(item, "source_price", 0) or getattr(item, "price", 0) or 0),
            market_price=float(getattr(item, "market_price", 0) or 0),
            profit=float(getattr(item, "profit", 0) or getattr(signals, "profit_estimate", 0) or 0),
            margin=float(getattr(item, "margin_percent", 0) or getattr(signals, "gap_percent", 0) or 0),
            fire_level=int(getattr(signals, "fire_level", 0) or 0) if signals else 0,
            quality_score=float(getattr(signals, "quality_score", 0) or 0) if signals else 0,
            comp_count=int(getattr(item, "comps_count", 0) or getattr(signals, "comp_count", 0) or 0),
            auth_confidence=float(getattr(auth_result, "confidence", 0) or 0) if auth_result else 0,
            image_url=getattr(item, "image_url", None) or (getattr(item, "images", [None]) or [None])[0],
            size=getattr(item, "size", None),
            condition=getattr(item, "condition", None),
            season_name=getattr(item, "season_name", None) or (getattr(signals, "season_name", None) if signals else None),
            demand_level=getattr(item, "demand_level", "unknown") or "unknown",
            tier=tier,
        )


async def _fetch_listing_image(url: str) -> Optional[Image.Image]:
    """Download a listing photo. Returns None on failure."""
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception as e:
        logger.warning(f"Failed to fetch listing image: {e}")
    return None


def _fetch_listing_image_sync(url: str) -> Optional[Image.Image]:
    """Synchronous version for non-async contexts."""
    if not url:
        return None
    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception as e:
        logger.warning(f"Failed to fetch listing image: {e}")
    return None


def _fire_text(level: int) -> str:
    """Fire level as display text."""
    if level >= 3:
        return "FIRE DEAL"
    elif level == 2:
        return "HOT DEAL"
    elif level == 1:
        return "DEAL"
    return ""


def _source_label(source: str) -> str:
    labels = {
        "grailed": "Grailed",
        "poshmark": "Poshmark",
        "ebay": "eBay",
        "depop": "Depop",
        "mercari": "Mercari",
        "vinted": "Vinted",
        "fashionphile": "Fashionphile",
    }
    return labels.get(source.lower(), source.title())


def generate_deal_card(
    data: DealCardData,
    listing_img: Optional[Image.Image] = None,
    save: bool = True,
) -> Tuple[Image.Image, Optional[str]]:
    """Generate a deal card image.

    Args:
        data: Deal data to render.
        listing_img: Pre-fetched listing photo (or None to skip).
        save: If True, save to the pending queue and return the file path.

    Returns:
        (image, file_path) — file_path is None if save=False.
    """
    W, H = INSTAGRAM_PORTRAIT
    img, draw = new_canvas(INSTAGRAM_PORTRAIT, BLACK)
    add_scanlines(draw, H)

    accent = get_brand_accent(data.brand)
    fire_color = FIRE_COLORS.get(data.fire_level, MID_GREY)

    # ── Top accent bar ──
    draw.rectangle([(0, 0), (W, 4)], fill=accent)

    # ── Header ──
    header_font = load_font(20)
    draw.text((80, 40), "ARCHIVE ARBITRAGE", font=header_font, fill=MID_GREY)

    fire_label = _fire_text(data.fire_level)
    if fire_label:
        bbox = draw.textbbox((0, 0), fire_label, font=header_font)
        fw = bbox[2] - bbox[0]
        draw.text((W - 80 - fw, 40), fire_label, font=header_font, fill=fire_color)

    draw_hline(draw, 75, color=(28, 28, 28))

    y = 90

    # ── Listing image region (top 35% of card) ──
    img_region_bottom = 480
    if listing_img:
        img = composite_listing_image(img, listing_img, (0, y, W, img_region_bottom), darken=0.55)
        # Re-create draw after pasting
        draw = ImageDraw.Draw(img)

        # Gradient fade at bottom of image
        for gy in range(img_region_bottom - 80, img_region_bottom):
            alpha = int(255 * ((gy - (img_region_bottom - 80)) / 80))
            draw.line([(0, gy), (W, gy)], fill=(8, 8, 8, alpha) if img.mode == "RGBA" else (8, 8, 8), width=1)
    else:
        # No image — fill with dark card background
        draw.rectangle([(0, y), (W, img_region_bottom)], fill=CARD_BG)
        # Placeholder text
        draw_text_centered(draw, y + 150, "NO IMAGE", load_font(36), MID_GREY, W)

    y = img_region_bottom + 15

    # ── Fire level badge (overlapping image bottom) ──
    if data.fire_level >= 2:
        badge_font = load_font(18, bold=True)
        score_text = f"SCORE: {data.quality_score:.0f}/100"
        bw, bh = draw_pill_badge(
            draw, 80, img_region_bottom - 25,
            score_text, badge_font,
            text_color=BLACK, bg_color=fire_color,
        )

    # ── Brand ──
    brand_font = load_font(22)
    draw.text((80, y), data.brand.upper(), font=brand_font, fill=accent)
    y += 35

    # ── Title ──
    title_font = load_font(40, bold=True)
    title_lines = wrap_text(draw, data.title.upper(), title_font, 900)
    for line in title_lines[:3]:  # Max 3 lines
        draw.text((80, y), line, font=title_font, fill=OFF_WHITE)
        y += 50
    y += 10

    # ── Season + size badges ──
    badge_x = 80
    badge_font = load_font(16, bold=True)
    if data.season_name:
        bw, _ = draw_pill_badge(draw, badge_x, y, data.season_name, badge_font, OFF_WHITE, (50, 50, 50))
        badge_x += bw + 10
    if data.size:
        bw, _ = draw_pill_badge(draw, badge_x, y, f"SIZE {data.size}", badge_font, OFF_WHITE, (50, 50, 50))
        badge_x += bw + 10
    if data.condition:
        bw, _ = draw_pill_badge(draw, badge_x, y, data.condition.upper(), badge_font, OFF_WHITE, (50, 50, 50))
    y += 50

    # ── Divider ──
    draw_hline(draw, y, color=accent, width=2)
    y += 25

    # ── Price comparison block ──
    label_font = load_font(18)
    price_font = load_font(52, bold=True)
    small_font = load_font(22)

    # Left: Buy price
    draw.text((80, y), "LISTED", font=label_font, fill=MID_GREY)
    y += 25
    draw.text((80, y), f"${data.buy_price:,.0f}", font=price_font, fill=OFF_WHITE)

    # Right: Market price
    draw.text((W // 2 + 40, y - 25), "MARKET VALUE", font=label_font, fill=MID_GREY)
    draw.text((W // 2 + 40, y), f"${data.market_price:,.0f}", font=price_font, fill=GOLD)

    # Arrow between them
    arrow_y = y + 22
    arrow_x = W // 2 - 30
    draw.line([(arrow_x - 40, arrow_y), (arrow_x + 20, arrow_y)], fill=accent, width=3)
    draw.line([(arrow_x + 5, arrow_y - 10), (arrow_x + 20, arrow_y)], fill=accent, width=3)
    draw.line([(arrow_x + 5, arrow_y + 10), (arrow_x + 20, arrow_y)], fill=accent, width=3)

    y += 80

    # ── Profit + stats row ──
    draw_hline(draw, y, color=(28, 28, 28))
    y += 20

    # Three columns: profit | margin | comps
    col_w = (W - 160) // 3
    cols = [
        ("EST. PROFIT", f"${data.profit:,.0f}", PROFIT_GREEN),
        ("BELOW MARKET", f"{data.margin * 100:.0f}%", PROFIT_GREEN),
        ("SOLD COMPS", f"{data.comp_count}", LIGHT_GREY),
    ]

    stat_label_font = load_font(16)
    stat_val_font = load_font(36, bold=True)

    for i, (label, value, color) in enumerate(cols):
        cx = 80 + i * col_w + col_w // 2
        # Center label
        lbbox = draw.textbbox((0, 0), label, font=stat_label_font)
        lw = lbbox[2] - lbbox[0]
        draw.text((cx - lw // 2, y), label, font=stat_label_font, fill=MID_GREY)
        # Center value
        vbbox = draw.textbbox((0, 0), value, font=stat_val_font)
        vw = vbbox[2] - vbbox[0]
        draw.text((cx - vw // 2, y + 25), value, font=stat_val_font, fill=color)

    y += 85

    # ── Auth confidence bar ──
    if data.auth_confidence > 0:
        draw_hline(draw, y, color=(28, 28, 28))
        y += 15
        auth_font = load_font(16)
        draw.text((80, y), "AUTH CONFIDENCE", font=auth_font, fill=MID_GREY)

        # Draw bar
        bar_x, bar_y = 260, y + 3
        bar_w, bar_h = 300, 14
        draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h)], radius=7, fill=(40, 40, 40))
        filled_w = int(bar_w * data.auth_confidence)
        if filled_w > 0:
            bar_color = GREEN if data.auth_confidence >= 0.7 else GOLD if data.auth_confidence >= 0.5 else RED
            draw.rounded_rectangle([(bar_x, bar_y), (bar_x + filled_w, bar_y + bar_h)], radius=7, fill=bar_color)

        pct_text = f"{data.auth_confidence * 100:.0f}%"
        draw.text((bar_x + bar_w + 15, y), pct_text, font=auth_font, fill=LIGHT_GREY)
        y += 35

    # ── Platform + demand ──
    y += 5
    platform_text = f"Found on {_source_label(data.source)}"
    if data.demand_level and data.demand_level != "unknown":
        demand_emoji = {"hot": "HOT", "warm": "WARM", "cold": "COLD"}.get(data.demand_level, "")
        if demand_emoji:
            platform_text += f"  |  Demand: {demand_emoji}"

    draw.text((80, y), platform_text, font=load_font(20), fill=MID_GREY)

    # ── Footer ──
    draw_hline(draw, H - 80, color=(28, 28, 28))
    footer_font = load_font(20)
    draw.text((80, H - 55), "@archivearbitrage", font=footer_font, fill=GOLD)
    draw.text((W - 250, H - 55), "Link in bio", font=footer_font, fill=MID_GREY)

    # ── Post-process ──
    img = finalize(img)

    # ── Save ──
    file_path = None
    if save:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        brand_slug = data.brand.lower().replace(" ", "_")[:20]
        filename = f"deal_{brand_slug}_{timestamp}.jpg"
        file_path = str(QUEUE_DIR / filename)
        img.save(file_path, "JPEG", quality=95)
        logger.info(f"Deal card saved: {file_path}")

    return img, file_path


async def generate_deal_card_async(
    data: DealCardData,
    fetch_image: bool = True,
    save: bool = True,
) -> Tuple[Image.Image, Optional[str]]:
    """Async wrapper that fetches the listing image then generates the card."""
    listing_img = None
    if fetch_image and data.image_url:
        listing_img = await _fetch_listing_image(data.image_url)

    return generate_deal_card(data, listing_img=listing_img, save=save)

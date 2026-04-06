"""
Auto-generate short-form video content (Reels/TikTok/Shorts) from deal data.

Renders animated deal breakdown videos:
- Brand name reveal
- Listing image fade-in
- Price counter animation (buy price → market value)
- Profit reveal with green flash
- Auth confidence bar fill
- Comp count + fire level badge
- CTA slide

Output: 1080x1920 (9:16 vertical), 8-12 seconds, 30fps MP4
Pipeline: PIL frames → ffmpeg encode

Hook: call generate_deal_video() from pipeline_hook.py for fire deals.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter
import numpy as np

from .design import (
    BLACK, DARK_BG, CARD_BG, MID_GREY, LIGHT_GREY, BODY_TEXT, OFF_WHITE,
    GOLD, BRIGHT_GOLD, GREEN, PROFIT_GREEN, RED, FIRE_ORANGE,
    FIRE_COLORS,
    load_font, add_grain, add_vignette,
    wrap_text, get_brand_accent,
)
from .deal_card import DealCardData

logger = logging.getLogger("auto_content.video_gen")

# ── Video config ──
VIDEO_SIZE = (1080, 1920)  # 9:16 vertical
FPS = 30
TOTAL_DURATION = 10.0  # seconds
TOTAL_FRAMES = int(FPS * TOTAL_DURATION)

QUEUE_DIR = Path(__file__).parent / "queue" / "pending"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)


def _ease_out_cubic(t: float) -> float:
    """Cubic ease-out for smooth animations."""
    return 1.0 - (1.0 - t) ** 3


def _ease_in_out(t: float) -> float:
    """Ease in-out for price counter."""
    if t < 0.5:
        return 4 * t * t * t
    return 1 - (-2 * t + 2) ** 3 / 2


def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation."""
    return a + (b - a) * max(0.0, min(1.0, t))


def _color_lerp(c1: tuple, c2: tuple, t: float) -> tuple:
    """Interpolate between two RGB colors."""
    t = max(0.0, min(1.0, t))
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _add_scanlines(draw: ImageDraw.Draw, w: int, h: int, opacity: int = 12):
    """Subtle scanlines for editorial feel."""
    for y in range(0, h, 3):
        draw.line([(0, y), (w, y)], fill=(opacity, opacity, opacity), width=1)


def _finalize_frame(img: Image.Image) -> Image.Image:
    """Light post-processing per frame (less than static images for perf)."""
    # Lighter grain for video (heavy grain causes compression artifacts)
    arr = np.array(img).astype(np.int16)
    noise = np.random.normal(0, 8, arr.shape).astype(np.int16)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


# ── Timeline (frame ranges for each animation phase) ──
# Phase 1: Brand reveal (0.0s - 1.5s)
# Phase 2: Item title + image (1.0s - 3.0s)
# Phase 3: Price counter (2.5s - 5.5s)
# Phase 4: Profit reveal (5.0s - 7.0s)
# Phase 5: Stats (auth, comps, fire) (6.5s - 8.5s)
# Phase 6: CTA (8.0s - 10.0s)

def _frame_progress(frame: int, start_sec: float, end_sec: float) -> float:
    """Get animation progress (0.0-1.0) for a frame within a time window."""
    start_f = start_sec * FPS
    end_f = end_sec * FPS
    if frame < start_f:
        return 0.0
    if frame >= end_f:
        return 1.0
    return (frame - start_f) / (end_f - start_f)


def render_frame(
    frame_num: int,
    data: DealCardData,
    listing_img: Optional[Image.Image] = None,
    accent: tuple = GOLD,
) -> Image.Image:
    """Render a single frame of the deal video."""
    W, H = VIDEO_SIZE
    img = Image.new("RGB", VIDEO_SIZE, BLACK)
    draw = ImageDraw.Draw(img)
    _add_scanlines(draw, W, H)

    # ── Phase 1: Brand reveal (0.0 - 1.5s) ──
    p1 = _frame_progress(frame_num, 0.0, 1.2)
    if p1 > 0:
        brand_alpha = _ease_out_cubic(p1)
        brand_font = load_font(36)
        brand_text = data.brand.upper()
        bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
        bw = bbox[2] - bbox[0]
        brand_color = _color_lerp(BLACK, accent, brand_alpha)
        draw.text(((W - bw) // 2, 140), brand_text, font=brand_font, fill=brand_color)

        # Accent line expanding
        line_w = int(400 * _ease_out_cubic(min(p1 * 1.5, 1.0)))
        if line_w > 0:
            x1 = (W - line_w) // 2
            draw.line([(x1, 190), (x1 + line_w, 190)], fill=accent, width=2)

    # ── Phase 2: Title + image (1.0 - 3.0s) ──
    p2 = _frame_progress(frame_num, 0.8, 2.5)
    if p2 > 0:
        title_alpha = _ease_out_cubic(p2)

        # Listing image (fade in behind)
        if listing_img:
            img_region = (0, 240, W, 900)
            x1, y1, x2, y2 = img_region
            tw, th = x2 - x1, y2 - y1

            # Resize to cover
            img_ratio = listing_img.width / listing_img.height
            target_ratio = tw / th
            if img_ratio > target_ratio:
                new_h = th
                new_w = int(new_h * img_ratio)
            else:
                new_w = tw
                new_h = int(new_w / img_ratio)
            resized = listing_img.resize((new_w, new_h), Image.LANCZOS)
            cx = (new_w - tw) // 2
            cy = (new_h - th) // 2
            cropped = resized.crop((cx, cy, cx + tw, cy + th))

            # Darken + fade in
            darkness = 0.6
            overlay = Image.new("RGB", (tw, th), BLACK)
            blended = Image.blend(cropped, overlay, darkness)

            # Fade in via alpha
            fade = int(255 * _ease_out_cubic(min(p2 * 1.3, 1.0)))
            mask = Image.new("L", (tw, th), fade)
            img.paste(blended, (x1, y1), mask)
            draw = ImageDraw.Draw(img)  # Recreate after paste

            # Bottom gradient
            for gy in range(y2 - 100, y2):
                ga = int(255 * ((gy - (y2 - 100)) / 100))
                draw.line([(0, gy), (W, gy)], fill=(8, 8, 8), width=1)
        else:
            draw.rectangle([(0, 240), (W, 900)], fill=CARD_BG)

        # Title text (slides up)
        title_y = int(_lerp(960, 920, _ease_out_cubic(p2)))
        title_font = load_font(44, bold=True)
        title_color = _color_lerp(BLACK, OFF_WHITE, title_alpha)
        title_lines = wrap_text(draw, data.title.upper(), title_font, 920)
        for line in title_lines[:3]:
            bbox = draw.textbbox((0, 0), line, font=title_font)
            lw = bbox[2] - bbox[0]
            draw.text(((W - lw) // 2, title_y), line, font=title_font, fill=title_color)
            title_y += 56

    # ── Phase 3: Price counter (2.5 - 5.5s) ──
    p3 = _frame_progress(frame_num, 2.5, 5.0)
    if p3 > 0:
        price_section_y = 1080
        price_alpha = _ease_out_cubic(min(p3 * 2, 1.0))

        # Labels
        label_font = load_font(22)
        label_color = _color_lerp(BLACK, MID_GREY, price_alpha)
        draw.text((W // 2 - 350, price_section_y), "LISTED", font=label_font, fill=label_color)
        draw.text((W // 2 + 120, price_section_y), "MARKET VALUE", font=label_font, fill=label_color)

        # Animated price values
        price_font = load_font(64, bold=True)
        counter_progress = _ease_in_out(min(p3 * 1.2, 1.0))

        # Buy price (counts up from 0)
        displayed_buy = int(data.buy_price * counter_progress)
        buy_color = _color_lerp(BLACK, OFF_WHITE, price_alpha)
        draw.text((W // 2 - 350, price_section_y + 30), f"${displayed_buy:,}", font=price_font, fill=buy_color)

        # Market price (counts up from 0, slightly delayed)
        market_progress = _ease_in_out(max(0, min((p3 - 0.15) * 1.3, 1.0)))
        displayed_market = int(data.market_price * market_progress)
        market_color = _color_lerp(BLACK, GOLD, price_alpha)
        draw.text((W // 2 + 120, price_section_y + 30), f"${displayed_market:,}", font=price_font, fill=market_color)

        # Arrow between
        if price_alpha > 0.5:
            arrow_x = W // 2 - 20
            arrow_y = price_section_y + 55
            arrow_color = _color_lerp(BLACK, accent, price_alpha)
            draw.line([(arrow_x - 30, arrow_y), (arrow_x + 30, arrow_y)], fill=arrow_color, width=3)
            draw.line([(arrow_x + 15, arrow_y - 12), (arrow_x + 30, arrow_y)], fill=arrow_color, width=3)
            draw.line([(arrow_x + 15, arrow_y + 12), (arrow_x + 30, arrow_y)], fill=arrow_color, width=3)

    # ── Phase 4: Profit reveal (5.0 - 7.0s) ──
    p4 = _frame_progress(frame_num, 5.0, 6.5)
    if p4 > 0:
        profit_y = 1240
        profit_alpha = _ease_out_cubic(p4)

        # Divider
        div_w = int(800 * _ease_out_cubic(min(p4 * 2, 1.0)))
        if div_w > 0:
            x1 = (W - div_w) // 2
            draw.line([(x1, profit_y), (x1 + div_w, profit_y)], fill=accent, width=2)

        # "EST. PROFIT" label
        plabel_font = load_font(24)
        plabel_color = _color_lerp(BLACK, MID_GREY, profit_alpha)
        plabel = "EST. PROFIT"
        bbox = draw.textbbox((0, 0), plabel, font=plabel_font)
        pw = bbox[2] - bbox[0]
        draw.text(((W - pw) // 2, profit_y + 20), plabel, font=plabel_font, fill=plabel_color)

        # Big profit number (scale up effect via font size interpolation)
        profit_text = f"${data.profit:,.0f}"
        profit_size = int(_lerp(40, 80, _ease_out_cubic(min(p4 * 1.5, 1.0))))
        profit_font = load_font(profit_size, bold=True)
        profit_color = _color_lerp(BLACK, PROFIT_GREEN, profit_alpha)
        bbox = draw.textbbox((0, 0), profit_text, font=profit_font)
        pw = bbox[2] - bbox[0]
        draw.text(((W - pw) // 2, profit_y + 55), profit_text, font=profit_font, fill=profit_color)

        # Margin badge
        if p4 > 0.5:
            margin_text = f"{data.margin * 100:.0f}% BELOW MARKET"
            margin_font = load_font(26)
            margin_color = _color_lerp(BLACK, PROFIT_GREEN, min((p4 - 0.5) * 2, 1.0))
            bbox = draw.textbbox((0, 0), margin_text, font=margin_font)
            mw = bbox[2] - bbox[0]
            draw.text(((W - mw) // 2, profit_y + 150), margin_text, font=margin_font, fill=margin_color)

    # ── Phase 5: Stats row (6.5 - 8.5s) ──
    p5 = _frame_progress(frame_num, 6.5, 8.0)
    if p5 > 0:
        stats_y = 1460
        stats_alpha = _ease_out_cubic(p5)
        stat_color = _color_lerp(BLACK, LIGHT_GREY, stats_alpha)
        accent_color = _color_lerp(BLACK, accent, stats_alpha)

        # Three stat columns
        stat_font = load_font(36, bold=True)
        label_font = load_font(16)
        col_w = W // 3

        stats = [
            (f"{data.comp_count}", "SOLD COMPS"),
            (f"{data.auth_confidence * 100:.0f}%", "AUTH SCORE"),
            (f"{'FIRE' if data.fire_level >= 3 else 'HOT' if data.fire_level >= 2 else 'DEAL'}", "RATING"),
        ]

        for i, (val, label) in enumerate(stats):
            cx = i * col_w + col_w // 2
            vbbox = draw.textbbox((0, 0), val, font=stat_font)
            vw = vbbox[2] - vbbox[0]
            draw.text((cx - vw // 2, stats_y), val, font=stat_font, fill=accent_color)

            lbbox = draw.textbbox((0, 0), label, font=label_font)
            lw = lbbox[2] - lbbox[0]
            draw.text((cx - lw // 2, stats_y + 45), label, font=label_font, fill=stat_color)

        # Auth bar animation
        if p5 > 0.3:
            bar_progress = min((p5 - 0.3) / 0.5, 1.0)
            bar_y = stats_y + 85
            bar_x = (W - 600) // 2
            bar_w = 600
            bar_h = 10
            draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h)], radius=5, fill=(30, 30, 30))
            filled = int(bar_w * data.auth_confidence * _ease_out_cubic(bar_progress))
            if filled > 0:
                bar_color = GREEN if data.auth_confidence >= 0.7 else GOLD
                bc = _color_lerp(BLACK, bar_color, stats_alpha)
                draw.rounded_rectangle([(bar_x, bar_y), (bar_x + filled, bar_y + bar_h)], radius=5, fill=bc)

    # ── Phase 6: CTA (8.0 - 10.0s) ──
    p6 = _frame_progress(frame_num, 8.0, 9.5)
    if p6 > 0:
        cta_alpha = _ease_out_cubic(p6)
        cta_y = 1620

        # Divider
        div_color = _color_lerp(BLACK, accent, cta_alpha)
        draw.line([(80, cta_y), (W - 80, cta_y)], fill=div_color, width=1)

        # Platform
        plat_font = load_font(22)
        plat_text = f"Found on {data.source.title()}"
        plat_color = _color_lerp(BLACK, MID_GREY, cta_alpha)
        bbox = draw.textbbox((0, 0), plat_text, font=plat_font)
        pw = bbox[2] - bbox[0]
        draw.text(((W - pw) // 2, cta_y + 20), plat_text, font=plat_font, fill=plat_color)

        # CTA text
        cta_font = load_font(32, bold=True)
        cta_text = "REAL-TIME ALERTS — LINK IN BIO"
        cta_color = _color_lerp(BLACK, OFF_WHITE, cta_alpha)
        bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
        cw = bbox[2] - bbox[0]
        draw.text(((W - cw) // 2, cta_y + 60), cta_text, font=cta_font, fill=cta_color)

        # @archivearbitrage
        handle_font = load_font(24)
        handle_color = _color_lerp(BLACK, GOLD, cta_alpha)
        handle = "@archivearbitrage"
        bbox = draw.textbbox((0, 0), handle, font=handle_font)
        hw = bbox[2] - bbox[0]
        draw.text(((W - hw) // 2, cta_y + 110), handle, font=handle_font, fill=handle_color)

    # ── Persistent top accent bar ──
    bar_alpha = min(_frame_progress(frame_num, 0.0, 0.5) * 2, 1.0)
    if bar_alpha > 0:
        bar_color = _color_lerp(BLACK, accent, bar_alpha)
        draw.rectangle([(0, 0), (W, 4)], fill=bar_color)

    # ── Persistent header after phase 1 ──
    if frame_num > FPS * 0.5:
        header_font = load_font(18)
        ha = min(_frame_progress(frame_num, 0.5, 1.0), 1.0)
        hc = _color_lerp(BLACK, MID_GREY, ha)
        draw.text((80, 50), "ARCHIVE ARBITRAGE", font=header_font, fill=hc)

        fire_label = "FIRE DEAL" if data.fire_level >= 3 else "HOT DEAL" if data.fire_level >= 2 else ""
        if fire_label:
            fc = _color_lerp(BLACK, FIRE_COLORS.get(data.fire_level, MID_GREY), ha)
            bbox = draw.textbbox((0, 0), fire_label, font=header_font)
            fw = bbox[2] - bbox[0]
            draw.text((W - 80 - fw, 50), fire_label, font=header_font, fill=fc)

    # Light post-processing
    img = _finalize_frame(img)
    return img


def generate_deal_video(
    data: DealCardData,
    listing_img: Optional[Image.Image] = None,
    save: bool = True,
) -> Tuple[Optional[str], Optional[str]]:
    """Generate a deal breakdown video.

    Returns (video_path, thumbnail_path) or (None, None) on failure.
    """
    W, H = VIDEO_SIZE
    accent = get_brand_accent(data.brand)

    # Create temp directory for frames
    tmp_dir = tempfile.mkdtemp(prefix="aa_video_")

    try:
        # Render frames
        logger.info(f"Rendering {TOTAL_FRAMES} frames for {data.brand} deal video...")
        for i in range(TOTAL_FRAMES):
            frame = render_frame(i, data, listing_img, accent)
            frame.save(os.path.join(tmp_dir, f"frame_{i:04d}.jpg"), "JPEG", quality=90)

        # Save thumbnail (frame at profit reveal moment)
        thumb_frame = int(6.0 * FPS)
        thumbnail = render_frame(thumb_frame, data, listing_img, accent)

        # Compile with ffmpeg
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        brand_slug = data.brand.lower().replace(" ", "_")[:20]

        video_filename = f"video_{brand_slug}_{timestamp}.mp4"
        thumb_filename = f"video_{brand_slug}_{timestamp}_thumb.jpg"

        video_path = str(QUEUE_DIR / video_filename) if save else None
        thumb_path = str(QUEUE_DIR / thumb_filename) if save else None

        if save:
            # ffmpeg: frames → MP4 with H.264
            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(FPS),
                "-i", os.path.join(tmp_dir, "frame_%04d.jpg"),
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "28",
                "-pix_fmt", "yuv420p",
                "-vf", f"scale={W}:{H}",
                "-movflags", "+faststart",  # Web-optimized
                video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                logger.error(f"ffmpeg failed: {result.stderr[:500]}")
                return None, None

            # Save thumbnail
            thumbnail.save(thumb_path, "JPEG", quality=95)

            logger.info(f"Video generated: {video_path}")
            logger.info(f"Thumbnail: {thumb_path}")

        return video_path, thumb_path

    except Exception as e:
        logger.error(f"Video generation failed: {e}", exc_info=True)
        return None, None

    finally:
        # Cleanup temp frames
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _fetch_listing_image_sync(url: str) -> Optional[Image.Image]:
    """Fetch listing image synchronously."""
    if not url:
        return None
    try:
        import httpx
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception as e:
        logger.warning(f"Failed to fetch image: {e}")
    return None


# ── CLI ──

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    print("Generating test deal video...\n")

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

    video_path, thumb_path = generate_deal_video(sample)

    if video_path:
        print(f"Video: {video_path}")
        print(f"Thumbnail: {thumb_path}")
        if sys.platform == "darwin":
            subprocess.run(["open", video_path], check=False)
    else:
        print("Video generation failed.")

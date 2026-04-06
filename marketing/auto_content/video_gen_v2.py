"""
Viral short-form video generator v2.

Built on research into what actually goes viral on Reels/TikTok:
- Hook in under 1.5 seconds (price gap or bold claim)
- New visual element every 2 seconds
- Price anchoring (market value FIRST, then deal price)
- Dramatic reveal with screen shake + flash
- Bold text (max 7 words per screen, white w/ black stroke)
- 8-12 seconds total (completion rate sweet spot)
- Comment bait ending
- Seamless loop potential

Templates:
  A: "The Steal" — single deal breakdown (most common)
  B: "The Rapid-Fire" — 3 deals in 8 seconds (engagement machine)

Output: 1080x1920 9:16 MP4, 30fps
"""

from __future__ import annotations

import io
import logging
import os
import random
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .design import (
    BLACK, DARK_BG, MID_GREY, LIGHT_GREY, OFF_WHITE,
    GOLD, BRIGHT_GOLD, GREEN, PROFIT_GREEN, RED, FIRE_ORANGE,
    load_font, get_brand_accent,
)
from .deal_card import DealCardData

logger = logging.getLogger("auto_content.video_v2")

W, H = 1080, 1920
FPS = 30
QUEUE_DIR = Path(__file__).parent / "queue" / "pending"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

# ── Colors ──
BG = (6, 6, 6)
TEXT_WHITE = (255, 255, 255)
TEXT_GREEN = (34, 197, 94)
TEXT_RED = (239, 68, 68)
TEXT_GOLD = (212, 168, 83)
FLASH_WHITE = (255, 255, 255)


# ── Animation helpers ──

def _ease_out(t: float) -> float:
    return 1 - (1 - min(max(t, 0), 1)) ** 3

def _ease_out_bounce(t: float) -> float:
    t = min(max(t, 0), 1)
    if t < 0.6:
        return (t / 0.6) ** 2 * 1.15
    elif t < 0.8:
        return 1.15 - (t - 0.7) * 1.5
    else:
        return 1.0

def _pop_scale(t: float) -> float:
    """Scale factor for pop-in: 0 -> overshoot 1.15 -> settle 1.0"""
    if t <= 0:
        return 0
    if t >= 1:
        return 1.0
    return _ease_out_bounce(t)

def _shake_offset(intensity: float) -> Tuple[int, int]:
    """Random screen shake offset."""
    if intensity <= 0:
        return (0, 0)
    dx = random.randint(int(-intensity), int(intensity))
    dy = random.randint(int(-intensity), int(intensity))
    return (dx, dy)


def _draw_stroke_text(
    draw: ImageDraw.Draw,
    x: int, y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple = TEXT_WHITE,
    stroke_width: int = 4,
    stroke_fill: tuple = (0, 0, 0),
    anchor: str = "lt",
):
    """Draw text with thick black stroke for maximum readability."""
    draw.text((x, y), text, font=font, fill=fill,
              stroke_width=stroke_width, stroke_fill=stroke_fill, anchor=anchor)


def _centered_stroke_text(
    draw: ImageDraw.Draw,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple = TEXT_WHITE,
    stroke_width: int = 4,
):
    """Draw centered text with stroke."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    _draw_stroke_text(draw, x, y, text, font, fill, stroke_width)


def _apply_flash(img: Image.Image, intensity: float) -> Image.Image:
    """White flash overlay."""
    if intensity <= 0:
        return img
    overlay = Image.new("RGB", img.size, FLASH_WHITE)
    return Image.blend(img, overlay, min(intensity, 0.7))


def _apply_shake(img: Image.Image, dx: int, dy: int) -> Image.Image:
    """Apply screen shake by offsetting and cropping."""
    if dx == 0 and dy == 0:
        return img
    result = Image.new("RGB", img.size, BG)
    result.paste(img, (dx, dy))
    return result


def _composite_product_image(
    canvas: Image.Image,
    listing_img: Image.Image,
    y_start: int,
    y_end: int,
    alpha: float = 1.0,
) -> Image.Image:
    """Composite product image into a region with darkening."""
    region_h = y_end - y_start
    region_w = W

    img_ratio = listing_img.width / listing_img.height
    target_ratio = region_w / region_h

    if img_ratio > target_ratio:
        new_h = region_h
        new_w = int(new_h * img_ratio)
    else:
        new_w = region_w
        new_h = int(new_w / img_ratio)

    resized = listing_img.resize((new_w, new_h), Image.LANCZOS)
    cx = (new_w - region_w) // 2
    cy = (new_h - region_h) // 2
    cropped = resized.crop((cx, cy, cx + region_w, cy + region_h))

    # Darken heavily so text is readable
    overlay = Image.new("RGB", (region_w, region_h), BG)
    blended = Image.blend(cropped, overlay, 0.55)

    if alpha < 1.0:
        mask = Image.new("L", (region_w, region_h), int(255 * alpha))
        canvas.paste(blended, (0, y_start), mask)
    else:
        canvas.paste(blended, (0, y_start))

    return canvas


# ── Frame timeline for "The Steal" template ──
# Total: 10 seconds (300 frames at 30fps)
#
# [0.0-1.5s]  HOOK: "I found this for $XXX" + product image fade
# [1.5-3.5s]  BRAND + PIECE NAME reveal
# [3.5-5.5s]  MARKET VALUE (big number, anchoring)
# [5.5-7.0s]  DEAL PRICE with screen shake
# [7.0-9.0s]  PROFIT REVEAL with flash + shake
# [9.0-10.0s] CTA: "cop or drop?" + @handle

def _frame_t(frame: int, start_s: float, end_s: float) -> float:
    """Progress 0-1 within a time window."""
    sf, ef = start_s * FPS, end_s * FPS
    if frame < sf: return 0.0
    if frame >= ef: return 1.0
    return (frame - sf) / (ef - sf)


def render_steal_frame(
    frame: int,
    data: DealCardData,
    listing_img: Optional[Image.Image] = None,
) -> Image.Image:
    """Render one frame of 'The Steal' template."""

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    accent = get_brand_accent(data.brand)
    shake_dx, shake_dy = 0, 0
    flash = 0.0

    # ── Phase 1: Hook (0.0 - 1.5s) ──
    p1 = _frame_t(frame, 0.0, 1.2)
    if p1 > 0:
        # Product image fades in
        if listing_img:
            img_alpha = _ease_out(p1 * 2)
            img = _composite_product_image(img, listing_img, 200, 950, img_alpha)
            draw = ImageDraw.Draw(img)

            # Bottom gradient
            for gy in range(850, 950):
                ga = (gy - 850) / 100
                c = int(6 * ga + 6)
                draw.line([(0, gy), (W, gy)], fill=(c, c, c), width=1)

        # Hook text: "I found this for $XXX"
        hook_font = load_font(72, bold=True)
        hook_scale = _pop_scale(p1 * 1.5)
        if hook_scale > 0.1:
            hook_text = f"${data.buy_price:,.0f}"
            _centered_stroke_text(draw, 100, "I FOUND THIS FOR", load_font(36, bold=True), TEXT_WHITE, 3)
            # Big price number
            price_font = load_font(int(96 * hook_scale), bold=True)
            _centered_stroke_text(draw, 160, hook_text, price_font, TEXT_GOLD, 5)

    # ── Phase 2: Brand + piece (1.5 - 3.5s) ──
    p2 = _frame_t(frame, 1.3, 2.5)
    if p2 > 0:
        brand_scale = _pop_scale(p2)
        if brand_scale > 0.1:
            brand_font = load_font(int(64 * brand_scale), bold=True)
            _centered_stroke_text(draw, 1000, data.brand.upper(), brand_font, TEXT_WHITE, 5)

        piece_t = _frame_t(frame, 1.8, 3.0)
        if piece_t > 0:
            piece_alpha = _ease_out(piece_t)
            title_short = data.title[:35].upper()
            piece_font = load_font(36, bold=True)
            piece_color = tuple(int(c * piece_alpha) for c in LIGHT_GREY)
            _centered_stroke_text(draw, 1080, title_short, piece_font, piece_color, 3)

    # ── Phase 3: Market value anchor (3.5 - 5.5s) ──
    p3 = _frame_t(frame, 3.3, 4.5)
    if p3 > 0:
        # Label
        _centered_stroke_text(draw, 1200, "MARKET VALUE", load_font(28, bold=True), MID_GREY, 2)

        # Big market price (the anchor)
        market_scale = _pop_scale(p3)
        if market_scale > 0.1:
            mkt_font = load_font(int(120 * market_scale), bold=True)
            _centered_stroke_text(draw, 1250, f"${data.market_price:,.0f}", mkt_font, TEXT_WHITE, 6)

        # Comp count
        comp_t = _frame_t(frame, 3.8, 4.8)
        if comp_t > 0:
            comp_color = tuple(int(c * _ease_out(comp_t)) for c in MID_GREY)
            _centered_stroke_text(draw, 1400, f"{data.comp_count} sold comps on Grailed", load_font(26), comp_color, 2)

    # ── Phase 4: Deal price reveal with SHAKE (5.5 - 7.0s) ──
    p4 = _frame_t(frame, 5.3, 6.0)
    if p4 > 0:
        # Screen shake on impact
        shake_intensity = max(0, (1 - p4) * 15) if p4 < 0.5 else 0
        shake_dx, shake_dy = _shake_offset(shake_intensity)

        # Flash on first frames of reveal
        if p4 < 0.15:
            flash = (0.15 - p4) / 0.15 * 0.4

        # "LISTED FOR" label
        _centered_stroke_text(draw, 1200, "LISTED FOR", load_font(32, bold=True), TEXT_RED, 3)

        deal_scale = _pop_scale(p4 * 1.3)
        deal_font = load_font(int(130 * min(deal_scale, 1.0)), bold=True)
        _centered_stroke_text(draw, 1260, f"${data.buy_price:,.0f}", deal_font, TEXT_RED, 6)

        # Strikethrough on market price (shows both)
        if _frame_t(frame, 5.8, 6.5) > 0:
            mkt_text = f"${data.market_price:,.0f}"
            small_mkt = load_font(48)
            bbox = draw.textbbox((0, 0), mkt_text, font=small_mkt)
            tw = bbox[2] - bbox[0]
            mx = (W - tw) // 2
            _draw_stroke_text(draw, mx, 1420, mkt_text, small_mkt, MID_GREY, 2)
            # Strikethrough line
            draw.line([(mx - 5, 1445), (mx + tw + 5, 1445)], fill=TEXT_RED, width=4)

    # ── Phase 5: PROFIT REVEAL with big flash + shake (7.0 - 9.0s) ──
    p5 = _frame_t(frame, 6.8, 7.5)
    if p5 > 0:
        # Big flash
        if p5 < 0.2:
            flash = max(flash, (0.2 - p5) / 0.2 * 0.6)

        # Big shake
        shake_intensity = max(0, (1 - p5) * 20) if p5 < 0.4 else 0
        sdx, sdy = _shake_offset(shake_intensity)
        shake_dx += sdx
        shake_dy += sdy

        _centered_stroke_text(draw, 1180, "EST. PROFIT", load_font(32, bold=True), TEXT_GREEN, 3)

        profit_scale = _pop_scale(p5 * 1.2)
        profit_font = load_font(int(140 * min(profit_scale, 1.0)), bold=True)
        _centered_stroke_text(draw, 1240, f"+${data.profit:,.0f}", profit_font, TEXT_GREEN, 7)

        # Margin line
        margin_t = _frame_t(frame, 7.3, 8.0)
        if margin_t > 0:
            margin_alpha = _ease_out(margin_t)
            margin_color = tuple(int(c * margin_alpha) for c in TEXT_GREEN)
            _centered_stroke_text(draw, 1420, f"{data.margin * 100:.0f}% BELOW MARKET", load_font(36, bold=True), margin_color, 4)

    # ── Phase 6: CTA (9.0 - 10.0s) ──
    p6 = _frame_t(frame, 8.5, 9.5)
    if p6 > 0:
        cta_alpha = _ease_out(p6)
        cta_color = tuple(int(c * cta_alpha) for c in TEXT_WHITE)
        gold_color = tuple(int(c * cta_alpha) for c in TEXT_GOLD)

        _centered_stroke_text(draw, 1560, "COP OR DROP?", load_font(48, bold=True), cta_color, 4)
        _centered_stroke_text(draw, 1640, "Follow for daily deals", load_font(28), gold_color, 2)
        _centered_stroke_text(draw, 1700, "@archivearbitrage", load_font(32, bold=True), gold_color, 3)

    # ── Persistent: top bar + "DEAL ALERT" badge ──
    if frame > 5:
        bar_alpha = min(_frame_t(frame, 0.0, 0.3) * 2, 1.0)
        if bar_alpha > 0:
            bar_c = tuple(int(c * bar_alpha) for c in accent)
            draw.rectangle([(0, 0), (W, 5)], fill=bar_c)

    # ── Apply post-effects ──
    if flash > 0:
        img = _apply_flash(img, flash)
    if shake_dx != 0 or shake_dy != 0:
        img = _apply_shake(img, shake_dx, shake_dy)

    # Light grain
    arr = np.array(img).astype(np.int16)
    noise = np.random.normal(0, 6, arr.shape).astype(np.int16)
    img = Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))

    return img


# ── "Rapid-Fire" template: 3 deals in 9 seconds ──

def render_rapid_fire_frame(
    frame: int,
    deals: List[DealCardData],
) -> Image.Image:
    """Render one frame of the Rapid-Fire template (3 deals)."""

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    shake_dx, shake_dy = 0, 0
    flash = 0.0

    # Header: "DEAL ALERT" (always visible after 0.3s)
    header_t = _frame_t(frame, 0.0, 0.5)
    if header_t > 0:
        h_alpha = _ease_out(header_t)
        h_color = tuple(int(c * h_alpha) for c in TEXT_RED)
        _centered_stroke_text(draw, 80, "DEAL ALERT", load_font(56, bold=True), h_color, 5)

    # Three deals, each gets ~2.5 seconds
    deal_timings = [(0.5, 3.0), (3.0, 5.5), (5.5, 8.0)]

    for i, (start, end) in enumerate(deal_timings):
        if i >= len(deals):
            break
        d = deals[i]
        dt = _frame_t(frame, start, end)
        if dt <= 0:
            continue

        y_base = 250 + i * 500

        # Pop-in
        pop = _pop_scale(dt * 2)
        if pop < 0.1:
            continue

        # Shake on each deal entrance
        if dt < 0.15:
            si = (0.15 - dt) / 0.15 * 12
            sdx, sdy = _shake_offset(si)
            shake_dx += sdx
            shake_dy += sdy
            flash = max(flash, (0.15 - dt) / 0.15 * 0.25)

        # Deal number
        num_font = load_font(48, bold=True)
        _draw_stroke_text(draw, 60, y_base, f"#{i+1}", num_font, TEXT_GOLD, 4)

        # Brand
        brand_font = load_font(int(52 * min(pop, 1.0)), bold=True)
        _draw_stroke_text(draw, 140, y_base - 5, d.brand.upper(), brand_font, TEXT_WHITE, 4)

        # Title
        if dt > 0.2:
            title_font = load_font(28)
            _draw_stroke_text(draw, 140, y_base + 55, d.title[:40].upper(), title_font, MID_GREY, 2)

        # Prices (appear after pop)
        if dt > 0.3:
            price_t = (dt - 0.3) / 0.4
            price_alpha = _ease_out(min(price_t, 1.0))

            # Buy price
            buy_color = tuple(int(c * price_alpha) for c in TEXT_WHITE)
            buy_font = load_font(44, bold=True)
            _draw_stroke_text(draw, 140, y_base + 110, f"${d.buy_price:,.0f}", buy_font, buy_color, 3)

            # Arrow
            _draw_stroke_text(draw, 380, y_base + 110, "->", load_font(36, bold=True), MID_GREY, 2)

            # Market price
            mkt_color = tuple(int(c * price_alpha) for c in TEXT_GOLD)
            _draw_stroke_text(draw, 460, y_base + 110, f"${d.market_price:,.0f}", buy_font, mkt_color, 3)

        # Profit badge
        if dt > 0.5:
            profit_t = (dt - 0.5) / 0.3
            profit_pop = _pop_scale(min(profit_t, 1.0))
            if profit_pop > 0.1:
                profit_font = load_font(int(56 * min(profit_pop, 1.0)), bold=True)
                _draw_stroke_text(draw, 700, y_base + 100, f"+${d.profit:,.0f}", profit_font, TEXT_GREEN, 5)

        # Divider line
        if i < 2:
            line_w = int(900 * _ease_out(min(dt * 3, 1.0)))
            if line_w > 0:
                lx = (W - line_w) // 2
                draw.line([(lx, y_base + 200), (lx + line_w, y_base + 200)], fill=(30, 30, 30), width=2)

    # CTA at bottom (8.0 - 9.5s)
    cta_t = _frame_t(frame, 8.0, 9.0)
    if cta_t > 0:
        cta_a = _ease_out(cta_t)
        cta_c = tuple(int(c * cta_a) for c in TEXT_WHITE)
        gold_c = tuple(int(c * cta_a) for c in TEXT_GOLD)
        _centered_stroke_text(draw, 1700, "WHICH ONE ARE YOU GRABBING?", load_font(36, bold=True), cta_c, 4)
        _centered_stroke_text(draw, 1770, "@archivearbitrage", load_font(28, bold=True), gold_c, 3)

    # Post-effects
    if flash > 0:
        img = _apply_flash(img, flash)
    if shake_dx != 0 or shake_dy != 0:
        img = _apply_shake(img, shake_dx, shake_dy)

    # Grain
    arr = np.array(img).astype(np.int16)
    noise = np.random.normal(0, 5, arr.shape).astype(np.int16)
    img = Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))

    return img


# ── Main generation functions ──

def generate_steal_video(
    data: DealCardData,
    listing_img: Optional[Image.Image] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Generate a 'Steal' format video (single deal breakdown)."""
    total_frames = int(10.0 * FPS)
    return _render_video(
        lambda f: render_steal_frame(f, data, listing_img),
        total_frames,
        f"steal_{data.brand.lower().replace(' ', '_')[:15]}",
    )


def generate_rapid_fire_video(
    deals: List[DealCardData],
) -> Tuple[Optional[str], Optional[str]]:
    """Generate a 'Rapid-Fire' format video (3 deals)."""
    total_frames = int(9.5 * FPS)
    brand_slug = deals[0].brand.lower().replace(" ", "_")[:10] if deals else "multi"
    return _render_video(
        lambda f: render_rapid_fire_frame(f, deals[:3]),
        total_frames,
        f"rapid_{brand_slug}",
    )


def _render_video(
    render_fn,
    total_frames: int,
    name_prefix: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Render frames and compile to MP4."""
    tmp_dir = tempfile.mkdtemp(prefix="aa_v2_")

    try:
        logger.info(f"Rendering {total_frames} frames...")
        for i in range(total_frames):
            frame = render_fn(i)
            frame.save(os.path.join(tmp_dir, f"f_{i:04d}.jpg"), "JPEG", quality=88)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_file = f"v2_{name_prefix}_{timestamp}.mp4"
        thumb_file = f"v2_{name_prefix}_{timestamp}_thumb.jpg"
        video_path = str(QUEUE_DIR / video_file)
        thumb_path = str(QUEUE_DIR / thumb_file)

        # Thumbnail: frame at the profit reveal
        thumb_frame = int(7.2 * FPS)
        if thumb_frame < total_frames:
            thumb = render_fn(thumb_frame)
            thumb.save(thumb_path, "JPEG", quality=95)

        # ffmpeg compile
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", os.path.join(tmp_dir, "f_%04d.jpg"),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "26",
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={W}:{H}",
            "-movflags", "+faststart",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error(f"ffmpeg failed: {result.stderr[:300]}")
            return None, None

        size_mb = os.path.getsize(video_path) / 1024 / 1024
        logger.info(f"Video: {video_path} ({size_mb:.1f} MB)")
        return video_path, thumb_path

    except Exception as e:
        logger.error(f"Video gen failed: {e}", exc_info=True)
        return None, None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _fetch_image_sync(url: str) -> Optional[Image.Image]:
    if not url:
        return None
    try:
        import httpx
        with httpx.Client(timeout=10, follow_redirects=True) as c:
            r = c.get(url)
            if r.status_code == 200:
                return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        pass
    return None


# ── CLI ──
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    # Test: single "Steal" video
    print("Generating 'The Steal' video...\n")
    sample = DealCardData(
        title="Cross Patch Trucker Jacket",
        brand="Chrome Hearts",
        source="grailed",
        source_url="",
        buy_price=583,
        market_price=1499,
        profit=916,
        margin=0.61,
        fire_level=3,
        quality_score=82,
        comp_count=12,
        auth_confidence=0.89,
        tier="pro",
    )

    vp, tp = generate_steal_video(sample)
    if vp:
        print(f"Steal video: {vp}")
        if sys.platform == "darwin":
            subprocess.run(["open", vp], check=False)

    # Test: "Rapid-Fire" video
    print("\nGenerating 'Rapid-Fire' video...\n")
    deals = [
        DealCardData(title="DRKSHDW Jumbo Lace", brand="Rick Owens", source="grailed", source_url="",
                     buy_price=215, market_price=599, profit=384, margin=0.64, fire_level=2,
                     quality_score=71, comp_count=8, auth_confidence=0.85),
        DealCardData(title="Hedi Era Waxed Jeans", brand="Dior Homme", source="grailed", source_url="",
                     buy_price=265, market_price=1169, profit=904, margin=0.77, fire_level=3,
                     quality_score=85, comp_count=12, auth_confidence=0.91),
        DealCardData(title="Archive Denim Jacket", brand="Raf Simons", source="poshmark", source_url="",
                     buy_price=197, market_price=599, profit=402, margin=0.67, fire_level=3,
                     quality_score=78, comp_count=6, auth_confidence=0.82),
    ]

    vp2, tp2 = generate_rapid_fire_video(deals)
    if vp2:
        print(f"Rapid-fire video: {vp2}")
        if sys.platform == "darwin":
            subprocess.run(["open", vp2], check=False)

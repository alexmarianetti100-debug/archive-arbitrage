"""
Viral video generator v3 — "Raw" style.

Research finding: polished graphics = ad = scroll past.
What goes viral in archive fashion TikTok:
  - Screen recordings of actual listings
  - Raw listing photos with TikTok-native text overlays
  - Feels like a person found this, not a system
  - Simulated "phone screen" showing real platform UI

This generator creates videos that look like someone is:
1. Scrolling Grailed and finding a deal
2. Showing the listing price
3. Then revealing what it's actually worth (comp data)
4. Mind-blown reaction via text

Formats:
  A: "The Find" — simulated Grailed listing discovery
  B: "The Receipt" — showing buy price vs sell price screenshot
  C: "3 Deals Right Now" — rapid listing screenshots

Key design rules:
  - Listing photo is THE visual (full bleed, minimal overlay)
  - Text looks like TikTok's native text tool (rounded pill bg, white text)
  - No scanlines, no grain, no editorial effects — those scream "generated"
  - Slight imperfection: text not perfectly centered, casual sizing
  - Phone-screen framing (status bar, rounded corners)
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
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .design import load_font, get_brand_accent
from .deal_card import DealCardData

logger = logging.getLogger("auto_content.video_v3")

W, H = 1080, 1920
FPS = 30
QUEUE_DIR = Path(__file__).parent / "queue" / "pending"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

# ── Colors (TikTok-native feel) ──
PHONE_BG = (0, 0, 0)
LISTING_BG = (18, 18, 18)
WHITE = (255, 255, 255)
GREY = (170, 170, 170)
DARK_GREY = (100, 100, 100)
PRICE_GREEN = (34, 197, 94)
PRICE_RED = (239, 68, 68)
PILL_BG = (0, 0, 0, 200)  # Semi-transparent black
PILL_WHITE = (255, 255, 255, 230)


def _ease(t: float) -> float:
    t = max(0, min(1, t))
    return 1 - (1 - t) ** 3

def _bounce(t: float) -> float:
    t = max(0, min(1, t))
    if t < 0.7:
        return (t / 0.7) * 1.1
    return 1.0 + (1.0 - t) / 0.3 * 0.1

def _ft(frame: int, start: float, end: float) -> float:
    s, e = start * FPS, end * FPS
    if frame < s: return 0.0
    if frame >= e: return 1.0
    return (frame - s) / (e - s)


def _draw_pill(
    draw: ImageDraw.Draw,
    x: int, y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    text_color: tuple = WHITE,
    bg_color: tuple = (0, 0, 0),
    bg_alpha: float = 0.75,
    padding_x: int = 24,
    padding_y: int = 12,
) -> Tuple[int, int]:
    """Draw a TikTok-style pill text overlay. Returns (width, height)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pw, ph = tw + padding_x * 2, th + padding_y * 2
    radius = ph // 2

    # Semi-transparent pill background
    # Since PIL doesn't support alpha on RGB, we darken the area
    overlay_color = tuple(int(c * (1 - bg_alpha)) for c in bg_color[:3])
    draw.rounded_rectangle(
        [(x, y), (x + pw, y + ph)],
        radius=radius,
        fill=overlay_color,
    )
    draw.text((x + padding_x, y + padding_y), text, font=font, fill=text_color)
    return pw, ph


def _draw_pill_centered(
    draw: ImageDraw.Draw,
    y: int,
    text: str,
    font: ImageFont.FreeTypeFont,
    text_color: tuple = WHITE,
    bg_alpha: float = 0.75,
) -> int:
    """Draw a centered pill. Returns pill width."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    pw = tw + 48
    x = (W - pw) // 2
    _draw_pill(draw, x, y, text, font, text_color, bg_alpha=bg_alpha)
    return pw


def _composite_listing_photo(
    canvas: Image.Image,
    photo: Image.Image,
    y_start: int = 0,
    y_end: int = 1400,
    darken: float = 0.15,
) -> Image.Image:
    """Put the listing photo as hero image — minimal darkening."""
    rw, rh = W, y_end - y_start
    img_ratio = photo.width / photo.height
    target_ratio = rw / rh

    if img_ratio > target_ratio:
        new_h = rh
        new_w = int(new_h * img_ratio)
    else:
        new_w = rw
        new_h = int(new_w / img_ratio)

    resized = photo.resize((new_w, new_h), Image.LANCZOS)
    cx, cy = (new_w - rw) // 2, (new_h - rh) // 2
    cropped = resized.crop((cx, cy, cx + rw, cy + rh))

    if darken > 0:
        overlay = Image.new("RGB", (rw, rh), PHONE_BG)
        cropped = Image.blend(cropped, overlay, darken)

    canvas.paste(cropped, (0, y_start))
    return canvas


def _draw_status_bar(draw: ImageDraw.Draw):
    """Draw a fake phone status bar for screen-recording feel."""
    bar_font = load_font(14)
    # Time
    draw.text((32, 12), "9:41", font=bar_font, fill=WHITE)
    # Battery/signal indicators (simple)
    draw.text((W - 80, 12), "100%", font=bar_font, fill=WHITE)
    # Subtle top bar background
    for y in range(0, 44):
        alpha = max(0, 1 - y / 44)
        c = int(alpha * 30)
        draw.line([(0, y), (W, y)], fill=(c, c, c), width=1)


def _draw_bottom_gradient(draw: ImageDraw.Draw, y_start: int, y_end: int):
    """Gradient from transparent to black at bottom of image."""
    for y in range(y_start, y_end):
        progress = (y - y_start) / (y_end - y_start)
        c = int(progress * progress * 255)
        draw.line([(0, y), (W, y)], fill=(0, 0, 0), width=1)


# ══════════════════════════════════════════════════════════
# FORMAT A: "The Find" — simulated Grailed listing discovery
# ══════════════════════════════════════════════════════════
#
# [0-1s]    Black screen, text: "found this on Grailed for $XXX"
# [1-3s]    Listing photo fills screen (zoom in slightly)
# [3-4.5s]  Brand + item name pills appear over photo
# [4.5-6s]  "what it's actually worth" text
# [6-8s]    Market value reveal: "$X,XXX" in big green text
# [8-9.5s]  Profit line: "+$XXX profit"
# [9.5-11s] "would you cop?" + @handle

def render_find_frame(
    frame: int,
    data: DealCardData,
    listing_img: Optional[Image.Image] = None,
) -> Image.Image:
    """Render 'The Find' format — looks like someone found a Grailed listing."""

    total_sec = 11.0
    img = Image.new("RGB", (W, H), PHONE_BG)
    draw = ImageDraw.Draw(img)

    # ── Persistent: listing photo (appears at 0.8s, stays) ──
    photo_t = _ft(frame, 0.5, 1.5)
    if photo_t > 0 and listing_img:
        # Slight zoom effect
        zoom = 1.0 + 0.03 * _ease(min(photo_t * 2, 1.0))
        zoomed = listing_img.resize(
            (int(listing_img.width * zoom), int(listing_img.height * zoom)),
            Image.LANCZOS,
        )
        img = _composite_listing_photo(img, zoomed, 0, 1400, darken=0.2)
        draw = ImageDraw.Draw(img)
        _draw_bottom_gradient(draw, 1100, 1400)
    elif photo_t > 0:
        # No listing image — dark placeholder
        draw.rectangle([(0, 0), (W, 1400)], fill=LISTING_BG)

    # Status bar (always)
    _draw_status_bar(draw)

    # ── Phase 1: Hook text (0-1.5s) ──
    p1 = _ft(frame, 0.0, 1.2)
    if p1 > 0 and p1 < 1.0:
        hook_alpha = _ease(p1) if p1 < 0.8 else _ease(1 - (p1 - 0.8) / 0.2)
        if hook_alpha > 0.05:
            hook_font = load_font(42, bold=True)
            price_font = load_font(64, bold=True)
            hook_color = tuple(int(255 * hook_alpha) for _ in range(3))
            gold_color = tuple(int(c * hook_alpha) for c in (212, 168, 83))

            _draw_pill_centered(draw, H // 2 - 80, f"found this on {data.source.title()}", hook_font, hook_color)
            _draw_pill_centered(draw, H // 2, f"${data.buy_price:,.0f}", price_font, gold_color)

    # ── Phase 2: Brand + piece name (3-5s) ──
    p2 = _ft(frame, 2.5, 3.5)
    if p2 > 0:
        pill_alpha = _ease(min(p2 * 2, 1.0))
        brand_font = load_font(38, bold=True)
        title_font = load_font(28)

        brand_color = tuple(int(255 * pill_alpha) for _ in range(3))
        title_color = tuple(int(200 * pill_alpha) for _ in range(3))

        _draw_pill_centered(draw, 1420, data.brand.upper(), brand_font, brand_color)

        title_short = data.title[:45]
        _draw_pill_centered(draw, 1490, title_short, title_font, title_color, bg_alpha=0.6)

    # ── Phase 3: "what it's actually worth" (4.5-6s) ──
    p3 = _ft(frame, 4.5, 5.5)
    if p3 > 0:
        worth_alpha = _ease(min(p3 * 2, 1.0))
        worth_font = load_font(32, bold=True)
        worth_color = tuple(int(255 * worth_alpha) for _ in range(3))
        _draw_pill_centered(draw, 1580, "what it's actually worth", worth_font, worth_color, bg_alpha=0.8)

    # ── Phase 4: Market value reveal (6-8s) ──
    p4 = _ft(frame, 5.8, 6.8)
    if p4 > 0:
        reveal_scale = _bounce(p4)
        if reveal_scale > 0.1:
            size = int(80 * min(reveal_scale, 1.0))
            market_font = load_font(size, bold=True)
            comp_font = load_font(22)

            _draw_pill_centered(draw, 1570, f"${data.market_price:,.0f}", market_font, WHITE)

            if _ft(frame, 6.3, 7.0) > 0:
                comp_alpha = _ease(_ft(frame, 6.3, 7.0))
                comp_color = tuple(int(170 * comp_alpha) for _ in range(3))
                _draw_pill_centered(draw, 1660, f"based on {data.comp_count} sold comps", comp_font, comp_color, bg_alpha=0.5)

    # ── Phase 5: Profit line (8-9.5s) ──
    p5 = _ft(frame, 7.8, 8.5)
    if p5 > 0:
        profit_scale = _bounce(p5)
        if profit_scale > 0.1:
            psize = int(72 * min(profit_scale, 1.0))
            profit_font = load_font(psize, bold=True)
            _draw_pill_centered(draw, 1700, f"+${data.profit:,.0f} profit", profit_font, PRICE_GREEN)

            margin_t = _ft(frame, 8.3, 9.0)
            if margin_t > 0:
                m_alpha = _ease(margin_t)
                m_color = tuple(int(c * m_alpha) for c in PRICE_GREEN)
                m_font = load_font(28, bold=True)
                _draw_pill_centered(draw, 1790, f"{data.margin * 100:.0f}% below market", m_font, m_color, bg_alpha=0.5)

    # ── Phase 6: CTA (9.5-11s) ──
    p6 = _ft(frame, 9.5, 10.5)
    if p6 > 0:
        cta_alpha = _ease(p6)
        cta_color = tuple(int(255 * cta_alpha) for _ in range(3))
        handle_color = tuple(int(c * cta_alpha) for c in (212, 168, 83))

        _draw_pill_centered(draw, 1700, "would you cop?", load_font(40, bold=True), cta_color)
        _draw_pill_centered(draw, 1780, "@archivearbitrage", load_font(28, bold=True), handle_color, bg_alpha=0.5)

    return img


# ══════════════════════════════════════════════════════════
# FORMAT B: "3 Deals Right Now" — rapid listing screenshots
# ══════════════════════════════════════════════════════════

def render_three_deals_frame(
    frame: int,
    deals: List[DealCardData],
    images: Optional[List[Image.Image]] = None,
) -> Image.Image:
    """3 deals rapid-fire — each gets their listing photo."""

    img = Image.new("RGB", (W, H), PHONE_BG)
    draw = ImageDraw.Draw(img)
    _draw_status_bar(draw)

    # Header (always visible)
    header_t = _ft(frame, 0.0, 0.5)
    if header_t > 0:
        ha = _ease(header_t)
        hc = tuple(int(255 * ha) for _ in range(3))
        _draw_pill_centered(draw, 60, "3 deals on Grailed right now", load_font(32, bold=True), hc)

    # Each deal: 3 seconds
    deal_windows = [(0.5, 3.5), (3.5, 6.5), (6.5, 9.5)]
    imgs = images or [None, None, None]

    for i, (start, end) in enumerate(deal_windows):
        if i >= len(deals):
            break
        d = deals[i]
        dt = _ft(frame, start, end)
        if dt <= 0:
            continue

        # Listing photo (swipe in from right)
        listing = imgs[i] if i < len(imgs) else None
        slide_x = int((1 - _ease(min(dt * 3, 1.0))) * W)

        if listing and dt > 0:
            # Composite listing photo with slide offset
            temp = Image.new("RGB", (W, H), PHONE_BG)
            temp = _composite_listing_photo(temp, listing, 140, 1300, darken=0.25)
            _draw_bottom_gradient(ImageDraw.Draw(temp), 1000, 1300)
            # Slide effect
            if slide_x > 0:
                visible = temp.crop((slide_x, 0, W, H))
                img.paste(visible, (slide_x, 0))
            else:
                img = temp
            draw = ImageDraw.Draw(img)
            _draw_status_bar(draw)
            # Re-draw header
            _draw_pill_centered(draw, 60, "3 deals on Grailed right now", load_font(32, bold=True), WHITE)

        # Deal number badge
        if dt > 0.1:
            num_font = load_font(48, bold=True)
            _draw_pill(draw, 40, 130, f"#{i+1}", num_font, WHITE, bg_alpha=0.8)

        # Brand + price overlay at bottom
        if dt > 0.2:
            info_alpha = _ease(min((dt - 0.2) * 3, 1.0))
            info_c = tuple(int(255 * info_alpha) for _ in range(3))
            green_c = tuple(int(c * info_alpha) for c in PRICE_GREEN)
            grey_c = tuple(int(170 * info_alpha) for _ in range(3))

            _draw_pill_centered(draw, 1320, d.brand.upper(), load_font(36, bold=True), info_c)
            _draw_pill_centered(draw, 1390, d.title[:40], load_font(24), grey_c, bg_alpha=0.5)

            # Price → value
            if dt > 0.35:
                _draw_pill(draw, 80, 1460, f"${d.buy_price:,.0f}", load_font(44, bold=True), info_c, bg_alpha=0.8)
                _draw_pill(draw, 340, 1465, "->", load_font(32), grey_c, bg_alpha=0.0)
                _draw_pill(draw, 430, 1460, f"${d.market_price:,.0f}", load_font(44, bold=True), (212, 168, 83), bg_alpha=0.8)

            # Profit
            if dt > 0.5:
                profit_pop = _bounce(min((dt - 0.5) * 3, 1.0))
                if profit_pop > 0.1:
                    ps = int(52 * min(profit_pop, 1.0))
                    _draw_pill(draw, 680, 1455, f"+${d.profit:,.0f}", load_font(ps, bold=True), green_c, bg_alpha=0.8)

    # CTA (9.5-10.5s)
    cta_t = _ft(frame, 9.5, 10.5)
    if cta_t > 0:
        ca = _ease(cta_t)
        cc = tuple(int(255 * ca) for _ in range(3))
        gc = tuple(int(c * ca) for c in (212, 168, 83))
        _draw_pill_centered(draw, 1700, "which one would you grab?", load_font(36, bold=True), cc)
        _draw_pill_centered(draw, 1780, "follow for daily finds", load_font(26), gc, bg_alpha=0.5)

    return img


# ══════════════════════════════════════════════════════════
# Main generation functions
# ══════════════════════════════════════════════════════════

def _compile(render_fn, total_frames: int, prefix: str) -> Tuple[Optional[str], Optional[str]]:
    tmp = tempfile.mkdtemp(prefix="aa_v3_")
    try:
        logger.info(f"Rendering {total_frames} frames ({prefix})...")
        for i in range(total_frames):
            render_fn(i).save(os.path.join(tmp, f"f_{i:04d}.jpg"), "JPEG", quality=88)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        vp = str(QUEUE_DIR / f"v3_{prefix}_{ts}.mp4")
        tp = str(QUEUE_DIR / f"v3_{prefix}_{ts}_thumb.jpg")

        # Thumbnail at profit reveal
        thumb_frame = min(int(8.0 * FPS), total_frames - 1)
        render_fn(thumb_frame).save(tp, "JPEG", quality=95)

        subprocess.run([
            "ffmpeg", "-y", "-framerate", str(FPS),
            "-i", os.path.join(tmp, "f_%04d.jpg"),
            "-c:v", "libx264", "-preset", "fast", "-crf", "26",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", vp,
        ], capture_output=True, timeout=120, check=True)

        size = os.path.getsize(vp) / 1024 / 1024
        logger.info(f"Video: {vp} ({size:.1f} MB)")
        return vp, tp
    except Exception as e:
        logger.error(f"Failed: {e}")
        return None, None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def generate_find_video(
    data: DealCardData,
    listing_img: Optional[Image.Image] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Generate 'The Find' video (simulated Grailed discovery)."""
    frames = int(11.0 * FPS)
    slug = data.brand.lower().replace(" ", "_")[:15]
    return _compile(lambda f: render_find_frame(f, data, listing_img), frames, f"find_{slug}")


def generate_three_deals_video(
    deals: List[DealCardData],
    images: Optional[List[Image.Image]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Generate '3 Deals' rapid-fire video."""
    frames = int(11.0 * FPS)
    return _compile(lambda f: render_three_deals_frame(f, deals[:3], images), frames, f"3deals")


# ── CLI ──
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    print("=== V3: 'The Find' (Chrome Hearts) ===\n")
    sample = DealCardData(
        title="Cross Patch Trucker Jacket",
        brand="Chrome Hearts",
        source="grailed",
        source_url="",
        buy_price=583, market_price=1499, profit=916, margin=0.61,
        fire_level=3, quality_score=82, comp_count=12, auth_confidence=0.89,
    )
    vp, tp = generate_find_video(sample)
    if vp:
        print(f"Video: {vp}")
        if sys.platform == "darwin":
            subprocess.run(["open", vp], check=False)

    print("\n=== V3: '3 Deals' (Rapid-Fire) ===\n")
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
    vp2, tp2 = generate_three_deals_video(deals)
    if vp2:
        print(f"Video: {vp2}")
        if sys.platform == "darwin":
            subprocess.run(["open", vp2], check=False)

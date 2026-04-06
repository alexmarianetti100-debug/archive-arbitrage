"""
Branded video generator — "The System" format.

Creative direction: faceless, brand-forward. The bot is the protagonist.
Archive Arbitrage IS the machine. Dark, data-dense, satisfying animations.
Every video is instantly recognizable as the brand.

Visual language:
  - Black background with subtle animated grid lines
  - Gold accent (#D4AF37) for brand elements
  - Green (#22C55E) for profit/positive
  - White for primary data
  - Monospace font for data, sans-serif bold for headlines
  - Persistent "ARCHIVE ARBITRAGE" header with live indicator dot
  - Data points animate in with satisfying snap/slide
  - Profit counter ticks up from $0 (slot machine dopamine)
  - Product image in a bordered frame (not full-bleed)

Templates:
  A: "System Alert" — single deal detected, data breakdown
  B: "Daily Scanner" — 3 deals with scanning animation
"""

from __future__ import annotations

import io
import logging
import math
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

from .design import load_font
from .deal_card import DealCardData

logger = logging.getLogger("auto_content.video_brand")

W, H = 1080, 1920
FPS = 30
QUEUE_DIR = Path(__file__).parent / "queue" / "pending"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

# ── Brand palette ──
BG = (6, 6, 6)
GRID_COLOR = (16, 16, 16)
GRID_ACCENT = (22, 22, 22)
GOLD = (212, 175, 55)
DIM_GOLD = (120, 100, 35)
WHITE = (240, 237, 232)
GREY = (120, 120, 120)
DIM_GREY = (60, 60, 60)
GREEN = (34, 197, 94)
BRIGHT_GREEN = (80, 230, 130)
RED = (200, 55, 50)
LIVE_RED = (239, 68, 68)
MONO_BG = (14, 14, 14)


# ── Animation ──

def _ease(t): return max(0, min(1, 1 - (1 - max(0, min(1, t))) ** 3))
def _snap(t):
    """Snappy overshoot for data reveals."""
    t = max(0, min(1, t))
    if t < 0.6: return (t / 0.6) ** 2 * 1.12
    if t < 0.85: return 1.12 - (t - 0.6) * 0.48
    return 1.0

def _ft(frame, start, end):
    s, e = start * FPS, end * FPS
    if frame < s: return 0.0
    if frame >= e: return 1.0
    return (frame - s) / (e - s)

def _counter_value(target, progress):
    """Ticking counter: overshoots slightly then settles."""
    if progress >= 1: return target
    raw = target * _ease(progress * 1.2)
    # Add slight jitter in the counting phase
    if progress < 0.8:
        jitter = random.randint(-2, 2) if progress > 0.1 else 0
        return max(0, int(raw) + jitter)
    return int(raw)


# ── Drawing helpers ──

def _draw_grid(draw, frame):
    """Subtle animated grid background — feels like a system/dashboard."""
    # Horizontal lines
    offset = (frame * 0.3) % 40
    for y in range(0, H + 40, 40):
        yy = int(y - offset)
        if 0 <= yy < H:
            draw.line([(0, yy), (W, yy)], fill=GRID_COLOR, width=1)
    # Vertical lines
    for x in range(0, W + 40, 40):
        draw.line([(x, 0), (x, H)], fill=GRID_COLOR, width=1)
    # Accent lines (brighter, fewer)
    for y in range(0, H + 200, 200):
        yy = int(y - offset * 5) % H
        draw.line([(0, yy), (W, yy)], fill=GRID_ACCENT, width=1)


def _draw_header(draw, frame):
    """Persistent brand header with live indicator."""
    # Background bar
    draw.rectangle([(0, 0), (W, 56)], fill=(10, 10, 10))
    draw.line([(0, 56), (W, 56)], fill=(30, 30, 30), width=1)

    # Brand name
    brand_font = load_font(16, bold=True)
    draw.text((24, 20), "ARCHIVE ARBITRAGE", font=brand_font, fill=GOLD)

    # Live dot (pulsing)
    pulse = 0.5 + 0.5 * math.sin(frame * 0.15)
    dot_r = int(4 + pulse * 2)
    dot_color = tuple(int(c * (0.6 + pulse * 0.4)) for c in LIVE_RED)
    cx, cy = W - 60, 28
    draw.ellipse([(cx - dot_r, cy - dot_r), (cx + dot_r, cy + dot_r)], fill=dot_color)
    draw.text((W - 48, 20), "LIVE", font=load_font(14, bold=True), fill=LIVE_RED)


def _draw_data_row(draw, x, y, label, value, font_size=36, label_color=GREY, value_color=WHITE, alpha=1.0):
    """Draw a label: value data row."""
    label_font = load_font(14)
    value_font = load_font(font_size, bold=True)
    lc = tuple(int(c * alpha) for c in label_color)
    vc = tuple(int(c * alpha) for c in value_color)
    draw.text((x, y), label.upper(), font=label_font, fill=lc)
    draw.text((x, y + 20), str(value), font=value_font, fill=vc)


def _draw_product_frame(canvas, draw, listing_img, x, y, w, h, alpha=1.0):
    """Draw the product image in a bordered frame."""
    if not listing_img:
        draw.rectangle([(x, y), (x + w, y + h)], fill=MONO_BG, outline=(30, 30, 30), width=1)
        return

    # Resize to fit
    img_ratio = listing_img.width / listing_img.height
    frame_ratio = w / h
    if img_ratio > frame_ratio:
        new_h = h
        new_w = int(new_h * img_ratio)
    else:
        new_w = w
        new_h = int(new_w / img_ratio)
    resized = listing_img.resize((new_w, new_h), Image.LANCZOS)
    cx = (new_w - w) // 2
    cy = (new_h - h) // 2
    cropped = resized.crop((cx, cy, cx + w, cy + h))

    if alpha < 1.0:
        mask = Image.new("L", (w, h), int(255 * alpha))
        canvas.paste(cropped, (x, y), mask)
    else:
        canvas.paste(cropped, (x, y))

    # Border
    border_color = tuple(int(c * alpha) for c in GOLD)
    draw_after = ImageDraw.Draw(canvas)
    draw_after.rectangle([(x, y), (x + w, y + h)], outline=border_color, width=2)
    return draw_after


def _draw_progress_bar(draw, x, y, w, h, progress, fill_color=GREEN, bg_color=MONO_BG, alpha=1.0):
    """Animated progress/confidence bar."""
    bgc = tuple(int(c * alpha) for c in bg_color)
    fc = tuple(int(c * alpha) for c in fill_color)
    draw.rounded_rectangle([(x, y), (x + w, y + h)], radius=h // 2, fill=bgc)
    filled_w = int(w * max(0, min(progress, 1.0)))
    if filled_w > 0:
        draw.rounded_rectangle([(x, y), (x + filled_w, y + h)], radius=h // 2, fill=fc)


# ══════════════════════════════════════════════════════════
# TEMPLATE A: "System Alert"
# ══════════════════════════════════════════════════════════
#
# [0-1.5s]   Grid bg + header + "DEAL DETECTED" flash
# [1.5-3.5s] Product image slides into frame + brand/title
# [3.5-5.5s] Data column animates: price, market value, comps, auth
# [5.5-7.5s] Profit counter ticks up from $0 to final
# [7.5-9.0s] Summary line + margin
# [9.0-10.5s] Brand CTA: "Deals like this. Every day."

def render_system_alert(
    frame: int,
    data: DealCardData,
    listing_img: Optional[Image.Image] = None,
) -> Image.Image:

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _draw_grid(draw, frame)
    _draw_header(draw, frame)

    # ── Phase 1: "DEAL DETECTED" (0 - 1.5s) ──
    p1 = _ft(frame, 0.2, 1.2)
    if p1 > 0:
        # Flash effect on first few frames
        if p1 < 0.15:
            flash_a = (0.15 - p1) / 0.15 * 0.3
            overlay = Image.new("RGB", (W, H), GOLD)
            img = Image.blend(img, overlay, flash_a)
            draw = ImageDraw.Draw(img)
            _draw_grid(draw, frame)
            _draw_header(draw, frame)

        alert_alpha = _ease(min(p1 * 2, 1.0))
        ac = tuple(int(c * alert_alpha) for c in GOLD)

        # Horizontal scan line
        scan_y = 80 + int(_ease(p1) * 30)
        draw.line([(0, scan_y), (W, scan_y)], fill=ac, width=1)

        # "DEAL DETECTED" text
        alert_font = load_font(52, bold=True)
        bbox = draw.textbbox((0, 0), "DEAL DETECTED", font=alert_font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, 100), "DEAL DETECTED", font=alert_font, fill=ac)

        # Subtitle
        if p1 > 0.4:
            sub_a = _ease((p1 - 0.4) / 0.3)
            sc = tuple(int(c * sub_a) for c in GREY)
            sub_font = load_font(18)
            sub_text = f"SCANNING {data.source.upper()} • {datetime.now().strftime('%H:%M:%S')}"
            bbox2 = draw.textbbox((0, 0), sub_text, font=sub_font)
            tw2 = bbox2[2] - bbox2[0]
            draw.text(((W - tw2) // 2, 165), sub_text, font=sub_font, fill=sc)

    # ── Phase 2: Product image + brand (1.5 - 3.5s) ──
    p2 = _ft(frame, 1.3, 2.8)
    if p2 > 0:
        img_alpha = _ease(min(p2 * 1.5, 1.0))

        # Product frame (centered, with border)
        frame_w, frame_h = 600, 600
        frame_x = (W - frame_w) // 2
        frame_y = 220

        # Slide up effect
        slide_offset = int((1 - _ease(min(p2 * 2, 1.0))) * 40)
        frame_y += slide_offset

        new_draw = _draw_product_frame(img, draw, listing_img, frame_x, frame_y, frame_w, frame_h, img_alpha)
        if new_draw:
            draw = new_draw

        # Brand + title below image
        if p2 > 0.3:
            text_a = _ease((p2 - 0.3) / 0.4)
            brand_font = load_font(40, bold=True)
            title_font = load_font(22)
            bc = tuple(int(c * text_a) for c in WHITE)
            tc = tuple(int(c * text_a) for c in GREY)

            brand_text = data.brand.upper()
            bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
            tw = bbox[2] - bbox[0]
            draw.text(((W - tw) // 2, 850), brand_text, font=brand_font, fill=bc)

            title_text = data.title[:45]
            bbox2 = draw.textbbox((0, 0), title_text, font=title_font)
            tw2 = bbox2[2] - bbox2[0]
            draw.text(((W - tw2) // 2, 900), title_text, font=title_font, fill=tc)

    # ── Phase 3: Data column (3.5 - 5.5s) ──
    data_x = 80
    data_base_y = 960

    # Each row animates in sequence
    rows = [
        (3.3, "Listed Price", f"${data.buy_price:,.0f}", WHITE, 40),
        (3.7, "Market Value", f"${data.market_price:,.0f}", GOLD, 40),
        (4.1, "Sold Comps", f"{data.comp_count} verified", WHITE, 32),
        (4.5, "Auth Score", None, None, 0),  # Special: progress bar
    ]

    for i, (start_t, label, value, color, size) in enumerate(rows):
        rt = _ft(frame, start_t, start_t + 0.6)
        if rt <= 0:
            continue

        row_y = data_base_y + i * 80
        row_alpha = _snap(rt)

        # Slide in from left
        slide_x = data_x - int((1 - _ease(min(rt * 2, 1.0))) * 60)

        if value:  # Normal data row
            _draw_data_row(draw, slide_x, row_y, label, value, size,
                          GREY, color, row_alpha)
        else:  # Auth bar
            lc = tuple(int(c * row_alpha) for c in GREY)
            draw.text((slide_x, row_y), "AUTH CONFIDENCE", font=load_font(14), fill=lc)
            bar_progress = data.auth_confidence * _ease(min(rt * 1.5, 1.0))
            _draw_progress_bar(draw, slide_x, row_y + 24, 400, 16, bar_progress,
                             GREEN if data.auth_confidence > 0.7 else GOLD, alpha=row_alpha)
            # Percentage text
            pct = f"{int(data.auth_confidence * 100 * _ease(min(rt * 1.5, 1.0)))}%"
            pc = tuple(int(c * row_alpha) for c in WHITE)
            draw.text((slide_x + 420, row_y + 20), pct, font=load_font(22, bold=True), fill=pc)

    # ── Phase 4: Profit counter (5.5 - 7.5s) ──
    p4 = _ft(frame, 5.3, 7.0)
    if p4 > 0:
        profit_y = 1340

        # Divider line
        line_w = int(920 * _ease(min(p4 * 3, 1.0)))
        if line_w > 0:
            lx = (W - line_w) // 2
            draw.line([(lx, profit_y), (lx + line_w, profit_y)], fill=GOLD, width=1)

        # Label
        if p4 > 0.1:
            la = _ease((p4 - 0.1) / 0.3)
            lc = tuple(int(c * la) for c in GREY)
            draw.text((80, profit_y + 20), "ESTIMATED PROFIT", font=load_font(16), fill=lc)

        # Ticking counter
        if p4 > 0.2:
            counter_progress = min((p4 - 0.2) / 0.6, 1.0)
            displayed = _counter_value(int(data.profit), counter_progress)
            profit_font = load_font(88, bold=True)
            gc = tuple(int(c * _ease(min(p4 * 2, 1.0))) for c in GREEN)
            profit_text = f"+${displayed:,}"
            bbox = draw.textbbox((0, 0), profit_text, font=profit_font)
            tw = bbox[2] - bbox[0]
            draw.text(((W - tw) // 2, profit_y + 45), profit_text, font=profit_font, fill=gc)

        # Margin
        if p4 > 0.7:
            ma = _ease((p4 - 0.7) / 0.2)
            mc = tuple(int(c * ma) for c in GREEN)
            margin_text = f"{data.margin * 100:.0f}% BELOW MARKET"
            margin_font = load_font(24, bold=True)
            bbox = draw.textbbox((0, 0), margin_text, font=margin_font)
            tw = bbox[2] - bbox[0]
            draw.text(((W - tw) // 2, profit_y + 155), margin_text, font=margin_font, fill=mc)

    # ── Phase 5: Brand CTA (9.0 - 10.5s) ──
    p5 = _ft(frame, 8.5, 10.0)
    if p5 > 0:
        cta_y = 1560
        cta_a = _ease(p5)

        # Divider
        lw = int(600 * _ease(min(p5 * 3, 1.0)))
        if lw > 0:
            lx = (W - lw) // 2
            draw.line([(lx, cta_y), (lx + lw, cta_y)], fill=(30, 30, 30), width=1)

        # CTA text
        gc = tuple(int(c * cta_a) for c in GOLD)
        wc = tuple(int(c * cta_a) for c in WHITE)
        dc = tuple(int(c * cta_a) for c in GREY)

        cta_font = load_font(28, bold=True)
        cta_text = "DEALS LIKE THIS. EVERY DAY."
        bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, cta_y + 30), cta_text, font=cta_font, fill=wc)

        # Handle
        handle_font = load_font(22, bold=True)
        handle = "@archivearbitrage"
        bbox = draw.textbbox((0, 0), handle, font=handle_font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, cta_y + 75), handle, font=handle_font, fill=gc)

        # Subtle tagline
        tag_font = load_font(16)
        tag = "7 platforms. 40+ brands. 24/7."
        bbox = draw.textbbox((0, 0), tag, font=tag_font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, cta_y + 115), tag, font=tag_font, fill=dc)

    return img


# ══════════════════════════════════════════════════════════
# TEMPLATE B: "Daily Scanner" — 3 deals, scanning animation
# ══════════════════════════════════════════════════════════

def render_daily_scanner(
    frame: int,
    deals: List[DealCardData],
    images: Optional[List[Image.Image]] = None,
) -> Image.Image:

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _draw_grid(draw, frame)
    _draw_header(draw, frame)

    imgs = images or [None] * 3

    # ── "DAILY SCAN COMPLETE" header (0 - 1s) ──
    p0 = _ft(frame, 0.2, 1.0)
    if p0 > 0:
        ha = _ease(min(p0 * 2, 1.0))
        hc = tuple(int(c * ha) for c in GOLD)
        gc = tuple(int(c * ha) for c in GREY)

        hf = load_font(40, bold=True)
        ht = "TODAY'S TOP 3"
        bbox = draw.textbbox((0, 0), ht, font=hf)
        draw.text(((W - bbox[2] + bbox[0]) // 2, 80), ht, font=hf, fill=hc)

        sf = load_font(16)
        st = f"{datetime.now().strftime('%B %d, %Y').upper()} • {len(deals)} DEALS DETECTED"
        bbox2 = draw.textbbox((0, 0), st, font=sf)
        draw.text(((W - bbox2[2] + bbox2[0]) // 2, 130), st, font=sf, fill=gc)

    # ── 3 deal cards stacked ──
    card_h = 480
    card_gap = 20
    cards_start_y = 175

    for i, d in enumerate(deals[:3]):
        card_start = 0.8 + i * 1.8
        card_end = card_start + 1.5
        ct = _ft(frame, card_start, card_end)
        if ct <= 0:
            continue

        card_y = cards_start_y + i * (card_h + card_gap)
        card_alpha = _snap(ct)

        # Card background (slide in)
        slide = int((1 - _ease(min(ct * 2, 1.0))) * 80)
        cy = card_y + slide

        ca = max(0, min(card_alpha, 1.0))
        card_bg = tuple(int(c * ca) for c in (14, 14, 14))
        border_c = tuple(int(c * ca) for c in (30, 30, 30))
        draw.rounded_rectangle([(40, cy), (W - 40, cy + card_h)], radius=12, fill=card_bg, outline=border_c)

        # Rank number
        rank_font = load_font(56, bold=True)
        rc = tuple(int(c * ca) for c in DIM_GOLD)
        draw.text((60, cy + 15), f"#{i + 1}", font=rank_font, fill=rc)

        # Product thumbnail (small, left side)
        thumb_size = 160
        listing = imgs[i] if i < len(imgs) else None
        if listing:
            _draw_product_frame(img, draw, listing, 60, cy + 90, thumb_size, thumb_size, ca)
            draw = ImageDraw.Draw(img)

        # Brand + title (right of thumbnail)
        text_x = 60 + thumb_size + 24 if listing else 60
        text_y = cy + 90 if listing else cy + 80

        if ct > 0.2:
            ta = _ease((ct - 0.2) / 0.3) * ca
            brand_c = tuple(int(c * ta) for c in WHITE)
            title_c = tuple(int(c * ta) for c in GREY)

            draw.text((text_x, text_y), d.brand.upper(), font=load_font(28, bold=True), fill=brand_c)
            draw.text((text_x, text_y + 35), d.title[:30], font=load_font(18), fill=title_c)

        # Price row
        if ct > 0.4:
            pa = _ease((ct - 0.4) / 0.3) * ca
            price_y = cy + card_h - 130

            # Buy price
            pc = tuple(int(c * pa) for c in WHITE)
            draw.text((60, price_y), "BUY", font=load_font(12), fill=tuple(int(c * pa) for c in GREY))
            draw.text((60, price_y + 16), f"${d.buy_price:,.0f}", font=load_font(36, bold=True), fill=pc)

            # Market price
            gc = tuple(int(c * pa) for c in GOLD)
            draw.text((300, price_y), "MARKET", font=load_font(12), fill=tuple(int(c * pa) for c in GREY))
            draw.text((300, price_y + 16), f"${d.market_price:,.0f}", font=load_font(36, bold=True), fill=gc)

        # Profit (pops in last)
        if ct > 0.6:
            profit_a = _snap((ct - 0.6) / 0.3) * ca
            profit_y = cy + card_h - 115
            profit_c = tuple(int(c * min(profit_a, 1.0)) for c in GREEN)
            profit_font = load_font(max(12, int(48 * min(_snap((ct - 0.6) / 0.3), 1.0))), bold=True)
            draw.text((600, profit_y), f"+${d.profit:,.0f}", font=profit_font, fill=profit_c)

        # Bottom border accent
        if ct > 0.5:
            ba = _ease((ct - 0.5) / 0.2) * ca
            acc_c = tuple(int(c * ba) for c in GOLD)
            bw = int(920 * _ease((ct - 0.5) / 0.2))
            if bw > 0:
                bx = (W - bw) // 2
                draw.line([(bx, cy + card_h - 2), (bx + bw, cy + card_h - 2)], fill=acc_c, width=2)

    # ── CTA (after all cards) ──
    cta_start = 0.8 + len(deals[:3]) * 1.8 + 0.5
    cta_t = _ft(frame, cta_start, cta_start + 1.2)
    if cta_t > 0:
        ca = _ease(cta_t)
        cta_y = cards_start_y + 3 * (card_h + card_gap) + 20

        gc = tuple(int(c * ca) for c in GOLD)
        wc = tuple(int(c * ca) for c in WHITE)
        dc = tuple(int(c * ca) for c in GREY)

        total_profit = sum(d.profit for d in deals[:3])
        total_font = load_font(20, bold=True)
        total_text = f"TOTAL OPPORTUNITY: +${total_profit:,.0f}"
        bbox = draw.textbbox((0, 0), total_text, font=total_font)
        draw.text(((W - bbox[2] + bbox[0]) // 2, cta_y), total_text, font=total_font, fill=tuple(int(c * ca) for c in GREEN))

        cta_font = load_font(24, bold=True)
        cta_text = "@archivearbitrage"
        bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
        draw.text(((W - bbox[2] + bbox[0]) // 2, cta_y + 40), cta_text, font=cta_font, fill=gc)

        tag_font = load_font(16)
        tag = "Link in bio for real-time alerts"
        bbox = draw.textbbox((0, 0), tag, font=tag_font)
        draw.text(((W - bbox[2] + bbox[0]) // 2, cta_y + 75), tag, font=tag_font, fill=dc)

    return img


# ══════════════════════════════════════════════════════════
# Compilation
# ══════════════════════════════════════════════════════════

def _compile(render_fn, total_frames, prefix):
    tmp = tempfile.mkdtemp(prefix="aa_brand_")
    try:
        logger.info(f"Rendering {total_frames} frames ({prefix})...")
        for i in range(total_frames):
            render_fn(i).save(os.path.join(tmp, f"f_{i:04d}.jpg"), "JPEG", quality=88)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        vp = str(QUEUE_DIR / f"brand_{prefix}_{ts}.mp4")
        tp = str(QUEUE_DIR / f"brand_{prefix}_{ts}_thumb.jpg")

        # Thumbnail at profit reveal
        thumb_f = min(int(6.5 * FPS), total_frames - 1)
        render_fn(thumb_f).save(tp, "JPEG", quality=95)

        subprocess.run([
            "ffmpeg", "-y", "-framerate", str(FPS),
            "-i", os.path.join(tmp, "f_%04d.jpg"),
            "-c:v", "libx264", "-preset", "fast", "-crf", "26",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", vp,
        ], capture_output=True, timeout=180, check=True)

        size = os.path.getsize(vp) / 1024 / 1024
        logger.info(f"Video: {vp} ({size:.1f} MB)")
        return vp, tp
    except Exception as e:
        logger.error(f"Failed: {e}")
        return None, None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def generate_system_alert(data, listing_img=None):
    frames = int(10.5 * FPS)
    slug = data.brand.lower().replace(" ", "_")[:15]
    return _compile(lambda f: render_system_alert(f, data, listing_img), frames, f"alert_{slug}")


def generate_daily_scanner(deals, images=None):
    total_sec = 0.8 + len(deals[:3]) * 1.8 + 2.0
    frames = int(total_sec * FPS)
    return _compile(lambda f: render_daily_scanner(f, deals[:3], images), frames, "scanner")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    # Try loading a real image
    listing_img = None
    try:
        listing_img = Image.open("/tmp/test_listing.jpg").convert("RGB")
    except Exception:
        pass

    print("=== System Alert (Chrome Hearts) ===\n")
    d = DealCardData(
        title="Cross Patch Trucker Jacket", brand="Chrome Hearts", source="grailed", source_url="",
        buy_price=583, market_price=1499, profit=916, margin=0.61,
        fire_level=3, quality_score=82, comp_count=12, auth_confidence=0.89,
    )
    vp, tp = generate_system_alert(d, listing_img)
    if vp:
        print(f"Video: {vp}")
        if sys.platform == "darwin":
            subprocess.run(["open", vp], check=False)

    print("\n=== Daily Scanner (3 deals) ===\n")
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
    vp2, tp2 = generate_daily_scanner(deals, [listing_img] * 3 if listing_img else None)
    if vp2:
        print(f"Video: {vp2}")
        if sys.platform == "darwin":
            subprocess.run(["open", vp2], check=False)

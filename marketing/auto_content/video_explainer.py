"""
Brand explainer videos — show what Archive Arbitrage actually does.

These aren't deal alerts. They're value proposition videos that
explain the system, show the pipeline in action, and demonstrate
why someone should subscribe.

Templates:
  A: "The System" — full pipeline walkthrough (scanning → pricing → alerting)
  B: "What $39/mo Gets You" — ROI breakdown with real numbers
  C: "Before vs After" — manual scrolling vs Archive Arbitrage
"""

from __future__ import annotations

import logging
import math
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

from .design import load_font
from .video_gen_brand import (
    W, H, FPS, QUEUE_DIR, BG, GRID_COLOR, GRID_ACCENT, GOLD, DIM_GOLD,
    WHITE, GREY, DIM_GREY, GREEN, BRIGHT_GREEN, RED, LIVE_RED, MONO_BG,
    _ease, _snap, _ft, _draw_grid, _draw_header, _draw_progress_bar,
    _compile,
)

logger = logging.getLogger("auto_content.video_explainer")


def _typewriter(text: str, progress: float) -> str:
    """Reveal text character by character."""
    chars = int(len(text) * max(0, min(progress, 1.0)))
    return text[:chars]


def _counting_number(target: int, progress: float) -> int:
    """Smooth counting animation."""
    return int(target * _ease(min(progress, 1.0)))


# ══════════════════════════════════════════════════════════
# TEMPLATE A: "The System" — full pipeline walkthrough
# ══════════════════════════════════════════════════════════
#
# [0-2s]    "While you're sleeping..."
# [2-4s]    "We're scanning 7 platforms" + platform names animate in
# [4-6s]    "10,000+ listings analyzed daily" + counter ticking
# [6-8s]    "Every item priced against sold comps" + comp visual
# [8-10s]   "Authenticated with 7 signals" + auth bar
# [10-12s]  "Deals hit your phone instantly" + alert mockup
# [12-14s]  "One flip pays for months" + ROI math
# [14-16s]  CTA: "@archivearbitrage • Link in bio"

def render_the_system(frame: int) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _draw_grid(draw, frame)
    _draw_header(draw, frame)

    # ── Phase 1: "While you're sleeping..." (0-2s) ──
    p1 = _ft(frame, 0.3, 1.8)
    if p1 > 0:
        a = _ease(min(p1 * 1.5, 1.0))
        # Fade out at end
        if p1 > 0.7:
            a *= _ease(1 - (p1 - 0.7) / 0.3)

        c = tuple(int(255 * a) for _ in range(3))
        gc = tuple(int(v * a) for v in GREY)

        font = load_font(52, bold=True)
        text = "WHILE YOU'RE SLEEPING"
        bbox = draw.textbbox((0, 0), text, font=font)
        draw.text(((W - bbox[2] + bbox[0]) // 2, H // 2 - 60), text, font=font, fill=c)

        sub = load_font(24)
        sub_t = "our system is working"
        bbox2 = draw.textbbox((0, 0), sub_t, font=sub)
        draw.text(((W - bbox2[2] + bbox2[0]) // 2, H // 2 + 10), sub_t, font=sub, fill=gc)

    # ── Phase 2: "Scanning 7 platforms" (2-4.5s) ──
    p2 = _ft(frame, 2.0, 4.2)
    if p2 > 0:
        a2 = _ease(min(p2 * 2, 1.0))
        if p2 > 0.85:
            a2 *= _ease(1 - (p2 - 0.85) / 0.15)

        # Header
        hc = tuple(int(v * a2) for v in GOLD)
        hf = load_font(44, bold=True)
        ht = "SCANNING 7 PLATFORMS"
        bbox = draw.textbbox((0, 0), ht, font=hf)
        draw.text(((W - bbox[2] + bbox[0]) // 2, 200), ht, font=hf, fill=hc)

        # Platform names animate in one by one
        platforms = ["GRAILED", "EBAY", "POSHMARK", "DEPOP", "MERCARI", "VINTED", "YAHOO JP"]
        plat_font = load_font(28, bold=True)
        start_y = 320

        for i, plat in enumerate(platforms):
            plat_delay = 0.05 + i * 0.08
            pt = max(0, (p2 - plat_delay) / 0.15)
            if pt <= 0:
                continue
            pa = _snap(min(pt, 1.0)) * a2
            if pa < 0.05:
                continue

            y = start_y + i * 65
            # Slide in from left
            slide = int((1 - _ease(min(pt, 1.0))) * 100)

            # Dot indicator
            dot_c = tuple(int(v * pa) for v in GREEN)
            draw.ellipse([(80 + slide - 5, y + 8), (80 + slide + 5, y + 18)], fill=dot_c)

            # Platform name
            pc = tuple(int(255 * pa) for _ in range(3))
            draw.text((100 + slide, y), plat, font=plat_font, fill=pc)

            # "LIVE" text
            live_c = tuple(int(v * pa) for v in GREEN)
            draw.text((380 + slide, y + 5), "CONNECTED", font=load_font(14), fill=live_c)

        # Scanning animation (sweeping line)
        scan_y = 300 + int((p2 * 3 % 1) * 460)
        scan_a = a2 * 0.3
        sc = tuple(int(v * scan_a) for v in GOLD)
        draw.line([(60, scan_y), (W - 60, scan_y)], fill=sc, width=1)

    # ── Phase 3: "10,000+ listings analyzed" (4.5-6.5s) ──
    p3 = _ft(frame, 4.5, 6.3)
    if p3 > 0:
        a3 = _ease(min(p3 * 2, 1.0))
        if p3 > 0.85:
            a3 *= _ease(1 - (p3 - 0.85) / 0.15)

        gc = tuple(int(v * a3) for v in GOLD)
        wc = tuple(int(255 * a3) for _ in range(3))
        grc = tuple(int(v * a3) for v in GREY)

        # Counter
        count = _counting_number(10000, min(p3 * 1.5, 1.0))
        count_font = load_font(96, bold=True)
        count_text = f"{count:,}+"
        bbox = draw.textbbox((0, 0), count_text, font=count_font)
        draw.text(((W - bbox[2] + bbox[0]) // 2, H // 2 - 100), count_text, font=count_font, fill=wc)

        sub = load_font(28)
        sub_t = "LISTINGS ANALYZED DAILY"
        bbox2 = draw.textbbox((0, 0), sub_t, font=sub)
        draw.text(((W - bbox2[2] + bbox2[0]) // 2, H // 2 + 20), sub_t, font=sub, fill=gc)

        # Sub-subtitle
        if p3 > 0.3:
            ss_a = _ease((p3 - 0.3) / 0.3) * a3
            ssc = tuple(int(v * ss_a) for v in GREY)
            ss = "across 40+ archive brands"
            bbox3 = draw.textbbox((0, 0), ss, font=load_font(20))
            draw.text(((W - bbox3[2] + bbox3[0]) // 2, H // 2 + 65), ss, font=load_font(20), fill=ssc)

    # ── Phase 4: "Priced against sold comps" (6.5-8.5s) ──
    p4 = _ft(frame, 6.5, 8.3)
    if p4 > 0:
        a4 = _ease(min(p4 * 2, 1.0))
        if p4 > 0.85:
            a4 *= _ease(1 - (p4 - 0.85) / 0.15)

        gc = tuple(int(v * a4) for v in GOLD)
        wc = tuple(int(255 * a4) for _ in range(3))
        grc = tuple(int(v * a4) for v in GREY)

        hf = load_font(36, bold=True)
        draw.text((80, 250), "EVERY ITEM PRICED AGAINST", font=hf, fill=wc)
        draw.text((80, 300), "REAL SOLD DATA", font=hf, fill=gc)

        # Simulated comp display
        if p4 > 0.2:
            comp_a = _ease((p4 - 0.2) / 0.4) * a4

            comps = [
                ("Sold 3 days ago", "$620"),
                ("Sold 1 week ago", "$585"),
                ("Sold 2 weeks ago", "$640"),
                ("Sold 3 weeks ago", "$550"),
                ("Sold 1 month ago", "$610"),
            ]

            mono = load_font(20, mono=True)
            label_f = load_font(14)

            draw.text((80, 400), "RECENT SOLD COMPS", font=label_f, fill=tuple(int(v * comp_a) for v in GREY))

            for i, (when, price) in enumerate(comps):
                row_delay = i * 0.08
                rt = max(0, min((p4 - 0.25 - row_delay) / 0.15, 1.0))
                if rt <= 0:
                    continue
                ra = _snap(rt) * comp_a
                y = 435 + i * 55

                # Row background
                rbg = tuple(int(14 * ra) for _ in range(3))
                draw.rounded_rectangle([(80, y), (W - 80, y + 44)], radius=6, fill=rbg)

                wrc = tuple(int(v * ra) for v in GREY)
                prc = tuple(int(v * ra) for v in GREEN)
                draw.text((100, y + 12), when, font=mono, fill=wrc)

                # Price right-aligned
                pbbox = draw.textbbox((0, 0), price, font=load_font(24, bold=True))
                draw.text((W - 100 - pbbox[2] + pbbox[0], y + 8), price, font=load_font(24, bold=True), fill=prc)

            # Market value summary
            if p4 > 0.6:
                mv_a = _ease((p4 - 0.6) / 0.2) * a4
                mvc = tuple(int(v * mv_a) for v in GOLD)
                draw.text((80, 730), "CALCULATED MARKET VALUE", font=label_f, fill=tuple(int(v * mv_a) for v in GREY))

                mvf = load_font(64, bold=True)
                draw.text((80, 755), "$601", font=mvf, fill=mvc)
                draw.text((300, 775), "weighted average", font=load_font(18), fill=tuple(int(v * mv_a) for v in GREY))

    # ── Phase 5: "Authenticated" (8.5-10.5s) ──
    p5 = _ft(frame, 8.5, 10.3)
    if p5 > 0:
        a5 = _ease(min(p5 * 2, 1.0))
        if p5 > 0.85:
            a5 *= _ease(1 - (p5 - 0.85) / 0.15)

        gc = tuple(int(v * a5) for v in GOLD)
        wc = tuple(int(255 * a5) for _ in range(3))

        hf = load_font(36, bold=True)
        draw.text((80, 250), "EVERY ITEM AUTHENTICATED", font=hf, fill=wc)
        draw.text((80, 300), "7-SIGNAL VERIFICATION", font=hf, fill=gc)

        signals = [
            ("Text analysis", "replica keywords, wholesale language"),
            ("Price plausibility", "statistical check against comps"),
            ("Seller reputation", "sales history, ratings, account age"),
            ("Listing quality", "photo count, description depth"),
            ("Image analysis", "stock photos, duplicates"),
            ("Brand markers", "hardware, tags, stitching"),
            ("Cross-reference", "multi-platform validation"),
        ]

        for i, (name, desc) in enumerate(signals):
            sig_delay = 0.1 + i * 0.07
            st = max(0, min((p5 - sig_delay) / 0.12, 1.0))
            if st <= 0:
                continue
            sa = _snap(st) * a5
            y = 400 + i * 70

            # Check mark
            check_c = tuple(int(v * sa) for v in GREEN)
            draw.text((80, y), "//", font=load_font(20, bold=True), fill=check_c)

            # Signal name
            nc = tuple(int(255 * sa) for _ in range(3))
            draw.text((120, y), name, font=load_font(24, bold=True), fill=nc)

            # Description
            dc = tuple(int(v * sa) for v in GREY)
            draw.text((120, y + 30), desc, font=load_font(16), fill=dc)

        # Auth score result
        if p5 > 0.7:
            auth_a = _ease((p5 - 0.7) / 0.15) * a5
            _draw_progress_bar(draw, 80, 910, 600, 20,
                             0.87 * _ease((p5 - 0.7) / 0.2), GREEN, alpha=auth_a)
            sc = tuple(int(255 * auth_a) for _ in range(3))
            draw.text((700, 905), "87%", font=load_font(28, bold=True), fill=sc)
            draw.text((80, 945), "ITEMS BELOW 65% ARE BLOCKED — YOU NEVER SEE THEM",
                      font=load_font(14), fill=tuple(int(v * auth_a) for v in GREY))

    # ── Phase 6: "Deals hit your phone" (10.5-12.5s) ──
    p6 = _ft(frame, 10.5, 12.3)
    if p6 > 0:
        a6 = _ease(min(p6 * 2, 1.0))
        if p6 > 0.85:
            a6 *= _ease(1 - (p6 - 0.85) / 0.15)

        gc = tuple(int(v * a6) for v in GOLD)
        wc = tuple(int(255 * a6) for _ in range(3))
        grc = tuple(int(v * a6) for v in GREEN)

        hf = load_font(36, bold=True)
        draw.text((80, 250), "QUALIFIED DEALS HIT", font=hf, fill=wc)
        draw.text((80, 300), "YOUR PHONE INSTANTLY", font=hf, fill=gc)

        # Simulated alert card
        if p6 > 0.2:
            card_a = _snap((p6 - 0.2) / 0.4) * a6
            card_slide = int((1 - _ease(min((p6 - 0.2) * 3, 1.0))) * 60)

            cy = 420 + card_slide
            card_bg = tuple(int(18 * card_a) for _ in range(3))
            border = tuple(int(v * card_a) for v in GOLD)
            draw.rounded_rectangle([(80, cy), (W - 80, cy + 350)], radius=16, fill=card_bg, outline=border, width=2)

            # Alert content
            cc = lambda color: tuple(int(v * card_a) for v in color)

            draw.text((120, cy + 20), "DEAL ALERT", font=load_font(16, bold=True), fill=cc(LIVE_RED))
            draw.text((120, cy + 50), "CHROME HEARTS", font=load_font(32, bold=True), fill=cc(WHITE))
            draw.text((120, cy + 90), "Cross Patch Trucker Jacket", font=load_font(20), fill=cc(GREY))

            draw.text((120, cy + 140), "BUY", font=load_font(12), fill=cc(GREY))
            draw.text((120, cy + 156), "$583", font=load_font(36, bold=True), fill=cc(WHITE))
            draw.text((340, cy + 140), "MARKET", font=load_font(12), fill=cc(GREY))
            draw.text((340, cy + 156), "$1,499", font=load_font(36, bold=True), fill=cc(GOLD))

            draw.text((120, cy + 220), "EST. PROFIT", font=load_font(14), fill=cc(GREY))
            draw.text((120, cy + 240), "+$916", font=load_font(52, bold=True), fill=cc(GREEN))

            draw.text((120, cy + 310), "Telegram • Discord • Real-time", font=load_font(16), fill=cc(GREY))

    # ── Phase 7: "One flip pays for months" (12.5-14.5s) ──
    p7 = _ft(frame, 12.5, 14.3)
    if p7 > 0:
        a7 = _ease(min(p7 * 2, 1.0))
        if p7 > 0.85:
            a7 *= _ease(1 - (p7 - 0.85) / 0.15)

        gc = tuple(int(v * a7) for v in GOLD)
        wc = tuple(int(255 * a7) for _ in range(3))
        grc = tuple(int(v * a7) for v in GREEN)

        hf = load_font(44, bold=True)
        ht = "THE MATH IS SIMPLE"
        bbox = draw.textbbox((0, 0), ht, font=hf)
        draw.text(((W - bbox[2] + bbox[0]) // 2, 300), ht, font=hf, fill=wc)

        # ROI breakdown
        rows = [
            (0.15, "SUBSCRIPTION", "$39/mo", WHITE, 48),
            (0.30, "AVG DEAL PROFIT", "$370", GREEN, 48),
            (0.45, "ROI PER FLIP", "9.5x", GOLD, 48),
            (0.60, "DEALS TO BREAK EVEN", "1", GREEN, 64),
        ]

        for delay, label, value, color, size in rows:
            rt = max(0, min((p7 - delay) / 0.15, 1.0))
            if rt <= 0:
                continue
            ra = _snap(rt) * a7
            idx = rows.index((delay, label, value, color, size))
            y = 420 + idx * 120

            lc = tuple(int(v * ra) for v in GREY)
            vc = tuple(int(v * ra) for v in color)

            draw.text((80, y), label, font=load_font(16), fill=lc)
            draw.text((80, y + 22), value, font=load_font(size, bold=True), fill=vc)

            # Divider
            draw.line([(80, y + 22 + size + 15), (W - 80, y + 22 + size + 15)],
                     fill=tuple(int(25 * ra) for _ in range(3)), width=1)

    # ── Phase 8: CTA (14.5-16s) ──
    p8 = _ft(frame, 14.5, 16.0)
    if p8 > 0:
        a8 = _ease(p8)
        gc = tuple(int(v * a8) for v in GOLD)
        wc = tuple(int(255 * a8) for _ in range(3))
        grc = tuple(int(v * a8) for v in GREY)
        grn = tuple(int(v * a8) for v in GREEN)

        # Big brand name
        bf = load_font(48, bold=True)
        bt = "ARCHIVE ARBITRAGE"
        bbox = draw.textbbox((0, 0), bt, font=bf)
        draw.text(((W - bbox[2] + bbox[0]) // 2, H // 2 - 120), bt, font=bf, fill=gc)

        # Gold divider
        lw = int(400 * _ease(min(p8 * 2, 1.0)))
        if lw > 0:
            lx = (W - lw) // 2
            draw.line([(lx, H // 2 - 50), (lx + lw, H // 2 - 50)], fill=gc, width=2)

        # Value props
        props = [
            "7 platforms scanned 24/7",
            "Priced against real sold comps",
            "7-signal authentication",
            "Real-time Telegram + Discord alerts",
        ]
        for i, prop in enumerate(props):
            prop_delay = 0.1 + i * 0.08
            pt = max(0, min((p8 - prop_delay) / 0.15, 1.0))
            if pt <= 0:
                continue
            pa = _ease(pt) * a8
            pc = tuple(int(255 * pa) for _ in range(3))
            dc = tuple(int(v * pa) for v in GREEN)

            y = H // 2 - 20 + i * 45
            draw.text((340, y), prop, font=load_font(22), fill=pc)
            draw.text((310, y + 3), "//", font=load_font(18, bold=True), fill=dc)

        # Price + CTA
        if p8 > 0.4:
            cta_a = _ease((p8 - 0.4) / 0.3) * a8
            ctc = tuple(int(255 * cta_a) for _ in range(3))
            ctagc = tuple(int(v * cta_a) for v in GOLD)

            pf = load_font(56, bold=True)
            pt = "$39/mo"
            bbox = draw.textbbox((0, 0), pt, font=pf)
            draw.text(((W - bbox[2] + bbox[0]) // 2, H // 2 + 200), pt, font=pf, fill=ctc)

            lf = load_font(24)
            lt = "Link in bio • Cancel anytime"
            bbox2 = draw.textbbox((0, 0), lt, font=lf)
            draw.text(((W - bbox2[2] + bbox2[0]) // 2, H // 2 + 275), lt, font=lf, fill=ctagc)

    return img


# ══════════════════════════════════════════════════════════
# Generation
# ══════════════════════════════════════════════════════════

def generate_the_system_video() -> Tuple[Optional[str], Optional[str]]:
    """Generate 'The System' explainer video."""
    frames = int(16.0 * FPS)
    return _compile(render_the_system, frames, "system_explainer")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    print("=== Generating 'The System' explainer ===\n")
    vp, tp = generate_the_system_video()
    if vp:
        print(f"Video: {vp}")
        if sys.platform == "darwin":
            subprocess.run(["open", vp], check=False)

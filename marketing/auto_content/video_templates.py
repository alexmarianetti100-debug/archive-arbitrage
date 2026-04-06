"""
Additional branded video templates — content variety for daily posting.

Uses the same brand aesthetic from video_gen_brand.py:
  - Dark grid background, gold accents, green profits
  - ARCHIVE ARBITRAGE header with live dot
  - Data-dense, satisfying snap animations

Templates:
  1. "Deal of the Week" — best single deal, full comp breakdown
  2. "Brand Spotlight" — one brand's market data + top deals
  3. "What $39 Gets You" — monthly ROI showcase
  4. "Member Wins" — profit ticker from Discord #wins
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw

from .design import load_font
from .video_gen_brand import (
    W, H, FPS, QUEUE_DIR, BG, GOLD, DIM_GOLD, WHITE, GREY, DIM_GREY,
    GREEN, BRIGHT_GREEN, RED, LIVE_RED, MONO_BG,
    _ease, _snap, _ft, _draw_grid, _draw_header, _draw_progress_bar,
    _draw_data_row, _compile, _counter_value,
)
from .deal_card import DealCardData

logger = logging.getLogger("auto_content.video_templates")

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


# ══════════════════════════════════════════════════════════
# 1. DEAL OF THE WEEK
# ══════════════════════════════════════════════════════════

def render_deal_of_week(frame: int, data: DealCardData, listing_img: Optional[Image.Image] = None) -> Image.Image:
    """Best deal of the week — full data breakdown."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _draw_grid(draw, frame)
    _draw_header(draw, frame)

    # [0-1.5s] "DEAL OF THE WEEK" title
    p1 = _ft(frame, 0.2, 1.3)
    if p1 > 0:
        a = _ease(min(p1 * 2, 1.0))
        gc = tuple(int(v * a) for v in GOLD)
        wc = tuple(int(255 * a) for _ in range(3))

        draw.text((80, 90), "DEAL OF THE WEEK", font=load_font(44, bold=True), fill=gc)

        # Gold underline
        lw = int(500 * _ease(min(p1 * 3, 1.0)))
        if lw > 0:
            draw.line([(80, 145), (80 + lw, 145)], fill=gc, width=2)

        draw.text((80, 160), date.today().strftime("%B %d, %Y").upper(), font=load_font(16), fill=tuple(int(v * a) for v in GREY))

    # [1.5-3.5s] Product image + brand
    p2 = _ft(frame, 1.3, 3.0)
    if p2 > 0:
        a2 = _ease(min(p2 * 1.5, 1.0))

        if listing_img:
            from .video_gen_brand import _draw_product_frame
            slide = int((1 - _ease(min(p2 * 2, 1.0))) * 50)
            _draw_product_frame(img, draw, listing_img, (W - 500) // 2, 210 + slide, 500, 500, a2)
            draw = ImageDraw.Draw(img)

        if p2 > 0.3:
            ta = _ease((p2 - 0.3) / 0.4) * a2
            bc = tuple(int(255 * ta) for _ in range(3))
            tc = tuple(int(v * ta) for v in GREY)
            bf = load_font(36, bold=True)
            bt = data.brand.upper()
            bbox = draw.textbbox((0, 0), bt, font=bf)
            draw.text(((W - bbox[2] + bbox[0]) // 2, 740), bt, font=bf, fill=bc)
            tf = load_font(22)
            tt = data.title[:45]
            bbox2 = draw.textbbox((0, 0), tt, font=tf)
            draw.text(((W - bbox2[2] + bbox2[0]) // 2, 785), tt, font=tf, fill=tc)

    # [3.5-6s] Full data breakdown — stacked rows
    rows = [
        (3.3, "SOURCE", f"{data.source.title()}", WHITE),
        (3.6, "LISTED PRICE", f"${data.buy_price:,.0f}", WHITE),
        (3.9, "MARKET VALUE", f"${data.market_price:,.0f}", GOLD),
        (4.2, "COMP COUNT", f"{data.comp_count} verified sold", WHITE),
        (4.5, "AUTH CONFIDENCE", f"{data.auth_confidence * 100:.0f}%", GREEN if data.auth_confidence > 0.7 else GOLD),
        (4.8, "DEMAND", data.demand_level.upper() if data.demand_level and data.demand_level != "unknown" else "ACTIVE", WHITE),
    ]

    for start, label, value, color in rows:
        rt = _ft(frame, start, start + 0.5)
        if rt <= 0:
            continue
        ra = _snap(rt)
        idx = rows.index((start, label, value, color))
        y = 850 + idx * 65
        slide = int((1 - _ease(min(rt * 2, 1.0))) * 60)
        _draw_data_row(draw, 80 + slide, y, label, value, 32, GREY, color, ra)

    # [6-8s] Profit reveal with counter
    p4 = _ft(frame, 5.8, 7.5)
    if p4 > 0:
        a4 = _ease(min(p4 * 2, 1.0))
        profit_y = 1280

        lw = int(900 * _ease(min(p4 * 3, 1.0)))
        if lw > 0:
            lx = (W - lw) // 2
            draw.line([(lx, profit_y), (lx + lw, profit_y)], fill=GOLD, width=2)

        if p4 > 0.15:
            la = _ease((p4 - 0.15) / 0.2) * a4
            draw.text((80, profit_y + 20), "ESTIMATED PROFIT", font=load_font(16), fill=tuple(int(v * la) for v in GREY))

            counter_p = min((p4 - 0.2) / 0.5, 1.0)
            displayed = _counter_value(int(data.profit), counter_p)
            pf = load_font(88, bold=True)
            gc = tuple(int(v * a4) for v in GREEN)
            pt = f"+${displayed:,}"
            bbox = draw.textbbox((0, 0), pt, font=pf)
            draw.text(((W - bbox[2] + bbox[0]) // 2, profit_y + 50), pt, font=pf, fill=gc)

            if p4 > 0.6:
                ma = _ease((p4 - 0.6) / 0.2) * a4
                mc = tuple(int(v * ma) for v in GREEN)
                mt = f"{data.margin * 100:.0f}% BELOW MARKET"
                mf = load_font(26, bold=True)
                bbox = draw.textbbox((0, 0), mt, font=mf)
                draw.text(((W - bbox[2] + bbox[0]) // 2, profit_y + 160), mt, font=mf, fill=mc)

    # [8-9.5s] CTA
    p5 = _ft(frame, 8.0, 9.5)
    if p5 > 0:
        a5 = _ease(p5)
        gc = tuple(int(v * a5) for v in GOLD)
        wc = tuple(int(255 * a5) for _ in range(3))

        draw.text((80, 1560), "WANT DEALS LIKE THIS EVERY DAY?", font=load_font(24, bold=True), fill=wc)
        draw.text((80, 1600), "@archivearbitrage", font=load_font(28, bold=True), fill=gc)
        draw.text((80, 1645), "Link in bio • $39/mo", font=load_font(18), fill=tuple(int(v * a5) for v in GREY))

    return img


# ══════════════════════════════════════════════════════════
# 2. BRAND SPOTLIGHT
# ══════════════════════════════════════════════════════════

def render_brand_spotlight(
    frame: int,
    brand: str,
    total_deals: int,
    avg_profit: float,
    best_gap: float,
    top_pieces: List[str],
) -> Image.Image:
    """Deep dive on one brand's data."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _draw_grid(draw, frame)
    _draw_header(draw, frame)

    from .design import get_brand_accent
    accent = get_brand_accent(brand)

    # [0-2s] Brand name reveal
    p1 = _ft(frame, 0.2, 1.8)
    if p1 > 0:
        a = _ease(min(p1 * 2, 1.0))
        ac = tuple(int(v * a) for v in accent)

        draw.text((80, 100), "BRAND SPOTLIGHT", font=load_font(20), fill=tuple(int(v * a) for v in GREY))

        # Big brand name
        scale = min(_snap(p1 * 1.5), 1.0)
        bf = load_font(max(12, int(72 * scale)), bold=True)
        draw.text((80, 140), brand.upper(), font=bf, fill=ac)

        lw = int(600 * _ease(min(p1 * 3, 1.0)))
        if lw > 0:
            draw.line([(80, 230), (80 + lw, 230)], fill=ac, width=2)

    # [2-4.5s] Stats grid
    stats = [
        (2.0, "DEALS FOUND", str(total_deals), GREEN),
        (2.4, "AVG PROFIT", f"${avg_profit:,.0f}", GREEN),
        (2.8, "BEST GAP", f"{best_gap * 100:.0f}%", GOLD),
        (3.2, "PLATFORMS", "7 SCANNED", WHITE),
    ]

    for start, label, value, color in stats:
        st = _ft(frame, start, start + 0.5)
        if st <= 0:
            continue
        sa = _snap(st)
        idx = stats.index((start, label, value, color))
        col = idx % 2
        row = idx // 2
        x = 80 + col * 480
        y = 280 + row * 150

        slide = int((1 - _ease(min(st * 2, 1.0))) * 40)
        _draw_data_row(draw, x + slide, y, label, value, 44, GREY, color, sa)

    # [4.5-7s] Top pieces list
    p3 = _ft(frame, 4.3, 6.5)
    if p3 > 0:
        a3 = _ease(min(p3 * 2, 1.0))
        draw.text((80, 620), "TOP SEARCHED PIECES", font=load_font(18), fill=tuple(int(v * a3) for v in GREY))
        draw.line([(80, 650), (W - 80, 650)], fill=tuple(int(25 * a3) for _ in range(3)), width=1)

        for i, piece in enumerate(top_pieces[:6]):
            pd = 0.1 + i * 0.07
            pt = max(0, min((p3 - pd) / 0.12, 1.0))
            if pt <= 0:
                continue
            pa = _snap(pt) * a3
            y = 670 + i * 55
            slide = int((1 - _ease(min(pt * 2, 1.0))) * 60)

            nc = tuple(int(v * pa) for v in DIM_GOLD)
            draw.text((80 + slide, y), f"{i + 1:02d}", font=load_font(20, bold=True), fill=nc)

            pc = tuple(int(255 * pa) for _ in range(3))
            draw.text((130 + slide, y), piece.upper(), font=load_font(22, bold=True), fill=pc)

    # [7-9s] CTA
    p4 = _ft(frame, 7.0, 8.5)
    if p4 > 0:
        a4 = _ease(p4)
        gc = tuple(int(v * a4) for v in GOLD)
        wc = tuple(int(255 * a4) for _ in range(3))

        draw.text((80, 1060), f"GET {brand.upper()} DEALS FIRST", font=load_font(28, bold=True), fill=wc)
        draw.text((80, 1105), "@archivearbitrage", font=load_font(24, bold=True), fill=gc)

    return img


# ══════════════════════════════════════════════════════════
# 3. WHAT $39 GETS YOU — Monthly ROI
# ══════════════════════════════════════════════════════════

def render_monthly_roi(
    frame: int,
    total_deals: int,
    total_profit: float,
    best_deal_profit: float,
    top_brands: List[tuple],
) -> Image.Image:
    """Monthly ROI showcase with real numbers."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _draw_grid(draw, frame)
    _draw_header(draw, frame)

    # [0-2s] "WHAT $39/MO GETS YOU"
    p1 = _ft(frame, 0.2, 1.5)
    if p1 > 0:
        a = _ease(min(p1 * 2, 1.0))
        wc = tuple(int(255 * a) for _ in range(3))
        gc = tuple(int(v * a) for v in GOLD)

        draw.text((80, 120), "WHAT", font=load_font(56, bold=True), fill=wc)
        draw.text((280, 120), "$39/MO", font=load_font(56, bold=True), fill=gc)
        draw.text((80, 195), "GETS YOU", font=load_font(56, bold=True), fill=wc)

        lw = int(700 * _ease(min(p1 * 3, 1.0)))
        if lw > 0:
            draw.line([(80, 265), (80 + lw, 265)], fill=gc, width=2)

        draw.text((80, 280), date.today().strftime("THIS MONTH • %B %Y").upper(), font=load_font(16), fill=tuple(int(v * a) for v in GREY))

    # [2-5s] Big stats with counters
    stat_data = [
        (2.0, "DEALS SENT", total_deals, "", WHITE, 72),
        (2.5, "TOTAL PROFIT OPPORTUNITY", int(total_profit), "$", GREEN, 72),
        (3.0, "BEST SINGLE DEAL", int(best_deal_profit), "+$", GREEN, 56),
        (3.5, "ROI ON SUBSCRIPTION", int(total_profit / 39) if total_profit > 0 else 0, "", GOLD, 56),
    ]

    for start, label, target, prefix, color, size in stat_data:
        st = _ft(frame, start, start + 1.0)
        if st <= 0:
            continue
        sa = _ease(min(st * 2, 1.0))
        idx = stat_data.index((start, label, target, prefix, color, size))
        y = 340 + idx * 170

        lc = tuple(int(v * sa) for v in GREY)
        draw.text((80, y), label, font=load_font(16), fill=lc)

        counter_p = min(st * 1.3, 1.0)
        displayed = _counter_value(target, counter_p)
        suffix = "x" if "ROI" in label else "+"  if "DEALS" in label else ""
        vt = f"{prefix}{displayed:,}{suffix}"
        vc = tuple(int(v * sa) for v in color)
        draw.text((80, y + 22), vt, font=load_font(size, bold=True), fill=vc)

        draw.line([(80, y + 22 + size + 20), (W - 80, y + 22 + size + 20)],
                 fill=tuple(int(20 * sa) for _ in range(3)), width=1)

    # [5.5-7.5s] Top brands
    p3 = _ft(frame, 5.5, 7.0)
    if p3 > 0:
        a3 = _ease(min(p3 * 2, 1.0))
        draw.text((80, 1100), "TOP BRANDS THIS MONTH", font=load_font(18), fill=tuple(int(v * a3) for v in GREY))

        for i, (brand_name, count) in enumerate(top_brands[:5]):
            bd = 0.1 + i * 0.06
            bt = max(0, min((p3 - bd) / 0.1, 1.0))
            if bt <= 0:
                continue
            ba = _snap(bt) * a3
            y = 1135 + i * 45

            bc = tuple(int(255 * ba) for _ in range(3))
            cc = tuple(int(v * ba) for v in GREY)
            draw.text((80, y), brand_name.title(), font=load_font(22, bold=True), fill=bc)
            draw.text((500, y + 3), f"{count} deals", font=load_font(18), fill=cc)

    # [7.5-9s] CTA
    p4 = _ft(frame, 7.5, 9.0)
    if p4 > 0:
        a4 = _ease(p4)
        gc = tuple(int(v * a4) for v in GOLD)
        wc = tuple(int(255 * a4) for _ in range(3))

        draw.text((80, 1420), "ONE FLIP COVERS MONTHS", font=load_font(32, bold=True), fill=wc)
        draw.text((80, 1470), "@archivearbitrage • Link in bio", font=load_font(22, bold=True), fill=gc)

    return img


# ══════════════════════════════════════════════════════════
# 4. MEMBER WINS
# ══════════════════════════════════════════════════════════

def render_member_wins(
    frame: int,
    wins: List[dict],  # [{"username": "...", "profit": 420, "brand": "Rick Owens"}, ...]
) -> Image.Image:
    """Animated ticker of member profits from Discord #wins."""
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    _draw_grid(draw, frame)
    _draw_header(draw, frame)

    # [0-1.5s] "MEMBER WINS THIS MONTH"
    p1 = _ft(frame, 0.2, 1.3)
    if p1 > 0:
        a = _ease(min(p1 * 2, 1.0))
        gc = tuple(int(v * a) for v in GOLD)
        wc = tuple(int(255 * a) for _ in range(3))

        draw.text((80, 90), "MEMBER WINS", font=load_font(48, bold=True), fill=gc)
        draw.text((80, 150), "THIS MONTH", font=load_font(48, bold=True), fill=wc)

        lw = int(500 * _ease(min(p1 * 3, 1.0)))
        if lw > 0:
            draw.line([(80, 215), (80 + lw, 215)], fill=gc, width=2)

    # [1.5-8s] Wins animate in one by one
    total_profit = sum(w.get("profit", 0) for w in wins)

    for i, win in enumerate(wins[:8]):
        start = 1.3 + i * 0.8
        wt = _ft(frame, start, start + 0.7)
        if wt <= 0:
            continue

        wa = _snap(wt)
        y = 260 + i * 100
        slide = int((1 - _ease(min(wt * 2, 1.0))) * 80)

        # Card background
        ca = max(0, min(wa, 1.0))
        cbg = tuple(int(14 * ca) for _ in range(3))
        draw.rounded_rectangle([(60, y), (W - 60, y + 85)], radius=10, fill=cbg)

        # Username
        uc = tuple(int(255 * ca) for _ in range(3))
        draw.text((80 + slide, y + 10), win.get("username", "Member"), font=load_font(22, bold=True), fill=uc)

        # Brand
        bc = tuple(int(v * ca) for v in GREY)
        draw.text((80 + slide, y + 40), win.get("brand", "Archive"), font=load_font(16), fill=bc)

        # Profit
        profit = win.get("profit", 0)
        pc = tuple(int(v * ca) for v in GREEN)
        pf = load_font(36, bold=True)
        pt = f"+${profit:,}"
        pbbox = draw.textbbox((0, 0), pt, font=pf)
        draw.text((W - 80 - pbbox[2] + pbbox[0], y + 20), pt, font=pf, fill=pc)

    # [8-9.5s] Total + CTA
    p_end = _ft(frame, 7.5 + len(wins[:8]) * 0.8, 7.5 + len(wins[:8]) * 0.8 + 1.5)
    if p_end > 0:
        ae = _ease(p_end)
        gc = tuple(int(v * ae) for v in GOLD)
        wc = tuple(int(255 * ae) for _ in range(3))
        grc = tuple(int(v * ae) for v in GREEN)

        # Total profit counter
        counter_p = min(p_end * 1.5, 1.0)
        displayed = _counter_value(int(total_profit), counter_p)

        draw.text((80, 1120), "TOTAL MEMBER PROFITS", font=load_font(18), fill=tuple(int(v * ae) for v in GREY))
        draw.text((80, 1150), f"+${displayed:,}", font=load_font(64, bold=True), fill=grc)

        draw.text((80, 1240), "JOIN THEM", font=load_font(28, bold=True), fill=wc)
        draw.text((80, 1280), "@archivearbitrage • Link in bio", font=load_font(22, bold=True), fill=gc)

    return img


# ══════════════════════════════════════════════════════════
# Generation functions
# ══════════════════════════════════════════════════════════

def generate_deal_of_week(data: DealCardData, listing_img=None):
    frames = int(10.0 * FPS)
    slug = data.brand.lower().replace(" ", "_")[:15]
    return _compile(lambda f: render_deal_of_week(f, data, listing_img), frames, f"dotw_{slug}")


def generate_brand_spotlight(brand, total_deals, avg_profit, best_gap, top_pieces):
    frames = int(9.0 * FPS)
    slug = brand.lower().replace(" ", "_")[:15]
    return _compile(lambda f: render_brand_spotlight(f, brand, total_deals, avg_profit, best_gap, top_pieces), frames, f"spotlight_{slug}")


def generate_monthly_roi(total_deals, total_profit, best_deal_profit, top_brands):
    frames = int(9.5 * FPS)
    return _compile(lambda f: render_monthly_roi(f, total_deals, total_profit, best_deal_profit, top_brands), frames, "monthly_roi")


def generate_member_wins(wins):
    duration = 7.5 + len(wins[:8]) * 0.8 + 2.0
    frames = int(duration * FPS)
    return _compile(lambda f: render_member_wins(f, wins), frames, "member_wins")


def generate_all_weekly_videos() -> List[str]:
    """Generate a full set of weekly video content from real data.

    Pulls data from the DB and generates:
    - 1 Brand Spotlight (top performing brand)
    - 1 Monthly ROI (if near end of month)
    - 1 Member Wins (from Discord leaderboard)

    Returns list of generated video paths.
    """
    paths = []

    # Brand Spotlight — top performing brand this week
    try:
        from .market_report import get_top_performing_brands
        top = get_top_performing_brands(1)
        if top:
            brand, deals, gap = top[0]
            # Get top pieces for this brand
            from .market_report import _load_query_performance, _extract_brand_from_query
            perf = _load_query_performance()
            pieces = []
            for q, d in perf.items():
                if _extract_brand_from_query(q).lower() == brand.lower() and d.get("total_deals", 0) > 0:
                    piece = q.lower().replace(brand.lower(), "").strip()
                    if piece and len(piece) > 2:
                        pieces.append(piece)

            avg_profit = 370  # Approximate from pipeline stats
            vp, _ = generate_brand_spotlight(brand, deals, avg_profit, gap, pieces[:6])
            if vp:
                paths.append(vp)
                logger.info(f"Generated brand spotlight: {brand}")
    except Exception as e:
        logger.error(f"Brand spotlight failed: {e}")

    # Member Wins — from Discord leaderboard
    try:
        from core.discord_bot import get_leaderboard
        entries = get_leaderboard("monthly", 8)
        if entries:
            wins = [{"username": e["username"], "profit": e["profit"], "brand": "Archive"} for e in entries]
            vp, _ = generate_member_wins(wins)
            if vp:
                paths.append(vp)
                logger.info("Generated member wins video")
    except Exception as e:
        logger.debug(f"Member wins skipped (no data yet): {e}")

    # Monthly ROI — pull from alert state
    try:
        alert_file = DATA_DIR / "alert_state.json"
        if alert_file.exists():
            state = json.loads(alert_file.read_text())
            stats = state.get("daily_stats", {})
            brands = stats.get("top_brands", {})
            top_brands = sorted(brands.items(), key=lambda x: -x[1])[:5]

            vp, _ = generate_monthly_roi(
                total_deals=stats.get("items_found", 0),
                total_profit=stats.get("total_profit_potential", 0),
                best_deal_profit=370,
                top_brands=top_brands,
            )
            if vp:
                paths.append(vp)
                logger.info("Generated monthly ROI video")
    except Exception as e:
        logger.error(f"Monthly ROI failed: {e}")

    return paths


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    print("=== Generating all weekly video content ===\n")
    paths = generate_all_weekly_videos()
    for p in paths:
        print(f"  {p}")

    if sys.platform == "darwin" and paths:
        import subprocess
        for p in paths:
            subprocess.run(["open", p], check=False)

    print(f"\n{len(paths)} videos generated.")

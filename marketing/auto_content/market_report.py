"""
Auto-generate weekly market intelligence content from trend engine data.

Produces:
1. "Brands Trending This Week" image card + caption
2. "Best Profit Opportunities" image card + caption
3. Discord embed for #market-talk
4. Weekly recap carousel (top deals of the week)

Data sources:
- data/trends/query_performance.json — per-query stats
- data/alert_state.json — daily deal stats
- data/sold_cache.json — price velocity data

Run: python -m marketing.auto_content.market_report
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from PIL import ImageDraw

from .design import (
    INSTAGRAM_PORTRAIT, BLACK, DARK_BG, CARD_BG, MID_GREY, LIGHT_GREY,
    BODY_TEXT, OFF_WHITE, GOLD, BRIGHT_GOLD, GREEN, PROFIT_GREEN, RED,
    load_font, new_canvas, finalize, wrap_text, draw_text_centered,
    draw_hline, draw_hline_centered, draw_pill_badge, add_scanlines,
)
from .content_queue import save_to_queue
from .caption import generate_market_intel_caption, generate_weekly_recap_caption

logger = logging.getLogger("auto_content.market_report")

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TRENDS_DIR = DATA_DIR / "trends"
QUEUE_DIR = Path(__file__).parent / "queue" / "pending"


def _load_query_performance() -> dict:
    perf_file = TRENDS_DIR / "query_performance.json"
    if perf_file.exists():
        return json.loads(perf_file.read_text())
    return {}


def _load_alert_state() -> dict:
    state_file = DATA_DIR / "alert_state.json"
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except Exception:
            pass
    return {}


def _extract_brand_from_query(query: str) -> str:
    """Extract the brand name from a search query."""
    known_brands = [
        "chrome hearts", "rick owens", "maison margiela", "margiela",
        "enfants riches deprimes", "erd", "saint laurent", "jean paul gaultier",
        "helmut lang", "raf simons", "bottega veneta", "dior homme",
        "undercover", "balenciaga", "kapital", "number nine",
        "alexander mcqueen", "thierry mugler", "vivienne westwood",
        "julius", "ann demeulemeester", "dries van noten", "yohji yamamoto",
        "prada", "guidi", "acne studios", "carol christian poell",
    ]
    query_lower = query.lower()
    for brand in sorted(known_brands, key=len, reverse=True):
        if query_lower.startswith(brand):
            return brand.title()
    return query.split()[0].title() if query else "Unknown"


def get_brand_stats() -> dict[str, dict]:
    """Aggregate query performance by brand."""
    perf = _load_query_performance()
    brand_stats = defaultdict(lambda: {
        "total_deals": 0,
        "total_runs": 0,
        "best_gap": 0,
        "queries": 0,
        "total_alerts": 0,
    })

    for query, data in perf.items():
        brand = _extract_brand_from_query(query)
        stats = brand_stats[brand]
        stats["total_deals"] += data.get("total_deals", 0)
        stats["total_runs"] += data.get("total_runs", 0)
        stats["best_gap"] = max(stats["best_gap"], data.get("best_gap", 0))
        stats["queries"] += 1
        stats["total_alerts"] += data.get("public_alerts_sent", 0)

    return dict(brand_stats)


def get_top_performing_brands(top_n: int = 10) -> list[tuple[str, int, float]]:
    """Get top brands by deal count. Returns [(brand, deals, best_gap), ...]."""
    stats = get_brand_stats()
    sorted_brands = sorted(stats.items(), key=lambda x: -x[1]["total_deals"])
    return [
        (brand, data["total_deals"], data["best_gap"])
        for brand, data in sorted_brands[:top_n]
        if data["total_deals"] > 0
    ]


def generate_trending_brands_card() -> tuple[str, str]:
    """Generate a 'Brands Trending This Week' image card.

    Returns (image_path, caption).
    """
    W, H = INSTAGRAM_PORTRAIT
    img, draw = new_canvas(INSTAGRAM_PORTRAIT, BLACK)
    add_scanlines(draw, H)

    # Top accent
    draw.rectangle([(0, 0), (W, 4)], fill=GOLD)

    # Header
    draw.text((80, 40), "ARCHIVE ARBITRAGE", font=load_font(20), fill=MID_GREY)
    draw.text((W - 280, 40), "WEEKLY INTEL", font=load_font(20), fill=GOLD)
    draw_hline(draw, 75, color=(28, 28, 28))

    # Title
    y = 120
    title_font = load_font(56, bold=True)
    draw.text((80, y), "TOP", font=title_font, fill=OFF_WHITE)
    y += 70
    draw.text((80, y), "PERFORMING", font=title_font, fill=OFF_WHITE)
    y += 70
    draw.text((80, y), "BRANDS", font=title_font, fill=BRIGHT_GOLD)
    y += 90

    draw_hline(draw, y, color=GOLD, width=2)
    y += 30

    # Subtitle
    sub_font = load_font(24)
    week_label = f"Week of {date.today().strftime('%B %d, %Y')}"
    draw.text((80, y), week_label, font=sub_font, fill=MID_GREY)
    y += 45

    # Brand list
    top_brands = get_top_performing_brands(8)
    rank_font = load_font(28, bold=True)
    brand_font = load_font(28)
    stat_font = load_font(22)

    for i, (brand, deals, best_gap) in enumerate(top_brands):
        # Rank number
        rank_text = f"{i + 1:02d}"
        draw.text((80, y), rank_text, font=rank_font, fill=GOLD)

        # Brand name
        draw.text((140, y), brand.upper(), font=brand_font, fill=OFF_WHITE)

        # Stats on right
        stat_text = f"{deals} deals | {best_gap * 100:.0f}% best gap"
        bbox = draw.textbbox((0, 0), stat_text, font=stat_font)
        sw = bbox[2] - bbox[0]
        draw.text((W - 80 - sw, y + 5), stat_text, font=stat_font, fill=MID_GREY)

        y += 55

        if i < len(top_brands) - 1:
            draw_hline(draw, y - 12, x1=140, x2=W - 80, color=(28, 28, 28))

    # Footer
    y = H - 120
    draw_hline(draw, y, color=(28, 28, 28))
    y += 20
    draw.text((80, y), "Data from 7 platforms | 200+ queries | Updated weekly", font=load_font(20), fill=MID_GREY)
    draw_hline(draw, H - 60, color=(28, 28, 28))
    draw.text((80, H - 42), "@archivearbitrage", font=load_font(18), fill=GOLD)

    img = finalize(img)

    # Save
    timestamp = datetime.now().strftime("%Y%m%d")
    filename = f"trending_brands_{timestamp}.jpg"
    path = str(QUEUE_DIR / filename)
    img.save(path, "JPEG", quality=95)

    # Caption
    trending_up = [(brand, gap * 100) for brand, deals, gap in top_brands[:5]]
    caption = generate_market_intel_caption(
        trending_up=trending_up,
        trending_down=[],  # Could compute from historical data
        insight="The comp data shows where the market is mispricing — our subscribers get there first.",
    )

    save_to_queue(
        image_path=path,
        caption=caption,
        post_type="market_intel",
        content_pillar="market_intel",
    )

    return path, caption


def generate_weekly_recap_card(
    deals_data: Optional[list[dict]] = None,
) -> tuple[str, str]:
    """Generate a weekly recap image card.

    Args:
        deals_data: List of deal dicts with brand, profit, gap, title.
                    If None, pulls from alert_state.
    """
    W, H = INSTAGRAM_PORTRAIT
    img, draw = new_canvas(INSTAGRAM_PORTRAIT, BLACK)
    add_scanlines(draw, H)

    draw.rectangle([(0, 0), (W, 4)], fill=GOLD)

    # Header
    draw.text((80, 40), "ARCHIVE ARBITRAGE", font=load_font(20), fill=MID_GREY)
    draw_hline(draw, 75, color=(28, 28, 28))

    # Title
    y = 120
    huge = load_font(64, bold=True)
    draw.text((80, y), "THIS WEEK'S", font=huge, fill=OFF_WHITE)
    y += 80
    draw.text((80, y), "RESULTS", font=huge, fill=BRIGHT_GOLD)
    y += 100

    draw_hline(draw, y, color=GOLD, width=2)
    y += 25

    # Pull stats
    alert_state = _load_alert_state()
    daily_stats = alert_state.get("daily_stats", {})
    total_deals = daily_stats.get("items_found", 0)
    total_profit = daily_stats.get("total_profit_potential", 0)
    top_brands_dict = daily_stats.get("top_brands", {})
    top_brands = sorted(top_brands_dict.items(), key=lambda x: -x[1])

    # Big stats
    stat_font = load_font(52, bold=True)
    label_font = load_font(18)

    stats_row = [
        (f"{total_deals}", "DEALS SENT"),
        (f"${total_profit:,.0f}", "TOTAL PROFIT OPP."),
    ]

    col_w = (W - 160) // len(stats_row)
    for i, (value, label) in enumerate(stats_row):
        cx = 80 + i * col_w + col_w // 2

        vbbox = draw.textbbox((0, 0), value, font=stat_font)
        vw = vbbox[2] - vbbox[0]
        draw.text((cx - vw // 2, y), value, font=stat_font, fill=PROFIT_GREEN)

        lbbox = draw.textbbox((0, 0), label, font=label_font)
        lw = lbbox[2] - lbbox[0]
        draw.text((cx - lw // 2, y + 65), label, font=label_font, fill=MID_GREY)

    y += 115

    draw_hline(draw, y, color=(28, 28, 28))
    y += 25

    # Top brands
    draw.text((80, y), "TOP BRANDS", font=load_font(20), fill=GOLD)
    y += 35

    brand_font = load_font(26)
    count_font = load_font(22)

    for brand, count in top_brands[:6]:
        draw.text((100, y), brand.title(), font=brand_font, fill=OFF_WHITE)
        count_text = f"{count} deal{'s' if count > 1 else ''}"
        bbox = draw.textbbox((0, 0), count_text, font=count_font)
        cw = bbox[2] - bbox[0]
        draw.text((W - 100 - cw, y + 3), count_text, font=count_font, fill=MID_GREY)
        y += 45

    # Footer
    draw_hline(draw, H - 100, color=GOLD, width=1)
    cta_font = load_font(26, bold=True)
    draw.text((80, H - 75), "LINK IN BIO", font=cta_font, fill=GOLD)
    draw.text((80, H - 42), "@archivearbitrage", font=load_font(18), fill=MID_GREY)

    img = finalize(img)

    timestamp = datetime.now().strftime("%Y%m%d")
    filename = f"weekly_recap_{timestamp}.jpg"
    path = str(QUEUE_DIR / filename)
    img.save(path, "JPEG", quality=95)

    # Caption
    best_profit = max((d.get("profit", 0) for d in (deals_data or [])), default=total_profit / max(total_deals, 1))
    caption = generate_weekly_recap_caption(
        total_deals=total_deals,
        total_profit=total_profit,
        top_brands=top_brands[:5],
        best_deal_profit=best_profit,
        date_range=f"{(date.today() - timedelta(days=7)).strftime('%b %d')} - {date.today().strftime('%b %d')}",
    )

    save_to_queue(
        image_path=path,
        caption=caption,
        post_type="weekly_recap",
        content_pillar="social_proof",
    )

    return path, caption


def generate_all_weekly_content() -> list[str]:
    """Generate all weekly market intelligence content.

    Call this every Monday (e.g., via cron).
    Returns list of generated file paths.
    """
    paths = []

    try:
        path, _ = generate_trending_brands_card()
        paths.append(path)
        logger.info(f"Generated trending brands card: {path}")
    except Exception as e:
        logger.error(f"Trending brands generation failed: {e}")

    try:
        path, _ = generate_weekly_recap_card()
        paths.append(path)
        logger.info(f"Generated weekly recap card: {path}")
    except Exception as e:
        logger.error(f"Weekly recap generation failed: {e}")

    return paths


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    print("Generating weekly market intelligence content...\n")
    paths = generate_all_weekly_content()
    for p in paths:
        print(f"  Generated: {p}")

    if sys.platform == "darwin" and paths:
        import subprocess
        for p in paths:
            subprocess.run(["open", p], check=False)

    print(f"\nDone! {len(paths)} posts queued in marketing/auto_content/queue/pending/")

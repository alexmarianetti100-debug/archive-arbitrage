"""
HTML → Image renderer using Playwright (Chrome-quality Instagram graphics).

Replaces the PIL-based deal_card.py with browser-rendered HTML templates.
Uses Jinja2 for template injection, Playwright for screenshot.
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path(__file__).parent / "queue" / "pending"

_jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

# Brand accent colors (matches your dark aesthetic)
BRAND_COLORS = {
    "chrome hearts": "#c9a84c",
    "rick owens": "#8a8a8a",
    "maison margiela": "#e0e0e0",
    "margiela": "#e0e0e0",
    "saint laurent": "#c0c0c0",
    "enfants riches deprimes": "#c0392b",
    "erd": "#c0392b",
    "bottega veneta": "#4a8c5c",
    "helmut lang": "#d0d0d0",
    "raf simons": "#e07040",
    "dior": "#b8a080",
    "jean paul gaultier": "#9b59b6",
    "gaultier": "#9b59b6",
    "balenciaga": "#d0d0d0",
    "prada": "#c9a84c",
    "undercover": "#e0e0e0",
    "number nine": "#e0e0e0",
    "kapital": "#8b6914",
    "guidi": "#8a7060",
    "julius": "#999999",
    "ann demeulemeester": "#d0d0d0",
    "vivienne westwood": "#c0392b",
}

FIRE_MAP = {
    0: ("", "#555"),
    1: ("Good Find", "#888"),
    2: ("Hot Deal", "#e87040"),
    3: ("Fire Deal", "#ff6b00"),
}


def _brand_color(brand: str) -> str:
    return BRAND_COLORS.get(brand.lower().strip(), "#c9a84c")


def _auth_colors(pct: int) -> tuple[str, str]:
    if pct >= 80:
        return "#4ade80", "#22c55e"
    if pct >= 60:
        return "#c9a84c", "#a88a30"
    return "#e87040", "#c05030"


async def render_html(html: str, width: int = 1080, height: int = 1350) -> bytes:
    """Render an HTML string to PNG bytes using Playwright."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        page = await browser.new_page(viewport={"width": width, "height": height})
        await page.set_content(html, wait_until="networkidle")
        # Wait for fonts to load
        await page.wait_for_timeout(500)
        screenshot = await page.screenshot(type="png")
        await browser.close()

    return screenshot


async def render_deal_card(
    title: str,
    brand: str,
    source: str,
    buy_price: float,
    market_price: float,
    profit: float,
    margin: float,
    comp_count: int,
    auth_confidence: float = 0.0,
    fire_level: int = 0,
    image_url: str = "",
    season: str = "",
    size: str = "",
    condition: str = "",
    demand: str = "",
    save: bool = True,
) -> tuple[bytes, Optional[str]]:
    """Render a deal card and optionally save to queue."""
    fire_text, fire_color = FIRE_MAP.get(fire_level, FIRE_MAP[0])
    brand_color = _brand_color(brand)
    auth_pct = int(auth_confidence * 100)
    auth_start, auth_end = _auth_colors(auth_pct)
    gap_pct = int(margin * 100)

    template = _jinja_env.get_template("deal_card.html")
    html = template.render(
        title=title,
        brand=brand.upper(),
        source=source.upper(),
        buy_price=buy_price,
        market_price=market_price,
        profit=profit,
        gap_pct=gap_pct,
        comp_count=comp_count,
        auth_pct=auth_pct,
        fire_text=fire_text,
        fire_color=fire_color,
        brand_color=brand_color,
        auth_color_start=auth_start,
        auth_color_end=auth_end,
        image_url=image_url,
        season=season,
        size=size,
        condition=condition,
        demand=demand,
    )

    png_bytes = await render_html(html, 1080, 1350)

    path = None
    if save:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_brand = brand.lower().replace(" ", "_")[:20]
        filename = f"deal_{safe_brand}_{ts}.png"
        path = str(OUTPUT_DIR / filename)
        with open(path, "wb") as f:
            f.write(png_bytes)
        logger.info(f"Deal card saved: {path}")

    return png_bytes, path


async def render_text_post(
    content_html: str,
    headline_size: int = 52,
    save: bool = True,
    label: str = "text",
) -> tuple[bytes, Optional[str]]:
    """Render a text-based post (authority, FOMO, hot take, etc.)."""
    template = _jinja_env.get_template("text_post.html")
    html = template.render(
        content=content_html,
        headline_size=headline_size,
    )

    png_bytes = await render_html(html, 1080, 1080)

    path = None
    if save:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{label}_{ts}.png"
        path = str(OUTPUT_DIR / filename)
        with open(path, "wb") as f:
            f.write(png_bytes)
        logger.info(f"Text post saved: {path}")

    return png_bytes, path


# ── Convenience: render from DealCardData ───────────────────────────────────

async def render_from_deal_data(data) -> tuple[bytes, Optional[str]]:
    """Accept a DealCardData object and render a deal card."""
    return await render_deal_card(
        title=data.title,
        brand=data.brand,
        source=data.source,
        buy_price=data.buy_price,
        market_price=data.market_price,
        profit=data.profit,
        margin=data.margin,
        comp_count=data.comp_count,
        auth_confidence=data.auth_confidence,
        fire_level=data.fire_level,
        image_url=data.image_url or "",
        season=data.season_name or "",
        size=data.size or "",
        condition=data.condition or "",
        demand=data.demand_level or "",
    )


# ── Pre-built text post content ─────────────────────────────────────────────

TEXT_POSTS = {
    "data_authority": """
        <div class="headline">We scanned <span class="gold">10,247</span> listings today.</div>
        <div class="stat-callout">
            <div class="callout-item">
                <div class="callout-value gold">6</div>
                <div class="callout-label">Platforms</div>
            </div>
            <div class="callout-item">
                <div class="callout-value">105</div>
                <div class="callout-label">Active Queries</div>
            </div>
            <div class="callout-item">
                <div class="callout-value green">14</div>
                <div class="callout-label">Deals Found</div>
            </div>
        </div>
        <div class="body">
            Found <strong>14 deals</strong> your eyes would have missed.<br>
            3 sold within <span class="gold">8 minutes</span> of the alert.<br><br>
            The system doesn't sleep. Neither do the deals.
        </div>
    """,

    "archive_vs_hype": """
        <div class="headline">Archive <span class="dim">vs.</span> Hype.</div>
        <div class="divider"></div>
        <div class="stat-callout">
            <div class="callout-item">
                <div class="callout-value dim">5-15%</div>
                <div class="callout-label">Hype Margins</div>
            </div>
            <div class="callout-item">
                <div class="callout-value green">40-65%</div>
                <div class="callout-label">Archive Margins</div>
            </div>
        </div>
        <div class="body">
            Hype kids flip Jordans for <span class="dim">$30 profit</span>.<br>
            Archive flippers sell a Helmut Lang jacket for <span class="gold">$400</span>.<br><br>
            Different market. Different game. Different money.
        </div>
    """,

    "roi_breakdown": """
        <div class="headline">What <span class="gold">$30/month</span> actually gets you.</div>
        <div class="divider"></div>
        <div class="body">
            Week 1: Chrome Hearts Tiny Ring &mdash; <span class="gold">$290 profit</span><br>
            Week 2: Prada Re-Nylon Jacket &mdash; <span class="gold">$280 profit</span><br>
            Week 3: Helmut Lang Jacket &mdash; <span class="gold">$295 profit</span><br>
            Week 4: Balenciaga Sweatpants &mdash; <span class="gold">$275 profit</span>
        </div>
        <div class="stat-callout">
            <div class="callout-item">
                <div class="callout-value green">$1,140</div>
                <div class="callout-label">Monthly Opportunity</div>
            </div>
            <div class="callout-item">
                <div class="callout-value gold">38x</div>
                <div class="callout-label">Return on Sub</div>
            </div>
        </div>
        <div class="body">
            One flip pays for <strong>3 years</strong>.
        </div>
    """,

    "free_channel": """
        <div class="headline" style="font-size: 46px; max-width: 800px;">
            We post 1-2 deals a day<br>for <span class="gold">free</span>.
        </div>
        <div class="divider"></div>
        <div class="body" style="font-size: 28px; line-height: 1.7;">
            <span class="dim">45 minutes</span> after subscribers get them.<br><br>
            Most are already sold by then.<br><br>
            <strong>That's the point.</strong>
        </div>
    """,

    "ai_discovery": """
        <div class="headline">Our AI tested <span class="gold">15 new queries</span> overnight.</div>
        <div class="divider"></div>
        <div class="body">
            6 promoted to active monitoring:<br><br>
            &rarr; Balenciaga Skater Sweatpants <span class="dim">(12 deals in 6 runs)</span><br>
            &rarr; Chrome Hearts Tiny Ring <span class="gold">($1,073 profit window)</span><br>
            &rarr; Chrome Hearts Sneakers <span class="gold">($548 in one scan)</span><br>
            &rarr; Helmut Lang Jacket <span class="dim">(10 deals in 4 runs)</span><br>
            &rarr; Prada Re-Nylon<br>
            &rarr; Bottega Veneta Knit Sweater<br><br>
            The system learns which queries find money &mdash;<br>
            and <strong>kills the ones that don't</strong>.
        </div>
    """,
}


async def render_all_text_posts(save: bool = True) -> list[str]:
    """Render all pre-built text posts. Returns list of saved paths."""
    paths = []
    for label, content in TEXT_POSTS.items():
        _, path = await render_text_post(content, save=save, label=label)
        if path:
            paths.append(path)
            print(f"  Rendered: {label} → {path}")
    return paths


# ── CLI entry point ─────────────────────────────────────────────────────────

async def _main():
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "text":
        print("Rendering all text posts...")
        paths = await render_all_text_posts()
        print(f"\nDone — {len(paths)} posts rendered.")
        return

    # Default: render a sample deal card
    print("Rendering sample deal card...")
    _, path = await render_deal_card(
        title="Leather Geobasket High Top Sneakers",
        brand="Rick Owens",
        source="Grailed",
        buy_price=280,
        market_price=650,
        profit=370,
        margin=0.57,
        comp_count=8,
        auth_confidence=0.87,
        fire_level=3,
        season="FW08",
        demand="hot",
    )
    print(f"Saved: {path}")

    print("\nRendering sample text post...")
    _, path = await render_text_post(
        TEXT_POSTS["archive_vs_hype"],
        label="archive_vs_hype",
    )
    print(f"Saved: {path}")


if __name__ == "__main__":
    asyncio.run(_main())

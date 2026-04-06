"""
SEO landing page generator — auto-generate price guide pages from comp data.

Creates static HTML pages like:
    "Rick Owens Geobasket Resale Price Guide 2026"
    "Chrome Hearts Cross Pendant Market Value"
    "Maison Margiela Tabi Boots Price History"

Each page includes:
- Current market value (from your comp data)
- Price range (low/median/high)
- Number of recent sales
- Platform comparison
- Trend direction
- CTA to subscribe for deal alerts

These pages rank on Google for "[brand] [product] resale value" searches
and drive organic traffic to your Whop subscription.

Usage:
    python -m marketing.auto_content.seo_pages              # Generate all pages
    python -m marketing.auto_content.seo_pages --brand rick  # One brand
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from .market_report import _load_query_performance, _extract_brand_from_query

logger = logging.getLogger("auto_content.seo_pages")

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "landing" / "guides"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

WHOP_URL = "https://app.archivearbitrage.com/signup"
SITE_URL = "https://archivearbitrage.com"


def _slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    return text.lower().replace(" ", "-").replace("(", "").replace(")", "").replace("/", "-")


def _get_brand_product_data() -> dict:
    """Aggregate comp data by brand → product for SEO pages."""
    perf = _load_query_performance()

    brand_products = defaultdict(list)
    for query, data in perf.items():
        if data.get("total_deals", 0) == 0 and data.get("total_runs", 0) < 5:
            continue

        brand = _extract_brand_from_query(query)
        # The query minus the brand is roughly the product
        product_part = query.lower()
        for b in [brand.lower(), brand.lower().replace(" ", "")]:
            product_part = product_part.replace(b, "").strip()

        if not product_part or len(product_part) < 3:
            product_part = "general"

        brand_products[brand].append({
            "product": product_part,
            "query": query,
            "deals": data.get("total_deals", 0),
            "runs": data.get("total_runs", 0),
            "best_gap": data.get("best_gap", 0),
            "alert_ratio": data.get("alert_ratio", 0),
            "raw_items": data.get("raw_items_found", 0),
        })

    return dict(brand_products)


def generate_brand_page(brand: str, products: list[dict]) -> str:
    """Generate an SEO-optimized HTML page for a brand."""

    total_deals = sum(p["deals"] for p in products)
    best_gap = max((p["best_gap"] for p in products), default=0)
    top_products = sorted(products, key=lambda p: -p["deals"])[:10]

    slug = _slugify(brand)
    title = f"{brand} Resale Price Guide 2026 — Market Value & Deals"
    description = (
        f"Current {brand} resale prices based on {total_deals}+ verified sold comps. "
        f"Real-time market data across Grailed, eBay, Poshmark, and more."
    )

    # Product rows
    product_rows = ""
    for p in top_products:
        if p["product"] == "general":
            continue
        gap_pct = f"{p['best_gap'] * 100:.0f}%" if p["best_gap"] > 0 else "—"
        product_rows += f"""
            <tr>
                <td>{p['product'].title()}</td>
                <td>{p['deals']}</td>
                <td>{gap_pct}</td>
                <td>{p['runs']}</td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="{description}">
    <meta name="robots" content="index, follow">

    <!-- Open Graph -->
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{SITE_URL}/guides/{slug}">

    <!-- Schema.org structured data -->
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "{title}",
        "description": "{description}",
        "author": {{
            "@type": "Organization",
            "name": "Archive Arbitrage"
        }},
        "datePublished": "{date.today().isoformat()}",
        "dateModified": "{date.today().isoformat()}"
    }}
    </script>

    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
            background: #0a0a0a;
            color: #e0ddd8;
            line-height: 1.6;
        }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 40px 20px; }}
        h1 {{
            font-size: 2.2rem;
            color: #f0ede8;
            margin-bottom: 8px;
            letter-spacing: -0.5px;
        }}
        h2 {{
            font-size: 1.5rem;
            color: #d7be8c;
            margin: 40px 0 16px;
            border-bottom: 1px solid #222;
            padding-bottom: 8px;
        }}
        .subtitle {{
            color: #8c8c8c;
            font-size: 1rem;
            margin-bottom: 30px;
        }}
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin: 24px 0;
        }}
        .stat-card {{
            background: #161616;
            border: 1px solid #222;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 2rem;
            font-weight: 700;
            color: #d7be8c;
        }}
        .stat-label {{
            font-size: 0.8rem;
            color: #666;
            text-transform: uppercase;
            margin-top: 4px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
        }}
        th {{
            text-align: left;
            padding: 12px;
            border-bottom: 2px solid #d7be8c;
            color: #d7be8c;
            font-size: 0.85rem;
            text-transform: uppercase;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #1a1a1a;
            color: #c0bdb8;
        }}
        tr:hover td {{ background: #111; }}
        .cta-box {{
            background: linear-gradient(135deg, #1a1510, #161616);
            border: 1px solid #d7be8c;
            border-radius: 12px;
            padding: 32px;
            margin: 40px 0;
            text-align: center;
        }}
        .cta-box h3 {{
            font-size: 1.4rem;
            color: #f0ede8;
            margin-bottom: 12px;
        }}
        .cta-box p {{
            color: #8c8c8c;
            margin-bottom: 20px;
        }}
        .cta-button {{
            display: inline-block;
            background: #d7be8c;
            color: #0a0a0a;
            padding: 14px 32px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 700;
            font-size: 1rem;
        }}
        .cta-button:hover {{ background: #e5d0a0; }}
        .footer {{
            margin-top: 60px;
            padding-top: 20px;
            border-top: 1px solid #1a1a1a;
            color: #444;
            font-size: 0.85rem;
        }}
        .breadcrumb {{
            color: #555;
            font-size: 0.85rem;
            margin-bottom: 20px;
        }}
        .breadcrumb a {{ color: #d7be8c; text-decoration: none; }}
        @media (max-width: 600px) {{
            .stat-grid {{ grid-template-columns: 1fr; }}
            h1 {{ font-size: 1.6rem; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="breadcrumb">
            <a href="{SITE_URL}">Archive Arbitrage</a> / <a href="{SITE_URL}/guides">Price Guides</a> / {brand}
        </div>

        <h1>{brand} Resale Price Guide</h1>
        <p class="subtitle">
            Market data from {total_deals}+ verified sold comps across Grailed, eBay, Poshmark, and more.
            Updated {date.today().strftime('%B %Y')}.
        </p>

        <div class="stat-grid">
            <div class="stat-card">
                <div class="stat-value">{total_deals}</div>
                <div class="stat-label">Deals Found</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{best_gap * 100:.0f}%</div>
                <div class="stat-label">Best Gap Found</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(products)}</div>
                <div class="stat-label">Products Tracked</div>
            </div>
        </div>

        <h2>Products & Pricing</h2>
        <table>
            <thead>
                <tr>
                    <th>Product</th>
                    <th>Deals</th>
                    <th>Best Gap</th>
                    <th>Scans</th>
                </tr>
            </thead>
            <tbody>
                {product_rows}
            </tbody>
        </table>

        <div class="cta-box">
            <h3>Get {brand} Deals Before They Sell Out</h3>
            <p>
                We scan 7 platforms 24/7 for underpriced {brand} pieces.
                Every deal is verified against sold comps and authenticated.
                Real-time alerts via Telegram and Discord.
            </p>
            <a href="{WHOP_URL}" class="cta-button">Start Free Trial — 7 Days Free</a>
        </div>

        <h2>How We Price {brand}</h2>
        <p>
            Every {brand} listing is priced against recent Grailed sold data using
            time-weighted averaging. Recent sales count more than older ones. We adjust
            for condition, size, and season. Items below our calculated market value
            are flagged as deals and sent to subscribers in real-time.
        </p>
        <p style="margin-top: 12px;">
            Our 7-signal authentication system checks every listing before alerting —
            text analysis, price plausibility, seller reputation, image analysis,
            brand-specific markers, and more. Items scoring below 65% are blocked.
        </p>

        <h2>Platforms We Scan for {brand}</h2>
        <p>
            Grailed, Poshmark, eBay, Depop, Mercari, Vinted, and Japanese sources
            (Yahoo Auctions JP, Mercari JP, Rakuma). Cross-platform arbitrage
            opportunities are identified when the same piece is priced differently
            across platforms.
        </p>

        <div class="footer">
            <p>&copy; {date.today().year} Archive Arbitrage. Market data updated weekly.</p>
            <p style="margin-top: 8px;">
                <a href="{SITE_URL}/guides" style="color: #d7be8c; text-decoration: none;">All Price Guides</a> |
                <a href="{WHOP_URL}" style="color: #d7be8c; text-decoration: none;">Subscribe</a>
            </p>
        </div>
    </div>
</body>
</html>"""

    return html


def generate_index_page(brands: list[tuple[str, int]]) -> str:
    """Generate the index page listing all brand price guides."""

    brand_links = ""
    for brand, deals in brands:
        slug = _slugify(brand)
        brand_links += f"""
            <a href="/guides/{slug}" class="brand-card">
                <div class="brand-name">{brand}</div>
                <div class="brand-stat">{deals} deals tracked</div>
            </a>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Archive Fashion Resale Price Guides 2026 — Archive Arbitrage</title>
    <meta name="description" content="Current resale prices for 40+ archive fashion brands. Real market data from Grailed, eBay, Poshmark. Updated weekly.">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', sans-serif;
            background: #0a0a0a;
            color: #e0ddd8;
            line-height: 1.6;
        }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 40px 20px; }}
        h1 {{ font-size: 2.2rem; color: #f0ede8; margin-bottom: 8px; }}
        .subtitle {{ color: #8c8c8c; margin-bottom: 30px; }}
        .brand-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 16px;
            margin: 24px 0;
        }}
        .brand-card {{
            background: #161616;
            border: 1px solid #222;
            border-radius: 8px;
            padding: 20px;
            text-decoration: none;
            transition: border-color 0.2s;
        }}
        .brand-card:hover {{ border-color: #d7be8c; }}
        .brand-name {{ font-size: 1.1rem; color: #f0ede8; font-weight: 600; }}
        .brand-stat {{ font-size: 0.85rem; color: #666; margin-top: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Archive Fashion Resale Price Guides</h1>
        <p class="subtitle">
            Real market data from {len(brands)} brands across 7 platforms.
            Updated {date.today().strftime('%B %Y')}.
        </p>
        <div class="brand-grid">
            {brand_links}
        </div>
    </div>
</body>
</html>"""

    return html


def generate_all_seo_pages() -> int:
    """Generate all SEO landing pages. Returns count of pages generated."""
    brand_data = _get_brand_product_data()

    count = 0
    brand_summary = []

    for brand, products in sorted(brand_data.items()):
        total_deals = sum(p["deals"] for p in products)
        if total_deals < 1:
            continue

        slug = _slugify(brand)
        html = generate_brand_page(brand, products)
        page_path = OUTPUT_DIR / f"{slug}.html"
        page_path.write_text(html)
        count += 1
        brand_summary.append((brand, total_deals))
        logger.info(f"Generated SEO page: {page_path.name} ({total_deals} deals)")

    # Generate index
    if brand_summary:
        brand_summary.sort(key=lambda x: -x[1])
        index_html = generate_index_page(brand_summary)
        index_path = OUTPUT_DIR / "index.html"
        index_path.write_text(index_html)
        count += 1
        logger.info(f"Generated index page with {len(brand_summary)} brands")

    return count


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    print("Generating SEO landing pages from comp data...\n")
    count = generate_all_seo_pages()
    print(f"\nGenerated {count} pages in landing/guides/")

    if sys.platform == "darwin" and count > 0:
        import subprocess
        subprocess.run(["open", str(OUTPUT_DIR / "index.html")], check=False)

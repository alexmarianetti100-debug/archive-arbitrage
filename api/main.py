"""
FastAPI application for Archive Arbitrage.
"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from db.sqlite_models import init_db, get_items, get_item_by_id, get_stats, get_price_history, get_sold_comps, get_sold_comps_stats, save_sold_comp, get_qualified_items, Item
from scrapers import GrailedScraper


# Pydantic models for API
class ItemResponse(BaseModel):
    id: int
    title: str
    brand: Optional[str]
    category: Optional[str]
    size: Optional[str]
    condition: Optional[str]
    price: float  # our_price
    original_price: float  # source_price
    market_price: Optional[float]
    margin_percent: Optional[float]
    images: List[str]
    source: str
    source_url: str
    is_auction: bool
    status: str
    # Qualification data (Pass 2)
    deal_grade: Optional[str] = None
    deal_grade_reasoning: Optional[str] = None
    comp_count: Optional[int] = None
    high_quality_comps: Optional[int] = None
    demand_score: Optional[float] = None
    demand_level: Optional[str] = None
    sold_count: Optional[int] = None
    active_count: Optional[int] = None
    exact_sell_price: Optional[float] = None
    exact_profit: Optional[float] = None
    exact_margin: Optional[float] = None
    sell_through_rate: Optional[float] = None
    est_days_to_sell: Optional[float] = None
    qualified_at: Optional[str] = None
    # Advanced volume metrics
    weighted_volume: Optional[float] = None
    sales_per_day: Optional[float] = None
    volume_trend: Optional[str] = None
    same_size_sold: Optional[int] = None
    price_trend_percent: Optional[float] = None
    # Exact season/year (Quick Win)
    exact_season: Optional[str] = None
    exact_year: Optional[int] = None
    season_confidence: Optional[str] = None
    # Image fingerprinting (Phase 1.1)
    image_hash: Optional[str] = None
    image_phash: Optional[str] = None

    @classmethod
    def from_db(cls, item: Item) -> "ItemResponse":
        return cls(
            id=item.id,
            title=item.title,
            brand=item.brand,
            category=item.category,
            size=item.size,
            condition=item.condition,
            price=item.our_price or 0,
            original_price=item.source_price,
            market_price=item.market_price,
            margin_percent=item.margin_percent,
            images=item.images or [],
            source=item.source,
            source_url=item.source_url,
            is_auction=item.is_auction,
            status=item.status,
            deal_grade=item.deal_grade,
            deal_grade_reasoning=item.deal_grade_reasoning,
            comp_count=item.comp_count,
            high_quality_comps=item.high_quality_comps,
            demand_score=item.demand_score,
            demand_level=item.demand_level,
            sold_count=item.sold_count,
            active_count=item.active_count,
            exact_sell_price=item.exact_sell_price,
            exact_profit=item.exact_profit,
            exact_margin=item.exact_margin,
            sell_through_rate=item.sell_through_rate,
            est_days_to_sell=item.est_days_to_sell,
            qualified_at=item.qualified_at,
            weighted_volume=item.weighted_volume,
            sales_per_day=item.sales_per_day,
            volume_trend=item.volume_trend,
            same_size_sold=item.same_size_sold,
            price_trend_percent=item.price_trend_percent,
            exact_season=item.exact_season,
            exact_year=item.exact_year,
            season_confidence=item.season_confidence,
            image_hash=item.image_hash,
            image_phash=item.image_phash,
        )


class ItemListResponse(BaseModel):
    items: List[ItemResponse]
    total: int
    page: int
    page_size: int


class StatsResponse(BaseModel):
    total_items: int
    active_items: int
    unique_brands: int
    avg_margin: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print("Starting Archive Arbitrage API...")
    init_db()
    try:
        from telegram_bot import init_telegram_db
        init_telegram_db()
    except Exception:
        pass
    yield
    print("Shutting down...")


app = FastAPI(
    title="Archive Arbitrage",
    description="API for archive fashion marketplace",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for frontend (allow all origins for local development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Serve the frontend."""
    # Try new React frontend first
    frontend_path = Path(__file__).parent.parent / "frontend-dist" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path)
    # Fallback to old frontend
    frontend_path = Path(__file__).parent.parent / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path)
    return {"status": "ok", "service": "archive-arbitrage"}


@app.get("/api/items", response_model=ItemListResponse)
async def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=1000),  # Allow up to 1000 for full load
    brand: Optional[str] = None,
    category: Optional[str] = None,
    size: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_sold_count: Optional[int] = Query(None, ge=0, description="Minimum Grailed sold count (selling volume)"),
    season: Optional[str] = Query(None, pattern="^(FW|SS|AW|RESORT|CRUISE|PF)$", description="Filter by season (FW, SS, etc.)"),
    year: Optional[int] = Query(None, ge=1970, le=2030, description="Filter by exact year"),
    year_min: Optional[int] = Query(None, ge=1970, le=2030, description="Minimum year"),
    year_max: Optional[int] = Query(None, ge=1970, le=2030, description="Maximum year"),
    sort: str = Query("newest", pattern="^(newest|grade_asc|profit_desc|margin_desc|sellthrough_desc|days_asc|price_asc|price_desc|sold_count_desc)$"),
):
    """List items available for purchase."""
    offset = (page - 1) * page_size
    
    items = get_items(
        status="active",
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        min_sold_count=min_sold_count,
        season=season,
        year=year,
        year_min=year_min,
        year_max=year_max,
        sort=sort,
        limit=page_size,
        offset=offset,
    )
    
    # Get total count (simplified - would need separate count query for pagination)
    all_items = get_items(status="active", brand=brand, min_price=min_price, max_price=max_price, min_sold_count=min_sold_count, season=season, year=year, year_min=year_min, year_max=year_max, sort=sort, limit=1000)
    total = len(all_items)
    
    return ItemListResponse(
        items=[ItemResponse.from_db(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@app.get("/api/items/{item_id}", response_model=ItemResponse)
async def get_item(item_id: int):
    """Get single item details."""
    item = get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return ItemResponse.from_db(item)


@app.get("/api/items/{item_id}/price-history")
async def get_item_price_history(item_id: int):
    """Get price history for an item."""
    item = get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    history = get_price_history(item_id)
    
    # Add current price as most recent
    return {
        "current": {
            "source_price": item.source_price,
            "our_price": item.our_price,
            "recorded_at": item.updated_at
        },
        "history": history
    }


@app.get("/api/items/{item_id}/market-data")
async def get_item_market_data(item_id: int):
    """Get market data for an item (active listings as demand proxy)."""
    item = get_item_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Create search key from brand
    search_key = (item.brand or '').strip().lower()
    if not search_key:
        return {"search_key": "", "listings": [], "stats": None, "demand_level": "unknown"}
    
    # Fetch active listings from Grailed to gauge demand
    try:
        async with GrailedScraper(use_proxies=False) as scraper:
            active_items = await scraper.search(search_key, max_results=20)
            
            if not active_items:
                return {
                    "search_key": search_key,
                    "listings": [],
                    "stats": None,
                    "demand_level": "unknown"
                }
            
            prices = [i.price for i in active_items if i.price > 0]
            
            # Calculate stats
            stats = {
                "count": len(active_items),
                "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
                "min_price": min(prices) if prices else None,
                "max_price": max(prices) if prices else None,
            }
            
            # Determine demand level based on listing volume
            if len(active_items) >= 15:
                demand_level = "high"
            elif len(active_items) >= 5:
                demand_level = "medium"
            else:
                demand_level = "low"
            
            # Return top listings for display
            listings = [
                {
                    "title": i.title[:60],
                    "price": i.price,
                    "image_url": i.images[0] if i.images else None,
                    "url": i.url,
                }
                for i in active_items[:6]
            ]
            
            return {
                "search_key": search_key,
                "listings": listings,
                "stats": stats,
                "demand_level": demand_level,
            }
            
    except Exception as e:
        print(f"Error fetching market data: {e}")
        return {"search_key": search_key, "listings": [], "stats": None, "demand_level": "unknown"}


@app.get("/api/deals")
async def list_deals(
    grade: Optional[str] = Query(None, pattern="^[A-D]$"),
    brand: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """List qualified deals, optionally filtered by grade."""
    deals = get_qualified_items(grade=grade, brand=brand, limit=limit)
    return {"deals": deals, "total": len(deals)}


@app.get("/api/stats", response_model=StatsResponse)
async def get_statistics():
    """Get store statistics."""
    stats = get_stats()
    return StatsResponse(**stats)


@app.get("/api/brands")
async def list_brands():
    """List all brands in the database."""
    items = get_items(status="active", limit=1000)
    brands = set()
    for item in items:
        if item.brand:
            brands.add(item.brand)
    return {"brands": sorted(list(brands))}


@app.get("/api/volume-stats")
async def get_volume_statistics():
    """Get volume analytics for dashboard."""
    items = get_items(status="active", limit=10000)
    
    # Volume distribution
    vol_ranges = {
        "hot": 0,      # 500+
        "warm": 0,     # 200-499
        "mild": 0,     # 50-199
        "cold": 0,     # <50
        "unknown": 0,  # no data
    }
    
    trend_counts = {
        "accelerating": 0,
        "steady": 0,
        "decelerating": 0,
        "unknown": 0,
    }
    
    total_volume = 0
    items_with_volume = 0
    
    for item in items:
        vol = item.weighted_volume or 0
        if vol >= 500:
            vol_ranges["hot"] += 1
        elif vol >= 200:
            vol_ranges["warm"] += 1
        elif vol >= 50:
            vol_ranges["mild"] += 1
        elif vol > 0:
            vol_ranges["cold"] += 1
        else:
            vol_ranges["unknown"] += 1
        
        if vol > 0:
            total_volume += vol
            items_with_volume += 1
        
        trend = item.volume_trend or "unknown"
        trend_counts[trend] = trend_counts.get(trend, 0) + 1
    
    return {
        "total_items": len(items),
        "items_with_volume": items_with_volume,
        "avg_volume": round(total_volume / items_with_volume, 1) if items_with_volume else 0,
        "volume_distribution": vol_ranges,
        "trend_distribution": trend_counts,
        "top_volume_items": [
            {
                "id": item.id,
                "brand": item.brand,
                "title": item.title[:50],
                "volume": item.weighted_volume,
                "trend": item.volume_trend,
                "sales_per_day": item.sales_per_day,
            }
            for item in sorted(items, key=lambda x: x.weighted_volume or 0, reverse=True)[:10]
            if item.weighted_volume and item.weighted_volume > 0
        ],
    }


@app.get("/api/products")
async def list_products(
    min_sales: int = Query(3, ge=1),
    high_velocity_only: bool = False,
):
    """List products in the catalog."""
    from db.sqlite_models import get_high_velocity_products
    
    if high_velocity_only:
        products = get_high_velocity_products(min_sales_30d=5)
    else:
        # Get all products with minimum sales
        import sqlite3
        conn = sqlite3.connect(Path(__file__).parent.parent / "data" / "archive.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM products WHERE total_sales >= ? ORDER BY sales_30d DESC",
            (min_sales,)
        )
        from db.sqlite_models import _row_to_product
        products = [_row_to_product(row) for row in cursor.fetchall()]
        conn.close()
    
    return {
        "products": [
            {
                "id": p.id,
                "canonical_name": p.canonical_name,
                "brand": p.brand,
                "sub_brand": p.sub_brand,
                "model": p.model,
                "item_type": p.item_type,
                "total_sales": p.total_sales,
                "sales_30d": p.sales_30d,
                "sales_90d": p.sales_90d,
                "velocity_trend": p.velocity_trend,
                "is_high_velocity": p.is_high_velocity,
            }
            for p in products
        ]
    }


@app.get("/api/arbitrage")
async def list_arbitrage(
    min_profit: float = Query(50, ge=0),
    max_items: int = Query(100, ge=1, le=500),
):
    """List cross-platform arbitrage opportunities."""
    import asyncio
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from detect_arbitrage import ArbitrageDetector
    
    detector = ArbitrageDetector()
    detector.min_profit = min_profit
    
    opportunities = await detector.find_arbitrage_opportunities(max_items=max_items)
    
    return {
        "opportunities": [
            {
                "fingerprint_hash": opp.fingerprint_hash,
                "canonical_name": opp.canonical_name,
                "buy_platform": opp.buy_platform,
                "buy_price": opp.buy_price,
                "sell_platform": opp.sell_platform,
                "sell_reference_price": opp.sell_reference_price,
                "net_profit": opp.net_profit,
                "net_margin": opp.net_margin,
                "confidence": opp.confidence,
                "reasoning": opp.reasoning,
            }
            for opp in opportunities
        ],
        "total": len(opportunities),
    }


# ---------------------------------------------------------------------------
# Landing Page
# ---------------------------------------------------------------------------

@app.get("/landing", response_class=HTMLResponse)
async def landing_page():
    """Serve the landing/marketing page."""
    import os
    landing_path = Path(__file__).parent.parent / "landing" / "index.html"
    if not landing_path.exists():
        raise HTTPException(status_code=404, detail="Landing page not found")
    
    html = landing_path.read_text()
    
    # Inject Stripe payment link if configured
    payment_link = os.getenv("STRIPE_PAYMENT_LINK", "")
    if payment_link:
        html = html.replace("%%STRIPE_PAYMENT_LINK%%", payment_link)
    
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# Stripe Webhook
# ---------------------------------------------------------------------------

@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events for subscription management."""
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature", "")
        
        from stripe_billing import verify_webhook_signature, process_webhook_event
        
        event = verify_webhook_signature(payload, sig_header)
        if not event:
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        await process_webhook_event(event)
        return {"received": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook error: {e}")


# ---------------------------------------------------------------------------
# Telegram Bot Webhook (optional — alternative to polling)
# ---------------------------------------------------------------------------

@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram bot updates via webhook (alternative to polling)."""
    try:
        update = await request.json()
        from telegram_bot import process_update
        await process_update(update)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

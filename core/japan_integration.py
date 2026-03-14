"""
Japan Arbitrage Integration Module

Integrates Japan auction monitoring with the main Archive Arbitrage system.
Scrapes Yahoo Auctions JP via proxy services and alerts on profitable deals.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from pathlib import Path
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from core.japan_cost_calculator import (
    JapanCostCalculator,
    calculate_japan_cost,
    is_arbitrage_profitable,
    PROXY_SERVICES,
)
from core.blue_chip_targets import BLUE_CHIP_WATCHES, BLUE_CHIP_BAGS, BLUE_CHIP_JEWELRY, BLUE_CHIP_FASHION
from core.mercari_scraper import MercariJapanScraper, MercariItem
from core.rakuma_scraper import RakumaJapanScraper, RakumaItem
from core.mercari_direct import MercariDirectScraper, HAS_MERCAPI
from core.robust_scraper import MercariRobustScraper
from core.yahoo_auctions_jp import YahooAuctionsScraper, YahooAuctionItem

logger = logging.getLogger("japan_integration")

JAPAN_PERF_FILE = Path(__file__).parent.parent / "data" / "trends" / "japan_query_performance.json"
GOLDEN_CATALOG_FILE = Path(__file__).parent.parent / "data" / "trends" / "golden_catalog.json"


def _load_japan_perf() -> dict:
    """Load Japan query performance telemetry."""
    if JAPAN_PERF_FILE.exists():
        try:
            with open(JAPAN_PERF_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_japan_perf(perf: dict):
    """Save Japan query performance telemetry."""
    try:
        JAPAN_PERF_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = JAPAN_PERF_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(perf, f, indent=2)
        tmp.replace(JAPAN_PERF_FILE)
    except Exception as e:
        logger.warning(f"Failed to save Japan perf: {e}")


def log_japan_query_performance(
    en_query: str,
    platform: str,
    items_found: int,
    deals_found: int,
    best_margin: float = 0.0,
):
    """Record telemetry for a Japan query run.

    Args:
        en_query: English query string (used as key).
        platform: 'yahoo', 'mercari', or 'rakuma'.
        items_found: Raw items returned by scraper.
        deals_found: Items that passed profitability filter.
        best_margin: Best margin % seen this run.
    """
    perf = _load_japan_perf()
    key = en_query.lower().strip()
    if key not in perf:
        perf[key] = {
            "total_runs": 0,
            "total_deals": 0,
            "best_margin": 0.0,
            "last_run": None,
            "items_found_total": 0,
            "by_platform": {},
        }
    entry = perf[key]
    entry["total_runs"] += 1
    entry["total_deals"] += deals_found
    entry["best_margin"] = max(entry["best_margin"], best_margin)
    entry["last_run"] = datetime.utcnow().isoformat()
    entry["items_found_total"] += items_found

    # Per-platform breakdown
    plat = entry.setdefault("by_platform", {}).setdefault(platform, {"runs": 0, "deals": 0, "items": 0})
    plat["runs"] += 1
    plat["deals"] += deals_found
    plat["items"] += items_found

    _save_japan_perf(perf)


def _load_golden_catalog() -> dict:
    """Load the main pipeline's golden catalog for priority scoring."""
    if GOLDEN_CATALOG_FILE.exists():
        try:
            with open(GOLDEN_CATALOG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def prioritize_japan_targets(targets: list[dict]) -> list[dict]:
    """Re-order Japan targets using main pipeline golden catalog scores.

    Targets whose ``en`` query appears in the golden catalog are sorted by
    opportunity_score (descending).  Targets not in the catalog keep their
    original order but are appended after catalog-matched targets.

    Also considers Japan-specific telemetry: targets with high deal rates
    get a boost, traps (many runs, 0 deals) get demoted.
    """
    catalog = _load_golden_catalog()
    japan_perf = _load_japan_perf()

    # Build a lookup from EN query -> opportunity score
    catalog_scores: dict[str, float] = {}
    for entry in catalog.get("catalog", []):
        q = entry.get("query", "").lower().strip()
        catalog_scores[q] = entry.get("opportunity_score", 0)

    def _score(target: dict) -> float:
        en = target["en"].lower().strip()
        # Base score from golden catalog (0 if not present)
        base = catalog_scores.get(en, 0)

        # Japan telemetry boost/penalty
        jp_entry = japan_perf.get(en)
        if jp_entry and jp_entry.get("total_runs", 0) >= 3:
            runs = jp_entry["total_runs"]
            deals = jp_entry["total_deals"]
            if deals == 0 and runs >= 10:
                # Trap — push to back
                return -1.0
            deal_rate = deals / runs
            # Multiply base by (1 + deal_rate) so proven JP performers rise
            base = max(base, 1.0) * (1 + deal_rate)

        return base

    scored = [(t, _score(t)) for t in targets]
    # Stable sort: catalog-matched first (desc score), then unmatched in original order
    scored.sort(key=lambda x: x[1], reverse=True)
    return [t for t, _ in scored]


@dataclass
class JapanDealAlert:
    """Structured alert for Japan arbitrage opportunity."""
    # Item details
    title: str
    title_jp: str
    item_price_jpy: int
    item_price_usd: float
    
    # Market data
    us_market_price: float
    us_market_source: str
    
    # Cost breakdown
    total_landed_cost: float
    proxy_service: str
    shipping_method: str
    
    # Profit analysis
    gross_profit: float
    net_profit: float  # After all fees
    margin_percent: float
    roi_percent: float
    
    # Recommendation
    recommendation: str  # STRONG_BUY, BUY, WATCH, SKIP
    confidence: str  # HIGH, MEDIUM, LOW
    
    # URLs
    auction_url: str
    image_url: Optional[str]
    
    # Metadata
    category: str
    brand: str
    auction_id: str
    platform: str
    end_time: Optional[datetime]
    bids: int
    seller_rating: Optional[float]
    
    # Timestamp
    discovered_at: datetime
    
    def to_discord_embed(self) -> dict:
        """Convert to Discord embed format."""
        color_map = {
            'STRONG_BUY': 0x00FF00,  # Green
            'BUY': 0x90EE90,  # Light green
            'WATCH': 0xFFD700,  # Gold
            'SKIP': 0x808080,  # Gray
        }
        
        emoji_map = {
            'STRONG_BUY': '🚀',
            'BUY': '✅',
            'WATCH': '👀',
            'SKIP': '❌',
        }
        
        return {
            'title': f"{emoji_map.get(self.recommendation, '💎')} Japan Arbitrage: {self.brand}",
            'description': f"**{self.title}**\n*{self.title_jp}*",
            'color': color_map.get(self.recommendation, 0x808080),
            'fields': [
                {
                    'name': '💰 Profit Analysis',
                    'value': (
                        f"Net Profit: **${self.net_profit:,.0f}**\n"
                        f"Margin: **{self.margin_percent:.1f}%**\n"
                        f"ROI: **{self.roi_percent:.1f}%**"
                    ),
                    'inline': True
                },
                {
                    'name': '💵 Pricing',
                    'value': (
                        f"Japan Price: ¥{self.item_price_jpy:,} (${self.item_price_usd:,.0f})\n"
                        f"US Market: ${self.us_market_price:,.0f}\n"
                        f"Landed Cost: ${self.total_landed_cost:,.0f}"
                    ),
                    'inline': True
                },
                {
                    'name': '📦 Logistics',
                    'value': (
                        f"Proxy: {self.proxy_service}\n"
                        f"Shipping: {self.shipping_method}\n"
                        f"Category: {self.category}"
                    ),
                    'inline': True
                },
                {
                    'name': '⏰ Auction Status',
                    'value': (
                        f"Bids: {self.bids}\n"
                        f"Ends: {self.end_time.strftime('%Y-%m-%d %H:%M') if self.end_time else 'Unknown'}\n"
                        f"Confidence: {self.confidence}"
                    ),
                    'inline': True
                },
            ],
            'image': {'url': self.image_url} if self.image_url else None,
            'footer': {
                'text': f"Via {self.platform} • ID: {self.auction_id} • Discovered: {self.discovered_at.strftime('%H:%M')}"
            },
            'url': self.auction_url,
        }


class JapanArbitrageMonitor:
    """Monitor Japanese auctions for arbitrage opportunities."""
    
    # Exchange rate
    JPY_TO_USD = 0.0067
    
    # Search queries optimized for Japanese market (Yahoo Auctions, Mercari, Rakuma)
    # Japanese queries use native terms and popular search patterns in Japan
    SEARCH_TARGETS = [
        # ===== WATCHES (時計) =====
        # Rolex - most popular luxury watch in Japan
        {'jp': 'ロレックス デイトジャスト', 'en': 'rolex datejust', 'category': 'watch', 'brand': 'Rolex', 'weight': 0.3},
        {'jp': 'ロレックス サブマリーナ', 'en': 'rolex submariner', 'category': 'watch', 'brand': 'Rolex', 'weight': 0.3},
        {'jp': 'ロレックス GMT マスター', 'en': 'rolex gmt master', 'category': 'watch', 'brand': 'Rolex', 'weight': 0.3},
        {'jp': 'ロレックス エクスプローラー', 'en': 'rolex explorer', 'category': 'watch', 'brand': 'Rolex', 'weight': 0.3},
        {'jp': 'ロレックス デイデイト', 'en': 'rolex day-date', 'category': 'watch', 'brand': 'Rolex', 'weight': 0.3},
        {'jp': 'ロレックス ヨットマスター', 'en': 'rolex yacht-master', 'category': 'watch', 'brand': 'Rolex', 'weight': 0.3},
        {'jp': 'ロレックス オイスター', 'en': 'rolex oyster perpetual', 'category': 'watch', 'brand': 'Rolex', 'weight': 0.3},
        
        # Cartier - extremely popular in Japan, especially among women
        {'jp': 'カルティエ タンク', 'en': 'cartier tank', 'category': 'watch', 'brand': 'Cartier', 'weight': 0.3},
        {'jp': 'カルティエ サントス', 'en': 'cartier santos', 'category': 'watch', 'brand': 'Cartier', 'weight': 0.3},
        {'jp': 'カルティエ バロンブルー', 'en': 'cartier ballon bleu', 'category': 'watch', 'brand': 'Cartier', 'weight': 0.3},
        {'jp': 'カルティエ パンテール', 'en': 'cartier panthere', 'category': 'watch', 'brand': 'Cartier', 'weight': 0.3},
        
        # Omega - strong following in Japan
        {'jp': 'オメガ スピードマスター', 'en': 'omega speedmaster', 'category': 'watch', 'brand': 'Omega', 'weight': 0.3},
        {'jp': 'オメガ シーマスター', 'en': 'omega seamaster', 'category': 'watch', 'brand': 'Omega', 'weight': 0.3},
        {'jp': 'オメガ コンステレーション', 'en': 'omega constellation', 'category': 'watch', 'brand': 'Omega', 'weight': 0.3},
        
        # High-end watches
        {'jp': 'パテックフィリップ ノーチラス', 'en': 'patek philippe nautilus', 'category': 'watch', 'brand': 'Patek Philippe', 'weight': 0.3},
        {'jp': 'パテックフィリップ アクアノート', 'en': 'patek philippe aquanaut', 'category': 'watch', 'brand': 'Patek Philippe', 'weight': 0.3},
        {'jp': 'オーデマピゲ ロイヤルオーク', 'en': 'audemars piguet royal oak', 'category': 'watch', 'brand': 'Audemars Piguet', 'weight': 0.3},
        {'jp': 'ヴァシュロンコンスタンタン', 'en': 'vacheron constantin', 'category': 'watch', 'brand': 'Vacheron Constantin', 'weight': 0.3},
        {'jp': 'ブレゲ マリーン', 'en': 'breguet marine', 'category': 'watch', 'brand': 'Breguet', 'weight': 0.3},
        {'jp': 'ブルガリ オクト', 'en': 'bvlgari octo', 'category': 'watch', 'brand': 'Bulgari', 'weight': 0.3},
        
        # Japanese watch brands (popular domestically)
        {'jp': 'グランドセイコー', 'en': 'grand seiko', 'category': 'watch', 'brand': 'Grand Seiko', 'weight': 0.3},
        {'jp': 'セイコー プロスペックス', 'en': 'seiko prospex', 'category': 'watch', 'brand': 'Seiko', 'weight': 0.3},
        
        # ===== BAGS (バッグ) =====
        # Hermès - extremely high demand in Japan
        {'jp': 'エルメス バーキン', 'en': 'hermes birkin', 'category': 'bag', 'brand': 'Hermès', 'weight': 0.8},
        {'jp': 'エルメス ケリー', 'en': 'hermes kelly', 'category': 'bag', 'brand': 'Hermès', 'weight': 0.8},
        {'jp': 'エルメス コンスタンス', 'en': 'hermes constance', 'category': 'bag', 'brand': 'Hermès', 'weight': 0.6},
        {'jp': 'エルメス ピコタン', 'en': 'hermes picotin', 'category': 'bag', 'brand': 'Hermès', 'weight': 0.5},
        {'jp': 'エルメス エブリン', 'en': 'hermes evelyne', 'category': 'bag', 'brand': 'Hermès', 'weight': 0.5},
        {'jp': 'エルメス リンディ', 'en': 'hermes lindy', 'category': 'bag', 'brand': 'Hermès', 'weight': 0.6},
        {'jp': 'エルメス ガーデンパーティ', 'en': 'hermes garden party', 'category': 'bag', 'brand': 'Hermès', 'weight': 0.5},
        {'jp': 'エルメス ボリード', 'en': 'hermes bolide', 'category': 'bag', 'brand': 'Hermès', 'weight': 0.5},
        
        # Chanel - very popular in Japan
        {'jp': 'シャネル マトラッセ', 'en': 'chanel classic flap', 'category': 'bag', 'brand': 'Chanel', 'weight': 0.6},
        {'jp': 'シャネル ボーイシャネル', 'en': 'chanel boy bag', 'category': 'bag', 'brand': 'Chanel', 'weight': 0.6},
        {'jp': 'シャネル 19', 'en': 'chanel 19', 'category': 'bag', 'brand': 'Chanel', 'weight': 0.6},
        {'jp': 'シャネル WOC', 'en': 'chanel wallet on chain', 'category': 'bag', 'brand': 'Chanel', 'weight': 0.4},
        {'jp': 'シャネル ココハンドル', 'en': 'chanel coco handle', 'category': 'bag', 'brand': 'Chanel', 'weight': 0.5},
        {'jp': 'シャネル GST', 'en': 'chanel gst', 'category': 'bag', 'brand': 'Chanel', 'weight': 0.5},
        
        # Louis Vuitton - accessible luxury, high volume
        {'jp': 'ルイヴィトン スピーディ', 'en': 'louis vuitton speedy', 'category': 'bag', 'brand': 'Louis Vuitton', 'weight': 0.5},
        {'jp': 'ルイヴィトン ネヴァーフル', 'en': 'louis vuitton neverfull', 'category': 'bag', 'brand': 'Louis Vuitton', 'weight': 0.5},
        {'jp': 'ルイヴィトン アルマ', 'en': 'louis vuitton alma', 'category': 'bag', 'brand': 'Louis Vuitton', 'weight': 0.5},
        {'jp': 'ルイヴィトン キーポル', 'en': 'louis vuitton keepall', 'category': 'bag', 'brand': 'Louis Vuitton', 'weight': 0.6},
        {'jp': 'ルイヴィトン ポシェット', 'en': 'louis vuitton pochette', 'category': 'bag', 'brand': 'Louis Vuitton', 'weight': 0.3},
        {'jp': 'ルイヴィトン モノグラム', 'en': 'louis vuitton monogram', 'category': 'bag', 'brand': 'Louis Vuitton', 'weight': 0.5},
        
        # Other luxury bags
        {'jp': 'ゴヤール サンルイ', 'en': 'goyard saint louis', 'category': 'bag', 'brand': 'Goyard', 'weight': 0.5},
        {'jp': 'ゴヤール アンジュ', 'en': 'goyard anjou', 'category': 'bag', 'brand': 'Goyard', 'weight': 0.5},
        {'jp': 'セリーヌ ボックス', 'en': 'celine box bag', 'category': 'bag', 'brand': 'Celine', 'weight': 0.5},
        {'jp': 'セリーヌ ラゲージ', 'en': 'celine luggage', 'category': 'bag', 'brand': 'Celine', 'weight': 0.6},
        {'jp': 'セリーヌ トリオンフ', 'en': 'celine triomphe', 'category': 'bag', 'brand': 'Celine', 'weight': 0.5},
        {'jp': 'ロエベ パズル', 'en': 'loewe puzzle', 'category': 'bag', 'brand': 'Loewe', 'weight': 0.6},
        {'jp': 'ボッテガヴェネタ カセット', 'en': 'bottega veneta cassette', 'category': 'bag', 'brand': 'Bottega Veneta', 'weight': 0.5},
        {'jp': 'プラダ ナイロン', 'en': 'prada nylon bag', 'category': 'bag', 'brand': 'Prada', 'weight': 0.4},
        
        # ===== JEWELRY (ジュエリー) =====
        # Chrome Hearts - cult following in Japan
        {'jp': 'クロムハーツ リング', 'en': 'chrome hearts ring', 'category': 'jewelry', 'brand': 'Chrome Hearts', 'weight': 0.1},
        {'jp': 'クロムハーツ ネックレス', 'en': 'chrome hearts necklace', 'category': 'jewelry', 'brand': 'Chrome Hearts', 'weight': 0.1},
        {'jp': 'クロムハーツ ブレスレット', 'en': 'chrome hearts bracelet', 'category': 'jewelry', 'brand': 'Chrome Hearts', 'weight': 0.1},
        {'jp': 'クロムハーツ ペンダント', 'en': 'chrome hearts pendant', 'category': 'jewelry', 'brand': 'Chrome Hearts', 'weight': 0.1},
        {'jp': 'クロムハーツ ピアス', 'en': 'chrome hearts earrings', 'category': 'jewelry', 'brand': 'Chrome Hearts', 'weight': 0.1},
        
        # Van Cleef - extremely popular in Japan
        {'jp': 'ヴァンクリーフ アルハンブラ', 'en': 'van cleef alhambra', 'category': 'jewelry', 'brand': 'Van Cleef & Arpels', 'weight': 0.1},
        {'jp': 'ヴァンクリーフ フリヴォル', 'en': 'van cleef frivole', 'category': 'jewelry', 'brand': 'Van Cleef & Arpels', 'weight': 0.1},
        
        # Cartier jewelry
        {'jp': 'カルティエ ラブブレス', 'en': 'cartier love bracelet', 'category': 'jewelry', 'brand': 'Cartier', 'weight': 0.1},
        {'jp': 'カルティエ ラブリング', 'en': 'cartier love ring', 'category': 'jewelry', 'brand': 'Cartier', 'weight': 0.1},
        {'jp': 'カルティエ ジャストアンクル', 'en': 'cartier juste un clou', 'category': 'jewelry', 'brand': 'Cartier', 'weight': 0.1},
        {'jp': 'カルティエ トリニティ', 'en': 'cartier trinity', 'category': 'jewelry', 'brand': 'Cartier', 'weight': 0.1},
        
        # Tiffany - popular in Japan
        {'jp': 'ティファニー Tワイヤー', 'en': 'tiffany t wire', 'category': 'jewelry', 'brand': 'Tiffany', 'weight': 0.1},
        {'jp': 'ティファニー リターントゥ', 'en': 'tiffany return to', 'category': 'jewelry', 'brand': 'Tiffany', 'weight': 0.1},
        {'jp': 'ティファニー オープンハート', 'en': 'tiffany open heart', 'category': 'jewelry', 'brand': 'Tiffany', 'weight': 0.1},
        
        # Other jewelry
        {'jp': 'ブルガリ セルペンティ', 'en': 'bvlgari serpenti', 'category': 'jewelry', 'brand': 'Bulgari', 'weight': 0.1},
        {'jp': 'ブルガリ ビーゼロワン', 'en': 'bvlgari b zero1', 'category': 'jewelry', 'brand': 'Bulgari', 'weight': 0.1},
        {'jp': 'エルメス クリッククラック', 'en': 'hermes clic clac', 'category': 'jewelry', 'brand': 'Hermès', 'weight': 0.1},
        {'jp': 'エルメス ケリーブレス', 'en': 'hermes kelly bracelet', 'category': 'jewelry', 'brand': 'Hermès', 'weight': 0.1},
        {'jp': 'ショーメ リアン', 'en': 'chaumet liens', 'category': 'jewelry', 'brand': 'Chaumet', 'weight': 0.1},
        
        # ===== FASHION (ファッション) =====
        # Rick Owens - strong following in Japan
        {'jp': 'リックオウエンス ダンク', 'en': 'rick owens dunks', 'category': 'fashion', 'brand': 'Rick Owens', 'weight': 1.0},
        {'jp': 'リックオウエンス ジオバスケット', 'en': 'rick owens geobasket', 'category': 'fashion', 'brand': 'Rick Owens', 'weight': 1.0},
        {'jp': 'リックオウエンス ラモーンズ', 'en': 'rick owens ramones', 'category': 'fashion', 'brand': 'Rick Owens', 'weight': 1.0},
        {'jp': 'リックオウエンス ジャケット', 'en': 'rick owens jacket', 'category': 'fashion', 'brand': 'Rick Owens', 'weight': 1.0},
        
        # Maison Margiela
        {'jp': 'マルジェラ タビ', 'en': 'maison margiela tabi', 'category': 'fashion', 'brand': 'Maison Margiela', 'weight': 0.8},
        {'jp': 'マルジェラ レプリカ', 'en': 'maison margiela replica', 'category': 'fashion', 'brand': 'Maison Margiela', 'weight': 0.8},
        {'jp': 'マルジェラ ジャパン', 'en': 'maison margiela japan', 'category': 'fashion', 'brand': 'Maison Margiela', 'weight': 0.8},
        
        # Saint Laurent
        {'jp': 'サンローラン テディジャケット', 'en': 'saint laurent teddy', 'category': 'fashion', 'brand': 'Saint Laurent', 'weight': 0.8},
        {'jp': 'サンローラン ワイアット', 'en': 'saint laurent wyatt', 'category': 'fashion', 'brand': 'Saint Laurent', 'weight': 1.0},
        {'jp': 'サンローラン サックドジュール', 'en': 'saint laurent sac de jour', 'category': 'fashion', 'brand': 'Saint Laurent', 'weight': 0.6},
        
        # Balenciaga
        {'jp': 'バレンシアガ トリプルS', 'en': 'balenciaga triple s', 'category': 'fashion', 'brand': 'Balenciaga', 'weight': 1.2},
        {'jp': 'バレンシアガ トラック', 'en': 'balenciaga track', 'category': 'fashion', 'brand': 'Balenciaga', 'weight': 1.0},
        {'jp': 'バレンシアガ シティ', 'en': 'balenciaga city bag', 'category': 'fashion', 'brand': 'Balenciaga', 'weight': 0.6},
        
        # Gucci
        {'jp': 'グッチ エース', 'en': 'gucci ace', 'category': 'fashion', 'brand': 'Gucci', 'weight': 0.8},
        {'jp': 'グッチ ディオンシアス', 'en': 'gucci dionysus', 'category': 'fashion', 'brand': 'Gucci', 'weight': 0.6},
        {'jp': 'グッチ マーモント', 'en': 'gucci marmont', 'category': 'fashion', 'brand': 'Gucci', 'weight': 0.5},
        
        # Alexander McQueen
        {'jp': 'アレキサンダーマックイーン', 'en': 'alexander mcqueen', 'category': 'fashion', 'brand': 'Alexander McQueen', 'weight': 0.8},
        
        # ===== ARCHIVE FASHION (アーカイブファッション) =====
        # Mirrors the main pipeline's archive brand list
        # Helmut Lang
        {'jp': 'ヘルムートラング レザージャケット', 'en': 'helmut lang leather jacket', 'category': 'fashion', 'brand': 'Helmut Lang', 'weight': 1.0},
        {'jp': 'ヘルムートラング アストロバイカー', 'en': 'helmut lang astro biker', 'category': 'fashion', 'brand': 'Helmut Lang', 'weight': 1.0},
        # Raf Simons
        {'jp': 'ラフシモンズ レザージャケット', 'en': 'raf simons leather jacket', 'category': 'fashion', 'brand': 'Raf Simons', 'weight': 1.0},
        {'jp': 'ラフシモンズ ライオットボンバー', 'en': 'raf simons riot bomber', 'category': 'fashion', 'brand': 'Raf Simons', 'weight': 0.8},
        {'jp': 'ラフシモンズ コンシューム', 'en': 'raf simons consumed', 'category': 'fashion', 'brand': 'Raf Simons', 'weight': 0.8},
        # Number (N)ine
        {'jp': 'ナンバーナイン レザージャケット', 'en': 'number nine leather jacket', 'category': 'fashion', 'brand': 'Number (N)ine', 'weight': 1.0},
        {'jp': 'ナンバーナイン', 'en': 'number nine', 'category': 'fashion', 'brand': 'Number (N)ine', 'weight': 0.8},
        # Jean Paul Gaultier
        {'jp': 'ジャンポールゴルチエ メッシュ', 'en': 'jean paul gaultier mesh top', 'category': 'fashion', 'brand': 'Jean Paul Gaultier', 'weight': 0.6},
        {'jp': 'ジャンポールゴルチエ コルセット', 'en': 'jean paul gaultier corset', 'category': 'fashion', 'brand': 'Jean Paul Gaultier', 'weight': 0.6},
        # Dior Homme
        {'jp': 'ディオールオム レザージャケット', 'en': 'dior homme leather jacket', 'category': 'fashion', 'brand': 'Dior Homme', 'weight': 1.0},
        {'jp': 'ディオールオム デニム', 'en': 'dior homme jeans', 'category': 'fashion', 'brand': 'Dior Homme', 'weight': 0.8},
        # Undercover
        {'jp': 'アンダーカバー ジャケット', 'en': 'undercover jacket', 'category': 'fashion', 'brand': 'Undercover', 'weight': 0.8},
        {'jp': 'アンダーカバー アーツアンドクラフツ', 'en': 'undercover arts and crafts', 'category': 'fashion', 'brand': 'Undercover', 'weight': 0.8},
        # Yohji Yamamoto
        {'jp': 'ヨウジヤマモト コート', 'en': 'yohji yamamoto coat', 'category': 'fashion', 'brand': 'Yohji Yamamoto', 'weight': 1.0},
        {'jp': 'ヨウジヤマモト ジャケット', 'en': 'yohji yamamoto jacket', 'category': 'fashion', 'brand': 'Yohji Yamamoto', 'weight': 1.0},
        # Comme des Garcons
        {'jp': 'コムデギャルソン ジャケット', 'en': 'comme des garcons jacket', 'category': 'fashion', 'brand': 'Comme des Garcons', 'weight': 0.8},
        # Junya Watanabe
        {'jp': 'ジュンヤワタナベ コート', 'en': 'junya watanabe coat', 'category': 'fashion', 'brand': 'Junya Watanabe', 'weight': 0.8},
        # Vivienne Westwood
        {'jp': 'ヴィヴィアンウエストウッド オーブ', 'en': 'vivienne westwood orb', 'category': 'fashion', 'brand': 'Vivienne Westwood', 'weight': 0.3},
        {'jp': 'ヴィヴィアンウエストウッド アーマーリング', 'en': 'vivienne westwood armor ring', 'category': 'fashion', 'brand': 'Vivienne Westwood', 'weight': 0.1},
        {'jp': 'ヴィヴィアンウエストウッド コルセット', 'en': 'vivienne westwood corset', 'category': 'fashion', 'brand': 'Vivienne Westwood', 'weight': 0.6},
        # Ann Demeulemeester
        {'jp': 'アンドゥムルメステール ブーツ', 'en': 'ann demeulemeester boots', 'category': 'fashion', 'brand': 'Ann Demeulemeester', 'weight': 1.0},

        # Carol Christian Poell
        {'jp': 'キャロルクリスチャンポエル ブーツ', 'en': 'carol christian poell boots', 'category': 'fashion', 'brand': 'Carol Christian Poell', 'weight': 1.0},
        # Boris Bidjan Saberi
        {'jp': 'ボリスビジャンサベリ コート', 'en': 'boris bidjan saberi coat', 'category': 'fashion', 'brand': 'Boris Bidjan Saberi', 'weight': 1.0},
    ]
    
    def __init__(
        self,
        proxy_service: str = 'buyee',
        min_margin_percent: float = 25.0,
        min_profit_usd: float = 200.0,
        data_dir: str = 'data',
    ):
        self.proxy_service = proxy_service
        self.min_margin = min_margin_percent
        self.min_profit = min_profit_usd
        self.calculator = JapanCostCalculator(proxy_service)
        
        # Data storage
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.opportunities_file = self.data_dir / 'japan_opportunities.jsonl'
        self.seen_auctions: set = self._load_seen()
        
        # US market price cache
        self.price_cache: Dict[str, Tuple[float, datetime]] = {}
        self.cache_ttl = timedelta(hours=6)
    
    def _load_seen(self) -> set:
        """Load previously seen auction IDs."""
        seen = set()
        if self.opportunities_file.exists():
            with open(self.opportunities_file, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        seen.add(data.get('auction_id', ''))
                    except:
                        continue
        return seen
    
    def _save_opportunity(self, alert: JapanDealAlert):
        """Save opportunity to file."""
        with open(self.opportunities_file, 'a') as f:
            f.write(json.dumps(asdict(alert), default=str) + '\n')
    
    async def get_us_market_price(self, query: str, category: str) -> Optional[Tuple[float, str]]:
        """Get US market price from cache or estimate."""
        cache_key = f"{query}_{category}"
        
        # Check cache
        if cache_key in self.price_cache:
            price, timestamp = self.price_cache[cache_key]
            if datetime.now() - timestamp < self.cache_ttl:
                return price, 'cache'
        
        # Get estimate from blue-chip targets
        from core.blue_chip_targets import get_target_config
        
        target = get_target_config(query)
        if target:
            # Use target's max_price as rough market estimate
            # In production, this would query Grailed/eBay sold data
            estimated_price = target.max_price * 1.2  # 20% above max target price
            self.price_cache[cache_key] = (estimated_price, datetime.now())
            return estimated_price, 'estimate'
        
        # Fallback estimates by category
        fallback_prices = {
            'watch': 5000,
            'bag': 3000,
            'jewelry': 1500,
            'fashion': 600,
        }
        
        price = fallback_prices.get(category, 1000)
        self.price_cache[cache_key] = (price, datetime.now())
        return price, 'fallback'
    
    async def search_buyee_yahoo(self, target: dict) -> List[dict]:
        """Search Yahoo Auctions via Buyee using Japanese query."""
        items = []
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Use the Japanese query directly - it will be URL encoded by the client
                url = f"https://buyee.jp/item/search/query/{target['jp']}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                }
                
                response = await client.get(url, headers=headers)
                
                if response.status_code != 200:
                    logger.warning(f"Buyee returned {response.status_code} for {target['en']}")
                    return []
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Parse items using correct Buyee HTML structure
                for item_el in soup.select('.itemCard')[:20]:  # Top 20 results
                    try:
                        # Title - inside itemCard__itemName
                        title_el = item_el.select_one('.itemCard__itemName a')
                        if not title_el:
                            continue
                        title_jp = title_el.get_text(strip=True)
                        
                        # Price - inside g-price
                        price_el = item_el.select_one('.g-price')
                        if not price_el:
                            continue
                        
                        price_text = price_el.get_text()
                        price_jpy = self._parse_jpy_price(price_text)
                        
                        if not price_jpy or price_jpy < 10000:  # Skip items under ¥10,000 (~$67)
                            continue
                        
                        # Auction ID and URL
                        auction_id = ""
                        auction_url = ""
                        if title_el and title_el.get('href'):
                            href = title_el['href']
                            auction_id = href.split('/')[-1].split('?')[0]
                            auction_url = f"https://buyee.jp{href}" if not href.startswith('http') else href
                        
                        if auction_id in self.seen_auctions:
                            continue
                        
                        # Image - inside g-thumbnail__image
                        img_el = item_el.select_one('.g-thumbnail__image')
                        image_url = img_el.get('data-src') if img_el else None
                        
                        # Bids - look for bid count in itemCard__itemDetails
                        bids = 0
                        details_el = item_el.select_one('.itemCard__itemDetails')
                        if details_el:
                            # Look for text containing "bid" or Japanese bid text
                            details_text = details_el.get_text()
                            if 'bid' in details_text.lower() or '入札' in details_text:
                                bids = self._extract_number(details_text) or 0
                        
                        # Time remaining
                        end_time = None
                        time_el = item_el.select_one('.itemCard__infoItem')
                        if time_el and ('remaining' in time_el.get_text().lower() or '残り' in time_el.get_text()):
                            end_time = self._parse_end_time(time_el.get_text())
                        
                        items.append({
                            'title_jp': title_jp,
                            'title_en': target['en'],
                            'price_jpy': price_jpy,
                            'auction_id': auction_id,
                            'auction_url': auction_url,
                            'image_url': image_url,
                            'bids': bids,
                            'end_time': end_time,
                            'category': target['category'],
                            'brand': target['brand'],
                            'weight_kg': target['weight'],
                        })
                        
                    except Exception as e:
                        logger.debug(f"Error parsing item: {e}")
                        continue
                
        except Exception as e:
            logger.error(f"Error searching Buyee: {e}")
        
        return items
    
    def _parse_jpy_price(self, price_text: str) -> Optional[int]:
        """Parse JPY price from text."""
        import re
        # Remove non-numeric except comma
        cleaned = re.sub(r'[^\d,]', '', price_text)
        cleaned = cleaned.replace(',', '')
        if cleaned:
            try:
                return int(cleaned)
            except:
                pass
        return None
    
    def _extract_number(self, text: str) -> Optional[int]:
        """Extract number from text."""
        import re
        numbers = re.findall(r'\d+', text)
        if numbers:
            try:
                return int(numbers[0])
            except:
                pass
        return None
    
    def _parse_end_time(self, time_text: str) -> Optional[datetime]:
        """Parse auction end time."""
        # Buyee shows relative time like "2 days 5 hours"
        # For now, return current time + parsed duration
        import re
        
        days = 0
        hours = 0
        
        day_match = re.search(r'(\d+)\s*day', time_text)
        if day_match:
            days = int(day_match.group(1))
        
        hour_match = re.search(r'(\d+)\s*hour', time_text)
        if hour_match:
            hours = int(hour_match.group(1))
        
        if days or hours:
            return datetime.now() + timedelta(days=days, hours=hours)
        
        return None
    
    async def analyze_opportunity(self, item: dict) -> Optional[JapanDealAlert]:
        """Analyze if item is a profitable arbitrage opportunity."""
        
        # Get US market price
        us_price_result = await self.get_us_market_price(item['title_en'], item['category'])
        if not us_price_result:
            return None
        
        us_market_price, price_source = us_price_result
        
        # Calculate all-in cost
        cost = self.calculator.calculate(
            item_price_jpy=item['price_jpy'],
            category=item['category'],
            weight_kg=item['weight_kg'],
        )
        
        # Calculate profit
        gross_profit = us_market_price - cost.total_landed
        
        # Account for US selling fees (Grailed 9% + PayPal 3% + shipping $20)
        us_selling_fees = us_market_price * 0.12 + 20
        net_profit = gross_profit - us_selling_fees
        
        if cost.total_landed <= 0:
            return None
        
        margin_percent = (net_profit / cost.total_landed) * 100
        roi_percent = (net_profit / cost.total_landed) * 100
        
        # Determine recommendation
        if margin_percent >= 50 and net_profit >= self.min_profit * 2:
            recommendation = 'STRONG_BUY'
            confidence = 'HIGH'
        elif margin_percent >= self.min_margin and net_profit >= self.min_profit:
            recommendation = 'BUY'
            confidence = 'HIGH' if item['bids'] < 5 else 'MEDIUM'
        elif margin_percent >= 15 and net_profit >= 100:
            recommendation = 'WATCH'
            confidence = 'MEDIUM'
        else:
            return None  # Skip unprofitable items
        
        # Adjust confidence based on factors
        if item['bids'] > 10:
            confidence = 'MEDIUM' if confidence == 'HIGH' else 'LOW'
        
        if item['price_jpy'] > 1_000_000:  # > ~$6,700
            confidence = 'MEDIUM' if confidence == 'HIGH' else 'LOW'
        
        return JapanDealAlert(
            title=item['title_en'],
            title_jp=item['title_jp'],
            item_price_jpy=item['price_jpy'],
            item_price_usd=cost.item_price_usd,
            us_market_price=us_market_price,
            us_market_source=price_source,
            total_landed_cost=cost.total_landed,
            proxy_service=cost.proxy_service,
            shipping_method=cost.shipping_method,
            gross_profit=gross_profit,
            net_profit=net_profit,
            margin_percent=margin_percent,
            roi_percent=roi_percent,
            recommendation=recommendation,
            confidence=confidence,
            auction_url=item['auction_url'],
            image_url=item['image_url'],
            category=item['category'],
            brand=item['brand'],
            auction_id=item['auction_id'],
            platform='Buyee (Yahoo Auctions JP)',
            end_time=item['end_time'],
            bids=item['bids'],
            seller_rating=None,
            discovered_at=datetime.now(),
        )
    
    async def scan_mercari(self, target: dict) -> List[JapanDealAlert]:
        """Scan Mercari for a specific target using robust scraper with proxy fallback."""
        opportunities = []
        
        try:
            logger.debug(f"  [Mercari] Searching with JP query: {target['jp']}")
            
            # Use robust scraper (stealth + proxy + fallback)
            scraper = MercariRobustScraper(use_proxies=True)
            items = await scraper.search(
                query_jp=target['jp'],
                query_en=target['en'],
                category=target['category'],
                brand=target['brand'],
                weight_kg=target['weight'],
                max_results=15,
            )
            
            for item in items:
                # Skip if we've seen this item
                if item['item_id'] in self.seen_auctions:
                    continue
                
                # Analyze as opportunity
                opportunity = await self._analyze_mercari_robust_item(item)
                if opportunity:
                    opportunities.append(opportunity)
                    self.seen_auctions.add(item['item_id'])
                    self._save_opportunity(opportunity)
                    
                    logger.info(
                        f"  🛒 [Mercari] {opportunity.recommendation}: {opportunity.brand} "
                        f"(${opportunity.net_profit:.0f} profit, {opportunity.margin_percent:.1f}% margin)"
                    )
                    
        except Exception as e:
            logger.error(f"Error scanning Mercari for {target['en']}: {e}")
        
        return opportunities
    
    async def _analyze_mercari_item(self, item: MercariItem) -> Optional[JapanDealAlert]:
        """Analyze Mercari item for arbitrage."""
        
        # Get US market price
        us_price_result = await self.get_us_market_price(item.title_en, item.category)
        if not us_price_result:
            return None
        
        us_market_price, price_source = us_price_result
        
        # Calculate all-in cost
        cost = self.calculator.calculate(
            item_price_jpy=item.price_jpy,
            category=item.category,
            weight_kg=item.weight_kg,
        )
        
        # Calculate profit
        gross_profit = us_market_price - cost.total_landed
        
        # Account for US selling fees
        us_selling_fees = us_market_price * 0.12 + 20
        net_profit = gross_profit - us_selling_fees
        
        if cost.total_landed <= 0:
            return None
        
        margin_percent = (net_profit / cost.total_landed) * 100
        
        # Determine recommendation
        if margin_percent >= 50 and net_profit >= self.min_profit * 2:
            recommendation = 'STRONG_BUY'
            confidence = 'HIGH'
        elif margin_percent >= self.min_margin and net_profit >= self.min_profit:
            recommendation = 'BUY'
            confidence = 'HIGH' if item.likes < 10 else 'MEDIUM'
        elif margin_percent >= 15 and net_profit >= 100:
            recommendation = 'WATCH'
            confidence = 'MEDIUM'
        else:
            return None
        
        # Adjust confidence based on factors
        if item.likes > 50:
            confidence = 'MEDIUM' if confidence == 'HIGH' else 'LOW'
        
        if item.price_jpy > 1_000_000:
            confidence = 'MEDIUM' if confidence == 'HIGH' else 'LOW'
        
        return JapanDealAlert(
            title=item.title_en,
            title_jp=item.title_jp,
            item_price_jpy=item.price_jpy,
            item_price_usd=cost.item_price_usd,
            us_market_price=us_market_price,
            us_market_source=price_source,
            total_landed_cost=cost.total_landed,
            proxy_service=cost.proxy_service,
            shipping_method=cost.shipping_method,
            gross_profit=gross_profit,
            net_profit=net_profit,
            margin_percent=margin_percent,
            roi_percent=margin_percent,  # Same for fixed price
            recommendation=recommendation,
            confidence=confidence,
            auction_url=item.item_url,
            image_url=item.image_url,
            category=item.category,
            brand=item.brand,
            auction_id=item.item_id,
            platform='Buyee (Mercari JP)',
            end_time=None,  # Fixed price, no end time
            bids=item.likes,  # Use likes as proxy for interest
            seller_rating=item.seller_rating,
            discovered_at=datetime.now(),
        )
    
    async def _analyze_mercari_direct_item(self, item) -> Optional[JapanDealAlert]:
        """Analyze Mercari direct API item for arbitrage."""
        
        # Get US market price
        us_price_result = await self.get_us_market_price(item.title_en, item.category)
        if not us_price_result:
            return None
        
        us_market_price, price_source = us_price_result
        
        # Calculate all-in cost
        cost = self.calculator.calculate(
            item_price_jpy=item.price_jpy,
            category=item.category,
            weight_kg=item.weight_kg,
        )
        
        # Calculate profit
        gross_profit = us_market_price - cost.total_landed
        
        # Account for US selling fees
        us_selling_fees = us_market_price * 0.12 + 20
        net_profit = gross_profit - us_selling_fees
        
        if cost.total_landed <= 0:
            return None
        
        margin_percent = (net_profit / cost.total_landed) * 100
        
        # Determine recommendation
        if margin_percent >= 50 and net_profit >= self.min_profit * 2:
            recommendation = 'STRONG_BUY'
            confidence = 'HIGH'
        elif margin_percent >= self.min_margin and net_profit >= self.min_profit:
            recommendation = 'BUY'
            confidence = 'HIGH'
        elif margin_percent >= 15 and net_profit >= 100:
            recommendation = 'WATCH'
            confidence = 'MEDIUM'
        else:
            return None
        
        # Adjust confidence for high-value items
        if item.price_jpy > 1_000_000:
            confidence = 'MEDIUM' if confidence == 'HIGH' else 'LOW'
        
        return JapanDealAlert(
            title=item.title_en,
            title_jp=item.title_jp,
            item_price_jpy=item.price_jpy,
            item_price_usd=cost.item_price_usd,
            us_market_price=us_market_price,
            us_market_source=price_source,
            total_landed_cost=cost.total_landed,
            proxy_service=cost.proxy_service,
            shipping_method=cost.shipping_method,
            gross_profit=gross_profit,
            net_profit=net_profit,
            margin_percent=margin_percent,
            roi_percent=margin_percent,
            recommendation=recommendation,
            confidence=confidence,
            auction_url=item.item_url,
            image_url=item.image_url,
            category=item.category,
            brand=item.brand,
            auction_id=item.item_id,
            platform='Mercari JP (Direct)',
            end_time=None,
            bids=0,  # Not available in direct API
            seller_rating=None,
            discovered_at=datetime.now(),
        )
    
    async def _analyze_mercari_robust_item(self, item: dict) -> Optional[JapanDealAlert]:
        """Analyze Mercari item from robust scraper."""
        
        # Get US market price
        us_price_result = await self.get_us_market_price(item['title_en'], item['category'])
        if not us_price_result:
            return None
        
        us_market_price, price_source = us_price_result
        
        # Calculate all-in cost
        cost = self.calculator.calculate(
            item_price_jpy=item['price_jpy'],
            category=item['category'],
            weight_kg=item['weight_kg'],
        )
        
        # Calculate profit
        gross_profit = us_market_price - cost.total_landed
        
        # Account for US selling fees
        us_selling_fees = us_market_price * 0.12 + 20
        net_profit = gross_profit - us_selling_fees
        
        if cost.total_landed <= 0:
            return None
        
        margin_percent = (net_profit / cost.total_landed) * 100
        
        # Determine recommendation
        if margin_percent >= 50 and net_profit >= self.min_profit * 2:
            recommendation = 'STRONG_BUY'
            confidence = 'HIGH'
        elif margin_percent >= self.min_margin and net_profit >= self.min_profit:
            recommendation = 'BUY'
            confidence = 'HIGH'
        elif margin_percent >= 15 and net_profit >= 100:
            recommendation = 'WATCH'
            confidence = 'MEDIUM'
        else:
            return None
        
        # Adjust confidence for high-value items
        if item['price_jpy'] > 1_000_000:
            confidence = 'MEDIUM' if confidence == 'HIGH' else 'LOW'
        
        # Determine platform label
        platform = 'Mercari JP'
        if item.get('platform') == 'mercari_stealth':
            platform = 'Mercari JP (Stealth)'
        elif item.get('platform') == 'mercari_direct':
            platform = 'Mercari JP (Direct)'
        
        return JapanDealAlert(
            title=item['title_en'],
            title_jp=item['title_jp'],
            item_price_jpy=item['price_jpy'],
            item_price_usd=cost.item_price_usd,
            us_market_price=us_market_price,
            us_market_source=price_source,
            total_landed_cost=cost.total_landed,
            proxy_service=cost.proxy_service,
            shipping_method=cost.shipping_method,
            gross_profit=gross_profit,
            net_profit=net_profit,
            margin_percent=margin_percent,
            roi_percent=margin_percent,
            recommendation=recommendation,
            confidence=confidence,
            auction_url=item['item_url'],
            image_url=item.get('image_url'),
            category=item['category'],
            brand=item['brand'],
            auction_id=item['item_id'],
            platform=platform,
            end_time=None,
            bids=0,
            seller_rating=None,
            discovered_at=datetime.now(),
        )
    
    async def scan_rakuma(self, target: dict) -> List[JapanDealAlert]:
        """Scan Rakuten Rakuma for a specific target using Japanese query."""
        opportunities = []
        
        try:
            logger.debug(f"  [Rakuma] Searching with JP query: {target['jp']}")
            async with RakumaJapanScraper() as scraper:
                items = await scraper.search(
                    query_jp=target['jp'],
                    query_en=target['en'],
                    category=target['category'],
                    brand=target['brand'],
                    weight_kg=target['weight'],
                    max_results=15,
                )
                
                for item in items:
                    # Skip if we've seen this item
                    if item.item_id in self.seen_auctions:
                        continue
                    
                    # Analyze as opportunity
                    opportunity = await self._analyze_rakuma_item(item)
                    if opportunity:
                        opportunities.append(opportunity)
                        self.seen_auctions.add(item.item_id)
                        self._save_opportunity(opportunity)
                        
                        logger.info(
                            f"  👜 [Rakuma] {opportunity.recommendation}: {opportunity.brand} "
                            f"(${opportunity.net_profit:.0f} profit, {opportunity.margin_percent:.1f}% margin)"
                        )
                        
        except Exception as e:
            logger.error(f"Error scanning Rakuma for {target['en']}: {e}")
        
        return opportunities
    
    async def _analyze_rakuma_item(self, item: RakumaItem) -> Optional[JapanDealAlert]:
        """Analyze Rakuma item for arbitrage."""
        
        # Get US market price
        us_price_result = await self.get_us_market_price(item.title_en, item.category)
        if not us_price_result:
            return None
        
        us_market_price, price_source = us_price_result
        
        # Calculate all-in cost
        cost = self.calculator.calculate(
            item_price_jpy=item.price_jpy,
            category=item.category,
            weight_kg=item.weight_kg,
        )
        
        # Calculate profit
        gross_profit = us_market_price - cost.total_landed
        
        # Account for US selling fees
        us_selling_fees = us_market_price * 0.12 + 20
        net_profit = gross_profit - us_selling_fees
        
        if cost.total_landed <= 0:
            return None
        
        margin_percent = (net_profit / cost.total_landed) * 100
        
        # Determine recommendation
        # Rakuma: comments indicate engagement, likes indicate interest
        engagement_score = item.likes + (item.comments * 2)  # Comments weighted higher
        
        if margin_percent >= 50 and net_profit >= self.min_profit * 2:
            recommendation = 'STRONG_BUY'
            confidence = 'HIGH'
        elif margin_percent >= self.min_margin and net_profit >= self.min_profit:
            recommendation = 'BUY'
            confidence = 'HIGH' if engagement_score < 10 else 'MEDIUM'
        elif margin_percent >= 15 and net_profit >= 100:
            recommendation = 'WATCH'
            confidence = 'MEDIUM'
        else:
            return None
        
        # Adjust confidence based on factors
        if engagement_score > 50:
            confidence = 'MEDIUM' if confidence == 'HIGH' else 'LOW'
        
        if item.price_jpy > 1_000_000:
            confidence = 'MEDIUM' if confidence == 'HIGH' else 'LOW'
        
        return JapanDealAlert(
            title=item.title_en,
            title_jp=item.title_jp,
            item_price_jpy=item.price_jpy,
            item_price_usd=cost.item_price_usd,
            us_market_price=us_market_price,
            us_market_source=price_source,
            total_landed_cost=cost.total_landed,
            proxy_service=cost.proxy_service,
            shipping_method=cost.shipping_method,
            gross_profit=gross_profit,
            net_profit=net_profit,
            margin_percent=margin_percent,
            roi_percent=margin_percent,
            recommendation=recommendation,
            confidence=confidence,
            auction_url=item.item_url,
            image_url=item.image_url,
            category=item.category,
            brand=item.brand,
            auction_id=item.item_id,
            platform='Buyee (Rakuma JP)',
            end_time=None,
            bids=item.likes,
            seller_rating=item.seller_rating,
            discovered_at=datetime.now(),
        )
    
    async def search_yahoo_direct(self, target: dict) -> List[dict]:
        """Search Yahoo Auctions Japan directly (bypassing Buyee)."""
        items = []
        try:
            async with YahooAuctionsScraper(use_proxies=True) as scraper:
                yahoo_items = await scraper.search(
                    query_jp=target['jp'],
                    query_en=target['en'],
                    category=target['category'],
                    brand=target['brand'],
                    weight_kg=target['weight'],
                    max_results=20,
                )
                
                for item in yahoo_items:
                    if item.auction_id in self.seen_auctions:
                        continue

                    # Skip auction-only listings — price is unpredictable
                    if not item.is_buy_now:
                        logger.debug(f"  [Yahoo] Skipping auction-only: {item.title_jp[:40]} (¥{item.price_jpy:,}, {item.bids} bids)")
                        continue

                    items.append({
                        'title_jp': item.title_jp,
                        'title_en': item.title,
                        'price_jpy': item.price_jpy,
                        'auction_id': item.auction_id,
                        'auction_url': item.auction_url,
                        'image_url': item.image_url,
                        'bids': item.bids,
                        'end_time': item.end_time,
                        'category': item.category,
                        'brand': item.brand,
                        'weight_kg': item.weight_kg,
                    })
                    
        except Exception as e:
            logger.error(f"Direct Yahoo search failed: {e}")
        
        return items

    async def scan_for_opportunities(self, include_mercari: bool = True, include_rakuma: bool = False) -> List[JapanDealAlert]:
        """Scan all targets for arbitrage opportunities."""
        all_opportunities = []

        # Disable Rakuma on macOS due to browser crashes
        import platform
        if include_rakuma and platform.system() == "Darwin":
            logger.warning("Rakuma scanning disabled on macOS due to browser stability issues")
            include_rakuma = False

        # Prioritize targets using golden catalog + Japan telemetry
        ordered_targets = prioritize_japan_targets(self.SEARCH_TARGETS)

        logger.info(f"Starting Japan arbitrage scan with {len(ordered_targets)} targets")
        logger.info(f"Platforms: Yahoo Auctions" + (", Mercari" if include_mercari else "") + (", Rakuma" if include_rakuma else ""))

        for target in ordered_targets:
            logger.info(f"Scanning: {target['en']} (JP: {target['jp']})")
            
            items = []
            
            # Try 1: Direct Yahoo Auctions (bypasses Buyee)
            try:
                items = await self.search_yahoo_direct(target)
                if items:
                    logger.info(f"  [Yahoo Direct] Found {len(items)} items")
            except Exception as e:
                logger.debug(f"Direct Yahoo failed: {e}")
            
            # Try 2: Buyee fallback (if direct fails)
            if not items:
                try:
                    items = await self.search_buyee_yahoo(target)
                    if items:
                        logger.info(f"  [Buyee] Found {len(items)} items")
                except Exception as e:
                    logger.debug(f"Buyee failed: {e}")
            
            # Process found items (Yahoo)
            yahoo_deals = 0
            yahoo_best_margin = 0.0
            for item in items:
                try:
                    opportunity = await self.analyze_opportunity(item)

                    if opportunity:
                        all_opportunities.append(opportunity)
                        self.seen_auctions.add(item['auction_id'])
                        self._save_opportunity(opportunity)
                        yahoo_deals += 1
                        yahoo_best_margin = max(yahoo_best_margin, opportunity.margin_percent)

                        logger.info(
                            f"  🎯 [Yahoo] {opportunity.recommendation}: {opportunity.brand} "
                            f"(${opportunity.net_profit:.0f} profit, {opportunity.margin_percent:.1f}% margin)"
                        )
                except Exception as e:
                    logger.debug(f"Error analyzing opportunity: {e}")
                    continue

                # Rate limiting
                await asyncio.sleep(2)

            # Log Yahoo telemetry
            log_japan_query_performance(
                en_query=target['en'],
                platform='yahoo',
                items_found=len(items),
                deals_found=yahoo_deals,
                best_margin=yahoo_best_margin,
            )

            # Scan Mercari if enabled
            if include_mercari:
                mercari_opps = []
                try:
                    mercari_opps = await self.scan_mercari(target)
                    all_opportunities.extend(mercari_opps)
                    await asyncio.sleep(1.5)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error scanning Mercari {target['en']}: {e}")

                mercari_best = max((o.margin_percent for o in mercari_opps), default=0.0)
                log_japan_query_performance(
                    en_query=target['en'],
                    platform='mercari',
                    items_found=len(mercari_opps),  # Mercari returns pre-filtered
                    deals_found=len(mercari_opps),
                    best_margin=mercari_best,
                )

            # Scan Rakuma if enabled
            if include_rakuma:
                rakuma_opps = []
                try:
                    rakuma_opps = await self.scan_rakuma(target)
                    all_opportunities.extend(rakuma_opps)
                    await asyncio.sleep(1.5)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error scanning Rakuma {target['en']}: {e}")

                rakuma_best = max((o.margin_percent for o in rakuma_opps), default=0.0)
                log_japan_query_performance(
                    en_query=target['en'],
                    platform='rakuma',
                    items_found=len(rakuma_opps),
                    deals_found=len(rakuma_opps),
                    best_margin=rakuma_best,
                )
        
        logger.info(f"Scan complete. Found {len(all_opportunities)} opportunities.")
        return all_opportunities


# Convenience function for integration
async def find_japan_arbitrage_deals(
    min_margin: float = 25.0,
    min_profit: float = 200.0,
    include_mercari: bool = True,
    include_rakuma: bool = False,  # Disabled: Rakuma browser crashes on macOS
) -> List[JapanDealAlert]:
    """Find Japan arbitrage deals for integration with main system."""
    monitor = JapanArbitrageMonitor(
        min_margin_percent=min_margin,
        min_profit_usd=min_profit,
    )
    return await monitor.scan_for_opportunities(
        include_mercari=include_mercari,
        include_rakuma=include_rakuma,
    )


if __name__ == "__main__":
    # Test the module
    async def test():
        monitor = JapanArbitrageMonitor()
        opportunities = await monitor.scan_for_opportunities()
        
        print(f"\n{'='*60}")
        print(f"Found {len(opportunities)} Japan arbitrage opportunities")
        print(f"{'='*60}\n")
        
        for opp in opportunities[:5]:  # Show top 5
            print(f"{opp.recommendation}: {opp.brand} - {opp.title}")
            print(f"  Japan: ¥{opp.item_price_jpy:,} → US: ${opp.us_market_price:,.0f}")
            print(f"  Landed: ${opp.total_landed_cost:,.0f} | Profit: ${opp.net_profit:,.0f} ({opp.margin_percent:.1f}%)")
            print(f"  URL: {opp.auction_url}")
            print()
    
    asyncio.run(test())

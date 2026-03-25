"""
Japanese Query Translation & Normalization

Translates English TrendEngine queries into Japanese for Yahoo Auctions JP,
Mercari JP, and Rakuma scrapers.  Also normalizes Japanese strings before
they hit the scraper URL-encode step.

Architecture:
    1. BRAND_TRANSLATIONS  — English brand prefix → (katakana, display, category, weight)
    2. PRODUCT_TRANSLATIONS — English product terms → Japanese equivalents
    3. translate_query()    — full EN→JP translation
    4. normalize_jp_query() — Unicode normalization, width, spacing
    5. build_japan_targets() — batch converter for TrendEngine output
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Optional

logger = logging.getLogger("jp_query_translator")

# ═══════════════════════════════════════════════════════════════════════════════
# BRAND TRANSLATIONS
# (english_prefix → katakana, display_name, default_category, default_weight_kg)
# Sorted longest-first at module init for greedy matching.
# ═══════════════════════════════════════════════════════════════════════════════

BRAND_TRANSLATIONS: dict[str, tuple[str, str, str, float]] = {
    # Archive fashion
    "rick owens":               ("リックオウエンス", "Rick Owens", "fashion", 1.0),
    "maison margiela":          ("マルジェラ", "Maison Margiela", "fashion", 0.8),
    "margiela":                 ("マルジェラ", "Maison Margiela", "fashion", 0.8),
    "saint laurent":            ("サンローラン", "Saint Laurent", "fashion", 0.8),
    "balenciaga":               ("バレンシアガ", "Balenciaga", "fashion", 1.0),
    "gucci":                    ("グッチ", "Gucci", "fashion", 0.6),
    "alexander mcqueen":        ("アレキサンダーマックイーン", "Alexander McQueen", "fashion", 0.8),
    "helmut lang":              ("ヘルムートラング", "Helmut Lang", "fashion", 1.0),
    "raf simons":               ("ラフシモンズ", "Raf Simons", "fashion", 0.8),
    "number nine":              ("ナンバーナイン", "Number (N)ine", "fashion", 0.8),
    "jean paul gaultier":       ("ジャンポールゴルチエ", "Jean Paul Gaultier", "fashion", 0.6),
    "dior homme":               ("ディオールオム", "Dior Homme", "fashion", 0.8),
    "dior":                     ("ディオール", "Dior", "fashion", 0.8),
    "undercover":               ("アンダーカバー", "Undercover", "fashion", 0.8),
    "comme des garcons":        ("コムデギャルソン", "Comme des Garcons", "fashion", 0.8),
    "vivienne westwood":        ("ヴィヴィアンウエストウッド", "Vivienne Westwood", "fashion", 0.3),
    "ann demeulemeester":       ("アンドゥムルメステール", "Ann Demeulemeester", "fashion", 1.0),
    "carol christian poell":    ("キャロルクリスチャンポエル", "Carol Christian Poell", "fashion", 1.0),
    "boris bidjan saberi":      ("ボリスビジャンサベリ", "Boris Bidjan Saberi", "fashion", 1.0),
    "prada":                    ("プラダ", "Prada", "fashion", 0.8),
    "bottega veneta":           ("ボッテガヴェネタ", "Bottega Veneta", "fashion", 0.8),
    "louis vuitton":            ("ルイヴィトン", "Louis Vuitton", "fashion", 0.6),
    "chanel":                   ("シャネル", "Chanel", "fashion", 0.5),
    "celine":                   ("セリーヌ", "Celine", "fashion", 0.8),
    "haider ackermann":         ("ハイダーアッカーマン", "Haider Ackermann", "fashion", 0.8),
    "dries van noten":          ("ドリスヴァンノッテン", "Dries Van Noten", "fashion", 0.8),
    "sacai":                    ("サカイ", "Sacai", "fashion", 0.8),
    "julius":                   ("ユリウス", "Julius", "fashion", 0.8),
    "kapital":                  ("キャピタル", "Kapital", "fashion", 0.8),
"hysteric glamour":         ("ヒステリックグラマー", "Hysteric Glamour", "fashion", 0.6),
    "thierry mugler":           ("ティエリーミュグレー", "Thierry Mugler", "fashion", 0.8),
    "guidi":                    ("グイディ", "Guidi", "fashion", 1.0),
    "lemaire":                  ("ルメール", "Lemaire", "fashion", 0.8),
    "acne studios":             ("アクネストゥディオズ", "Acne Studios", "fashion", 0.8),
    "simone rocha":             ("シモーネロシャ", "Simone Rocha", "fashion", 0.6),
    "brunello cucinelli":       ("ブルネロクチネリ", "Brunello Cucinelli", "fashion", 0.8),
    "soloist":                  ("ソロイスト", "The Soloist", "fashion", 0.8),
    "takahiromiyashita":        ("タカヒロミヤシタ", "Takahiromiyashita", "fashion", 0.8),
    "mihara yasuhiro":          ("ミハラヤスヒロ", "Mihara Yasuhiro", "fashion", 0.8),
    "enfants riches deprimes":  ("アンファンリッシュドゥプリメ", "Enfants Riches Deprimes", "fashion", 0.6),
    "stone island":             ("ストーンアイランド", "Stone Island", "fashion", 0.8),
    "kiko kostadinov":          ("キココスタディノフ", "Kiko Kostadinov", "fashion", 0.8),
    "a-cold-wall":              ("アコールドウォール", "A-Cold-Wall", "fashion", 0.8),
    "craig green":              ("クレイググリーン", "Craig Green", "fashion", 0.8),
    "needles":                  ("ニードルズ", "Needles", "fashion", 0.6),
    "walter van beirendonck":   ("ウォルターヴァンベイレンドンク", "Walter Van Beirendonck", "fashion", 0.8),
    "jean colonna":             ("ジャンコロナ", "Jean Colonna", "fashion", 0.8),
    # Jewelry brands
    "chrome hearts":            ("クロムハーツ", "Chrome Hearts", "jewelry", 0.1),
}

# ═══════════════════════════════════════════════════════════════════════════════
# PRODUCT TERM TRANSLATIONS
# English product/model terms → Japanese equivalents.
# Sorted longest-first at module init for greedy matching.
# ═══════════════════════════════════════════════════════════════════════════════

PRODUCT_TRANSLATIONS: dict[str, str] = {
    # ── Garment types ─────────────────────────────────────────────────────────
    "leather jacket":       "レザージャケット",
    "denim jacket":         "デニムジャケット",
    "bomber jacket":        "ボンバージャケット",
    "varsity jacket":       "バーシティジャケット",
    "teddy jacket":         "テディジャケット",
    "trucker jacket":       "トラッカージャケット",
    "biker jacket":         "バイカージャケット",
    "nylon jacket":         "ナイロンジャケット",
    "archive jacket":       "アーカイブジャケット",
    "flak jacket":          "フラックジャケット",
    "jacket":               "ジャケット",
    "bomber":               "ボンバー",
    "blazer":               "ブレイザー",
    "coat":                 "コート",
    "parka":                "パーカー",
    "fishtail parka":       "フィッシュテールパーカー",
    "hoodie":               "フーディー",
    "zip up hoodie":        "ジップアップフーディー",
    "sweater":              "セーター",
    "knit":                 "ニット",
    "knit sweater":         "ニットセーター",
    "cashmere sweater":     "カシミアセーター",
    "cashmere jacket":      "カシミアジャケット",
    "tee":                  "Tシャツ",
    "long sleeve":          "ロングスリーブ",
    "shirt":                "シャツ",
    "flannel":              "フランネル",
    "tank":                 "タンク",
    "thermal":              "サーマル",
    "mesh top":             "メッシュトップ",
    "top":                  "トップ",
    "corset":               "コルセット",
    "dress":                "ドレス",
    "cargo pants":          "カーゴパンツ",
    "track pants":          "トラックパンツ",
    "bondage pants":        "ボンデージパンツ",
    "sweatpants":           "スウェットパンツ",
    "pants":                "パンツ",
    "jeans":                "ジーンズ",
    "denim":                "デニム",
    "shorts":               "ショーツ",
    # ── Footwear ──────────────────────────────────────────────────────────────
    "leather boots":        "レザーブーツ",
    "chelsea boots":        "チェルシーブーツ",
    "chain boots":          "チェーンブーツ",
    "lace up boots":        "レースアップブーツ",
    "tractor boots":        "トラクターブーツ",
    "western boots":        "ウエスタンブーツ",
    "back zip boots":       "バックジップブーツ",
    "wyatt boots":          "ワイアットブーツ",
    "puddle boots":         "パドルブーツ",
    "tire boots":           "タイヤブーツ",
    "monolith boots":       "モノリスブーツ",
    "kiss boots":           "キスブーツ",
    "haddock leather boots": "ハドックレザーブーツ",
    "virgil boots":         "ヴァージルブーツ",
    "boots":                "ブーツ",
    "sneakers":             "スニーカー",
    "loafers":              "ローファー",
    "derby shoes":          "ダービーシューズ",
    "shoes":                "シューズ",
    "heels":                "ヒール",
    "espadrilles":          "エスパドリーユ",
    "slingbacks":           "スリングバック",
    # ── Specific models / product names ───────────────────────────────────────
    "dunks":                "ダンク",
    "geobasket":            "ジオバスケット",
    "ramones":              "ラモーンズ",
    "tabi boots":           "タビブーツ",
    "tabi loafers":         "タビローファー",
    "tabi":                 "タビ",
    "replica sneakers":     "レプリカスニーカー",
    "replica":              "レプリカ",
    "gat low":              "GATロー",
    "gat":                  "GAT",
    "wyatt":                "ワイアット",
    "triple s":             "トリプルS",
    "track sneakers":       "トラックスニーカー",
    "track":                "トラック",
    "speed trainer":        "スピードトレーナー",
    "runner":               "ランナー",
    "ace sneakers":         "エーススニーカー",
    "ace":                  "エース",
    "dionysus":             "ディオニソス",
    "marmont":              "マーモント",
    "sac de jour":          "サックドジュール",
    "orbit sneaker":        "オービットスニーカー",
    "horsebit loafers":     "ホースビットローファー",
    "rhyton sneakers":      "リートンスニーカー",
    "monolith":             "モノリス",
    "america's cup sneakers": "アメリカズカップスニーカー",
    "america's cup":        "アメリカズカップ",
    "americas cup":         "アメリカズカップ",
    "trainer":              "トレーナー",
    "astro biker":          "アストロバイカー",
    "riot bomber":          "ライオットボンバー",
    "consumed hoodie":      "コンシュームフーディー",
    "consumed":             "コンシューム",
    "tape bomber":          "テープボンバー",
    "sterling ruby":        "スターリングルビー",
    "b23 sneakers":         "B23スニーカー",
    "b23":                  "B23",
    "oblique jacket":       "オブリークジャケット",
    "oblique":              "オブリーク",
    "arts and crafts":      "アーツアンドクラフツ",
    "orb necklace":         "オーブネックレス",
    "orb":                  "オーブ",
    "armor ring":           "アーマーリング",
    "gas mask hoodie":      "ガスマスクフーディー",
    "fbt":                  "FBT",
    "drkshdw":              "DRKSHDW",
    "stooges leather jacket": "ストゥージーズレザージャケット",
    "stooges":              "ストゥージーズ",
    "creatch cargo":        "クリーチカーゴ",
    "memphis":              "メンフィス",
    "island dunk":          "アイランドダンク",
    "level tee":            "レベルTシャツ",
    "intarsia":             "インターシャ",
    "dustulator":           "ダスチュレーター",
    "bauhaus":              "バウハウス",
    "fogachine":            "フォガシーン",
    "tecuatl":              "テクアトル",
    "painter jeans":        "ペインタージーンズ",
    "bondage strap":        "ボンデージストラップ",
    "reflective":           "リフレクティブ",
    "raw denim":            "ローデニム",
    "paint splatter":       "ペイントスプラッター",
    "deconstructed blazer": "デコンストラクテッドブレイザー",
    "deconstructed jacket": "デコンストラクテッドジャケット",
    "deconstructed":        "デコンストラクテッド",
    "numbers tee":          "ナンバーズTシャツ",
    "glam slam":            "グラムスラム",
    "artisanal jacket":     "アルチザナルジャケット",
    "artisanal":            "アルチザナル",
    "duvet coat":           "デュベコート",
    "white label jacket":   "ホワイトレーベルジャケット",
    "skull cashmere":       "スカルカシミア",
    "kurt cobain":          "カートコバーン",
    "heart skull":          "ハートスカル",
    "skull scarf":          "スカルスカーフ",
    "skull ring":           "スカルリング",
    "skull":                "スカル",
    "bumster":              "バムスター",
    "butterfly jacket":     "バタフライジャケット",
    "boro jacket":          "ボロジャケット",
    "boro":                 "ボロ",
    "kountry coat":         "カントリーコート",
    "kountry denim":        "カントリーデニム",
    "kountry":              "カントリー",
    "century denim":        "センチュリーデニム",
    "pearl necklace":       "パールネックレス",
    "pearl":                "パール",
    "embellished":          "エンベリッシュド",
    "velocite jacket":      "ベロサイトジャケット",
    "shearling":            "シアリング",
    "twisted shirt":        "ツイステッドシャツ",
    "triomphe belt":        "トリオンフベルト",
    "murakami":             "ムラカミ",
    "tattoo":               "タトゥー",
    "tattoo top":           "タトゥートップ",
    "cyberbaba":            "サイバーババ",
    "maille":               "マイユ",
    "sailor":               "セーラー",
    "femme":                "ファム",
    "sheer":                "シアー",
    "navigate bomber":      "ナビゲートボンバー",
    "navigate":             "ナビゲート",
    "waxed jeans":          "ワックスジーンズ",
    "luster denim":         "ラスターデニム",
    "85 bomber":            "85ボンバー",
    "bug denim":            "バグデニム",
    "scab":                 "スカブ",
    "but beautiful":        "バットビューティフル",
    "twin peaks":           "ツインピークス",
    "bones":                "ボーンズ",
    "witch cell division":  "ウィッチセルディビジョン",
    "speedhunters":         "スピードハンターズ",
    "political campaign":   "ポリティカルキャンペーン",
    "destroyed hoodie":     "デストロイドフーディー",
    "leather biker":        "レザーバイカー",
    "arena high top":       "アリーナハイトップ",
    "arena":                "アリーナ",
    "oversized denim":      "オーバーサイズデニム",
    "campaign hoodie":      "キャンペーンフーディー",
    "skater sweatpants":    "スケータースウェットパンツ",
    "paris sneaker":        "パリスニーカー",
    "demna archive":        "デムナアーカイブ",
    "hummer boots":         "ハマーブーツ",
    "lost tape flared":     "ロストテープフレアード",
    # Raf Simons specific
    "virginia creeper":     "ヴァージニアクリーパー",
    "virginia creepers":    "ヴァージニアクリーパー",
    "power corruption lies": "パワーコラプションライズ",
    "peter saville":        "ピーターサヴィル",
    "riot riot riot":       "ライオットライオットライオット",
    "nebraska":             "ネブラスカ",
    "kollaps":              "コラプス",
    "ozweego":              "オズウィーゴ",
    "response trail":       "レスポンストレイル",
    "detroit runner":       "デトロイトランナー",
    # Guidi model numbers (keep as-is — JP users search with numbers)
    "988":                  "988",
    "995":                  "995",
    "986":                  "986",
    "drip rubber":          "ドリップラバー",
    "horse leather":        "ホースレザー",
    # Jewelry terms
    "cross pendant":        "クロスペンダント",
    "baby fat pendant":     "ベイビーファットペンダント",
    "baby fat":             "ベイビーファット",
    "babyfat":              "ベイビーファット",
    "dagger pendant":       "ダガーペンダント",
    "dagger":               "ダガー",
    "floral cross":         "フローラルクロス",
    "cross ring":           "クロスリング",
    "fuck you ring":        "ファックユーリング",
    "spinner ring":         "スピナーリング",
    "keeper ring":          "キーパーリング",
    "horseshoe ring":       "ホースシューリング",
    "morning star bracelet": "モーニングスターブレスレット",
    "paper chain":          "ペーパーチェーン",
    "paperchain":           "ペーパーチェーン",
    "forever ring":         "フォーエバーリング",
    "scroll ring":          "スクロールリング",
    "tiny e":               "タイニーE",
    "tiny ring":            "タイニーリング",
    "plus ring":            "プラスリング",
    "ch cross":             "CHクロス",
    "mini cross":           "ミニクロス",
    "star ring":            "スターリング",
    "love ring":            "ラブリング",
    "nail ring":            "ネイルリング",
    "double floral":        "ダブルフローラル",
    "maltese cross":        "マルタクロス",
    "cemetery cross":       "セメタリークロス",
    "cemetery":             "セメタリー",
    "cross patch jeans":    "クロスパッチジーンズ",
    "cross patch flannel":  "クロスパッチフランネル",
    "cross patch hat":      "クロスパッチハット",
    "deadly doll tank":     "デッドリードールタンク",
    "deadly doll":          "デッドリードール",
    "matty boy hoodie":     "マッティーボーイフーディー",
    "matty boy tee":        "マッティーボーイTシャツ",
    "matty boy":            "マッティーボーイ",
    "leather cross patch":  "レザークロスパッチ",
    "baby rib tank":        "ベイビーリブタンク",
    "neck logo long":       "ネックロゴロング",
    "pony hair triple":     "ポニーヘアトリプル",
    "paper jam triple":     "ペーパージャムトリプル",
    "gittin any frame":     "ギッティンエニーフレーム",
    "glitter friends family": "グリッターフレンズファミリー",
    "vagilante glasses":    "ヴィジランテメガネ",
    "sunglasses":           "サングラス",
    "trypoleagain glasses": "トリポレアゲインメガネ",
    "see you tea":          "シーユーティー",
    "cross":                "クロス",
    "ring":                 "リング",
    "necklace":             "ネックレス",
    "bracelet":             "ブレスレット",
    "pendant":              "ペンダント",
    "earrings":             "ピアス",
    "belt":                 "ベルト",
    "hat":                  "ハット",
    "diamond":              "ダイヤモンド",
    "glasses":              "メガネ",
    "bag":                  "バッグ",
    "scarf":                "スカーフ",
    "leather":              "レザー",
    "velvet blazer":        "ベルベットブレイザー",
    "velvet":               "ベルベット",
    "silk bomber":          "シルクボンバー",
    "re-nylon":             "リナイロン",
    "nylon":                "ナイロン",
    "cotton velvet blouson": "コットンベルベットブルゾン",
    "chocolate loafers":    "チョコレートローファー",
    "leather loafers":      "レザーローファー",
    "embroidered jacket":   "エンブロイダードジャケット",
    "floral jacket":        "フローラルジャケット",
    "printed jacket":       "プリントジャケット",
    "future":               "フューチャー",
    "archive":              "アーカイブ",
    "vintage":              "ヴィンテージ",
    # Season codes / years (keep as-is — JP users search "ラフシモンズ 2002")
    "1998":                 "1998",
    "1999":                 "1999",
    "2001":                 "2001",
    "2002":                 "2002",
    "fw03":                 "FW03",
    "fw03 leather":         "FW03レザー",
    "fw07":                 "FW07",
    "jewelry hedi slimane":  "ジュエリー エディスリマン",
    "hedi slimane":         "エディスリマン",
    "kris van assche":      "クリスヴァンアッシュ",
    "paris oil":            "パリ オイル",
    "paris ribbed long":    "パリ リブドロング",
    "champion":             "チャンピオン",
    "jumbo lace":           "ジャンボレース",
    "grained leather sneakers": "グレインレザースニーカー",
    "cargo":                "カーゴ",
    # ── Chrome Hearts piece-specific ────────────────────────────────────────
    "baby fat cross":       "ベビーファットクロス",
    "tiny e":               "タイニーE",
    "floral cross pendant": "フローラルクロスペンダント",
    "nail cross":           "ネイルクロス",
    "filigree cross":       "フィリグリークロス",
    "forever ring":         "フォーエバーリング",
    "spacer ring":          "スペーサーリング",
    "scroll band ring":     "スクロールバンドリング",
    "keeper ring":          "キーパーリング",
    "cemetery ring":        "セメタリーリング",
    "roller cross bracelet":"ローラークロスブレスレット",
    "plus bracelet":        "プラスブレスレット",
    "fancy link bracelet":  "ファンシーリンクブレスレット",
    "fancy chain necklace": "ファンシーチェーンネックレス",
    "ball chain necklace":  "ボールチェーンネックレス",
    "ne chain necklace":    "NEチェーンネックレス",
    "plus stud earring":    "プラススタッドイヤリング",
    "cross stud earring":   "クロススタッドイヤリング",
    "hoop earring":         "フープイヤリング",
    "horseshoe tee":        "ホースシューTシャツ",
    "scroll tee":           "スクロールTシャツ",
    "cross patch hoodie":   "クロスパッチフーディー",
    "cemetery hoodie":      "セメタリーフーディー",
    "fleur knee jeans":     "フルールニージーンズ",
    "penetranus":           "ペネトラナス",
    "bone prone":           "ボーンプローン",
    "pony hair trucker":    "ポニーヘアトラッカー",
    "rolling stones":       "ローリングストーンズ",
    "sex records":          "セックスレコーズ",
    # ── ERD piece-specific ───────────────────────────────────────────────────
    "classic logo hoodie":      "クラシックロゴフーディー",
    "classic logo tee":         "クラシックロゴTシャツ",
    "classic logo long sleeve": "クラシックロゴロングスリーブ",
    "safety pin earring":       "セーフティピンイヤリング",
    "bennys video":             "ベニーズビデオ",
    "menendez":                 "メネンデス",
    "viper room":               "バイパールーム",
    "teenage snuff":            "ティーンエイジスナッフ",
    "flowers of anger":         "フラワーズオブアンガー",
    "god with revolver":        "ゴッドウィズリボルバー",
    "spanish elegy":            "スパニッシュエレジー",
    "rose buckle belt":         "ローズバックルベルト",
    "bohemian scum":            "ボヘミアンスカム",
    "frozen beauties":          "フローズンビューティーズ",
    "le rosey":                 "ル・ロゼ",
}

# ═══════════════════════════════════════════════════════════════════════════════
# Module-level sorted lookups (longest match first)
# ═══════════════════════════════════════════════════════════════════════════════

_SORTED_BRANDS = sorted(BRAND_TRANSLATIONS.keys(), key=len, reverse=True)
_SORTED_PRODUCTS = sorted(PRODUCT_TRANSLATIONS.keys(), key=len, reverse=True)


# ═══════════════════════════════════════════════════════════════════════════════
# JAPANESE STRING NORMALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

# Half-width katakana → full-width katakana mapping
_HW_TO_FW_KATAKANA: dict[str, str] = {}
for _hw in range(0xFF65, 0xFF9F + 1):
    _c = chr(_hw)
    _nfkc = unicodedata.normalize("NFKC", _c)
    if _nfkc != _c:
        _HW_TO_FW_KATAKANA[_c] = _nfkc


def normalize_jp_query(jp_str: str) -> str:
    """Normalize a Japanese query string for consistent search results.

    Steps:
        1. NFC Unicode normalization (canonical composition)
        2. Full-width ASCII → half-width (Ａ→A, ０→0, etc.)
        3. Half-width katakana → full-width katakana (ｸﾛﾑﾊｰﾂ→クロムハーツ)
        4. Ideographic space (U+3000) → regular space
        5. Collapse multiple whitespace to single space
        6. Strip leading/trailing whitespace
    """
    if not jp_str:
        return ""

    # Step 1: NFC normalize
    s = unicodedata.normalize("NFC", jp_str)

    # Step 2 + 3: NFKC handles both full-width ASCII→half-width AND
    # half-width katakana→full-width katakana in one pass
    s = unicodedata.normalize("NFKC", s)

    # Step 4: Ideographic space → regular space
    s = s.replace("\u3000", " ")

    # Step 5: Collapse whitespace
    s = re.sub(r"\s+", " ", s)

    # Step 6: Strip
    s = s.strip()

    return s


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSLATION
# ═══════════════════════════════════════════════════════════════════════════════

def translate_query(en_query: str) -> Optional[str]:
    """Translate an English query to Japanese.

    Returns the Japanese query string, or None if the brand is unknown
    (cannot be meaningfully translated for JP marketplace search).
    """
    q = en_query.lower().strip()

    # 1. Match brand prefix (longest match first)
    brand_jp = None
    remainder = q
    for brand_en in _SORTED_BRANDS:
        if q.startswith(brand_en):
            brand_jp = BRAND_TRANSLATIONS[brand_en][0]
            remainder = q[len(brand_en):].strip()
            break

    if brand_jp is None:
        return None  # Unknown brand — skip

    if not remainder:
        return normalize_jp_query(brand_jp)  # Brand-only query

    # 2. Translate product portion (longest match first)
    product_jp = None
    for product_en in _SORTED_PRODUCTS:
        if remainder == product_en or remainder.startswith(product_en):
            product_jp = PRODUCT_TRANSLATIONS[product_en]
            break

    if product_jp:
        return normalize_jp_query(f"{brand_jp} {product_jp}")

    # 3. Fallback: use English remainder as-is
    #    (JP sites often index English model names, season codes, etc.)
    return normalize_jp_query(f"{brand_jp} {remainder}")


def brand_info_from_query(en_query: str) -> tuple[str, str, float]:
    """Extract (brand_display, category, weight_kg) from an English query."""
    q = en_query.lower().strip()
    for brand_en in _SORTED_BRANDS:
        if q.startswith(brand_en):
            _, display, cat, weight = BRAND_TRANSLATIONS[brand_en]
            return display, cat, weight
    return "Unknown", "fashion", 0.8


def build_japan_target(en_query: str) -> Optional[dict]:
    """Convert a single English query to a Japan scraper target dict.

    Returns None if the query can't be translated (unknown brand).
    """
    jp = translate_query(en_query)
    if jp is None:
        return None
    brand, category, weight = brand_info_from_query(en_query)
    return {
        "jp": jp,
        "en": en_query.lower().strip(),
        "category": category,
        "brand": brand,
        "weight": weight,
    }


def build_japan_targets(en_queries: list[str]) -> list[dict]:
    """Convert a list of English queries into Japan target dicts.

    Only includes queries that can be translated (known brand prefix).
    Deduplicates by JP query string to avoid redundant scrapes.
    """
    targets = []
    seen_jp: set[str] = set()
    for q in en_queries:
        target = build_japan_target(q)
        if target is None:
            continue
        if target["jp"] in seen_jp:
            continue
        seen_jp.add(target["jp"])
        targets.append(target)
    return targets


# ═══════════════════════════════════════════════════════════════════════════════
# TIER PROPAGATION
# ═══════════════════════════════════════════════════════════════════════════════

def propagate_english_tiers_to_japan(
    en_perf: dict,
    jp_perf: dict,
    en_queries: list[str],
) -> list[dict]:
    """Build Japan targets with English tier data as a starting prior.

    For each translatable English query:
        - If the EN query is A-tier (high deal rate), the JP target gets a
          boosted score even if JP has no telemetry yet.
        - If the EN query is a trap (many runs, 0 deals), the JP target
          starts with a penalty.
        - Otherwise, neutral starting weight.

    JP-specific telemetry, if available, overrides the English prior
    (JP market dynamics may differ).

    Returns a list of target dicts sorted by effective score (desc).
    """
    from core.query_tiering import classify_query

    targets = build_japan_targets(en_queries)
    scored: list[tuple[dict, float]] = []

    for target in targets:
        en_key = target["en"]

        # Look up English telemetry for this query
        en_entry = (
            en_perf.get(en_key)
            or en_perf.get(en_key.lower())
        )
        en_tier = classify_query(en_key, en_entry)

        # Base score from English tier
        base_score = en_tier.weight_multiplier  # 3.5 / 1.0 / 0.15

        # JP telemetry override (if we have enough data)
        jp_entry = jp_perf.get(en_key) or jp_perf.get(en_key.lower())
        if jp_entry and jp_entry.get("total_runs", 0) >= 3:
            jp_tier = classify_query(en_key, jp_entry)
            # Use JP tier directly — we have real JP data
            base_score = jp_tier.weight_multiplier
        elif jp_entry and jp_entry.get("total_runs", 0) > 0:
            # Some JP data but not enough — blend EN prior with JP signal
            jp_deals = jp_entry.get("total_deals", 0)
            jp_runs = jp_entry.get("total_runs", 0)
            if jp_deals > 0:
                # JP found deals — boost the EN prior
                base_score *= 1.5
            elif jp_runs >= 2 and jp_deals == 0:
                # JP finding nothing — dampen slightly
                base_score *= 0.7

        scored.append((target, base_score))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    return [t for t, _ in scored]

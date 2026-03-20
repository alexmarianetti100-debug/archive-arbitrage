"""Tests for core.jp_query_translator — JP translation, normalization, tier propagation."""

import pytest
from core.jp_query_translator import (
    normalize_jp_query,
    translate_query,
    brand_info_from_query,
    build_japan_target,
    build_japan_targets,
    propagate_english_tiers_to_japan,
    BRAND_TRANSLATIONS,
    PRODUCT_TRANSLATIONS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# normalize_jp_query
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalizeJpQuery:
    def test_empty_string(self):
        assert normalize_jp_query("") == ""

    def test_strip_whitespace(self):
        assert normalize_jp_query("  クロムハーツ  ") == "クロムハーツ"

    def test_collapse_multiple_spaces(self):
        assert normalize_jp_query("クロムハーツ   リング") == "クロムハーツ リング"

    def test_ideographic_space_to_regular(self):
        """U+3000 (ideographic space) → regular ASCII space."""
        assert normalize_jp_query("クロムハーツ\u3000リング") == "クロムハーツ リング"

    def test_fullwidth_ascii_to_halfwidth(self):
        """Full-width ASCII digits/letters → half-width via NFKC."""
        # Ａ → A, ０ → 0
        assert normalize_jp_query("Ｂ２３") == "B23"

    def test_halfwidth_katakana_to_fullwidth(self):
        """Half-width katakana → full-width katakana via NFKC."""
        # ｸﾛﾑﾊｰﾂ → クロムハーツ
        assert normalize_jp_query("ｸﾛﾑﾊｰﾂ") == "クロムハーツ"

    def test_nfc_normalization(self):
        """Different Unicode forms of same character normalize to same output."""
        # が (U+304C precomposed) vs か+゛ (U+304B + U+3099 combining dakuten)
        precomposed = "バレンシアガ"
        decomposed = "バレンシアカ\u3099"  # カ + combining dakuten → ガ
        assert normalize_jp_query(precomposed) == normalize_jp_query(decomposed)

    def test_mixed_fullwidth_and_regular(self):
        """Mix of full-width numbers and regular katakana."""
        assert normalize_jp_query("トリプル　Ｓ") == "トリプル S"

    def test_preserves_valid_katakana(self):
        """Already-normalized query passes through unchanged."""
        q = "リックオウエンス ジオバスケット"
        assert normalize_jp_query(q) == q


# ═══════════════════════════════════════════════════════════════════════════════
# translate_query
# ═══════════════════════════════════════════════════════════════════════════════

class TestTranslateQuery:
    def test_known_brand_with_product(self):
        result = translate_query("chrome hearts ring")
        assert result == "クロムハーツ リング"

    def test_known_brand_only(self):
        result = translate_query("number nine")
        assert result == "ナンバーナイン"

    def test_unknown_brand_returns_none(self):
        assert translate_query("unknown brand jacket") is None

    def test_case_insensitive(self):
        result = translate_query("Rick Owens Geobasket")
        assert result == "リックオウエンス ジオバスケット"

    def test_longer_brand_matches_first(self):
        """'dior homme' should match before 'dior'."""
        result = translate_query("dior homme leather jacket")
        assert result is not None
        assert result.startswith("ディオールオム")

    def test_longer_product_matches_first(self):
        """'leather jacket' should match before 'leather'."""
        result = translate_query("raf simons leather jacket")
        assert result == "ラフシモンズ レザージャケット"

    def test_english_remainder_fallback(self):
        """Unknown product term falls back to English."""
        result = translate_query("rick owens fw23 special")
        assert result is not None
        assert result.startswith("リックオウエンス")
        assert "fw23 special" in result

    def test_margiela_alias(self):
        """Both 'maison margiela' and 'margiela' should translate."""
        full = translate_query("maison margiela tabi boots")
        short = translate_query("margiela tabi boots")
        # Both should produce マルジェラ
        assert full is not None and "マルジェラ" in full
        assert short is not None and "マルジェラ" in short

    def test_output_is_normalized(self):
        """Translation output should be normalized."""
        result = translate_query("chrome hearts cross pendant")
        assert result is not None
        # Should not have double spaces or trailing space
        assert "  " not in result
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_season_codes_preserved(self):
        """Year/season codes should pass through."""
        result = translate_query("raf simons 2002")
        assert result == "ラフシモンズ 2002"

    def test_fw_codes_preserved(self):
        result = translate_query("dior homme fw03")
        assert result is not None
        assert "FW03" in result or "fw03" in result.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# brand_info_from_query
# ═══════════════════════════════════════════════════════════════════════════════

class TestBrandInfoFromQuery:
    def test_known_brand(self):
        brand, cat, weight = brand_info_from_query("chrome hearts ring")
        assert brand == "Chrome Hearts"
        assert cat == "jewelry"
        assert weight == 0.1

    def test_fashion_brand(self):
        brand, cat, weight = brand_info_from_query("rick owens geobasket")
        assert brand == "Rick Owens"
        assert cat == "fashion"
        assert weight == 1.0

    def test_unknown_brand(self):
        brand, cat, weight = brand_info_from_query("totally unknown brand")
        assert brand == "Unknown"
        assert cat == "fashion"
        assert weight == 0.8


# ═══════════════════════════════════════════════════════════════════════════════
# build_japan_target / build_japan_targets
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildJapanTarget:
    def test_returns_complete_dict(self):
        target = build_japan_target("chrome hearts cross pendant")
        assert target is not None
        assert set(target.keys()) == {"jp", "en", "category", "brand", "weight"}
        assert target["jp"] == "クロムハーツ クロスペンダント"
        assert target["en"] == "chrome hearts cross pendant"
        assert target["category"] == "jewelry"
        assert target["brand"] == "Chrome Hearts"
        assert target["weight"] == 0.1

    def test_unknown_returns_none(self):
        assert build_japan_target("adidas yeezy 350") is None

    def test_en_field_is_lowercase(self):
        target = build_japan_target("Rick Owens DUNKS")
        assert target is not None
        assert target["en"] == "rick owens dunks"


class TestBuildJapanTargets:
    def test_translatable_queries_only(self):
        queries = ["chrome hearts ring", "unknown brand shoes", "rick owens boots"]
        targets = build_japan_targets(queries)
        assert len(targets) == 2
        brands = {t["brand"] for t in targets}
        assert "Chrome Hearts" in brands
        assert "Rick Owens" in brands

    def test_deduplication(self):
        """Same JP output from different EN queries should be deduped."""
        queries = ["margiela tabi", "maison margiela tabi"]
        targets = build_japan_targets(queries)
        # Both map to マルジェラ タビ — should be deduped
        assert len(targets) == 1

    def test_empty_input(self):
        assert build_japan_targets([]) == []

    def test_all_unknown(self):
        assert build_japan_targets(["unknown a", "unknown b"]) == []


# ═══════════════════════════════════════════════════════════════════════════════
# propagate_english_tiers_to_japan
# ═══════════════════════════════════════════════════════════════════════════════

def _perf_entry(runs=0, deals=0, gap=0.0):
    return {
        "total_runs": runs,
        "total_deals": deals,
        "best_gap": gap,
        "last_run": "2026-03-15T00:00:00",
    }


class TestPropagateEnglishTiers:
    def test_a_tier_english_boosts_jp(self):
        """A-tier EN query should rank higher than B-tier EN query in JP targets."""
        en_perf = {
            "rick owens geobasket": _perf_entry(runs=20, deals=10, gap=0.8),  # A-tier
            "helmut lang jacket": _perf_entry(runs=5, deals=0),                # B-tier
        }
        jp_perf = {}  # No JP data yet
        queries = ["rick owens geobasket", "helmut lang jacket"]
        targets = propagate_english_tiers_to_japan(en_perf, jp_perf, queries)

        assert len(targets) == 2
        # A-tier query should come first (higher score)
        assert targets[0]["en"] == "rick owens geobasket"

    def test_trap_english_demotes_jp(self):
        """Trap EN query should rank lower than B-tier EN query in JP targets."""
        en_perf = {
            "rick owens geobasket": _perf_entry(runs=50, deals=0),   # Trap
            "helmut lang jacket": _perf_entry(runs=2, deals=1),       # B-tier
        }
        jp_perf = {}
        queries = ["rick owens geobasket", "helmut lang jacket"]
        targets = propagate_english_tiers_to_japan(en_perf, jp_perf, queries)

        assert len(targets) == 2
        # Trap query should be last
        assert targets[-1]["en"] == "rick owens geobasket"

    def test_jp_telemetry_overrides_en(self):
        """JP-specific data should override EN prior when sufficient."""
        en_perf = {
            "chrome hearts ring": _perf_entry(runs=50, deals=0),  # EN trap
        }
        jp_perf = {
            "chrome hearts ring": _perf_entry(runs=10, deals=5),  # JP A-tier!
        }
        queries = ["chrome hearts ring", "rick owens boots"]
        targets = propagate_english_tiers_to_japan(en_perf, jp_perf, queries)

        # JP says chrome hearts ring is great — should rank first
        assert targets[0]["en"] == "chrome hearts ring"

    def test_no_en_perf_still_works(self):
        """Empty EN perf data should not crash — all queries get B-tier."""
        targets = propagate_english_tiers_to_japan(
            {}, {}, ["chrome hearts ring", "rick owens boots"]
        )
        assert len(targets) == 2

    def test_untranslatable_queries_excluded(self):
        """Queries with unknown brands should be excluded."""
        targets = propagate_english_tiers_to_japan(
            {}, {}, ["unknown brand x", "chrome hearts ring"]
        )
        assert len(targets) == 1
        assert targets[0]["en"] == "chrome hearts ring"


# ═══════════════════════════════════════════════════════════════════════════════
# English pipeline backward compatibility
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnglishPipelineUnchanged:
    """Verify that the existing English normalization pipeline is not affected."""

    def test_normalize_query_unchanged(self):
        """English normalize_query should still work identically."""
        from core.query_normalization import normalize_query
        assert normalize_query("Rick Owens Boots") == "rick owens boots"
        assert normalize_query("  chrome   hearts  ") == "chrome hearts"
        assert normalize_query("Helmut Lang") == "helmut lang"

    def test_is_promoted_unchanged(self):
        from core.query_normalization import is_promoted_query
        assert is_promoted_query("chrome hearts cross pendant") is True
        assert is_promoted_query("random unknown query") is False

    def test_is_demoted_unchanged(self):
        from core.query_normalization import is_demoted_query
        assert is_demoted_query("balenciaga triple s") is True
        assert is_demoted_query("rick owens geobasket") is False

    def test_query_tiering_unchanged(self):
        from core.query_tiering import classify_query, QueryTier
        # A-tier: high deal rate
        r = classify_query("test", {"total_runs": 10, "total_deals": 5, "best_gap": 0.5})
        assert r.tier == QueryTier.A
        # Trap: many runs, 0 deals
        r = classify_query("test", {"total_runs": 30, "total_deals": 0, "best_gap": 0.0})
        assert r.tier == QueryTier.TRAP


# ═══════════════════════════════════════════════════════════════════════════════
# Translation coverage
# ═══════════════════════════════════════════════════════════════════════════════

class TestTranslationCoverage:
    """Ensure key English pipeline queries have JP translations."""

    # Queries that appear in CORE_TARGETS or PROMOTED_LIQUIDITY_QUERIES
    MUST_TRANSLATE = [
        "chrome hearts cross pendant",
        "chrome hearts ring",
        "rick owens geobasket",
        "rick owens dunks",
        "maison margiela tabi boots",
        "saint laurent wyatt boots",
        "helmut lang leather jacket",
        "raf simons leather jacket",
        "jean paul gaultier mesh top",
        "dior homme leather jacket",
        "undercover jacket",
        "balenciaga triple s",
        "bottega veneta tire boots",
        "enfants riches deprimes hoodie",
    ]

    @pytest.mark.parametrize("query", MUST_TRANSLATE)
    def test_core_query_translates(self, query):
        result = translate_query(query)
        assert result is not None, f"'{query}' should translate but returned None"
        assert len(result) > 0

    @pytest.mark.parametrize("query", MUST_TRANSLATE)
    def test_core_query_builds_target(self, query):
        target = build_japan_target(query)
        assert target is not None, f"'{query}' should produce a target"
        assert target["jp"]  # non-empty JP query
        assert target["brand"] != "Unknown"

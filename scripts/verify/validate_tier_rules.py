#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
CONFIG_PATH = ROOT / "config" / "tier_rules.json"
VALID_TIERS = {"beginner", "pro", "big_baller"}
REQUIRED_TOP_LEVEL = ["beginner", "pro", "big_baller", "strict_auth_brands", "terms"]
REQUIRED_TIER_FIELDS = {
    "beginner": ["min_profit", "min_margin", "min_liquidity", "brands", "routing"],
    "pro": ["min_profit", "min_margin", "min_liquidity", "brands", "routing"],
    "big_baller": ["min_profit", "min_margin", "min_liquidity", "brands", "routing"],
}


def fail(msg: str) -> None:
    print(f"❌ {msg}")
    raise SystemExit(1)


def check_numeric(obj: dict, key: str, label: str) -> None:
    if key in obj and not isinstance(obj[key], (int, float)):
        fail(f"{label}.{key} must be numeric")


def main() -> None:
    if not CONFIG_PATH.exists():
        fail(f"Missing config: {CONFIG_PATH}")

    try:
        data = json.loads(CONFIG_PATH.read_text())
    except Exception as e:
        fail(f"Invalid JSON: {e}")

    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            fail(f"Missing top-level key: {key}")

    for tier, required_fields in REQUIRED_TIER_FIELDS.items():
        block = data.get(tier)
        if not isinstance(block, dict):
            fail(f"{tier} must be an object")
        for field in required_fields:
            if field not in block:
                fail(f"Missing field: {tier}.{field}")
        if not isinstance(block.get("brands"), list):
            fail(f"{tier}.brands must be a list")
        if not isinstance(block.get("routing"), list):
            fail(f"{tier}.routing must be a list")
        invalid = [x for x in block.get("routing", []) if x not in VALID_TIERS]
        if invalid:
            fail(f"{tier}.routing contains invalid tier(s): {invalid}")
        for numeric_key in ["min_profit", "min_margin", "min_liquidity", "min_auth", "strict_auth_min", "min_price", "max_price"]:
            check_numeric(block, numeric_key, tier)

    if not isinstance(data.get("strict_auth_brands"), list):
        fail("strict_auth_brands must be a list")

    terms = data.get("terms")
    if not isinstance(terms, dict):
        fail("terms must be an object")
    for key in ["watch", "bag", "jewelry", "shoe", "archive"]:
        if key not in terms or not isinstance(terms[key], list):
            fail(f"terms.{key} must be a list")

    from core.tier_policy import classify_discord_tiers

    samples = [
        ("Chrome Hearts Cross Pendant", 340, 0.50, 9.0, 0.85, "beginner"),
        ("Cartier Love Bracelet Size 17", 4200, 0.38, 8.5, 0.92, "pro"),
        ("Hermes Birkin 25 Gold Togo", 18500, 0.34, 8.0, 0.95, "big_baller"),
    ]
    for title, price, margin, liquidity, auth, expected in samples:
        item = SimpleNamespace(title=title, price=price, source="grailed")
        signals = SimpleNamespace(liquidity_score=liquidity)
        auth_result = SimpleNamespace(confidence=auth)
        profit = price * margin
        decision = classify_discord_tiers(item, profit, margin, signals=signals, auth_result=auth_result)
        if decision.minimum_tier != expected:
            fail(f"Sample classification mismatch for '{title}': expected {expected}, got {decision.minimum_tier}")

    print(f"✅ Tier rules valid: {CONFIG_PATH}")


if __name__ == "__main__":
    main()

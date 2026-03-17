"""Tests for deal_quality.py score weight recalibration."""

from core.deal_quality import (
    WEIGHT_GAP, WEIGHT_LINE, WEIGHT_CONDITION,
    WEIGHT_SEASON, WEIGHT_SIZE, WEIGHT_AUTH, WEIGHT_LIQUIDITY,
)


class TestWeightDistribution:
    def test_weights_sum_to_100(self):
        total = WEIGHT_GAP + WEIGHT_LINE + WEIGHT_CONDITION + WEIGHT_SEASON + WEIGHT_SIZE + WEIGHT_AUTH + WEIGHT_LIQUIDITY
        assert total == 100

    def test_gap_is_dominant_signal(self):
        assert WEIGHT_GAP >= 40

    def test_liquidity_reduced(self):
        assert WEIGHT_LIQUIDITY <= 10

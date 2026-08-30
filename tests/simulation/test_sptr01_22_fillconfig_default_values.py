from __future__ import annotations

from decimal import Decimal

from app.simulation.fill_config import FillAssumptionsConfig, FILL_MODEL_VERSION


class TestFillConfigDefaults:
    def test_22_01_defaults_match_story_spec(self):
        cfg = FillAssumptionsConfig()
        assert cfg.taker_fee_bps == Decimal("10")
        assert cfg.maker_fee_bps == Decimal("4")
        assert cfg.default_fee_type == "taker"
        assert cfg.default_spread_bps == 5.0
        assert cfg.base_slippage_bps == 2.0
        assert cfg.max_slippage_bps == 500.0
        assert cfg.base_latency_ms == 50
        assert cfg.max_latency_ms == 5000
        assert cfg.latency_jitter_ms == 10
        assert cfg.fill_ratio == Decimal("1.0")
        assert cfg.partial_count_limit == 1
        assert cfg.max_spread_bps == 1000.0
        assert cfg.max_fee_bps == Decimal("100")
        assert cfg.min_fee_quote_floor == Decimal("0.00000001")

    def test_22_02_fill_model_version_locked(self):
        assert FILL_MODEL_VERSION == "1.0.0"

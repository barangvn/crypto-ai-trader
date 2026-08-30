from __future__ import annotations

from decimal import Decimal

import pytest

from app.contracts import (
    PaperOrderSide,
    QualityFlags,
    Symbol,
)
from app.simulation import (
    FillAssumptionsConfig,
    PaperExecutionSimulator,
    apply_slippage_directional,
    apply_spread_cost,
    calculate_fee_quote,
    calculate_fill_quantities,
    deterministic_latency_ms,
    build_pipeline_reference_data,
)


_5_MODEL_SCENARIOS = [
    ("spread", "zero", PaperOrderSide.BUY),
    ("spread", "small", PaperOrderSide.BUY),
    ("spread", "normal", PaperOrderSide.BUY),
    ("spread", "high", PaperOrderSide.BUY),
    ("spread", "invalid", PaperOrderSide.BUY),
    ("spread", "zero", PaperOrderSide.SELL),
    ("spread", "small", PaperOrderSide.SELL),
    ("spread", "normal", PaperOrderSide.SELL),
    ("spread", "high", PaperOrderSide.SELL),
    ("spread", "invalid", PaperOrderSide.SELL),
    ("slippage", "zero", PaperOrderSide.BUY),
    ("slippage", "small", PaperOrderSide.BUY),
    ("slippage", "normal", PaperOrderSide.BUY),
    ("slippage", "high", PaperOrderSide.BUY),
    ("slippage", "invalid", PaperOrderSide.BUY),
    ("slippage", "zero", PaperOrderSide.SELL),
    ("slippage", "small", PaperOrderSide.SELL),
    ("slippage", "normal", PaperOrderSide.SELL),
    ("slippage", "high", PaperOrderSide.SELL),
    ("slippage", "invalid", PaperOrderSide.SELL),
    ("fee", "zero", PaperOrderSide.BUY),
    ("fee", "small", PaperOrderSide.BUY),
    ("fee", "normal", PaperOrderSide.BUY),
    ("fee", "high", PaperOrderSide.BUY),
    ("fee", "invalid", PaperOrderSide.BUY),
    ("fee", "zero", PaperOrderSide.SELL),
    ("fee", "small", PaperOrderSide.SELL),
    ("fee", "normal", PaperOrderSide.SELL),
    ("fee", "high", PaperOrderSide.SELL),
    ("fee", "invalid", PaperOrderSide.SELL),
    ("latency", "zero", PaperOrderSide.BUY),
    ("latency", "small", PaperOrderSide.BUY),
    ("latency", "normal", PaperOrderSide.BUY),
    ("latency", "high", PaperOrderSide.BUY),
    ("latency", "invalid", PaperOrderSide.BUY),
    ("latency", "zero", PaperOrderSide.SELL),
    ("latency", "small", PaperOrderSide.SELL),
    ("latency", "normal", PaperOrderSide.SELL),
    ("latency", "high", PaperOrderSide.SELL),
    ("latency", "invalid", PaperOrderSide.SELL),
    ("partial", "zero", PaperOrderSide.BUY),
    ("partial", "small", PaperOrderSide.BUY),
    ("partial", "normal", PaperOrderSide.BUY),
    ("partial", "high", PaperOrderSide.BUY),
    ("partial", "invalid", PaperOrderSide.BUY),
    ("partial", "zero", PaperOrderSide.SELL),
    ("partial", "small", PaperOrderSide.SELL),
    ("partial", "normal", PaperOrderSide.SELL),
    ("partial", "high", PaperOrderSide.SELL),
    ("partial", "invalid", PaperOrderSide.SELL),
]


def _make_config(model: str, level: str) -> FillAssumptionsConfig:
    base = FillAssumptionsConfig()
    if model == "spread":
        if level == "zero":
            return FillAssumptionsConfig(default_spread_bps=0.0)
        elif level == "small":
            return FillAssumptionsConfig(default_spread_bps=1.0)
        elif level == "normal":
            return FillAssumptionsConfig(default_spread_bps=5.0)
        elif level == "high":
            return FillAssumptionsConfig(default_spread_bps=800.0)
        else:
            return FillAssumptionsConfig(default_spread_bps=10001.0)
    if model == "slippage":
        if level == "zero":
            return FillAssumptionsConfig(base_slippage_bps=0.0)
        elif level == "small":
            return FillAssumptionsConfig(base_slippage_bps=1.0)
        elif level == "normal":
            return FillAssumptionsConfig(base_slippage_bps=10.0)
        elif level == "high":
            return FillAssumptionsConfig(base_slippage_bps=400.0)
        else:
            return FillAssumptionsConfig(base_slippage_bps=1000.0)
    if model == "fee":
        if level == "zero":
            return FillAssumptionsConfig(taker_fee_bps=Decimal("0.0001"))
        elif level == "small":
            return FillAssumptionsConfig(taker_fee_bps=Decimal("1"))
        elif level == "normal":
            return FillAssumptionsConfig(taker_fee_bps=Decimal("10"))
        elif level == "high":
            return FillAssumptionsConfig(taker_fee_bps=Decimal("80"))
        else:
            return FillAssumptionsConfig(taker_fee_bps=Decimal("200"))
    if model == "latency":
        if level == "zero":
            return FillAssumptionsConfig(base_latency_ms=0, latency_jitter_ms=0)
        elif level == "small":
            return FillAssumptionsConfig(base_latency_ms=5, latency_jitter_ms=2)
        elif level == "normal":
            return FillAssumptionsConfig(base_latency_ms=50, latency_jitter_ms=10)
        elif level == "high":
            return FillAssumptionsConfig(base_latency_ms=4000, latency_jitter_ms=500)
        else:
            return FillAssumptionsConfig(base_latency_ms=6000, latency_jitter_ms=0)
    if model == "partial":
        if level == "zero":
            return FillAssumptionsConfig(fill_ratio=Decimal("0"))
        elif level == "small":
            return FillAssumptionsConfig(fill_ratio=Decimal("0.01"))
        elif level == "normal":
            return FillAssumptionsConfig(fill_ratio=Decimal("0.5"))
        elif level == "high":
            return FillAssumptionsConfig(fill_ratio=Decimal("0.9999"))
        else:
            return FillAssumptionsConfig(fill_ratio=Decimal("1.5"))
    return base


class TestBoundary5ModelMatrix:
    @pytest.mark.parametrize("model,level,side", _5_MODEL_SCENARIOS)
    def test_21_01_five_model_boundary_matrix(self, model, level, side, sptr01_order_buy, sptr01_order_sell, sptr01_ref_tick, sptr01_tick_no_bidask, sptr01_bus):
        from app.simulation import build_pipeline_reference_data
        config = _make_config(model, level)
        sim = PaperExecutionSimulator(config=config, event_bus=sptr01_bus)
        order = sptr01_order_buy if side == PaperOrderSide.BUY else sptr01_order_sell
        if model == "spread" and level == "invalid":
            ref = build_pipeline_reference_data(tick=sptr01_tick_no_bidask)
        else:
            ref = sptr01_ref_tick
        result = sim.simulate(
            order=order,
            reference=ref,
            quality_ctx=QualityFlags(),
            publish_to_bus=False,
        )
        invalid = level == "invalid"
        if invalid:
            assert result.rejected is True, f"{model}/{level}/{side} expected reject"
            assert len(result.reject_reasons) >= 1
        else:
            if result.rejected:
                assert result.reject_reasons, "reasons exist"
            else:
                assert result.fill is not None, f"{model}/{level}/{side} should fill"
                assert result.fill.fill_qty_base > 0

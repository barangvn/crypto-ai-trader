from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from app.contracts import (
    CONTRACT_VERSION,
    MarketTick,
    PaperOrder,
    PaperOrderPolicyRefs,
    PaperOrderSide,
    PaperOrderStatus,
    PaperOrderType,
    QualityFlags,
    Symbol,
    format_instant,
    schema_sha256,
)
from app.platform.event_bus import InMemoryTypedEventBus
from app.simulation import (
    FillAssumptionsConfig,
    PaperExecutionSimulator,
    build_pipeline_reference_data,
)


# G16: 14 tests — AD-20 Determinism 10x for 7 fixtures × 2 side (buy/sell = 14)
def _make_order(side: PaperOrderSide, ts: str, corr: str, rd: str, po: str, qty: Decimal) -> PaperOrder:
    policy = PaperOrderPolicyRefs(
        risk_decision_id=rd, strategy_id="trend_momentum_v1", strategy_version="1.0.0",
    )
    return PaperOrder(
        paper_order_id=po,
        side=side,
        order_type=PaperOrderType.MARKET,
        requested_qty_base=qty,
        policy_refs=policy,
        status=PaperOrderStatus.CREATED,
        created_at=ts,
        updated_at=ts,
        correlation_id=corr,
        causation_id=rd,
    )


FIXTURES = [
    # (name, side, qty, cfg_overrides, price, bid, ask, spread)
    ("f1_small_qty_buy", PaperOrderSide.BUY, Decimal("0.001"), {}, Decimal("50000"), Decimal("49990"), Decimal("50010"), 40.0),
    ("f2_large_qty_buy", PaperOrderSide.BUY, Decimal("100.0"), {}, Decimal("50000"), Decimal("49990"), Decimal("50010"), 40.0),
    ("f3_partial_buy", PaperOrderSide.BUY, Decimal("0.1"), {"fill_ratio": Decimal("0.3")}, Decimal("100"), Decimal("99.9"), Decimal("100.1"), 2.0),
    ("f4_zero_spread_buy", PaperOrderSide.BUY, Decimal("0.1"), {"default_spread_bps": 0.0, "base_slippage_bps": 0.0}, Decimal("10"), None, None, None),
    ("f5_high_fee_buy", PaperOrderSide.BUY, Decimal("0.5"), {"taker_fee_bps": Decimal("100"), "max_fee_bps": Decimal("100")}, Decimal("1000"), Decimal("999.9"), Decimal("1000.1"), 0.2),
    ("f6_max_latency_buy", PaperOrderSide.BUY, Decimal("1"), {"base_latency_ms": 5000, "latency_jitter_ms": 0}, Decimal("50"), Decimal("49.9"), Decimal("50.1"), 4.0),
    ("f7_candle_ref_buy", PaperOrderSide.BUY, Decimal("2.5"), {}, None, None, None, None),
]


@pytest.mark.parametrize("idx", range(7))
def test_determinism_buy_side_10x(idx, sptr01_ts, sptr01_candle_closed):
    name, side, qty, cfg_ovr, price, bid, ask, spread = FIXTURES[idx]
    cfg = FillAssumptionsConfig(**cfg_ovr) if "max_fee_bps" in cfg_ovr else FillAssumptionsConfig(**cfg_ovr)
    ts = sptr01_ts
    corr = f"COR_{name}_XXXX_0000001"
    rd = f"RD_{name}_XXXX_000000001"
    po = f"PO_{name}_XXXX_000000001"
    order = _make_order(side, ts, corr, rd, po, qty)
    qf = QualityFlags()
    if name.startswith("f7_"):
        ref = build_pipeline_reference_data(candle=sptr01_candle_closed, symbol=Symbol("BTC_USDT"))
    else:
        tick = MarketTick(
            price=price, market_ts=ts, bid_price=bid, ask_price=ask, spread_bps=spread,
        )
        ref = build_pipeline_reference_data(tick=tick, symbol=Symbol("BTC_USDT"))
    results = []
    hashes = []
    for run in range(10):
        bus = InMemoryTypedEventBus()
        sim = PaperExecutionSimulator(config=cfg, event_bus=bus)
        res = sim.simulate(order=order, reference=ref, quality_ctx=qf)
        assert res.fill is not None, f"{name} run {run} failed {res.reject_reasons}"
        results.append((
            str(res.fill.fill_price), str(res.fill.fill_qty_base),
            str(res.fill.fill_qty_quote), str(res.fill.fees_quote),
            res.fill.slippage_bps, res.fill.latency_ms,
        ))
        hashes.append(schema_sha256(res.fill))
    # All runs identical
    assert len(set(hashes)) == 1, f"{name}: sha256 not identical {hashes}"
    assert len(set(results)) == 1, f"{name}: run results not identical"


@pytest.mark.parametrize("idx", range(7))
def test_determinism_sell_side_10x(idx, sptr01_ts, sptr01_candle_closed):
    name_t, _, qty, cfg_ovr, price, bid, ask, spread = FIXTURES[idx]
    side = PaperOrderSide.SELL
    name = name_t.replace("_buy", "_sell")
    if "max_fee_bps" in cfg_ovr:
        cfg = FillAssumptionsConfig(**cfg_ovr)
    else:
        cfg = FillAssumptionsConfig(**cfg_ovr)
    ts = sptr01_ts
    corr = f"COR_{name}_X_0000001"
    rd = f"RD_{name}_X000000001"
    po = f"PO_{name}_X000000001"
    order = _make_order(side, ts, corr, rd, po, qty)
    qf = QualityFlags()
    if name_t.startswith("f7_"):
        ref = build_pipeline_reference_data(candle=sptr01_candle_closed, symbol=Symbol("BTC_USDT"))
    else:
        tick = MarketTick(
            price=price, market_ts=ts, bid_price=bid, ask_price=ask, spread_bps=spread,
        )
        ref = build_pipeline_reference_data(tick=tick, symbol=Symbol("BTC_USDT"))
    results = []
    hashes = []
    for run in range(10):
        bus = InMemoryTypedEventBus()
        sim = PaperExecutionSimulator(config=cfg, event_bus=bus)
        res = sim.simulate(order=order, reference=ref, quality_ctx=qf)
        assert res.fill is not None, f"{name} run {run} rejected: {res.reject_reasons}"
        results.append((
            str(res.fill.fill_price), str(res.fill.fill_qty_base),
            str(res.fill.fill_qty_quote), str(res.fill.fees_quote),
        ))
        hashes.append(schema_sha256(res.fill))
    assert len(set(hashes)) == 1, f"{name}: sha256 not identical"
    assert len(set(results)) == 1, f"{name}: results not identical"

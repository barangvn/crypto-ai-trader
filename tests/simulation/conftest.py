from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid5

import pytest

from app.contracts import (
    CONTRACT_VERSION,
    Candle,
    ClockRef,
    MarketTick,
    OrderBookSnapshot,
    PaperOrder,
    PaperOrderPolicyRefs,
    PaperOrderSide,
    PaperOrderStatus,
    PaperOrderType,
    QualityFlags,
    RunMode,
    SourceType,
    Symbol,
    format_instant,
)
from app.platform.event_bus import InMemoryTypedEventBus
from app.simulation import (
    FILL_MODEL_VERSION,
    FillAssumptionsConfig,
    PaperExecutionSimulator,
    PipelineReferenceData,
    build_pipeline_reference_data,
)


FIXTURE_TS = "2026-08-30T12:00:00.000Z"
FIXED_CORR = "COR000000000000000000000001"
FIXED_RD_ID = "RD0000000000000000000000001"
FIXED_PO_ID = "PO0000000000000000000000001"
FIXED_NAMESPACE = UUID("01920000-0000-7000-8000-000000000000")


@pytest.fixture
def sptr01_ts() -> str:
    return FIXTURE_TS


@pytest.fixture
def sptr01_policy_refs() -> PaperOrderPolicyRefs:
    return PaperOrderPolicyRefs(
        risk_decision_id=FIXED_RD_ID,
        strategy_id="trend_momentum_v1",
        strategy_version="1.0.0",
    )


@pytest.fixture
def sptr01_order_buy(sptr01_ts, sptr01_policy_refs) -> PaperOrder:
    return PaperOrder(
        paper_order_id=FIXED_PO_ID,
        side=PaperOrderSide.BUY,
        order_type=PaperOrderType.MARKET,
        requested_qty_base=Decimal("0.1"),
        policy_refs=sptr01_policy_refs,
        status=PaperOrderStatus.CREATED,
        created_at=sptr01_ts,
        updated_at=sptr01_ts,
        correlation_id=FIXED_CORR,
        causation_id=FIXED_RD_ID,
    )


@pytest.fixture
def sptr01_order_sell(sptr01_ts, sptr01_policy_refs) -> PaperOrder:
    return PaperOrder(
        paper_order_id=FIXED_PO_ID + "S",
        side=PaperOrderSide.SELL,
        order_type=PaperOrderType.MARKET,
        requested_qty_base=Decimal("0.1"),
        policy_refs=sptr01_policy_refs,
        status=PaperOrderStatus.CREATED,
        created_at=sptr01_ts,
        updated_at=sptr01_ts,
        correlation_id=FIXED_CORR,
        causation_id=FIXED_RD_ID,
    )


@pytest.fixture
def sptr01_tick_btc(sptr01_ts) -> MarketTick:
    return MarketTick(
        price=Decimal("50000.0"),
        market_ts=sptr01_ts,
        bid_price=Decimal("49990.0"),
        ask_price=Decimal("50010.0"),
        last_size=Decimal("0.5"),
        spread_bps=4.0,
    )


@pytest.fixture
def sptr01_tick_no_bidask(sptr01_ts) -> MarketTick:
    return MarketTick(
        price=Decimal("50000.0"),
        market_ts=sptr01_ts,
    )


@pytest.fixture
def sptr01_candle_closed(sptr01_ts) -> Candle:
    return Candle(
        timeframe="1m",
        open_time="2026-08-30T11:59:00.000Z",
        close_time=sptr01_ts,
        open=Decimal("49800.0"),
        high=Decimal("50100.0"),
        low=Decimal("49700.0"),
        close=Decimal("50000.0"),
        volume=Decimal("1234.5"),
        closed=True,
    )


@pytest.fixture
def sptr01_candle_notclosed(sptr01_ts) -> Candle:
    return Candle(
        timeframe="1m",
        open_time="2026-08-30T11:59:00.000Z",
        close_time=sptr01_ts,
        open=Decimal("49800.0"),
        high=Decimal("50100.0"),
        low=Decimal("49700.0"),
        close=Decimal("50000.0"),
        volume=Decimal("1234.5"),
        closed=False,
    )


@pytest.fixture
def sptr01_orderbook(sptr01_ts) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        depth_levels=5,
        bids=[
            [Decimal("49990.0"), Decimal("1.5")],
            [Decimal("49989.0"), Decimal("0.8")],
        ],
        asks=[
            [Decimal("50010.0"), Decimal("2.0")],
            [Decimal("50011.0"), Decimal("1.1")],
        ],
        book_ts=sptr01_ts,
    )


@pytest.fixture
def sptr01_orderbook_crossed(sptr01_ts) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        depth_levels=1,
        bids=[[Decimal("50010.0"), Decimal("1.0")]],
        asks=[[Decimal("50000.0"), Decimal("1.0")]],
        book_ts=sptr01_ts,
    )


@pytest.fixture
def sptr01_config_default() -> FillAssumptionsConfig:
    return FillAssumptionsConfig()


@pytest.fixture
def sptr01_config_zero_costs() -> FillAssumptionsConfig:
    return FillAssumptionsConfig(
        taker_fee_bps=Decimal("0.0001"),
        default_spread_bps=0.0,
        base_slippage_bps=0.0,
        base_latency_ms=0,
        latency_jitter_ms=0,
        fill_ratio=Decimal("1.0"),
        min_fee_quote_floor=Decimal("0.00000001"),
    )


@pytest.fixture
def sptr01_config_partial() -> FillAssumptionsConfig:
    return FillAssumptionsConfig(
        fill_ratio=Decimal("0.5"),
    )


@pytest.fixture
def sptr01_config_high_latency() -> FillAssumptionsConfig:
    return FillAssumptionsConfig(
        base_latency_ms=5000,
        latency_jitter_ms=0,
    )


@pytest.fixture
def sptr01_quality_healthy() -> QualityFlags:
    return QualityFlags()


@pytest.fixture(params=[
    ("stale", dict(stale=True)),
    ("invalid", dict(invalid=True)),
    ("quarantined", dict(quarantined=True)),
    ("duplicate", dict(duplicate=True)),
    ("out_of_order", dict(out_of_order=True)),
    ("missing", dict(missing=True)),
])
def sptr01_quality_blocked(request) -> tuple[str, QualityFlags]:
    name, kwargs = request.param
    return name, QualityFlags(**kwargs)


@pytest.fixture
def sptr01_bus() -> InMemoryTypedEventBus:
    return InMemoryTypedEventBus()


@pytest.fixture
def sptr01_sim_default(sptr01_bus, sptr01_config_default) -> PaperExecutionSimulator:
    return PaperExecutionSimulator(config=sptr01_config_default, event_bus=sptr01_bus)


@pytest.fixture
def sptr01_ref_tick(sptr01_tick_btc) -> PipelineReferenceData:
    return build_pipeline_reference_data(tick=sptr01_tick_btc, symbol=Symbol("BTC_USDT"))


@pytest.fixture
def sptr01_ref_ob(sptr01_orderbook) -> PipelineReferenceData:
    return build_pipeline_reference_data(orderbook=sptr01_orderbook, symbol=Symbol("BTC_USDT"))


@pytest.fixture
def sptr01_ref_candle(sptr01_candle_closed) -> PipelineReferenceData:
    return build_pipeline_reference_data(candle=sptr01_candle_closed, symbol=Symbol("BTC_USDT"))


@pytest.fixture
def sptr01_clock_ref(sptr01_ts) -> ClockRef:
    return ClockRef(wall=sptr01_ts)


def _bypass_paper_order(**overrides: Any) -> PaperOrder:
    """Normally impossible PaperOrder states for defense-in-depth testing."""
    policy = PaperOrderPolicyRefs(
        risk_decision_id=FIXED_RD_ID,
        strategy_id="x",
        strategy_version="1.0.0",
    )
    base = dict(
        paper_order_id=FIXED_PO_ID + "BP",
        side=PaperOrderSide.BUY,
        order_type=PaperOrderType.MARKET,
        requested_qty_base=Decimal("0.1"),
        policy_refs=policy,
        status=PaperOrderStatus.CREATED,
        created_at=FIXTURE_TS,
        updated_at=FIXTURE_TS,
        correlation_id=FIXED_CORR,
        causation_id=FIXED_RD_ID,
    )
    base.update(overrides)
    try:
        return PaperOrder(**base)
    except Exception:
        instance = object.__new__(PaperOrder)
        for k, v in base.items():
            try:
                object.__setattr__(instance, k, v)
            except Exception:
                pass
        return instance

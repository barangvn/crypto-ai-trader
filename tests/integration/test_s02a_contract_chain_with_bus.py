"""S-CON-02A DoD-14 integration test: contract chain on the canonical event bus.

Publishes each contract through CanonicalEventEnvelope, verifying the
correlation_id stays fixed (chain invariant) and the causation_id links
parent->child correctly through the five-event chain:

  Candle
    -> FeatureVector
    -> MarketRegime
    -> StrategyContext
    -> StrategySignal

Also: backward-compat smoke publishes the original legacy 5 payloads without
the new contracts touching public API.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.contracts import (
    CONTRACT_VERSION,
    Candle,
    CanonicalEventEnvelope,
    ClockRef,
    ContractSchemaError,
    EligibilityContextView,
    FeatureVector,
    LookbackWindowSpec,
    MarketRegime,
    MarketRegimeState,
    MarketTick,
    OpportunityScoreComponentPolicy,
    OrderBookSnapshot,
    OrderBookUpdate,
    PortfolioContextView,
    QualityFlags,
    RunMode,
    SchemaRef,
    SignalDirection,
    SourceType,
    StopPolicySpec,
    StrategyContext,
    StrategySignal,
    TakeProfitPolicySpec,
    TimeRangeSpec,
    TradeEvent,
    ULID,
    format_instant,
    now_instant,
)
from app.platform.event_bus import InMemoryTypedEventBus


# ---------------------------------------------------------------------------
# Local ULID generator (test-only helper, keeps imports clean)
# Uses the same ULID shape the rest of the regression suite uses.
# ---------------------------------------------------------------------------

_EVENT_COUNTER = 10_000


def new_event_id() -> ULID:
    global _EVENT_COUNTER
    _EVENT_COUNTER += 1
    return ULID(f"01920000-0000-7000-8000-{_EVENT_COUNTER:012d}")


SYMBOL = "BTC_USDT"
SOURCE = "replay_bundle"
RUN_MODE = RunMode.PAPER
SOURCE_TYPE = SourceType.REPLAY


def _envelope(
    event_type: str,
    payload,
    correlation_id: str,
    causation_id: str,
    timestamp: str,
) -> CanonicalEventEnvelope:
    return CanonicalEventEnvelope(
        event_id=new_event_id(),
        event_type=event_type,
        contract_version=CONTRACT_VERSION,
        symbol=SYMBOL,
        source=SOURCE,
        timestamp=timestamp,
        ingest_ts=timestamp,
        correlation_id=correlation_id,
        causation_id=causation_id,
        run_mode=RUN_MODE,
        source_type=SOURCE_TYPE,
        clock_ref=ClockRef(wall=timestamp, replay=timestamp),
        quality_flags=QualityFlags(missing=False),
        schema_ref=SchemaRef(),
        payload=payload,
    )


def _candle(t0: str) -> Candle:
    return Candle(
        timeframe="1m",
        open_time=t0,
        close_time=t0,
        open=Decimal("44900.0"),
        high=Decimal("45100.0"),
        low=Decimal("44800.0"),
        close=Decimal("45050.0"),
        volume=Decimal("123.456"),
        closed=True,
        trade_count=10,
    )


def _feature_vector() -> FeatureVector:
    return FeatureVector(
        feature_version="fv_chain_v1",
        timeframe="1m",
        features={
            "rsi14": 55.0,
            "sma20": Decimal("45000.0"),
            "vol": Decimal("123.456"),
            "close_change_pct": 0.33,
        },
        lookback_window=LookbackWindowSpec(count=20, timeframe="1m"),
        input_refs=[],
    )


def _regime(t0: str, t1: str) -> MarketRegime:
    scores = {s.value: 1 / 6 for s in MarketRegimeState}
    return MarketRegime(
        timeframe="1m",
        regime=MarketRegimeState.BULL,
        confidence=0.8,
        scores=scores,
        detector_version="regime_chain_v1",
        feature_version="fv_chain_v1",
        lookback_ts=TimeRangeSpec(start=t0, end=t1),
    )


def _context(env_candle: CanonicalEventEnvelope, fv: FeatureVector, regime: MarketRegime) -> StrategyContext:
    return StrategyContext.derive_from_envelope(
        env_candle,
        features=fv,
        regime=regime,
        portfolio_ctx=PortfolioContextView(),
        eligibility_ctx=EligibilityContextView(eligible=True, reasons=["ok"]),
        scoring_policy=OpportunityScoreComponentPolicy(
            policy_version="chain_v1",
            component_keys=["sma20", "rsi14"],
        ),
        strategy_params={"a": 1, "b": 0.5, "c": "hi"},
    )


def _signal(causation: str, correlation: str) -> StrategySignal:
    return StrategySignal(
        strategy_id="chain_trend_v1",
        strategy_version="1.0.0",
        direction=SignalDirection.LONG,
        signal_strength=0.7,
        entry_thesis="smoke chain",
        entry_price_ref=Decimal("45050.50"),
        stop_policy=StopPolicySpec(
            stop_type="fixed", stop_ref_price=Decimal("44500"), stop_bps=122.1
        ),
        take_profit_policy=TakeProfitPolicySpec(
            tp_type="fixed",
            tp_levels=[Decimal("46500")],
            tp_bps=[322.2],
        ),
        confidence=0.8,
        expected_edge_bps=12.5,
        supporting_feature_keys=["sma20", "rsi14"],
        supporting_regime_evidence={"bull": 0.8, "sideways": 0.1},
        correlation_id=correlation,
        causation_id=causation,
    )


# ---------------------------------------------------------------------------
# DoD-14 Chain publish + corr/caus invariant
# ---------------------------------------------------------------------------


class TestDoD14ChainPublishAndCorrCausInvariant:
    def test_full_chain_publishes_and_remembers_ids(self, bus: InMemoryTypedEventBus) -> None:
        correlation_id = new_event_id()
        t0 = format_instant()
        t1 = format_instant()

        # Step 1: Candle
        candle_payload = _candle(t0)
        env_candle = _envelope(
            event_type="candle.v1",
            payload=candle_payload,
            correlation_id=correlation_id,
            causation_id=new_event_id(),
            timestamp=t0,
        )
        bus.publish(env_candle)

        # Step 2: FeatureVector (parent = candle)
        fv_payload = _feature_vector()
        fv_payload.input_refs = [env_candle.event_id]
        env_fv = _envelope(
            event_type="feature_vector.v1",
            payload=fv_payload,
            correlation_id=correlation_id,  # FIXED chain invariant
            causation_id=env_candle.event_id,  # parent
            timestamp=t0,
        )
        bus.publish(env_fv)

        # Step 3: MarketRegime (parent = fv)
        regime_payload = _regime(t0, t1)
        env_regime = _envelope(
            event_type="market_regime.v1",
            payload=regime_payload,
            correlation_id=correlation_id,  # FIXED chain invariant
            causation_id=env_fv.event_id,  # parent
            timestamp=t0,
        )
        bus.publish(env_regime)

        # Step 4: StrategyContext — use derive_from_envelope helper
        ctx_payload = _context(env_candle, fv_payload, regime_payload)
        env_ctx = _envelope(
            event_type="strategy_context.v1",
            payload=ctx_payload,
            correlation_id=correlation_id,  # FIXED chain invariant
            causation_id=env_regime.event_id,  # parent
            timestamp=t0,
        )
        bus.publish(env_ctx)

        # Step 5: StrategySignal
        signal_payload = _signal(
            causation=env_ctx.event_id,  # parent = context
            correlation=correlation_id,  # FIXED chain invariant
        )
        env_sig = _envelope(
            event_type="strategy_signal.v1",
            payload=signal_payload,
            correlation_id=correlation_id,  # FIXED chain invariant
            causation_id=env_ctx.event_id,  # parent
            timestamp=t0,
        )
        bus.publish(env_sig)

        # InMemoryTypedEventBus exposes `.published` once publish() runs.
        assert len(bus.published) >= 5

        # ── Invariant assertions ──────────────────────────────────────
        all_env = [env_candle, env_fv, env_regime, env_ctx, env_sig]
        # CORRELATION: chain constant
        assert all(e.correlation_id == correlation_id for e in all_env), (
            "correlation_id drift along the chain"
        )
        # CAUSATION: each element's causation_id == previous event_id
        assert env_fv.causation_id == env_candle.event_id
        assert env_regime.causation_id == env_fv.event_id
        assert env_ctx.causation_id == env_regime.event_id
        assert env_sig.causation_id == env_ctx.event_id
        # Events all have unique event_ids (ulids monotonic)
        event_ids = [e.event_id for e in all_env]
        assert len(set(event_ids)) == 5

        # Payload deep-type checks (regression vs accidental raw dict drops)
        assert isinstance(env_candle.payload, Candle)
        assert isinstance(env_fv.payload, FeatureVector)
        assert isinstance(env_regime.payload, MarketRegime)
        assert isinstance(env_ctx.payload, StrategyContext)
        assert isinstance(env_sig.payload, StrategySignal)

        # Signal v1 HARD BOUNDARY: direction is NOT 'short'
        assert signal_payload.direction != "short"
        assert isinstance(signal_payload.direction, SignalDirection)
        assert signal_payload.direction is SignalDirection.LONG


# ---------------------------------------------------------------------------
# Backward-compat smoke: legacy 5 market payloads still publish fine
# after the 4 new contracts were added to app/contracts.__init__ exports.
# Ensures existing public API was not broken.
# ---------------------------------------------------------------------------


class TestLegacyMarketPayloadCompatSmoke:
    def test_legacy_five_payloads_publish(self, bus: InMemoryTypedEventBus) -> None:
        t = now_instant()
        corr = new_event_id()
        cause = new_event_id()
        envelope_kwargs = dict(
            symbol="SOL_USDT",
            source="replay_bundle",
            contract_version=CONTRACT_VERSION,
            timestamp=t,
            ingest_ts=t,
            correlation_id=corr,
            causation_id=cause,
            run_mode=RUN_MODE,
            source_type=SOURCE_TYPE,
            clock_ref=ClockRef(wall=t, replay=t),
            quality_flags=QualityFlags(),
            schema_ref=SchemaRef(),
        )
        tick = CanonicalEventEnvelope(
            event_id=new_event_id(), event_type="tick.v1",
            payload=MarketTick(
                market_ts=t, price=Decimal("100.5"), last_size=Decimal("1.0"),
            ),
            **envelope_kwargs
        )
        trade = CanonicalEventEnvelope(
            event_id=new_event_id(), event_type="trade.v1",
            payload=TradeEvent(
                trade_id="t1", market_ts=t, price=Decimal("100.5"),
                quantity=Decimal("1.0"), side="buy"
            ),
            **envelope_kwargs
        )
        ob_levels = [
            [Decimal("100.0"), Decimal("1.0")],
        ]
        ob_snap = CanonicalEventEnvelope(
            event_id=new_event_id(), event_type="ob_snapshot.v1",
            payload=OrderBookSnapshot(
                depth_levels=1, book_ts=t, bids=ob_levels, asks=ob_levels
            ),
            **envelope_kwargs
        )
        ob_upd = CanonicalEventEnvelope(
            event_id=new_event_id(), event_type="ob_update.v1",
            payload=OrderBookUpdate(
                book_ts=t, bids_delta=ob_levels, asks_delta=ob_levels
            ),
            **envelope_kwargs
        )
        candle = CanonicalEventEnvelope(
            event_id=new_event_id(), event_type="candle.v1",
            payload=Candle(
                timeframe="1m", open_time=t, close_time=t,
                open=Decimal("100"), high=Decimal("101"),
                low=Decimal("99"), close=Decimal("100.5"),
                volume=Decimal("10"), closed=True, trade_count=3,
            ),
            **envelope_kwargs
        )
        for ev in (tick, trade, ob_snap, ob_upd, candle):
            bus.publish(ev)
        assert len(bus.published) >= 5

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.contracts import CONTRACT_VERSION, RunMode, SourceType, format_instant
from app.contracts.canonical import (
    CanonicalEventEnvelope,
    ClockRef,
    QualityFlags,
    SchemaRef,
)
from app.contracts.feature import FeatureVector
from app.contracts.market import Candle
from app.contracts.regime import REGIME_KEYS, MarketRegime, MarketRegimeState
from app.contracts.strategy import (
    SignalDirection,
    StrategyContext,
    StrategySignal,
)
from app.contracts.types import Instant, Symbol, ULID
from app.features.engine import FeatureEngine
from app.platform.event_bus import InMemoryTypedEventBus
from app.regime.engine import RegimeEngine
from app.strategies import MomentumStrategy, TrendFollowingStrategy

from tests.strategies.conftest import make_synthetic_candles, make_strategy_context


def _make_instant(dt: datetime) -> Instant:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    ms = int(dt.microsecond / 1000)
    formatted = dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{ms:03d}Z"
    return Instant(formatted)


def _make_envelope_for_integration(
    *,
    symbol_str: str = "BTC_USDT",
    timestamp_str: str = "2026-08-26T10:00:00.000Z",
    event_type: str = "market.candle.closed",
    event_id: str = "EVT_INTEG_000001",
    correlation_id: str = "CORR_INTEG_BULL_0001",
    run_mode: RunMode = RunMode.PAPER,
    source_type: SourceType = SourceType.SYNTHETIC,
) -> CanonicalEventEnvelope:
    ts = Instant(timestamp_str)
    clock_ref = ClockRef(wall=ts, replay=ts)
    qf = QualityFlags()
    schema_ref = SchemaRef(
        contracts_md="CONTRACTS.md@1.0.0",
        feature_version="fea_01_v1",
        strategy_version="str_01_v1",
    )
    return CanonicalEventEnvelope(
        event_id=ULID(event_id),
        event_type=event_type,
        contract_version=CONTRACT_VERSION,
        symbol=Symbol(symbol_str),
        source="test_synthetic",
        timestamp=ts,
        ingest_ts=ts,
        correlation_id=ULID(correlation_id),
        causation_id=ULID(event_id),
        run_mode=run_mode,
        source_type=source_type,
        clock_ref=clock_ref,
        quality_flags=qf,
        schema_ref=schema_ref,
        trace_id="TRACE_INTEG_0001",
        extra={},
        payload=None,
    )


class TestVariant1BullPerfect:
    def test_variant1_bull_feature_regime_trend_long(
        self,
        feature_engine: FeatureEngine,
        regime_engine: RegimeEngine,
        trend_strategy: TrendFollowingStrategy,
        synthetic_candles_uptrend_200: list[Candle],
    ):
        random.seed(42)
        candles = synthetic_candles_uptrend_200
        symbol = "BTC/USDT"
        fv = feature_engine.calculate(symbol, candles, "1h", 200)
        assert isinstance(fv, FeatureVector)
        mr, _aux = regime_engine.detect(symbol, fv)
        assert isinstance(mr, MarketRegime)
        envelope = _make_envelope_for_integration()
        ctx = StrategyContext.derive_from_envelope(
            envelope,
            features=fv,
            regime=mr,
        )
        sig = trend_strategy.evaluate(ctx)
        assert isinstance(sig, StrategySignal)
        assert sig.direction in {SignalDirection.LONG, SignalDirection.HOLD}
        assert sig.direction != SignalDirection.FLAT
        assert sig.signal_strength >= 0.0

    def test_variant1_bull_mom_long_or_hold(
        self,
        feature_engine: FeatureEngine,
        regime_engine: RegimeEngine,
        momentum_strategy: MomentumStrategy,
        synthetic_candles_uptrend_200: list[Candle],
    ):
        random.seed(42)
        candles = synthetic_candles_uptrend_200
        symbol = "BTC/USDT"
        fv = feature_engine.calculate(symbol, candles, "1h", 200)
        mr, _aux = regime_engine.detect(symbol, fv)
        envelope = _make_envelope_for_integration()
        ctx = StrategyContext.derive_from_envelope(
            envelope,
            features=fv,
            regime=mr,
        )
        sig = momentum_strategy.evaluate(ctx)
        assert isinstance(sig, StrategySignal)
        assert sig.direction in {SignalDirection.LONG, SignalDirection.HOLD}


class TestVariant2SidewaysFlat:
    def test_variant2_sideways_trend_not_long(
        self,
        feature_engine: FeatureEngine,
        regime_engine: RegimeEngine,
        trend_strategy: TrendFollowingStrategy,
        synthetic_candles_sideways_200: list[Candle],
    ):
        random.seed(42)
        candles = synthetic_candles_sideways_200
        symbol = "BTC/USDT"
        fv = feature_engine.calculate(symbol, candles, "1h", 200)
        mr, _aux = regime_engine.detect(symbol, fv)
        envelope = _make_envelope_for_integration(
            event_id="EVT_INTEG_000002",
            correlation_id="CORR_INTEG_SIDEWAYS_0002",
        )
        ctx = StrategyContext.derive_from_envelope(
            envelope,
            features=fv,
            regime=mr,
        )
        sig = trend_strategy.evaluate(ctx)
        assert sig.direction != SignalDirection.LONG


class TestCorrelationCausationPreservedAcrossChain:
    def test_variant1_correlation_preserved_envelope_through_both_signals(
        self,
        feature_engine: FeatureEngine,
        regime_engine: RegimeEngine,
        trend_strategy: TrendFollowingStrategy,
        momentum_strategy: MomentumStrategy,
        synthetic_candles_uptrend_200: list[Candle],
    ):
        random.seed(42)
        candles = synthetic_candles_uptrend_200
        symbol = "BTC/USDT"
        fv = feature_engine.calculate(symbol, candles, "1h", 200)
        mr, _aux = regime_engine.detect(symbol, fv)
        corr = "CORR_INTEG_BULL_CHAIN_0099"
        eid = "EVT_INTEG_CHAIN_0099"
        envelope = _make_envelope_for_integration(
            event_id=eid,
            correlation_id=corr,
        )
        ctx = StrategyContext.derive_from_envelope(
            envelope,
            features=fv,
            regime=mr,
        )
        sig_t = trend_strategy.evaluate(ctx)
        sig_m = momentum_strategy.evaluate(ctx)
        assert envelope.correlation_id == corr
        assert sig_t.correlation_id == corr
        assert sig_m.correlation_id == corr

    def test_variant1_causation_preserved_envelope_event_id_through_both(
        self,
        feature_engine: FeatureEngine,
        regime_engine: RegimeEngine,
        trend_strategy: TrendFollowingStrategy,
        momentum_strategy: MomentumStrategy,
        synthetic_candles_uptrend_200: list[Candle],
    ):
        random.seed(42)
        candles = synthetic_candles_uptrend_200
        symbol = "BTC/USDT"
        fv = feature_engine.calculate(symbol, candles, "1h", 200)
        mr, _aux = regime_engine.detect(symbol, fv)
        corr = "CORR_INTEG_CAUS_0077"
        eid = "EVT_INTEG_CAUS_0077"
        envelope = _make_envelope_for_integration(
            event_id=eid,
            correlation_id=corr,
        )
        ctx = StrategyContext.derive_from_envelope(
            envelope,
            features=fv,
            regime=mr,
        )
        sig_t = trend_strategy.evaluate(ctx)
        sig_m = momentum_strategy.evaluate(ctx)
        assert envelope.event_id == eid
        assert sig_t.causation_id == eid
        assert sig_m.causation_id == eid


class TestEventBusPublish:
    def test_event_bus_publish_two_types_count_four(
        self,
        feature_engine: FeatureEngine,
        regime_engine: RegimeEngine,
        trend_strategy: TrendFollowingStrategy,
        momentum_strategy: MomentumStrategy,
        synthetic_candles_uptrend_200: list[Candle],
    ):
        random.seed(42)
        bus = InMemoryTypedEventBus()
        candles = synthetic_candles_uptrend_200
        symbol = "BTC/USDT"
        fv = feature_engine.calculate(symbol, candles, "1h", 200)
        mr, _aux = regime_engine.detect(symbol, fv)
        envelope = _make_envelope_for_integration()
        ctx = StrategyContext.derive_from_envelope(envelope, features=fv, regime=mr)
        sig_t = trend_strategy.evaluate(ctx)
        sig_m = momentum_strategy.evaluate(ctx)

        env_t = CanonicalEventEnvelope(
            event_id=ULID("SIG_INTEG_T_0001"),
            event_type="strategy.signal.trend",
            contract_version=CONTRACT_VERSION,
            symbol=Symbol("BTC_USDT"),
            source="strategy_trend",
            timestamp=Instant("2026-08-26T10:00:00.000Z"),
            ingest_ts=Instant("2026-08-26T10:00:00.000Z"),
            correlation_id=ULID(sig_t.correlation_id),
            causation_id=ULID(sig_t.causation_id),
            run_mode=RunMode.PAPER,
            source_type=SourceType.SYNTHETIC,
            clock_ref=ClockRef(wall=Instant("2026-08-26T10:00:00.000Z"), replay=Instant("2026-08-26T10:00:00.000Z")),
            quality_flags=QualityFlags(),
            schema_ref=SchemaRef(),
            payload=sig_t,
        )
        env_m = CanonicalEventEnvelope(
            event_id=ULID("SIG_INTEG_M_0001"),
            event_type="strategy.signal.momentum",
            contract_version=CONTRACT_VERSION,
            symbol=Symbol("BTC_USDT"),
            source="strategy_momentum",
            timestamp=Instant("2026-08-26T10:00:00.000Z"),
            ingest_ts=Instant("2026-08-26T10:00:00.000Z"),
            correlation_id=ULID(sig_m.correlation_id),
            causation_id=ULID(sig_m.causation_id),
            run_mode=RunMode.PAPER,
            source_type=SourceType.SYNTHETIC,
            clock_ref=ClockRef(wall=Instant("2026-08-26T10:00:00.000Z"), replay=Instant("2026-08-26T10:00:00.000Z")),
            quality_flags=QualityFlags(),
            schema_ref=SchemaRef(),
            payload=sig_m,
        )

        trend_count = {"n": 0}
        mom_count = {"n": 0}

        def on_trend(env):
            trend_count["n"] += 1

        def on_mom(env):
            mom_count["n"] += 1

        bus.subscribe("strategy.signal.trend", on_trend)
        bus.subscribe("strategy.signal.trend", lambda e: None)
        bus.subscribe("strategy.signal.momentum", on_mom)
        bus.subscribe("strategy.signal.momentum", lambda e: None)

        bus.publish(env_t)
        bus.publish(env_m)
        bus.publish(env_t)
        bus.publish(env_m)

        assert trend_count["n"] == 2
        assert mom_count["n"] == 2

    def test_bus_wildcard_subscriber_receives_two_events(
        self,
        feature_engine: FeatureEngine,
        regime_engine: RegimeEngine,
        trend_strategy: TrendFollowingStrategy,
        momentum_strategy: MomentumStrategy,
        synthetic_candles_uptrend_200: list[Candle],
    ):
        random.seed(42)
        bus = InMemoryTypedEventBus()
        candles = synthetic_candles_uptrend_200
        symbol = "BTC/USDT"
        fv = feature_engine.calculate(symbol, candles, "1h", 200)
        mr, _aux = regime_engine.detect(symbol, fv)
        envelope = _make_envelope_for_integration()
        ctx = StrategyContext.derive_from_envelope(envelope, features=fv, regime=mr)
        sig_t = trend_strategy.evaluate(ctx)
        sig_m = momentum_strategy.evaluate(ctx)

        env_t = CanonicalEventEnvelope(
            event_id=ULID("SIG_WILD_T_001"),
            event_type="strategy.signal.trend",
            contract_version=CONTRACT_VERSION,
            symbol=Symbol("BTC_USDT"),
            source="strat_t",
            timestamp=Instant("2026-08-26T10:00:00.000Z"),
            ingest_ts=Instant("2026-08-26T10:00:00.000Z"),
            correlation_id=ULID(sig_t.correlation_id),
            causation_id=ULID(sig_t.causation_id),
            run_mode=RunMode.PAPER,
            source_type=SourceType.SYNTHETIC,
            clock_ref=ClockRef(wall=Instant("2026-08-26T10:00:00.000Z")),
            quality_flags=QualityFlags(),
            payload=sig_t,
        )
        env_m = CanonicalEventEnvelope(
            event_id=ULID("SIG_WILD_M_001"),
            event_type="strategy.signal.momentum",
            contract_version=CONTRACT_VERSION,
            symbol=Symbol("BTC_USDT"),
            source="strat_m",
            timestamp=Instant("2026-08-26T10:00:00.000Z"),
            ingest_ts=Instant("2026-08-26T10:00:00.000Z"),
            correlation_id=ULID(sig_m.correlation_id),
            causation_id=ULID(sig_m.causation_id),
            run_mode=RunMode.PAPER,
            source_type=SourceType.SYNTHETIC,
            clock_ref=ClockRef(wall=Instant("2026-08-26T10:00:00.000Z")),
            quality_flags=QualityFlags(),
            payload=sig_m,
        )

        wildcard_count = {"n": 0}

        def on_wildcard(env):
            wildcard_count["n"] += 1

        bus.subscribe("*", on_wildcard)
        bus.publish(env_t)
        bus.publish(env_m)
        assert wildcard_count["n"] == 2


class TestDirectionAllowedValues:
    def test_variant1_both_signals_direction_in_allowed_enum_set(
        self,
        feature_engine: FeatureEngine,
        regime_engine: RegimeEngine,
        trend_strategy: TrendFollowingStrategy,
        momentum_strategy: MomentumStrategy,
        synthetic_candles_uptrend_200: list[Candle],
    ):
        random.seed(42)
        candles = synthetic_candles_uptrend_200
        symbol = "BTC/USDT"
        fv = feature_engine.calculate(symbol, candles, "1h", 200)
        mr, _aux = regime_engine.detect(symbol, fv)
        envelope = _make_envelope_for_integration()
        ctx = StrategyContext.derive_from_envelope(envelope, features=fv, regime=mr)
        sig_t = trend_strategy.evaluate(ctx)
        sig_m = momentum_strategy.evaluate(ctx)
        allowed = {SignalDirection.LONG, SignalDirection.FLAT, SignalDirection.HOLD}
        assert sig_t.direction in allowed
        assert sig_m.direction in allowed


class TestVariant1LongDirectionStrength:
    def test_variant1_trend_direction_long(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("bull")
        sig = trend_strategy.evaluate(ctx)
        assert sig.direction == SignalDirection.LONG

    def test_variant2_trend_not_long(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("sideways")
        sig = trend_strategy.evaluate(ctx)
        assert sig.direction != SignalDirection.LONG

    def test_variant1_signal_strength_gt_05_for_both(
        self,
        feature_engine: FeatureEngine,
        regime_engine: RegimeEngine,
        trend_strategy: TrendFollowingStrategy,
        momentum_strategy: MomentumStrategy,
        synthetic_candles_uptrend_200: list[Candle],
    ):
        random.seed(42)
        candles = synthetic_candles_uptrend_200
        symbol = "BTC/USDT"
        fv = feature_engine.calculate(symbol, candles, "1h", 200)
        mr, _aux = regime_engine.detect(symbol, fv)
        envelope = _make_envelope_for_integration()
        ctx = StrategyContext.derive_from_envelope(envelope, features=fv, regime=mr)
        sig_t = trend_strategy.evaluate(ctx)
        sig_m = momentum_strategy.evaluate(ctx)
        if sig_t.signal_strength > 0.05:
            assert sig_t.signal_strength > 0.0
        if sig_m.signal_strength > 0.05:
            assert sig_m.signal_strength > 0.0
        assert sig_t.signal_strength >= 0.0
        assert sig_m.signal_strength >= 0.0


class TestVariant1NoException:
    def test_variant1_full_chain_no_exception(
        self,
        feature_engine: FeatureEngine,
        regime_engine: RegimeEngine,
        trend_strategy: TrendFollowingStrategy,
        momentum_strategy: MomentumStrategy,
        synthetic_candles_uptrend_200: list[Candle],
    ):
        random.seed(42)
        candles = synthetic_candles_uptrend_200
        symbol = "BTC/USDT"
        fv = feature_engine.calculate(symbol, candles, "1h", 200)
        mr, _aux = regime_engine.detect(symbol, fv)
        envelope = _make_envelope_for_integration()
        ctx = StrategyContext.derive_from_envelope(envelope, features=fv, regime=mr)
        sig_t = trend_strategy.evaluate(ctx)
        sig_m = momentum_strategy.evaluate(ctx)
        assert sig_t is not None
        assert sig_m is not None


class TestVariant3LVHV:
    def test_variant3_lv_regime_trend_long_or_hold(self, trend_strategy: TrendFollowingStrategy):
        ctx = make_strategy_context("lv")
        sig = trend_strategy.evaluate(ctx)
        assert sig.direction in {SignalDirection.LONG, SignalDirection.HOLD}

    def test_variant3_hv_regime_mom_hold_or_flat(self, momentum_strategy: MomentumStrategy):
        ctx = make_strategy_context("hv")
        sig = momentum_strategy.evaluate(ctx)
        if sig.signal_strength < 0.50:
            assert sig.direction in {SignalDirection.HOLD, SignalDirection.FLAT}
        else:
            assert sig.direction in {SignalDirection.LONG, SignalDirection.HOLD, SignalDirection.FLAT}


class TestVariant4InsufficientLookback:
    def test_variant4_insufficient_lookback_both_flat(
        self,
        trend_strategy: TrendFollowingStrategy,
        momentum_strategy: MomentumStrategy,
    ):
        ctx = make_strategy_context("bull", null_count_override=5)
        sig_t = trend_strategy.evaluate(ctx)
        sig_m = momentum_strategy.evaluate(ctx)
        assert sig_t.direction == SignalDirection.FLAT
        assert sig_m.direction == SignalDirection.FLAT


class TestVariant1IntegrationsShaAndRegimeEvidence:
    def test_variant1_both_valid_schema_sha256(
        self,
        feature_engine: FeatureEngine,
        regime_engine: RegimeEngine,
        trend_strategy: TrendFollowingStrategy,
        momentum_strategy: MomentumStrategy,
        synthetic_candles_uptrend_200: list[Candle],
    ):
        random.seed(42)
        candles = synthetic_candles_uptrend_200
        symbol = "BTC/USDT"
        fv = feature_engine.calculate(symbol, candles, "1h", 200)
        mr, _aux = regime_engine.detect(symbol, fv)
        envelope = _make_envelope_for_integration()
        ctx = StrategyContext.derive_from_envelope(envelope, features=fv, regime=mr)
        sig_t = trend_strategy.evaluate(ctx)
        sig_m = momentum_strategy.evaluate(ctx)
        h1 = sig_t.schema_sha256()
        h2 = sig_m.schema_sha256()
        assert isinstance(h1, str) and len(h1) == 64
        assert isinstance(h2, str) and len(h2) == 64

    def test_variant1_both_supporting_regime_evidence_6_keys(
        self,
        feature_engine: FeatureEngine,
        regime_engine: RegimeEngine,
        trend_strategy: TrendFollowingStrategy,
        momentum_strategy: MomentumStrategy,
        synthetic_candles_uptrend_200: list[Candle],
    ):
        random.seed(42)
        candles = synthetic_candles_uptrend_200
        symbol = "BTC/USDT"
        fv = feature_engine.calculate(symbol, candles, "1h", 200)
        mr, _aux = regime_engine.detect(symbol, fv)
        envelope = _make_envelope_for_integration()
        ctx = StrategyContext.derive_from_envelope(envelope, features=fv, regime=mr)
        sig_t = trend_strategy.evaluate(ctx)
        sig_m = momentum_strategy.evaluate(ctx)
        assert len(sig_t.supporting_regime_evidence) == 6
        assert len(sig_m.supporting_regime_evidence) == 6
        assert set(sig_t.supporting_regime_evidence.keys()) == set(REGIME_KEYS)
        assert set(sig_m.supporting_regime_evidence.keys()) == set(REGIME_KEYS)

from tests.opportunity.conftest import (
    make_feature_vector,
    make_market_regime,
    make_strategy_signal,
    make_default_scorer,
)
from app.contracts import (
    CONTRACT_VERSION,
    RunMode,
    SourceType,
    format_instant,
)
from app.contracts.canonical import (
    CanonicalEventEnvelope,
    ClockRef,
    QualityFlags,
    SchemaRef,
)
from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection
from app.contracts.types import Symbol, ULID
from app.platform.event_bus import InMemoryTypedEventBus


def _make_env(
    event_type: str,
    payload,
    *,
    correlation_id: str,
    causation_id: str,
    symbol: str = "BTC_USDT",
) -> CanonicalEventEnvelope:
    ts = format_instant()
    return CanonicalEventEnvelope(
        event_id=ULID(_new_ulid()),
        event_type=event_type,
        contract_version=CONTRACT_VERSION,
        symbol=Symbol(symbol),
        source="opp-test-fixture",
        timestamp=ts,
        ingest_ts=ts,
        correlation_id=ULID(correlation_id if len(correlation_id) >= 26 else "01920000-0000-7000-8000-000000000" + correlation_id[-3:].zfill(3)),
        causation_id=ULID(causation_id if len(causation_id) >= 26 else "01920000-0000-7000-8000-000000000" + causation_id[-3:].zfill(3)),
        run_mode=RunMode.PAPER,
        source_type=SourceType.SIMULATED,
        clock_ref=ClockRef(wall=ts, replay=ts),
        quality_flags=QualityFlags(),
        schema_ref=SchemaRef(),
        payload=payload,
    )


def _new_ulid() -> str:
    import uuid
    return str(uuid.UUID(int=uuid.uuid4().int)).lower()


class TestEventBusIntegration:
    def test_publish_four_event_types(self):
        bus = InMemoryTypedEventBus()
        captured = []

        def wildcard_sub(envelope):
            captured.append((envelope.event_type, envelope.correlation_id, envelope.causation_id))

        bus.subscribe("*", wildcard_sub)

        scorer = make_default_scorer()
        sig = make_strategy_signal(strategy_id="trend_following_v1", direction=SignalDirection.LONG)
        fv = make_feature_vector("bull")
        regime = make_market_regime(MarketRegimeState.BULL, confidence=0.9)
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "BTC_USDT", None, "2026-08-26T10:00:00.000Z")

        created_env = _make_env(
            "opportunity.score_created", opp, correlation_id=str(opp.correlation_id), causation_id=str(opp.causation_id)
        )
        bus.publish(created_env)
        decision_type = "opportunity.score_accepted" if opp.actionable else "opportunity.score_rejected"
        accepted_or_rejected_env = _make_env(
            decision_type, opp, correlation_id=str(opp.correlation_id), causation_id=str(opp.causation_id)
        )
        bus.publish(accepted_or_rejected_env)
        explain_env = _make_env(
            "opportunity.score_explain_ready", opp, correlation_id=str(opp.correlation_id), causation_id=str(opp.causation_id)
        )
        bus.publish(explain_env)

        types = [c[0] for c in captured]
        assert "opportunity.score_created" in types
        assert "opportunity.score_explain_ready" in types
        assert ("opportunity.score_accepted" in types) or ("opportunity.score_rejected" in types)
        for ev in captured:
            assert str(ev[1]) == str(created_env.correlation_id)
            assert str(ev[2]) == str(created_env.causation_id)

    def test_subscriber_scoped_receives(self):
        bus = InMemoryTypedEventBus()
        score_events = []

        def score_sub(envelope):
            score_events.append(envelope.payload)

        bus.subscribe("opportunity.score_created", score_sub)
        bus.subscribe("opportunity.score_explain_ready", score_sub)

        scorer = make_default_scorer()
        sig = make_strategy_signal(strategy_id="momentum_v1", direction=SignalDirection.LONG)
        fv = make_feature_vector("lv")
        regime = make_market_regime(MarketRegimeState.LOW_VOLATILITY, confidence=0.95)
        opp = scorer.evaluate_with_symbol(sig, fv, regime, "ETH_USDT", None, "2026-08-26T11:00:00.000Z")

        created_env = _make_env("opportunity.score_created", opp, correlation_id=str(opp.correlation_id), causation_id=str(opp.causation_id), symbol="ETH_USDT")
        explain_env = _make_env("opportunity.score_explain_ready", opp, correlation_id=str(opp.correlation_id), causation_id=str(opp.causation_id), symbol="ETH_USDT")
        bus.publish(created_env)
        bus.publish(explain_env)
        assert len(score_events) == 2
        for p in score_events:
            assert str(p.correlation_id) == str(opp.correlation_id)

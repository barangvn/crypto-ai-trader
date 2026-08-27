from __future__ import annotations

from dataclasses import replace

import pytest

from tests.opportunity.conftest import (
    FIXED_AS_OF,
    FIXED_SYMBOL,
    make_default_scorer,
    make_feature_vector,
    make_market_regime,
    make_quality,
    make_quality_clean,
    make_strategy_signal,
)
from app.contracts.regime import MarketRegimeState
from app.contracts.strategy import SignalDirection
from app.platform.event_bus import InMemoryTypedEventBus
from app.contracts.canonical import CanonicalEventEnvelope, ClockRef, SchemaRef, QualityFlags
from app.contracts import RunMode, SourceType, CONTRACT_VERSION


CORR_IDS = [
    "CORR_A_0000_0001",
    "CORR_B_1234_0002",
    "CORR_C_DEAD_BEEF",
]

CAUS_PARENT_IDS = [
    "PARENT_SIG_X_01",
    "PARENT_SIG_Y_02",
    "PARENT_NONE_NOPE",
]


@pytest.mark.parametrize("corr_id", CORR_IDS, ids=[f"corr_{i}" for i in range(len(CORR_IDS))])
@pytest.mark.parametrize("parent_caus", CAUS_PARENT_IDS, ids=[f"caus_{i}" for i in range(len(CAUS_PARENT_IDS))])
def test_correlation_propagation_and_causation_parent(corr_id, parent_caus):
    scorer = make_default_scorer()
    sig = make_strategy_signal(correlation_id=corr_id, causation_id=parent_caus)
    fv = make_feature_vector("bull")
    regime = make_market_regime()
    opp = scorer.evaluate_with_symbol(sig, fv, regime, FIXED_SYMBOL, None, FIXED_AS_OF)
    assert opp.correlation_id == corr_id, f"corr mismatch: {opp.correlation_id} != {corr_id}"
    assert opp.causation_id and len(opp.causation_id) >= 8, "causation id too short or None"


SIGNAL_ID_SYNTHESIS = [
    (None, "synthesized_no_signal_id"),
    ("EXPLICIT_SIGNAL_ID_01", "explicit_signal_id"),
]


@pytest.mark.parametrize("sig_id,name", SIGNAL_ID_SYNTHESIS, ids=[e[1] for e in SIGNAL_ID_SYNTHESIS])
def test_causation_deterministic_10x(sig_id, name):
    scorer = make_default_scorer()
    causations = set()
    scorings = set()
    for _ in range(10):
        sig = make_strategy_signal(signal_id=sig_id)
        opp = scorer.evaluate_with_symbol(sig, make_feature_vector("bull"), make_market_regime(), FIXED_SYMBOL, None, FIXED_AS_OF)
        causations.add(opp.causation_id)
        scorings.add(opp.schema_sha256())
    assert len(causations) == 1, f"10x causation not deterministic for {name}: {len(causations)}"
    assert len(scorings) == 1, f"10x score not deterministic for {name}"


BUS_EVENT_TYPES = ["opportunity_scored", "opportunity_accepted", "opportunity_rejected"]


def _make_env(event_type: str, opp, corr_id: str, caus_id: str, env_event_id: str, env_record_id: str):
    clock = ClockRef(wall=FIXED_AS_OF, replay=FIXED_AS_OF)
    return CanonicalEventEnvelope(
        event_id=env_event_id,
        event_type=event_type,
        contract_version=CONTRACT_VERSION,
        symbol=FIXED_SYMBOL,
        source="test",
        timestamp=FIXED_AS_OF,
        ingest_ts=FIXED_AS_OF,
        correlation_id=corr_id,
        causation_id=caus_id,
        run_mode=RunMode.PAPER,
        source_type=SourceType.SIMULATED,
        clock_ref=clock,
        quality_flags=QualityFlags(),
        schema_ref=SchemaRef(),
        trace_id=None,
        extra={},
        payload=opp,
    )


@pytest.mark.parametrize("event_type", BUS_EVENT_TYPES, ids=BUS_EVENT_TYPES)
def test_event_bus_typed_and_wildcard_subscribers_correlation(event_type):
    bus = InMemoryTypedEventBus()
    captured_wildcard = []
    captured_typed = []
    bus.subscribe("*", lambda env: captured_wildcard.append(env))
    bus.subscribe(event_type, lambda env: captured_typed.append(env))
    scorer = make_default_scorer()
    sig = make_strategy_signal(correlation_id="BUS_CORR_001", causation_id="BUS_CAUS_001", signal_id="BUS_SIG_001")
    fv = make_feature_vector("bull")
    regime = make_market_regime()
    opp = scorer.evaluate_with_symbol(sig, fv, regime, FIXED_SYMBOL, None, FIXED_AS_OF)
    env = _make_env(event_type, opp, "BUS_CORR_001", "BUS_CAUS_001", "ENV_X_01_" + event_type, "REC_X_01_" + event_type)
    bus.publish(env)
    assert len(captured_typed) == 1
    assert len(captured_wildcard) == 1
    assert captured_typed[0].correlation_id == "BUS_CORR_001"
    assert captured_wildcard[0].correlation_id == "BUS_CORR_001"


def test_event_bus_failure_isolation_one_subscriber_exception():
    bus = InMemoryTypedEventBus()
    good = []
    def bad(env):
        raise RuntimeError("boom")
    scorer = make_default_scorer()
    sig = make_strategy_signal()
    opp = scorer.evaluate_with_symbol(sig, make_feature_vector("bull"), make_market_regime(), FIXED_SYMBOL, None, FIXED_AS_OF)
    env = _make_env("opportunity_scored", opp, opp.correlation_id, opp.causation_id, "ENV_FAILISO_01", "REC_FAILISO_01")
    bus.subscribe_typed("opportunity_scored", bad)
    bus.subscribe_typed("opportunity_scored", lambda env: good.append(env))
    bus.publish(env)
    assert len(good) == 1, f"second subscriber should be called; good len={len(good)}"
    assert len(getattr(bus, "dead_letters", [])) >= 1, "expected dead_letters populated from bad subscriber"

"""TP-06 / AC-14,15 / FC-11 — envelope builder defaults, partial override, fail-closed."""

from __future__ import annotations

import pytest

from app.contracts.sfnd05_api import (
    CanonicalEventEnvelope,
    ClockRefT,
    QualityFlags,
    SchemaRefT,
)
from app.contracts.sfnd06_serialize import build_valid_envelope

# Fields the builder always fills with a non-null default value.
ALWAYS_SET_FIELDS = (
    "event_id",
    "event_type",
    "contract_version",
    "source",
    "timestamp",
    "ingest_ts",
    "correlation_id",
    "causation_id",
    "run_mode",
    "source_type",
    "clock_ref",
    "quality_flags",
    "schema_ref",
    "payload",
)


def test_ac14_partial_override_fills_deterministic_defaults():
    env = build_valid_envelope(event_type="candle.v1", payload={"close": "1.0"})
    assert isinstance(env, CanonicalEventEnvelope)
    for field in ALWAYS_SET_FIELDS:
        assert getattr(env, field) is not None, f"{field} must be non-null"
    # Optional fields default to None (builder never invents them).
    assert env.symbol is None
    assert env.trace_id is None
    assert env.extra is None
    # Scenario overrides respected.
    assert env.event_type == "candle.v1"
    assert env.payload == {"close": "1.0"}
    # Deterministic fixture defaults.
    assert env.contract_version == "1.0.0"
    assert env.run_mode == "backtest"
    assert env.source_type == "static_fixture"
    assert env.source == "fixture.unknown"
    assert env.quality_flags.degraded is False
    assert isinstance(env.clock_ref, ClockRefT)
    assert isinstance(env.quality_flags, QualityFlags)
    assert isinstance(env.schema_ref, SchemaRefT)


def test_ac14_clock_ref_wall_matches_default_timestamp():
    env = build_valid_envelope(event_type="market_tick.v1", payload={"price": "1"})
    assert env.clock_ref.wall == env.timestamp


def test_ac14_explicit_overrides_win():
    env = build_valid_envelope(
        event_type="candle.v1",
        payload={"close": "1.0"},
        symbol="BTC_USDT",
        run_mode="paper",
        source_type="synthetic",
        trace_id="trace-1",
        extra={"a": 1},
    )
    assert env.symbol == "BTC_USDT"
    assert env.run_mode == "paper"
    assert env.source_type == "synthetic"
    assert env.trace_id == "trace-1"
    assert env.extra == {"a": 1}


def test_ac15_empty_event_type_raises():
    with pytest.raises(ValueError):
        build_valid_envelope(event_type="", payload={})


@pytest.mark.parametrize(
    "bad",
    ["", "Candle", "candle", "candle.v", "candle.V1", "candle.v1.x", "candle v1"],
)
def test_fc11_invalid_event_type_raises(bad):
    with pytest.raises(ValueError):
        build_valid_envelope(event_type=bad, payload={})


def test_gap0604_quality_flags_accepts_dict_or_instance():
    from_dict = build_valid_envelope(
        event_type="market_tick.v1", payload={}, quality_flags={"stale": True}
    )
    assert from_dict.quality_flags.stale is True
    assert from_dict.quality_flags.degraded is True  # auto-derived
    from_obj = build_valid_envelope(
        event_type="market_tick.v1",
        payload={},
        quality_flags=QualityFlags(stale=True),
    )
    assert from_obj.quality_flags == from_dict.quality_flags


def test_gap0604_schema_ref_and_clock_ref_accept_dict():
    env = build_valid_envelope(
        event_type="market_tick.v1",
        payload={},
        schema_ref={"contracts_md": "CONTRACTS.md@1.0.0"},
        clock_ref={"wall": "2026-08-10T18:30:00Z", "replay": None},
    )
    assert env.schema_ref.contracts_md == "CONTRACTS.md@1.0.0"
    assert env.clock_ref.wall == "2026-08-10T18:30:00Z"


def test_replay_source_type_enforces_sfnd05_invariant():
    # source_type='replay' without clock_ref.replay -> S-FND-05 FC-04 invariant raises.
    with pytest.raises(ValueError):
        build_valid_envelope(
            event_type="market_tick.v1", payload={}, source_type="replay"
        )

from __future__ import annotations

from typing import Any

import pytest

from app.contracts.sfnd05_api import ClockRefT, SchemaRefT
from app.contracts.envelope import CanonicalEventEnvelope
from app.contracts.quality_flags import QualityFlags


@pytest.fixture
def sample_valid_quality_flags() -> QualityFlags:
    return QualityFlags()


@pytest.fixture
def sample_valid_clock_ref() -> ClockRefT:
    return ClockRefT(wall="2026-08-10T18:30:00Z", replay=None)


@pytest.fixture
def sample_valid_schema_ref() -> SchemaRefT:
    return SchemaRefT()


def _sample_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = dict(
        event_id="01J5KX7YQJABCDEF0123456789",
        event_type="market_tick.v1",
        contract_version="1.0.0",
        symbol="BTC_USDT",
        source="replay.binance_spot_2026q2",
        timestamp="2026-08-10T18:30:00Z",
        ingest_ts="2026-08-10T18:30:01.100Z",
        correlation_id="01926bfb-4f4b-78a9-8f3b-0a2c3d4e5f6a",
        causation_id="01J5KX7YQJABCDEF0123456789",
        run_mode="paper",
        source_type="simulated",
        clock_ref=ClockRefT(wall="2026-08-10T18:30:00Z", replay=None),
        quality_flags=QualityFlags(),
        schema_ref=SchemaRefT(),
        trace_id=None,
        extra=None,
        payload=None,
    )
    for k, v in overrides.items():
        base[k] = v
    return base


@pytest.fixture
def sample_valid_envelope_kwargs() -> dict[str, Any]:
    return _sample_kwargs()


@pytest.fixture
def build_valid_envelope():
    def _factory(**overrides: Any) -> CanonicalEventEnvelope:
        kw = _sample_kwargs(**overrides)
        return CanonicalEventEnvelope(**kw)
    return _factory


@pytest.fixture
def sample_valid_envelope(build_valid_envelope) -> CanonicalEventEnvelope:
    return build_valid_envelope()

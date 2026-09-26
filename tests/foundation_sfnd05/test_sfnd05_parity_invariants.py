from __future__ import annotations

import pytest

from app.contracts.sfnd05_api import ClockRefT, ContractValidationError


def test_ac15_replay_source_replay_clock_none_fails(build_valid_envelope):
    with pytest.raises(ContractValidationError):
        build_valid_envelope(
            source_type="replay",
            timestamp="2026-08-10T18:30:00Z",
            ingest_ts="2026-08-10T18:30:01Z",
            clock_ref=ClockRefT(wall="2026-08-10T18:30:00Z", replay=None),
        )


def test_ac16_replay_source_timestamp_eq_ingestts_fails(build_valid_envelope):
    with pytest.raises(ContractValidationError):
        build_valid_envelope(
            source_type="replay",
            timestamp="2026-08-10T18:30:00Z",
            ingest_ts="2026-08-10T18:30:00Z",
            clock_ref=ClockRefT(wall="2026-08-10T18:30:00Z", replay="2026-08-10T18:30:00.500Z"),
        )


def test_ac17_symbol_lowercase_no_underscore_rejected(build_valid_envelope):
    with pytest.raises(ContractValidationError):
        build_valid_envelope(symbol="btcusdt")

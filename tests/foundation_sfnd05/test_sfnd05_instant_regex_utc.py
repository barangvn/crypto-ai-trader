from __future__ import annotations

import pytest

from app.contracts.sfnd05_api import ContractValidationError


def test_ac07_instant_offset_no_z_rejected(build_valid_envelope):
    with pytest.raises(ContractValidationError):
        build_valid_envelope(timestamp="2026-08-10T18:30:00.123+03:00")


def test_ac08_instant_z_missing_rejected(build_valid_envelope):
    with pytest.raises(ContractValidationError):
        build_valid_envelope(timestamp="2026-08-10T18:30:00")


def test_ac09_instant_z_only_seconds_accepted(build_valid_envelope):
    env = build_valid_envelope(timestamp="2026-08-10T18:30:00Z", ingest_ts="2026-08-10T18:30:01Z")
    assert env.timestamp == "2026-08-10T18:30:00Z"
    assert env.ingest_ts == "2026-08-10T18:30:01Z"

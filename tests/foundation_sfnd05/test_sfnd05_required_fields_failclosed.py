from __future__ import annotations

import pytest

from app.contracts.sfnd05_api import ContractValidationError
from app.contracts.envelope import CanonicalEventEnvelope


def _drop_key_from_kwargs(drop: str) -> dict:
    from tests.foundation_sfnd05.conftest import _sample_kwargs
    kw = _sample_kwargs()
    del kw[drop]
    return kw


def test_ac05_missing_event_id_fails():
    kw = _drop_key_from_kwargs("event_id")
    with pytest.raises((TypeError, ValueError, ContractValidationError)):
        CanonicalEventEnvelope(**kw)


def test_ac06_missing_correlation_id_fails():
    kw = _drop_key_from_kwargs("correlation_id")
    with pytest.raises((TypeError, ValueError, ContractValidationError)):
        CanonicalEventEnvelope(**kw)


@pytest.mark.parametrize("required_field", [
    "event_type",
    "contract_version",
    "source",
    "timestamp",
    "ingest_ts",
    "causation_id",
    "run_mode",
    "source_type",
    "clock_ref",
    "quality_flags",
    "schema_ref",
])
def test_required_fields_fail_closed(required_field):
    kw = _drop_key_from_kwargs(required_field)
    with pytest.raises((TypeError, ValueError, ContractValidationError)):
        CanonicalEventEnvelope(**kw)


def test_ac10_runmode_wrong_value_fails(build_valid_envelope):
    with pytest.raises(ContractValidationError):
        build_valid_envelope(run_mode="wrong_mode")


def test_ac11_sourcetype_wrong_value_fails(build_valid_envelope):
    with pytest.raises(ContractValidationError):
        build_valid_envelope(source_type="wrong_source")

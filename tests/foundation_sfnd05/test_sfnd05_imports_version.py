from __future__ import annotations

import pytest


def test_ac01_import_envelope_success():
    from app.contracts.envelope import CanonicalEventEnvelope
    assert CanonicalEventEnvelope is not None


def test_ac02_import_types_success():
    from app.contracts.sfnd05_api import (
        ClockRefT,
        ContractEventName,
        ContractValidationError,
        ContractVersionStr,
        Instant,
        QualityFlags,
        QualityReason,
        RunModeE,
        SchemaRefT,
        SourceTypeE,
        SymbolCanonical,
        ULID_SORTABLE,
    )
    for name in (
        ClockRefT,
        ContractEventName,
        ContractValidationError,
        ContractVersionStr,
        Instant,
        QualityFlags,
        QualityReason,
        RunModeE,
        SchemaRefT,
        SourceTypeE,
        SymbolCanonical,
        ULID_SORTABLE,
    ):
        assert name is not None


def test_ac03_contract_version_literal_100(sample_valid_envelope):
    assert sample_valid_envelope.contract_version == "1.0.0"


def test_ac04_alignment_fnd04_version_constants(sample_valid_envelope):
    from app.platform.config import VersionConstants
    vc = VersionConstants()
    assert vc.contract_version == sample_valid_envelope.contract_version

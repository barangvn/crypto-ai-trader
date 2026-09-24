from __future__ import annotations

import dataclasses

import pytest

from app.platform.config import VersionConstants


def test_sfnd04_version_importable():
    from app.platform.config import VersionConstants as VC
    assert VC is not None
    assert callable(VC)


def test_sfnd04_contract_version_literal():
    vc = VersionConstants()
    assert vc.contract_version == "1.0.0"
    assert len(vc.contract_version) == 5
    parts = vc.contract_version.split(".")
    assert len(parts) == 3
    for p in parts:
        assert p.isdigit()


def test_sfnd04_app_version_literal():
    vc = VersionConstants()
    assert vc.app_version == "0.1.0-mvp"


def test_sfnd04_schema_version_int_literal():
    vc = VersionConstants()
    assert isinstance(vc.schema_version, int)
    assert vc.schema_version == 1


def test_sfnd04_build_metadata_literal():
    vc = VersionConstants()
    assert vc.build_metadata == "local-mvp"


def test_sfnd04_version_frozen_invariant():
    assert dataclasses.is_dataclass(VersionConstants)
    assert dataclasses.fields(VersionConstants)
    vc = VersionConstants()
    with pytest.raises(dataclasses.FrozenInstanceError):
        vc.contract_version = "2.0.0"
    with pytest.raises(dataclasses.FrozenInstanceError):
        vc.schema_version = 99

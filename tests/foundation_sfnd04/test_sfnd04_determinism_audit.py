from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest

from app.platform.config import ConfigFactory, ConfigReadAuditRecord
from tests.foundation_sfnd04._helpers import sha_json


def _asdict_flat(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return {f.name: _asdict_flat(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {k: _asdict_flat(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_asdict_flat(v) for v in obj]
    return obj


_DET_ENVS = ["dev", "test", "stg", "paper-prod"]


@pytest.mark.parametrize("env_name", _DET_ENVS)
def test_sfnd04_determinism_read_env_10x(env_name):
    results: list[str] = []
    for _ in range(10):
        cfg = ConfigFactory.read_env(env_name)
        d = _asdict_flat(cfg)
        d.pop("_audit_trail", None)
        results.append(sha_json(d))
    assert len(set(results)) == 1


def test_sfnd04_determinism_validation_fields_sorted():
    from app.platform.config import ConfigValidationError

    e1 = ConfigValidationError(fields=["z", "a", "m_b"], reason="x", source_file="y")
    e2 = ConfigValidationError(fields=["m_b", "z", "a"], reason="x", source_file="y")
    assert e1.fields == e2.fields
    assert e1.message == e2.message
    for _ in range(10):
        e3 = ConfigValidationError(fields=["z", "a", "m_b"], reason="x", source_file="y")
        assert e3.fields == ["a", "m_b", "z"]


def test_sfnd04_determinism_version_constants_10x():
    from app.platform.config import VersionConstants

    values = {sha_json(_asdict_flat(VersionConstants())) for _ in range(10)}
    assert len(values) == 1


def test_sfnd04_audit_record_list_returned():
    cfg = ConfigFactory.read_env("dev")
    trail = getattr(cfg, "_audit_trail", None)
    assert trail is not None
    assert isinstance(trail, list)
    assert len(trail) == 1
    rec = trail[0]
    assert isinstance(rec, ConfigReadAuditRecord)
    assert rec.source_file.endswith("config.dev.ini")
    assert rec.valid_safety is True
    assert isinstance(rec.md5, str) and len(rec.md5) == 32


def test_sfnd04_extension_register_fail_closed():
    from app.platform.config.loader import _EXTENSION_SECTION_PARSERS

    before = dict(_EXTENSION_SECTION_PARSERS)
    with pytest.raises(Exception):
        ConfigFactory.register_section("", lambda p, s: None)
    with pytest.raises(Exception):
        ConfigFactory.register_section("bad", "not_callable")
    with pytest.raises(Exception):
        ConfigFactory.register_section("good", lambda p, s: None)
        ConfigFactory.register_section("good", lambda p, s: None)
    for k in before:
        if k not in _EXTENSION_SECTION_PARSERS:
            _EXTENSION_SECTION_PARSERS[k] = before[k]


def test_sfnd04_extension_bad_parser_failclosed(tmp_ini_factory, monkeypatch, tmp_path):
    from app.platform.config.loader import _EXTENSION_SECTION_PARSERS

    def bad_parser(p, s):
        raise RuntimeError("boom")

    _EXTENSION_SECTION_PARSERS["boom"] = bad_parser
    try:
        from tests.foundation_sfnd04.test_sfnd04_validation import _inject, _patch_cfg_dir

        p = _inject(tmp_path, tmp_ini_factory, {})
        _patch_cfg_dir(monkeypatch, tmp_path)
        with pytest.raises(Exception):
            ConfigFactory.read_env("dev")
    finally:
        del _EXTENSION_SECTION_PARSERS["boom"]


def test_sfnd04_interpolation_explode_failclosed(tmp_path, monkeypatch):
    bad = """[env
env = dev
db_namespace = bad
=== invalid INI syntax without closing bracket ===
"""
    from app.platform.config import loader, ConfigValidationError

    monkeypatch.setattr(loader, "_CONFIG_DIR", tmp_path)
    (tmp_path / "config.dev.ini").write_text(bad, encoding="utf-8")
    import configparser

    raised = False
    try:
        ConfigFactory.read_env("dev")
    except (configparser.Error, ConfigValidationError):
        raised = True
    assert raised, "Expected failclosed raise for malformed INI (unterminated section)"

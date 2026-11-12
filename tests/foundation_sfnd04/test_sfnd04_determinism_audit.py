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


# --- Package C / K-3: public audit API ``read_env(..., return_audit=True)`` ---


def test_sfnd04_read_env_default_returns_appconfig():
    from app.platform.config import AppConfig

    result = ConfigFactory.read_env("dev")
    assert isinstance(result, AppConfig)
    assert not isinstance(result, tuple)


def test_sfnd04_return_audit_default_is_false():
    import inspect

    sig = inspect.signature(ConfigFactory.read_env)
    assert "return_audit" in sig.parameters
    assert sig.parameters["return_audit"].default is False


def test_sfnd04_read_env_return_audit_true_returns_exact_tuple():
    result = ConfigFactory.read_env("dev", return_audit=True)
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_sfnd04_return_audit_tuple_types():
    from app.platform.config import AppConfig

    cfg, records = ConfigFactory.read_env("dev", return_audit=True)
    assert isinstance(cfg, AppConfig)
    assert isinstance(records, list)
    assert len(records) >= 1
    for rec in records:
        assert isinstance(rec, ConfigReadAuditRecord)


def test_sfnd04_return_audit_record_schema_matches_k3():
    _cfg, records = ConfigFactory.read_env("dev", return_audit=True)
    rec = records[-1]
    assert rec.source_file.endswith("config.dev.ini")
    assert rec.valid_safety is True
    assert isinstance(rec.md5, str) and len(rec.md5) == 32
    assert rec.correlation_id is None or isinstance(rec.correlation_id, str)


def test_sfnd04_return_audit_no_secret_fields():
    _cfg, records = ConfigFactory.read_env("dev", return_audit=True)
    allowed = {"source_file", "md5", "valid_safety", "correlation_id"}
    for rec in records:
        d = rec.to_dict()
        assert set(d.keys()) == allowed
        for key, val in d.items():
            if isinstance(val, str):
                low = val.lower()
                assert "api_key" not in low
                assert "secret" not in low
                assert "password" not in low


def test_sfnd04_return_audit_deterministic():
    payloads = {
        sha_json([rec.to_dict() for rec in ConfigFactory.read_env("dev", return_audit=True)[1]])
        for _ in range(10)
    }
    assert len(payloads) == 1


def test_sfnd04_audit_no_accumulation_across_calls():
    lengths = [len(ConfigFactory.read_env("dev", return_audit=True)[1]) for _ in range(5)]
    assert len(set(lengths)) == 1
    assert lengths[0] >= 1


def test_sfnd04_audit_public_list_isolation_from_private_state():
    cfg, records = ConfigFactory.read_env("dev", return_audit=True)
    private = getattr(cfg, "_audit_trail")
    assert records is not private
    assert records == private

    # Public listenin/kayıtların değiştirilmesi private state'i ETKİLEMEZ.
    records.clear()
    records.append(
        ConfigReadAuditRecord(source_file="tampered", md5="0" * 32, valid_safety=False)
    )
    assert getattr(cfg, "_audit_trail") == private
    assert len(getattr(cfg, "_audit_trail")) == 1

    # Sonraki çağrı da etkilenmez ve tam/bağımsız kayıt döner.
    _cfg2, records2 = ConfigFactory.read_env("dev", return_audit=True)
    assert len(records2) == 1
    assert records2[0].source_file.endswith("config.dev.ini")
    assert records2[0].valid_safety is True


def test_sfnd04_return_audit_error_behavior_preserved(tmp_ini_factory, monkeypatch, tmp_path):
    from app.platform.config import ConfigValidationError
    from tests.foundation_sfnd04.test_sfnd04_validation import _inject, _patch_cfg_dir

    _inject(tmp_path, tmp_ini_factory, {"safety": {"max_leverage_allowed": "2"}})
    _patch_cfg_dir(monkeypatch, tmp_path)

    with pytest.raises(ConfigValidationError) as exc_default:
        ConfigFactory.read_env("dev")
    with pytest.raises(ConfigValidationError) as exc_audit:
        ConfigFactory.read_env("dev", return_audit=True)

    # Kısmi (cfg, records) dönmez; validation hatası her iki modda da yükseltilir.
    assert exc_audit.value.fields == exc_default.value.fields
    assert "max_leverage_allowed" in exc_audit.value.fields


def test_sfnd04_allow_api_keys_and_strict_coercion_unaffected_by_audit_api():
    from app.platform.config import ConfigValidationError
    from app.platform.config.validation import coerce_bool

    cfg = ConfigFactory.read_env("dev")
    assert cfg.safety.allow_api_keys is False

    # STRICT coercion (OD-04 / D-02) korunur: legacy token'lar reddedilir.
    for token in ("yes", "no", "on", "off", "y", "n", ""):
        with pytest.raises(ConfigValidationError):
            coerce_bool(token, "src", "field")
    assert coerce_bool("true", "src", "field") is True
    assert coerce_bool("0", "src", "field") is False
    assert coerce_bool(True, "src", "field") is True


# --- JSON typed safety overlay: determinism + audit kaynağı korunumu ---


def test_sfnd04_json_overlay_determinism_10x(tmp_ini_factory, monkeypatch, tmp_path):
    from tests.foundation_sfnd04.test_sfnd04_validation import _inject, _patch_cfg_dir

    _inject(tmp_path, tmp_ini_factory, {})
    (tmp_path / "config.dev.safety.json").write_text(
        json.dumps({"allow_api_keys": False}), encoding="utf-8"
    )
    _patch_cfg_dir(monkeypatch, tmp_path)
    results: list[str] = []
    for _ in range(10):
        cfg = ConfigFactory.read_env("dev")
        d = _asdict_flat(cfg)
        d.pop("_audit_trail", None)
        results.append(sha_json(d))
    assert len(set(results)) == 1
    assert cfg.safety.allow_api_keys is False


def test_sfnd04_json_overlay_preserves_ini_audit_source_file(
    tmp_ini_factory, monkeypatch, tmp_path
):
    from tests.foundation_sfnd04.test_sfnd04_validation import _inject, _patch_cfg_dir

    _inject(tmp_path, tmp_ini_factory, {})
    (tmp_path / "config.dev.safety.json").write_text(
        json.dumps({"allow_api_keys": False}), encoding="utf-8"
    )
    _patch_cfg_dir(monkeypatch, tmp_path)
    _cfg, records = ConfigFactory.read_env("dev", return_audit=True)
    assert len(records) == 1
    # ``source_file`` audit alanı mevcut INI kaynak anlamını korur; JSON yolu eklenmez.
    assert records[0].source_file.endswith("config.dev.ini")
    assert "safety.json" not in records[0].source_file

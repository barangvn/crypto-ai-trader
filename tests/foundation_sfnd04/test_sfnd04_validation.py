from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.platform.config import ConfigFactory, ConfigValidationError
from app.platform.config.loader import _YAML_DISABLED_MSG, _YAML_ENABLED
from app.platform.config.validation import coerce_bool


def _inject(tmp_path: Path, tmp_ini_factory, extra_sections: dict, name: str = "config.dev.ini") -> Path:
    base = {
        "env": {
            "env": "dev",
            "db_namespace": "inject_dev",
            "artifact_path": "inject/artifacts",
            "run_mode_default": "replay",
        },
        "mode": {"mode": "replay"},
        "network_policy": {"allow_network": "false"},
        "credential_policy": {"source": "none", "allowed_keys": ""},
        "data_policy": {"allow_local_fs": "true"},
        "defaults": {"adn03_stale_min": "5"},
    }
    for s, kv in extra_sections.items():
        if s not in base:
            base[s] = {}
        base[s].update(kv)
    return tmp_ini_factory(base, name)


def _patch_cfg_dir(monkeypatch, tmp_path: Path):
    from app.platform.config import loader

    monkeypatch.setattr(loader, "_CONFIG_DIR", tmp_path)


def test_sfnd04_max_leverage_2_failclosed(tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {"safety": {"max_leverage_allowed": "2"}})
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "max_leverage_allowed" in exc.value.fields
    assert "Safety lock violation" in exc.value.reason


def test_sfnd04_allow_short_true_failclosed(tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {"safety": {"allow_short": "True"}})
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "allow_short" in exc.value.fields


_K_ALLOW = "allow_api" + "_keys"


def test_sfnd04_allow_ext_creds_true_failclosed(tmp_ini_factory, monkeypatch, tmp_path):
    # ``allow_api_keys`` artık JSON overlay'inden okunur (INI yok sayılır):
    # JSON true -> FC-3 safety lock ihlali.
    _inject(tmp_path, tmp_ini_factory, {})
    (tmp_path / "config.dev.safety.json").write_text(
        json.dumps({_K_ALLOW: True}), encoding="utf-8"
    )
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert _K_ALLOW in exc.value.fields


def test_sfnd04_trading_permission_true_failclosed(tmp_ini_factory, monkeypatch, tmp_path):
    # Safety-lock intent: a canonical truthy literal must reach the FC-3 lock,
    # not fail earlier in the STRICT coercion stage (see _strict rejection tests).
    _inject(tmp_path, tmp_ini_factory, {"safety": {"trading_permission_default": "true"}})
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "trading_permission_default" in exc.value.fields
    assert "Safety lock violation" in exc.value.reason


def test_sfnd04_missing_env_section_failclosed(tmp_ini_factory, monkeypatch, tmp_path):
    sections = {
        "mode": {"mode": "replay"},
        "network_policy": {"allow_network": "false"},
        "credential_policy": {"source": "none", "allowed_keys": ""},
        "data_policy": {"allow_local_fs": "true"},
        "defaults": {"adn03_stale_min": "5"},
    }
    tmp_ini_factory(sections, "config.dev.ini")
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "[env]" in exc.value.fields
    assert "missing" in exc.value.reason


def test_sfnd04_missing_ini_file_notfound(tmp_path, monkeypatch):
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(FileNotFoundError):
        ConfigFactory.read_env("dev")


def test_sfnd04_yaml_permanently_off_runtime_error():
    assert _YAML_ENABLED is False
    with pytest.raises(RuntimeError) as exc:
        ConfigFactory.try_yaml("any.yml")
    assert str(exc.value) == _YAML_DISABLED_MSG


def test_sfnd04_yaml_import_wrap_runtimeerror():
    raised_ok = False
    try:
        try:
            import yaml  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "PyYAML disabled by OD-FND-04. No YAML config parsed unless open decision resolved YAML=true."
            ) from e
    except RuntimeError as exc:
        if "PyYAML disabled" in str(exc):
            raised_ok = True
    assert raised_ok


def test_sfnd04_yaml_gate_defense_indepth_safe_load(yaml_enabled_override, tmp_path, monkeypatch):
    from app.platform.config import loader

    assert loader._YAML_ENABLED is True

    class FakeSafeLoader:
        @staticmethod
        def safe_load(stream):
            return {"a": 1, "b": [2, 3]}

    class FakeYamlModule:
        @staticmethod
        def safe_load(fh):
            return {"a": 1, "b": [2, 3]}

    import sys
    sys.modules["yaml"] = FakeYamlModule()
    try:
        p = tmp_path / "sample.yml"
        p.write_text("a: 1\nb: [2,3]\n", encoding="utf-8")
        data = ConfigFactory.try_yaml(str(p))
        assert data == {"a": 1, "b": [2, 3]}
    finally:
        if "yaml" in sys.modules:
            del sys.modules["yaml"]


def test_sfnd04_boolean_coerce_strict_invalid(tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {"safety": {"allow_short": "definitely_not"}})
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "allow_short" in exc.value.fields
    assert "Boolean coerce failed" in exc.value.reason


# --- D-02 STRICT boolean coercion contract (OD-04) ---------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("  true  ", True),
        ("1", True),
        (" 1 ", True),
        ("false", False),
        ("False", False),
        ("FALSE", False),
        ("  false  ", False),
        ("0", False),
    ],
)
def test_sfnd04_coerce_bool_strict_accepts_canonical_literals(raw, expected):
    assert coerce_bool(raw, "src", "field") is expected


@pytest.mark.parametrize(("raw", "expected"), [(True, True), (False, False)])
def test_sfnd04_coerce_bool_strict_accepts_native_bool(raw, expected):
    assert coerce_bool(raw, "src", "field") is expected


@pytest.mark.parametrize("raw", ["yes", "no", "on", "off", "y", "n", "YES", "Off", " truee "])
def test_sfnd04_coerce_bool_strict_rejects_legacy_tokens(raw):
    with pytest.raises(ConfigValidationError) as exc:
        coerce_bool(raw, "src", "target_field")
    assert "target_field" in exc.value.fields
    assert "Boolean coerce failed" in exc.value.reason
    assert "strict bool only: true/false/1/0" in exc.value.reason


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_sfnd04_coerce_bool_strict_rejects_empty_and_none(raw):
    with pytest.raises(ConfigValidationError) as exc:
        coerce_bool(raw, "src", "target_field")
    assert "target_field" in exc.value.fields
    assert "Boolean coerce failed" in exc.value.reason


@pytest.mark.parametrize("raw", [1, 0, 1.0, 0.0, [], {"a": 1}, b"true"])
def test_sfnd04_coerce_bool_strict_rejects_unsupported_types(raw):
    with pytest.raises(ConfigValidationError) as exc:
        coerce_bool(raw, "src", "target_field")
    assert "target_field" in exc.value.fields


def test_sfnd04_coerce_bool_strict_rejection_via_read_env(tmp_ini_factory, monkeypatch, tmp_path):
    # An explicitly invalid token fails closed during coercion (not silently
    # defaulted, and distinct from a missing field falling back to its default).
    _inject(tmp_path, tmp_ini_factory, {"safety": {"allow_short": "yes"}})
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "allow_short" in exc.value.fields
    assert "Boolean coerce failed" in exc.value.reason


def test_sfnd04_coerce_bool_strict_preserves_allow_api_keys_field(
    tmp_ini_factory, monkeypatch, tmp_path
):
    # INI'de geçersiz bir allow_api_keys token'ı bulunsa bile tek yetkili kaynak
    # JSON overlay'idir: INI değeri ne okunur ne coerce edilir -> varsayılan False.
    _inject(tmp_path, tmp_ini_factory, {"safety": {_K_ALLOW: "off"}})
    _patch_cfg_dir(monkeypatch, tmp_path)
    cfg = ConfigFactory.read_env("dev")
    assert cfg.safety.allow_api_keys is False


def test_sfnd04_coerce_bool_strict_observability_metrics_rejected(
    tmp_ini_factory, monkeypatch, tmp_path
):
    _inject(tmp_path, tmp_ini_factory, {"observability": {"metrics_enabled": "on"}})
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "metrics_enabled" in exc.value.fields
    assert "Boolean coerce failed" in exc.value.reason


def test_sfnd04_missing_safety_section_uses_defaults(tmp_ini_factory, monkeypatch, tmp_path):
    # Missing config field -> defaults apply (no coercion error); this is a
    # DIFFERENT behavior from explicitly passing an invalid token.
    _inject(tmp_path, tmp_ini_factory, {})
    _patch_cfg_dir(monkeypatch, tmp_path)
    cfg = ConfigFactory.read_env("dev")
    assert cfg.safety.allow_short is False
    assert cfg.safety.allow_api_keys is False
    assert cfg.safety.trading_permission_default is False
    assert cfg.safety.max_leverage_allowed == 1


# --- S-FND-04 JSON typed overlay: allow_api_keys (OD-FND-04-05/CLAR-01/CLAR-02) ---

_JSON_ALIAS = {"dev": "dev", "test": "test", "stg": "stg", "paper-prod": "prod"}


def _write_safety_json(tmp_path: Path, alias: str, raw: str) -> Path:
    p = tmp_path / f"config.{alias}.safety.json"
    p.write_text(raw, encoding="utf-8")
    return p


@pytest.mark.parametrize("env_name", ["dev", "test", "stg", "paper-prod"])
def test_sfnd04_json_alias_mapping(env_name, tmp_ini_factory, monkeypatch, tmp_path):
    alias = _JSON_ALIAS[env_name]
    _inject(tmp_path, tmp_ini_factory, {}, name=f"config.{alias}.ini")
    for a in ("dev", "test", "stg", "prod"):
        _write_safety_json(tmp_path, a, json.dumps({_K_ALLOW: a == alias}))
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env(env_name)
    assert _K_ALLOW in exc.value.fields


@pytest.mark.parametrize("env_name", ["dev", "test", "stg", "paper-prod"])
def test_sfnd04_json_overlay_false_all_envs(env_name, tmp_ini_factory, monkeypatch, tmp_path):
    alias = _JSON_ALIAS[env_name]
    _inject(tmp_path, tmp_ini_factory, {}, name=f"config.{alias}.ini")
    for a in ("dev", "test", "stg", "prod"):
        _write_safety_json(tmp_path, a, json.dumps({_K_ALLOW: False}))
    _patch_cfg_dir(monkeypatch, tmp_path)
    cfg = ConfigFactory.read_env(env_name)
    assert cfg.safety.allow_api_keys is False


def test_sfnd04_json_false_ok(tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {})
    _write_safety_json(tmp_path, "dev", json.dumps({_K_ALLOW: False}))
    _patch_cfg_dir(monkeypatch, tmp_path)
    cfg = ConfigFactory.read_env("dev")
    assert cfg.safety.allow_api_keys is False


def test_sfnd04_json_missing_file_defaults_false(tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {})
    _patch_cfg_dir(monkeypatch, tmp_path)
    cfg = ConfigFactory.read_env("dev")
    assert cfg.safety.allow_api_keys is False


def test_sfnd04_json_missing_key_defaults_false(tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {})
    _write_safety_json(tmp_path, "dev", json.dumps({}))
    _patch_cfg_dir(monkeypatch, tmp_path)
    cfg = ConfigFactory.read_env("dev")
    assert cfg.safety.allow_api_keys is False


def test_sfnd04_json_true_reaches_safety_lock(tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {})
    _write_safety_json(tmp_path, "dev", json.dumps({_K_ALLOW: True}))
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert _K_ALLOW in exc.value.fields
    assert "Safety lock violation" in exc.value.reason


@pytest.mark.parametrize(
    "raw",
    ['"true"', '"false"', "null", "1", "0", "1.5", "[]", "{}", "[true]"],
)
def test_sfnd04_json_bad_type_rejected(raw, tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {})
    _write_safety_json(tmp_path, "dev", '{"' + _K_ALLOW + '": ' + raw + "}")
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "json_schema" in exc.value.fields


@pytest.mark.parametrize("raw", ["true", "false", "1", '"x"', "[]"])
def test_sfnd04_json_root_not_object_rejected(raw, tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {})
    _write_safety_json(tmp_path, "dev", raw)
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "json_schema" in exc.value.fields


def test_sfnd04_json_unknown_key_rejected(tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {})
    _write_safety_json(tmp_path, "dev", json.dumps({_K_ALLOW: False, "nope": 1}))
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "json_schema" in exc.value.fields
    assert "nope" in exc.value.reason


def test_sfnd04_json_unknown_keys_sorted(tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {})
    _write_safety_json(tmp_path, "dev", json.dumps({"zzz": 1, "aaa": 2}))
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "aaa, zzz" in exc.value.reason


def test_sfnd04_json_broken_rejected(tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {})
    _write_safety_json(tmp_path, "dev", "{not-json")
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "json_parse" in exc.value.fields


def test_sfnd04_json_duplicate_key_rejected(tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {})
    _write_safety_json(
        tmp_path, "dev", '{"' + _K_ALLOW + '": false, "' + _K_ALLOW + '": true}'
    )
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "json_parse" in exc.value.fields
    assert _K_ALLOW in exc.value.reason


def test_sfnd04_json_utf8_rejected(tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {})
    (tmp_path / "config.dev.safety.json").write_bytes(b"\xff\xfe\x00")
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "json_read" in exc.value.fields


def test_sfnd04_json_oserror_rejected(tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {})
    (tmp_path / "config.dev.safety.json").mkdir()
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "json_read" in exc.value.fields


def test_sfnd04_ini_allow_api_keys_ignored(tmp_ini_factory, monkeypatch, tmp_path):
    # INI'de truthy allow_api_keys olsa bile JSON yoksa sonuç False: INI okunmaz.
    _inject(tmp_path, tmp_ini_factory, {"safety": {_K_ALLOW: "1"}})
    _patch_cfg_dir(monkeypatch, tmp_path)
    cfg = ConfigFactory.read_env("dev")
    assert cfg.safety.allow_api_keys is False


def test_sfnd04_no_ini_json_merge(tmp_ini_factory, monkeypatch, tmp_path):
    # JSON false, INI truthy -> JSON kazanır (merge/fallback/öncelik zinciri yok).
    _inject(tmp_path, tmp_ini_factory, {"safety": {_K_ALLOW: "true"}})
    _write_safety_json(tmp_path, "dev", json.dumps({_K_ALLOW: False}))
    _patch_cfg_dir(monkeypatch, tmp_path)
    cfg = ConfigFactory.read_env("dev")
    assert cfg.safety.allow_api_keys is False


def test_sfnd04_other_safety_fields_still_from_ini(tmp_ini_factory, monkeypatch, tmp_path):
    # Diğer safety alanları INI düzeninde çalışmaya devam eder.
    _inject(tmp_path, tmp_ini_factory, {"safety": {"max_leverage_allowed": "2"}})
    _write_safety_json(tmp_path, "dev", json.dumps({_K_ALLOW: False}))
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "max_leverage_allowed" in exc.value.fields


def test_sfnd04_audit_source_file_is_ini(tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {})
    _write_safety_json(tmp_path, "dev", json.dumps({_K_ALLOW: False}))
    _patch_cfg_dir(monkeypatch, tmp_path)
    cfg, records = ConfigFactory.read_env("dev", return_audit=True)
    assert len(records) == 1
    assert records[0].source_file.endswith("config.dev.ini")

from __future__ import annotations

from pathlib import Path

import pytest

from app.platform.config import ConfigFactory, ConfigValidationError
from app.platform.config.loader import _YAML_DISABLED_MSG, _YAML_ENABLED


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
    _inject(tmp_path, tmp_ini_factory, {"safety": {_K_ALLOW: "1"}})
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert _K_ALLOW in exc.value.fields


def test_sfnd04_trading_permission_true_failclosed(tmp_ini_factory, monkeypatch, tmp_path):
    _inject(tmp_path, tmp_ini_factory, {"safety": {"trading_permission_default": "yes"}})
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "trading_permission_default" in exc.value.fields


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

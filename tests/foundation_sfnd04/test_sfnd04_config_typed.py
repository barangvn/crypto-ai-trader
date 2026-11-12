from __future__ import annotations

import json
import os
from dataclasses import fields
from pathlib import Path

import pytest

from app.platform.config import ConfigFactory, ConfigValidationError, EnvSafetyLocks

_K_ALLOW = "allow_api" + "_keys"
_K_LEGACY = "allow_external" + "_creds"


def _env_names():
    return ["dev", "test", "stg", "paper-prod"]


def _safety_ini_sections(api_value: str) -> dict:
    return {
        "env": {
            "env": "dev",
            "db_namespace": "map_dev",
            "artifact_path": "map/artifacts",
            "run_mode_default": "replay",
        },
        "mode": {"mode": "replay"},
        "network_policy": {"allow_network": "false"},
        "credential_policy": {"source": "none", "allowed_keys": ""},
        "data_policy": {"allow_local_fs": "true"},
        "defaults": {"adn03_stale_min": "5"},
        "safety": {
            _K_ALLOW: api_value,
            "max_leverage_allowed": "1",
            "allow_short": "false",
            "trading_permission_default": "false",
        },
    }


def _patch_cfg_dir(monkeypatch, tmp_path: Path) -> None:
    from app.platform.config import loader

    monkeypatch.setattr(loader, "_CONFIG_DIR", tmp_path)


def test_sfnd04_read_env_dev_returns_appconfig():
    cfg = ConfigFactory.read_env("dev")
    assert cfg.env_name == "dev"
    assert cfg.safety.max_leverage_allowed == 1
    assert cfg.safety.allow_short is False
    assert cfg.safety.allow_api_keys is False


def test_sfnd04_allow_api_keys_json_mapping_and_exc_fields(
    tmp_ini_factory, monkeypatch, tmp_path
):
    # (a) Dataclass contract (D-01): canonical attribute present, legacy name removed.
    field_names = {f.name for f in fields(EnvSafetyLocks)}
    assert "allow_api_keys" in field_names
    assert _K_LEGACY not in field_names

    # (b) JSON safety overlay value maps onto the typed attribute (JSON false);
    #     INI içindeki allow_api_keys artık okunmaz (tek yetkili kaynak JSON).
    tmp_ini_factory(_safety_ini_sections("false"), "config.dev.ini")
    (tmp_path / "config.dev.safety.json").write_text(
        json.dumps({_K_ALLOW: False}), encoding="utf-8"
    )
    _patch_cfg_dir(monkeypatch, tmp_path)
    cfg = ConfigFactory.read_env("dev")
    assert cfg.safety.allow_api_keys is False

    # (c) JSON true reaches the FC-3 safety lock and preserves exc.fields name.
    (tmp_path / "config.dev.safety.json").write_text(
        json.dumps({_K_ALLOW: True}), encoding="utf-8"
    )
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("dev")
    assert "allow_api_keys" in exc.value.fields
    assert _K_LEGACY not in exc.value.fields


def test_sfnd04_prod_runtime_key_rejected():
    # ``prod`` geçerli bir runtime environment key DEĞİLDİR.
    with pytest.raises(ValueError):
        ConfigFactory.read_env("prod")


def test_sfnd04_paper_prod_maps_to_prod_safety_json(
    tmp_ini_factory, monkeypatch, tmp_path
):
    # ``paper-prod`` runtime key'i ``config.prod.safety.json`` dosyasına çözülür.
    tmp_ini_factory(_safety_ini_sections("false"), "config.prod.ini")
    (tmp_path / "config.prod.safety.json").write_text(
        json.dumps({_K_ALLOW: True}), encoding="utf-8"
    )
    _patch_cfg_dir(monkeypatch, tmp_path)
    with pytest.raises(ConfigValidationError) as exc:
        ConfigFactory.read_env("paper-prod")
    assert "allow_api_keys" in exc.value.fields


@pytest.mark.parametrize("env_name", _env_names())
def test_sfnd04_4_env_db_namespace_distinct(env_name):
    cfg = ConfigFactory.read_env(env_name)
    assert isinstance(cfg.db_namespace, str)
    assert len(cfg.db_namespace) > 0


def test_sfnd04_4_env_db_namespace_all_different():
    ns = {ConfigFactory.read_env(e).db_namespace for e in _env_names()}
    assert len(ns) == 4


@pytest.mark.parametrize(
    ("env_name", "expected_mode"),
    [
        ("dev", "replay"),
        ("test", "replay"),
        ("stg", "paper"),
        ("paper-prod", "paper"),
    ],
)
def test_sfnd04_run_mode_mapping(env_name, expected_mode):
    cfg = ConfigFactory.read_env(env_name)
    assert cfg.run_mode_default == expected_mode


def test_sfnd04_safety_platform_contract_not_none():
    cfg = ConfigFactory.read_env("dev")
    assert cfg.safety is not None
    assert cfg.platform_contract is not None
    assert cfg.platform_contract.decimal_precision == 8


@pytest.mark.parametrize(
    ("env_name", "expected_level"),
    [
        ("dev", "DEBUG"),
        ("test", "DEBUG"),
        ("stg", "WARN"),
        ("paper-prod", "INFO"),
    ],
)
def test_sfnd04_observability_default_section_fallback(env_name, expected_level):
    cfg = ConfigFactory.read_env(env_name)
    assert cfg.observability is not None
    assert cfg.observability.log_level == expected_level
    assert cfg.observability.metrics_enabled is True


def test_sfnd04_unknown_env_rejected():
    bad = "production_real_live"
    with pytest.raises(ValueError) as exc_info:
        ConfigFactory.read_env(bad)
    assert bad in str(exc_info.value)

from __future__ import annotations

import os

import pytest

from app.platform.config import ConfigFactory


def _env_names():
    return ["dev", "test", "stg", "paper-prod"]


def test_sfnd04_read_env_dev_returns_appconfig():
    cfg = ConfigFactory.read_env("dev")
    assert cfg.env_name == "dev"
    assert cfg.safety.max_leverage_allowed == 1
    assert cfg.safety.allow_short is False


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

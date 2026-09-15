from __future__ import annotations

import pytest

from app.rollback import (
    RollbackEngine,
    ThresholdsConfig,
    ERR_ROLLBACK_THRESHOLDS_VERSION_MISMATCH,
    THRESHOLDS_CONFIG_VERSION_V1,
    check_thresholds_version,
)


def test_check_thresholds_version_mismatch_emits_reason():
    cfg = ThresholdsConfig.from_dict({"thresholds_config_version": "1.0.0"})
    reasons = check_thresholds_version(cfg, "2.0.0")
    assert ERR_ROLLBACK_THRESHOLDS_VERSION_MISMATCH in reasons


def test_check_thresholds_version_none_expected_no_reason():
    cfg = ThresholdsConfig.from_dict({"thresholds_config_version": "1.0.0"})
    assert check_thresholds_version(cfg, None) == []


def test_check_thresholds_version_match_no_reason():
    cfg = ThresholdsConfig.from_dict({"thresholds_config_version": "1.0.0"})
    assert check_thresholds_version(cfg, "1.0.0") == []


@pytest.mark.parametrize(
    "cfg_ver,expected_ver,expect_mismatch",
    [
        ("1.0.0", "1.0.0", False),
        ("1.0.0", "1.0.1", True),
        ("2.0.0", "1.0.0", True),
        ("v1", "v1", False),
        ("v1", "v2", True),
    ],
)
def test_thresholds_version_matrix(cfg_ver, expected_ver, expect_mismatch):
    cfg = ThresholdsConfig.from_dict({"thresholds_config_version": cfg_ver})
    r = check_thresholds_version(cfg, expected_ver)
    if expect_mismatch:
        assert ERR_ROLLBACK_THRESHOLDS_VERSION_MISMATCH in r
    else:
        assert ERR_ROLLBACK_THRESHOLDS_VERSION_MISMATCH not in r


def test_engine_propagates_mismatch_to_reasons(dummy_storage_happy, common_evaluate_kwargs):
    cfg = ThresholdsConfig.from_dict({"thresholds_config_version": "9.9.9"})
    engine = RollbackEngine(
        storage=dummy_storage_happy,
        thresholds_cfg=cfg,
        expected_thresholds_version="1.0.0",
        explicit_seed=55,
    )
    d, _ = engine.evaluate(**common_evaluate_kwargs)
    assert d.eligible is False
    assert ERR_ROLLBACK_THRESHOLDS_VERSION_MISMATCH in d.reasons


def test_default_thresholds_version_constant_exists():
    assert isinstance(THRESHOLDS_CONFIG_VERSION_V1, str)
    assert THRESHOLDS_CONFIG_VERSION_V1 == "1.0.0"

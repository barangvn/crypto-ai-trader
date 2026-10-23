"""TP-07 / AC-16,17 / FC-12,16 / HR-12 — quality builders, degraded invariant, manual override."""

from __future__ import annotations

from dataclasses import astuple

import pytest

from app.contracts.sfnd05_api import QualityFlags, QualityReason
from app.contracts.sfnd06_serialize import (
    append_quality_reason,
    build_quality,
    set_quality_flag,
)


def test_ac16_build_quality_stale_autosets_degraded():
    qf = build_quality(stale=True)
    assert isinstance(qf, QualityFlags)
    assert qf.stale is True
    assert qf.degraded is True  # auto-derived by the S-FND-05 invariant


def test_ac16_default_build_quality_is_clean():
    qf = build_quality()
    assert qf.degraded is False
    assert astuple(qf) == (False, False, False, False, False, False, False, ())


def test_ac16_append_reason_then_duplicate_is_idempotent_first_wins():
    qf = build_quality(stale=True)
    qf2 = append_quality_reason(qf, "STALE_MS", "stale >5m", {"threshold_ms": 300000})
    assert len(qf2.reasons) == 1
    assert qf2.reasons[0].code == "STALE_MS"
    assert qf2.reasons[0].message == "stale >5m"
    assert qf2.reasons[0].context == {"threshold_ms": 300000}
    # duplicate code -> NOOP idempotent, first message wins (GAP-06-05)
    qf3 = append_quality_reason(qf2, "STALE_MS", "different message")
    assert len(qf3.reasons) == 1
    assert qf3.reasons[0].message == "stale >5m"


def test_ac16_append_never_mutates_original_frozen_instance():
    qf = build_quality(stale=True)
    qf2 = append_quality_reason(qf, "C1", "m")
    assert len(qf.reasons) == 0
    assert qf2 is not qf
    assert len(qf2.reasons) == 1


def test_fc12_empty_code_raises():
    with pytest.raises(ValueError):
        append_quality_reason(build_quality(stale=True), "", "x")


def test_fc12_code_too_long_raises():
    with pytest.raises(ValueError):
        append_quality_reason(build_quality(stale=True), "C" * 65, "x")


def test_fc12_code_max_boundary_is_accepted():
    qf = append_quality_reason(build_quality(stale=True), "C" * 64, "x")
    assert len(qf.reasons) == 1


def test_ac17_manual_degraded_override_raises():
    with pytest.raises(ValueError):
        build_quality(degraded=True)


def test_ac17_manual_degraded_with_real_flag_still_raises():
    # HR-12 default safety: manual override rejected even alongside a real flag.
    with pytest.raises(ValueError):
        build_quality(stale=True, degraded=True)


def test_fc16_hr12_set_quality_flag_degraded_raises():
    with pytest.raises(ValueError):
        set_quality_flag(build_quality(stale=True), "degraded", True)


def test_set_quality_flag_toggles_and_autosets_degraded():
    qf = build_quality()
    qf2 = set_quality_flag(qf, "missing", True)
    assert qf2.missing is True
    assert qf2.degraded is True
    assert qf.missing is False  # original frozen instance unchanged


def test_gap0608_unknown_flag_name_raises():
    with pytest.raises(ValueError):
        set_quality_flag(build_quality(), "nonexistent", True)


def test_reasons_accept_instance_and_dict_forms():
    qf = build_quality(stale=True, reasons=[QualityReason(code="A", message="m")])
    assert len(qf.reasons) == 1
    qf2 = build_quality(stale=True, reasons=[{"code": "A", "message": "m"}])
    assert qf2.reasons[0].code == "A"


def test_append_quality_reason_context_defaults_none():
    qf = append_quality_reason(build_quality(stale=True), "CODE", "message")
    assert qf.reasons[0].context is None

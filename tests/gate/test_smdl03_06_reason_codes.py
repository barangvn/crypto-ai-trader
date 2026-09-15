from decimal import Decimal

import pytest

from app.gate import (
    build_promotion_gate_result,
    build_reason_codes,
    default_thresholds_v1,
)
from app.gate.builder import _parse_ts
from app.gate.exceptions import THRESHOLD_FAIL_BY_METRIC_KEY
from tests.gate.conftest import _base_metrics_template


def test_build_reason_codes_sorted_asc():
    reasons = [
        "THRESHOLD_RETURN_PCT_FAIL",
        "HARD_RETURN_NOT_POSITIVE",
        "EVAL_STALE",
    ]
    out = build_reason_codes(reasons)
    assert out == sorted(set(reasons))
    assert out == ["EVAL_STALE", "HARD_RETURN_NOT_POSITIVE", "THRESHOLD_RETURN_PCT_FAIL"]


def test_build_reason_codes_dedupe():
    reasons = ["A", "B", "A", "C", "B"]
    out = build_reason_codes(reasons)
    assert out == ["A", "B", "C"]


def test_build_reason_codes_multiple_buckets():
    b1 = ["Z", "A"]
    b2 = ["M", "A"]
    out = build_reason_codes(b1, b2)
    assert out == ["A", "M", "Z"]


def test_build_reason_codes_empty():
    assert build_reason_codes() == []
    assert build_reason_codes([], [], []) == []


def test_build_promotion_gate_result_empty_reasons_passes():
    gate = build_promotion_gate_result(
        reasons=[],
        meta_cfg=default_thresholds_v1()["meta_thresholds"],
        gate_passed=True,
        thresholds_version="v1",
        weights_version="w1",
    )
    assert gate.passed is True
    assert gate.reasons == []
    assert gate.thresholds_used_version == "v1/w1"


def test_build_promotion_gate_result_reasons_present_not_passed():
    gate = build_promotion_gate_result(
        reasons=["HARD_RETURN_NOT_POSITIVE"],
        meta_cfg=default_thresholds_v1()["meta_thresholds"],
        gate_passed=True,
        thresholds_version="v1",
        weights_version="w1",
    )
    assert gate.passed is False
    assert gate.reasons == ["HARD_RETURN_NOT_POSITIVE"]


def test_build_promotion_gate_result_sorted_reasons():
    unsorted = [
        "THRESHOLD_RETURN_PCT_FAIL",
        "EVAL_STALE",
        "HARD_RETURN_NOT_POSITIVE",
    ]
    gate = build_promotion_gate_result(
        reasons=unsorted,
        meta_cfg={},
        gate_passed=False,
        thresholds_version="t-v",
        weights_version="w-v",
    )
    assert gate.reasons == sorted(set(unsorted))


def test_parse_ts_formats():
    assert _parse_ts("2026-09-12T12:00:00") is not None
    assert _parse_ts("2026-09-12T12:00:00Z") is not None
    assert _parse_ts("2026-09-12") is not None
    assert _parse_ts("not a date") is None
    assert _parse_ts(None) is None

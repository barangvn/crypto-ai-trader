import pytest

from app.gate import (
    ERR_GATE_EVAL_STALE,
    age_evaluation_check,
)


def test_age_eval_fresh_5d():
    reasons = age_evaluation_check(
        eval_ts="2026-09-07T00:00:00",
        comparison_window_end_ts="2026-09-12T00:00:00",
        max_eval_age_days=30,
    )
    assert reasons == []


def test_age_eval_exactly_30d():
    reasons = age_evaluation_check(
        eval_ts="2026-08-13T00:00:00",
        comparison_window_end_ts="2026-09-12T00:00:00",
        max_eval_age_days=30,
    )
    assert reasons == []


def test_age_eval_stale_90d():
    reasons = age_evaluation_check(
        eval_ts="2026-06-12T00:00:00",
        comparison_window_end_ts="2026-09-12T00:00:00",
        max_eval_age_days=30,
    )
    assert ERR_GATE_EVAL_STALE in reasons


def test_age_eval_negative_age():
    reasons = age_evaluation_check(
        eval_ts="2026-10-01T00:00:00",
        comparison_window_end_ts="2026-09-12T00:00:00",
        max_eval_age_days=30,
    )
    assert ERR_GATE_EVAL_STALE in reasons


def test_age_eval_bad_ts_str():
    reasons = age_evaluation_check(
        eval_ts="invalid",
        comparison_window_end_ts="2026-09-12T00:00:00",
    )
    assert ERR_GATE_EVAL_STALE in reasons


def test_age_eval_none_ts():
    reasons = age_evaluation_check(None, None)
    assert ERR_GATE_EVAL_STALE in reasons

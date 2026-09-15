import pytest

from app.gate import (
    ERR_GATE_EVAL_INCOMPARABLE,
    comparable_flag_check,
)


def test_comparable_flag_ok():
    assert comparable_flag_check(True) == []


def test_comparable_flag_false_generic():
    reasons = comparable_flag_check(False)
    assert ERR_GATE_EVAL_INCOMPARABLE in reasons


def test_comparable_flag_preserves_inner_codes():
    inner = ["INCOMPARABLE_WINDOW_MISMATCH", "INCOMPATIBLE_SYMBOL_UNIVERSE"]
    reasons = comparable_flag_check(False, inner)
    assert ERR_GATE_EVAL_INCOMPARABLE in reasons
    assert "INCOMPARABLE_WINDOW_MISMATCH" in reasons
    assert "INCOMPATIBLE_SYMBOL_UNIVERSE" in reasons


def test_comparable_flag_ignores_mismatch_when_comparable():
    inner = ["INCOMPARABLE_WINDOW_MISMATCH"]
    reasons = comparable_flag_check(True, inner)
    assert reasons == []

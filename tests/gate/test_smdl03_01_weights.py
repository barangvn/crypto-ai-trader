from decimal import Decimal

import pytest

from app.gate import (
    ERR_GATE_WEIGHT_MISSING_REQUIRED,
    ERR_GATE_WEIGHT_OUT_OF_RANGE,
    ERR_GATE_WEIGHT_SUM_INVALID,
    ERR_GATE_WEIGHT_UNKNOWN_KEY,
    WEIGHTS_VERSION_V1,
    GateValidationError,
    default_weights_v1,
    renormalize_weights_if_needed,
    validate_weights_definition,
)
from app.gate.weights import _REQUIRED_KEYS_SET
from app.contracts.model import _REQUIRED_METRIC_KEYS


def test_default_weights_v1_keys():
    w = default_weights_v1()
    for key in _REQUIRED_METRIC_KEYS:
        assert key in w
    assert "stability" in w
    assert "fees_per_trade" in w


def test_default_weights_v1_sum_close_to_one():
    w = default_weights_v1()
    total = sum(w.values())
    assert 0.999 <= total <= 1.001


def test_validate_weights_definition_ok_default():
    w = default_weights_v1()
    renormed = renormalize_weights_if_needed(w, WEIGHTS_VERSION_V1)
    validated = validate_weights_definition(renormed)
    total = sum(validated.values())
    assert 0.99999999 <= total <= 1.00000001


def test_validate_weights_missing_required_key():
    w = default_weights_v1()
    w.pop("return_pct")
    with pytest.raises(GateValidationError) as exc:
        validate_weights_definition(w)
    assert exc.value.reason_code == ERR_GATE_WEIGHT_MISSING_REQUIRED


@pytest.mark.parametrize("bad_key,bad_val", [
    ("return_pct", -0.01), ("return_pct", 1.1), ("sharpe_ratio", -0.5)
])
def test_validate_weights_out_of_range(bad_key, bad_val):
    w = default_weights_v1()
    w[bad_key] = bad_val
    with pytest.raises(GateValidationError) as exc:
        validate_weights_definition(w)
    assert exc.value.reason_code == ERR_GATE_WEIGHT_OUT_OF_RANGE


def test_validate_weights_bad_sum():
    w = default_weights_v1()
    w["return_pct"] = 0.5
    w["max_drawdown_pct"] = 0.5
    with pytest.raises(GateValidationError) as exc:
        validate_weights_definition(w)
    assert exc.value.reason_code == ERR_GATE_WEIGHT_SUM_INVALID


def test_validate_weights_unknown_key():
    w = default_weights_v1()
    w["unknown_metric_x"] = 0.01
    with pytest.raises(GateValidationError) as exc:
        validate_weights_definition(w)
    assert exc.value.reason_code == ERR_GATE_WEIGHT_UNKNOWN_KEY


def test_renormalize_weights_if_needed_noop():
    w = default_weights_v1()
    renormed = renormalize_weights_if_needed(w)
    assert len(renormed) == len(w)
    total = sum(renormed.values())
    assert 0.99999999 <= total <= 1.00000001


def test_renormalize_weights_optional_extras_absent():
    w = {k: v for k, v in default_weights_v1().items() if k != "stability" and k != "fees_per_trade"}
    renormed = renormalize_weights_if_needed(w)
    assert 0.99999999 <= sum(renormed.values()) <= 1.00000001


def test_validate_weights_optional_extras_removed_sum_check():
    w = default_weights_v1()
    renormed = renormalize_weights_if_needed(w)
    assert renormed["stability"] > 0
    assert renormed["fees_per_trade"] > 0


@pytest.mark.parametrize("key", list(_REQUIRED_METRIC_KEYS))
def test_validate_weights_each_required_missing_raises(key):
    w = default_weights_v1()
    w.pop(key)
    with pytest.raises(GateValidationError):
        validate_weights_definition(w)


@pytest.mark.parametrize("val", [float("nan"), float("inf"), float("-inf")])
def test_validate_weights_nan_inf_raises(val):
    w = default_weights_v1()
    w["return_pct"] = val
    with pytest.raises(GateValidationError) as exc:
        validate_weights_definition(w)
    assert exc.value.reason_code == ERR_GATE_WEIGHT_OUT_OF_RANGE

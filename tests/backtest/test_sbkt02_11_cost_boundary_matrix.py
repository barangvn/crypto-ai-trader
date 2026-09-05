"""S-BKT-02-11: Cost Injection Boundary Matrix (Priority 1)

Her cost model alanı için: default vs override, zero, non-zero, invalid, negative.
Combos: single, pair, triple, quaternary, full.
Isolation: tek field değişince diğerleri değişmez.
Determinism: 10x identical input -> SHA unique=1.
Backward: default S-PTR-01 baseline match.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace

import pytest

from app.backtest.cost_injection import (
    CostModelOverrides,
    apply_cost_overrides,
    cost_overrides_manifest,
    validate_cost_overrides,
)
from app.backtest.runner import BacktestRunner, compute_result_sha256
from app.backtest.run_metadata import BacktestAssumptions
from app.simulation.fill_config import FillAssumptionsConfig
from tests.backtest.conftest import SyntheticBundle

FEE_FIELDS = [
    "taker_fee_bps",
    "maker_fee_bps",
]
SPREAD_FIELDS = [
    "default_spread_bps",
]
SLIPPAGE_FIELDS = [
    "base_slippage_bps",
]
LATENCY_FIELDS = [
    "base_latency_ms",
    "latency_jitter_ms",
]
PARTIAL_FIELDS = [
    "fill_ratio",
    "partial_count_limit",
]
ALL_FIELDS = FEE_FIELDS + SPREAD_FIELDS + SLIPPAGE_FIELDS + LATENCY_FIELDS + PARTIAL_FIELDS


# ----- Helpers ----------------------------------------------------------------
def _small_bundle(n=300):
    return SyntheticBundle(num_candles=n)


def _runner(overrides=None, asum=None):
    asum = asum or BacktestAssumptions()
    return BacktestRunner(assumptions=asum, cost_overrides=overrides)


# ----- 01a. FEE: DEFAULT vs OVERRIDE, ZERO, NON-ZERO -------------------------
@pytest.mark.parametrize("field", FEE_FIELDS)
@pytest.mark.parametrize("value", [0, 1, 5, 10, 25, 50, 100, 250, 500])
def test_fee_field_override_applied(field, value):
    base = FillAssumptionsConfig()
    ov = CostModelOverrides(**{field: value})
    validate_cost_overrides(ov)
    eff = apply_cost_overrides(base, ov)
    assert float(getattr(eff, field)) == float(value)


@pytest.mark.parametrize("field", FEE_FIELDS)
@pytest.mark.parametrize("value", [-1, -10, -50, -500])
def test_fee_negative_raises(field, value):
    ov = CostModelOverrides(**{field: value})
    with pytest.raises(ValueError, match="BK_COST_INVALID.*negatif"):
        validate_cost_overrides(ov)


@pytest.mark.parametrize("field", FEE_FIELDS)
def test_fee_invalid_type_raises(field):
    for bad in ["not_a_number", [], object()]:
        ov = CostModelOverrides(**{field: bad})
        # Constructor allows any type; validation raises TypeError for invalid types
        with pytest.raises((ValueError, TypeError)):
            validate_cost_overrides(ov)


# ----- 01b. SPREAD boundaries ------------------------------------------------
@pytest.mark.parametrize("value", [0, 1, 5, 10, 30, 100, 250])
def test_spread_override_applied(value):
    ov = CostModelOverrides(default_spread_bps=value)
    validate_cost_overrides(ov)
    eff = apply_cost_overrides(FillAssumptionsConfig(), ov)
    assert float(eff.default_spread_bps) == float(value)


def test_spread_negative_raises():
    with pytest.raises((ValueError, TypeError)):
        validate_cost_overrides(CostModelOverrides(default_spread_bps=-1))


# ----- 01c. SLIPPAGE boundaries ----------------------------------------------
@pytest.mark.parametrize("value", [0, 1, 3, 5, 10, 20, 50])
def test_slippage_override_applied(value):
    ov = CostModelOverrides(base_slippage_bps=value)
    validate_cost_overrides(ov)
    eff = apply_cost_overrides(FillAssumptionsConfig(), ov)
    assert float(eff.base_slippage_bps) == float(value)


def test_slippage_negative_raises():
    with pytest.raises((ValueError, TypeError)):
        validate_cost_overrides(CostModelOverrides(base_slippage_bps=-1))


# ----- 01d. LATENCY boundaries -----------------------------------------------
@pytest.mark.parametrize("field", LATENCY_FIELDS)
@pytest.mark.parametrize("value", [0, 1, 5, 50, 100, 500, 1000, 5000])
def test_latency_override_applied(field, value):
    ov = CostModelOverrides(**{field: value})
    validate_cost_overrides(ov)
    eff = apply_cost_overrides(FillAssumptionsConfig(), ov)
    assert int(getattr(eff, field)) == int(value)


@pytest.mark.parametrize("field", LATENCY_FIELDS)
def test_latency_negative_raises(field):
    with pytest.raises((ValueError, TypeError)):
        validate_cost_overrides(CostModelOverrides(**{field: -1}))


# ----- 01e. PARTIAL FILL boundaries ------------------------------------------
@pytest.mark.parametrize("ratio", ["0.01", "0.1", "0.5", "0.9", "0.99", "1.0"])
def test_partial_fill_ratio_valid(ratio):
    for pcl in [1, 2, 3, 5, 10, 25, 100]:
        ov = CostModelOverrides(fill_ratio=ratio, partial_count_limit=pcl)
        validate_cost_overrides(ov)
        eff = apply_cost_overrides(FillAssumptionsConfig(), ov)
        assert float(eff.fill_ratio) == float(ratio)
        assert int(eff.partial_count_limit) == int(pcl)


@pytest.mark.parametrize("ratio", ["-0.01", "0", "1.01", "2.0", "-1", -0.01, 0, 1.01, 2.0, -1])
def test_partial_fill_ratio_invalid(ratio):
    ov = CostModelOverrides(fill_ratio=ratio, partial_count_limit=3)
    with pytest.raises(ValueError, match="BK_COST_INVALID.*fill_ratio.*\\[0,1\\]"):
        validate_cost_overrides(ov)


@pytest.mark.parametrize("ratio", ["abc", "not_a_number", [], object()])
def test_partial_fill_ratio_invalid_type(ratio):
    ov = CostModelOverrides(fill_ratio=ratio, partial_count_limit=3)
    with pytest.raises(TypeError, match="BK_COST_INVALID_TYPE.*fill_ratio"):
        validate_cost_overrides(ov)


@pytest.mark.parametrize("pcl", [0, -1, -10])
def test_partial_count_limit_invalid(pcl):
    with pytest.raises((ValueError, TypeError)):
        validate_cost_overrides(CostModelOverrides(fill_ratio="0.5", partial_count_limit=pcl))


# ----- 02. Combinations ------------------------------------------------------
PAIRS = [
    ("taker_fee_bps", "default_spread_bps"),
    ("taker_fee_bps", "base_slippage_bps"),
    ("taker_fee_bps", "base_latency_ms"),
    ("taker_fee_bps", "fill_ratio"),
    ("default_spread_bps", "base_slippage_bps"),
    ("default_spread_bps", "base_latency_ms"),
    ("default_spread_bps", "fill_ratio"),
    ("base_slippage_bps", "base_latency_ms"),
    ("base_slippage_bps", "fill_ratio"),
    ("base_latency_ms", "fill_ratio"),
]


@pytest.mark.parametrize("a,b", PAIRS)
def test_two_field_combo_apply(a, b):
    base = FillAssumptionsConfig()
    if b == "fill_ratio":
        va, vb = 23, "0.47"
    elif a == "fill_ratio":
        va, vb = "0.23", 47
    else:
        va, vb = 23, 47
    ov = CostModelOverrides(**{a: va, b: vb})
    eff = apply_cost_overrides(base, ov)
    if isinstance(va, str):
        assert float(getattr(eff, a)) == float(va)
    else:
        assert float(getattr(eff, a)) == float(va)
    if isinstance(vb, str):
        assert float(getattr(eff, b)) == float(vb)
    else:
        assert float(getattr(eff, b)) == float(vb)


TRIPLES = [
    ("taker_fee_bps", "default_spread_bps", "base_slippage_bps"),
    ("taker_fee_bps", "base_latency_ms", "partial_count_limit"),
    ("default_spread_bps", "base_slippage_bps", "base_latency_ms"),
    ("default_spread_bps", "latency_jitter_ms", "partial_count_limit"),
]


@pytest.mark.parametrize("a,b,c", TRIPLES)
def test_three_field_combo_apply(a, b, c):
    ov = CostModelOverrides(**{a: 7, b: 11, c: 13})
    eff = apply_cost_overrides(FillAssumptionsConfig(), ov)
    assert float(getattr(eff, a)) == 7.0
    assert float(getattr(eff, b)) == 11.0
    assert float(getattr(eff, c)) == 13.0


FOUR_FIELD_CASES = [
    ("taker_fee_bps", "default_spread_bps", "base_slippage_bps", "base_latency_ms"),
    ("maker_fee_bps", "default_spread_bps", "latency_jitter_ms", "partial_count_limit"),
]


@pytest.mark.parametrize("a,b,c,d", FOUR_FIELD_CASES)
def test_four_field_combo(a, b, c, d):
    vals = {a: 2, b: 3, c: 5, d: 7}
    ov = CostModelOverrides(**vals)
    eff = apply_cost_overrides(FillAssumptionsConfig(), ov)
    for k, v in vals.items():
        assert float(getattr(eff, k)) == float(v)


def test_all_fields_override_applied():
    kwargs = {
        "taker_fee_bps": 12,
        "maker_fee_bps": 6,
        "default_spread_bps": 15,
        "base_slippage_bps": 9,
        "base_latency_ms": 321,
        "latency_jitter_ms": 54,
        "fill_ratio": "0.75",
        "partial_count_limit": 7,
    }
    ov = CostModelOverrides(**kwargs)
    eff = apply_cost_overrides(FillAssumptionsConfig(), ov)
    for k, v in kwargs.items():
        assert str(getattr(eff, k)).strip() == str(v).strip() or float(getattr(eff, k)) == float(v)


# ----- 03. Isolation: bir field değişince diğerleri değişmez -----------------
@pytest.mark.parametrize("only_field", ALL_FIELDS)
def test_isolation_only_one_changed(only_field):
    base = FillAssumptionsConfig()
    val_map = {
        "taker_fee_bps": 33,
        "maker_fee_bps": 22,
        "default_spread_bps": 44,
        "base_slippage_bps": 11,
        "base_latency_ms": 555,
        "latency_jitter_ms": 66,
        "fill_ratio": "0.33",
        "partial_count_limit": 9,
    }
    ov = CostModelOverrides(**{only_field: val_map[only_field]})
    eff = apply_cost_overrides(base, ov)
    for f in ALL_FIELDS:
        if f == only_field:
            continue
        # unchanged fields: eff[f] == base[f] (identity)
        assert getattr(eff, f) == getattr(base, f), (f, getattr(eff, f), getattr(base, f))


# ----- 04. Metadata deterministic --------------------------------------------
def test_manifest_is_deterministic_across_calls():
    base = FillAssumptionsConfig()
    ov = CostModelOverrides(taker_fee_bps=17, default_spread_bps=31, base_latency_ms=99)
    out = []
    for _ in range(20):
        out.append(
            json.dumps(cost_overrides_manifest(base, ov, None), sort_keys=True, separators=(",", ":"))
        )
    assert len(set(out)) == 1


def test_manifest_diff_per_override_diff():
    base = FillAssumptionsConfig()
    A = json.dumps(cost_overrides_manifest(base, CostModelOverrides(taker_fee_bps=5), None), sort_keys=True)
    B = json.dumps(cost_overrides_manifest(base, CostModelOverrides(taker_fee_bps=6), None), sort_keys=True)
    assert A != B


def test_manifest_order_none_global_none_fold_same():
    base = FillAssumptionsConfig()
    a = json.dumps(cost_overrides_manifest(base, None, None), sort_keys=True)
    b = json.dumps(cost_overrides_manifest(base, None, None), sort_keys=True)
    assert a == b


# ----- 05. Default S-PTR-01 baseline identical -------------------------------
def test_default_override_none_effective_eq_base():
    base = FillAssumptionsConfig()
    eff = apply_cost_overrides(base, None)
    # identity match when no overrides
    for f in [x.name for x in FillAssumptionsConfig.__dataclass_fields__.values()]:
        assert getattr(eff, f) == getattr(base, f)


def test_runner_default_fillconfig_spirit_matches_ptr01_baseline():
    from app.backtest.cost_injection import _fill_config_sorted_dict
    r = BacktestRunner(assumptions=BacktestAssumptions())
    d = FillAssumptionsConfig()
    assert _fill_config_sorted_dict(r.fill_config) == _fill_config_sorted_dict(d)


# ----- 06. Determinism 10x ---------------------------------------------------
def test_10x_same_override_same_sha_result(sbkt_small_bundle):
    ov = CostModelOverrides(
        taker_fee_bps=21,
        default_spread_bps=17,
        base_slippage_bps=3,
        base_latency_ms=123,
    )
    shas = []
    asum = BacktestAssumptions()
    for _ in range(10):
        r = _runner(ov, asum)
        res = r.run(sbkt_small_bundle)
        shas.append(compute_result_sha256(res))
    assert len(set(shas)) == 1


def test_10x_same_default_same_sha(sbkt_small_bundle):
    shas = []
    for _ in range(10):
        r = BacktestRunner(assumptions=BacktestAssumptions())
        res = r.run(sbkt_small_bundle)
        shas.append(compute_result_sha256(res))
    assert len(set(shas)) == 1


def test_cross_instance_identical_override_same_sha(sbkt_small_bundle):
    ov = CostModelOverrides(taker_fee_bps=7, default_spread_bps=9)
    r1 = BacktestRunner(assumptions=BacktestAssumptions(), cost_overrides=copy.deepcopy(ov))
    r2 = BacktestRunner(assumptions=BacktestAssumptions(), cost_overrides=copy.deepcopy(ov))
    s1 = compute_result_sha256(r1.run(sbkt_small_bundle))
    s2 = compute_result_sha256(r2.run(sbkt_small_bundle))
    assert s1 == s2

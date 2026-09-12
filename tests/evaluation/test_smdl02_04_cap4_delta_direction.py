"""T04 — CAP-4: Metric Delta direction correctness 11 keys × 5 cases = 55 tests."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.evaluation.conftest import (  # noqa: E402
    _base_metrics_template,
    challenger_better_metrics,
    champion_metrics,
    make_engine_with_fixtures,
)
from app.evaluation import (  # noqa: E402
    CRITICAL_DELTA_KEYS_ORDERED,
    ERR_METRIC_TYPE_MISMATCH,
    ERR_NAN_NUMERIC,
    CompareValidationError,
    MetricDelta,
    compare_metric_delta,
)
from app.evaluation.delta import Directionality  # noqa: E402


# 11 keys × 5 = 55 parametrize
KEY_DIR = [
    ("return_pct", Directionality.HIGHER_BETTER),
    ("max_drawdown_pct", Directionality.LOWER_BETTER),
    ("sharpe_ratio", Directionality.HIGHER_BETTER),
    ("sortino_ratio", Directionality.HIGHER_BETTER),
    ("profit_factor", Directionality.HIGHER_BETTER),
    ("total_fees_quote", Directionality.LOWER_BETTER),
    ("avg_slippage_bps", Directionality.LOWER_BETTER),
    ("trade_count", Directionality.HIGHER_BETTER),
    ("regime_coverage_count", Directionality.HIGHER_BETTER),
    ("window_days", Directionality.NEUTRAL_MATCH),
    ("oos_flag", Directionality.NEUTRAL_MATCH),
]


@pytest.mark.parametrize("key,expected_dir", KEY_DIR)
def test_direction_table(key, expected_dir):
    from app.evaluation.delta import metric_direction_table

    assert metric_direction_table[key] == expected_dir


@pytest.mark.parametrize("key,dir_expected", KEY_DIR)
def test_delta_positive_when_challenger_better_higher(tmp_path, key, dir_expected):
    """Case A: HigherBetter with challenger > champion → delta >0."""
    if dir_expected != Directionality.HIGHER_BETTER:
        pytest.skip("only HigherBetter")
    c_metrics = champion_metrics()
    t_metrics = dict(champion_metrics())
    # Make challenger larger
    if key == "return_pct":
        t_metrics[key] = Decimal("0.16000000")
        c_metrics[key] = Decimal("0.12000000")
    elif key in {"sharpe_ratio", "sortino_ratio", "profit_factor", "avg_slippage_bps"}:
        t_metrics[key] = float(c_metrics[key]) + 0.5
    elif key in {"trade_count", "regime_coverage_count"}:
        t_metrics[key] = int(c_metrics[key]) + 20
    else:
        pytest.skip("not HigherBetter numeric")
    d: MetricDelta = compare_metric_delta(key, {key: c_metrics[key]}, {key: t_metrics[key]})
    assert d.directionality == dir_expected.value
    assert d.delta > 0
    assert d.winner_hint in {"challenger", "tie", "champion"}
    assert d.winner_hint == "challenger"


@pytest.mark.parametrize("key,dir_expected", KEY_DIR)
def test_delta_positive_when_challenger_better_lower(tmp_path, key, dir_expected):
    """Case B: LowerBetter with challenger smaller → delta > 0."""
    if dir_expected != Directionality.LOWER_BETTER:
        pytest.skip("only LowerBetter")
    c_metrics = champion_metrics()
    # Make challenger smaller
    if key == "max_drawdown_pct":
        c_v = 0.10
        t_v = 0.05
    elif key == "total_fees_quote":
        c_v = Decimal("500")
        t_v = Decimal("200")
    elif key == "avg_slippage_bps":
        c_v = 5.0
        t_v = 2.0
    else:
        pytest.skip("key not LowerBetter")
    d = compare_metric_delta(key, {key: c_v}, {key: t_v})
    assert d.directionality == dir_expected.value
    assert d.delta > 0
    assert d.winner_hint == "challenger"


@pytest.mark.parametrize("key,dir_expected", KEY_DIR)
def test_delta_champion_wins_higher(tmp_path, key, dir_expected):
    """Case C: HigherBetter champion > challenger → delta <0, winner=champion."""
    if dir_expected != Directionality.HIGHER_BETTER:
        pytest.skip("only HigherBetter")
    if key == "return_pct":
        c_v, t_v = Decimal("0.20"), Decimal("0.10")
    elif key in {"sharpe_ratio", "sortino_ratio", "profit_factor"}:
        c_v, t_v = 2.5, 1.0
    elif key in {"trade_count", "regime_coverage_count"}:
        c_v, t_v = 300, 100
    else:
        pytest.skip("skip")
    d = compare_metric_delta(key, {key: c_v}, {key: t_v})
    assert d.delta < 0
    assert d.winner_hint == "champion"


@pytest.mark.parametrize("key,dir_expected", KEY_DIR)
def test_delta_champion_wins_lower(tmp_path, key, dir_expected):
    """Case D: LowerBetter challenger larger (worse) → champion wins, delta<0."""
    if dir_expected != Directionality.LOWER_BETTER:
        pytest.skip("only LowerBetter")
    if key == "max_drawdown_pct":
        c_v, t_v = 0.05, 0.10
    elif key == "total_fees_quote":
        c_v, t_v = Decimal("100"), Decimal("500")
    elif key == "avg_slippage_bps":
        c_v, t_v = 1.0, 5.0
    else:
        pytest.skip("skip")
    d = compare_metric_delta(key, {key: c_v}, {key: t_v})
    assert d.delta < 0
    assert d.winner_hint == "champion"


@pytest.mark.parametrize("key,dir_expected", KEY_DIR)
def test_delta_tie(tmp_path, key, dir_expected):
    """Case E: Equal values → delta==0 tie."""
    VALUES = {
        "return_pct": Decimal("0.10"),
        "max_drawdown_pct": 0.05,
        "sharpe_ratio": 1.2,
        "sortino_ratio": 1.5,
        "profit_factor": 1.4,
        "total_fees_quote": Decimal("300"),
        "avg_slippage_bps": 2.0,
        "trade_count": 200,
        "regime_coverage_count": 5,
        "window_days": 30,
        "oos_flag": True,
    }
    v = VALUES[key]
    d = compare_metric_delta(key, {key: v}, {key: v})
    if dir_expected == Directionality.NEUTRAL_MATCH:
        assert d.winner_hint == "tie"
    else:
        assert d.delta == 0
        assert d.winner_hint == "tie"


def test_delta_decimal_8dp_rounding(tmp_path):
    """Decimal delta rounded to 1e-8 ROUND_HALF_EVEN.
    Per convention, champion_value and challenger_value are rounded first;
    then delta = challenger - challenger rounded.
    """
    from decimal import Decimal as D, ROUND_HALF_EVEN

    Q = D("1e-8")
    c_raw = D("0.123456781")
    t_raw = D("0.123456786")
    # Round inputs first per convention
    c_round = c_raw.quantize(Q, rounding=ROUND_HALF_EVEN)  # 0.12345678 (1 rounds down)
    t_round = t_raw.quantize(Q, rounding=ROUND_HALF_EVEN)  # 0.12345679 (6 rounds up 8->9)
    expected = (t_round - c_round).quantize(Q, rounding=ROUND_HALF_EVEN)  # 1e-8
    d = compare_metric_delta("return_pct", {"return_pct": c_raw}, {"return_pct": t_raw})
    assert d.champion_value == c_round
    assert d.challenger_value == t_round
    assert d.delta == expected


def test_delta_float_8dp_rounding():
    d = compare_metric_delta("sharpe_ratio", {"sharpe_ratio": 1.00000001}, {"sharpe_ratio": 1.00000002})
    # delta rounded to 8 dp
    assert isinstance(d.delta, float)
    assert round(d.delta, 9) == round(1.00000002 - 1.00000001, 8)


def test_delta_nan_fail_closed():
    import math

    with pytest.raises(CompareValidationError) as ex:
        compare_metric_delta("sharpe_ratio", {"sharpe_ratio": 1.0}, {"sharpe_ratio": float("nan")})
    assert ex.value.reason_code in {ERR_NAN_NUMERIC, ERR_METRIC_TYPE_MISMATCH}


def test_delta_infinity_fail_closed():
    with pytest.raises(CompareValidationError):
        compare_metric_delta("max_drawdown_pct", {"max_drawdown_pct": 0.1}, {"max_drawdown_pct": float("inf")})


def test_delta_champion_value_matches():
    c = Decimal("0.1234")
    t = Decimal("0.5678")
    d = compare_metric_delta("return_pct", {"return_pct": c}, {"return_pct": t})
    assert d.champion_value == c.quantize(Decimal("1e-8"))
    assert d.challenger_value == t.quantize(Decimal("1e-8"))


def test_delta_order_in_output(tmp_path):
    """Metric deltas in payload sorted deterministically (required first ordered by CRITICAL then rest sorted)."""
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    md = r.payload.metric_deltas
    first_6_keys = [md[i].metric_key for i in range(6)]
    # First 6 MUST be critical ordered
    assert tuple(first_6_keys) == CRITICAL_DELTA_KEYS_ORDERED


def test_delta_negative_trade_count_fail():
    with pytest.raises(CompareValidationError):
        compare_metric_delta("trade_count", {"trade_count": 10}, {"trade_count": -5})

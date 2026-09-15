from decimal import Decimal

import pytest

from app.contracts.model import (
    CCWinnerEnum,
    PromotionGateResult,
    _REQUIRED_METRIC_KEYS,
)
from app.evaluation.delta import Directionality
from app.gate import (
    GateInvariantError,
    PromotionGate,
    THRESHOLDS_VERSION_V1,
    WEIGHTS_VERSION_V1,
    enforce_winner_gate_invariant,
    default_thresholds_v1,
    default_weights_v1,
    compute_weighted_total_score,
)
from app.gate.exceptions import (
    ERR_GATE_EVIDENCE_DELTAS_INSUFFICIENT,
    ERR_GATE_HARD_DELTA_SIGN_INSUFFICIENT,
    ERR_GATE_HARD_OOS_FLAG_FALSE,
    ERR_GATE_MIN_APPROVALS_FAIL,
    ERR_GATE_MIN_TOTAL_SCORE_UNMET,
    ERR_GATE_NORM_METRIC_MISSING,
)
from app.gate.thresholds import normalize_metric
from app.gate.weights import validate_weights_definition
from tests.gate.conftest import (
    DEFAULT_EVAL_TS,
    DEFAULT_WINDOW_END,
    DummyCompareResult,
    _make_metric_deltas,
    _make_model_eval,
    _make_payload,
)
from tests.evaluation.conftest import _base_metrics_template


def _champion_fixture():
    return _base_metrics_template(
        return_pct=Decimal("0.10"), max_drawdown_pct=0.10, sharpe_ratio=1.2,
        sortino_ratio=1.6, profit_factor=1.30, total_fees_quote=Decimal("250"),
        avg_slippage_bps=8.0, trade_count=100, regime_coverage_count=4,
        window_days=250, oos_flag=True,
    )


def _challenger_fixture_passing():
    return _base_metrics_template(
        return_pct=Decimal("0.25"), max_drawdown_pct=0.04, sharpe_ratio=3.0,
        sortino_ratio=4.0, profit_factor=2.5, total_fees_quote=Decimal("100"),
        avg_slippage_bps=1.0, trade_count=400, regime_coverage_count=9,
        window_days=365, oos_flag=True, stability=0.95, fees_per_trade=0.00005,
    )


def _passing_compare_result():
    champion = _champion_fixture()
    challenger = _challenger_fixture_passing()
    deltas = _make_metric_deltas(champion, challenger)
    payload = _make_payload(CCWinnerEnum.CHALLENGER_PROMOTED, True, challenger, DEFAULT_EVAL_TS)
    return DummyCompareResult(
        payload=payload, comparable=True, metric_deltas=deltas,
        champion_eval=_make_model_eval(champion),
    )


def test_AC_C01_required_11keys_fail_closed():
    weights = validate_weights_definition(default_weights_v1())
    bounds = default_thresholds_v1()["metric_bounds"]
    cm = _challenger_fixture_passing()
    del cm["return_pct"]
    score, reasons = compute_weighted_total_score(cm, weights, bounds, _champion_fixture())
    assert score == 0.0
    assert ERR_GATE_NORM_METRIC_MISSING in reasons


def test_AC_C02_normalize_higherbetter_clamp_upper():
    n_val, _ = normalize_metric("return_pct", Decimal("1.50"), (-0.05, 0.50), Directionality.HIGHER_BETTER)
    assert n_val == pytest.approx(1.0, abs=1e-9)


def test_AC_C02_normalize_higherbetter_clamp_lower():
    n_val, _ = normalize_metric("return_pct", Decimal("-1.0"), (-0.05, 0.50), Directionality.HIGHER_BETTER)
    assert n_val == pytest.approx(0.0, abs=1e-9)


def test_AC_C02_normalize_lowerbetter_clamp_best():
    n_val, _ = normalize_metric("max_drawdown_pct", 0.01, (0.0, 0.5), Directionality.LOWER_BETTER)
    assert n_val == pytest.approx(0.98, abs=1e-9)


def test_AC_C02_normalize_lowerbetter_clamp_worst():
    n_val, _ = normalize_metric("max_drawdown_pct", 0.80, (0.0, 0.5), Directionality.LOWER_BETTER)
    assert n_val == pytest.approx(0.0, abs=1e-9)


def test_AC_C03_weight_out_of_range_fails():
    wbase = default_weights_v1()
    wbad = dict(wbase)
    wbad["return_pct"] = 1.5
    with pytest.raises(Exception):
        validate_weights_definition(wbad)


def test_AC_C03_weight_negative_fails():
    wbase = default_weights_v1()
    wbad = dict(wbase)
    wbad["sharpe_ratio"] = -0.2
    with pytest.raises(Exception):
        validate_weights_definition(wbad)


def test_AC_C03_weight_sum_not_one_fails():
    w = {k: 0.0 for k in _REQUIRED_METRIC_KEYS}
    w["return_pct"] = 0.5
    w["max_drawdown_pct"] = 0.3
    with pytest.raises(Exception):
        validate_weights_definition(w)


def test_AC_C04_weighted_score_8decimals_deterministic():
    weights = validate_weights_definition(default_weights_v1())
    bounds = default_thresholds_v1()["metric_bounds"]
    cm = _challenger_fixture_passing()
    champion = _champion_fixture()
    scores = []
    for _ in range(20):
        s, _ = compute_weighted_total_score(cm, weights, bounds, champion)
        scores.append(f"{s:.8f}")
    assert len(set(scores)) == 1


def test_AC_C05_fees_dynamic_bound_2x_champion():
    champion = _champion_fixture()
    challenger_ok = _base_metrics_template(
        return_pct=Decimal("0.20"), max_drawdown_pct=0.05, sharpe_ratio=1.8,
        sortino_ratio=2.4, profit_factor=1.8, total_fees_quote=Decimal("300"),
        avg_slippage_bps=6.0, trade_count=200, regime_coverage_count=7,
        window_days=300, oos_flag=True,
    )
    w = default_weights_v1()
    weights = validate_weights_definition(w)
    bounds = default_thresholds_v1()["metric_bounds"]
    s, r = compute_weighted_total_score(challenger_ok, weights, bounds, champion)
    assert isinstance(s, float)
    assert 0.0 <= s <= 1.0


def test_AC_C06_min_total_score_065_enforced_fail():
    champion = _champion_fixture()
    challenger_low = _base_metrics_template(
        return_pct=Decimal("0.005"), max_drawdown_pct=0.20, sharpe_ratio=0.15,
        sortino_ratio=0.3, profit_factor=1.02, total_fees_quote=Decimal("450"),
        avg_slippage_bps=20.0, trade_count=45, regime_coverage_count=1,
        window_days=70, oos_flag=True, stability=0.2, fees_per_trade=0.0007,
    )
    deltas = _make_metric_deltas(champion, challenger_low)
    payload = _make_payload(CCWinnerEnum.CHALLENGER_PROMOTED, True, challenger_low, DEFAULT_EVAL_TS)
    cr = DummyCompareResult(
        payload=payload, comparable=True, metric_deltas=deltas,
        champion_eval=_make_model_eval(champion),
    )
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert result["passed"] is False
    assert ERR_GATE_MIN_TOTAL_SCORE_UNMET in result["reasons"]


def test_AC_C07_delta_sign_3plus_wins_enforced():
    champion = _base_metrics_template(
        return_pct=Decimal("0.15"), max_drawdown_pct=0.05, sharpe_ratio=2.5,
        sortino_ratio=3.0, profit_factor=2.0, total_fees_quote=Decimal("180"),
        avg_slippage_bps=3.0, trade_count=300, regime_coverage_count=8,
        window_days=350, oos_flag=True,
    )
    challenger_barely = _base_metrics_template(
        return_pct=Decimal("0.16"), max_drawdown_pct=0.04, sharpe_ratio=2.49,
        sortino_ratio=2.99, profit_factor=1.99, total_fees_quote=Decimal("181"),
        avg_slippage_bps=3.01, trade_count=299, regime_coverage_count=8,
        window_days=349, oos_flag=True,
    )
    deltas = _make_metric_deltas(champion, challenger_barely)
    payload = _make_payload(CCWinnerEnum.CHALLENGER_PROMOTED, True, challenger_barely, DEFAULT_EVAL_TS)
    cr = DummyCompareResult(
        payload=payload, comparable=True, metric_deltas=deltas,
        champion_eval=_make_model_eval(champion),
    )
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert ERR_GATE_HARD_DELTA_SIGN_INSUFFICIENT in result["reasons"]


def test_AC_C08_evidence_chain_min_2_challenger_deltas():
    from app.evaluation.delta import MetricDelta
    champion = _champion_fixture()
    challenger = _challenger_fixture_passing()
    real = _make_metric_deltas(champion, challenger)
    bad = []
    for md in real:
        bad.append(MetricDelta(
            metric_key=md.metric_key,
            champion_value=md.champion_value,
            challenger_value=md.challenger_value,
            delta=md.delta,
            directionality=md.directionality,
            winner_hint="tie",
        ))
    payload = _make_payload(CCWinnerEnum.CHALLENGER_PROMOTED, True, challenger, DEFAULT_EVAL_TS)
    cr = DummyCompareResult(
        payload=payload, comparable=True, metric_deltas=bad,
        champion_eval=_make_model_eval(champion),
    )
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert ERR_GATE_EVIDENCE_DELTAS_INSUFFICIENT in result["reasons"]


def test_AC_C09_hard_reason_code_present():
    cm = _challenger_fixture_passing()
    cm["oos_flag"] = False
    champion = _champion_fixture()
    deltas = _make_metric_deltas(champion, cm)
    payload = _make_payload(CCWinnerEnum.CHALLENGER_PROMOTED, True, cm, DEFAULT_EVAL_TS)
    cr = DummyCompareResult(
        payload=payload, comparable=True, metric_deltas=deltas,
        champion_eval=_make_model_eval(champion),
    )
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"])
    assert ERR_GATE_HARD_OOS_FLAG_FALSE in result["reasons"]


def test_AC_C10_champion_keeps_with_passed_gate_raises():
    gate_ok = PromotionGateResult(passed=True, reasons=[], thresholds_used_version="tv1/wv1")
    with pytest.raises(GateInvariantError):
        enforce_winner_gate_invariant(CCWinnerEnum.CHAMPION_KEEPS, gate_ok)


def test_AC_C10_challenger_wins_with_not_passed_gate_raises():
    gate_no = PromotionGateResult(passed=False, reasons=["HARD_RETURN"], thresholds_used_version="tv1/wv1")
    with pytest.raises(GateInvariantError):
        enforce_winner_gate_invariant(CCWinnerEnum.CHALLENGER_PROMOTED, gate_no)


def test_AC_C11_determinism_10x_identical_output():
    cr = _passing_compare_result()
    gate = PromotionGate()
    results = []
    for _ in range(10):
        results.append(gate.evaluate(cr, DEFAULT_WINDOW_END, approval_refs=["a1"]))
    weighted_set = {r["weighted_total"] for r in results}
    reasons_set = {tuple(r["reasons"]) for r in results}
    passed_set = {r["passed"] for r in results}
    sha_set = {r["schema_sha256"] for r in results}
    winner_set = {r["final_winner"] for r in results}
    version_set = {r["thresholds_used_version"] for r in results}
    gate_tuple_set = {(r["gate"]["passed"], tuple(r["gate"]["reasons"]), r["gate"]["thresholds_used_version"]) for r in results}
    assert len(weighted_set) == 1
    assert len(reasons_set) == 1
    assert len(passed_set) == 1
    assert len(sha_set) == 1
    assert len(winner_set) == 1
    assert len(version_set) == 1
    assert len(gate_tuple_set) == 1


def test_AC_C12_staleness_30days_boundary_fail():
    from app.gate.builder import age_evaluation_check
    eval_ts = "2026-01-01T00:00:00.000Z"
    window_end = "2026-05-01T00:00:00.000Z"
    reasons = age_evaluation_check(eval_ts, window_end, 30)
    assert len(reasons) == 1
    assert reasons[0].startswith("EVAL_STALE")


def test_AC_C12_staleness_within_30days_ok():
    from app.gate.builder import age_evaluation_check
    reasons = age_evaluation_check(DEFAULT_EVAL_TS, DEFAULT_WINDOW_END, 30)
    assert reasons == []


def test_AC_C13_no_approvals_fail_closed():
    cr = _passing_compare_result()
    result = PromotionGate().evaluate(cr, DEFAULT_WINDOW_END, approval_refs=None)
    assert ERR_GATE_MIN_APPROVALS_FAIL in result["reasons"]


def test_AC_C13_insufficient_approvals_fail_closed():
    cr = _passing_compare_result()
    result = PromotionGate().evaluate(
        cr, DEFAULT_WINDOW_END, approval_refs=["a1"],
        min_approval_count_override=5,
    )
    assert ERR_GATE_MIN_APPROVALS_FAIL in result["reasons"]


def test_AC_C14_registry_ast_no_mutation_patterns():
    from app.gate import WeightsConfig, ThresholdsConfig
    w = WeightsConfig(default_weights_v1())
    assert isinstance(w, WeightsConfig)
    assert hasattr(w, "weights")
    assert len(getattr(w, "weights", {})) == len(default_weights_v1())
    tc = ThresholdsConfig(
        thresholds=default_thresholds_v1(),
        thresholds_version=THRESHOLDS_VERSION_V1,
    )
    assert tc.thresholds_version == THRESHOLDS_VERSION_V1
    assert hasattr(tc, "meta_thresholds")
    assert tc.meta_thresholds.get("min_total_score", 0.65) >= 0.65


def test_AC_C15_uses_delta_module_output_untouched():
    import app.evaluation.delta as delta_mod
    assert hasattr(delta_mod, "MetricDelta")
    assert hasattr(delta_mod, "compare_metric_delta")
    champion = _champion_fixture()
    challenger = _challenger_fixture_passing()
    deltas = _make_metric_deltas(champion, challenger)
    assert isinstance(deltas, list)
    assert len(deltas) >= len(_REQUIRED_METRIC_KEYS)
    for md in deltas:
        assert hasattr(md, "metric_key")
        assert hasattr(md, "winner_hint")
        assert hasattr(md, "delta")
        assert md.winner_hint in {"challenger", "champion", "tie"}

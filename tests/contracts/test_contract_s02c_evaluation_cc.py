from __future__ import annotations

import pytest
from decimal import Decimal
from app.contracts.exceptions import ContractSchemaError
from app.contracts import (
    DatasetKindEnum,
    ModelEvaluation,
    CCWinnerEnum,
    ChampionChallengerEvaluation,
    ModelRef,
    PromotionGateResult,
    schema_sha256,
)


# ---------------------------------------------------------------------------
# 11 zorunlu metrics sözlüğü
# ---------------------------------------------------------------------------


def _base_metrics(
    *,
    return_pct: Decimal = Decimal("12.50"),
    max_drawdown_pct: float = 0.08,
    sharpe_ratio: float = 1.85,
    sortino_ratio: float = 2.44,
    profit_factor: float = 1.92,
    total_fees_quote: Decimal = Decimal("340.25"),
    avg_slippage_bps: float = 3.2,
    trade_count: int = 144,
    regime_coverage_count: int = 5,
    window_days: int = 365,
    oos_flag: bool = True,
):
    return {
        "return_pct": return_pct,
        "max_drawdown_pct": max_drawdown_pct,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "profit_factor": profit_factor,
        "total_fees_quote": total_fees_quote,
        "avg_slippage_bps": avg_slippage_bps,
        "trade_count": trade_count,
        "regime_coverage_count": regime_coverage_count,
        "window_days": window_days,
        "oos_flag": oos_flag,
    }


# ---------------------------------------------------------------------------
# ModelEvaluation fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def base_me_args() -> dict:
    return dict(
        eval_id="EVAL_RUN_00099",
        model_id="trend_dual_momentum",
        model_version="1.2.0",
        dataset_kind=DatasetKindEnum.OUT_OF_SAMPLE,
        metrics=_base_metrics(),
        evaluation_ts="2026-07-01T12:00:00.000Z",
        thresholds_config_version="thresholds-v3.1.0",
        evaluation_window_days=365,
        oos_flag=True,
        paper_flag=False,
        correlation_id="COR_EVAL_00099",
        causation_id="PIPELINE_STEP_EVAL",
        notes="OOS evaluation — walk-forward 70/30 split",
    )


# ---------------------------------------------------------------------------
# C-30: metrics 11 zorunlu key — 1 eksik RAISE
# ---------------------------------------------------------------------------


def test_C30_missing_sharpe_ratio_key_raises(base_me_args):
    m = _base_metrics()
    del m["sharpe_ratio"]  # 1 eksik
    base_me_args["metrics"] = m
    with pytest.raises(ContractSchemaError):
        ModelEvaluation(**base_me_args)


def test_C30_all_11_keys_present_pass(base_me_args):
    m = _base_metrics()
    base_me_args["metrics"] = m
    ev = ModelEvaluation(**base_me_args)
    assert len(ev.metrics) >= 11  # 11 required + ek keys


# ---------------------------------------------------------------------------
# C-31: dataset_kind invalid enum RAISE
# ---------------------------------------------------------------------------


def test_C31_dataset_kind_invalid_raises(base_me_args):
    base_me_args["dataset_kind"] = "invalid_dataset_kind_bad"  # type: ignore[assignment]
    with pytest.raises(ContractSchemaError):
        ModelEvaluation(**base_me_args)


def test_C31_all_4_dataset_kind_pass(base_me_args):
    for d in DatasetKindEnum:
        base_me_args["dataset_kind"] = d
        if d.value == "out_of_sample":
            base_me_args["oos_flag"] = True
            base_me_args["metrics"] = _base_metrics(oos_flag=True)
        elif d.value == "paper_trading":
            base_me_args["oos_flag"] = True
            base_me_args["paper_flag"] = True
            base_me_args["metrics"] = _base_metrics(oos_flag=True)
        else:
            base_me_args["oos_flag"] = False
            base_me_args["metrics"] = _base_metrics(oos_flag=False)
        ModelEvaluation(**base_me_args)


# ---------------------------------------------------------------------------
# C-32: evaluation_ts Z yoksa RAISE
# ---------------------------------------------------------------------------


def test_C32_evaluation_ts_no_z_raises(base_me_args):
    base_me_args["evaluation_ts"] = "2026-07-01T12:00:00.000+03:00"
    with pytest.raises(ContractSchemaError):
        ModelEvaluation(**base_me_args)


# ---------------------------------------------------------------------------
# C-33: thresholds_config_version empty RAISE
# ---------------------------------------------------------------------------


def test_C33_thresholds_version_empty_raises(base_me_args):
    base_me_args["thresholds_config_version"] = ""
    with pytest.raises(ContractSchemaError):
        ModelEvaluation(**base_me_args)


# ---------------------------------------------------------------------------
# C-34: max_drawdown_pct 1.0'dan büyükse RAISE (test range enforcement)
# ---------------------------------------------------------------------------


def test_C34_metrics_dd_above_1_raises(base_me_args):
    m = _base_metrics(max_drawdown_pct=1.5)
    base_me_args["metrics"] = m
    with pytest.raises(ContractSchemaError):
        ModelEvaluation(**base_me_args)


def test_C34_metrics_dd_0_or_1_pass(base_me_args):
    for dd in (0.0, 1.0):
        m = _base_metrics(max_drawdown_pct=dd)
        base_me_args["metrics"] = m
        if base_me_args["oos_flag"] != m["oos_flag"]:
            base_me_args["oos_flag"] = m["oos_flag"]
        ModelEvaluation(**base_me_args)


# ---------------------------------------------------------------------------
# Decimal vs Float Doğru ayrımı (DoD-15 ön test): fees Decimal, slippage Float
# ---------------------------------------------------------------------------


def test_metrics_total_fees_must_be_decimal_not_float(base_me_args):
    m = _base_metrics()
    m["total_fees_quote"] = 340.25  # FLOAT, Decimal olmalı — RAISE
    base_me_args["metrics"] = m
    with pytest.raises(ContractSchemaError):
        ModelEvaluation(**base_me_args)


def test_metrics_avg_slippage_must_be_float_not_int(base_me_args):
    m = _base_metrics()
    m["avg_slippage_bps"] = 3  # INT değil, float olmalı — RAISE
    base_me_args["metrics"] = m
    with pytest.raises(ContractSchemaError):
        ModelEvaluation(**base_me_args)


# ---------------------------------------------------------------------------
# ChampionChallengerEvaluation C-35..39
# ---------------------------------------------------------------------------


@pytest.fixture()
def base_cc_args() -> dict:
    comparison_metrics = _base_metrics(
        return_pct=Decimal("14.80"),
        max_drawdown_pct=0.07,
        sharpe_ratio=2.1,
        total_fees_quote=Decimal("312.50"),
        oos_flag=True,
    )
    return dict(
        cc_id="CC_EVAL_2026_AUG_01",
        champion_ref=ModelRef(model_id="trend_dual_momentum", version="1.1.0"),
        challenger_ref=ModelRef(model_id="trend_dual_momentum", version="1.2.0"),
        winner=CCWinnerEnum.CHALLENGER_PROMOTED,
        comparison_metrics=comparison_metrics,
        evaluation_period_days=180,
        promotion_gate_result=PromotionGateResult(
            passed=True,
            reasons=["Sharpe improved > 5%", "DD in tolerance", "Trade count ≥ 100"],
            thresholds_used_version="promotion-gate-v2.0",
        ),
        rollback_strategy_ref="prior_champion_restore_v1",
        approval_refs=["mgmt_board_approval_01", "compliance_sign_off_08"],
        evaluation_ts="2026-08-15T09:30:00.000Z",
        correlation_id="COR_CC_AUG2026_001",
        causation_id="EVAL_RUN_00099",
        notes="Challenger shows 5.2% higher CAGR; similar vol",
    )


# C-35 winner invalid RAISE / 3 doğru değer PASS
def test_C35_winner_invalid_raises(base_cc_args):
    base_cc_args["winner"] = "champion_wins_yay"  # type: ignore[assignment]
    with pytest.raises(ContractSchemaError):
        ChampionChallengerEvaluation(**base_cc_args)


def test_C35_all_3_winner_values_pass(base_cc_args):
    # winner=challenger_promoted + gate.passed=True → geçer (varsayılan)
    ChampionChallengerEvaluation(**base_cc_args)
    # winner=champion_keeps + gate.passed=False → geçer
    base_cc_args["winner"] = CCWinnerEnum.CHAMPION_KEEPS
    base_cc_args["promotion_gate_result"] = PromotionGateResult(
        passed=False,
        reasons=["Challenger failed max_drawdown threshold"],
        thresholds_used_version="promotion-gate-v2.0",
    )
    ChampionChallengerEvaluation(**base_cc_args)
    # winner=inconclusive_rerun + gate.passed=False → geçer
    base_cc_args["winner"] = CCWinnerEnum.INCONCLUSIVE_RERUN
    ChampionChallengerEvaluation(**base_cc_args)


# C-36 champion_ref.model_id EMPTY RAISE
def test_C36_ref_model_id_empty_raises(base_cc_args):
    with pytest.raises(ContractSchemaError):
        base_cc_args["champion_ref"] = ModelRef(model_id="", version="1.1.0")
        ChampionChallengerEvaluation(**base_cc_args)


# C-37 comparison_metrics 1 key eksik RAISE
def test_C37_comparison_metrics_key_missing_raises(base_cc_args):
    cm = base_cc_args["comparison_metrics"]
    del cm["profit_factor"]
    with pytest.raises(ContractSchemaError):
        ChampionChallengerEvaluation(**base_cc_args)


# C-38 promotion_gate_result.thresholds_used_version EMPTY RAISE
def test_C38_gate_thresholds_version_empty_raises(base_cc_args):
    with pytest.raises(ContractSchemaError):
        base_cc_args["promotion_gate_result"] = PromotionGateResult(
            passed=True,
            reasons=["ok"],
            thresholds_used_version="",
        )
        ChampionChallengerEvaluation(**base_cc_args)


# C-39 rollback_strategy_ref non-empty str PASS
def test_C39_rollback_ref_valid_string_pass(base_cc_args):
    base_cc_args["rollback_strategy_ref"] = "prior_champion_restore_v1"
    cc = ChampionChallengerEvaluation(**base_cc_args)
    assert cc.rollback_strategy_ref == "prior_champion_restore_v1"


# C/C invariant: winner=challenger_promoted & gate.passed=True / champion_keeps & gate.passed=True FAIL
def test_cc_invariant_gate_passed_but_champion_keeps_raises(base_cc_args):
    base_cc_args["winner"] = CCWinnerEnum.CHAMPION_KEEPS
    base_cc_args["promotion_gate_result"] = PromotionGateResult(
        passed=True,  # GEÇTİ ama winner=champion_keeps — contradiction RAISE
        reasons=["foo"],
        thresholds_used_version="v1",
    )
    with pytest.raises(ContractSchemaError):
        ChampionChallengerEvaluation(**base_cc_args)


def test_cc_invariant_winner_promoted_but_gate_failed_raises(base_cc_args):
    base_cc_args["winner"] = CCWinnerEnum.CHALLENGER_PROMOTED
    base_cc_args["promotion_gate_result"] = PromotionGateResult(
        passed=False,  # KALDI ama promoted — contradiction RAISE
        reasons=["foo"],
        thresholds_used_version="v1",
    )
    with pytest.raises(ContractSchemaError):
        ChampionChallengerEvaluation(**base_cc_args)


# ---------------------------------------------------------------------------
# Determinism 10x x 2 contract (ModelEval + CC)
# ---------------------------------------------------------------------------


def test_modelevaluation_10x_determinism(base_me_args):
    ev = ModelEvaluation(**base_me_args)
    digests = [schema_sha256(ev) for _ in range(10)]
    assert len(set(digests)) == 1


def test_cc_10x_determinism(base_cc_args):
    cc = ChampionChallengerEvaluation(**base_cc_args)
    digests = [schema_sha256(cc) for _ in range(10)]
    assert len(set(digests)) == 1

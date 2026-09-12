"""T07 — CAP-7: Fold/aggregate delta consumption. 18 tests."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.evaluation.conftest import (  # noqa: E402
    challenger_better_metrics,
    champion_metrics,
    make_engine_with_fixtures,
)
from app.evaluation import CompareValidationError, ERR_INCOMPARABLE_FOLD_COUNT  # noqa: E402


def _fold_template(n: int, r_base: float = 0.01, tc_base: int = 50) -> list[dict]:
    out = []
    for i in range(n):
        out.append({
            "return_pct": Decimal(str(r_base * (1 + i * 0.01))),
            "trade_count": tc_base + i * 2,
            "sharpe_ratio": 1.0 + i * 0.05,
            "sortino_ratio": 1.5 + i * 0.05,
            "profit_factor": 1.2 + i * 0.02,
            "total_fees_quote": Decimal(str(50 + i * 1.5)),
        })
    return out


def test_fold_count_2_both(tmp_path):
    pf = _fold_template(2)
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), per_fold=pf, challenger_per_fold=pf)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    mk = [m.metric_key for m in r.payload.metric_deltas]
    assert "fold_000_return_pct" in mk
    assert "fold_001_return_pct" in mk
    assert "fold_000_trade_count" in mk


def test_fold_count_5_both(tmp_path):
    pf = _fold_template(5)
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), per_fold=pf, challenger_per_fold=pf)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    mk = [m.metric_key for m in r.payload.metric_deltas]
    for i in range(5):
        assert f"fold_{i:03d}_return_pct" in mk


def test_fold_deltas_challenger_better_higher(tmp_path):
    champ_folds = [{
        "return_pct": Decimal("0.05"), "trade_count": 100, "sharpe_ratio": 1.0,
        "sortino_ratio": 1.5, "profit_factor": 1.2, "total_fees_quote": Decimal("100"),
    }]
    chall_folds = [{
        "return_pct": Decimal("0.08"), "trade_count": 120, "sharpe_ratio": 1.3,
        "sortino_ratio": 1.8, "profit_factor": 1.5, "total_fees_quote": Decimal("80"),
    }]
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), per_fold=champ_folds, challenger_per_fold=chall_folds)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    deltas_by_key = {d.metric_key: d for d in r.payload.metric_deltas}
    # return_pct HigherBetter challenger bigger → delta > 0
    assert deltas_by_key["fold_000_return_pct"].delta > Decimal("0")
    assert deltas_by_key["fold_000_return_pct"].winner_hint == "challenger"
    # total_fees_quote LowerBetter challenger smaller → delta > 0
    assert deltas_by_key["fold_000_total_fees_quote"].delta > Decimal("0")
    assert deltas_by_key["fold_000_total_fees_quote"].winner_hint == "challenger"


def test_fold_delta_champion_better_lower(tmp_path):
    champ_folds = [{"max_drawdown_pct": 0.05, "trade_count": 100, "return_pct": Decimal("0.05")}]
    chall_folds = [{"max_drawdown_pct": 0.10, "trade_count": 80, "return_pct": Decimal("0.04")}]
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), per_fold=champ_folds, challenger_per_fold=chall_folds)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    dby = {d.metric_key: d for d in r.payload.metric_deltas}
    assert dby["fold_000_max_drawdown_pct"].delta < 0
    assert dby["fold_000_max_drawdown_pct"].winner_hint == "champion"


def test_fold_count_mismatch_raises(tmp_path):
    champ_folds = _fold_template(3)
    chall_folds = _fold_template(2)
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), per_fold=champ_folds, challenger_per_fold=chall_folds)
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INCOMPARABLE_FOLD_COUNT


def test_fold_count_0_both(tmp_path):
    """Both sides have no folds → fold_count both None/0 comparable."""
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.comparability_result.comparable is True
    # No fold keys if both sides no folds
    mk = [m.metric_key for m in r.payload.metric_deltas]
    assert not any(k.startswith("fold_") for k in mk)


# 18: parametrize fold key directions per test
FOLD_KEYS_DIR = [
    ("return_pct", 0.05, 0.08, "challenger"),  # HigherBetter challenger bigger → challenger winner
    ("return_pct", 0.08, 0.05, "champion"),
    ("sharpe_ratio", 1.0, 1.5, "challenger"),
    ("sharpe_ratio", 1.5, 1.0, "champion"),
    ("sortino_ratio", 1.0, 1.5, "challenger"),
    ("sortino_ratio", 1.5, 1.0, "champion"),
    ("profit_factor", 1.0, 1.5, "challenger"),
    ("profit_factor", 1.5, 1.0, "champion"),
    ("total_fees_quote", Decimal("100"), Decimal("80"), "challenger"),  # LowerBetter → smaller challenger better
    ("total_fees_quote", Decimal("80"), Decimal("100"), "champion"),
    ("trade_count", 100, 150, "challenger"),
    ("trade_count", 150, 100, "champion"),
]


@pytest.mark.parametrize("key,cv,tv,expect_win", FOLD_KEYS_DIR)
def test_fold_keys_winner_directions(tmp_path, key, cv, tv, expect_win):
    if isinstance(cv, float):
        cf = [{key: float(cv)}]
        tf = [{key: float(tv)}]
    elif isinstance(cv, Decimal):
        cf = [{key: cv}]
        tf = [{key: tv}]
    else:
        cf = [{key: int(cv)}]
        tf = [{key: int(tv)}]
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), per_fold=cf, challenger_per_fold=tf)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    by_key = {d.metric_key: d for d in r.payload.metric_deltas}
    fk = f"fold_000_{key}"
    assert fk in by_key, (fk, by_key.keys())
    assert by_key[fk].winner_hint == expect_win

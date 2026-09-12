"""T08 — CAP-8: Regime performance delta consumption. 14 tests."""

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
from app.evaluation import CompareValidationError, ERR_INCOMPARABLE_REGIME_GROUPS  # noqa: E402


def _rmat(*rows):
    return list(rows)


def test_regime_delta_present(tmp_path):
    regime = _rmat(
        {"strategy_id": "s1", "regime": "low_vol", "return_pct": Decimal("0.01"), "trade_count": 10, "sharpe_ratio": 1.0, "profit_factor": 1.2, "total_fees_quote": Decimal("50"), "sortino_ratio": 1.3, "avg_slippage_bps": 2.0},
        {"strategy_id": "s2", "regime": "low_vol", "return_pct": Decimal("0.02"), "trade_count": 15, "sharpe_ratio": 1.1, "profit_factor": 1.3, "total_fees_quote": Decimal("60"), "sortino_ratio": 1.4, "avg_slippage_bps": 2.1},
    )
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), regime=regime, challenger_regime=regime)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    keys = {d.metric_key for d in r.payload.metric_deltas}
    assert "regime_s1_low_vol_return_pct" in keys
    assert "regime_s2_low_vol_trade_count" in keys


def test_regime_delta_challenger_better(tmp_path):
    c = _rmat({"strategy_id": "s1", "regime": "lv", "return_pct": Decimal("0.01"), "total_fees_quote": Decimal("100"), "trade_count": 50, "sharpe_ratio": 1.0, "sortino_ratio": 1.5, "profit_factor": 1.2, "avg_slippage_bps": 3.0})
    t = _rmat({"strategy_id": "s1", "regime": "lv", "return_pct": Decimal("0.02"), "total_fees_quote": Decimal("50"), "trade_count": 80, "sharpe_ratio": 1.5, "sortino_ratio": 2.0, "profit_factor": 1.4, "avg_slippage_bps": 1.5})
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), regime=c, challenger_regime=t)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    byk = {d.metric_key: d for d in r.payload.metric_deltas}
    assert byk["regime_s1_lv_return_pct"].winner_hint == "challenger"
    assert byk["regime_s1_lv_total_fees_quote"].winner_hint == "challenger"
    assert byk["regime_s1_lv_trade_count"].winner_hint == "challenger"


def test_regime_delta_champion_better(tmp_path):
    c = _rmat({"strategy_id": "s1", "regime": "hv", "return_pct": Decimal("0.03"), "total_fees_quote": Decimal("50"), "trade_count": 100, "sharpe_ratio": 2.0, "sortino_ratio": 2.5, "profit_factor": 1.5, "avg_slippage_bps": 1.0})
    t = _rmat({"strategy_id": "s1", "regime": "hv", "return_pct": Decimal("0.01"), "total_fees_quote": Decimal("120"), "trade_count": 50, "sharpe_ratio": 1.0, "sortino_ratio": 1.2, "profit_factor": 1.1, "avg_slippage_bps": 4.0})
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), regime=c, challenger_regime=t)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    byk = {d.metric_key: d for d in r.payload.metric_deltas}
    assert byk["regime_s1_hv_return_pct"].winner_hint == "champion"
    assert byk["regime_s1_hv_total_fees_quote"].winner_hint == "champion"
    assert byk["regime_s1_hv_avg_slippage_bps"].winner_hint == "champion"


def test_regime_groups_mismatch(tmp_path):
    c = _rmat({"strategy_id": "s1", "regime": "lv", "return_pct": Decimal("0.01")})
    t = _rmat({"strategy_id": "s1", "regime": "hv", "return_pct": Decimal("0.01")})
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), regime=c, challenger_regime=t)
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INCOMPARABLE_REGIME_GROUPS


def test_regime_groups_match_stability_optional(tmp_path):
    c = _rmat(
        {"strategy_id": "s1", "regime": "lv", "return_pct": Decimal("0.01"), "trade_count": 10, "sharpe_ratio": 1.0},
        {"strategy_id": "s1", "regime": "hv", "return_pct": Decimal("0.005"), "trade_count": 12, "sharpe_ratio": 0.9},
    )
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), regime=c, challenger_regime=c)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.comparability_result.comparable is True
    # stability optional: artifact summary stability absent → no delta needed; comparable ok


# 14 tests: 10 parametrize
REGIME_KEYS = [
    ("return_pct", Decimal("0.01"), Decimal("0.02"), "challenger"),
    ("return_pct", Decimal("0.03"), Decimal("0.01"), "champion"),
    ("trade_count", 100, 150, "challenger"),
    ("trade_count", 150, 100, "champion"),
    ("sharpe_ratio", 1.0, 1.5, "challenger"),
    ("sharpe_ratio", 1.5, 1.0, "champion"),
    ("total_fees_quote", Decimal("100"), Decimal("80"), "challenger"),
    ("total_fees_quote", Decimal("80"), Decimal("100"), "champion"),
    ("avg_slippage_bps", 3.0, 1.5, "challenger"),
    ("avg_slippage_bps", 1.5, 3.0, "champion"),
]


@pytest.mark.parametrize("key,cv,tv,expect", REGIME_KEYS)
def test_regime_keys_directions(tmp_path, key, cv, tv, expect):
    c = _rmat({"strategy_id": "s0", "regime": "r0", key: cv})
    t = _rmat({"strategy_id": "s0", "regime": "r0", key: tv})
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), regime=c, challenger_regime=t)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    byk = {d.metric_key: d for d in r.payload.metric_deltas}
    k = f"regime_s0_r0_{key}"
    assert k in byk, (k, list(byk.keys())[:50])
    assert byk[k].winner_hint == expect

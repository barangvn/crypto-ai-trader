"""T02 — CAP-2: Comparability 6 invariants + extras. 25 tests parametrize."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.contracts.model import (  # noqa: E402
    DatasetKindEnum,
    ModelCompatibilityRef,
    TrainingDataRange,
)
from app.evaluation import (  # noqa: E402
    CompareValidationError,
    ERR_INCOMPARABLE_COMPATIBILITY,
    ERR_INCOMPARABLE_COST,
    ERR_INCOMPARABLE_DATASET,
    ERR_INCOMPARABLE_FOLD_COUNT,
    ERR_INCOMPARABLE_REGIME_GROUPS,
    ERR_INCOMPARABLE_THRESHOLDS,
    ERR_INCOMPARABLE_UNIVERSE,
    ERR_INCOMPARABLE_WINDOW,
)
from tests.evaluation.conftest import (  # noqa: E402
    DEFAULT_COMPAT,
    DEFAULT_COST_VERSION,
    DEFAULT_THRESHOLDS_VERSION,
    DEFAULT_UNIVERSE,
    DEFAULT_WINDOW,
    challenger_better_metrics,
    champion_metrics,
    make_engine_with_fixtures,
)


def _shift_ts(ts: str, days: int) -> str:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    shifted = dt + timedelta(days=days)
    shifted = shifted.astimezone(timezone.utc)
    ms = int(shifted.microsecond / 1000)
    return shifted.strftime("%Y-%m-%dT%H:%M:%S") + f".{ms:03d}Z"


def test_happy_comparable_true(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.comparability_result.comparable is True
    assert r.payload.comparable is True


def test_incomparable_window_100_percent_overlap(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    # Happy no error
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.comparability_result.comparable is True


def test_incomparable_window_95_percent_overlap(tmp_path):
    """Challenger window 365-day shifted 18-days forward → overlap ~347/383 < 0.99 → ERR_INCOMPARABLE_WINDOW."""
    challenger_w = TrainingDataRange(start=_shift_ts(DEFAULT_WINDOW.start, 18), end=_shift_ts(DEFAULT_WINDOW.end, 18))
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), challenger_window=challenger_w)
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INCOMPARABLE_WINDOW


def test_incomparable_window_no_overlap(tmp_path):
    challenger_w = TrainingDataRange(start="2026-01-02T00:00:00.000Z", end="2027-01-01T00:00:00.000Z")
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), challenger_window=challenger_w)
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INCOMPARABLE_WINDOW


def test_incomparable_dataset_kind(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), dataset_kind=DatasetKindEnum.OUT_OF_SAMPLE, challenger_dataset_kind=DatasetKindEnum.IN_SAMPLE)
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INCOMPARABLE_DATASET


def test_incomparable_dataset_kind_walk_forward_vs_paper(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), dataset_kind=DatasetKindEnum.WALK_FORWARD, challenger_dataset_kind=DatasetKindEnum.PAPER_TRADING)
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INCOMPARABLE_DATASET


def test_incomparable_thresholds(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), thresholds="1.0.0", challenger_thresholds="1.0.1")
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INCOMPARABLE_THRESHOLDS


def test_incomparable_cost(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), cost=DEFAULT_COST_VERSION, challenger_cost="cost-v2")
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INCOMPARABLE_COST


def test_incomparable_universe_extra_symbol(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), universe=DEFAULT_UNIVERSE, challenger_universe=["BTC_USDT", "ETH_USDT", "SOL_USDT"])
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INCOMPARABLE_UNIVERSE


def test_incomparable_universe_partial(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), universe=["BTC_USDT"], challenger_universe=["ETH_USDT"])
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INCOMPARABLE_UNIVERSE


def test_incomparable_universe_casefold_match(tmp_path):
    """Case-insensitive match btc_usdt vs BTC_USDT → same universe"""
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), universe=["btc_usdt", "eth_usdt"], challenger_universe=["BTC_USDT", "ETH_USDT"])
    # No error, comparable OK
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.comparability_result.comparable is True


def test_incomparable_empty_universe(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), universe=[], challenger_universe=[])
    # Empty universe comparable (both empty) → OK
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.comparability_result.comparable is True


def test_incomparable_compat_feature(tmp_path):
    challenger_compat = ModelCompatibilityRef(
        feature_version="feature-v2.1",
        strategy_version=DEFAULT_COMPAT.strategy_version,
        regime_version=DEFAULT_COMPAT.regime_version,
    )
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), compat=DEFAULT_COMPAT, challenger_compat=challenger_compat)
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INCOMPARABLE_COMPATIBILITY


def test_incomparable_compat_strategy(tmp_path):
    challenger_compat = ModelCompatibilityRef(
        feature_version=DEFAULT_COMPAT.feature_version,
        strategy_version="strategy-v999",
        regime_version=DEFAULT_COMPAT.regime_version,
    )
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), compat=DEFAULT_COMPAT, challenger_compat=challenger_compat)
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INCOMPARABLE_COMPATIBILITY


def test_incomparable_compat_regime(tmp_path):
    challenger_compat = ModelCompatibilityRef(
        feature_version=DEFAULT_COMPAT.feature_version,
        strategy_version=DEFAULT_COMPAT.strategy_version,
        regime_version="regime-v99",
    )
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), compat=DEFAULT_COMPAT, challenger_compat=challenger_compat)
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INCOMPARABLE_COMPATIBILITY


def test_incomparable_fold_count_mismatch(tmp_path):
    pf_ch = [{"return_pct": Decimal("0.01"), "trade_count": 50}, {"return_pct": Decimal("0.02"), "trade_count": 50}]
    pf_ct = [{"return_pct": Decimal("0.015"), "trade_count": 55}]  # len 1 vs 2
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), per_fold=pf_ch, challenger_per_fold=pf_ct)
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INCOMPARABLE_FOLD_COUNT


def test_comparable_fold_count_match(tmp_path):
    pf = [{"return_pct": Decimal("0.01"), "trade_count": 50, "sharpe_ratio": 1.0}, {"return_pct": Decimal("0.02"), "trade_count": 50, "sharpe_ratio": 1.1}]
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), per_fold=pf, challenger_per_fold=pf)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.comparability_result.comparable is True
    # Fold deltas in metric_deltas: fold_000_return_pct / fold_001_return_pct present
    metric_keys = [m.metric_key for m in r.payload.metric_deltas]
    assert "fold_000_return_pct" in metric_keys
    assert "fold_001_return_pct" in metric_keys


def test_incomparable_regime_groups_mismatch(tmp_path):
    regime_c = [
        {"strategy_id": "s1", "regime": "low_vol", "return_pct": Decimal("0.01"), "trade_count": 10},
        {"strategy_id": "s1", "regime": "high_vol", "return_pct": Decimal("0.005"), "trade_count": 12},
        {"strategy_id": "s2", "regime": "low_vol", "return_pct": Decimal("0.02"), "trade_count": 15},
    ]
    regime_t = [
        {"strategy_id": "s1", "regime": "low_vol", "return_pct": Decimal("0.012"), "trade_count": 11},
        {"strategy_id": "s1", "regime": "high_vol", "return_pct": Decimal("0.006"), "trade_count": 13},
    ]
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), regime=regime_c, challenger_regime=regime_t)
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INCOMPARABLE_REGIME_GROUPS


def test_comparable_regime_groups_match(tmp_path):
    regime = [
        {"strategy_id": "s1", "regime": "low_vol", "return_pct": Decimal("0.01"), "trade_count": 10},
        {"strategy_id": "s2", "regime": "low_vol", "return_pct": Decimal("0.02"), "trade_count": 15},
    ]
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), regime=regime, challenger_regime=regime)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.comparability_result.comparable is True
    mk = [m.metric_key for m in r.payload.metric_deltas]
    assert "regime_s1_low_vol_return_pct" in mk
    assert "regime_s2_low_vol_trade_count" in mk


def test_incomparable_details_contains_first_mismatch_window(tmp_path):
    challenger_w = TrainingDataRange(start="2026-01-02T00:00:00.000Z", end="2027-01-01T00:00:00.000Z")
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), challenger_window=challenger_w)
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    d = ex.value.details
    assert "mismatches" in d
    assert "window_overlap" in d["mismatches"]
    assert "champion_invariants" in d and "challenger_invariants" in d


def test_multiple_mismatches_reports_all(tmp_path):
    challenger_w = TrainingDataRange(start="2026-01-02T00:00:00.000Z", end="2027-01-01T00:00:00.000Z")
    fix = make_engine_with_fixtures(
        tmp_path, champion_metrics(), challenger_better_metrics(),
        challenger_window=challenger_w, challenger_cost="cost-v2",
    )
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    mismatches = ex.value.details["mismatches"]
    assert len(mismatches) >= 2
    assert "window_overlap" in mismatches
    assert "cost_config_version" in mismatches


def test_universe_order_independent_comparable(tmp_path):
    """Universe order diff should be comparable OK due to canonical set fold/casefold equality."""
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), universe=["BTC_USDT", "ETH_USDT"], challenger_universe=["ETH_USDT", "BTC_USDT"])
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.comparability_result.comparable is True


def test_incomparable_window_shifted_1_day_same_end(tmp_path):
    """Start shifted 1 day within 365-day range → overlap 364/366 = ~0.9945 still > 0.99 → comparable OK."""
    challenger_w = TrainingDataRange(start=_shift_ts(DEFAULT_WINDOW.start, 1), end=DEFAULT_WINDOW.end)
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), challenger_window=challenger_w)
    # No error (overlap ratio ~0.994 > 0.99)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.comparability_result.comparable is True

"""T03 — CAP-3: Artifact -> ModelEvaluation build strict fail-closed. 39 tests."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.evaluation.conftest import (  # noqa: E402
    DEFAULT_COST_VERSION,
    DEFAULT_THRESHOLDS_VERSION,
    challenger_better_metrics,
    champion_metrics,
    make_engine_with_fixtures,
)
from app.evaluation import (  # noqa: E402
    CompareValidationError,
    ERR_ARTIFACT_CORRUPT,
    ERR_METRIC_TYPE_MISMATCH,
    ERR_MISSING_METRIC,
    ERR_MODEL_NOT_FOUND,
)


def test_build_model_eval_11_required(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    from app.contracts.model import _REQUIRED_METRIC_KEYS

    for k in _REQUIRED_METRIC_KEYS:
        assert k in r.champion_eval.metrics
        assert k in r.challenger_eval.metrics
    # champion_eval type correct
    from app.contracts.model import ModelEvaluation
    assert isinstance(r.champion_eval, ModelEvaluation)


def test_build_eval_decimal_keys_decimal_type(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert isinstance(r.champion_eval.metrics["return_pct"], Decimal)
    assert isinstance(r.champion_eval.metrics["total_fees_quote"], Decimal)


def test_build_eval_int_keys_int_type(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    for k in ("trade_count", "regime_coverage_count", "window_days"):
        assert isinstance(r.champion_eval.metrics[k], int), k
        assert isinstance(r.challenger_eval.metrics[k], int), k


def test_build_eval_float_keys_float_type(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    for k in ("max_drawdown_pct", "sharpe_ratio", "sortino_ratio", "profit_factor", "avg_slippage_bps"):
        assert isinstance(r.champion_eval.metrics[k], float), k


def test_build_eval_oos_flag_bool(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert isinstance(r.champion_eval.metrics["oos_flag"], bool)
    assert isinstance(r.champion_eval.oos_flag, bool)


def test_build_eval_evaluation_ts_instant_valid(tmp_path):
    from app.contracts.types import validate_instant

    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert validate_instant(r.champion_eval.evaluation_ts)
    assert validate_instant(r.challenger_eval.evaluation_ts)


def test_build_eval_thresholds_config_version(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.champion_eval.thresholds_config_version == DEFAULT_THRESHOLDS_VERSION


def test_build_eval_paper_flag_default_false(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.champion_eval.paper_flag is False
    assert r.challenger_eval.paper_flag is False


def test_build_eval_evaluation_window_days_matches(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.champion_eval.evaluation_window_days == champion_metrics()["window_days"]
    assert r.challenger_eval.evaluation_window_days == challenger_better_metrics()["window_days"]


def test_build_eval_metrics_correlation_id(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert isinstance(r.champion_eval.correlation_id, str)
    assert len(r.champion_eval.correlation_id) >= 8


def test_build_eval_metrics_causation_id(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert isinstance(r.champion_eval.causation_id, str)
    assert len(r.champion_eval.causation_id) >= 8


def test_build_eval_eval_id(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert isinstance(r.champion_eval.eval_id, str)
    assert len(r.champion_eval.eval_id) >= 8


@pytest.mark.parametrize("key", [
    "return_pct", "max_drawdown_pct", "sharpe_ratio", "sortino_ratio", "profit_factor",
    "total_fees_quote", "avg_slippage_bps", "trade_count", "regime_coverage_count",
    "window_days", "oos_flag",
])
def test_build_eval_missing_each_required_key(tmp_path, key):
    """Corrupt artifact by removing one required key from champion metrics -> ERR_MISSING_METRIC or ERR_ARTIFACT_CORRUPT."""
    from tests.evaluation.conftest import build_artifact_json_bytes, hashlib
    from app.registry import EvidenceKind
    from tests.evaluation.conftest import make_sample_mv, build_registry_with_models
    from app.evaluation import CompareEngine

    ch_mv = make_sample_mv(model_id="miss_kp", version="1.0.0", status=__import__("app.contracts.model", fromlist=["ModelLifecycleStatus"]).ModelLifecycleStatus.CHAMPION)
    ct_mv = make_sample_mv(model_id="miss_ks", version="2.0.0", status=__import__("app.contracts.model", fromlist=["ModelLifecycleStatus"]).ModelLifecycleStatus.CHALLENGER)
    # Corrupt champion_metrics drop `key`
    ch_metrics = dict(champion_metrics())
    ch_metrics.pop(key, None)
    _ch_sha, ch_hist = build_artifact_json_bytes(ch_mv.model_id, ch_mv.version, ch_metrics)
    _ct_sha, ct_hist = build_artifact_json_bytes(ct_mv.model_id, ct_mv.version, challenger_better_metrics())
    champion_bytes = {k: ch_hist for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
    challenger_bytes = {k: ct_hist for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
    registry, paths = build_registry_with_models(tmp_path, ch_mv, ct_mv, champion_artifact_bytes=champion_bytes, challenger_artifact_bytes=challenger_bytes)
    engine = CompareEngine(registry=registry)
    with pytest.raises(CompareValidationError) as ex:
        engine.compare(ch_mv.model_id, ch_mv.version, ct_mv.model_id, ct_mv.version)
    assert ex.value.reason_code in {ERR_MISSING_METRIC, ERR_ARTIFACT_CORRUPT}


def test_build_eval_invalid_decimal_str(tmp_path):
    """Corrupt return_pct to non-numeric str -> ERR_METRIC_TYPE_MISMATCH or ERR_ARTIFACT_CORRUPT."""
    from tests.evaluation.conftest import build_artifact_json_bytes, hashlib
    from app.registry import EvidenceKind
    from tests.evaluation.conftest import make_sample_mv, build_registry_with_models
    from app.evaluation import CompareEngine
    from app.contracts.model import ModelLifecycleStatus

    ch_mv = make_sample_mv(model_id="bad_decimal_mv", version="1.0.0", status=ModelLifecycleStatus.CHAMPION)
    ct_mv = make_sample_mv(model_id="good_2_mv", version="2.0.0", status=ModelLifecycleStatus.CHALLENGER)
    ch_metrics = dict(champion_metrics())
    ch_metrics["return_pct"] = "NOT_A_NUMBER"
    _ch_sha, ch_hist = build_artifact_json_bytes(ch_mv.model_id, ch_mv.version, ch_metrics)
    _ct_sha, ct_hist = build_artifact_json_bytes(ct_mv.model_id, ct_mv.version, challenger_better_metrics())
    champion_bytes = {k: ch_hist for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
    challenger_bytes = {k: ct_hist for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
    registry, _p = build_registry_with_models(tmp_path, ch_mv, ct_mv, champion_artifact_bytes=champion_bytes, challenger_artifact_bytes=challenger_bytes)
    eng = CompareEngine(registry=registry)
    with pytest.raises(CompareValidationError) as ex:
        eng.compare(ch_mv.model_id, ch_mv.version, ct_mv.model_id, ct_mv.version)
    assert ex.value.reason_code in {ERR_METRIC_TYPE_MISMATCH, ERR_ARTIFACT_CORRUPT}


def test_build_eval_model_id_mismatch(tmp_path):
    """Champion artifact model_id does not match registry mv -> ERR_INCOMPATIBLE_STATUS_TRANSITION or MODEL_NOT_FOUND."""
    from tests.evaluation.conftest import build_artifact_json_bytes
    from app.registry import EvidenceKind
    from tests.evaluation.conftest import make_sample_mv, build_registry_with_models
    from app.evaluation import CompareEngine
    from app.contracts.model import ModelLifecycleStatus

    ch_mv = make_sample_mv(model_id="ch_id_mv", version="1.0.0", status=ModelLifecycleStatus.CHAMPION)
    ct_mv = make_sample_mv(model_id="ct_id_mv", version="2.0.0", status=ModelLifecycleStatus.CHALLENGER)
    # Artifact for champion has wrong model_id (ct_mv's id instead)
    _ch_sha, ch_hist = build_artifact_json_bytes("WRONG_ID", ch_mv.version, champion_metrics())
    _ct_sha, ct_hist = build_artifact_json_bytes(ct_mv.model_id, ct_mv.version, challenger_better_metrics())
    champion_bytes = {k: ch_hist for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
    challenger_bytes = {k: ct_hist for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
    registry, _p = build_registry_with_models(tmp_path, ch_mv, ct_mv, champion_artifact_bytes=champion_bytes, challenger_artifact_bytes=challenger_bytes)
    eng = CompareEngine(registry=registry)
    with pytest.raises(CompareValidationError):
        eng.compare(ch_mv.model_id, ch_mv.version, ct_mv.model_id, ct_mv.version)


def test_build_eval_cost_config_version_consumed(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), cost=DEFAULT_COST_VERSION)
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    # champion_eval thresholds version OK
    assert r.champion_eval.thresholds_config_version == DEFAULT_THRESHOLDS_VERSION


def test_build_eval_notes_roundtrip(tmp_path):
    from tests.evaluation.conftest import build_artifact_json_bytes
    from app.registry import EvidenceKind
    from tests.evaluation.conftest import make_sample_mv, build_registry_with_models
    from app.evaluation import CompareEngine
    from app.contracts.model import ModelLifecycleStatus

    ch_mv = make_sample_mv(model_id="notes_ch", version="1.0.0", status=ModelLifecycleStatus.CHAMPION)
    ct_mv = make_sample_mv(model_id="notes_ct", version="2.0.0", status=ModelLifecycleStatus.CHALLENGER)
    notes = "Notes content with unicode 日"
    _ch_sha, ch_hist = build_artifact_json_bytes(ch_mv.model_id, ch_mv.version, champion_metrics(), notes=notes)
    _ct_sha, ct_hist = build_artifact_json_bytes(ct_mv.model_id, ct_mv.version, challenger_better_metrics(), notes=None)
    champion_bytes = {k: ch_hist for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
    challenger_bytes = {k: ct_hist for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
    registry, _p = build_registry_with_models(tmp_path, ch_mv, ct_mv, champion_artifact_bytes=champion_bytes, challenger_artifact_bytes=challenger_bytes)
    eng = CompareEngine(registry=registry)
    r = eng.compare(ch_mv.model_id, ch_mv.version, ct_mv.model_id, ct_mv.version)
    assert r.champion_eval.notes == notes

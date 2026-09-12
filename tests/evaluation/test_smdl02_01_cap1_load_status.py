"""T01 — CAP-1: Champion/Challenger identify + load + status. 22 tests parametrize."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.evaluation.conftest import (  # noqa: E402
    DEFAULT_WINDOW,
    challenger_better_metrics,
    champion_metrics,
    make_engine_with_fixtures,
)
from app.contracts.model import DatasetKindEnum, ModelLifecycleStatus  # noqa: E402
from app.registry import EvidenceKind  # noqa: E402
from app.evaluation import (  # noqa: E402
    CompareValidationError,
    ERR_EMPTY_CHALLENGER_MODEL,
    ERR_EMPTY_CHAMPION_MODEL,
    ERR_MODEL_NOT_FOUND,
    ERR_NOT_CHALLENGER_STATUS,
    ERR_NOT_CHAMPION_STATUS,
    ERR_SAME_MODEL_SAME_VERSION,
)


@pytest.mark.parametrize(
    "case,champion_status,challenger_status,expect_reason,should_pass",
    [
        ("happy", ModelLifecycleStatus.CHAMPION, ModelLifecycleStatus.CHALLENGER, None, True),
        ("challenger_tested_allowed", ModelLifecycleStatus.CHAMPION, ModelLifecycleStatus.TESTED, None, True),
        ("champion_wrong_paper", ModelLifecycleStatus.PAPER, ModelLifecycleStatus.CHALLENGER, ERR_NOT_CHAMPION_STATUS, False),
        ("champion_wrong_tested", ModelLifecycleStatus.TESTED, ModelLifecycleStatus.CHALLENGER, ERR_NOT_CHAMPION_STATUS, False),
        ("challenger_wrong_paper", ModelLifecycleStatus.CHAMPION, ModelLifecycleStatus.PAPER, ERR_NOT_CHALLENGER_STATUS, False),
        ("challenger_wrong_candidate", ModelLifecycleStatus.CHAMPION, ModelLifecycleStatus.CANDIDATE, ERR_NOT_CHALLENGER_STATUS, False),
        ("challenger_wrong_retired", ModelLifecycleStatus.CHAMPION, ModelLifecycleStatus.RETIRED, ERR_NOT_CHALLENGER_STATUS, False),
    ],
)
def test_identify_status(tmp_path, case, champion_status, challenger_status, expect_reason, should_pass):
    from tests.evaluation.conftest import make_sample_mv, build_registry_with_models
    from tests.evaluation.conftest import build_artifact_json_bytes

    ch_mv = make_sample_mv(model_id="ch_mv_v1", version="1.0.0", status=champion_status, window=DEFAULT_WINDOW)
    ct_mv = make_sample_mv(model_id="ct_mv_v2", version="2.0.0", status=challenger_status, window=DEFAULT_WINDOW)
    _ch_sha, ch_hist = build_artifact_json_bytes(ch_mv.model_id, ch_mv.version, champion_metrics(), dataset_kind=DatasetKindEnum.OUT_OF_SAMPLE)
    _ct_sha, ct_hist = build_artifact_json_bytes(ct_mv.model_id, ct_mv.version, challenger_better_metrics(), dataset_kind=DatasetKindEnum.OUT_OF_SAMPLE)
    champion_bytes = {EvidenceKind.HISTORICAL_OOS_EVAL: ch_hist, EvidenceKind.WALK_FORWARD_RUN: ch_hist, EvidenceKind.PAPER_REPLAY_EVAL: ch_hist}
    challenger_bytes = {EvidenceKind.HISTORICAL_OOS_EVAL: ct_hist, EvidenceKind.WALK_FORWARD_RUN: ct_hist, EvidenceKind.PAPER_REPLAY_EVAL: ct_hist}
    registry, paths = build_registry_with_models(tmp_path, ch_mv, ct_mv, champion_artifact_bytes=champion_bytes, challenger_artifact_bytes=challenger_bytes)
    from app.evaluation import CompareEngine

    engine = CompareEngine(registry=registry)
    if should_pass:
        r = engine.compare(ch_mv.model_id, ch_mv.version, ct_mv.model_id, ct_mv.version)
        assert r.payload.comparable is True
        assert r.champion_model.status == champion_status
        assert r.challenger_model.status == challenger_status
        assert r.payload.winner_hint.value in {"challenger_promoted", "inconclusive_rerun", "champion_keeps"}
    else:
        with pytest.raises(CompareValidationError) as ex:
            engine.compare(ch_mv.model_id, ch_mv.version, ct_mv.model_id, ct_mv.version)
        assert ex.value.reason_code == expect_reason, ex.value


def test_challenger_same_model_same_version(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(
            fix["champion_mv"].model_id,
            fix["champion_mv"].version,
            fix["champion_mv"].model_id,
            fix["champion_mv"].version,
        )
    assert ex.value.reason_code == ERR_SAME_MODEL_SAME_VERSION


def test_champion_model_not_found(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare("does_not_exist", "1.0.0", fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_MODEL_NOT_FOUND


def test_challenger_model_not_found(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, "ct_missing", "3.0.0")
    assert ex.value.reason_code == ERR_MODEL_NOT_FOUND


def test_champion_empty_model_id(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare("", fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_EMPTY_CHAMPION_MODEL


def test_champion_empty_version(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, "", fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_EMPTY_CHAMPION_MODEL


def test_challenger_empty_model_id(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, "", fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_EMPTY_CHALLENGER_MODEL


def test_challenger_empty_version(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, "")
    assert ex.value.reason_code == ERR_EMPTY_CHALLENGER_MODEL


def test_evidence_list_contains_three_required_kinds(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    champ_ev = fix["registry"].list_evidence(fix["champion_mv"].model_id, fix["champion_mv"].version)
    chall_ev = fix["registry"].list_evidence(fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    present_c = {e.kind.value for e in champ_ev}
    present_t = {e.kind.value for e in chall_ev}
    for required in ("historical_oos_eval", "walk_forward_run", "paper_replay_eval"):
        assert required in present_c
        assert required in present_t
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    # evidence refs in payload
    kinds_in_payload = {e.get("kind") for e in r.payload.evidence_refs}
    assert {"historical_oos_eval", "walk_forward_run", "paper_replay_eval"} <= kinds_in_payload


def test_correlation_short_not_reject(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    # correlation short length (<8) if set; we don't care; fixture default corr length >=8
    assert "correlation_id" in r.payload.metadata
    # causation short length
    assert "causation_id" in r.payload.metadata
    # empty corr/caus fallback not reject
    r2 = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version, correlation_id="", causation_id="")
    # Empty correlation → engine overrides with default (non-empty fallback) → no reject
    assert r2.payload is not None


def test_registry_return_mv_deep_copy(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    mv, sha = fix["registry"].get(fix["champion_mv"].model_id, fix["champion_mv"].version)
    assert mv.status == ModelLifecycleStatus.CHAMPION
    # S-MDL-01: no direct mutation allowed; registry returns deep copy; assign attempt; if dataclass frozen? not frozen; but storage immutable because next get returns independent copy. We do not mutate (S-MDL-02 read-only)
    mv.status = ModelLifecycleStatus.RETIRED  # type: ignore[misc]  # local
    mv2, _sha2 = fix["registry"].get(fix["champion_mv"].model_id, fix["champion_mv"].version)
    assert mv2.status == ModelLifecycleStatus.CHAMPION

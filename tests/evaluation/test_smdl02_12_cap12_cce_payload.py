"""T12 — CAP-12: CCE payload serialization + contract fields. 8 tests."""

from __future__ import annotations

import sys
import json
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.evaluation.conftest import (  # noqa: E402
    challenger_better_metrics,
    champion_metrics,
    make_engine_with_fixtures,
)
from app.contracts.model import (  # noqa: E402
    ChampionChallengerEvaluation,
    CCWinnerEnum,
    PromotionGateResult,
)
from app.evaluation.contract_payload import ChampionChallengerEvaluationPayload  # noqa: E402


def test_payload_contains_cce_contract(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert isinstance(r.payload, ChampionChallengerEvaluationPayload)
    assert isinstance(r.payload.cce_contract, ChampionChallengerEvaluation)


def test_payload_winner_hint_cce_same(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.payload.cce_contract.winner == r.payload.winner_hint


def test_payload_promotion_gate_result_default_false(tmp_path):
    """Spec S-MDL-02: gate_result.passed NEVER set = default False from constructor."""
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    pg = r.payload.cce_contract.promotion_gate_result
    assert isinstance(pg, PromotionGateResult)
    assert pg.passed is False


def test_payload_comparable_true(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert r.payload.comparable is True
    assert r.payload.cce_contract.comparison_metrics is not None


def test_payload_evidence_refs_list(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert isinstance(r.payload.evidence_refs, list)
    assert len(r.payload.evidence_refs) >= 6  # 2 sides × 3 required


def test_payload_metadata_keys(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    md = r.payload.metadata
    for required in ("correlation_id", "causation_id", "evaluation_ts", "thresholds_config_version", "cost_config_version", "champion_model_id", "challenger_model_id", "champion_version", "challenger_version"):
        assert required in md, required


def test_payload_to_sorted_dict_sorted_keys(tmp_path):
    import json

    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    d = r.payload.to_sorted_dict()
    s1 = json.dumps(d, sort_keys=True, separators=(",", ":"), default=str)
    s2 = json.dumps(json.loads(json.dumps(d, default=str)), sort_keys=True, separators=(",", ":"), default=str)
    assert s1 == s2
    # Metric deltas order
    assert "metric_deltas" in d and isinstance(d["metric_deltas"], list)
    first_6_keys = [m["metric_key"] for m in d["metric_deltas"][:6]]
    from app.evaluation import CRITICAL_DELTA_KEYS_ORDERED

    assert tuple(first_6_keys) == CRITICAL_DELTA_KEYS_ORDERED


def test_payload_schema_sha_matches_to_json_sorted(tmp_path):
    import hashlib, json

    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    d = r.payload.to_sorted_dict()
    s = json.dumps(d, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    expected_sha = hashlib.sha256(s).hexdigest()
    assert r.payload.schema_sha256() == expected_sha

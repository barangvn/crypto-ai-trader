"""T06 — CAP-6: Evidence SHA integrity + 3 required kinds. 4 tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.evaluation.conftest import (  # noqa: E402
    challenger_better_metrics,
    champion_metrics,
    make_engine_with_fixtures,
)
from app.evaluation import CompareValidationError, ERR_INTEGRITY_SHA_MISMATCH  # noqa: E402


def test_integrity_sha_mismatch_fail(tmp_path):
    fix = make_engine_with_fixtures(
        tmp_path, champion_metrics(), challenger_better_metrics(),
        integrity_mismatch_champion_historical=True,
    )
    with pytest.raises(CompareValidationError) as ex:
        fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    assert ex.value.reason_code == ERR_INTEGRITY_SHA_MISMATCH


def test_integrity_sha_match_ok(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    # champion sha matches
    champ_hist_ref = [e for e in fix["registry"].list_evidence(fix["champion_mv"].model_id, fix["champion_mv"].version) if e.kind.value == "historical_oos_eval"][0]
    import hashlib

    bytes_on_disk = Path(champ_hist_ref.artifact_uri).read_bytes()
    assert hashlib.sha256(bytes_on_disk).hexdigest() == champ_hist_ref.integrity_sha256
    assert r is not None


def test_evidence_refs_in_payload(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    # evidence_refs present as list of dicts in payload
    from app.evaluation.contract_payload import ChampionChallengerEvaluationPayload

    assert isinstance(r.payload, ChampionChallengerEvaluationPayload)
    assert isinstance(r.payload.evidence_refs, list)
    assert len(r.payload.evidence_refs) >= 6  # 2 sides × 3 required kinds


def test_evidence_uri_exists(tmp_path):
    fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
    r = fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
    for ref in r.payload.evidence_refs:
        uri = ref.get("artifact_uri")
        assert uri
        # file:// URIs strip to local path
        if uri.startswith("file://"):
            p = Path(uri[len("file://"):])
        else:
            p = Path(uri)
        assert p.exists(), f"Missing artifact file: {p}"

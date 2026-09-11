from __future__ import annotations

from app.registry import EvidenceKind, EvidenceRef
from app.contracts import now_instant
from tests.registry.conftest import sample_mv


VALID_ULIDISH = "01ABCDEF000000000000000001"


def _make(kind, ref_id, uri):
    return EvidenceRef(
        kind=kind,
        ref_id=ref_id,
        artifact_uri=uri,
        source_created_ts=now_instant(),
        correlation_id=VALID_ULIDISH,
    )


def _append_sbkt_evidence(reg, model_id, version):
    e1 = _make(
        EvidenceKind.HISTORICAL_OOS_EVAL,
        "BKT01-eval-001",
        ".bk-artifacts/runs/bkt01/summary.json",
    )
    e2 = _make(
        EvidenceKind.WALK_FORWARD_RUN,
        "BKT02-fold-A1",
        ".bk-artifacts/mf-runs/abc/mfr.json",
    )
    e3 = _make(
        EvidenceKind.HISTORICAL_OOS_EVAL,
        "BKT03-metrics-L3",
        ".bk-artifacts/bkt03/metrics.json",
    )
    reg.append_evidence(model_id, version, e1)
    reg.append_evidence(model_id, version, e2)
    reg.append_evidence(model_id, version, e3)


def test_smdl01_11_sbkt01_linkage_mock_ref_and_uri(fresh_registry):
    reg, _bus, _storage = fresh_registry
    mv = sample_mv(model_id="sbkt_link_model", version="0.1.0")
    reg.create(mv)

    e = _make(
        EvidenceKind.HISTORICAL_OOS_EVAL,
        "BKT01-eval-001",
        ".bk-artifacts/runs/bkt01/summary.json",
    )
    reg.append_evidence(mv.model_id, mv.version, e)

    listed = reg.list_evidence(mv.model_id, mv.version)
    assert len(listed) == 1
    assert listed[0].ref_id == "BKT01-eval-001"
    assert listed[0].artifact_uri == ".bk-artifacts/runs/bkt01/summary.json"
    assert listed[0].kind == EvidenceKind.HISTORICAL_OOS_EVAL


def test_smdl01_11_sbkt02_linkage_mock_ref_and_uri(fresh_registry):
    reg, _bus, _storage = fresh_registry
    mv = sample_mv(model_id="sbkt_link_model", version="0.1.0")
    reg.create(mv)

    e = _make(
        EvidenceKind.WALK_FORWARD_RUN,
        "BKT02-fold-A1",
        ".bk-artifacts/mf-runs/abc/mfr.json",
    )
    reg.append_evidence(mv.model_id, mv.version, e)

    listed = reg.list_evidence(mv.model_id, mv.version)
    assert len(listed) == 1
    assert listed[0].ref_id == "BKT02-fold-A1"
    assert listed[0].artifact_uri == ".bk-artifacts/mf-runs/abc/mfr.json"
    assert listed[0].kind == EvidenceKind.WALK_FORWARD_RUN


def test_smdl01_11_sbkt03_linkage_mock_ref_and_uri(fresh_registry):
    reg, _bus, _storage = fresh_registry
    mv = sample_mv(model_id="sbkt_link_model", version="0.1.0")
    reg.create(mv)

    e = _make(
        EvidenceKind.HISTORICAL_OOS_EVAL,
        "BKT03-metrics-L3",
        ".bk-artifacts/bkt03/metrics.json",
    )
    reg.append_evidence(mv.model_id, mv.version, e)

    listed = reg.list_evidence(mv.model_id, mv.version)
    assert len(listed) == 1
    assert listed[0].ref_id == "BKT03-metrics-L3"
    assert listed[0].artifact_uri == ".bk-artifacts/bkt03/metrics.json"
    assert listed[0].kind == EvidenceKind.HISTORICAL_OOS_EVAL


def test_smdl01_11_three_evidences_canonical_order(fresh_registry):
    reg, _bus, _storage = fresh_registry
    mv = sample_mv(model_id="sbkt_link_model", version="0.1.0")
    reg.create(mv)

    _append_sbkt_evidence(reg, mv.model_id, mv.version)
    listed = reg.list_evidence(mv.model_id, mv.version)

    assert len(listed) == 3

    keys = [(e.kind.value, e.ref_id) for e in listed]
    assert keys == sorted(keys)

    expected_order = [
        (EvidenceKind.HISTORICAL_OOS_EVAL.value, "BKT01-eval-001"),
        (EvidenceKind.HISTORICAL_OOS_EVAL.value, "BKT03-metrics-L3"),
        (EvidenceKind.WALK_FORWARD_RUN.value, "BKT02-fold-A1"),
    ]
    assert keys == expected_order


def test_smdl01_11_append_three_times_list_length_equals_three(fresh_registry):
    reg, _bus, _storage = fresh_registry
    mv = sample_mv(model_id="sbkt_link_model", version="0.1.0")
    reg.create(mv)

    _append_sbkt_evidence(reg, mv.model_id, mv.version)
    assert len(reg.list_evidence(mv.model_id, mv.version)) == 3


def test_smdl01_11_list_zero_is_historical_oos_eval_alphabetical(fresh_registry):
    reg, _bus, _storage = fresh_registry
    mv = sample_mv(model_id="sbkt_link_model", version="0.1.0")
    reg.create(mv)

    _append_sbkt_evidence(reg, mv.model_id, mv.version)
    listed = reg.list_evidence(mv.model_id, mv.version)

    assert listed[0].kind == EvidenceKind.HISTORICAL_OOS_EVAL
    assert listed[0].ref_id == "BKT01-eval-001"

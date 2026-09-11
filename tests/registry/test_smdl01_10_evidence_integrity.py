from __future__ import annotations

import pytest

from app.registry import (
    ERR_EVIDENCE_INTEGRITY,
    ERR_EVIDENCE_REF_DUPLICATE,
    ERR_EVIDENCE_TYPE_INVALID,
    ERR_FIELD_VALIDATION,
    EvidenceKind,
    EvidenceRef,
    RegistryError,
)
from app.contracts import now_instant


VALID_SHA256 = "a" * 64
VALID_ULIDISH = "01ABCDEF000000000000000001"


def _make_evidence(kind: EvidenceKind, ref_id: str = "ref-001", **overrides):
    base = dict(
        kind=kind,
        ref_id=ref_id,
        artifact_uri=f".bk-artifacts/{kind.value}/{ref_id}.json",
        source_created_ts=now_instant(),
        correlation_id=VALID_ULIDISH,
        integrity_sha256=None,
        metadata={},
    )
    base.update(overrides)
    return EvidenceRef(**base)


HAPPY_KINDS = [
    EvidenceKind.HISTORICAL_OOS_EVAL,
    EvidenceKind.WALK_FORWARD_RUN,
    EvidenceKind.PAPER_REPLAY_EVAL,
    EvidenceKind.ARTIFACT_PACKAGE,
    EvidenceKind.FEATURESET_REF,
    EvidenceKind.HYPERPARAMS_SNAPSHOT,
    EvidenceKind.COST_INJECTION_CONFIG,
]


@pytest.mark.parametrize("kind", HAPPY_KINDS, ids=[k.value for k in HAPPY_KINDS])
def test_smdl01_10_evidence_kind_happy_create(kind):
    ev = _make_evidence(kind=kind, ref_id=f"ref-{kind.value}")
    assert ev.kind == kind
    assert isinstance(ev.ref_id, str) and ev.ref_id
    assert isinstance(ev.artifact_uri, str) and ev.artifact_uri


def test_smdl01_10_kind_invalid_string_raises_evidence_type_invalid():
    with pytest.raises(RegistryError) as exc_info:
        EvidenceRef(
            kind="bogus_kind",
            ref_id="x",
            artifact_uri="uri:x",
            source_created_ts=now_instant(),
            correlation_id=VALID_ULIDISH,
        )
    assert exc_info.value.reason_code == ERR_EVIDENCE_TYPE_INVALID


def test_smdl01_10_kind_invalid_enum_raises_evidence_type_invalid():
    with pytest.raises(RegistryError) as exc_info:
        EvidenceRef(
            kind="not_a_real_kind_xyz",
            ref_id="x",
            artifact_uri="uri:x",
            source_created_ts=now_instant(),
            correlation_id=VALID_ULIDISH,
        )
    assert exc_info.value.reason_code == ERR_EVIDENCE_TYPE_INVALID


def test_smdl01_10_ref_id_empty_raises_field_validation():
    with pytest.raises(RegistryError) as exc_info:
        EvidenceRef(
            kind=EvidenceKind.HISTORICAL_OOS_EVAL,
            ref_id="",
            artifact_uri="uri:x",
            source_created_ts=now_instant(),
            correlation_id=VALID_ULIDISH,
        )
    assert exc_info.value.reason_code == ERR_FIELD_VALIDATION


def test_smdl01_10_integrity_sha_65_chars_raises_evidence_integrity():
    with pytest.raises(RegistryError) as exc_info:
        EvidenceRef(
            kind=EvidenceKind.HISTORICAL_OOS_EVAL,
            ref_id="r1",
            artifact_uri="uri:x",
            source_created_ts=now_instant(),
            correlation_id=VALID_ULIDISH,
            integrity_sha256="a" * 65,
        )
    assert exc_info.value.reason_code == ERR_EVIDENCE_INTEGRITY


def test_smdl01_10_integrity_sha_non_hex_raises_evidence_integrity():
    with pytest.raises(RegistryError) as exc_info:
        EvidenceRef(
            kind=EvidenceKind.HISTORICAL_OOS_EVAL,
            ref_id="r1",
            artifact_uri="uri:x",
            source_created_ts=now_instant(),
            correlation_id=VALID_ULIDISH,
            integrity_sha256="g" * 64,
        )
    assert exc_info.value.reason_code == ERR_EVIDENCE_INTEGRITY


def test_smdl01_10_integrity_sha_uppercase_hex_raises_evidence_integrity():
    with pytest.raises(RegistryError) as exc_info:
        EvidenceRef(
            kind=EvidenceKind.HISTORICAL_OOS_EVAL,
            ref_id="r1",
            artifact_uri="uri:x",
            source_created_ts=now_instant(),
            correlation_id=VALID_ULIDISH,
            integrity_sha256="A" * 64,
        )
    assert exc_info.value.reason_code == ERR_EVIDENCE_INTEGRITY


def test_smdl01_10_integrity_sha_64_lower_hex_ok():
    ev = EvidenceRef(
        kind=EvidenceKind.HISTORICAL_OOS_EVAL,
        ref_id="r1",
        artifact_uri="uri:x",
        source_created_ts=now_instant(),
        correlation_id=VALID_ULIDISH,
        integrity_sha256=VALID_SHA256,
    )
    assert ev.integrity_sha256 == VALID_SHA256


def test_smdl01_10_duplicate_kind_refid_append_raises_dup(fresh_registry):
    reg, _bus, _storage = fresh_registry
    mv_id, mv_ver = "mymodel", "1.0.0"

    e1 = _make_evidence(EvidenceKind.HISTORICAL_OOS_EVAL, ref_id="eval-a")
    reg.append_evidence(mv_id, mv_ver, e1)

    e2 = _make_evidence(EvidenceKind.HISTORICAL_OOS_EVAL, ref_id="eval-a")
    with pytest.raises(RegistryError) as exc_info:
        reg.append_evidence(mv_id, mv_ver, e2)
    assert exc_info.value.reason_code == ERR_EVIDENCE_REF_DUPLICATE


def test_smdl01_10_evidence_list_order_deterministic_kind_then_refid(fresh_registry):
    reg, _bus, _storage = fresh_registry
    mv_id, mv_ver = "mymodel", "1.0.0"

    items = [
        (EvidenceKind.WALK_FORWARD_RUN, "wf-z"),
        (EvidenceKind.HISTORICAL_OOS_EVAL, "eval-b"),
        (EvidenceKind.ARTIFACT_PACKAGE, "pkg-1"),
        (EvidenceKind.HISTORICAL_OOS_EVAL, "eval-a"),
        (EvidenceKind.WALK_FORWARD_RUN, "wf-a"),
    ]
    for kind, ref in items:
        reg.append_evidence(mv_id, mv_ver, _make_evidence(kind, ref_id=ref))

    listed = reg.list_evidence(mv_id, mv_ver)
    assert len(listed) == 5

    keys = [(e.kind.value, e.ref_id) for e in listed]
    expected = sorted(keys)
    assert keys == expected


def test_smdl01_10_evidence_kind_enum_members_match_spec():
    assert EvidenceKind.HISTORICAL_OOS_EVAL.value == "historical_oos_eval"
    assert EvidenceKind.WALK_FORWARD_RUN.value == "walk_forward_run"
    assert EvidenceKind.PAPER_REPLAY_EVAL.value == "paper_replay_eval"
    assert EvidenceKind.ARTIFACT_PACKAGE.value == "artifact_package"
    assert EvidenceKind.FEATURESET_REF.value == "featureset_ref"
    assert EvidenceKind.HYPERPARAMS_SNAPSHOT.value == "hyperparams_snapshot"
    assert EvidenceKind.COST_INJECTION_CONFIG.value == "cost_injection_config"
    assert len(EvidenceKind.__members__) == 7

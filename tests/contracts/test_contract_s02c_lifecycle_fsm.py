from __future__ import annotations

import pytest
from app.contracts.exceptions import ContractSchemaError
from app.contracts import (
    ModelLifecycleStatus,
    ModelLifecycleTransition,
)


# ---------------------------------------------------------------------------
# Base args helper (transition minimal valid)
# ---------------------------------------------------------------------------


def base_args(*, from_s, to_s) -> dict:
    return dict(
        transition_id="LT_0001_" + from_s + "_" + to_s,
        model_id="trend_dual_momentum",
        model_version="1.2.0",
        from_status=ModelLifecycleStatus(from_s),
        to_status=ModelLifecycleStatus(to_s),
        reason="Passed " + from_s + " → " + to_s + " evaluation gate",
        evidence_refs=["eval_run_id=E99", "paper_report_id=PR123"],
        requested_by="ml_engineer_01",
        approved_by="model_governance_board",
        requested_ts="2026-08-22T10:00:00.000Z",
        correlation_id="COR_MODEL_GOVERNANCE_FLOW",
        causation_id="PREVIOUS_EVENT_001",
        metadata={"voting_quorum": "5/7"},
    )


# ---------------------------------------------------------------------------
# C-22: 9 İZİNLİ transition — 9/9 PASS
# ---------------------------------------------------------------------------


ALLOWED = [
    ("candidate", "tested"),
    ("tested", "paper"),
    ("paper", "challenger"),
    ("challenger", "champion"),
    ("champion", "retired"),
    # Admin retire 4 tane
    ("candidate", "retired"),
    ("tested", "retired"),
    ("paper", "retired"),
    ("challenger", "retired"),
]


@pytest.mark.parametrize("from_s,to_s", ALLOWED)
def test_C22_9_allowed_transitions_pass(from_s, to_s):
    t = ModelLifecycleTransition(**base_args(from_s=from_s, to_s=to_s))
    assert t.from_status.value == from_s
    assert t.to_status.value == to_s


# ---------------------------------------------------------------------------
# FORBIDDEN 7 + 1 no-op = C-23..29
# ---------------------------------------------------------------------------


# C-23 F1: candidate → champion
def test_C23_F1_candidate_to_champion_FORBIDDEN():
    with pytest.raises(ContractSchemaError):
        ModelLifecycleTransition(**base_args(from_s="candidate", to_s="champion"))


# C-24 F2: paper → champion direkt
def test_C24_F2_paper_to_champion_direct_FORBIDDEN():
    with pytest.raises(ContractSchemaError):
        ModelLifecycleTransition(**base_args(from_s="paper", to_s="champion"))


# C-25 F3: tested → champion
def test_C25_F3_tested_to_champion_FORBIDDEN():
    with pytest.raises(ContractSchemaError):
        ModelLifecycleTransition(**base_args(from_s="tested", to_s="champion"))


# C-26 F4: Retired → Paper (ya da Retired HERHANGİ outbound)
def test_C26_F4_retired_to_any_FORBIDDEN():
    # Retired → Candidate, Paper, herhangi bir şeye RAISE
    for to_s in ["candidate", "tested", "paper", "challenger", "champion", "retired"]:
        with pytest.raises(ContractSchemaError):  # ya no-op ya da forbidden
            ModelLifecycleTransition(**base_args(from_s="retired", to_s=to_s))


# C-27 F5: Champion → Challenger (downgrade YOK)
def test_C27_F5_champion_to_challenger_FORBIDDEN():
    with pytest.raises(ContractSchemaError):
        ModelLifecycleTransition(**base_args(from_s="champion", to_s="challenger"))


# C-28 F6: Challenger → Paper default downgrade YOK
def test_C28_F6_challenger_to_paper_FORBIDDEN():
    with pytest.raises(ContractSchemaError):
        ModelLifecycleTransition(**base_args(from_s="challenger", to_s="paper"))


# Ek: tested → candidate GERİ DÖNÜŞ YOK (forbidden 7. — 7 tane)
def test_extra_tested_to_candidate_back_FORBIDDEN():
    with pytest.raises(ContractSchemaError):
        ModelLifecycleTransition(**base_args(from_s="tested", to_s="candidate"))


# C-29: same-status NO-OP RAISE
@pytest.mark.parametrize(
    "same_s",
    ["candidate", "tested", "paper", "challenger", "champion", "retired"],
)
def test_C29_same_status_noop_FORBIDDEN(same_s):
    with pytest.raises(ContractSchemaError):
        ModelLifecycleTransition(**base_args(from_s=same_s, to_s=same_s))


# ---------------------------------------------------------------------------
# C-52: Retired → Candidate DENEMESİ RAISE (H8'de ayrıca)
# ---------------------------------------------------------------------------


def test_C52_retired_to_candidate_raises():
    with pytest.raises(ContractSchemaError):
        ModelLifecycleTransition(**base_args(from_s="retired", to_s="candidate"))


# ---------------------------------------------------------------------------
# ModelLifecycleTransition kendi determinism 10x
# ---------------------------------------------------------------------------


def test_lifecycle_transition_10x_determinism():
    args = base_args(from_s="candidate", to_s="tested")
    t = ModelLifecycleTransition(**args)
    from app.contracts import schema_sha256

    digests = [schema_sha256(t) for _ in range(10)]
    assert len(set(digests)) == 1

"""TP-09 / AC-02,19 — version literal alignment (1.0.0 / CONTRACTS.md@1.0.0)."""

from __future__ import annotations

import app.contracts._sfnd06_constants as C
from app.contracts.sfnd05_api import ContractVersionStr
from app.contracts.sfnd06_serialize import (
    build_valid_envelope,
    canonical_json,
    canonical_loads,
)
from app.platform.config import VersionConstants as VC


def test_ac02_version_constants_contract_version_is_exactly_1_0_0():
    assert str(VC().contract_version) == "1.0.0"


def test_ac02_story_constant_matches_upstream_version_constants():
    assert C.CONTRACT_VERSION_STR == "1.0.0"
    assert C.CONTRACT_VERSION_STR == str(VC().contract_version)


def test_sfnd05_public_contract_version_newtype_is_1_0_0():
    assert ContractVersionStr("1.0.0") == "1.0.0"


def test_ac19_serialized_envelope_version_alignment():
    env = build_valid_envelope(event_type="market_tick.v1", payload={"price": "1"})
    parsed = canonical_loads(canonical_json(env))
    assert parsed["contract_version"] == "1.0.0"
    assert parsed["contract_version"] == str(VC().contract_version)
    assert parsed["schema_ref"]["contracts_md"] == "CONTRACTS.md@1.0.0"
    assert parsed["schema_ref"]["contracts_md"] == C.SCHEMA_REF_CONTRACTS_MD


def test_ac19_version_alignment_is_stable_over_10_runs():
    results = set()
    for _ in range(10):
        parsed = canonical_loads(
            canonical_json(
                build_valid_envelope(
                    event_type="market_tick.v1", payload={"price": "1"}
                )
            )
        )
        results.add((parsed["contract_version"], parsed["schema_ref"]["contracts_md"]))
    assert results == {("1.0.0", "CONTRACTS.md@1.0.0")}

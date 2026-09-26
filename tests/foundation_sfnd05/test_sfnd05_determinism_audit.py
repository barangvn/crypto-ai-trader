from __future__ import annotations

from dataclasses import astuple

import pytest

from app.contracts.envelope import CanonicalEventEnvelope
from app.contracts.quality_flags import QualityFlags
from tests.foundation_sfnd05._helpers import sha_json


def _envelope_tuple_list(n: int, build_valid_envelope) -> list[str]:
    out: list[str] = []
    for _ in range(n):
        env: CanonicalEventEnvelope = build_valid_envelope()
        t = (
            env.event_id,
            env.event_type,
            env.contract_version,
            env.symbol,
            env.source,
            env.timestamp,
            env.ingest_ts,
            env.correlation_id,
            env.causation_id,
            env.run_mode,
            env.source_type,
            (env.clock_ref.wall, env.clock_ref.replay),
            tuple(astuple(env.quality_flags)),
            (
                env.schema_ref.contracts_md,
                env.schema_ref.feature_version,
                env.schema_ref.strategy_version,
                env.schema_ref.model_id,
            ),
            env.trace_id,
            env.extra,
        )
        out.append(sha_json(t))
    return out


def _quality_tuple_list(n: int) -> list[str]:
    out: list[str] = []
    for _ in range(n):
        qf = QualityFlags(stale=True)
        out.append(sha_json(astuple(qf)))
    return out


def test_ac18_determinism_envelope_10x_unique_inputs(build_valid_envelope):
    digests = _envelope_tuple_list(10, build_valid_envelope)
    assert len(set(digests)) == 1


def test_determinism_qualityflags_degraded_autoset_10x():
    digests = _quality_tuple_list(10)
    assert len(set(digests)) == 1


def test_determinism_instant_regex_10x(build_valid_envelope):
    results = []
    for _ in range(10):
        try:
            build_valid_envelope(timestamp="2026-08-10T18:30:00+03:00")
            results.append("PASS")
        except Exception:
            results.append("FAIL")
    assert len(set(results)) == 1
    assert results[0] == "FAIL"


def test_determinism_enum_membership_10x(build_valid_envelope):
    results = []
    for _ in range(10):
        try:
            build_valid_envelope(run_mode="paper")
            results.append("PASS")
        except Exception:
            results.append("FAIL")
    assert len(set(results)) == 1
    assert results[0] == "PASS"


def test_determinism_version_alignment_10x(build_valid_envelope):
    from app.platform.config import VersionConstants
    results = []
    for _ in range(10):
        env = build_valid_envelope()
        vc = VersionConstants()
        results.append(env.contract_version == vc.contract_version)
    assert len(set(results)) == 1
    assert results[0] is True

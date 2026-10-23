"""TP-10 / D-01..D-07 — determinism audit: >=10 repetitions, full output tuple compare.

No wall-clock / random / filesystem ordering leakage: every helper output must be
byte-for-byte identical across repetitions for identical inputs.
"""

from __future__ import annotations

import random
from decimal import Decimal

from app.contracts.sfnd05_api import QualityFlags
from app.contracts.sfnd06_serialize import (
    build_quality,
    build_valid_envelope,
    canonical_json,
    canonical_symbol,
    envelope_fingerprint,
    ulid_compare,
)

OLDER = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
NEWER = "01ARZ3NDEKTSV4RRFFQ69G5FB2"

REPEATS = 10


def _full_envelope_output_tuple() -> tuple:
    """Full observable output tuple of one builder-produced envelope."""
    env = build_valid_envelope(event_type="market_tick.v1", payload={"price": "1"})
    return (
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
        (
            env.quality_flags.stale,
            env.quality_flags.missing,
            env.quality_flags.duplicate,
            env.quality_flags.out_of_order,
            env.quality_flags.invalid,
            env.quality_flags.quarantined,
            env.quality_flags.degraded,
            env.quality_flags.reasons,
        ),
        (
            env.schema_ref.contracts_md,
            env.schema_ref.feature_version,
            env.schema_ref.strategy_version,
            env.schema_ref.model_id,
        ),
        env.trace_id,
        env.extra,
        canonical_json(env),
    )


def test_d01_canonical_bytes_10x_set_len_1():
    digests = {
        canonical_json(
            build_valid_envelope(event_type="market_tick.v1", payload={"price": "1"})
        )
        for _ in range(REPEATS)
    }
    assert len(digests) == 1


def test_d02_fingerprint_10x_set_len_1():
    fingerprints = {
        envelope_fingerprint(
            build_valid_envelope(event_type="market_tick.v1", payload={"price": "1"})
        )
        for _ in range(REPEATS)
    }
    assert len(fingerprints) == 1
    fp = fingerprints.pop()
    assert len(fp) == 12
    assert all(c in "0123456789abcdef" for c in fp)


def test_full_output_tuple_10x_set_len_1():
    outputs = {_full_envelope_output_tuple() for _ in range(REPEATS)}
    assert len(outputs) == 1


def test_d03_ulid_compare_10x_same_result():
    results = {ulid_compare(OLDER, NEWER) for _ in range(REPEATS)}
    assert results == {-1}
    assert isinstance(next(iter(results)), int)


def test_d04_symbol_canonical_10x_same_output():
    results = {canonical_symbol("btc/usdt") for _ in range(REPEATS)}
    assert results == {"BTC_USDT"}


def test_d05_quality_builder_10x_same_flags_and_reasons():
    results = set()
    for _ in range(REPEATS):
        qf = build_quality(stale=True, reasons=[{"code": "S", "message": "m"}])
        results.add((qf.stale, qf.degraded, len(qf.reasons), qf.reasons[0].code))
    assert results == {(True, True, 1, "S")}
    assert isinstance(build_quality(stale=True), QualityFlags)


def test_d06_shuffled_key_order_is_irrelevant():
    base = {"z": 1, "a": {"y": 2, "b": 3}, "m": [{"q": 4, "c": 5}]}
    reference = canonical_json(base)
    rng = random.Random(1234)
    for _ in range(REPEATS):
        items = list(base.items())
        rng.shuffle(items)
        assert canonical_json(dict(items)) == reference


def test_d07_same_decimal_input_same_output():
    results = {canonical_json({"p": Decimal("123.456")}) for _ in range(REPEATS)}
    assert results == {b'{"p":"123.456"}'}

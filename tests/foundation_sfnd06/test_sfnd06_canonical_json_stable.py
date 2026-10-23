"""TP-02 / AC-03,04,05 — canonical JSON stability, fingerprint determinism, sort_keys.

AUD-01: byte-exact canonical output against a known fixture.
"""

from __future__ import annotations

from app.contracts.sfnd06_serialize import (
    canonical_json,
    canonical_loads,
    envelope_fingerprint,
)


def test_ac03_envelope_canonical_bytes_10x_identical(sample_valid_env_fixture):
    digests = {canonical_json(sample_valid_env_fixture) for _ in range(10)}
    assert len(digests) == 1


def test_ac04_envelope_fingerprint_10x_identical(sample_valid_env_fixture):
    fps = {envelope_fingerprint(sample_valid_env_fixture) for _ in range(10)}
    assert len(fps) == 1
    fp = fps.pop()
    assert len(fp) == 12
    assert all(c in "0123456789abcdef" for c in fp)


def test_ac05_shuffled_dict_equals_sorted_dict(
    sample_shuffled_dict, sample_sorted_dict
):
    assert canonical_json(sample_shuffled_dict) == canonical_json(sample_sorted_dict)


def test_aud01_byte_exact_fixture():
    # sort_keys=True + compact separators=(",", ":") + no whitespace.
    assert canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    assert canonical_json({"a": {"y": 2, "b": 3}}) == b'{"a":{"b":3,"y":2}}'
    assert canonical_json([3, 1, 2]) == b"[3,1,2]"  # sequence order IS data


def test_deep_key_order_is_sorted_hr09(sample_valid_env_fixture):
    payload = canonical_loads(canonical_json(sample_valid_env_fixture))
    # Every nested dict level must have sorted keys.
    def _assert_sorted(node):
        if isinstance(node, dict):
            keys = list(node.keys())
            assert keys == sorted(keys), f"unsorted keys: {keys}"
            for value in node.values():
                _assert_sorted(value)
        elif isinstance(node, list):
            for item in node:
                _assert_sorted(item)

    _assert_sorted(payload)


def test_canonical_loads_roundtrip(sample_shuffled_dict):
    assert canonical_loads(canonical_json(sample_shuffled_dict)) == sample_shuffled_dict

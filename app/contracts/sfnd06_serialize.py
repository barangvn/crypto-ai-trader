"""S-FND-06 public API — Deterministic Contract Serialization & Canonical Builders.

Entry point for all downstream consumers (S-RDH-01, S-CON-02, S-PLN-01,
S-FEA-03, ...). This module re-exports the story's public helpers from the
internal implementation modules; it contains no logic of its own.

Import path: `app.contracts.sfnd06_serialize`.

NOTE (documented SPEC count drift, D-06-A): the SPEC §6.1 heading / P01 / DoD#8 /
TP-01 describe the public API as "13 fonksiyon + 1 exception", but the §6.1
signature body explicitly defines 17 functions + 1 exception. Per "do not invent
behavior", the full §6.1 body is implemented and exported here — no function is
dropped and none is invented. `__all__` therefore holds 18 names.

No I/O, no network, no credentials, no DB/exchange, no dynamic execution, no
registry mutation, no third-party runtime dependency, no NOW() source
(fixture-only helper aside).
"""

from __future__ import annotations

from app.contracts._sfnd06_builders import (
    append_quality_reason,
    build_quality,
    build_valid_envelope,
    set_quality_flag,
)
from app.contracts._sfnd06_fingerprint import (
    envelope_fingerprint,
    payload_fingerprint,
)
from app.contracts._sfnd06_helpers import (
    canonical_symbol,
    is_canonical_symbol,
    now_instant_utc_fixture,
    ulid_compare,
    ulid_newer,
    ulid_older,
    validate_instant,
    validate_ulid_sortable,
)
from app.contracts._sfnd06_json import (
    CanonicalSerializationError,
    canonical_json,
    canonical_json_equal,
    canonical_loads,
)

__all__ = [
    "CanonicalSerializationError",
    "canonical_json",
    "canonical_loads",
    "canonical_json_equal",
    "envelope_fingerprint",
    "payload_fingerprint",
    "canonical_symbol",
    "is_canonical_symbol",
    "validate_instant",
    "now_instant_utc_fixture",
    "build_valid_envelope",
    "build_quality",
    "append_quality_reason",
    "set_quality_flag",
    "validate_ulid_sortable",
    "ulid_compare",
    "ulid_newer",
    "ulid_older",
]

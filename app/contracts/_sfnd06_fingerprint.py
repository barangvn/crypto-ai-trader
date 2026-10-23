"""S-FND-06 deterministic fingerprint helpers (CAP-SER-02).

Internal helper module. stdlib only (`hashlib`, `typing`) plus internal app
imports. No I/O. No network.

Fingerprint contract (HR-10): SHA-256 over canonical JSON bytes, truncated to
the FIRST 12 hex characters, lowercase. No MD5/RIPEMD160/other algorithm.
"""

from __future__ import annotations

import hashlib
from typing import Any

from app.contracts._sfnd06_json import CanonicalSerializationError, canonical_json
from app.contracts.sfnd05_api import CanonicalEventEnvelope

FINGERPRINT_LENGTH = 12


def _fingerprint(obj: Any) -> str:
    digest = hashlib.sha256(canonical_json(obj)).hexdigest()
    return digest[:FINGERPRINT_LENGTH]


def envelope_fingerprint(env: "CanonicalEventEnvelope", /) -> str:
    """Return 12 lowercase hex chars: `SHA256(canonical_json(env))[:12]`.

    OD-06-06 DEFAULT: hash covers the WHOLE envelope (all 16 fields + payload).
    Fail-closed (FC-15): a non-envelope argument raises CanonicalSerializationError.
    """
    if not isinstance(env, CanonicalEventEnvelope):
        raise CanonicalSerializationError(
            "envelope_fingerprint requires a CanonicalEventEnvelope instance; got "
            f"{type(env).__name__} (fail-closed FC-15)"
        )
    return _fingerprint(env)


def payload_fingerprint(payload: Any, /) -> str:
    """Generic payload fingerprint (same algorithm); helper for S-FEA-03 leakage lock."""
    return _fingerprint(payload)


__all__ = ["envelope_fingerprint", "payload_fingerprint", "FINGERPRINT_LENGTH"]

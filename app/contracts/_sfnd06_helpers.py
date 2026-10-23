"""S-FND-06 symbol / instant / ULID helpers (CAP-SER-03 / 04 / 07).

Internal helper module. stdlib only (`datetime`, `typing`) plus internal app
imports. Regex constants come from this story's single-source copy in
`app/contracts/_sfnd06_constants.py` (OD-06-08 default two-sequence strategy:
S-FND-05 public API does not export the raw regex constants).

Hard-red:
  - HR-11: no production NOW() source. `datetime.now` appears ONLY inside
    `now_instant_utc_fixture`, which is explicitly fixture/replay-only.
  - HR-13: symbols are NEVER sanitized. Strict accept/reject gate only.
"""

from __future__ import annotations

import datetime as _datetime

from app.contracts._sfnd06_constants import (
    INSTANT_RGX,
    SYMBOL_RGX,
    ULID_CROCKFORD_RGX,
    UUID7_RGX,
)
from app.contracts.sfnd05_api import (
    ContractValidationError,
    Instant,
    SymbolCanonical,
    ULID_SORTABLE,
)

# Same value as app/contracts/types.py::_COMMON_QUOTES (reference only; no import
# of the legacy non-frozen type system).
_COMMON_QUOTES: tuple[str, ...] = ("USDT", "BUSD", "USDC", "BTC", "ETH")


def canonical_symbol(raw: str, /) -> "SymbolCanonical":
    """Return the canonical BASE_QUOTE form of `raw`.

    Accepted input variants: `btcusdt`, `BTC/USDT`, `BTC-USDT`, `btc_usdt`.
    Non-matching input raises ContractValidationError (ValueError subclass).
    Strict accept/reject gate — input is NEVER sanitized (HR-13, FC-13).
    """
    if not isinstance(raw, str):
        raise ContractValidationError("[symbol] must be str")
    if not raw:
        raise ContractValidationError("[symbol] must be a non-empty str")

    upper = raw.upper()
    candidate: str | None = None
    if "/" in upper:
        candidate = upper.replace("/", "_")
    elif "-" in upper:
        candidate = upper.replace("-", "_")
    elif "_" in upper:
        candidate = upper
    else:
        for quote in _COMMON_QUOTES:
            if upper.endswith(quote) and len(upper) > len(quote):
                candidate = f"{upper[: -len(quote)]}_{quote}"
                break

    if candidate is None or SYMBOL_RGX.match(candidate) is None:
        raise ContractValidationError(
            f"[symbol] {raw!r} is not a valid BASE_QUOTE symbol; strict accept/reject "
            "only, no sanitization (fail-closed HR-13/FC-13)"
        )
    return SymbolCanonical(candidate)


def is_canonical_symbol(s: str, /) -> bool:
    """Return True iff `s` already matches the canonical BASE_QUOTE regex (no raise)."""
    return isinstance(s, str) and SYMBOL_RGX.match(s) is not None


def validate_instant(raw: str, /) -> "Instant":
    """Return `raw` as an Instant if it matches the S-FND-05 INSTANT regex.

    Z suffix is mandatory; UTC offsets (`+HH:MM`) are rejected; fractional digits
    are limited to 1-6. Otherwise raises (fail-closed FC-14).
    """
    if not isinstance(raw, str):
        raise ContractValidationError("[instant] must be str")
    if INSTANT_RGX.match(raw) is None:
        raise ContractValidationError(
            "[instant] must match ISO-8601 UTC with a mandatory 'Z' suffix and "
            "optional 1-6 fractional digits (offsets disallowed), e.g. "
            "2026-08-10T18:30:00Z or 2026-08-10T18:30:00.123Z"
        )
    return Instant(raw)


def now_instant_utc_fixture(*, _clock: object = None) -> "Instant":
    """FIXTURE-ONLY UTC ISO-8601 'Z' instant with 3-digit fractional ms.

    NOT a production clock source (HR-11). S-RDH-01 ingest owns the real NOW()
    source; this helper exists for tests and replay fixtures only.
    `_clock` may be injected (a `datetime`, or a callable returning one) so tests
    never depend on wall-clock time.
    """
    if _clock is None:
        moment = _datetime.datetime.now(_datetime.timezone.utc)
    elif callable(_clock):
        moment = _clock()
    else:
        moment = _clock

    if not isinstance(moment, _datetime.datetime):
        raise ContractValidationError(
            "[now_instant_utc_fixture._clock] must be a datetime or a callable "
            "returning a datetime"
        )
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_datetime.timezone.utc)
    else:
        moment = moment.astimezone(_datetime.timezone.utc)

    millis = moment.microsecond // 1000
    text = moment.strftime("%Y-%m-%dT%H:%M:%S") + f".{millis:03d}Z"
    return Instant(text)


def validate_ulid_sortable(raw: str, /) -> "ULID_SORTABLE":
    """Return `raw` as ULID_SORTABLE if it matches ULID (Crockford) or UUIDv7 format."""
    if not isinstance(raw, str):
        raise ContractValidationError("[ulid] must be str")
    if ULID_CROCKFORD_RGX.match(raw) is None and UUID7_RGX.match(raw) is None:
        raise ContractValidationError(
            "[ulid] must be a ULID (Crockford Base32, 26 chars) or a UUIDv7 string"
        )
    return ULID_SORTABLE(raw)


def _format_of(raw: str) -> str:
    if UUID7_RGX.match(raw) is not None:
        return "uuid7"
    if ULID_CROCKFORD_RGX.match(raw) is not None:
        return "ulid"
    return "unknown"


def ulid_compare(a: str, b: str, /) -> int:
    """Lexicographic compare of two sortable IDs. Returns -1, 0 or 1.

    Both arguments are validated first. Comparing across formats (ULID vs UUIDv7)
    is not meaningful and raises TypeError (GAP-06-06).
    """
    validate_ulid_sortable(a)
    validate_ulid_sortable(b)
    format_a = _format_of(a)
    format_b = _format_of(b)
    if format_a != format_b:
        raise TypeError(
            "ulid_compare does not support mixing formats: "
            f"{format_a!r} vs {format_b!r} (GAP-06-06)"
        )
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def ulid_newer(a: str, b: str, /) -> bool:
    """True iff `a` sorts after `b`."""
    return ulid_compare(a, b) > 0


def ulid_older(a: str, b: str, /) -> bool:
    """True iff `a` sorts before `b`."""
    return ulid_compare(a, b) < 0


__all__ = [
    "canonical_symbol",
    "is_canonical_symbol",
    "validate_instant",
    "now_instant_utc_fixture",
    "validate_ulid_sortable",
    "ulid_compare",
    "ulid_newer",
    "ulid_older",
]

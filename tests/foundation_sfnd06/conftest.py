from __future__ import annotations

from typing import Any

import pytest

from app.contracts.sfnd06_serialize import build_valid_envelope


@pytest.fixture
def sample_valid_env_fixture():
    """A builder-produced valid S-FND-05 envelope (deterministic fixture defaults)."""
    return build_valid_envelope(event_type="market_tick.v1", payload={"price": "1"})


@pytest.fixture
def sample_shuffled_dict() -> dict[str, Any]:
    """Deliberately unsorted insertion order (deep)."""
    return {"z": 1, "a": {"y": 2, "b": 3}, "m": [{"q": 4, "c": 5}]}


@pytest.fixture
def sample_sorted_dict() -> dict[str, Any]:
    """Same key/value pairs as `sample_shuffled_dict`, deep-sorted insertion order."""
    return {"a": {"b": 3, "y": 2}, "m": [{"c": 5, "q": 4}], "z": 1}


@pytest.fixture
def sample_instant_strings() -> dict[str, str]:
    return {
        "valid_z_3": "2026-01-01T00:00:00.123Z",
        "valid_z_none": "2026-08-10T18:30:00Z",
        "valid_z_6": "2026-08-10T18:30:00.123456Z",
        "offset": "2026-01-01T00:00:00+03:00",
        "no_z": "2026-01-01T00:00:00",
        "frac7": "2026-01-01T00:00:00.1234567Z",
    }


@pytest.fixture
def clean_no_now_mock(monkeypatch):
    """HR-11 guard.

    Replaces the helpers module's `datetime` with a shim whose `datetime.now`
    raises, proving the production helper never reads wall-clock time. Returns
    the shim datetime class so tests can still build compatible injected values.
    """
    import datetime as real_datetime

    import app.contracts._sfnd06_helpers as helpers

    class _NoNowDatetime(real_datetime.datetime):
        @classmethod
        def now(cls, tz=None):  # pragma: no cover - must never execute
            raise AssertionError("wall-clock NOW() blocked in tests (HR-11)")

    class _Shim:
        datetime = _NoNowDatetime
        timezone = real_datetime.timezone

    monkeypatch.setattr(helpers, "_datetime", _Shim)
    return _NoNowDatetime

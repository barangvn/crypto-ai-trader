"""TP-05 / AC-11,12,13 / FC-14 / HR-11 — instant validation + fixture generator."""

from __future__ import annotations

import datetime as _datetime
import re

import pytest

from app.contracts.sfnd06_serialize import now_instant_utc_fixture, validate_instant

INSTANT_RGX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$")


@pytest.mark.parametrize(
    "value",
    [
        "2026-01-01T00:00:00.123Z",
        "2026-08-10T18:30:00Z",
        "2026-08-10T18:30:00.123456Z",
    ],
)
def test_ac11_valid_utc_z_passes_through(value):
    assert validate_instant(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "2026-01-01T00:00:00+03:00",
        "2026-01-01T00:00:00",
        "2026-01-01T00:00:00.1234567Z",
        "2026-01-01T00:00:00.123+00:00",
        "not-an-instant",
    ],
)
def test_ac12_invalid_instant_raises(value):
    with pytest.raises(ValueError):
        validate_instant(value)


def test_ac12_regex_is_structural_not_calendar():
    # The shared S-FND-05 INSTANT regex is structural (\d{2} month/day digits),
    # not a calendar validator -> a structurally valid but impossible date passes.
    assert validate_instant("2026-13-01T00:00:00Z") == "2026-13-01T00:00:00Z"


def test_ac12_offset_without_z_raises():
    with pytest.raises(ValueError):
        validate_instant("2026-01-01T00:00:00+03:00")


def test_ac13_fixture_generator_ends_with_z_and_matches_regex():
    result = now_instant_utc_fixture()
    assert result.endswith("Z")
    assert INSTANT_RGX.match(result) is not None
    # GAP-06-07: 3-digit fractional milliseconds.
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$", result)


def test_ac13_fixture_generator_injected_clock_is_deterministic():
    fixed = _datetime.datetime(2026, 8, 10, 18, 30, 0, 123000, tzinfo=_datetime.timezone.utc)
    outputs = {now_instant_utc_fixture(_clock=fixed) for _ in range(10)}
    assert len(outputs) == 1
    assert outputs.pop() == "2026-08-10T18:30:00.123Z"


def test_ac13_fixture_generator_accepts_callable_clock():
    fixed = _datetime.datetime(2026, 1, 1, 0, 0, 0, 5000, tzinfo=_datetime.timezone.utc)
    assert now_instant_utc_fixture(_clock=lambda: fixed) == "2026-01-01T00:00:00.005Z"


def test_fc14_fractional_digit_bounds():
    assert validate_instant("2026-01-01T00:00:00.1Z")
    assert validate_instant("2026-01-01T00:00:00.123456Z")
    with pytest.raises(ValueError):
        validate_instant("2026-01-01T00:00:00.1234567Z")


def test_hr11_wall_clock_now_is_blocked_under_guard(clean_no_now_mock):
    # Under the HR-11 guard, the fixture generator cannot fall back to real time.
    with pytest.raises(AssertionError):
        now_instant_utc_fixture()

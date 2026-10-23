"""TP-03 / AC-06,07 / FC-09,10 — Decimal, unknown types, circular refs (fail-closed)."""

from __future__ import annotations

import datetime as _datetime
from decimal import Decimal

import pytest

from app.contracts.sfnd06_serialize import (
    CanonicalSerializationError,
    canonical_json,
    canonical_json_equal,
    canonical_loads,
)


def test_ac06_decimal_to_plain_string_no_exponent():
    raw = canonical_json({"price": Decimal("123.456")}).decode("utf-8")
    assert '"123.456"' in raw
    # The serialized numeric value must not use scientific exponent notation.
    value = canonical_loads(raw)["price"]
    assert "E" not in value and "e" not in value
    assert value == "123.456"


def test_od0602_decimal_preserves_original_string():
    # OD-06-02 DEFAULT: preserve original string; no normalisation.
    raw = canonical_json({"price": Decimal("123.456000")}).decode("utf-8")
    assert '"123.456000"' in raw


def test_ac07_circular_reference_raises():
    cyclic: dict = {"b": None}
    cyclic["b"] = cyclic
    with pytest.raises(CanonicalSerializationError):
        canonical_json(cyclic)


def test_fc09_datetime_is_rejected():
    with pytest.raises(CanonicalSerializationError):
        canonical_json({"ts": _datetime.datetime(2026, 1, 1)})


def test_fc09_set_is_rejected():
    with pytest.raises(CanonicalSerializationError):
        canonical_json({"s": {1, 2, 3}})


def test_fc09_bytes_is_rejected():
    with pytest.raises(CanonicalSerializationError):
        canonical_json({"b": b"raw"})


def test_fc09_non_str_key_is_rejected():
    with pytest.raises(CanonicalSerializationError):
        canonical_json({1: "a"})


def test_nan_and_inf_are_rejected():
    with pytest.raises(CanonicalSerializationError):
        canonical_json({"x": float("nan")})
    with pytest.raises(CanonicalSerializationError):
        canonical_json({"x": float("inf")})


def test_canonical_json_equal_semantics():
    assert canonical_json_equal({"a": 1, "b": 2}, {"b": 2, "a": 1}) is True
    assert canonical_json_equal({"a": 1}, {"a": 2}) is False


def test_bool_lowercase_and_none_null():
    assert canonical_json({"f": False, "t": True, "n": None}) == b'{"f":false,"n":null,"t":true}'

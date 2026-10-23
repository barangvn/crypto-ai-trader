"""TP-04 / AC-08,09,10 / HR-13 / FC-13 — symbol canonical strict gate (no sanitize)."""

from __future__ import annotations

import pytest

from app.contracts.sfnd06_serialize import canonical_symbol, is_canonical_symbol

VALID_VARIANTS = [
    ("btcusdt", "BTC_USDT"),
    ("BTCUSDT", "BTC_USDT"),
    ("BTC/USDT", "BTC_USDT"),
    ("BTC-USDT", "BTC_USDT"),
    ("btc_usdt", "BTC_USDT"),
    ("btc/usdt", "BTC_USDT"),
    ("ethusdt", "ETH_USDT"),
    ("solusdt", "SOL_USDT"),
]

INVALID_INPUTS = [
    "",
    "BTC",
    "USDT",
    "<script>alert(1)</script>",
    "BTC/USDT'; DROP TABLE symbols--",
    "btc_usdt<script>",
    "BTC_USDT;",
    "BTC USDT",
    "BTC_USDT ",
    "A_B",
    "BTC_USDT_X",
]


@pytest.mark.parametrize("raw,expected", VALID_VARIANTS)
def test_ac08_ac09_canonical_forms(raw, expected):
    result = canonical_symbol(raw)
    assert result == expected
    assert is_canonical_symbol(result) is True


@pytest.mark.parametrize("raw", INVALID_INPUTS)
def test_ac10_invalid_raises_no_sanitize(raw):
    with pytest.raises(ValueError):
        canonical_symbol(raw)


def test_hr13_no_silent_sanitization():
    # A sanitizer would strip tags and return BTC_USDT; we must reject instead.
    with pytest.raises(ValueError):
        canonical_symbol("btc_usdt<script>")


def test_non_str_input_raises():
    with pytest.raises(ValueError):
        canonical_symbol(123)  # type: ignore[arg-type]


def test_is_canonical_symbol_never_raises():
    assert is_canonical_symbol("BTC_USDT") is True
    assert is_canonical_symbol("btcusdt") is False
    assert is_canonical_symbol(None) is False  # type: ignore[arg-type]


def test_gap0603_quote_required():
    with pytest.raises(ValueError):
        canonical_symbol("BTC")

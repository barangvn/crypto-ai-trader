from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
str(ROOT) not in sys.path and sys.path.insert(0, str(ROOT))

from app.contracts.exceptions import ContractSchemaError  # noqa: E402
from app.contracts.feature import (  # noqa: E402
    FEATURE_SCHEMA_REGISTRY,
    FeatureVector,
    LookbackWindowSpec,
)
from app.contracts.market import Candle  # noqa: E402
from app.contracts.types import Instant  # noqa: E402
from app.features import FeatureEngine, SFEA01_FEATURE_VERSION, SFEA01_SCHEMA_SPEC  # noqa: E402


def _ts(secs: int) -> Instant:
    import datetime
    epoch_ms = secs * 1000 + 1725000000000
    dt = datetime.datetime.fromtimestamp(epoch_ms / 1000.0, tz=datetime.timezone.utc)
    s = dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{epoch_ms % 1000:03d}Z"
    return Instant(s)


def _make_candle(
    idx: int,
    open_: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.0,
    volume: float = 1_000_000.0,
    closed: bool = True,
) -> Candle:
    t0 = 3600
    return Candle(
        timeframe="1h",
        open_time=_ts(idx * t0),
        close_time=_ts((idx + 1) * t0),
        open=Decimal(str(open_)),
        high=Decimal(str(high)),
        low=Decimal(str(low)),
        close=Decimal(str(close)),
        volume=Decimal(str(volume)),
        closed=closed,
    )


def _n_candles(n: int, base_close: float = 100.0, step: float = 0.0) -> list[Candle]:
    arr: list[Candle] = []
    for i in range(n):
        c = base_close + step * i
        arr.append(
            _make_candle(
                idx=i,
                open_=c - 0.5,
                high=c + 0.5,
                low=c - 0.5,
                close=c,
                volume=1_000_000.0,
            )
        )
    return arr


class TestHappyC01:  # C01 happy path
    def test_c01_fifty_closed_sorted_ok(self):
        eng = FeatureEngine()
        candles = _n_candles(50)
        fv = eng.calculate("BTC_USDT", candles, timeframe="1h")
        assert isinstance(fv, FeatureVector)
        assert fv.feature_version == SFEA01_FEATURE_VERSION
        for k in SFEA01_SCHEMA_SPEC.required_keys:
            assert k in fv.features


class TestC02Empty:
    def test_c02_empty_raises(self):
        eng = FeatureEngine()
        with pytest.raises(ContractSchemaError, match="empty"):
            eng.calculate("BTC_USDT", [])


class TestC03Sorting:
    def test_c03_desc_sorted_raises(self):
        eng = FeatureEngine()
        candles = list(reversed(_n_candles(20)))
        with pytest.raises(ContractSchemaError, match="not sorted|ascending"):
            eng.calculate("X", candles)


class TestC04Duplicate:
    def test_c04_dup_open_time_raises(self):
        eng = FeatureEngine()
        c1 = _make_candle(0)
        c2 = _make_candle(0)
        c3 = _make_candle(1)
        with pytest.raises(ContractSchemaError, match="duplicate"):
            eng.calculate("X", [c1, c2, c3])


class TestC05ClosedStrict:
    def test_c05_partial_closed_false_strict_raises(self):
        eng = FeatureEngine(strict_closed_only=True)
        candles = _n_candles(5) + [_make_candle(5, closed=False)]
        with pytest.raises(ContractSchemaError, match="closed=False"):
            eng.calculate("X", candles)

    def test_c05_nonstrict_partial_ok(self):
        eng = FeatureEngine(strict_closed_only=False)
        candles = _n_candles(50)
        candles[-1] = Candle(
            timeframe=candles[-1].timeframe,
            open_time=candles[-1].open_time,
            close_time=candles[-1].close_time,
            open=candles[-1].open,
            high=candles[-1].high,
            low=candles[-1].low,
            close=candles[-1].close,
            volume=candles[-1].volume,
            closed=False,
        )
        fv = eng.calculate("X", candles)
        assert isinstance(fv, FeatureVector)


class TestC06OhlcvValidation:
    def test_c06_high_less_than_low_raises(self):
        eng = FeatureEngine()
        c_bad = _make_candle(0, high=50.0, low=55.0)
        c_next = _make_candle(1)
        with pytest.raises(ContractSchemaError, match="high<low"):
            eng.calculate("X", [c_bad, c_next])

    def test_c06_non_positive_close_raises(self):
        eng = FeatureEngine()
        candles = _n_candles(5)
        bad = Candle(
            timeframe=candles[-1].timeframe,
            open_time=_ts(6 * 3600),
            close_time=_ts(7 * 3600),
            open=Decimal("99"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("0"),
            volume=Decimal("1000"),
            closed=True,
        )
        with pytest.raises(ContractSchemaError, match="non-positive price"):
            eng.calculate("X", candles + [bad])


class TestC07VersionAttr:
    def test_c07_version_constant(self):
        assert FeatureEngine().feature_version == "fea_01_v1"
        assert SFEA01_FEATURE_VERSION == "fea_01_v1"


class TestC08Registry:
    def test_c08_registry_has_fea_01_v1(self):
        assert SFEA01_FEATURE_VERSION in FEATURE_SCHEMA_REGISTRY
        spec = FEATURE_SCHEMA_REGISTRY[SFEA01_FEATURE_VERSION]
        assert len(spec.required_keys) == 12
        for k in spec.required_keys:
            assert k in spec.key_types
            assert spec.key_types[k] is float
            assert k in spec.allowed_keys


class TestC09ValidateAgainstRegistry:
    def test_c09_registry_validate_empty_reasons(self):
        eng = FeatureEngine()
        fv = eng.calculate("BTC", _n_candles(100))
        reasons = fv.validate_against_registry()
        assert reasons == []


class TestC10LookbackMetadata:
    def test_c10_lookback_200(self):
        eng = FeatureEngine(default_lookback=200)
        fv = eng.calculate("BTC", _n_candles(200), lookback=200)
        assert isinstance(fv.lookback_window, LookbackWindowSpec)
        assert fv.lookback_window.count == 200
        assert fv.lookback_window.timeframe == "1h"


class TestC11LookbackDefault:
    def test_c11_default_max_window(self):
        eng = FeatureEngine(default_lookback=20)
        candles = _n_candles(200)
        fv = eng.calculate("BTC", candles)
        assert fv.lookback_window.count in (20, 200)


class TestC12InputRefs:
    def test_c12_input_refs_ulidish_length(self):
        candles = _n_candles(200)
        eng = FeatureEngine()
        fv = eng.calculate("BTC", candles, lookback=200)
        assert len(fv.input_refs) == 200
        all_ulid = all(isinstance(r, str) and len(r) >= 8 for r in fv.input_refs)
        assert all_ulid


class TestC13InputRefsChronOrder:
    def test_c13_chronological_no_future(self):
        candles = [
            _make_candle(i, close=100.0 + i * 0.1) for i in range(200)
        ]
        eng = FeatureEngine()
        fv = eng.calculate("BTC", candles, lookback=200)
        assert len(fv.input_refs) == 200


class TestC14NullCount:
    def test_c14_null_count_matches_actual(self):
        eng = FeatureEngine()
        candles = _n_candles(15, step=0.1)
        fv = eng.calculate("X", candles)
        actual_nones = sum(1 for v in fv.features.values() if v is None)
        assert fv.null_count == actual_nones


class TestC15DeterminismPair:
    def test_c15_sorted_dict_pair_eq(self):
        candles = _n_candles(100, step=0.2)
        eng = FeatureEngine()
        fv1 = eng.calculate("BTC", candles)
        fv2 = eng.calculate("BTC", candles)
        assert fv1.to_sorted_dict() == fv2.to_sorted_dict()
        assert fv1.schema_sha256() == fv2.schema_sha256()


class TestC16RegistryBounds:
    def test_c16_close_raw_bound_violation(self):
        eng = FeatureEngine()
        fv = eng.calculate("BTC", _n_candles(30))
        fv.features["close_raw"] = 1e-12
        reasons = fv.validate_against_registry()
        assert any("close_raw" in r for r in reasons)

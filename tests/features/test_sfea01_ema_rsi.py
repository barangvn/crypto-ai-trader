from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
str(ROOT) not in sys.path and sys.path.insert(0, str(ROOT))

from app.contracts.exceptions import ContractSchemaError  # noqa: E402
from app.contracts.feature import FeatureVector  # noqa: E402
from app.contracts.market import Candle  # noqa: E402
from app.contracts.types import Instant  # noqa: E402
from app.features.engine import FeatureEngine  # noqa: E402


def _ts(secs: int) -> Instant:
    import datetime
    epoch_ms = secs * 1000 + 1725000000000
    dt = datetime.datetime.fromtimestamp(epoch_ms / 1000.0, tz=datetime.timezone.utc)
    s = dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{epoch_ms % 1000:03d}Z"
    return Instant(s)


def _c_close(idx: int, close: float) -> Candle:
    return Candle(
        timeframe="1h",
        open_time=_ts(idx * 3600),
        close_time=_ts((idx + 1) * 3600),
        open=Decimal(str(close - 0.5)),
        high=Decimal(str(close + 0.5)),
        low=Decimal(str(close - 0.5)),
        close=Decimal(str(close)),
        volume=Decimal("1000000"),
        closed=True,
    )


def _candles_from_close(values: list[float]) -> list[Candle]:
    return [_c_close(i, v) for i, v in enumerate(values)]


class TestC17EmaConstant:
    def test_c17_ema_14_constant_10(self):
        closes = [10.0] * 16
        result = FeatureEngine._compute_ema(closes, 14)
        assert result[13] == pytest.approx(10.0)
        assert result[14] == pytest.approx(10.0)
        assert result[15] == pytest.approx(10.0)


class TestC18EmaInsufficient:
    def test_c18_ema_insufficient_len_10(self):
        closes = [10.0] * 10
        result = FeatureEngine._compute_ema(closes, 14)
        assert result[9] is None
        assert all(v is None for v in result)


class TestC19EmaLinear:
    def test_c19_ema_linear_1_through_500(self):
        closes = [float(i) for i in range(1, 501)]
        result = FeatureEngine._compute_ema(closes, 14)
        seed_expected = sum(range(1, 15)) / 14.0
        assert result[13] == pytest.approx(seed_expected)
        alpha = 2.0 / 15.0
        expected_t14 = alpha * closes[14] + (1.0 - alpha) * result[13]
        assert result[14] == pytest.approx(expected_t14)

    def test_c19_fv_ema_14_from_engine(self):
        closes = [float(i) for i in range(1, 101)]
        candles = _candles_from_close(closes)
        eng = FeatureEngine()
        fv = eng.calculate("BTC", candles, lookback=100)
        ema_expected = FeatureEngine._compute_ema(closes, 14)[-1]
        assert fv.features["ema_14"] == pytest.approx(ema_expected)


class TestC20RsiAllUp:
    def test_c20_rsi_zero_loss(self):
        closes = [10.0 + 1.0 * i for i in range(30)]
        result = FeatureEngine._compute_rsi(closes, 14)
        last = result[-1]
        assert isinstance(last, float)
        assert last == pytest.approx(100.0)


class TestC21RsiAllDown:
    def test_c21_rsi_zero_gain(self):
        closes = [100.0 - 1.0 * i for i in range(30)]
        result = FeatureEngine._compute_rsi(closes, 14)
        last = result[-1]
        assert isinstance(last, float)
        assert last == pytest.approx(0.0)


class TestC22RsiInsufficient:
    def test_c22_rsi_n_less_than_period(self):
        closes = [10.0] * 10
        result = FeatureEngine._compute_rsi(closes, 14)
        assert result[9] is None


class TestC23RsiOscillating:
    def test_c23_rsi_range_0_100(self):
        closes: list[float] = []
        for i in range(50):
            closes.append(100.0 + ((i % 4) - 1.5) * 2.0)
        result = FeatureEngine._compute_rsi(closes, 14)
        last = result[-1]
        assert isinstance(last, float)
        assert 0.0 <= last <= 100.0
        candles = _candles_from_close(closes)
        eng = FeatureEngine()
        fv = eng.calculate("X", candles, lookback=50)
        r = fv.features["rsi_14"]
        assert isinstance(r, float)
        assert 0.0 <= r <= 100.0
        reasons = fv.validate_against_registry()
        assert reasons == []


class TestC24C25RsiRegistryBounds:
    def test_c24_rsi_above_100_invalid(self):
        eng = FeatureEngine()
        candles = _candles_from_close([100.0 + i for i in range(50)])
        fv = eng.calculate("X", candles)
        fv.features["rsi_14"] = 150.0
        reasons = fv.validate_against_registry()
        assert any("rsi_14" in r and "max" in r for r in reasons)

    def test_c25_rsi_below_0_invalid(self):
        eng = FeatureEngine()
        candles = _candles_from_close([100.0 + i for i in range(50)])
        fv = eng.calculate("X", candles)
        fv.features["rsi_14"] = -5.0
        reasons = fv.validate_against_registry()
        assert any("rsi_14" in r and "min" in r for r in reasons)


class TestC26EmaRsiDeterminism10x:
    def test_c26_determinism_10x_ema_rsi(self):
        closes: list[float] = []
        for i in range(200):
            closes.append(100.0 + (i % 17) * 0.7 + (i % 13) * 0.13)
        candles = _candles_from_close(closes)
        eng = FeatureEngine()
        fvs = [eng.calculate("BTC", candles, lookback=200) for _ in range(10)]
        sha_s = [f.schema_sha256() for f in fvs]
        dicts = [f.to_sorted_dict() for f in fvs]
        for d in dicts[1:]:
            assert d == dicts[0]
        assert len(set(sha_s)) == 1


@pytest.mark.parametrize("i", list(range(10)))
def test_param_rsi_formula_10_variants(i: int):
    n = 20 + i * 3
    closes = [100.0 + 0.3 * j + 0.01 * (j % 5) for j in range(n)]
    rsi_series = FeatureEngine._compute_rsi(closes, 14)
    last = rsi_series[-1]
    if last is None:
        assert n <= 14
    else:
        assert 0.0 <= last <= 100.0

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
str(ROOT) not in sys.path and sys.path.insert(0, str(ROOT))

from app.contracts.market import Candle  # noqa: E402
from app.contracts.types import Instant  # noqa: E402
from app.features.engine import FeatureEngine  # noqa: E402


def _ts(secs: int) -> Instant:
    import datetime
    epoch_ms = secs * 1000 + 1725000000000
    dt = datetime.datetime.fromtimestamp(epoch_ms / 1000.0, tz=datetime.timezone.utc)
    s = dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{epoch_ms % 1000:03d}Z"
    return Instant(s)


def _make_ohlcv(idx: int, o: float, h: float, l: float, c: float, v: float) -> Candle:
    return Candle(
        timeframe="1h",
        open_time=_ts(idx * 3600),
        close_time=_ts((idx + 1) * 3600),
        open=Decimal(str(o)),
        high=Decimal(str(h)),
        low=Decimal(str(l)),
        close=Decimal(str(c)),
        volume=Decimal(str(v)),
        closed=True,
    )


class TestC27ATRTrueRange:
    def test_c27_tr_single(self):
        highs = [0.0, 50.0]
        lows = [0.0, 40.0]
        closes = [45.0, 46.0]
        result = FeatureEngine._compute_atr(highs, lows, closes, 1)
        tr_t1 = max(50 - 40, abs(50 - 45), abs(40 - 45))
        assert tr_t1 == 10.0
        assert result[1] == pytest.approx(tr_t1)


class TestC28ATRInsufficient:
    def test_c28_atr_insufficient(self):
        n = 10
        h = [100.0 + i for i in range(n)]
        l = [90.0 + i for i in range(n)]
        c = [95.0 + i for i in range(n)]
        result = FeatureEngine._compute_atr(h, l, c, 14)
        assert result[9] is None


class TestC29ATRUniform:
    def test_c29_atr_uniform_10(self):
        n = 50
        h = [50.0] * n
        l = [40.0] * n
        c = [45.0] * n
        result = FeatureEngine._compute_atr(h, l, c, 14)
        final = result[-1]
        assert isinstance(final, float)
        assert final == pytest.approx(10.0, rel=1e-3)

    def test_c29_fv_atr_min_bound(self):
        candles = [
            _make_ohlcv(i, 95.0, 105.0, 90.0, 100.0, 1_000_000.0) for i in range(100)
        ]
        fv = FeatureEngine().calculate("BTC", candles, lookback=100)
        atr = fv.features["atr_14"]
        assert isinstance(atr, float)
        assert atr >= 0.0


class TestC30ATRMinBound:
    def test_c30_atr_negative_invalid(self):
        candles = [
            _make_ohlcv(i, 95.0, 105.0, 90.0, 100.0, 1_000_000.0) for i in range(50)
        ]
        fv = FeatureEngine().calculate("BTC", candles, lookback=50)
        fv.features["atr_14"] = -1.0
        reasons = fv.validate_against_registry()
        assert any("atr_14" in r and "min" in r for r in reasons)


class TestC31VWAPZeroVolume:
    def test_c31_vwap_zero_vol_none(self):
        n = 50
        h = [50.0] * n
        l = [40.0] * n
        c = [45.0] * n
        v = [0.0] * n
        result = FeatureEngine._compute_vwap(h, l, c, v, 20)
        for t in range(min(5, n)):
            pass
        assert result[19] is None


class TestC32VWAPUniform:
    def test_c32_vwap_uniform_50(self):
        n = 100
        h = [55.0] * n
        l = [45.0] * n
        c = [50.0] * n
        v = [100.0] * n
        result = FeatureEngine._compute_vwap(h, l, c, v, 20)
        assert result[50] == pytest.approx(50.0)

    def test_c32_vwap_fv(self):
        candles = [
            _make_ohlcv(i, 45.0, 55.0, 45.0, 50.0, 100.0) for i in range(100)
        ]
        fv = FeatureEngine().calculate("X", candles, lookback=100)
        vwap = fv.features["vwap_20"]
        assert isinstance(vwap, float)
        assert vwap == pytest.approx(50.0)


class TestC33VWAPInsufficient:
    def test_c33_vwap_insufficient_t_9(self):
        n = 10
        h = [50.0] * n
        l = [40.0] * n
        c = [45.0] * n
        v = [100.0] * n
        result = FeatureEngine._compute_vwap(h, l, c, v, 20)
        assert result[9] is None


class TestC34VwapAtrDeterminism:
    def test_c34_10x_determinism(self):
        candles = [
            _make_ohlcv(
                i,
                100.0 + i * 0.3,
                101.0 + i * 0.3,
                99.0 + i * 0.3,
                100.5 + i * 0.3,
                1_000_000.0 + (i % 11) * 2000.0,
            )
            for i in range(200)
        ]
        eng = FeatureEngine()
        fvs = [eng.calculate("BTC", candles, lookback=200) for _ in range(10)]
        sha_set = {f.schema_sha256() for f in fvs}
        assert len(sha_set) == 1
        dicts = [f.to_sorted_dict() for f in fvs]
        assert all(d == dicts[0] for d in dicts)


@pytest.mark.parametrize("i", list(range(8)))
def test_param_atr_vwap_8variants(i: int):
    n = 30 + i * 5
    h = [100.0 + 1.0 * j + 0.1 * (j % 7) for j in range(n)]
    l = [95.0 + 0.8 * j + 0.1 * (j % 5) for j in range(n)]
    c = [97.5 + 0.9 * j + 0.1 * (j % 3) for j in range(n)]
    v = [1_000_000.0 + (j % (i + 1 + 1)) * 1000.0 for j in range(n)]
    atr_series = FeatureEngine._compute_atr(h, l, c, 14)
    vwap_series = FeatureEngine._compute_vwap(h, l, c, v, 20)
    last_atr = atr_series[-1]
    last_vwap = vwap_series[-1]
    if last_atr is not None:
        assert last_atr >= 0.0
    if last_vwap is not None:
        assert isinstance(last_vwap, float)

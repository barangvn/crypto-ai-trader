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


def _from_close_volume(closes: list[float], volumes: list[float]) -> list[Candle]:
    arr: list[Candle] = []
    for i, c in enumerate(closes):
        v = volumes[i]
        arr.append(
            Candle(
                timeframe="1h",
                open_time=_ts(i * 3600),
                close_time=_ts((i + 1) * 3600),
                open=Decimal(str(c - 0.5)),
                high=Decimal(str(c + 0.5)),
                low=Decimal(str(c - 0.5)),
                close=Decimal(str(c)),
                volume=Decimal(str(v)),
                closed=True,
            )
        )
    return arr


class TestC35C36Momentum:
    def test_c35_mom_abs(self):
        closes = [100.0] * 10 + [110.0]
        abs_series, _ = FeatureEngine._compute_momentum(closes, 10)
        assert abs_series[10] == pytest.approx(10.0)

    def test_c36_mom_pct(self):
        closes = [100.0] * 10 + [110.0]
        _, pct_series = FeatureEngine._compute_momentum(closes, 10)
        assert pct_series[10] == pytest.approx(10.0)


class TestC37MomInsufficient:
    def test_c37_mom_insufficient_t5(self):
        closes = [100.0] * 8
        a, p = FeatureEngine._compute_momentum(closes, 10)
        assert a[5] is None
        assert p[5] is None


class TestC38Volatility:
    def test_c38_volatility_non_negative_and_deterministic(self):
        closes: list[float] = []
        for i in range(60):
            closes.append(100.0 + ((i % 2) - 0.5) * 2.0)
        series = FeatureEngine._compute_volatility(closes, 20)
        last = series[-1]
        assert isinstance(last, float)
        assert last >= 0.0
        series2 = FeatureEngine._compute_volatility(closes, 20)
        assert last == pytest.approx(series2[-1])


class TestC39VolatilityInsufficient:
    def test_c39_vol_insufficient_t10(self):
        closes = [100.0 + i for i in range(15)]
        result = FeatureEngine._compute_volatility(closes, 20)
        assert result[-1] is None


class TestC40VolumeRatio:
    def test_c40_ratio_uniform_1(self):
        volumes = [1000.0] * 40
        r, _ = FeatureEngine._compute_volume_features(volumes, 20)
        assert r[-1] == pytest.approx(1.0)
        assert r[30] == pytest.approx(1.0)


class TestC41VolumeRatioZeroMean:
    def test_c41_zero_mean_returns_0(self):
        volumes = [0.0] * 40
        r, _ = FeatureEngine._compute_volume_features(volumes, 20)
        last = r[-1]
        assert isinstance(last, float)
        assert last == 0.0


class TestC42VolumeStdInsufficient:
    def test_c42_std_insufficient_t10(self):
        volumes = [100.0] * 10
        _, s = FeatureEngine._compute_volume_features(volumes, 20)
        assert s[9] is None


class TestC43MomVolDeterminism10x:
    def test_c43_10x_determinism(self):
        closes = [100.0 + 0.3 * i + 0.05 * (i % 7) for i in range(200)]
        volumes = [1_000_000.0 + (i % 13) * 5000.0 for i in range(200)]
        candles = _from_close_volume(closes, volumes)
        eng = FeatureEngine()
        fvs = [eng.calculate("BTC", candles, lookback=200) for _ in range(10)]
        sha_set = {f.schema_sha256() for f in fvs}
        assert len(sha_set) == 1
        mom_abs_vals = {f.features["mom_10_abs"] for f in fvs}
        assert len(mom_abs_vals) == 1
        volatility_set = {f.features["volatility_20_bps"] for f in fvs}
        assert len(volatility_set) == 1
        vol_ratio_set = {f.features["vol_ratio_20"] for f in fvs}
        assert len(vol_ratio_set) == 1


class TestPerFeatureMath12Keys:
    @pytest.mark.parametrize("k_idx", list(range(12)))
    def test_12keys_typed_or_none(self, k_idx: int):
        keys = [
            "ema_14",
            "rsi_14",
            "atr_14",
            "vwap_20",
            "mom_10_abs",
            "mom_10_pct",
            "volatility_20_bps",
            "vol_ratio_20",
            "vol_std_20_scaled",
            "close_raw",
            "high_raw",
            "low_raw",
        ]
        k = keys[k_idx]
        closes = [100.0 + 0.2 * i + 0.1 * (i % 5) for i in range(300)]
        volumes = [1_000_000.0 + (i % 19) * 3000.0 for i in range(300)]
        candles = _from_close_volume(closes, volumes)
        fv = FeatureEngine().calculate("X", candles, lookback=300)
        val = fv.features[k]
        assert val is None or isinstance(val, float)
        if isinstance(val, float):
            import math

            assert not math.isnan(val)
            assert not math.isinf(val)


@pytest.mark.parametrize("i", list(range(10)))
def test_formula_param_10_variants(i: int):
    n = 40 + i * 7
    closes = [100.0 + 0.3 * j + 0.07 * (j % (i + 3)) for j in range(n)]
    volumes = [500_000.0 + (j % (i + 2 + 1)) * 7000.0 for j in range(n)]
    abs_s, pct_s = FeatureEngine._compute_momentum(closes, 10)
    vol_s = FeatureEngine._compute_volatility(closes, 20)
    rat_s, std_s = FeatureEngine._compute_volume_features(volumes, 20)
    for idx, series in (
        ("mom_abs", abs_s),
        ("mom_pct", pct_s),
        ("volatility", vol_s),
        ("vol_ratio", rat_s),
        ("vol_std_scaled", std_s),
    ):
        last = series[-1]
        if last is None:
            assert n < 20 if idx in ("volatility", "vol_ratio", "vol_std_scaled") else n <= 10
        else:
            assert isinstance(last, float)

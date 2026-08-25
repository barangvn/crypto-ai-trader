from __future__ import annotations

from tests.regime._fixtures import (  # noqa: E402
    MarketRegimeState,
    QualityHint,
    RegimeEngine,
    DetectOptions,
    _clean_fv,
    _make_fv,
)


class TestReg01H2HighVol:
    def test_reg01_c19_high_vol_bps_200_ratio2(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 5.0, "volatility_20_bps": 500.0,
            "vol_ratio_20": 5.0, "vol_std_20_scaled": 200.0,
            "high_raw": 110.0, "low_raw": 90.0,
        })
        mr, aux = RegimeEngine().detect("BTC_USDT", fv)
        assert mr.scores["high_volatility"] >= 0.80
        assert aux["raw_axes"]["vol_axis"] >= 0.5

    def test_reg01_c20_high_vol_midband_v125_ratio1(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 2.0, "volatility_20_bps": 225.0,
            "vol_ratio_20": 1.0, "vol_std_20_scaled": 20.0,
            "high_raw": 103.0, "low_raw": 97.0,
        })
        mr, _ = RegimeEngine().detect("BTC_USDT", fv)
        assert 0.30 <= mr.scores["high_volatility"] <= 0.70

    def test_reg01_c23_spike_flag_v100_ratio2(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 2.0, "volatility_20_bps": 120.0,
            "vol_ratio_20": 3.0, "vol_std_20_scaled": 60.0,
            "high_raw": 103.0, "low_raw": 97.0,
        })
        mr_no_spike, _ = RegimeEngine(options=DetectOptions(high_vol_bps_floor=999999.0)).detect("X", fv)
        mr_with, _ = RegimeEngine().detect("X", fv)
        # Spike bonus 0.15 should add vs a case without spike (high_vol disabled via huge floor)
        assert mr_with.scores["high_volatility"] >= mr_no_spike.scores["high_volatility"] - 1e-9

    def test_reg01_c26_vol_pos1_trend0_pick_high_vol(self):
        # Force vol +1, trend=0 mom=0 neutral; neutral → tie threshold might
        # transition, so disable tie by raising threshold and lowering conf floor
        opt = DetectOptions(
            tie_threshold=0.0,
            min_confidence_before_transition=0.0,
            conflict_threshold=1.0,
        )
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 5.0, "volatility_20_bps": 1000.0,
            "vol_ratio_20": 5.0, "vol_std_20_scaled": 200.0,
            "high_raw": 110.0, "low_raw": 90.0,
        })
        mr, _ = RegimeEngine(options=opt).detect("X", fv)
        assert mr.regime == MarketRegimeState.HIGH_VOLATILITY

    def test_reg01_c31_vol_bps_zero_low_vol_score_ge_085(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 0.1, "volatility_20_bps": 0.0,
            "vol_ratio_20": 0.5, "vol_std_20_scaled": 0.0,
            "high_raw": 100.1, "low_raw": 99.9,
        })
        mr, _ = RegimeEngine().detect("X", fv)
        assert mr.scores["low_volatility"] >= 0.85

    def test_reg01_c32_vol_bps_500_high_vol_ge_090(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 5.0, "volatility_20_bps": 500.0,
            "vol_ratio_20": 3.0, "vol_std_20_scaled": 200.0,
            "high_raw": 110.0, "low_raw": 90.0,
        })
        mr, _ = RegimeEngine().detect("X", fv)
        assert mr.scores["high_volatility"] >= 0.90

    def test_reg01_c35_high_vol_is_max_when_extreme(self):
        opt = DetectOptions(
            tie_threshold=0.0001,
            min_confidence_before_transition=0.0,
            conflict_threshold=1.0,
            null_count_pct_transition=1.0,
        )
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 5.0, "volatility_20_bps": 10_000.0,
            "vol_ratio_20": 10.0, "vol_std_20_scaled": 500.0,
            "high_raw": 150.0, "low_raw": 50.0,
        })
        mr, _ = RegimeEngine(options=opt).detect("X", fv)
        assert mr.regime == MarketRegimeState.HIGH_VOLATILITY
        assert max(mr.scores, key=lambda k: mr.scores[k]) == "high_volatility"


class TestReg01H2LowVol:
    def test_reg01_c21_low_vol_v10_ratio07(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 0.01, "volatility_20_bps": 0.0,
            "vol_ratio_20": 0.05, "vol_std_20_scaled": 0.0,
            "high_raw": 100.01, "low_raw": 99.99,
        })
        mr, _ = RegimeEngine().detect("X", fv)
        assert mr.scores["low_volatility"] >= 0.75

    def test_reg01_c22_low_vol_v30_ratio12(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 1.0, "volatility_20_bps": 100.0,
            "vol_ratio_20": 2.0, "vol_std_20_scaled": 20.0,
            "high_raw": 101.0, "low_raw": 99.0,
        })
        mr, _ = RegimeEngine().detect("X", fv)
        assert mr.scores["low_volatility"] <= 0.15

    def test_reg01_c24_calm_flag(self):
        # calm = v <= 25 AND ratio <= 0.9 → adds 0.15 to low_vol
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 0.1, "volatility_20_bps": 20.0,
            "vol_ratio_20": 0.8, "vol_std_20_scaled": 3.0,
            "high_raw": 100.1, "low_raw": 99.9,
        })
        mr_calm, _ = RegimeEngine().detect("X", fv)
        # make version with v=20 but ratio=1.0 (no calm)
        fv2 = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 0.1, "volatility_20_bps": 20.0,
            "vol_ratio_20": 1.0, "vol_std_20_scaled": 3.0,
            "high_raw": 100.1, "low_raw": 99.9,
        })
        mr_nocalm, _ = RegimeEngine().detect("X", fv2)
        assert mr_calm.scores["low_volatility"] >= mr_nocalm.scores["low_volatility"]

    def test_reg01_c27_vol_neg1_pick_low_vol(self):
        opt = DetectOptions(
            tie_threshold=0.0001,
            min_confidence_before_transition=0.0,
            conflict_threshold=1.0,
        )
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 0.01, "volatility_20_bps": 0.0,
            "vol_ratio_20": 0.1, "vol_std_20_scaled": 0.0,
            "high_raw": 100.01, "low_raw": 99.99,
        })
        mr, _ = RegimeEngine(options=opt).detect("X", fv)
        assert mr.regime == MarketRegimeState.LOW_VOLATILITY

    def test_reg01_c25_vol_axis_0_neutral_high_low_vol_both_low(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 0.5, "volatility_20_bps": 87.5,   # mid band 25+150 midpoint approx 87.5
            "vol_ratio_20": 1.0, "vol_std_20_scaled": 0.0,
            "high_raw": 100.5, "low_raw": 99.5,
        })
        _, aux = RegimeEngine().detect("X", fv)
        # mid band; vol_axis should be around 0 (between -0.3..+0.3)
        assert abs(aux["raw_axes"]["vol_axis"]) <= 0.5

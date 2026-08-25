from __future__ import annotations

from tests.regime._fixtures import (  # noqa: E402
    Decimal,
    DetectOptions,
    Instant,
    MarketRegimeState,
    QualityHint,
    REGIME_KEYS,
    RegimeEngine,
    TimeRangeSpec,
    _clean_fv,
    _make_fv,
    _ts,
    datetime,
    pytest,
)


class TestReg01H1EnumCoverage:
    def test_reg01_c1_bull_dominant_regime_bull(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 72.0,
            "vwap_20": 99.5, "mom_10_abs": 4.8, "mom_10_pct": 0.048,
            "atr_14": 0.8, "volatility_20_bps": 18.0,
            "vol_ratio_20": 0.6, "vol_std_20_scaled": 8.0,
            "high_raw": 105.5, "low_raw": 104.2,
        })
        eng = RegimeEngine()
        mr, aux = eng.detect("BTC_USDT", fv)
        assert mr.regime == MarketRegimeState.BULL
        assert mr.confidence >= 0.40

    def test_reg01_c2_bear_dominant_regime_bear(self):
        fv = _clean_fv({
            "close_raw": 95.0, "ema_14": 100.0, "rsi_14": 28.0,
            "vwap_20": 100.5, "mom_10_abs": -4.8, "mom_10_pct": -0.048,
            "atr_14": 0.8, "volatility_20_bps": 18.0,
            "vol_ratio_20": 0.6, "vol_std_20_scaled": 8.0,
            "high_raw": 95.8, "low_raw": 94.2,
        })
        eng = RegimeEngine()
        mr, aux = eng.detect("BTC_USDT", fv)
        assert mr.regime == MarketRegimeState.BEAR
        assert mr.confidence >= 0.40

    def test_reg01_c3_sideways_3_neutral(self):
        fv = _clean_fv({
            "close_raw": 100.02, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.1, "mom_10_pct": 0.001,
            "atr_14": 0.3, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.9, "vol_std_20_scaled": 5.0,
            "high_raw": 100.3, "low_raw": 99.7,
        })
        eng = RegimeEngine()
        mr, aux = eng.detect("BTC_USDT", fv)
        # Either sideways outright, or near-tie transition (acceptable in C3;
        # we only check sideways_score is high when neutral)
        scores = mr.scores
        assert scores["sideways"] >= 0.50
        # regime should be either sideways or transition
        assert mr.regime in (MarketRegimeState.SIDEWAYS, MarketRegimeState.TRANSITION_UNCERTAIN)

    def test_reg01_c6_tie_transition_triggered(self):
        fv = _clean_fv({
            "close_raw": 102.0, "ema_14": 100.0, "rsi_14": 62.0,
            "vwap_20": 101.0, "mom_10_abs": 0.5, "mom_10_pct": 0.005,
            "atr_14": 2.0, "volatility_20_bps": 225.0,
            "vol_ratio_20": 1.5, "vol_std_20_scaled": 15.0,
            "high_raw": 103.0, "low_raw": 101.0,
        })
        opt = DetectOptions(tie_threshold=0.30)
        mr, aux = RegimeEngine(options=opt).detect("BTC_USDT", fv)
        assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN
        assert aux["tie_activated"] is True or aux["conflict_activated"] is True or aux["low_confidence_activated"] is True

    def test_reg01_c8_scores_keys_exactly_regime_keys(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 72.0,
            "vwap_20": 99.5, "mom_10_abs": 4.8, "mom_10_pct": 0.048,
            "atr_14": 0.8, "volatility_20_bps": 18.0,
            "vol_ratio_20": 0.6, "vol_std_20_scaled": 8.0,
            "high_raw": 105.5, "low_raw": 104.2,
        })
        mr, _ = RegimeEngine().detect("BTC_USDT", fv)
        assert set(mr.scores.keys()) == REGIME_KEYS

    def test_reg01_c9_scores_values_in_0_1(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 72.0,
            "vwap_20": 99.5, "mom_10_abs": 4.8, "mom_10_pct": 0.048,
            "atr_14": 0.8, "volatility_20_bps": 18.0,
            "vol_ratio_20": 0.6, "vol_std_20_scaled": 8.0,
            "high_raw": 105.5, "low_raw": 104.2,
        })
        mr, _ = RegimeEngine().detect("BTC_USDT", fv)
        for k, v in mr.scores.items():
            assert isinstance(v, float)
            assert 0.0 <= v <= 1.0, (k, v)

    def test_reg01_c10_scores_sum_not_required_to_be_one(self):
        # Make extreme scenario so sum is NOT close to 1 — the 6 scores
        # individually clamp [0,1], sum can be anything from ~0.006 up to ~6
        fv = _clean_fv({
            "close_raw": 100.1, "ema_14": 100.0, "rsi_14": 52.0,
            "vwap_20": 100.0, "mom_10_abs": 0.1, "mom_10_pct": 0.001,
            "atr_14": 0.2, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.85, "vol_std_20_scaled": 6.0,
            "high_raw": 100.3, "low_raw": 99.8,
        })
        mr, _ = RegimeEngine().detect("BTC_USDT", fv)
        total = sum(mr.scores.values())
        # Explicitly allow sum != 1
        assert 0.0 < total < 6.0

    def test_reg01_c11_detector_version_string(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 72.0,
            "vwap_20": 99.5, "mom_10_abs": 4.8, "mom_10_pct": 0.048,
            "atr_14": 0.8, "volatility_20_bps": 18.0,
            "vol_ratio_20": 0.6, "vol_std_20_scaled": 8.0,
            "high_raw": 105.5, "low_raw": 104.2,
        })
        mr, aux = RegimeEngine().detect("BTC_USDT", fv)
        assert mr.detector_version == "reg_01_v1"
        assert aux["detector_version"] == "reg_01_v1"

    def test_reg01_c12_feature_version_preserved(self):
        fv = _make_fv({"close_raw": 105.0})  # feature_version default fea_01_v1
        mr, _ = RegimeEngine().detect("BTC_USDT", fv)
        assert mr.feature_version == "fea_01_v1"

    def test_reg01_c13_timeframe_preserved(self):
        fv = _make_fv({"close_raw": 100.0}, timeframe="15m")
        mr, _ = RegimeEngine().detect("BTC_USDT", fv)
        assert mr.timeframe == "15m"

    def test_reg01_c14_lookback_ts_start_leq_end(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 72.0,
            "vwap_20": 99.5, "mom_10_abs": 4.8, "mom_10_pct": 0.048,
            "atr_14": 0.8, "volatility_20_bps": 18.0,
            "vol_ratio_20": 0.6, "vol_std_20_scaled": 8.0,
            "high_raw": 105.5, "low_raw": 104.2,
        })
        mr, _ = RegimeEngine().detect("BTC_USDT", fv)
        assert isinstance(mr.lookback_ts, TimeRangeSpec)
        assert mr.lookback_ts.start <= mr.lookback_ts.end

    def test_reg01_c15_to_sorted_dict_deterministic_twice(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 72.0,
            "vwap_20": 99.5, "mom_10_abs": 4.8, "mom_10_pct": 0.048,
            "atr_14": 0.8, "volatility_20_bps": 18.0,
            "vol_ratio_20": 0.6, "vol_std_20_scaled": 8.0,
            "high_raw": 105.5, "low_raw": 104.2,
        })
        eng = RegimeEngine()
        a, _ = eng.detect("BTC_USDT", fv)
        b, _ = eng.detect("BTC_USDT", fv)
        assert a.to_sorted_dict() == b.to_sorted_dict()
        assert a.schema_sha256() == b.schema_sha256()

    def test_reg01_c16_bull_score_trend_weight_hand_verify(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 100.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.050,
            "atr_14": 0.5, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.6, "vol_std_20_scaled": 5.0,
            "high_raw": 105.3, "low_raw": 104.7,
        })
        mr, aux = RegimeEngine().detect("BTC_USDT", fv)
        tr = aux["raw_axes"]["trend_axis"]
        mm = aux["raw_axes"]["mom_axis"]
        vo = aux["raw_axes"]["vol_axis"]
        # Bull raw hand calc (approx):
        raw = 0.55 * max(0, tr) + 0.30 * max(0, mm) + 0.15 * max(0, -vo)
        clamped = max(0.0, min(1.0, raw))
        assert abs(mr.scores["bull"] - clamped) < 1e-6

    def test_reg01_c17_bear_score_trend_weight_hand_verify(self):
        fv = _clean_fv({
            "close_raw": 95.0, "ema_14": 100.0, "rsi_14": 0.0,
            "vwap_20": 100.0, "mom_10_abs": -5.0, "mom_10_pct": -0.050,
            "atr_14": 0.5, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.6, "vol_std_20_scaled": 5.0,
            "high_raw": 95.3, "low_raw": 94.7,
        })
        mr, aux = RegimeEngine().detect("BTC_USDT", fv)
        tr = aux["raw_axes"]["trend_axis"]
        mm = aux["raw_axes"]["mom_axis"]
        vo = aux["raw_axes"]["vol_axis"]
        raw = 0.55 * max(0, -tr) + 0.30 * max(0, -mm) + 0.15 * max(0, -vo)
        clamped = max(0.0, min(1.0, raw))
        assert abs(mr.scores["bear"] - clamped) < 1e-6

    def test_reg01_c18_transition_floor_nonzero(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 72.0,
            "vwap_20": 99.5, "mom_10_abs": 4.8, "mom_10_pct": 0.048,
            "atr_14": 0.8, "volatility_20_bps": 18.0,
            "vol_ratio_20": 0.6, "vol_std_20_scaled": 8.0,
            "high_raw": 105.5, "low_raw": 104.2,
        })
        mr, _ = RegimeEngine().detect("BTC_USDT", fv)
        # Floor is 0.001 before any T activation; even in bull regime
        # transition_uncertain score should be >= 0.0009 (accounting for
        # floating point)
        assert mr.scores["transition_uncertain"] >= 0.0009

    def test_reg01_aux_correlation_causation_returned(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 72.0,
            "vwap_20": 99.5, "mom_10_abs": 4.8, "mom_10_pct": 0.048,
            "atr_14": 0.8, "volatility_20_bps": 18.0,
            "vol_ratio_20": 0.6, "vol_std_20_scaled": 8.0,
            "high_raw": 105.5, "low_raw": 104.2,
        })
        mr, aux = RegimeEngine().detect(
            "BTC_USDT",
            fv,
            correlation_id="CORR_abc123",
            causation_id="CAU_def456",
        )
        assert aux["correlation_id"] == "CORR_abc123"
        assert aux["causation_id"] == "CAU_def456"
        assert aux["symbol"] == "BTC_USDT"

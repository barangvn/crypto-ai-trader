from __future__ import annotations

from tests.regime._fixtures import (  # noqa: E402
    MarketRegimeState,
    QualityHint,
    DetectOptions,
    RegimeEngine,
    SREG01_NULLABLE_FEATURE_COUNT,
    _clean_fv,
    _make_fv,
    pytest,
)


class TestReg01T1Tie:
    def test_reg01_c37_T1_tie_diff_002_triggers_transition(self):
        opt = DetectOptions(
            tie_threshold=0.10,
            min_confidence_before_transition=0.0,
            conflict_threshold=1.0,
            null_count_pct_transition=1.0,
        )
        # Balanced fixture: mild up-trend + moderate high_vol → bull and hv close
        fv = _clean_fv({
            "close_raw": 102.0, "ema_14": 100.0, "rsi_14": 60.0,
            "vwap_20": 100.5, "mom_10_abs": 0.4, "mom_10_pct": 0.004,
            "atr_14": 1.5, "volatility_20_bps": 200.0,
            "vol_ratio_20": 1.2, "vol_std_20_scaled": 10.0,
            "high_raw": 103.0, "low_raw": 101.0,
        })
        mr, aux = RegimeEngine(options=opt).detect("X", fv)
        # Either tie or low_conf or conflict fires → transition
        assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN
        assert aux["tie_activated"] or aux["low_confidence_activated"] or aux["conflict_activated"]

    def test_reg01_c38_T1_diff_006_notie(self):
        # Bull fixture strong
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 78.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.050,
            "atr_14": 0.8, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.6, "vol_std_20_scaled": 4.0,
            "high_raw": 105.5, "low_raw": 104.5,
        })
        opt = DetectOptions(
            tie_threshold=0.0001,  # disable tie
            min_confidence_before_transition=0.0,
            conflict_threshold=1.0,
            null_count_pct_transition=1.0,
        )
        mr, aux = RegimeEngine(options=opt).detect("X", fv)
        # Strong bull → bull regime (no transition)
        assert mr.regime == MarketRegimeState.BULL
        assert aux["tie_activated"] is False


class TestReg01T2Conflict:
    def test_reg01_c39_T2_trend_up_high_vol_conflict(self):
        # Trend strongly bull BUT vol strongly high → conflict
        opt = DetectOptions(
            tie_threshold=0.0,
            min_confidence_before_transition=0.0,
            conflict_threshold=0.05,
            null_count_pct_transition=1.0,
        )
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 78.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.050,
            "atr_14": 5.0, "volatility_20_bps": 500.0,
            "vol_ratio_20": 5.0, "vol_std_20_scaled": 200.0,
            "high_raw": 110.0, "low_raw": 95.0,
        })
        mr, aux = RegimeEngine(options=opt).detect("X", fv)
        assert aux["conflict_activated"] is True
        assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN

    def test_reg01_c40_T2_no_conflict_small_signals(self):
        opt = DetectOptions(
            tie_threshold=0.0,
            min_confidence_before_transition=0.0,
            conflict_threshold=0.99,
            null_count_pct_transition=1.0,
        )
        fv = _clean_fv({
            "close_raw": 101.0, "ema_14": 100.0, "rsi_14": 55.0,
            "vwap_20": 100.0, "mom_10_abs": 0.5, "mom_10_pct": 0.005,
            "atr_14": 0.6, "volatility_20_bps": 40.0,
            "vol_ratio_20": 1.0, "vol_std_20_scaled": 10.0,
            "high_raw": 101.5, "low_raw": 100.5,
        })
        _, aux = RegimeEngine(options=opt).detect("X", fv)
        assert aux["conflict_activated"] is False


class TestReg01T3InsufficientLookback:
    def test_reg01_c41_T3_6_of_9_null_triggers(self):
        # 9 nullable keys; fill 5 with None → ratio 5/9 ~0.55 ≥ 0.5 T3 fires
        feat = {
            "close_raw": 100.0, "high_raw": 100.5, "low_raw": 99.5,
            # 9 nullable:
            "ema_14": None,
            "rsi_14": None,
            "atr_14": None,
            "vwap_20": None,
            "mom_10_abs": None,
            # 4 remaining with values
            "mom_10_pct": 0.0,
            "volatility_20_bps": 50.0,
            "vol_ratio_20": 1.0,
            "vol_std_20_scaled": 10.0,
        }
        fv = _make_fv(feat, input_ref_count=200)
        mr, aux = RegimeEngine().detect("X", fv)
        assert aux["insufficient_lookback_activated"] is True
        assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN

    def test_reg01_c42_T3_4_of_9_null_no_trigger(self):
        feat = {
            "close_raw": 100.0, "high_raw": 100.5, "low_raw": 99.5,
            "ema_14": 100.0,
            "rsi_14": 50.0,
            "atr_14": 0.5,
            "vwap_20": 100.0,
            "mom_10_abs": 0.0,
            # 4 remaining as null
            "mom_10_pct": None,
            "volatility_20_bps": None,
            "vol_ratio_20": None,
            "vol_std_20_scaled": None,
        }
        fv = _make_fv(feat)
        _, aux = RegimeEngine().detect("X", fv)
        assert aux["insufficient_lookback_activated"] is False

    def test_reg01_c49_T3_threshold_overridable(self):
        # 2 null of 9 = 0.22 ratio; default 0.5 → no trigger
        # Override pct = 0.20 → 2/9 = 0.22 ≥ 0.20 T3 triggers
        feat = {
            "close_raw": 100.0, "high_raw": 100.5, "low_raw": 99.5,
            "ema_14": 100.0,
            "rsi_14": None,
            "atr_14": 0.5,
            "vwap_20": 100.0,
            "mom_10_abs": 0.0,
            "mom_10_pct": None,
            "volatility_20_bps": 60.0,
            "vol_ratio_20": 1.0,
            "vol_std_20_scaled": 10.0,
        }
        fv = _make_fv(feat)
        opt = DetectOptions(
            null_count_pct_transition=0.20,
            tie_threshold=0.0,
            min_confidence_before_transition=0.0,
            conflict_threshold=1.0,
        )
        _, aux = RegimeEngine(options=opt).detect("X", fv)
        assert aux["insufficient_lookback_activated"] is True

    def test_reg01_c50_T3_9_nullable_count_is_9(self):
        assert SREG01_NULLABLE_FEATURE_COUNT == 9


class TestReg01T4LowConfidence:
    def test_reg01_c43_T4_low_conf_triggers(self):
        # 6 scores all equal-ish (small spread)
        feat = {
            "close_raw": 100.0, "high_raw": 100.5, "low_raw": 99.5,
            "ema_14": 100.0, "rsi_14": 50.0, "atr_14": 0.5,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "volatility_20_bps": 50.0, "vol_ratio_20": 1.0,
            "vol_std_20_scaled": 10.0,
        }
        fv = _clean_fv(feat)
        opt = DetectOptions(
            tie_threshold=0.0,
            min_confidence_before_transition=0.99,  # unrealistically high -> always T4
            conflict_threshold=1.0,
            null_count_pct_transition=1.0,
        )
        mr, aux = RegimeEngine(options=opt).detect("X", fv)
        assert aux["low_confidence_activated"] is True
        assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN

    def test_reg01_c44_T4_no_lowconf_when_clear(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 85.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.050,
            "atr_14": 0.8, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
            "high_raw": 105.5, "low_raw": 104.5,
        })
        opt = DetectOptions(
            tie_threshold=0.0,
            min_confidence_before_transition=0.01,
            conflict_threshold=1.0,
            null_count_pct_transition=1.0,
        )
        _, aux = RegimeEngine(options=opt).detect("X", fv)
        assert aux["low_confidence_activated"] is False


class TestReg01T5QualityInvalidQuarantined:
    def test_reg01_c45_T5_invalid_triggers_transition(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 85.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.050,
            "atr_14": 0.8, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
            "high_raw": 105.5, "low_raw": 104.5,
        })
        qh = QualityHint(invalid=True)
        mr, aux = RegimeEngine().detect("X", fv, quality_hint=qh)
        assert aux["quality_triggered_transition"] is True
        assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN
        assert mr.confidence <= 0.25  # 0.20 penalty * 0.75 transition = 0.15 top

    def test_reg01_c46_T5_quarantined_triggers_transition(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 85.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.050,
            "atr_14": 0.8, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
            "high_raw": 105.5, "low_raw": 104.5,
        })
        qh = QualityHint(quarantined=True)
        mr, aux = RegimeEngine().detect("X", fv, quality_hint=qh)
        assert aux["quality_triggered_transition"] is True
        assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN


class TestReg01TransitionCombined3Triggers:
    def test_reg01_cmb_T1T3T5_three_active(self):
        # Tie (threshold 1.0 → top1-top2 always < threshold), T3 nulls, T5 invalid quarantine
        feat = {
            "close_raw": 100.0, "high_raw": 100.5, "low_raw": 99.5,
            "ema_14": None, "rsi_14": None, "atr_14": None,
            "vwap_20": None, "mom_10_abs": None, "mom_10_pct": None,
            "volatility_20_bps": None, "vol_ratio_20": None,
            "vol_std_20_scaled": None,
        }
        fv = _make_fv(feat)
        qh = QualityHint(invalid=True)
        opt = DetectOptions(tie_threshold=1.0)
        mr, aux = RegimeEngine(options=opt).detect("X", fv, quality_hint=qh)
        flags = aux["transition_flags"]
        count = sum(1 for v in flags.values() if v)
        assert count >= 3
        assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN

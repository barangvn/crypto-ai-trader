from __future__ import annotations

from tests.regime._fixtures import (  # noqa: E402
    DetectOptions,
    MarketRegimeState,
    QualityHint,
    RegimeEngine,
    _clean_fv,
)


class TestReg01ThreeAxesDirectFormula:
    def test_reg01_fv1_trend_axis_ema_plus2pct_handcalc(self):
        # close 102 vs ema 100 → +2% difference → clamp by ±5% → norm to 1 → 0.4
        fv = _clean_fv({
            "close_raw": 102.0, "ema_14": 100.0, "rsi_14": 50.0,  # rsi component = 0 (center 50)
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,  # mom 0
            "atr_14": 0.5, "volatility_20_bps": 50.0,
            "vol_ratio_20": 1.0, "vol_std_20_scaled": 10.0,
            "high_raw": 102.5, "low_raw": 101.5,
        })
        _, aux = RegimeEngine().detect("X", fv)
        # trend_ema = 0.02/0.05 = 0.4; rsi = (50-50)/50 = 0; vwap = 0.02/0.05 = 0.4
        # trend = 0.45*0.4 + 0.35*0 + 0.20*0.4 = 0.18 + 0.08 = 0.26
        expected = 0.45 * (0.02 / 0.05) + 0.35 * 0.0 + 0.20 * (0.02 / 0.05)
        assert abs(aux["raw_axes"]["trend_axis"] - expected) < 1e-9

    def test_reg01_fv2_trend_axis_rsi_80_handcalc(self):
        # rsi 80 -> +0.6
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 80.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 0.5, "volatility_20_bps": 50.0,
            "vol_ratio_20": 1.0, "vol_std_20_scaled": 10.0,
            "high_raw": 100.5, "low_raw": 99.5,
        })
        _, aux = RegimeEngine().detect("X", fv)
        rsi_c = (80.0 - 50.0) / 50.0  # 0.6
        expected = 0.45 * 0.0 + 0.35 * rsi_c + 0.20 * 0.0
        assert abs(aux["raw_axes"]["trend_axis"] - expected) < 1e-9

    def test_reg01_fv3_mom_axis_plus4pct(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 4.0, "mom_10_pct": 0.04,
            "atr_14": 0.5, "volatility_20_bps": 50.0,
            "vol_ratio_20": 1.0, "vol_std_20_scaled": 10.0,
            "high_raw": 100.5, "low_raw": 99.5,
        })
        _, aux = RegimeEngine().detect("X", fv)
        abs_c = 4.0 / 100.0 / 0.05  # 0.04 / 0.05 = 0.8
        pct_c = 0.04 / 0.05  # 0.8
        expected = 0.55 * abs_c + 0.45 * pct_c
        assert abs(aux["raw_axes"]["mom_axis"] - expected) < 1e-9

    def test_reg01_fv4_mom_axis_minus3pct(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": -3.0, "mom_10_pct": -0.03,
            "atr_14": 0.5, "volatility_20_bps": 50.0,
            "vol_ratio_20": 1.0, "vol_std_20_scaled": 10.0,
            "high_raw": 100.5, "low_raw": 99.5,
        })
        _, aux = RegimeEngine().detect("X", fv)
        abs_c = -3.0 / 100.0 / 0.05
        pct_c = -0.03 / 0.05
        expected = 0.55 * abs_c + 0.45 * pct_c
        assert abs(aux["raw_axes"]["mom_axis"] - expected) < 1e-9

    def test_reg01_fv5_vol_axis_highvol_300bps(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 2.0, "volatility_20_bps": 300.0,
            "vol_ratio_20": 1.0, "vol_std_20_scaled": 0.0,
            "high_raw": 103.0, "low_raw": 97.0,
        })
        _, aux = RegimeEngine().detect("X", fv)
        # 300 bps, hv_floor 150 → (300-150)/150 = 1.0 → clamp 0..1 → 1.0
        # ratio=1.0 → 0 adjust; std=0 → 0 adjust
        expected = (300.0 - 150.0) / 150.0
        assert expected >= 0.99  # 1.0
        assert abs(aux["raw_axes"]["vol_axis"] - 1.0) < 1e-9

    def test_reg01_fv6_vol_axis_lowvol_10bps(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 0.1, "volatility_20_bps": 10.0,
            "vol_ratio_20": 1.0, "vol_std_20_scaled": 0.0,
            "high_raw": 100.1, "low_raw": 99.9,
        })
        _, aux = RegimeEngine().detect("X", fv)
        # 10 bps, lv_ceil 25 → -1 + 2*(10/25) = -1 + 0.8 = -0.2
        expected = -1.0 + 2.0 * (10.0 / 25.0)
        assert abs(aux["raw_axes"]["vol_axis"] - expected) < 1e-9

    def test_reg01_fv7_vol_axis_ratio_30_and_std_100(self):
        # ratio >= 2.0 → +0.1; std >= 50 → +0.1
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 0.5, "volatility_20_bps": 87.5,  # mid band (linear 0.3 spread centered 0)
            "vol_ratio_20": 3.0, "vol_std_20_scaled": 100.0,
            "high_raw": 100.5, "low_raw": 99.5,
        })
        _, aux = RegimeEngine().detect("X", fv)
        # v_bps = 87.5 = midpoint of 25 and 150 → midpoint band: (0.3)*clamp
        # Actually mid formula: mid=(25+150)/2=87.5, half_span = (150-25)/2=62.5
        # vol_ax = (87.5-87.5)/62.5 *0.3 = 0.0. ratio >= 2 → +0.1. std>=50→+0.1 → 0.2
        expected = 0.0 + 0.1 + 0.1
        assert abs(aux["raw_axes"]["vol_axis"] - expected) < 1e-9

    def test_reg01_fv8_vol_axis_ratio_03_and_std_0(self):
        # ratio <=0.5 → -0.1
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 0.5, "volatility_20_bps": 87.5,
            "vol_ratio_20": 0.3, "vol_std_20_scaled": 0.0,
            "high_raw": 100.5, "low_raw": 99.5,
        })
        _, aux = RegimeEngine().detect("X", fv)
        expected = 0.0 + (-0.1) + 0.0
        assert abs(aux["raw_axes"]["vol_axis"] - expected) < 1e-9


class TestReg01SixScoresHand:
    def test_reg01_scores_bull_formula(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 100.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.05,
            "atr_14": 0.5, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.5, "vol_std_20_scaled": 3.0,
            "high_raw": 105.5, "low_raw": 104.5,
        })
        mr, aux = RegimeEngine().detect("X", fv)
        tr = aux["raw_axes"]["trend_axis"]
        mm = aux["raw_axes"]["mom_axis"]
        vo = aux["raw_axes"]["vol_axis"]
        raw_bull = 0.55 * max(0.0, tr) + 0.30 * max(0.0, mm) + 0.15 * max(0.0, -vo)
        clamped = max(0.0, min(1.0, raw_bull))
        assert abs(mr.scores["bull"] - clamped) < 1e-6

    def test_reg01_scores_bear_formula(self):
        fv = _clean_fv({
            "close_raw": 95.0, "ema_14": 100.0, "rsi_14": 0.0,
            "vwap_20": 100.0, "mom_10_abs": -5.0, "mom_10_pct": -0.05,
            "atr_14": 0.5, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.5, "vol_std_20_scaled": 3.0,
            "high_raw": 95.5, "low_raw": 94.5,
        })
        mr, aux = RegimeEngine().detect("X", fv)
        tr = aux["raw_axes"]["trend_axis"]
        mm = aux["raw_axes"]["mom_axis"]
        vo = aux["raw_axes"]["vol_axis"]
        raw_bear = 0.55 * max(0.0, -tr) + 0.30 * max(0.0, -mm) + 0.15 * max(0.0, -vo)
        clamped = max(0.0, min(1.0, raw_bear))
        assert abs(mr.scores["bear"] - clamped) < 1e-6

    def test_reg01_scores_sideways_formula_no_bonus(self):
        # No ema_flat/rsi_neutral/mom_flat → no 0.30 bonus, just product of neutrals
        fv = _clean_fv({
            "close_raw": 103.0, "ema_14": 100.0,  # ema +3% → not flat (>0.5%)
            "rsi_14": 70.0,  # not 43-57
            "vwap_20": 100.0, "mom_10_abs": 3.0, "mom_10_pct": 0.03,  # mom 3% → not ≤0.3%
            "atr_14": 0.8, "volatility_20_bps": 50.0,
            "vol_ratio_20": 1.0, "vol_std_20_scaled": 10.0,
            "high_raw": 103.5, "low_raw": 102.5,
        })
        opt = DetectOptions(
            sideways_band_ema_pct=0.001,   # even tighter; 3% >> 0.1% so ema NOT flat
            sideways_rsi_band_lo=49.0, sideways_rsi_band_hi=51.0,  # 70 outside
            momentum_band_abs_pct=0.001,  # 0.03 >> 0.001 → mom_flat = False
        )
        mr, aux = RegimeEngine(options=opt).detect("X", fv)
        tr = aux["raw_axes"]["trend_axis"]
        mm = aux["raw_axes"]["mom_axis"]
        vo = aux["raw_axes"]["vol_axis"]
        expected = (1.0 - abs(tr)) * (1.0 - abs(mm)) * (1.0 - abs(vo))
        clamped = max(0.0, min(1.0, expected))
        assert abs(mr.scores["sideways"] - clamped) < 1e-6

    def test_reg01_scores_sideways_030_bonus_applied_when_3_conditions(self):
        # All 3 flat conditions true → + 0.30 bonus
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0,  # 0 diff → ema flat
            "rsi_14": 50.0,  # 50 inside 43-57
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,  # 0 ≤ 0.3%
            "atr_14": 0.2, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.8, "vol_std_20_scaled": 5.0,
            "high_raw": 100.2, "low_raw": 99.8,
        })
        mr, aux = RegimeEngine().detect("X", fv)
        tr = aux["raw_axes"]["trend_axis"]
        mm = aux["raw_axes"]["mom_axis"]
        vo = aux["raw_axes"]["vol_axis"]
        base = (1.0 - abs(tr)) * (1.0 - abs(mm)) * (1.0 - abs(vo))
        raw = base + 0.30
        clamped = max(0.0, min(1.0, raw))
        assert abs(mr.scores["sideways"] - clamped) < 1e-6

    def test_reg01_scores_highvol_formula(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 2.0, "volatility_20_bps": 300.0,
            "vol_ratio_20": 3.0, "vol_std_20_scaled": 80.0,
            "high_raw": 105.0, "low_raw": 95.0,
        })
        mr, aux = RegimeEngine().detect("X", fv)
        vo = aux["raw_axes"]["vol_axis"]
        spike = 0.15  # v=300 >= 100 AND ratio 3.0 >= 2 → True
        raw = 0.85 * max(0.0, vo) + spike
        clamped = max(0.0, min(1.0, raw))
        assert abs(mr.scores["high_volatility"] - clamped) < 1e-6

    def test_reg01_scores_lowvol_formula(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 0.05, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.7, "vol_std_20_scaled": 1.0,
            "high_raw": 100.05, "low_raw": 99.95,
        })
        mr, aux = RegimeEngine().detect("X", fv)
        vo = aux["raw_axes"]["vol_axis"]
        calm = 0.15  # v = 10 <= 25 AND ratio 0.7 <= 0.9 → True
        raw = 0.85 * max(0.0, -vo) + calm
        clamped = max(0.0, min(1.0, raw))
        assert abs(mr.scores["low_volatility"] - clamped) < 1e-6

    def test_reg01_scores_transition_floor_0001(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 90.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.05,
            "atr_14": 0.8, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
            "high_raw": 105.5, "low_raw": 104.5,
        })
        mr, _ = RegimeEngine().detect("X", fv)
        # transition_uncertain score is exactly 0.001 after clamping (0.001 clamped 0-1 = 0.001)
        assert abs(mr.scores["transition_uncertain"] - 0.001) < 1e-9


class TestReg01ConfidenceFormula:
    def test_reg01_c61_confidence_clean_bull(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 95.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.05,
            "atr_14": 0.8, "volatility_20_bps": 8.0,
            "vol_ratio_20": 0.4, "vol_std_20_scaled": 1.0,
            "high_raw": 105.5, "low_raw": 104.5,
        })
        opt = DetectOptions(
            tie_threshold=0.0,
            conflict_threshold=1.0,
            null_count_pct_transition=1.0,
            min_confidence_before_transition=0.0,
        )
        mr, _ = RegimeEngine(options=opt).detect("X", fv)
        # Hand compute confidence
        ordered = sorted(mr.scores.items(), key=lambda kv: kv[1], reverse=True)
        top1 = ordered[0][1]
        rest_sum = sum(v for _, v in ordered[1:])
        mean_rest = rest_sum / 5.0
        conf_base = max(0.0, min(1.0, top1 - mean_rest))
        alpha = opt.confidence_smooth_alpha  # 0.85
        conf_sm = alpha * conf_base + (1.0 - alpha) * top1
        qmul = 1.0
        eff_trans = mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN
        if eff_trans:
            qmul *= opt.transition_confidence_mult
        expected = max(0.0, min(1.0, conf_sm * qmul))
        assert abs(mr.confidence - expected) < 1e-6

    def test_reg01_confidence_quality_multipliers(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 90.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.05,
            "atr_14": 0.8, "volatility_20_bps": 8.0,
            "vol_ratio_20": 0.4, "vol_std_20_scaled": 2.0,
            "high_raw": 105.5, "low_raw": 104.5,
        })
        qh = QualityHint(
            stale=True, degraded=True, duplicate=True,
            out_of_order=True, missing=True, abnormal_spread=True,
        )
        opt = DetectOptions(
            tie_threshold=0.0,
            conflict_threshold=1.0,
            null_count_pct_transition=1.0,
            min_confidence_before_transition=0.0,
        )
        mr_clean, _ = RegimeEngine(options=opt).detect("X", fv)
        mr_q, aux_q = RegimeEngine(options=opt).detect("X", fv, quality_hint=qh)
        # applied_penalty should be 0.75 * 0.90 * 0.85 (stale/degraded=0.75, dup/miss/ooo=0.90, abnormal=0.85)
        # times 1.0 (no transition active)
        expected_mult = 0.75 * 0.90 * 0.85
        assert abs(aux_q["quality_hint_applied_penalty"] - expected_mult) < 1e-9
        # And mr_q confidence = mr_clean confidence * expected_mult (approximately,
        # since they share same scores and transition not active)
        assert abs(mr_q.confidence - mr_clean.confidence * expected_mult) < 1e-6

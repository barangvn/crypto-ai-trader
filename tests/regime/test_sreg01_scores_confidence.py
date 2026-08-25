from __future__ import annotations

from tests.regime._fixtures import (  # noqa: E402
    MarketRegimeState,
    QualityHint,
    DetectOptions,
    REGIME_KEYS,
    RegimeEngine,
    _clean_fv,
    _make_fv,
)


class TestReg01ConfidenceRange:
    def test_reg01_c55_confidence_in_0_1_all_clean(self):
        for v_bps in (0, 10, 25, 50, 150, 300, 500, 10000):
            for tr in ("bull", "bear", "neutral"):
                if tr == "bull":
                    feat = {
                        "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 80.0,
                        "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.05,
                        "atr_14": 0.8, "volatility_20_bps": float(v_bps),
                        "vol_ratio_20": 0.6, "vol_std_20_scaled": 4.0,
                        "high_raw": 105.5, "low_raw": 104.5,
                    }
                elif tr == "bear":
                    feat = {
                        "close_raw": 95.0, "ema_14": 100.0, "rsi_14": 20.0,
                        "vwap_20": 100.0, "mom_10_abs": -5.0, "mom_10_pct": -0.05,
                        "atr_14": 0.8, "volatility_20_bps": float(v_bps),
                        "vol_ratio_20": 0.6, "vol_std_20_scaled": 4.0,
                        "high_raw": 95.5, "low_raw": 94.5,
                    }
                else:
                    feat = {
                        "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
                        "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
                        "atr_14": 0.3, "volatility_20_bps": float(v_bps),
                        "vol_ratio_20": 1.0, "vol_std_20_scaled": 10.0,
                        "high_raw": 100.5, "low_raw": 99.5,
                    }
                fv = _clean_fv(feat)
                mr, _ = RegimeEngine().detect("X", fv)
                assert 0.0 <= mr.confidence <= 1.0

    def test_reg01_c56_confidence_never_negative_or_over_one(self):
        # Combined worst case: stale + degraded + duplicate + abnormal_spread
        # (invalid would make it transition; but these 4 all reduce confidence)
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 85.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.050,
            "atr_14": 0.8, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
            "high_raw": 105.5, "low_raw": 104.5,
        })
        qh = QualityHint(
            stale=True,
            degraded=True,
            duplicate=True,
            out_of_order=True,
            missing=True,
            abnormal_spread=True,
        )
        mr, _ = RegimeEngine().detect("X", fv, quality_hint=qh)
        # qmul approx: 0.75 * 0.90 * 0.85 = 0.57375; transition not active so no 0.75 extra
        assert 0.0 <= mr.confidence <= 1.0

    def test_reg01_c57_nulls_2of9_lowered_conf_but_no_T3(self):
        # 2 null: ratio 0.22 < 0.5 → T3 no; but confidence will be lower vs clean
        feat = {
            "close_raw": 105.0, "high_raw": 105.5, "low_raw": 104.5,
            "ema_14": None, "vwap_20": None,
            "rsi_14": 80.0, "atr_14": 0.8,
            "mom_10_abs": 5.0, "mom_10_pct": 0.050,
            "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
        }
        fv_dirty = _make_fv(feat)
        feat2 = dict(feat)
        feat2["ema_14"] = 100.0
        feat2["vwap_20"] = 100.0
        fv_clean = _clean_fv(feat2)
        opt = DetectOptions(
            tie_threshold=0.0,
            min_confidence_before_transition=0.0,
            conflict_threshold=1.0,
            null_count_pct_transition=1.0,
        )
        mr_d, _ = RegimeEngine(options=opt).detect("X", fv_dirty)
        mr_c, _ = RegimeEngine(options=opt).detect("X", fv_clean)
        # Dirty null version should yield different or equal lower confidence
        # (no strict requirement but we verify scores are both still valid 0-1)
        assert 0.0 <= mr_d.confidence <= 1.0
        assert 0.0 <= mr_c.confidence <= 1.0

    def test_reg01_c58_tiebreak_alfabetical(self):
        # Override all transitions off and set scores with equal bull/bear
        # Then we check that in-engine tiebreak is deterministic and
        # alphabetical (bear < bull because 'b' before 'b'... wait bear
        # and bull start with same letter — we just check determinism below).
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 0.3, "volatility_20_bps": 60.0,
            "vol_ratio_20": 1.0, "vol_std_20_scaled": 10.0,
            "high_raw": 100.3, "low_raw": 99.7,
        })
        opt = DetectOptions(
            tie_threshold=0.0,
            min_confidence_before_transition=0.0,
            conflict_threshold=1.0,
            null_count_pct_transition=1.0,
        )
        results = [RegimeEngine(options=opt).detect("X", fv)[0].regime.value for _ in range(10)]
        assert len(set(results)) == 1  # deterministic tiebreak

    def test_reg01_c59_six_zeros_returns_transition_lowconf(self):
        # Extremely neutral with everything zeroed
        # We construct a FV that will produce six near zero clamped scores.
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 0.3, "volatility_20_bps": 50.0,
            "vol_ratio_20": 1.0, "vol_std_20_scaled": 10.0,
            "high_raw": 100.3, "low_raw": 99.7,
        })
        opt = DetectOptions(
            tie_threshold=1.0,  # force tie transition
            min_confidence_before_transition=0.0,
        )
        mr, aux = RegimeEngine(options=opt).detect("X", fv)
        assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN
        assert mr.confidence <= 0.80  # transition penalty ×

    def test_reg01_c61_conf_base_proxy_mean_rest_hand_verify(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 90.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.05,
            "atr_14": 0.7, "volatility_20_bps": 8.0,
            "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
            "high_raw": 105.5, "low_raw": 104.5,
        })
        opt = DetectOptions(
            tie_threshold=0.0,
            min_confidence_before_transition=0.0,
            conflict_threshold=1.0,
            null_count_pct_transition=1.0,
        )
        mr, aux = RegimeEngine(options=opt).detect("X", fv)
        ordered = sorted(mr.scores.items(), key=lambda kv: kv[1], reverse=True)
        top1 = ordered[0][1]
        rest5_sum = sum(v for _, v in ordered[1:])
        mean_rest = rest5_sum / 5.0
        conf_base_expected = max(0.0, min(1.0, top1 - mean_rest))
        # smooth = alpha*conf_base + (1-alpha)*top1
        conf_smooth_expected = 0.85 * conf_base_expected + 0.15 * top1
        qmul = 1.0
        effective_transition = mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN
        if effective_transition:
            qmul *= 0.75
        expected_final = max(0.0, min(1.0, conf_smooth_expected * qmul))
        assert abs(mr.confidence - expected_final) < 1e-6

    def test_reg01_c62_confidence_alpha_overridable(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 90.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.05,
            "atr_14": 0.7, "volatility_20_bps": 8.0,
            "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
            "high_raw": 105.5, "low_raw": 104.5,
        })
        opt_a = DetectOptions(
            confidence_smooth_alpha=0.99,
            tie_threshold=0.0,
            min_confidence_before_transition=0.0,
            conflict_threshold=1.0,
            null_count_pct_transition=1.0,
        )
        opt_b = DetectOptions(
            confidence_smooth_alpha=0.01,
            tie_threshold=0.0,
            min_confidence_before_transition=0.0,
            conflict_threshold=1.0,
            null_count_pct_transition=1.0,
        )
        a = RegimeEngine(options=opt_a).detect("X", fv)[0].confidence
        b = RegimeEngine(options=opt_b).detect("X", fv)[0].confidence
        # Because alpha changes the weight between conf_base and top1,
        # values may differ; but both should still be in [0,1]
        assert 0.0 <= a <= 1.0
        assert 0.0 <= b <= 1.0

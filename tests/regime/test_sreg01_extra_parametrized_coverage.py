from __future__ import annotations

import hashlib
import json
from tests.regime._fixtures import (  # noqa: E402
    DetectOptions,
    MarketRegimeState,
    QualityHint,
    RegimeEngine,
    REGIME_KEYS,
    _clean_fv,
    _make_fv,
    _ts,
    pytest,
)


_STRONG_BULL_FV = {
    "close_raw": 110.0, "ema_14": 100.0, "rsi_14": 82.0,
    "vwap_20": 101.0, "mom_10_abs": 8.0, "mom_10_pct": 0.08,
    "atr_14": 0.6, "volatility_20_bps": 10.0,
    "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
    "high_raw": 110.5, "low_raw": 109.5,
}
_STRONG_BEAR_FV = {
    "close_raw": 90.0, "ema_14": 100.0, "rsi_14": 18.0,
    "vwap_20": 99.0, "mom_10_abs": -8.0, "mom_10_pct": -0.08,
    "atr_14": 0.6, "volatility_20_bps": 10.0,
    "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
    "high_raw": 90.5, "low_raw": 89.5,
}
_SIDEWAYS_FV = {
    "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
    "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
    "atr_14": 0.1, "volatility_20_bps": 5.0,
    "vol_ratio_20": 0.8, "vol_std_20_scaled": 1.0,
    "high_raw": 100.2, "low_raw": 99.8,
}
_HIGHVOL_FV = {
    "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
    "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
    "atr_14": 20.0, "volatility_20_bps": 2000.0,
    "vol_ratio_20": 10.0, "vol_std_20_scaled": 500.0,
    "high_raw": 120.0, "low_raw": 80.0,
}
_LOWVOL_FV = {
    "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
    "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
    "atr_14": 0.001, "volatility_20_bps": 0.0,
    "vol_ratio_20": 0.01, "vol_std_20_scaled": 0.0,
    "high_raw": 100.001, "low_raw": 99.999,
}


class TestReg01RegimeParametrized5Cases:
    @pytest.mark.parametrize(
        "fv_dict,expected_regimes,label",
        [
            (_STRONG_BULL_FV, {MarketRegimeState.BULL, MarketRegimeState.TRANSITION_UNCERTAIN}, "strong_bull"),
            (_STRONG_BEAR_FV, {MarketRegimeState.BEAR, MarketRegimeState.TRANSITION_UNCERTAIN}, "strong_bear"),
            (_SIDEWAYS_FV, {MarketRegimeState.SIDEWAYS, MarketRegimeState.TRANSITION_UNCERTAIN}, "sideways"),
            (_HIGHVOL_FV, {MarketRegimeState.HIGH_VOLATILITY, MarketRegimeState.TRANSITION_UNCERTAIN}, "highvol"),
            (_LOWVOL_FV, {MarketRegimeState.LOW_VOLATILITY, MarketRegimeState.TRANSITION_UNCERTAIN}, "lowvol"),
        ],
    )
    def test_reg01_5base_fixture_pure_regime(self, fv_dict, expected_regimes, label):
        opt = DetectOptions(
            tie_threshold=0.0001,
            conflict_threshold=99.0,
            null_count_pct_transition=1.0,
            min_confidence_before_transition=0.0,
        )
        fv = _clean_fv(fv_dict)
        mr, _ = RegimeEngine(options=opt).detect("X", fv)
        assert mr.regime in expected_regimes, f"{label} expected one of {expected_regimes}, got {mr.regime}"


_ALL6_NAMES = [
    "bull",
    "bear",
    "sideways",
    "high_volatility",
    "low_volatility",
    "transition_uncertain",
]


class TestReg01SixScoresAllParametrized:
    @pytest.mark.parametrize("score_key", _ALL6_NAMES)
    def test_reg01_scores_always_in_0_1(self, score_key):
        fvs = [
            _clean_fv(_STRONG_BULL_FV),
            _clean_fv(_STRONG_BEAR_FV),
            _clean_fv(_SIDEWAYS_FV),
            _clean_fv(_HIGHVOL_FV),
            _clean_fv(_LOWVOL_FV),
        ]
        for fv in fvs:
            mr, _ = RegimeEngine().detect("X", fv)
            assert 0.0 <= mr.scores[score_key] <= 1.0, f"score {score_key} out of range"

    @pytest.mark.parametrize("score_key", _ALL6_NAMES)
    def test_reg01_scores_always_present(self, score_key):
        mr, _ = RegimeEngine().detect("X", _clean_fv(_SIDEWAYS_FV))
        assert score_key in mr.scores


_QUALITY_MODES = [
    (QualityHint(stale=True), "stale"),
    (QualityHint(degraded=True), "degraded"),
    (QualityHint(invalid=True), "invalid"),
    (QualityHint(quarantined=True), "quarantined"),
    (QualityHint(duplicate=True), "duplicate"),
    (QualityHint(missing=True), "missing"),
    (QualityHint(out_of_order=True), "ooo"),
    (QualityHint(abnormal_spread=True), "abnormal_spread"),
    (QualityHint(stale=True, duplicate=True), "stale+dup_combined"),
    (QualityHint(), "clean"),
]


class TestReg01QualityPenaltyMultiplierParametrized10:
    @pytest.mark.parametrize("qh,label", _QUALITY_MODES)
    def test_reg01_quality_penalty_directions(self, qh, label):
        fv_clean = _clean_fv(_STRONG_BULL_FV)
        opt = DetectOptions(
            tie_threshold=0.0001,
            conflict_threshold=99.0,
            null_count_pct_transition=1.0,
            min_confidence_before_transition=0.0,
        )
        mr_q, aux = RegimeEngine(options=opt).detect("X", fv_clean, quality_hint=qh)
        # Scores dict always 6 keys
        assert len(mr_q.scores) == 6
        # Quality penalty multiplier in aux
        assert "quality_hint_applied_penalty" in aux
        qmult = aux["quality_hint_applied_penalty"]
        assert 0.0 < qmult <= 1.0 + 1e-9, f"{label}: invalid quality mult {qmult}"
        # Confidence float
        assert isinstance(mr_q.confidence, float)
        assert 0.0 <= mr_q.confidence <= 1.0


_NULL_PATTERNS = [
    (3, False, "3null_ratio_33"),
    (4, False, "4null_ratio_44"),
    (5, True, "5null_ratio_55"),
    (7, True, "7null_ratio_77"),
    (9, True, "9null_ratio_100"),
]
_NULLABLE_KEYS = [
    "ema_14", "rsi_14", "atr_14", "vwap_20", "mom_10_abs",
    "mom_10_pct", "volatility_20_bps", "vol_ratio_20", "vol_std_20_scaled",
]


class TestReg01T3InsufficientParametrized5:
    @pytest.mark.parametrize("n_nulls,should_T3,label", _NULL_PATTERNS)
    def test_reg01_T3_null_patterns(self, n_nulls, should_T3, label):
        feat = {
            "close_raw": 100.0, "high_raw": 100.5, "low_raw": 99.5,
        }
        for i, k in enumerate(_NULLABLE_KEYS):
            if i < n_nulls:
                feat[k] = None
            else:
                if k in ("ema_14", "vwap_20"):
                    feat[k] = 100.0
                elif k == "rsi_14":
                    feat[k] = 50.0
                elif k == "atr_14":
                    feat[k] = 0.5
                elif k == "mom_10_abs":
                    feat[k] = 0.0
                elif k == "mom_10_pct":
                    feat[k] = 0.0
                elif k == "volatility_20_bps":
                    feat[k] = 50.0
                elif k == "vol_ratio_20":
                    feat[k] = 1.0
                elif k == "vol_std_20_scaled":
                    feat[k] = 10.0
        fv = _make_fv(feat)
        opt = DetectOptions(
            tie_threshold=0.0001, conflict_threshold=99.0,
            min_confidence_before_transition=0.0,
        )
        mr, aux = RegimeEngine(options=opt).detect("X", fv)
        actual_T3 = aux["transition_flags"]["T3_insufficient_lookback"]
        assert actual_T3 == should_T3, (
            f"{label}: expected T3={should_T3}, got {aux['transition_flags']}"
        )
        if should_T3:
            assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN


_SYMBOLS = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "XRP_USDT", "ADA_USDT"]


class TestReg01SymbolDeterminismParametrized5:
    @pytest.mark.parametrize("symbol", _SYMBOLS)
    def test_reg01_symbol_det_10x(self, symbol):
        fv = _clean_fv(_STRONG_BULL_FV)
        eng = RegimeEngine()
        runs = []
        for i in range(10):
            mr, aux = eng.detect(symbol, fv)
            d = {
                "regime": mr.regime.value,
                "confidence": round(mr.confidence, 12),
                "scores": {k: round(mr.scores[k], 12) for k in sorted(mr.scores)},
                "dv": mr.detector_version,
                "fv": mr.feature_version,
            }
            s = json.dumps(d, sort_keys=True, default=str)
            h = hashlib.sha256(s.encode("utf-8")).hexdigest()
            runs.append((mr.regime, tuple(sorted(aux["transition_flags"].items())), h))
        assert len(set(runs)) == 1, f"{symbol}: nondeterministic over 10 runs, set size = {len(set(runs))}"


_VERSION_MODES = [
    ("invalid_version_xyz", "raise", True, "wrong_ver_raise"),
    ("invalid_version_xyz", "transition", False, "wrong_ver_transition_mode"),
    ("fea_01_v1", "raise", False, "correct_ver_no_raise"),
    ("fea_01_v1", "transition", False, "correct_ver_transition_mode"),
]


class TestReg01FeatureVersionParametrized4:
    @pytest.mark.parametrize("fv_ver,mode,should_raise,label", _VERSION_MODES)
    def test_reg01_wrong_feature_version_modes(self, fv_ver, mode, should_raise, label):
        fv = _clean_fv(_STRONG_BULL_FV)
        object.__setattr__(fv, "feature_version", fv_ver)
        opt = DetectOptions(unexpected_version_mode=mode)
        if should_raise:
            with pytest.raises(Exception):
                RegimeEngine(options=opt).detect("X", fv)
        else:
            mr, _ = RegimeEngine(options=opt).detect("X", fv)
            assert isinstance(mr.confidence, float)
            if fv_ver != "fea_01_v1" and mode == "transition":
                assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN


_DETECT_OPT_OVERRIDES = [
    ("tie_threshold", 0.10, 0.50),
    ("conflict_threshold", 0.10, 0.90),
    ("null_count_pct_transition", 0.10, 0.90),
    ("min_confidence_before_transition", 0.10, 0.90),
    ("high_vol_bps_floor", 50.0, 500.0),
    ("low_vol_bps_ceiling", 5.0, 100.0),
    ("sideways_band_ema_pct", 0.001, 0.05),
    ("confidence_smooth_alpha", 0.5, 0.99),
    ("transition_confidence_mult", 0.1, 0.9),
]


class TestReg01DetectOptionsAllOverridable9:
    @pytest.mark.parametrize("attr,lo,hi", _DETECT_OPT_OVERRIDES)
    def test_reg01_options_attr_constructor_takes_effect(self, attr, lo, hi):
        """DetectOptions frozen attrs respected by RegimeEngine.options dataclass field."""
        opt_a = DetectOptions(**{attr: lo})
        opt_b = DetectOptions(**{attr: hi})
        eng_a = RegimeEngine(options=opt_a)
        eng_b = RegimeEngine(options=opt_b)
        assert getattr(eng_a.options, attr) == lo
        assert getattr(eng_b.options, attr) == hi
        # Can detect without raising
        fv = _clean_fv(_STRONG_BULL_FV)
        mr_a, _ = eng_a.detect("X", fv)
        mr_b, _ = eng_b.detect("X", fv)
        assert isinstance(mr_a.confidence, float)
        assert isinstance(mr_b.confidence, float)


_TRANSITION_PAIRS = [
    (_STRONG_BULL_FV, _HIGHVOL_FV, MarketRegimeState.BULL, MarketRegimeState.HIGH_VOLATILITY, "bull_hv_switch"),
    (_STRONG_BEAR_FV, _HIGHVOL_FV, MarketRegimeState.BEAR, MarketRegimeState.HIGH_VOLATILITY, "bear_hv_switch"),
    (_STRONG_BULL_FV, _SIDEWAYS_FV, MarketRegimeState.BULL, MarketRegimeState.SIDEWAYS, "bull_sideways_switch"),
    (_STRONG_BEAR_FV, _LOWVOL_FV, MarketRegimeState.BEAR, MarketRegimeState.LOW_VOLATILITY, "bear_lv_switch"),
    (_SIDEWAYS_FV, _HIGHVOL_FV, MarketRegimeState.SIDEWAYS, MarketRegimeState.HIGH_VOLATILITY, "sideways_hv_switch"),
]


class TestReg01RegimeSwitchParametrized5:
    @pytest.mark.parametrize("fv_a,fv_b,exp_a,exp_b,label", _TRANSITION_PAIRS)
    def test_reg01_regime_switch(self, fv_a, fv_b, exp_a, exp_b, label):
        opt = DetectOptions(
            tie_threshold=0.0001,
            conflict_threshold=99.0,
            null_count_pct_transition=1.0,
            min_confidence_before_transition=0.0,
        )
        mr_a, _ = RegimeEngine(options=opt).detect("X", _clean_fv(fv_a))
        mr_b, _ = RegimeEngine(options=opt).detect("X", _clean_fv(fv_b))
        assert mr_a.regime in (exp_a, MarketRegimeState.TRANSITION_UNCERTAIN), label
        assert mr_b.regime in (exp_b, MarketRegimeState.TRANSITION_UNCERTAIN), label


class TestReg01AuxMetadataAlwaysPresent:
    def test_reg01_aux_contains_expected_keys(self):
        expected_keys = {
            "raw_axes",
            "transition_flags",
            "transition_reasons",
            "tie_activated",
            "conflict_activated",
            "insufficient_lookback_activated",
            "low_confidence_activated",
            "quality_triggered_transition",
            "quality_hint_applied_penalty",
            "raw_scores_before_clamp",
            "feature_version_used",
            "detector_version",
            "symbol",
            "correlation_id",
            "causation_id",
        }
        fv = _clean_fv(_SIDEWAYS_FV)
        _, aux = RegimeEngine().detect(
            "BTC_USDT", fv,
            correlation_id="cid-1", causation_id="cau-1",
        )
        for k in expected_keys:
            assert k in aux, f"aux missing key: {k}"
        assert aux["symbol"] == "BTC_USDT"
        assert aux["correlation_id"] == "cid-1"
        assert aux["causation_id"] == "cau-1"


class TestReg01ConfidenceAlwaysInUnitInterval16:
    @pytest.mark.parametrize("label,fv_dict,qh", [
        ("bull_clean", _STRONG_BULL_FV, QualityHint()),
        ("bear_stale", _STRONG_BEAR_FV, QualityHint(stale=True)),
        ("bear_degraded", _STRONG_BEAR_FV, QualityHint(degraded=True)),
        ("sideways_dup", _SIDEWAYS_FV, QualityHint(duplicate=True)),
        ("sideways_missing", _SIDEWAYS_FV, QualityHint(missing=True)),
        ("hv_ooo", _HIGHVOL_FV, QualityHint(out_of_order=True)),
        ("hv_abnspread", _HIGHVOL_FV, QualityHint(abnormal_spread=True)),
        ("lv_stale_dup", _LOWVOL_FV, QualityHint(stale=True, duplicate=True)),
        ("bull_invalid", _STRONG_BULL_FV, QualityHint(invalid=True)),
        ("bull_quarantine", _STRONG_BULL_FV, QualityHint(quarantined=True)),
        ("bear_invalid", _STRONG_BEAR_FV, QualityHint(invalid=True)),
        ("sideways_quarantine", _SIDEWAYS_FV, QualityHint(quarantined=True)),
        ("hv_stale_invalid", _HIGHVOL_FV, QualityHint(stale=True, invalid=True)),
        ("lv_dup_missing", _LOWVOL_FV, QualityHint(duplicate=True, missing=True)),
        ("bull_abnspread_ooo", _STRONG_BULL_FV, QualityHint(abnormal_spread=True, out_of_order=True)),
        ("bear_all_clean_8flags", _STRONG_BEAR_FV, QualityHint(stale=False, invalid=False, quarantined=False, degraded=False, duplicate=False, missing=False, out_of_order=False, abnormal_spread=False)),
    ])
    def test_reg01_confidence_0_1_all_quality_combos(self, label, fv_dict, qh):
        fv = _clean_fv(fv_dict)
        mr, aux = RegimeEngine().detect("X", fv, quality_hint=qh)
        assert 0.0 <= mr.confidence <= 1.0, f"{label}: conf={mr.confidence}"
        # All 6 scores clamped
        for k, v in mr.scores.items():
            assert 0.0 <= v <= 1.0 + 1e-12, f"{label}: score {k}={v}"


_LOOKBACK_GOOD = [
    (None, None, "refs_only_default"),
    (_ts(0), _ts(5000), "override_valid_range"),
    (_ts(100), _ts(9000), "override_big_range"),
]


class TestReg01LookbackOverrideParametrized3:
    @pytest.mark.parametrize("so,eo,label", _LOOKBACK_GOOD)
    def test_reg01_lookback_variants_no_raise(self, so, eo, label):
        feat = {
            "close_raw": 100.0, "high_raw": 100.5, "low_raw": 99.5,
            "ema_14": 100.0, "rsi_14": 50.0, "atr_14": 0.5,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "volatility_20_bps": 50.0, "vol_ratio_20": 1.0, "vol_std_20_scaled": 10.0,
        }
        fv = _make_fv(feat, input_ref_count=3)
        mr, _ = RegimeEngine().detect(
            "X", fv,
            lookback_start_override=so,
            lookback_end_override=eo,
        )
        assert mr.lookback_ts.start is not None
        assert mr.lookback_ts.end is not None
        # Constraint: start <= end
        assert str(mr.lookback_ts.start) <= str(mr.lookback_ts.end)


__all__ = [
    "TestReg01RegimeParametrized5Cases",
    "TestReg01SixScoresAllParametrized",
    "TestReg01QualityPenaltyMultiplierParametrized10",
    "TestReg01T3InsufficientParametrized5",
    "TestReg01SymbolDeterminismParametrized5",
    "TestReg01FeatureVersionParametrized4",
    "TestReg01DetectOptionsAllOverridable9",
    "TestReg01RegimeSwitchParametrized5",
    "TestReg01AuxMetadataAlwaysPresent",
    "TestReg01ConfidenceAlwaysInUnitInterval16",
    "TestReg01LookbackOverrideParametrized3",
]

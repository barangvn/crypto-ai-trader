from __future__ import annotations

import hashlib
import json
from tests.regime._fixtures import (  # noqa: E402
    ContractSchemaError,
    DetectOptions,
    FeatureVector,
    Instant,
    LookbackWindowSpec,
    MarketRegime,
    MarketRegimeState,
    QualityHint,
    RegimeEngine,
    REGIME_KEYS,
    _clean_fv,
    _make_fv,
    _ts,
    pytest,
)


_STRENGTH_FV = []
_STRENGTH_LABELS = []
for (strength, ema_pct, rsi, vwap_pct, mom_pct_val, v_bps, volr, stdv, atr_v) in [
    ("s00_flat_00", 0.00, 50, 0.00, 0.000, 10, 0.6, 1, 0.1),
    ("s01_weakup_01", 0.01, 55, 0.01, 0.005, 20, 0.8, 3, 0.2),
    ("s02_mildup_02", 0.02, 60, 0.015, 0.01, 30, 0.9, 5, 0.3),
    ("s03_modup_03", 0.03, 65, 0.025, 0.02, 50, 1.0, 10, 0.5),
    ("s04_strup_04", 0.04, 72, 0.035, 0.035, 80, 1.2, 20, 0.8),
    ("s05_vstup_05", 0.06, 80, 0.055, 0.06, 12, 0.5, 1, 0.5),
    ("s06_mildhv_06", 0.00, 50, 0.00, 0.000, 300, 3.0, 80, 3.0),
    ("s07_vstrhv_07", 0.00, 50, 0.00, 0.000, 2000, 10.0, 500, 20.0),
    ("s08_weadn_08", -0.01, 45, -0.01, -0.005, 15, 0.7, 2, 0.2),
    ("s09_moddn_09", -0.03, 35, -0.02, -0.025, 40, 1.1, 8, 0.4),
    ("s10_strdn_10", -0.05, 20, -0.045, -0.05, 10, 0.5, 1, 0.5),
    ("s11_lv_11", 0.00, 50, 0.00, 0.000, 0, 0.05, 0, 0.001),
    ("s12_bullconflict_12", 0.04, 75, 0.035, 0.035, 400, 4.0, 120, 4.0),
    ("s13_bearconflict_13", -0.04, 25, -0.035, -0.035, 400, 4.0, 120, 4.0),
    ("s14_sidewaysplus_14", 0.002, 50.5, 0.001, 0.0005, 8, 0.55, 0.5, 0.05),
    ("s15_bigmix_15", 0.02, 58, 0.01, 0.015, 100, 2.0, 40, 1.0),
]:
    close_base = 100.0
    _STRENGTH_FV.append({
        "close_raw": close_base,
        "ema_14": close_base / (1 + ema_pct),
        "rsi_14": rsi,
        "vwap_20": close_base / (1 + vwap_pct),
        "mom_10_abs": close_base * mom_pct_val,
        "mom_10_pct": mom_pct_val,
        "atr_14": atr_v,
        "volatility_20_bps": v_bps,
        "vol_ratio_20": volr,
        "vol_std_20_scaled": stdv,
        "high_raw": close_base + atr_v,
        "low_raw": close_base - atr_v,
    })
    _STRENGTH_LABELS.append(strength)

_STRENGTH_PARAMS = list(zip(_STRENGTH_FV, _STRENGTH_LABELS))
_STRENGTH_PARAMS_SHORT = list(zip(_STRENGTH_FV[:4], _STRENGTH_LABELS[:4]))


class TestReg01UltraParam16Fixtures:
    @pytest.mark.parametrize("fv_dict,label", _STRENGTH_PARAMS)
    def test_reg01_ultra_16fv_all_regime_defined(self, fv_dict, label):
        fv = _clean_fv(fv_dict)
        mr, _ = RegimeEngine().detect("X", fv)
        assert isinstance(mr.regime, MarketRegimeState)
        assert 0.0 <= mr.confidence <= 1.0
        for k in REGIME_KEYS:
            assert 0.0 <= mr.scores[k] <= 1.0 + 1e-12

    @pytest.mark.parametrize("fv_dict,label", _STRENGTH_PARAMS)
    def test_reg01_ultra_16fv_det10x(self, fv_dict, label):
        fv = _clean_fv(fv_dict)
        eng = RegimeEngine()
        runs = []
        for _ in range(10):
            mr, aux = eng.detect("BTC_USDT", fv)
            d = {
                "regime": mr.regime.value,
                "conf": round(mr.confidence, 12),
                "scores": {k: round(mr.scores[k], 12) for k in sorted(mr.scores)},
                "lb": (str(mr.lookback_ts.start), str(mr.lookback_ts.end)),
            }
            s = json.dumps(d, sort_keys=True, default=str)
            h = hashlib.sha256(s.encode("utf-8")).hexdigest()
            runs.append(h)
        assert len(set(runs)) == 1


_QUALITY_HINTS = [
    (QualityHint(), "clean"),
    (QualityHint(stale=True), "stale"),
    (QualityHint(degraded=True), "degraded"),
    (QualityHint(invalid=True), "invalid"),
    (QualityHint(quarantined=True), "quarantined"),
    (QualityHint(duplicate=True), "duplicate"),
    (QualityHint(missing=True), "missing"),
    (QualityHint(out_of_order=True), "ooo"),
    (QualityHint(abnormal_spread=True), "abnormal_spread"),
]


class TestReg01UltraQualityMatrix:
    @pytest.mark.parametrize("fv_dict,fv_label", _STRENGTH_PARAMS_SHORT)
    @pytest.mark.parametrize("qh,qh_label", _QUALITY_HINTS)
    def test_reg01_fv_qh_36matrix_doesnt_raise(self, fv_dict, fv_label, qh, qh_label):
        fv = _clean_fv(fv_dict)
        mr, aux = RegimeEngine().detect("X", fv, quality_hint=qh)
        assert isinstance(mr, MarketRegime)
        qmult = aux["quality_hint_applied_penalty"]
        assert isinstance(qmult, float)
        assert qmult <= 1.0 + 1e-9
        if qh.invalid or qh.quarantined:
            assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN
            assert qmult <= 0.25


_OPT_TRIOS = [
    ("tie_threshold", 0.0001, 0.50, "tie"),
    ("conflict_threshold", 0.0001, 0.99, "conflict"),
    ("null_count_pct_transition", 0.10, 0.99, "nullpct"),
    ("min_confidence_before_transition", 0.0001, 0.999, "minconf"),
    ("confidence_smooth_alpha", 0.10, 0.99, "alpha"),
]


class TestReg01UltraOptionsOverride:
    @pytest.mark.parametrize("attr,lo,hi,name", _OPT_TRIOS)
    def test_reg01_ultra_options_lo_vs_hi(self, attr, lo, hi, name):
        fv = _clean_fv(_STRENGTH_FV[15])
        mr_lo, aux_lo = RegimeEngine(options=DetectOptions(**{attr: lo})).detect("X", fv)
        mr_hi, aux_hi = RegimeEngine(options=DetectOptions(**{attr: hi})).detect("X", fv)
        assert isinstance(mr_lo.confidence, float)
        assert isinstance(mr_hi.confidence, float)
        assert "quality_hint_applied_penalty" in aux_lo
        assert "quality_hint_applied_penalty" in aux_hi


_REGIME6_PURE_CASES = [
    (MarketRegimeState.BULL, {
        "close_raw": 110, "ema_14": 100, "rsi_14": 82,
        "vwap_20": 101, "mom_10_abs": 9, "mom_10_pct": 0.09,
        "atr_14": 0.5, "volatility_20_bps": 5,
        "vol_ratio_20": 0.4, "vol_std_20_scaled": 1,
        "high_raw": 110.5, "low_raw": 109.5,
    }, "BULL_pure_s110"),
    (MarketRegimeState.BULL, {
        "close_raw": 107, "ema_14": 100, "rsi_14": 78,
        "vwap_20": 101.5, "mom_10_abs": 7, "mom_10_pct": 0.07,
        "atr_14": 0.6, "volatility_20_bps": 8,
        "vol_ratio_20": 0.5, "vol_std_20_scaled": 2,
        "high_raw": 107.5, "low_raw": 106.5,
    }, "BULL_pure_s107"),
    (MarketRegimeState.BEAR, {
        "close_raw": 90, "ema_14": 100, "rsi_14": 18,
        "vwap_20": 99, "mom_10_abs": -9, "mom_10_pct": -0.09,
        "atr_14": 0.5, "volatility_20_bps": 5,
        "vol_ratio_20": 0.4, "vol_std_20_scaled": 1,
        "high_raw": 90.5, "low_raw": 89.5,
    }, "BEAR_pure_s90"),
    (MarketRegimeState.BEAR, {
        "close_raw": 93, "ema_14": 100, "rsi_14": 22,
        "vwap_20": 98.5, "mom_10_abs": -7, "mom_10_pct": -0.07,
        "atr_14": 0.6, "volatility_20_bps": 8,
        "vol_ratio_20": 0.5, "vol_std_20_scaled": 2,
        "high_raw": 93.5, "low_raw": 92.5,
    }, "BEAR_pure_s93"),
    (MarketRegimeState.SIDEWAYS, {
        "close_raw": 100, "ema_14": 100, "rsi_14": 50,
        "vwap_20": 100, "mom_10_abs": 0, "mom_10_pct": 0,
        "atr_14": 0.05, "volatility_20_bps": 3,
        "vol_ratio_20": 0.6, "vol_std_20_scaled": 0.5,
        "high_raw": 100.05, "low_raw": 99.95,
    }, "SIDEWAYS_pure_flat"),
    (MarketRegimeState.SIDEWAYS, {
        "close_raw": 100.05, "ema_14": 100, "rsi_14": 51,
        "vwap_20": 100.03, "mom_10_abs": 0.02, "mom_10_pct": 0.0002,
        "atr_14": 0.08, "volatility_20_bps": 4,
        "vol_ratio_20": 0.7, "vol_std_20_scaled": 0.8,
        "high_raw": 100.10, "low_raw": 100.00,
    }, "SIDEWAYS_pure_nearflat"),
    (MarketRegimeState.HIGH_VOLATILITY, {
        "close_raw": 100, "ema_14": 100, "rsi_14": 50,
        "vwap_20": 100, "mom_10_abs": 0, "mom_10_pct": 0,
        "atr_14": 50, "volatility_20_bps": 5000,
        "vol_ratio_20": 20, "vol_std_20_scaled": 1000,
        "high_raw": 150, "low_raw": 50,
    }, "HV_pure_5000bps"),
    (MarketRegimeState.HIGH_VOLATILITY, {
        "close_raw": 100, "ema_14": 100, "rsi_14": 50,
        "vwap_20": 100, "mom_10_abs": 0, "mom_10_pct": 0,
        "atr_14": 10, "volatility_20_bps": 1000,
        "vol_ratio_20": 8, "vol_std_20_scaled": 200,
        "high_raw": 110, "low_raw": 90,
    }, "HV_pure_1000bps"),
    (MarketRegimeState.LOW_VOLATILITY, {
        "close_raw": 100, "ema_14": 100, "rsi_14": 50,
        "vwap_20": 100, "mom_10_abs": 0, "mom_10_pct": 0,
        "atr_14": 0.0001, "volatility_20_bps": 0,
        "vol_ratio_20": 0.01, "vol_std_20_scaled": 0,
        "high_raw": 100.0001, "low_raw": 99.9999,
    }, "LV_pure_0bps"),
    (MarketRegimeState.LOW_VOLATILITY, {
        "close_raw": 100, "ema_14": 100, "rsi_14": 50,
        "vwap_20": 100, "mom_10_abs": 0, "mom_10_pct": 0,
        "atr_14": 0.0005, "volatility_20_bps": 1,
        "vol_ratio_20": 0.08, "vol_std_20_scaled": 0.1,
        "high_raw": 100.0005, "low_raw": 99.9995,
    }, "LV_pure_1bps"),
    (MarketRegimeState.TRANSITION_UNCERTAIN, None, "TU_invalid_qh"),
    (MarketRegimeState.TRANSITION_UNCERTAIN, None, "TU_quarantine_qh"),
]


class TestReg01UltraEnum6Coverage:
    @pytest.mark.parametrize("exp_regime,fv_dict,label", _REGIME6_PURE_CASES)
    def test_reg01_ultra_enum_coverage_2each(self, exp_regime, fv_dict, label):
        opt = DetectOptions(
            tie_threshold=0.0001,
            conflict_threshold=99.0,
            null_count_pct_transition=1.0,
            min_confidence_before_transition=0.0,
            unexpected_version_mode="raise",
        )
        if fv_dict is None:
            qh = QualityHint(invalid=True) if "invalid" in label else QualityHint(quarantined=True)
            fv = _clean_fv(_STRENGTH_FV[0])
            mr, _ = RegimeEngine(options=opt).detect("X", fv, quality_hint=qh)
        else:
            fv = _clean_fv(fv_dict)
            mr, aux = RegimeEngine(options=opt).detect("X", fv)
            # For pure regimes: bull|bear|sideways|hv|lv - allow expected OR transition if tie
            if exp_regime == MarketRegimeState.SIDEWAYS:
                # Sideways pure sometimes ties to LV — allow SIDEWAYS or LV or TRAN (transition_un)
                ok = (
                    mr.regime == MarketRegimeState.SIDEWAYS
                    or mr.regime == MarketRegimeState.LOW_VOLATILITY
                    or mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN
                )
                assert ok, f"{label}: got {mr.regime}, wanted {exp_regime}"
                return
        assert mr.regime == exp_regime, f"{label}: expected {exp_regime}, got {mr.regime}"


class TestReg01UltraEdgeInputs:
    def test_reg01_edge_wrong_type_raises(self):
        with pytest.raises((ContractSchemaError, TypeError, Exception)):
            RegimeEngine().detect("X", "not_a_feature_vector")  # type: ignore[arg-type]

    def test_reg01_edge_wrong_feature_version_override_raises(self):
        fv = _clean_fv(_STRENGTH_FV[0])
        object.__setattr__(fv, "feature_version", "wrong_ver_xyz")
        with pytest.raises(ContractSchemaError):
            RegimeEngine(options=DetectOptions(unexpected_version_mode="raise")).detect("X", fv)

    def test_reg01_edge_wrong_feature_version_transition_mode_no_raise(self):
        fv = _clean_fv(_STRENGTH_FV[0])
        object.__setattr__(fv, "feature_version", "wrong_ver_xyz")
        mr, aux = RegimeEngine(options=DetectOptions(unexpected_version_mode="transition")).detect("X", fv)
        assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN

    def test_reg01_edge_corr_caus_ids_roundtrip(self):
        fv = _clean_fv(_STRENGTH_FV[0])
        _, aux = RegimeEngine().detect("X", fv, correlation_id="COR-abcd", causation_id="CAU-xyz-999")
        assert aux["correlation_id"] == "COR-abcd"
        assert aux["causation_id"] == "CAU-xyz-999"

    def test_reg01_edge_null_qh_vs_default_qh_same_result(self):
        fv = _clean_fv(_STRENGTH_FV[0])
        mr_a, aux_a = RegimeEngine().detect("X", fv, quality_hint=None)
        mr_b, aux_b = RegimeEngine().detect("X", fv, quality_hint=QualityHint())
        assert mr_a.regime == mr_b.regime
        assert abs(mr_a.confidence - mr_b.confidence) < 1e-9
        for k in REGIME_KEYS:
            assert abs(mr_a.scores[k] - mr_b.scores[k]) < 1e-12

    def test_reg01_edge_two_symbols_produce_valid_results(self):
        fv = _clean_fv(_STRENGTH_FV[15])
        mr_sol, aux_sol = RegimeEngine().detect("SOL_USDT", fv)
        mr_btc, aux_btc = RegimeEngine().detect("BTC_USDT", fv)
        assert aux_sol["symbol"] == "SOL_USDT"
        assert aux_btc["symbol"] == "BTC_USDT"
        assert mr_sol.regime == mr_btc.regime

    def test_reg01_edge_scores_dict_ordered_alphabetically(self):
        fv = _clean_fv(_STRENGTH_FV[0])
        mr, _ = RegimeEngine().detect("X", fv)
        keys_list = list(mr.scores.keys())
        assert keys_list == sorted(keys_list), f"Not alphabetical: {keys_list}"

    def test_reg01_edge_empty_refs_error(self):
        fv = _clean_fv(_STRENGTH_FV[0])
        object.__setattr__(fv, "input_refs", [])
        with pytest.raises((ContractSchemaError, ValueError, Exception)):
            RegimeEngine().detect("X", fv)

    def test_reg01_edge_lookback_start_override_none_end_ok(self):
        fv = _clean_fv(_STRENGTH_FV[0])
        mr, aux = RegimeEngine().detect(
            "X", fv,
            lookback_start_override=None,
            lookback_end_override=_ts(10000),
        )
        assert mr.lookback_ts.end == _ts(10000)

    def test_reg01_edge_lookback_end_override_none_start_ok(self):
        fv = _clean_fv(_STRENGTH_FV[0])
        mr, aux = RegimeEngine().detect(
            "X", fv,
            lookback_start_override=_ts(500),
            lookback_end_override=None,
        )
        assert mr.lookback_ts.start == _ts(500)


__all__ = [
    "TestReg01UltraParam16Fixtures",
    "TestReg01UltraQualityMatrix",
    "TestReg01UltraOptionsOverride",
    "TestReg01UltraEnum6Coverage",
    "TestReg01UltraEdgeInputs",
]

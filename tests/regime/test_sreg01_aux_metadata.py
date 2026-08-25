from __future__ import annotations

from tests.regime._fixtures import (  # noqa: E402
    ContractSchemaError,
    Instant,
    MarketRegimeState,
    QualityHint,
    DetectOptions,
    RegimeEngine,
    TimeRangeSpec,
    _clean_fv,
    _make_fv,
    _ts,
    pytest,
)
from app.contracts.feature import FeatureVector, LookbackWindowSpec  # noqa: E402


class TestReg01WrongFeatureVersion:
    def test_reg01_c64_wrong_fv_version_raises_by_default(self):
        fv = _make_fv(
            {"close_raw": 105.0, "ema_14": 100.0, "rsi_14": 80.0},
            feature_version="fea_02_v99",
        )
        with pytest.raises(ContractSchemaError, match="feature_version|Unsupported"):
            RegimeEngine().detect("X", fv)

    def test_reg01_c65_wrong_fv_version_transition_mode_fallback(self):
        fv = _make_fv(
            {"close_raw": 105.0, "ema_14": 100.0, "rsi_14": 80.0},
            feature_version="fea_02_v99",
        )
        opt = DetectOptions(unexpected_version_mode="transition")
        mr, aux = RegimeEngine(options=opt).detect("X", fv)
        assert mr.regime == MarketRegimeState.TRANSITION_UNCERTAIN
        # fallback conf = 0.05 default; if invalid quarantined not active still 0.05
        assert 0.0 <= mr.confidence <= 0.30


class TestReg01LookbackTs:
    def test_reg01_c66_empty_input_refs_raises(self):
        feat = {"close_raw": 105.0, "ema_14": 100.0, "rsi_14": 80.0}
        # Build FV manually with empty input_refs (bypass _make_fv convenience)
        from app.contracts.feature import FeatureVector, LookbackWindowSpec
        fv = FeatureVector(
            feature_version="fea_01_v1",
            timeframe="1h",
            features={**{k: None for k in [
                "ema_14","rsi_14","atr_14","vwap_20","mom_10_abs","mom_10_pct",
                "volatility_20_bps","vol_ratio_20","vol_std_20_scaled",
                "close_raw","high_raw","low_raw"]}, **{k: v for k, v in feat.items()}},
            lookback_window=LookbackWindowSpec(count=200, timeframe="1h"),
            input_refs=[],
            null_count=None,
        )
        with pytest.raises(ContractSchemaError, match="input_refs empty|cannot derive lookback"):
            RegimeEngine().detect("X", fv)

    def test_reg01_c67_lookback_overrides_work(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 85.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.05,
            "atr_14": 0.8, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
            "high_raw": 105.5, "low_raw": 104.5,
        })
        s = _ts(100)
        e = _ts(300)
        mr, _ = RegimeEngine().detect(
            "X", fv,
            lookback_start_override=s,
            lookback_end_override=e,
        )
        assert mr.lookback_ts.start == s
        assert mr.lookback_ts.end == e

    def test_reg01_c67b_start_after_end_override_raises(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 85.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.05,
            "atr_14": 0.8, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
            "high_raw": 105.5, "low_raw": 104.5,
        })
        s = _ts(300)
        e = _ts(100)  # start AFTER end
        with pytest.raises(ContractSchemaError, match="start.*end|start must be"):
            RegimeEngine().detect(
                "X", fv,
                lookback_start_override=s,
                lookback_end_override=e,
            )


class TestReg01CorrelationCausationAux:
    def test_reg01_c68_aux_contains_corr_caus_symbol(self):
        fv = _clean_fv({
            "close_raw": 105.0, "ema_14": 100.0, "rsi_14": 85.0,
            "vwap_20": 100.0, "mom_10_abs": 5.0, "mom_10_pct": 0.05,
            "atr_14": 0.8, "volatility_20_bps": 10.0,
            "vol_ratio_20": 0.5, "vol_std_20_scaled": 2.0,
            "high_raw": 105.5, "low_raw": 104.5,
        })
        mr, aux = RegimeEngine().detect(
            "BTC_USDT", fv,
            correlation_id="CID_ABC_123",
            causation_id="CAU_DEF_456",
        )
        assert aux["correlation_id"] == "CID_ABC_123"
        assert aux["causation_id"] == "CAU_DEF_456"
        assert aux["symbol"] == "BTC_USDT"
        # MarketRegime payload itself does NOT carry these 3 fields (ADN-REG-01 —
        # keeps contract 7-field public API unchanged, no bump required)
        assert not hasattr(mr, "correlation_id")
        assert not hasattr(mr, "causation_id")
        assert not hasattr(mr, "symbol")


class TestReg01RawAxesInAux:
    def test_reg01_c69_raw_axes_3_in_range_minus1_plus1(self):
        fv = _clean_fv({
            "close_raw": 100.0, "ema_14": 100.0, "rsi_14": 50.0,
            "vwap_20": 100.0, "mom_10_abs": 0.0, "mom_10_pct": 0.0,
            "atr_14": 0.5, "volatility_20_bps": 80.0,
            "vol_ratio_20": 1.0, "vol_std_20_scaled": 15.0,
            "high_raw": 100.5, "low_raw": 99.5,
        })
        _, aux = RegimeEngine().detect("X", fv)
        tr = aux["raw_axes"]["trend_axis"]
        mm = aux["raw_axes"]["mom_axis"]
        vo = aux["raw_axes"]["vol_axis"]
        assert -1.0 - 1e-9 <= tr <= 1.0 + 1e-9
        assert -1.0 - 1e-9 <= mm <= 1.0 + 1e-9
        assert -1.0 - 1e-9 <= vo <= 1.0 + 1e-9

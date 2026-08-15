"""S-CON-02A MarketRegime + AD-8 6-enum contract tests.

AC covered: C-13 (6 enum), C-14 (invalid string regime raise),
C-15 (confidence out of [0,1]), C-16 (scores 6-key set exact),
C-17 (score value out of [0,1]), C-18 (lookback_ts start>end).
+ 6 extras: enum value canonical strings, TimeRangeSpec bad instant formats,
post_init normalises str regime to enum, scores sum allowed !=1,
deterministic digest stable 10x, detector/feature_version empty rejected.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.contracts import (
    ContractSchemaError,
    MarketRegime,
    MarketRegimeState,
    REGIME_KEYS,
    TimeRangeSpec,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


SAMPLE_INSTANTS = (
    "2026-01-01T00:00:00.000Z",
    "2026-01-01T01:00:00.000Z",
)


def _full_scores(**overrides: float) -> dict[str, float]:
    base = {k: 0.0 for k in sorted(REGIME_KEYS)}
    base["bull"] = 0.8
    base["sideways"] = 0.1
    base["bear"] = 0.05
    base["high_volatility"] = 0.02
    base["low_volatility"] = 0.02
    base["transition_uncertain"] = 0.01
    for k, v in overrides.items():
        base[k] = v
    return base


def _make_regime(
    regime: MarketRegimeState | str = MarketRegimeState.BULL,
    confidence: float = 0.82,
    scores: dict[str, float] | None = None,
    start: str = SAMPLE_INSTANTS[0],
    end: str = SAMPLE_INSTANTS[1],
    detector_version: str = "regime_kb_v1.0.0",
    feature_version: str = "fv_mvp_v1.0.0",
) -> MarketRegime:
    return MarketRegime(
        timeframe="1h",
        regime=regime,
        confidence=confidence,
        scores=scores or _full_scores(),
        detector_version=detector_version,
        feature_version=feature_version,
        lookback_ts=TimeRangeSpec(start=start, end=end),
    )


# ---------------------------------------------------------------------------
# C-13: MarketRegimeState has exactly 6 named values
# ---------------------------------------------------------------------------


class TestSixRegimeEnumC13:
    def test_six_enum_values_exact_names(self) -> None:
        names = sorted(s.value for s in MarketRegimeState)
        assert names == sorted([
            "bull", "bear", "sideways",
            "high_volatility", "low_volatility", "transition_uncertain",
        ])

    def test_REGIME_KEYS_matches_enum(self) -> None:
        assert REGIME_KEYS == frozenset(s.value for s in MarketRegimeState)

    def test_no_extra_values(self) -> None:
        assert len(MarketRegimeState) == 6


# ---------------------------------------------------------------------------
# C-14: invalid string regime raises
# ---------------------------------------------------------------------------


class TestInvalidRegimeValueC14:
    def test_unknown_string_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            _make_regime(regime="bullx")  # type: ignore[arg-type]

    def test_numeric_value_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            _make_regime(regime=3)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# C-15: confidence range [0,1]
# ---------------------------------------------------------------------------


class TestConfidenceRangeC15:
    @pytest.mark.parametrize("bad", [-0.01, 1.01, 1.5, -0.5])
    def test_confidence_out_of_range_raises(self, bad) -> None:
        with pytest.raises(ContractSchemaError, match="confidence"):
            _make_regime(confidence=bad)

    @pytest.mark.parametrize("ok", [0.0, 0.5, 1.0])
    def test_confidence_endpoints_accepted(self, ok) -> None:
        r = _make_regime(confidence=ok)
        assert r.confidence == ok

    def test_confidence_float_accepted_int_bool_rejected(self) -> None:
        r = _make_regime(confidence=0.82)
        assert r.confidence == pytest.approx(0.82)
        with pytest.raises(ContractSchemaError):
            _make_regime(confidence=1)  # type: ignore[arg-type]
        with pytest.raises(ContractSchemaError):
            _make_regime(confidence=True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# C-16: scores dict must have exactly 6 REGIME_KEYS keys
# ---------------------------------------------------------------------------


class TestScoresKeysExactC16:
    def test_missing_key_raises(self) -> None:
        bad = _full_scores()
        del bad["bear"]
        with pytest.raises(ContractSchemaError, match="missing regime keys"):
            _make_regime(scores=bad)

    def test_extra_key_raises(self) -> None:
        bad = _full_scores()
        bad["custom_extra"] = 0.0
        with pytest.raises(ContractSchemaError, match="unknown extra keys"):
            _make_regime(scores=bad)

    def test_scores_not_sum_to_one_accepted(self) -> None:
        # CONTRACTS.md §3.6: sum is NOT required to be 1.
        odd = {k: 1.0 for k in REGIME_KEYS}  # sum 6.0
        r = _make_regime(scores=odd)
        assert r.scores["bull"] == 1.0


# ---------------------------------------------------------------------------
# C-17: individual score values out of [0,1]
# ---------------------------------------------------------------------------


class TestScoreValuesRangeC17:
    @pytest.mark.parametrize("bad", [-0.001, 1.001, 2.0, -0.1])
    def test_out_of_range_score_raises(self, bad) -> None:
        scores = _full_scores(bull=bad)
        with pytest.raises(ContractSchemaError, match="out of"):
            _make_regime(scores=scores)

    @pytest.mark.parametrize("bad_type", [1, None, True])
    def test_non_float_score_raises(self, bad_type) -> None:
        scores = _full_scores()
        scores["bull"] = bad_type  # type: ignore[assignment]
        with pytest.raises(ContractSchemaError):
            _make_regime(scores=scores)


# ---------------------------------------------------------------------------
# C-18: lookback_ts start <= end + bad Instant format
# ---------------------------------------------------------------------------


class TestLookbackTimeRangeC18:
    def test_start_after_end_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="start must be <= end"):
            _make_regime(start=SAMPLE_INSTANTS[1], end=SAMPLE_INSTANTS[0])

    def test_bad_instant_start_format_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            TimeRangeSpec(start="2026-01-01 00:00:00", end=SAMPLE_INSTANTS[1])

    def test_equal_start_end_accepted(self) -> None:
        same = SAMPLE_INSTANTS[0]
        tr = TimeRangeSpec(start=same, end=same)
        assert tr.start == same == tr.end


# ---------------------------------------------------------------------------
# Extras: detector_version / feature_version shape, post_init str regime cast,
# deterministic sha256 10x stable, timeframe non-empty.
# ---------------------------------------------------------------------------


class TestRegimeExtras:
    def test_empty_detector_version_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            _make_regime(detector_version="")

    def test_empty_feature_version_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            _make_regime(feature_version="")

    def test_str_regime_casts_to_enum(self) -> None:
        r = _make_regime(regime="transition_uncertain")  # type: ignore[arg-type]
        assert r.regime == MarketRegimeState.TRANSITION_UNCERTAIN

    def test_timeframe_empty_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            MarketRegime(
                timeframe="",
                regime=MarketRegimeState.BULL,
                confidence=0.7,
                scores=_full_scores(),
                detector_version="d_v1",
                feature_version="f_v1",
                lookback_ts=TimeRangeSpec(*SAMPLE_INSTANTS),
            )

    def test_sha256_stable_10x(self) -> None:
        r = _make_regime()
        digests = [r.schema_sha256() for _ in range(10)]
        assert len(set(digests)) == 1

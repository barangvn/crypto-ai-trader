"""S-CON-02A FeatureVector + AD-22 contract tests.

Covers story AC:
  C-06 required fields, C-07 nested rejection, C-08 registry missing keys,
  C-09 registry type mismatch, C-10 deterministic digest,
  C-11 null_count invariant (auto-calc + mismatch), C-12 lookback count<1,
  + 2 extra AD-22 positive scenarios + 3 determinism/serde.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.contracts import (
    ContractSchemaError,
    FEATURE_SCHEMA_REGISTRY,
    FeatureSchemaSpec,
    FeatureVector,
    LookbackWindowSpec,
    register_feature_schema,
    validate_feature_vector_features,
)


# ---------------------------------------------------------------------------
# Helpers / Fixture factories
# ---------------------------------------------------------------------------


def _make_lb(count: int = 200, timeframe: str = "1m") -> LookbackWindowSpec:
    return LookbackWindowSpec(count=count, timeframe=timeframe)


def _make_fv(
    features: dict | None = None,
    feature_version: str = "fv_mvp_v1.0.0",
    timeframe: str = "1m",
    lookback: LookbackWindowSpec | None = None,
    input_refs: list[str] | None = None,
    null_count: int | None = None,
) -> FeatureVector:
    features = features if features is not None else {"rsi14": 70.2, "sma20": Decimal("45000.5")}
    lookback = lookback or _make_lb()
    input_refs = input_refs if input_refs is not None else ["01J0XYZ000AAAAAAAAAAAAAAA001"]
    return FeatureVector(
        feature_version=feature_version,
        timeframe=timeframe,
        features=features,
        lookback_window=lookback,
        input_refs=input_refs,
        null_count=null_count,
    )


# ---------------------------------------------------------------------------
# C-06: required fields
# ---------------------------------------------------------------------------


class TestFeatureVectorRequiredFieldsC06:
    """Trigger ContractSchemaError (AD-22 post_init) by passing invalid-typed
    values. NOTE: `_make_fv` replaces None with defaults, so we call the
    FeatureVector constructor directly here for negative tests.
    """

    def test_invalid_feature_version_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            FeatureVector(  # type: ignore[misc]
                feature_version=None,
                timeframe="1m",
                features={"a": 1.0},
                lookback_window=_make_lb(),
                input_refs=[],
            )

    def test_empty_timeframe_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            FeatureVector(
                feature_version="fv_v1",
                timeframe="",
                features={"a": 1.0},
                lookback_window=_make_lb(),
                input_refs=[],
            )

    def test_features_must_be_dict_str_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            FeatureVector(  # type: ignore[misc]
                feature_version="fv_v1",
                timeframe="1m",
                features="not-a-dict",
                lookback_window=_make_lb(),
                input_refs=[],
            )

    def test_features_none_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            FeatureVector(  # type: ignore[misc]
                feature_version="fv_v1",
                timeframe="1m",
                features=None,
                lookback_window=_make_lb(),
                input_refs=[],
            )

    def test_input_refs_none_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            FeatureVector(  # type: ignore[misc]
                feature_version="fv_v1",
                timeframe="1m",
                features={"a": 1.0},
                lookback_window=_make_lb(),
                input_refs=None,
            )


# ---------------------------------------------------------------------------
# C-07: AD-22 flat dict rejection for nested/list/bool values
# ---------------------------------------------------------------------------


class TestFeatureVectorAD22FlatC07:
    def test_nested_dict_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="nested value forbidden"):
            _make_fv(features={"bad": {"x": 1.0}})

    def test_list_value_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="nested value forbidden"):
            _make_fv(features={"bad": [1.0, 2.0]})

    def test_bool_value_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="boolean primitive forbidden"):
            _make_fv(features={"bad": True})

    def test_invalid_key_format_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="key invalid format"):
            _make_fv(features={"BadKey-UPPER": 1.0})


# ---------------------------------------------------------------------------
# C-12: LookbackWindowSpec bounds
# ---------------------------------------------------------------------------


class TestLookbackWindowSpecC12:
    @pytest.mark.parametrize("bad", [0, -1, 1.5])
    def test_count_invalid_raises(self, bad) -> None:
        with pytest.raises(ContractSchemaError):
            LookbackWindowSpec(count=bad, timeframe="1m")  # type: ignore[arg-type]

    def test_empty_timeframe_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            LookbackWindowSpec(count=1, timeframe="")


# ---------------------------------------------------------------------------
# C-11: null_count invariant
# ---------------------------------------------------------------------------


class TestNullCountInvariantC11:
    def test_null_count_auto_calculated(self) -> None:
        fv = _make_fv(features={"a": 1.0, "b": None, "c": None, "d": Decimal("1.0")})
        assert fv.null_count == 2

    def test_null_count_mismatch_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="null_count mismatch"):
            _make_fv(features={"a": None, "b": 1.0}, null_count=7)


# ---------------------------------------------------------------------------
# C-08 / C-09: FeatureSchemaSpec registry — missing/extra keys + type mismatch
# ---------------------------------------------------------------------------


TEST_FV = "fv_s02atest_v1"  # unique to avoid bleed across test modules


class TestFeatureSchemaRegistryC08C09:
    def test_register_and_validate_missing_keys_reports(self) -> None:
        spec = FeatureSchemaSpec(
            feature_version=TEST_FV,
            required_keys=frozenset({"rsi14", "sma20", "vol20"}),
            allowed_keys=frozenset({"rsi14", "sma20", "vol20", "bband"}),
            key_types={
                "rsi14": float,
                "sma20": Decimal,
                "vol20": Decimal,
                "bband": float,
            },
            nullable_keys=frozenset({"bband"}),
        )
        register_feature_schema(spec)
        assert TEST_FV in FEATURE_SCHEMA_REGISTRY
        fv = _make_fv(
            feature_version=TEST_FV,
            features={"rsi14": 70.2, "sma20": Decimal("45000.5")},  # missing vol20
        )
        reasons = validate_feature_vector_features(fv)
        assert any("missing required keys" in r for r in reasons), reasons

    def test_register_and_validate_extra_key_reports(self) -> None:
        # feature_version already registered (idempotent) — reuse TEST_FV
        fv = _make_fv(
            feature_version=TEST_FV,
            features={
                "rsi14": 70.2,
                "sma20": Decimal("45000.5"),
                "vol20": Decimal("123"),
                "extra_weird": 0.5,
            },
        )
        reasons = validate_feature_vector_features(fv)
        assert any("extra forbidden keys" in r for r in reasons), reasons

    def test_type_mismatch_float_expected_got_decimal_reports(self) -> None:
        fv = _make_fv(
            feature_version=TEST_FV,
            features={
                "rsi14": Decimal("70.2"),  # should be float
                "sma20": Decimal("45000.5"),
                "vol20": Decimal("123"),
            },
        )
        reasons = validate_feature_vector_features(fv)
        assert any("type mismatch" in r for r in reasons), reasons

    def test_null_not_allowed_reports(self) -> None:
        fv = _make_fv(
            feature_version=TEST_FV,
            features={
                "rsi14": None,  # NOT in nullable_keys (only bband is)
                "sma20": Decimal("45000.5"),
                "vol20": Decimal("123"),
            },
        )
        reasons = validate_feature_vector_features(fv)
        assert any("NULL not allowed" in r for r in reasons), reasons


# ---------------------------------------------------------------------------
# C-10 / Determinism: to_sorted_dict + schema_sha256 stable 10x
# ---------------------------------------------------------------------------


class TestDeterminismC10:
    def test_to_sorted_dict_returns_sorted_keys(self) -> None:
        fv = _make_fv(features={"z": 1.0, "a": 2.0, "m": Decimal("3")})
        d = fv.to_sorted_dict()
        keys = list(d.keys())
        assert keys == sorted(keys), f"not sorted: {keys}"
        features_inner = d["features"]
        assert list(features_inner.keys()) == sorted(features_inner.keys())

    def test_schema_sha256_stable_10_times(self) -> None:
        fv = _make_fv()
        digests = [fv.schema_sha256() for _ in range(10)]
        assert all(d == digests[0] for d in digests), digests


# ---------------------------------------------------------------------------
# AD-22 positive scenarios (extra coverage)
# ---------------------------------------------------------------------------


class TestFeatureVectorPositive:
    def test_minimal_valid_instance(self) -> None:
        fv = _make_fv(
            features={"rsi": 55.5},
            input_refs=[],
        )
        assert fv.null_count == 0
        assert fv.feature_version == "fv_mvp_v1.0.0"

    def test_input_refs_must_be_strings(self) -> None:
        with pytest.raises(ContractSchemaError):
            _make_fv(input_refs=["ok", 12345])  # type: ignore[list-item]

    def test_feature_version_bad_chars_rejected(self) -> None:
        with pytest.raises(ContractSchemaError):
            _make_fv(feature_version="NOT_LOWERCASE_v1")

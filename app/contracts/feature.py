from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.contracts.exceptions import (
    ContractSchemaError,
    schema_sha256,
    to_sorted_dict,
)


_FEATURE_VERSION_RE = re.compile(r"^[a-z0-9_.]+$")
_FEATURE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_ALLOWED_PRIMITIVE = (Decimal, float, int, str)  # None allowed via separate check


@dataclass
class LookbackWindowSpec:
    """Describes what feature calculation window looked over (AD-22 provenance).

    NOTE: count >= 1 required. timeframe is a string (not enum) so new timeframes
    can be introduced without a contract_version bump, consistent with CONTRACTS.md.
    """

    count: int
    timeframe: str

    def __post_init__(self) -> None:
        if isinstance(self.count, bool) or not isinstance(self.count, int):
            raise ContractSchemaError(
                f"LookbackWindowSpec.count must be int >= 1, got {type(self.count).__name__}"
            )
        if self.count < 1:
            raise ContractSchemaError(
                f"LookbackWindowSpec.count must be >= 1, got {self.count!r}"
            )
        if not isinstance(self.timeframe, str) or not self.timeframe:
            raise ContractSchemaError(
                f"LookbackWindowSpec.timeframe must be non-empty str, got {self.timeframe!r}"
            )

    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)


@dataclass(frozen=True)
class FeatureSchemaSpec:
    """AD-22: typed/versioned schema for a specific feature_version.

    Register via register_feature_schema() so validate_feature_vector_features()
    can apply strong validation (missing/extra keys, type, null, min/max bounds).
    """

    feature_version: str
    required_keys: frozenset[str]
    allowed_keys: frozenset[str]
    key_types: dict[str, type]
    nullable_keys: frozenset[str]
    min_value_per_key: dict[str, Decimal | float | int] = field(default_factory=dict)
    max_value_per_key: dict[str, Decimal | float | int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.feature_version, str) or not _FEATURE_VERSION_RE.match(
            self.feature_version
        ):
            raise ContractSchemaError(
                f"FeatureSchemaSpec.feature_version invalid: {self.feature_version!r}"
            )

        for key in self.required_keys:
            if key not in self.allowed_keys:
                raise ContractSchemaError(
                    f"FeatureSchemaSpec required key {key!r} not in allowed_keys"
                )
            if key not in self.key_types:
                raise ContractSchemaError(
                    f"FeatureSchemaSpec required key {key!r} missing from key_types"
                )
        for key, tp in self.key_types.items():
            if key not in self.allowed_keys:
                raise ContractSchemaError(
                    f"FeatureSchemaSpec key_types entry {key!r} not in allowed_keys"
                )
            if tp not in (Decimal, float, int, str):
                raise ContractSchemaError(
                    f"FeatureSchemaSpec key_types[{key!r}] invalid type: {tp!r}"
                )


FEATURE_SCHEMA_REGISTRY: dict[str, FeatureSchemaSpec] = {}


def register_feature_schema(spec: FeatureSchemaSpec) -> None:
    """Idempotently register a FeatureSchemaSpec (append-only registry).

    Re-registration of the same feature_version is silently a no-op so plugins
    can safely call this at import-time or at construction.
    """
    if not isinstance(spec, FeatureSchemaSpec):
        raise ContractSchemaError(
            f"register_feature_schema expects FeatureSchemaSpec, got {type(spec).__name__}"
        )
    if spec.feature_version in FEATURE_SCHEMA_REGISTRY:
        return
    FEATURE_SCHEMA_REGISTRY[spec.feature_version] = spec


def validate_feature_vector_features(fv: "FeatureVector") -> list[str]:
    """Return a list of AD-22 schema violation reasons. Empty list = OK.

    If fv.feature_version has no registered FeatureSchemaSpec the registry
    does not enforce anything (future-compatible: unknown versions skipped).
    """
    reasons: list[str] = []
    if not isinstance(fv, FeatureVector):
        return [f"validate_feature_vector_features: not a FeatureVector: {type(fv).__name__}"]
    spec = FEATURE_SCHEMA_REGISTRY.get(fv.feature_version)
    if spec is None:
        return reasons

    keys = set(fv.features.keys())
    missing = sorted(spec.required_keys - keys)
    extra = sorted(keys - spec.allowed_keys)
    if missing:
        reasons.append(f"AD-22 missing required keys: {missing}")
    if extra:
        reasons.append(f"AD-22 extra forbidden keys: {extra}")
    for k in sorted(keys):
        v = fv.features[k]
        if k not in spec.key_types:
            continue  # allowed but typed? no type info — skip
        expected_type = spec.key_types[k]
        if v is None:
            if k not in spec.nullable_keys:
                reasons.append(f"AD-22 key={k!r} NULL not allowed")
            continue
        # bool is a subclass of int in Python — reject bools explicitly unless int typed,
        # but even for int typed we disallow bools (FeatureVector values may never be bool).
        if isinstance(v, bool):
            reasons.append(f"AD-22 key={k!r} boolean forbidden (expected {expected_type.__name__})")
            continue
        if not isinstance(v, expected_type):
            reasons.append(
                f"AD-22 key={k!r} type mismatch: expected {expected_type.__name__}, got {type(v).__name__}"
            )
            continue
        mn = spec.min_value_per_key.get(k)
        mx = spec.max_value_per_key.get(k)
        try:
            if mn is not None and v < mn:  # type: ignore[operator]
                reasons.append(f"AD-22 key={k!r} value={v!r} < min={mn!r}")
        except TypeError:
            reasons.append(f"AD-22 key={k!r} cannot compare value to min={mn!r}")
        try:
            if mx is not None and v > mx:  # type: ignore[operator]
                reasons.append(f"AD-22 key={k!r} value={v!r} > max={mx!r}")
        except TypeError:
            reasons.append(f"AD-22 key={k!r} cannot compare value to max={mx!r}")
    return reasons


def _validate_features_flat(features: Any) -> None:
    """AD-22: validate flat dict — no nested dict/list, key regex, value type allowed.

    Used by FeatureVector.__post_init__ independently of the registry so even
    unregistered feature_versions still respect the AD-22 flat boundary.
    """
    if not isinstance(features, dict):
        raise ContractSchemaError(
            f"FeatureVector.features must be dict, got {type(features).__name__}"
        )
    for key, value in features.items():
        if not isinstance(key, str):
            raise ContractSchemaError(
                f"FeatureVector.features key must be str, got {type(key).__name__}: {key!r}"
            )
        if not _FEATURE_KEY_RE.match(key):
            raise ContractSchemaError(
                f"FeatureVector.features key invalid format: {key!r} (must match ^[a-z][a-z0-9_]*$)"
            )
        if value is None:
            continue
        if isinstance(value, bool):
            raise ContractSchemaError(
                f"FeatureVector.features[{key!r}] boolean primitive forbidden"
            )
        if isinstance(value, (dict, list, tuple, set, frozenset, bytes, bytearray)):
            raise ContractSchemaError(
                f"FeatureVector.features[{key!r}] nested value forbidden (AD-22 flat dict): {type(value).__name__}"
            )
        if not isinstance(value, _ALLOWED_PRIMITIVE):
            raise ContractSchemaError(
                f"FeatureVector.features[{key!r}] type {type(value).__name__} forbidden; allowed: Decimal/float/int/str/None"
            )


def _validate_ulidish_list(values: Any, field_name: str) -> None:
    """Basic provenance shape: input_refs must be a list of str (ULID-like)."""
    if not isinstance(values, list):
        raise ContractSchemaError(
            f"FeatureVector.{field_name} must be list[str] (ULIDs), got {type(values).__name__}"
        )
    for idx, v in enumerate(values):
        if not isinstance(v, str):
            raise ContractSchemaError(
                f"FeatureVector.{field_name}[{idx}] must be str (ULID), got {type(v).__name__}"
            )


@dataclass
class FeatureVector:
    """AD-22 FeatureVector contract: flat, typed, versioned, deterministic, provenance-aware.

    See S-CON-02A story §3.1 for field-level detail and CONTRACTS.md §3.7 for
    canonical reference.
    """

    feature_version: str
    timeframe: str
    features: dict[str, Decimal | float | int | str | None]
    lookback_window: LookbackWindowSpec
    input_refs: list[str]  # ULIDs — provenance of inputs used to compute features
    null_count: int | None = None

    def __post_init__(self) -> None:
        # feature_version
        if not isinstance(self.feature_version, str) or not _FEATURE_VERSION_RE.match(
            self.feature_version
        ):
            raise ContractSchemaError(
                f"FeatureVector.feature_version invalid: {self.feature_version!r}"
            )
        # timeframe
        if not isinstance(self.timeframe, str) or not self.timeframe:
            raise ContractSchemaError(
                f"FeatureVector.timeframe must be non-empty str, got {self.timeframe!r}"
            )
        # flat features validation (AD-22 hard boundary — always run, independent of registry)
        _validate_features_flat(self.features)
        # lookback_window must be LookbackWindowSpec (dataclass check)
        if not isinstance(self.lookback_window, LookbackWindowSpec):
            raise ContractSchemaError(
                f"FeatureVector.lookback_window must be LookbackWindowSpec, got {type(self.lookback_window).__name__}"
            )
        # input_refs shape
        _validate_ulidish_list(self.input_refs, "input_refs")
        # null_count validation: if provided must equal actual null count; else compute
        actual_nulls = sum(1 for v in self.features.values() if v is None)
        if self.null_count is None:
            self.null_count = actual_nulls
        else:
            if isinstance(self.null_count, bool) or not isinstance(self.null_count, int):
                raise ContractSchemaError(
                    f"FeatureVector.null_count must be int|None, got {type(self.null_count).__name__}"
                )
            if self.null_count < 0:
                raise ContractSchemaError(
                    f"FeatureVector.null_count must be >= 0, got {self.null_count!r}"
                )
            if self.null_count != actual_nulls:
                raise ContractSchemaError(
                    f"FeatureVector.null_count mismatch: declared={self.null_count!r}, actual={actual_nulls}"
                )

    # ---- serialisation / determinism helpers ---------------------------------
    def to_sorted_dict(self) -> dict[str, Any]:
        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        return schema_sha256(self)

    # ---- AD-22 registry validation (short-cut) ---------------------------------
    def validate_against_registry(self) -> list[str]:
        """Convenience wrapper; see validate_feature_vector_features."""
        return validate_feature_vector_features(self)

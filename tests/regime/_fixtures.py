from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
str(ROOT) not in sys.path and sys.path.insert(0, str(ROOT))

import datetime  # noqa: E402
from decimal import Decimal  # noqa: E402

import pytest  # noqa: F401, E402

from app.contracts.exceptions import ContractSchemaError  # noqa: E402
from app.contracts.feature import FeatureVector, LookbackWindowSpec  # noqa: E402
from app.contracts.regime import (  # noqa: E402
    MarketRegime,
    MarketRegimeState,
    REGIME_KEYS,
    TimeRangeSpec,
)
from app.contracts.types import Instant  # noqa: E402
from app.regime import (  # noqa: E402
    DEFAULT_OPTIONS,
    DetectOptions,
    QualityHint,
    RegimeEngine,
    SREG01_EXPECTED_FEATURE_VERSION,
    SREG01_NULLABLE_FEATURE_COUNT,
)


def _ts(secs: int) -> Instant:
    epoch_ms = secs * 1000 + 1725000000000
    dt = datetime.datetime.fromtimestamp(epoch_ms / 1000.0, tz=datetime.timezone.utc)
    s = dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{epoch_ms % 1000:03d}Z"
    return Instant(s)


_DEFAULT_FEATURE_KEYS_12: list[str] = [
    "ema_14",
    "rsi_14",
    "atr_14",
    "vwap_20",
    "mom_10_abs",
    "mom_10_pct",
    "volatility_20_bps",
    "vol_ratio_20",
    "vol_std_20_scaled",
    "close_raw",
    "high_raw",
    "low_raw",
]


def _make_fv(
    features: dict[str, float | Decimal | int | None],
    *,
    timeframe: str = "1h",
    feature_version: str = SREG01_EXPECTED_FEATURE_VERSION,
    lookback_count: int = 200,
    input_ref_count: int = 3,
) -> FeatureVector:
    """Build a valid FeatureVector suitable for regime detection.

    Features dict may be partial; any keys missing from the 12 SFEA01 required
    keys are added as None (actual_null_count computed by FV.__post_init__).
    """
    fv_features: dict[str, Decimal | float | int | str | None] = {}
    for k in _DEFAULT_FEATURE_KEYS_12:
        if k in features:
            v = features[k]
            if v is None or isinstance(v, (Decimal, float, int, str)):
                fv_features[k] = v
            else:
                fv_features[k] = float(v)
        else:
            fv_features[k] = None

    refs: list[str] = [_ts(i * 3600) for i in range(input_ref_count)]

    return FeatureVector(
        feature_version=feature_version,
        timeframe=timeframe,
        features=fv_features,
        lookback_window=LookbackWindowSpec(count=lookback_count, timeframe=timeframe),
        input_refs=refs,
        null_count=None,
    )


def _clean_fv(fv_features: dict[str, float]) -> FeatureVector:
    """Make FV where all 12 features are provided (no nulls)."""
    return _make_fv(fv_features, input_ref_count=200)


__all__ = [
    "ContractSchemaError",
    "DEFAULT_OPTIONS",
    "DetectOptions",
    "FeatureVector",
    "LookbackWindowSpec",
    "Instant",
    "MarketRegime",
    "MarketRegimeState",
    "QualityHint",
    "REGIME_KEYS",
    "RegimeEngine",
    "ROOT",
    "SREG01_NULLABLE_FEATURE_COUNT",
    "TimeRangeSpec",
    "_clean_fv",
    "_make_fv",
    "_ts",
    "datetime",
    "pytest",
    "Decimal",
]

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.contracts.exceptions import ContractSchemaError
from app.contracts.feature import (
    FEATURE_SCHEMA_REGISTRY,
    FeatureSchemaSpec,
    FeatureVector,
    LookbackWindowSpec,
    register_feature_schema,
)
from app.contracts.market import Candle

SFEA01_FEATURE_VERSION = "fea_01_v1"
_DEFAULT_TIMEFRAME = "1h"
_DEFAULT_LOOKBACK = 200
_INDICATOR_MAX_WINDOW = 20
_STRICT_CLOSED_ONLY_DEFAULT = True

_SFEA01_REQUIRED_KEYS: frozenset[str] = frozenset(
    [
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
)
_SFEA01_ALLOWED_KEYS: frozenset[str] = _SFEA01_REQUIRED_KEYS
_SFEA01_KEY_TYPES: dict[str, type] = {k: float for k in _SFEA01_REQUIRED_KEYS}
_SFEA01_NULLABLE_KEYS: frozenset[str] = frozenset(
    [
        "ema_14",
        "rsi_14",
        "atr_14",
        "vwap_20",
        "mom_10_abs",
        "mom_10_pct",
        "volatility_20_bps",
        "vol_ratio_20",
        "vol_std_20_scaled",
    ]
)
_SFEA01_MIN_VALUES: dict[str, Decimal | float | int] = {
    "rsi_14": 0.0,
    "atr_14": 0.0,
    "volatility_20_bps": 0.0,
    "vol_ratio_20": 0.0,
    "vol_std_20_scaled": 0.0,
    "close_raw": 1e-9,
    "high_raw": 1e-9,
    "low_raw": 1e-9,
}
_SFEA01_MAX_VALUES: dict[str, Decimal | float | int] = {
    "rsi_14": 100.0,
}

SFEA01_SCHEMA_SPEC = FeatureSchemaSpec(
    feature_version=SFEA01_FEATURE_VERSION,
    required_keys=_SFEA01_REQUIRED_KEYS,
    allowed_keys=_SFEA01_ALLOWED_KEYS,
    key_types=_SFEA01_KEY_TYPES,
    nullable_keys=_SFEA01_NULLABLE_KEYS,
    min_value_per_key=_SFEA01_MIN_VALUES,
    max_value_per_key=_SFEA01_MAX_VALUES,
)
register_feature_schema(SFEA01_SCHEMA_SPEC)


def _is_close(v: float, w: float, rel: float = 1e-9) -> bool:
    return math.isclose(v, w, rel_tol=rel)


@dataclass
class FeatureEngine:
    feature_version: str = SFEA01_FEATURE_VERSION
    default_timeframe: str = _DEFAULT_TIMEFRAME
    default_lookback: int = _DEFAULT_LOOKBACK
    strict_closed_only: bool = _STRICT_CLOSED_ONLY_DEFAULT

    # ----- Public API (side-effect free, deterministic) ---------------------
    def calculate(
        self,
        symbol: str,
        candles: list[Candle],
        timeframe: str | None = None,
        lookback: int | None = None,
    ) -> FeatureVector:
        self._validate_inputs(candles)
        tf = timeframe or self.default_timeframe
        n = len(candles)
        if lookback is not None and lookback >= 1:
            actual_lookback = lookback
        else:
            actual_lookback = max(_INDICATOR_MAX_WINDOW, self.default_lookback)
        effective_lookback = min(actual_lookback, n)
        start = n - effective_lookback
        if start < 0:
            start = 0
        used_candles = candles[start:n]
        closes = [self._d_to_f(c.close) for c in used_candles]
        highs = [self._d_to_f(c.high) for c in used_candles]
        lows = [self._d_to_f(c.low) for c in used_candles]
        volumes = [self._d_to_f(c.volume) for c in used_candles]
        L = len(used_candles)
        last = L - 1
        ema = self._compute_ema(closes, 14)
        rsi = self._compute_rsi(closes, 14)
        atr = self._compute_atr(highs, lows, closes, 14)
        vwap = self._compute_vwap(highs, lows, closes, volumes, 20)
        mom_abs, mom_pct = self._compute_momentum(closes, 10)
        vol_bps = self._compute_volatility(closes, 20)
        vol_ratio, vol_std_scaled = self._compute_volume_features(volumes, 20)
        features: dict[str, Any] = {
            "ema_14": ema[last],
            "rsi_14": rsi[last],
            "atr_14": atr[last],
            "vwap_20": vwap[last],
            "mom_10_abs": mom_abs[last],
            "mom_10_pct": mom_pct[last],
            "volatility_20_bps": vol_bps[last],
            "vol_ratio_20": vol_ratio[last],
            "vol_std_20_scaled": vol_std_scaled[last],
            "close_raw": closes[last],
            "high_raw": highs[last],
            "low_raw": lows[last],
        }
        for k, v in list(features.items()):
            if v is not None and isinstance(v, float):
                if math.isnan(v) or math.isinf(v):
                    features[k] = None
        input_refs: list[str] = [
            getattr(c, "candle_id", None) or getattr(c, "open_time", None) or ""
            for c in used_candles
        ]
        if not all(isinstance(r, str) and len(r) >= 1 for r in input_refs):
            input_refs = [f"CANDLE_{i:06d}" for i in range(L)]
        lookback_spec = LookbackWindowSpec(count=effective_lookback, timeframe=tf)
        return FeatureVector(
            feature_version=self.feature_version,
            timeframe=tf,
            features=features,
            lookback_window=lookback_spec,
            input_refs=input_refs,
        )

    # ----- Input validation (raises ContractSchemaError) --------------------
    def _validate_inputs(self, candles: list[Candle]) -> None:
        if not candles:
            raise ContractSchemaError("FeatureEngine: candles empty")
        if not isinstance(candles, list):
            raise ContractSchemaError("FeatureEngine: candles must be list")
        prev = None
        seen_open_ts: set[Any] = set()
        for idx, c in enumerate(candles):
            if not isinstance(c, Candle):
                raise ContractSchemaError(
                    f"FeatureEngine: candles[{idx}] not Candle instance"
                )
            if self.strict_closed_only and not c.closed:
                raise ContractSchemaError(
                    "FeatureEngine: closed=False candles not allowed in strict mode"
                )
            op = c.open_time
            if prev is not None and not (op > prev):
                if op == prev:
                    raise ContractSchemaError(
                        "FeatureEngine: duplicate open_ts in candles"
                    )
                raise ContractSchemaError(
                    "FeatureEngine: candles not sorted ascending by open_time"
                )
            if op in seen_open_ts:
                raise ContractSchemaError(
                    "FeatureEngine: duplicate open_ts (second pass)"
                )
            seen_open_ts.add(op)
            prev = op
            o_high = self._d_to_f(c.high)
            o_low = self._d_to_f(c.low)
            o_open = self._d_to_f(c.open)
            o_close = self._d_to_f(c.close)
            o_vol = self._d_to_f(c.volume)
            if o_high < o_low:
                raise ContractSchemaError(
                    f"FeatureEngine: invalid OHLC high<low at idx={idx}"
                )
            if o_open <= 0.0 or o_close <= 0.0 or o_high <= 0.0 or o_low <= 0.0:
                raise ContractSchemaError(
                    f"FeatureEngine: non-positive price at idx={idx}"
                )
            if o_vol < 0.0:
                raise ContractSchemaError(
                    f"FeatureEngine: negative volume at idx={idx}"
                )

    # ----- Decimal to float coercion (Candle prices are Decimal) -------------
    @staticmethod
    def _d_to_f(value: Decimal | float | int) -> float:
        if isinstance(value, bool):
            raise ContractSchemaError("FeatureEngine: bool price forbidden")
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        raise ContractSchemaError(
            f"FeatureEngine: invalid numeric type {type(value).__name__}"
        )

    # ----- Per-indicator static helpers (return len(input) arrays) ----------
    @staticmethod
    def _compute_ema(close: list[float], period: int) -> list[float | None]:
        n = len(close)
        out: list[float | None] = [None] * n
        if period < 1:
            return out
        if n < period:
            return out
        alpha = 2.0 / (period + 1.0)
        sma_seed = statistics.mean(close[0:period])
        out[period - 1] = sma_seed
        for t in range(period, n):
            prev = out[t - 1]
            assert isinstance(prev, float)
            out[t] = alpha * close[t] + (1.0 - alpha) * prev
        return out

    @staticmethod
    def _compute_rsi(close: list[float], period: int) -> list[float | None]:
        n = len(close)
        out: list[float | None] = [None] * n
        if period < 1:
            return out
        if n <= period:
            return out
        gains: list[float] = [0.0] * n
        losses: list[float] = [0.0] * n
        for t in range(1, n):
            d = close[t] - close[t - 1]
            gains[t] = max(d, 0.0)
            losses[t] = max(-d, 0.0)
        avg_gain: list[float] = [0.0] * n
        avg_loss: list[float] = [0.0] * n
        avg_gain[period] = statistics.mean(gains[1 : period + 1])
        avg_loss[period] = statistics.mean(losses[1 : period + 1])
        for t in range(period + 1, n):
            avg_gain[t] = (avg_gain[t - 1] * (period - 1) + gains[t]) / period
            avg_loss[t] = (avg_loss[t - 1] * (period - 1) + losses[t]) / period
        for t in range(period, n):
            if t == period:
                ag = avg_gain[period]
                al = avg_loss[period]
            else:
                ag = avg_gain[t]
                al = avg_loss[t]
            if _is_close(al, 0.0):
                out[t] = 100.0
            else:
                rs = ag / al
                out[t] = 100.0 - (100.0 / (1.0 + rs))
        return out

    @staticmethod
    def _compute_atr(
        high: list[float], low: list[float], close: list[float], period: int
    ) -> list[float | None]:
        n = len(close)
        out: list[float | None] = [None] * n
        if period < 1:
            return out
        if n <= period:
            return out
        tr: list[float] = [0.0] * n
        for t in range(1, n):
            tr1 = high[t] - low[t]
            tr2 = abs(high[t] - close[t - 1])
            tr3 = abs(low[t] - close[t - 1])
            tr[t] = max(tr1, tr2, tr3)
        seed = statistics.mean(tr[1 : period + 1])
        out[period] = seed
        for t in range(period + 1, n):
            prev = out[t - 1]
            assert isinstance(prev, float)
            out[t] = (prev * (period - 1) + tr[t]) / period
        return out

    @staticmethod
    def _compute_vwap(
        high: list[float],
        low: list[float],
        close: list[float],
        volume: list[float],
        window: int,
    ) -> list[float | None]:
        n = len(close)
        out: list[float | None] = [None] * n
        if window < 1:
            return out
        if n < window:
            return out
        for t in range(window - 1, n):
            start = t - window + 1
            denom = 0.0
            numer = 0.0
            for i in range(start, t + 1):
                tp = (high[i] + low[i] + close[i]) / 3.0
                denom += volume[i]
                numer += tp * volume[i]
            if _is_close(denom, 0.0):
                out[t] = None
            else:
                out[t] = numer / denom
        return out

    @staticmethod
    def _compute_momentum(
        close: list[float], period: int
    ) -> tuple[list[float | None], list[float | None]]:
        n = len(close)
        out_abs: list[float | None] = [None] * n
        out_pct: list[float | None] = [None] * n
        if period < 1:
            return out_abs, out_pct
        if n <= period:
            return out_abs, out_pct
        for t in range(period, n):
            ref = close[t - period]
            cur = close[t]
            out_abs[t] = cur - ref
            if _is_close(ref, 0.0):
                out_pct[t] = None
            else:
                out_pct[t] = (cur / ref - 1.0) * 100.0
        return out_abs, out_pct

    @staticmethod
    def _compute_volatility(
        close: list[float], window: int
    ) -> list[float | None]:
        n = len(close)
        out: list[float | None] = [None] * n
        if window < 2:
            return out
        if n <= window:
            return out
        rets: list[float] = [0.0] * n
        for t in range(1, n):
            prev = close[t - 1]
            if _is_close(prev, 0.0):
                rets[t] = 0.0
            else:
                rets[t] = (close[t] / prev) - 1.0
        for t in range(window, n):
            start = t - window + 1
            window_rets = rets[start : t + 1]
            if len(window_rets) < 2:
                out[t] = None
                continue
            stdev = statistics.stdev(window_rets)
            out[t] = stdev * 10000.0
        return out

    @staticmethod
    def _compute_volume_features(
        volume: list[float], window: int
    ) -> tuple[list[float | None], list[float | None]]:
        n = len(volume)
        out_ratio: list[float | None] = [None] * n
        out_std: list[float | None] = [None] * n
        if window < 1:
            return out_ratio, out_std
        if n < window:
            return out_ratio, out_std
        for t in range(window - 1, n):
            start = t - window + 1
            w = volume[start : t + 1]
            mean_v = statistics.fmean(w)
            if _is_close(mean_v, 0.0):
                out_ratio[t] = 0.0
            else:
                out_ratio[t] = volume[t] / mean_v
            if len(w) < 2:
                out_std[t] = 0.0
            else:
                std_v = statistics.stdev(w)
                out_std[t] = std_v / 1_000_000.0
        return out_ratio, out_std

    def to_sorted_dict(self) -> dict[str, Any]:
        from app.contracts.exceptions import to_sorted_dict

        return to_sorted_dict(self)

    def schema_sha256(self) -> str:
        from app.contracts.exceptions import schema_sha256

        return schema_sha256(self)

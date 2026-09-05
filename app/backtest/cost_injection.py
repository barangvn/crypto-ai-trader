"""S-BKT-02: Cost Model Injection Layer (Wrapper Only).

Yeni fill/cost ALGORİTMASI YOK. FillAssumptionsConfig'in alan-level
override'ını üretir ve merge eder. S-PTR-01 doğrudan REUSE edilir.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from decimal import Decimal
from typing import Any

from ..simulation.fill_config import FillAssumptionsConfig


def _fill_config_sorted_dict(cfg: FillAssumptionsConfig) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    for f in fields(cfg):
        v = getattr(cfg, f.name)
        if isinstance(v, Decimal):
            raw[f.name] = format(v, "f")
        else:
            raw[f.name] = v
    return dict(sorted(raw.items()))


@dataclass(frozen=True)
class CostModelOverrides:
    """Field-level overrides for FillAssumptionsConfig.

    Alani None olan korunur (default). Deterministik serialization için
    frozen + to_sorted_dict kullanilir.
    """

    taker_fee_bps: Decimal | None = None
    maker_fee_bps: Decimal | None = None
    default_spread_bps: Decimal | None = None
    base_slippage_bps: Decimal | None = None
    base_latency_ms: Decimal | None = None
    latency_jitter_ms: Decimal | None = None
    fill_ratio: Decimal | None = None
    partial_count_limit: int | None = None

    def to_sorted_dict(self) -> dict[str, Any]:
        raw: dict[str, Any] = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if v is None:
                raw[f.name] = None
            elif isinstance(v, Decimal):
                raw[f.name] = format(v, "f")
            else:
                raw[f.name] = v
        return dict(sorted(raw.items()))


_OVERRIDE_FIELDS: tuple[str, ...] = tuple(f.name for f in fields(CostModelOverrides))


def _coerce_decimal(value: Any, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise TypeError(f"BK_COST_INVALID_TYPE: {field_name} Decimal/int/float/str(numeric) olmalı: bool")
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except Exception:
            raise TypeError(f"BK_COST_INVALID_TYPE: {field_name} Decimal/int/float/str(numeric) olmalı: str")
    raise TypeError(f"BK_COST_INVALID_TYPE: {field_name} Decimal/int/float/str(numeric) olmalı: {type(value).__name__}")


def _validate_and_coerce(field_name: str, value: Any) -> Any:
    if value is None:
        return None
    if field_name in {"taker_fee_bps", "maker_fee_bps"}:
        d = _coerce_decimal(value, field_name)
        if d < 0:
            raise ValueError(f"BK_COST_INVALID: {field_name} negatif: {value}")
        return d
    if field_name == "default_spread_bps":
        d = _coerce_decimal(value, field_name)
        if d < 0:
            raise ValueError(f"BK_COST_INVALID: default_spread_bps negatif: {value}")
        return d
    if field_name in {"base_slippage_bps", "base_latency_ms", "latency_jitter_ms"}:
        d = _coerce_decimal(value, field_name)
        if d < 0:
            raise ValueError(f"BK_COST_INVALID: {field_name} negatif: {value}")
        return d
    if field_name == "fill_ratio":
        d = _coerce_decimal(value, field_name)
        if d <= 0 or d > 1:
            raise ValueError(f"BK_COST_INVALID: fill_ratio [0,1] olmalı: {value}")
        return d
    if field_name == "partial_count_limit":
        if isinstance(value, bool):
            raise TypeError(f"BK_COST_INVALID_TYPE: partial_count_limit int olmalı: bool")
        if isinstance(value, int):
            if value < 1:
                raise ValueError(f"BK_COST_INVALID: partial_count_limit >=1 olmalı: {value}")
            return value
        raise TypeError(f"BK_COST_INVALID_TYPE: partial_count_limit int olmalı: {type(value).__name__}")
    raise TypeError(f"BK_COST_INVALID_TYPE: bilinmeyen alan: {field_name}")


def validate_cost_overrides(overrides: CostModelOverrides | None) -> None:
    if overrides is None:
        return
    if not isinstance(overrides, CostModelOverrides):
        raise TypeError(f"BK_COST_INVALID_TYPE: CostModelOverrides gerekli, alındı: {type(overrides).__name__}")
    for fn in _OVERRIDE_FIELDS:
        v = getattr(overrides, fn)
        _validate_and_coerce(fn, v)


def apply_cost_overrides(
    base: FillAssumptionsConfig, overrides: CostModelOverrides | None
) -> FillAssumptionsConfig:
    """base + overrides => yeni FillAssumptionsConfig. None alanlar korunur.

    Deterministik: Ayni (base, overrides) her zaman ayni cikti.
    Coerce: str(numeric) -> Decimal, bool reject, range validate.
    """
    if overrides is None:
        return base
    if not isinstance(overrides, CostModelOverrides):
        raise TypeError(f"BK_COST_INVALID_TYPE: CostModelOverrides gerekli, alındı: {type(overrides).__name__}")
    update_kwargs: dict[str, Any] = {}
    for fn in _OVERRIDE_FIELDS:
        v = getattr(overrides, fn)
        coerced = _validate_and_coerce(fn, v)
        if coerced is not None:
            update_kwargs[fn] = coerced
    if not update_kwargs:
        return base
    return replace(base, **update_kwargs)


def cost_overrides_manifest(
    base: FillAssumptionsConfig,
    overrides_global: CostModelOverrides | None,
    overrides_fold: CostModelOverrides | None = None,
) -> dict[str, Any]:
    """Deterministik cost override manifest (artifact metadata için).

    Precedence: overrides_fold > overrides_global > base.
    """
    eff = apply_cost_overrides(apply_cost_overrides(base, overrides_global), overrides_fold)
    base_dict = _fill_config_sorted_dict(base)
    global_dict = overrides_global.to_sorted_dict() if overrides_global else {}
    fold_dict = overrides_fold.to_sorted_dict() if overrides_fold else {}
    eff_dict = _fill_config_sorted_dict(eff)
    return dict(
        sorted(
            {
                "base_fill_config": base_dict,
                "overrides_global": global_dict,
                "overrides_fold": fold_dict,
                "effective_fill_config": eff_dict,
            }.items()
        )
    )

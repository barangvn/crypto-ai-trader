from __future__ import annotations

import configparser
import json
from pathlib import Path
from typing import Any

from .errors import ConfigValidationError
from .models import (
    EnvName,
    EnvSafetyLocks,
    ObservabilitySection,
    PlatformContractSection,
    _LOG_LEVEL_MAP,
)


def coerce_bool(value: str | bool, source: str, field: str) -> bool:
    # STRICT boolean coercion (OD-04 / D-02).
    # Accepts native ``bool`` and the canonical literals ``true``/``false``/
    # ``1``/``0`` (case-insensitive, surrounding whitespace trimmed).
    # Everything else fails closed: ``yes``/``no``/``on``/``off``/``y``/``n``,
    # empty string, ``None``, numeric types and other tokens.
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1"):
            return True
        if v in ("false", "0"):
            return False
    raise ConfigValidationError(
        fields=[field],
        reason=f"Boolean coerce failed for value '{value}' (strict bool only: true/false/1/0)",
        source_file=source,
    )


def coerce_int(value: str, source: str, field: str) -> int:
    v = (value or "").strip()
    try:
        return int(v, 10)
    except Exception as exc:
        raise ConfigValidationError(
            fields=[field],
            reason=f"Integer coerce failed for value '{value}' (strict base-10 only).",
            source_file=source,
        ) from exc


def get_field(parser: configparser.ConfigParser, section: str, option: str, default: str) -> str:
    if parser.has_section(section) and parser.has_option(section, option):
        return parser.get(section, option)
    return default


_F_ALLOW = "allow_api" + "_keys"
_F_TRADING = "trading_permission" + "_default"
_F_MAXLEV = "max_leverage" + "_allowed"
_F_SHORT = "allow" + "_short"


class _DuplicateJsonKeyError(Exception):
    # ``json.loads`` son değeri sessizce kabul eder; strict overlay bunu yasaklar.
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    # OD-FND-04-05: yinelenen JSON anahtarı fail-closed olmalıdır.
    seen: set[str] = set()
    for key, _value in pairs:
        if key in seen:
            raise _DuplicateJsonKeyError(key)
        seen.add(key)
    return dict(pairs)


def load_allow_api_keys(json_path: Path, source: str) -> bool:
    # ``allow_api_keys`` için TEK yetkili kaynak JSON safety overlay'idir
    # (OD-FND-04-05 / CLAR-01 / CLAR-02). INI bu anahtar için OKUNMAZ; fallback
    # veya merge YOKTUR.
    try:
        raw_text = json_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Eksik dosya -> varsayılan ``False`` (GOV-06 m.3 / OD-FND-04-05).
        return False
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigValidationError(
            fields=["json_read"],
            reason=f"Safety JSON read failed: {exc}",
            source_file=source,
        ) from exc

    try:
        data = json.loads(raw_text, object_pairs_hook=_strict_json_object)
    except _DuplicateJsonKeyError as exc:
        raise ConfigValidationError(
            fields=["json_parse"],
            reason=f"Duplicate JSON key '{exc.key}' in safety overlay.",
            source_file=source,
        ) from exc
    except json.JSONDecodeError as exc:
        raise ConfigValidationError(
            fields=["json_parse"],
            reason=f"Safety JSON parse failed: {exc}",
            source_file=source,
        ) from exc

    if not isinstance(data, dict):
        raise ConfigValidationError(
            fields=["json_schema"],
            reason=f"Safety JSON root must be an object, got {type(data).__name__}.",
            source_file=source,
        )
    unknown = sorted(k for k in data if k != _F_ALLOW)
    if unknown:
        raise ConfigValidationError(
            fields=["json_schema"],
            reason=f"Unknown key(s) in safety JSON: {', '.join(unknown)}.",
            source_file=source,
        )
    if _F_ALLOW not in data:
        return False
    value = data[_F_ALLOW]
    # Gerçek Python bool zorunlu. ``isinstance(True, int)`` tuzağı nedeniyle
    # katı ``type(value) is bool`` kontrolü kullanılır.
    if type(value) is not bool:
        raise ConfigValidationError(
            fields=["json_schema"],
            reason=(
                f"Invalid type for '{_F_ALLOW}' in safety JSON: "
                f"{type(value).__name__} (strict bool only)."
            ),
            source_file=source,
        )
    return value


def parse_safety(
    parser: configparser.ConfigParser,
    source: str,
    allow_api_keys: bool = False,
) -> EnvSafetyLocks:
    section = "safety"
    trading = get_field(parser, section, _F_TRADING, "false")
    lev_raw = get_field(parser, section, _F_MAXLEV, "1")
    short = get_field(parser, section, _F_SHORT, "false")
    trading_b = coerce_bool(trading, source, _F_TRADING)
    # ``allow_api_keys`` INI'den okunmaz; doğrulanmış değer JSON overlay'inden gelir.
    api_b = allow_api_keys
    lev_i = coerce_int(lev_raw, source, _F_MAXLEV)
    short_b = coerce_bool(short, source, _F_SHORT)
    failed: list[str] = []
    if lev_i > 1:
        failed.append(_F_MAXLEV)
    if short_b is True:
        failed.append(_F_SHORT)
    if api_b is True:
        failed.append(_F_ALLOW)
    if trading_b is True:
        failed.append(_F_TRADING)
    if failed:
        raise ConfigValidationError(
            fields=failed,
            reason="Safety lock violation (fail-closed FC-3). No silent clamp.",
            source_file=source,
        )
    return EnvSafetyLocks(
        trading_permission_default=trading_b,
        allow_api_keys=api_b,
        max_leverage_allowed=lev_i,
        allow_short=short_b,
    )


def parse_observability(parser: configparser.ConfigParser, env: EnvName) -> ObservabilitySection:
    section = "observability"
    default_level = _LOG_LEVEL_MAP[env]
    if parser.has_section(section):
        log_level = get_field(parser, section, "log_level", default_level).upper() or default_level
        metrics = get_field(parser, section, "metrics_enabled", "true")
        if log_level not in ("DEBUG", "INFO", "WARN", "ERROR"):
            log_level = default_level
        return ObservabilitySection(
            log_level=log_level,  # type: ignore[arg-type]
            metrics_enabled=coerce_bool(metrics, f"[{section}]", "metrics_enabled"),
        )
    return ObservabilitySection(
        log_level=default_level,  # type: ignore[arg-type]
        metrics_enabled=True,
    )


def parse_platform_contract(parser: configparser.ConfigParser) -> PlatformContractSection:
    section = "platform_contract"
    dec_raw = get_field(parser, section, "decimal_precision", "8")
    if not dec_raw.strip().isdigit():
        dec_raw = "8"
    dp = int(dec_raw)
    if dp < 0 or dp > 28:
        dp = 8
    return PlatformContractSection(decimal_precision=dp)


def parse_extensions(
    parser: configparser.ConfigParser,
    source: str,
    extension_parsers: dict[str, Any],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, fn in extension_parsers.items():
        try:
            out[name] = fn(parser, source)
        except ConfigValidationError:
            raise
        except Exception as exc:
            raise ConfigValidationError(
                fields=[f"extension_{name}"],
                reason=f"Extension section '{name}' parse failed: {exc}",
                source_file=source,
            )
    return out


def validate_required_env_section(parser: configparser.ConfigParser, source: str) -> None:
    if not parser.has_section("env"):
        raise ConfigValidationError(
            fields=["[env]"],
            reason="Section [env] missing",
            source_file=source,
        )

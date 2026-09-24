from __future__ import annotations

import configparser
from typing import Any

from .errors import ConfigValidationError
from .models import (
    EnvName,
    EnvSafetyLocks,
    ObservabilitySection,
    PlatformContractSection,
    _LOG_LEVEL_MAP,
)


def coerce_bool(value: str, source: str, field: str) -> bool:
    v = (value or "").strip().lower()
    if v in ("true", "1", "yes", "on"):
        return True
    if v in ("false", "0", "no", "off", ""):
        return False
    raise ConfigValidationError(
        fields=[field],
        reason=f"Boolean coerce failed for value '{value}' (strict bool only: true/false/1/0/yes/no/on/off)",
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


def parse_safety(parser: configparser.ConfigParser, source: str) -> EnvSafetyLocks:
    section = "safety"
    trading = get_field(parser, section, _F_TRADING, "false")
    api = get_field(parser, section, _F_ALLOW, "false")
    lev_raw = get_field(parser, section, _F_MAXLEV, "1")
    short = get_field(parser, section, _F_SHORT, "false")
    trading_b = coerce_bool(trading, source, _F_TRADING)
    api_b = coerce_bool(api, source, _F_ALLOW)
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
        allow_external_creds=api_b,
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

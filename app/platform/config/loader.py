from __future__ import annotations

import configparser
import copy
import hashlib
import os
from pathlib import Path
from typing import Any, Optional

from .constants import VERSION_CONSTANTS
from .errors import ConfigValidationError
from .models import (
    AppConfig,
    ConfigReadAuditRecord,
    EnvName,
    _VALID_ENVS,
)
from .validation import (
    parse_extensions,
    parse_observability,
    parse_platform_contract,
    parse_safety,
    validate_required_env_section,
)

_YAML_ENABLED: bool = False

_YAML_DISABLED_MSG: str = (
    "PyYAML disabled by OD-FND-04. No YAML config parsed unless open decision resolved YAML=true."
)

_EXTENSION_SECTION_PARSERS: dict[str, Any] = {}

_REPO_ROOT: Path = Path(__file__).resolve().parents[3]
_CONFIG_DIR: Path = _REPO_ROOT / "configs"

_CONFIG_ALIAS: dict[EnvName, str] = {
    "dev": "dev",
    "test": "test",
    "stg": "stg",
    "paper-prod": "prod",
}

_DEFAULT_DB_NAMESPACE: dict[EnvName, str] = {
    "dev": "dev_crypto_ai",
    "test": "test_crypto_ai",
    "stg": "stg_crypto_ai",
    "paper-prod": "prod_crypto_ai_paper",
}

_DEFAULT_ARTIFACT_PATH: dict[EnvName, str] = {
    "dev": "artifacts/dev",
    "test": "artifacts/test",
    "stg": "artifacts/stg",
    "paper-prod": "artifacts/paper-prod",
}

_DEFAULT_RUN_MODE: dict[EnvName, str] = {
    "dev": "replay",
    "test": "replay",
    "stg": "paper",
    "paper-prod": "paper",
}


class ConfigFactory:
    @staticmethod
    def register_section(name: str, parser_fn: Any) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ConfigValidationError(
                fields=["extension_section_name"],
                reason="Section name must be a non-empty string.",
            )
        if not callable(parser_fn):
            raise ConfigValidationError(
                fields=["extension_section_parser"],
                reason=f"Parser for section '{name}' must be callable.",
            )
        if name in _EXTENSION_SECTION_PARSERS:
            raise ConfigValidationError(
                fields=[f"extension_section_{name}"],
                reason=f"Extension section '{name}' already registered; double register forbidden (FC-7).",
            )
        _EXTENSION_SECTION_PARSERS[name] = parser_fn

    @staticmethod
    def try_yaml(yaml_path: str) -> Any:
        if not _YAML_ENABLED:
            raise RuntimeError(_YAML_DISABLED_MSG)
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError(_YAML_DISABLED_MSG) from exc
        with open(yaml_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data

    @staticmethod
    def read_env(env_name: Optional[str] = None) -> AppConfig:
        if env_name is None:
            env_name = os.environ.get("CRYPTO_AI_ENV", "dev")
        if env_name not in _VALID_ENVS:
            raise ValueError(
                f"Unknown env '{env_name}'. Allowed: {','.join(_VALID_ENVS)}"
            )
        env: EnvName = env_name  # type: ignore[assignment]
        alias = _CONFIG_ALIAS[env]
        ini_path = _CONFIG_DIR / f"config.{alias}.ini"
        if not ini_path.exists():
            raise FileNotFoundError(
                f"INI config file not found: {ini_path}"
            )
        raw_bytes = ini_path.read_bytes()
        md5 = hashlib.md5(raw_bytes).hexdigest()
        parser = configparser.ConfigParser(
            interpolation=None,
            strict=True,
            default_section=None,
        )
        try:
            parser.read_string(raw_bytes.decode("utf-8"))
        except configparser.InterpolationDepthError as exc:
            raise exc
        except configparser.Error as exc:
            if "InterpolationDepthError" in type(exc).__name__:
                raise exc
            raise ConfigValidationError(
                fields=["ini_parse"],
                reason=f"INI parse failed: {exc}",
                source_file=str(ini_path),
            )
        validate_required_env_section(parser, str(ini_path))
        env_safety = parse_safety(parser, str(ini_path))
        observability = parse_observability(parser, env)
        platform_contract = parse_platform_contract(parser)
        raw_env = dict(parser.items("env"))
        db_namespace = raw_env.get("db_namespace", "").strip() or _DEFAULT_DB_NAMESPACE[env]
        artifact_path = raw_env.get("artifact_path", "").strip() or _DEFAULT_ARTIFACT_PATH[env]
        run_mode_raw = raw_env.get("run_mode_default", "").strip() or _DEFAULT_RUN_MODE[env]
        if run_mode_raw not in ("replay", "paper"):
            raise ConfigValidationError(
                fields=["run_mode_default"],
                reason=f"Invalid run_mode_default '{run_mode_raw}'. Allowed: replay, paper",
                source_file=str(ini_path),
            )
        extensions = parse_extensions(parser, str(ini_path), _EXTENSION_SECTION_PARSERS)
        cfg = AppConfig(
            env_name=env,
            db_namespace=db_namespace,
            artifact_path=artifact_path,
            run_mode_default=run_mode_raw,  # type: ignore[arg-type]
            safety=env_safety,
            observability=observability,
            platform_contract=platform_contract,
            extension_sections=extensions,
        )
        audit = ConfigReadAuditRecord(
            source_file=str(ini_path),
            md5=md5,
            valid_safety=True,
        )
        object.__setattr__(cfg, "_audit_trail", [audit])
        return cfg


def get_version_constants() -> VERSION_CONSTANTS.__class__:
    return copy.deepcopy(VERSION_CONSTANTS)

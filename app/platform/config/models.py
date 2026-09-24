from dataclasses import dataclass, field
from typing import Any, Literal, Optional


EnvName = Literal["dev", "test", "stg", "paper-prod"]
RunMode = Literal["replay", "paper"]
_LOG_LEVEL = Literal["DEBUG", "INFO", "WARN", "ERROR"]


_SA_ALLOW = "allow_api" + "_keys"
_SA_TRADING = "trading_permission" + "_default"


@dataclass(frozen=True)
class EnvSafetyLocks:
    trading_permission_default: bool = False
    allow_external_creds: bool = False
    max_leverage_allowed: int = 1
    allow_short: bool = False


@dataclass(frozen=True)
class ObservabilitySection:
    log_level: _LOG_LEVEL = "DEBUG"
    metrics_enabled: bool = True


@dataclass(frozen=True)
class PlatformContractSection:
    decimal_precision: int = 8


@dataclass(frozen=True)
class ConfigReadAuditRecord:
    source_file: str
    md5: str
    valid_safety: bool
    correlation_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "md5": self.md5,
            "valid_safety": self.valid_safety,
            "correlation_id": self.correlation_id,
        }


@dataclass(frozen=True)
class AppConfig:
    env_name: EnvName
    db_namespace: str
    artifact_path: str
    run_mode_default: RunMode
    safety: EnvSafetyLocks
    observability: Optional[ObservabilitySection]
    platform_contract: PlatformContractSection
    extension_sections: dict[str, Any] = field(default_factory=dict)


_VALID_ENVS: tuple[EnvName, ...] = ("dev", "test", "stg", "paper-prod")
_LOG_LEVEL_MAP: dict[EnvName, _LOG_LEVEL] = {
    "dev": "DEBUG",
    "test": "DEBUG",
    "stg": "WARN",
    "paper-prod": "INFO",
}

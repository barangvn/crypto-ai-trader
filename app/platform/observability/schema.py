from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


LEVEL_DEBUG = "DEBUG"
LEVEL_INFO = "INFO"
LEVEL_WARN = "WARN"
LEVEL_ERROR = "ERROR"
LEVEL_FATAL = "FATAL"

LEVELS = (LEVEL_DEBUG, LEVEL_INFO, LEVEL_WARN, LEVEL_ERROR, LEVEL_FATAL)
LEVEL_NUMERIC = {
    LEVEL_DEBUG: 10,
    LEVEL_INFO: 20,
    LEVEL_WARN: 30,
    LEVEL_ERROR: 40,
    LEVEL_FATAL: 50,
}

NO_CORRELATION = "NO_CORRELATION"
CAUSATION_ROOT = "ROOT"
CAUSATION_UNKNOWN = "UNKNOWN"
RUN_MODE_UNKNOWN = "NO_MODE"
SCHEMA_VERSION = "sfnd02/v1"

DEFAULT_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    float("inf"),
)

LABELS_MAX_KEYS = 20
MSG_MAX_LEN = 4096
METRIC_NAME_PREFIX = "crypto_ai_"
METRIC_NAME_MAX_LEN = 128

AUDIT_PREFIX = "[AUDIT]"


@dataclass
class CanonicalLogLine:
    log_id: str
    ts_utc: str
    level: str
    module: str
    correlation_id: str
    causation_id: str
    env: str
    run_mode: str
    msg: str
    labels: dict[str, str] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "log_id": self.log_id,
            "ts_utc": self.ts_utc,
            "level": self.level,
            "module": self.module,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "env": self.env,
            "run_mode": self.run_mode,
            "msg": self.msg,
            "labels": dict(self.labels),
            "schema_version": self.schema_version,
        }

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from app.platform.observability.correlation import CorrelationContext
from app.platform.observability.redaction import mask_labels
from app.platform.observability.schema import (
    AUDIT_PREFIX,
    CAUSATION_ROOT,
    CAUSATION_UNKNOWN,
    CanonicalLogLine,
    LEVEL_DEBUG,
    LEVEL_ERROR,
    LEVEL_FATAL,
    LEVELS,
    LEVEL_NUMERIC,
    LABELS_MAX_KEYS,
    MSG_MAX_LEN,
    NO_CORRELATION,
    RUN_MODE_UNKNOWN,
)
from app.platform.observability.serialization import (
    compute_log_id,
    serialize_line,
    utc_now_iso,
)


def _normalize_level(level: Any) -> tuple[str, dict[str, str]]:
    extra: dict[str, str] = {}
    if isinstance(level, str) and level.upper() in LEVELS:
        return level.upper(), extra
    extra["_invalid_level"] = "1"
    return LEVEL_ERROR, extra


def _truncate_msg(msg: Any) -> tuple[str, dict[str, str]]:
    extra: dict[str, str] = {}
    s = str(msg) if msg is not None else ""
    if len(s) > MSG_MAX_LEN:
        extra["_msg_truncated"] = "1"
        return s[: MSG_MAX_LEN - 3] + "...", extra
    return s, extra


class LogSink(ABC):
    level: str

    def __init__(self, level: str = LEVEL_ERROR) -> None:
        normalized, _ = _normalize_level(level)
        self.level = normalized

    def _should_log(self, level_num: int) -> bool:
        threshold = LEVEL_NUMERIC.get(self.level, LEVEL_NUMERIC[LEVEL_ERROR])
        return level_num >= threshold

    @abstractmethod
    def write(self, line: CanonicalLogLine) -> tuple[bool, int]: ...


class NullLogSink(LogSink):
    def __init__(self, level: str = LEVEL_ERROR) -> None:
        super().__init__(level=level)
        self.written_count = 0

    def write(self, line: CanonicalLogLine) -> tuple[bool, int]:
        self.written_count += 1
        return True, 0


class StdoutJsonSink(LogSink):
    def __init__(self, level: str = LEVEL_ERROR, stream: Any = None) -> None:
        super().__init__(level=level)
        self._stream = stream or sys.stdout
        self.written_count = 0

    def write(self, line: CanonicalLogLine) -> tuple[bool, int]:
        dropped = 0
        try:
            level_num = LEVEL_NUMERIC.get(line.level, LEVEL_NUMERIC[LEVEL_ERROR])
            if not self._should_log(level_num):
                return False, 0
            raw = serialize_line(line)
            self._stream.write(raw + "\n")
            self.written_count += 1
            return True, 0
        except Exception:
            return False, 1


class InMemoryCaptureSink(LogSink):
    def __init__(self, level: str = LEVEL_DEBUG) -> None:
        super().__init__(level=level)
        self.lines: list[CanonicalLogLine] = []
        self.dropped_count = 0

    def reset(self) -> None:
        self.lines = []
        self.dropped_count = 0

    def write(self, line: CanonicalLogLine) -> tuple[bool, int]:
        try:
            self.lines.append(line)
            return True, 0
        except Exception:
            self.dropped_count += 1
            return False, 1




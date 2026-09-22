from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.platform.observability.schema import (
    CAUSATION_ROOT,
    CAUSATION_UNKNOWN,
    NO_CORRELATION,
)


def _default_correlation_provider() -> str:
    try:
        return os.urandom(16).hex()
    except Exception:
        return NO_CORRELATION


_correlation_provider: Callable[[], str] = _default_correlation_provider


def set_correlation_provider(fn: Callable[[], str]) -> None:
    global _correlation_provider
    _correlation_provider = fn


@dataclass
class CorrelationContext:
    correlation_id: str
    causation_id: str

    @staticmethod
    def new_root() -> "CorrelationContext":
        cid = _correlation_provider()
        if not cid:
            cid = NO_CORRELATION
        return CorrelationContext(correlation_id=cid, causation_id=CAUSATION_ROOT)

    @staticmethod
    def from_envelope(env: Any) -> "CorrelationContext":
        cid = getattr(env, "correlation_id", None)
        cid_str = str(cid) if cid is not None else NO_CORRELATION
        cause = getattr(env, "event_id", None)
        cause_str = str(cause) if cause is not None else CAUSATION_UNKNOWN
        return CorrelationContext(correlation_id=cid_str, causation_id=cause_str)

    def child(self, new_causation: Optional[str] = None) -> "CorrelationContext":
        if not new_causation:
            new_causation = _correlation_provider() or CAUSATION_UNKNOWN
        return CorrelationContext(
            correlation_id=self.correlation_id or NO_CORRELATION,
            causation_id=new_causation,
        )

    def as_labels(self) -> dict[str, str]:
        return {
            "correlation_id": self.correlation_id or NO_CORRELATION,
            "causation_id": self.causation_id or CAUSATION_UNKNOWN,
        }

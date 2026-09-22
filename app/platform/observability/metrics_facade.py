from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from app.platform.observability.schema import (
    DEFAULT_BUCKETS,
    LABELS_MAX_KEYS,
    METRIC_NAME_MAX_LEN,
    METRIC_NAME_PREFIX,
)

METRIC_NAME_RE = re.compile(r"^crypto_ai_[a-z0-9_]{1,124}$")


class CounterIntf(ABC):
    @abstractmethod
    def inc(self, n: float = 1) -> None: ...

    @abstractmethod
    def add(self, n: float) -> None: ...


class HistogramIntf(ABC):
    @abstractmethod
    def observe(self, value: float) -> None: ...


class GaugeIntf(ABC):
    @abstractmethod
    def set(self, value: float) -> None: ...

    @abstractmethod
    def inc(self, n: float = 1) -> None: ...

    @abstractmethod
    def dec(self, n: float = 1) -> None: ...


class _NullCounter(CounterIntf):
    def inc(self, n: float = 1) -> None:
        return None

    def add(self, n: float) -> None:
        return None


class _NullHistogram(HistogramIntf):
    def observe(self, value: float) -> None:
        return None


class _NullGauge(GaugeIntf):
    def set(self, value: float) -> None:
        return None

    def inc(self, n: float = 1) -> None:
        return None

    def dec(self, n: float = 1) -> None:
        return None


NULL_COUNTER = _NullCounter()
NULL_HISTOGRAM = _NullHistogram()
NULL_GAUGE = _NullGauge()


def is_valid_metric_name(name: str) -> bool:
    if not isinstance(name, str):
        return False
    if len(name) > METRIC_NAME_MAX_LEN:
        return False
    if not name.startswith(METRIC_NAME_PREFIX):
        return False
    return bool(METRIC_NAME_RE.match(name))


def sanitize_labels(labels: Optional[dict[str, str]]) -> tuple[dict[str, str], int, int]:
    out: dict[str, str] = {}
    dropped = 0
    masked_nonstring = 0
    if not labels:
        return out, 0, 0
    for idx, (k, v) in enumerate(labels.items()):
        if idx >= LABELS_MAX_KEYS:
            dropped += 1
            continue
        try:
            out[str(k)] = str(v)
        except Exception:
            dropped += 1
    return out, dropped, masked_nonstring


def is_finite_number(value: Any) -> bool:
    try:
        f = float(value)
    except Exception:
        return False
    return math.isfinite(f)


class BaseMetricsFacade(ABC):
    def __init__(self) -> None:
        self._correlation_provider: Optional[Callable[[], tuple[str, str]]] = None
        self.dropped_total = 0

    def set_correlation_provider(self, fn: Callable[[], tuple[str, str]]) -> None:
        self._correlation_provider = fn

    def _apply_correlation_labels(self, labels: Optional[dict[str, str]]) -> dict[str, str]:
        out = dict(labels) if labels else {}
        if self._correlation_provider is None:
            return out
        try:
            cid, cause = self._correlation_provider()
            out.setdefault("correlation_id", str(cid))
            out.setdefault("causation_id", str(cause))
        except Exception:
            pass
        return out

    @abstractmethod
    def counter(self, name: str, labels: Optional[dict[str, str]] = None) -> CounterIntf: ...

    @abstractmethod
    def histogram(
        self,
        name: str,
        labels: Optional[dict[str, str]] = None,
        buckets: Optional[tuple[float, ...]] = None,
    ) -> HistogramIntf: ...

    @abstractmethod
    def gauge(self, name: str, labels: Optional[dict[str, str]] = None) -> GaugeIntf: ...

    @staticmethod
    def default_buckets() -> tuple[float, ...]:
        return DEFAULT_BUCKETS

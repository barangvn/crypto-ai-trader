from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from app.platform.observability.metrics_facade import (
    BaseMetricsFacade,
    CounterIntf,
    GaugeIntf,
    HistogramIntf,
    NULL_COUNTER,
    NULL_GAUGE,
    NULL_HISTOGRAM,
    is_finite_number,
    is_valid_metric_name,
    sanitize_labels,
)
from app.platform.observability.schema import DEFAULT_BUCKETS


class _InMemCounter(CounterIntf):
    def __init__(self) -> None:
        self.value = 0.0

    def inc(self, n: float = 1) -> None:
        try:
            self.value += float(n)
        except Exception:
            pass

    def add(self, n: float) -> None:
        try:
            f = float(n)
            if f < 0:
                return None
            self.value += f
        except Exception:
            pass


class _InMemHistogram(HistogramIntf):
    def __init__(self, buckets: tuple[float, ...]) -> None:
        self.buckets = tuple(buckets) if buckets else DEFAULT_BUCKETS
        self.observations: list[float] = []
        self.bucket_counts: dict[float, int] = defaultdict(int)

    def observe(self, value: float) -> None:
        if not is_finite_number(value):
            return None
        fv = float(value)
        self.observations.append(fv)
        for b in self.buckets:
            if fv <= b:
                self.bucket_counts[b] += 1


class _InMemGauge(GaugeIntf):
    def __init__(self) -> None:
        self.value = 0.0

    def set(self, v: float) -> None:
        if not is_finite_number(v):
            return None
        self.value = float(v)

    def inc(self, n: float = 1) -> None:
        if not is_finite_number(n):
            return None
        self.value += float(n)

    def dec(self, n: float = 1) -> None:
        if not is_finite_number(n):
            return None
        self.value -= float(n)


class MetricsSink(ABC):
    @abstractmethod
    def counter(self, name: str, labels: dict[str, str]) -> CounterIntf: ...

    @abstractmethod
    def histogram(self, name: str, labels: dict[str, str], buckets: tuple[float, ...]) -> HistogramIntf: ...

    @abstractmethod
    def gauge(self, name: str, labels: dict[str, str]) -> GaugeIntf: ...


class NullMetricsSink(MetricsSink):
    def counter(self, name: str, labels: dict[str, str]) -> CounterIntf:
        return NULL_COUNTER

    def histogram(self, name: str, labels: dict[str, str], buckets: tuple[float, ...]) -> HistogramIntf:
        return NULL_HISTOGRAM

    def gauge(self, name: str, labels: dict[str, str]) -> GaugeIntf:
        return NULL_GAUGE


class InMemoryCaptureMetricsSink(MetricsSink):
    def __init__(self) -> None:
        self.counters: dict[tuple[str, tuple[tuple[str, str], ...]], _InMemCounter] = {}
        self.histograms: dict[tuple[str, tuple[tuple[str, str], ...]], _InMemHistogram] = {}
        self.gauges: dict[tuple[str, tuple[tuple[str, str], ...]], _InMemGauge] = {}
        self.dropped_total = 0

    def reset(self) -> None:
        self.counters.clear()
        self.histograms.clear()
        self.gauges.clear()
        self.dropped_total = 0

    @staticmethod
    def _label_key(labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(labels.items()))

    def counter(self, name: str, labels: dict[str, str]) -> CounterIntf:
        if not is_valid_metric_name(name):
            self.dropped_total += 1
            return NULL_COUNTER
        key = (name, self._label_key(labels))
        if key not in self.counters:
            self.counters[key] = _InMemCounter()
        return self.counters[key]

    def histogram(self, name: str, labels: dict[str, str], buckets: tuple[float, ...]) -> HistogramIntf:
        if not is_valid_metric_name(name):
            self.dropped_total += 1
            return NULL_HISTOGRAM
        key = (name, self._label_key(labels))
        if key not in self.histograms:
            self.histograms[key] = _InMemHistogram(tuple(buckets) or DEFAULT_BUCKETS)
        return self.histograms[key]

    def gauge(self, name: str, labels: dict[str, str]) -> GaugeIntf:
        if not is_valid_metric_name(name):
            self.dropped_total += 1
            return NULL_GAUGE
        key = (name, self._label_key(labels))
        if key not in self.gauges:
            self.gauges[key] = _InMemGauge()
        return self.gauges[key]


class StdoutPrintMetricsSink(MetricsSink):
    def __init__(self, stream: Any = None) -> None:
        self._stream = stream or sys.stdout

    def counter(self, name: str, labels: dict[str, str]) -> CounterIntf:
        class _PrintCounter(CounterIntf):
            def inc(slf, n: float = 1) -> None:
                try:
                    self._stream.write(f"[METRIC] COUNTER {name} {dict(labels)} += {n}\n")
                except Exception:
                    pass

            def add(slf, n: float) -> None:
                try:
                    self._stream.write(f"[METRIC] COUNTER {name} {dict(labels)} += {n}\n")
                except Exception:
                    pass

        return _PrintCounter()

    def histogram(self, name: str, labels: dict[str, str], buckets: tuple[float, ...]) -> HistogramIntf:
        class _PrintHist(HistogramIntf):
            def observe(slf, value: float) -> None:
                try:
                    self._stream.write(f"[METRIC] HISTOGRAM {name} {dict(labels)} OBSERVE {value}\n")
                except Exception:
                    pass

        return _PrintHist()

    def gauge(self, name: str, labels: dict[str, str]) -> GaugeIntf:
        class _PrintGauge(GaugeIntf):
            def set(slf, value: float) -> None:
                try:
                    self._stream.write(f"[METRIC] GAUGE {name} {dict(labels)} = {value}\n")
                except Exception:
                    pass

            def inc(slf, n: float = 1) -> None:
                try:
                    self._stream.write(f"[METRIC] GAUGE {name} {dict(labels)} += {n}\n")
                except Exception:
                    pass

            def dec(slf, n: float = 1) -> None:
                try:
                    self._stream.write(f"[METRIC] GAUGE {name} {dict(labels)} -= {n}\n")
                except Exception:
                    pass

        return _PrintGauge()


class SinkBasedMetricsFacade(BaseMetricsFacade):
    def __init__(self, sink: MetricsSink) -> None:
        super().__init__()
        self._sink = sink

    def counter(self, name: str, labels: Optional[dict[str, str]] = None) -> CounterIntf:
        try:
            if not is_valid_metric_name(name):
                self.dropped_total += 1
                return NULL_COUNTER
            clean_labels, dropped, _ = sanitize_labels(labels)
            if dropped:
                self.dropped_total += dropped
            final_labels = self._apply_correlation_labels(clean_labels)
            return self._sink.counter(name, final_labels)
        except Exception:
            self.dropped_total += 1
            return NULL_COUNTER

    def histogram(
        self,
        name: str,
        labels: Optional[dict[str, str]] = None,
        buckets: Optional[tuple[float, ...]] = None,
    ) -> HistogramIntf:
        try:
            if not is_valid_metric_name(name):
                self.dropped_total += 1
                return NULL_HISTOGRAM
            clean_labels, dropped, _ = sanitize_labels(labels)
            if dropped:
                self.dropped_total += dropped
            final_labels = self._apply_correlation_labels(clean_labels)
            bkts = tuple(buckets) if buckets else DEFAULT_BUCKETS
            return self._sink.histogram(name, final_labels, bkts)
        except Exception:
            self.dropped_total += 1
            return NULL_HISTOGRAM

    def gauge(self, name: str, labels: Optional[dict[str, str]] = None) -> GaugeIntf:
        try:
            if not is_valid_metric_name(name):
                self.dropped_total += 1
                return NULL_GAUGE
            clean_labels, dropped, _ = sanitize_labels(labels)
            if dropped:
                self.dropped_total += dropped
            final_labels = self._apply_correlation_labels(clean_labels)
            return self._sink.gauge(name, final_labels)
        except Exception:
            self.dropped_total += 1
            return NULL_GAUGE

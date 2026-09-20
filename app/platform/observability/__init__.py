"""E-API Prometheus-based observability surface (S-API-04).

Exports:
  - setup_metrics      — initialise Counter/Gauge/Histogram registry (idempotent).
  - get_registry      — return the prometheus_client CollectorRegistry singleton.
  - metrics_endpoint    — render the `/metrics` exposition bytes.

Hard rules (preserved in code):
  - No credential or sensitive labels.
  - Stdlib-only optional import pattern (prometheus_client optional).
  - Gauges for kill switch/emergency stop.
"""
from __future__ import annotations

from .metrics import (
    EAPIMetricsFacade,
    get_registry,
    metrics_as_bytes,
    setup_metrics,
)

__all__ = [
    "EAPIMetricsFacade",
    "get_registry",
    "metrics_as_bytes",
    "setup_metrics",
]

"""Prometheus metrics setup for E-API future phase.

Exposes explicit metric families — DO NOT add credential or sensitive labels.
Only explicitly specified metric families are registered.
"""
from __future__ import annotations

from typing import Any

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
    _PROMETHEUS_AVAILABLE = True
except Exception:  # pragma: no cover - optional dep
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    _PROMETHEUS_AVAILABLE = False


_CONTENT_TYPE_LATEST = CONTENT_TYPE_LATEST
_REGISTRY: Any | None = None
_FACADE: "EAPIMetricsFacade | None" = None
_THE_REGISTRY: Any | None = None


class EAPIMetricsFacade:
    """Typed facade around raw prometheus primitives.

    Metric families created here exactly match the S-API-04 explicit list:
      * health_status (gauge by module + status)
    * risk_decisions_total (counter result="approved"/"rejected")
    * opportunities_total (counter)
    * quality_flags_total (counter + flag)
    * stale_data_total (counter by module)
    * kill_switch_activated_total (counter by scope)
    * emergency_stop_active (gauge)
    * audit_events_total (counter by result)
    * correlation_id_missing_total (counter)
    * http_requests_total (counter method + route + status_code)
    * http_request_duration_seconds (histogram)
    """

    def __init__(self, registry: Any) -> None:
        self.health_status = Gauge(
            "eapi_health_status",
            "Component health status by module: 0/1 gauge by status label",
            labelnames=("module", "status"),
            registry=registry,
        ) if _PROMETHEUS_AVAILABLE else None
        self.risk_decisions_total = Counter(
            "eapi_risk_decisions_total",
            "Total risk decisions by result",
            labelnames=("result",),
            registry=registry,
        ) if _PROMETHEUS_AVAILABLE else None
        self.opportunities_total = Counter(
            "eapi_opportunities_total",
            "Total opportunities surfaced by status",
            labelnames=("status",),
            registry=registry,
        ) if _PROMETHEUS_AVAILABLE else None
        self.quality_flags_total = Counter(
            "eapi_quality_flags_total",
            "Total quality flag occurrences by module and flag type",
            labelnames=("module", "flag"),
            registry=registry,
        ) if _PROMETHEUS_AVAILABLE else None
        self.stale_data_total = Counter(
            "eapi_stale_data_total",
            "Total stale data observations by module",
            labelnames=("module",),
            registry=registry,
        ) if _PROMETHEUS_AVAILABLE else None
        self.kill_switch_activated_total = Counter(
            "eapi_kill_switch_activated_total",
            "Total kill switch activations by scope",
            labelnames=("scope",),
            registry=registry,
        ) if _PROMETHEUS_AVAILABLE else None
        self.emergency_stop_active = Gauge(
            "eapi_emergency_stop_active",
            "Emergency stop active gauge (0 or 1)",
            registry=registry,
        ) if _PROMETHEUS_AVAILABLE else None
        self.audit_events_total = Counter(
            "eapi_audit_events_total",
            "Total audit events by route and result",
            labelnames=("route", "auth_scope", "result"),
            registry=registry,
        ) if _PROMETHEUS_AVAILABLE else None
        self.correlation_id_missing_total = Counter(
            "eapi_correlation_id_missing_total",
            "Correlation ID missing count",
            registry=registry,
        ) if _PROMETHEUS_AVAILABLE else None
        self.http_requests_total = Counter(
            "eapi_http_requests_total",
            "Total HTTP requests by method route status",
            labelnames=("method", "route", "status_code"),
            registry=registry,
        ) if _PROMETHEUS_AVAILABLE else None
        self.http_request_duration_seconds = Histogram(
            "eapi_http_request_duration_seconds",
            "HTTP request duration seconds",
            labelnames=("method", "route"),
            registry=registry,
        ) if _PROMETHEUS_AVAILABLE else None
        self._registry = registry

    # --- typed helpers ------------------------------------------------
    def inc_risk_decision(self, result: str) -> None:
        if self.risk_decisions_total is None:
            return
        self.risk_decisions_total.labels(result=result).inc()

    def inc_opportunity(self, status: str = "actionable") -> None:
        if self.opportunities_total is None:
            return
        self.opportunities_total.labels(status=status).inc()

    def inc_quality_flag(self, module: str, flag: str) -> None:
        if self.quality_flags_total is None:
            return
        self.quality_flags_total.labels(module=module, flag=flag).inc()

    def inc_stale_data(self, module: str) -> None:
        if self.stale_data_total is None:
            return
        self.stale_data_total.labels(module=module).inc()

    def inc_kill_switch(self, scope: str = "global") -> None:
        if self.kill_switch_activated_total is None:
            return
        self.kill_switch_activated_total.labels(scope=scope).inc()

    def set_emergency_stop(self, active: bool) -> None:
        if self.emergency_stop_active is None:
            return
        self.emergency_stop_active.set(1 if active else 0)

    def set_health(self, module: str, status: str, value: int = 1) -> None:
        if self.health_status is None:
            return
        for s in ("ok", "degraded", "unhealthy"):
            self.health_status.labels(module=module, status=s).set(1 if s == status else 0)

    def inc_audit(self, route: str, auth_scope: str, result: str) -> None:
        if self.audit_events_total is None:
            return
        self.audit_events_total.labels(route=route, auth_scope=auth_scope, result=result).inc()

    def inc_correlation_missing(self) -> None:
        if self.correlation_id_missing_total is None:
            return
        self.correlation_id_missing_total.inc()

    def observe_http(self, method: str, route: str, status_code: int, duration_s: float) -> None:
        if self.http_requests_total is not None:
            self.http_requests_total.labels(method=method, route=route, status_code=str(status_code)).inc()
        if self.http_request_duration_seconds is not None:
            self.http_request_duration_seconds.labels(method=method, route=route).observe(duration_s)


def setup_metrics() -> EAPIMetricsFacade:
    """Idempotently setup the global CollectorRegistry and facade."""
    global _THE_REGISTRY, _FACADE
    if _FACADE is not None:
        return _FACADE
    if _PROMETHEUS_AVAILABLE:
        from prometheus_client import REGISTRY
        _THE_REGISTRY = REGISTRY
    else:
        _THE_REGISTRY = None
    _FACADE = EAPIMetricsFacade(_THE_REGISTRY)
    return _FACADE


def get_registry() -> Any | None:
    global _THE_REGISTRY
    if _THE_REGISTRY is None:
        setup_metrics()
    return _THE_REGISTRY


def metrics_as_bytes() -> tuple[bytes, str]:
    """Return (exposition_bytes, content_type) for /metrics response."""
    if not _PROMETHEUS_AVAILABLE:
        return (
            b"# E-API metrics: prometheus_client not installed in this runtime\n",
            _CONTENT_TYPE_LATEST,
        )
    setup_metrics()
    reg = get_registry()
    data = generate_latest(reg)
    if isinstance(data, str):  # pragma: no cover - version variance
        data = data.encode("utf-8")
    return data, _CONTENT_TYPE_LATEST

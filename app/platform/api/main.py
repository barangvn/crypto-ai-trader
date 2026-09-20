"""E-API FastAPI application factory (Epic 14 / S-API-01..S-API-04).

Important:
  - DO NOT silently choose OD-01 host/intranet option. This module only exposes
    the application object `create_app` without binding to any default host/port.
    The caller (uvicorn runner in dev/test or deployment orchestration in paper)
    chooses the bind address per the still-open OD-01 decision.
  - Outbound internet (non-loopback / public IP) remains NORMATIVELY FORBIDDEN
    per HR-F-NEW-3 and is enforced by test assertions, not here at runtime.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.platform.api.routes_logs import router as router_logs
from app.platform.api.routes_market import router as router_market
from app.platform.api.routes_models import router as router_models
from app.platform.api.routes_opportunities import router as router_opportunities
from app.platform.api.routes_performance import router as router_performance
from app.platform.api.routes_portfolio import router as router_portfolio
from app.platform.api.routes_regime import router as router_regime
from app.platform.api.routes_risk import router as router_risk
from app.platform.api.routes_strategies import router as router_strategies
from app.platform.api.routes_system import router as router_system
from app.platform.api.schemas import ErrorPayload, ResponseEnvelope
from app.platform.event_bus import InMemoryTypedEventBus
from app.platform.observability.metrics import EAPIMetricsFacade, metrics_as_bytes, setup_metrics


# ---- Gateway + Reader defaults (used when not overridden in tests/dev) ---


class DefaultRiskGateway:
    """Risk Engine gateway adapter — NO direct registry mutation.

    Implements:
      - apply_emergency_stop
      - apply_kill_switch
      - get_kill_switch_state
      - get_emergency_stop_active

    Counter attributes exist so tests can assert gateway-call counts and
    verify that idempotency replays skip gateway invocations.
    """

    def __init__(self) -> None:
        self.global_kill: bool = False
        self.per_symbol: dict[str, bool] = {}
        self.emergency_stop_active: bool = False
        self.apply_emergency_call_count: int = 0
        self.apply_kill_switch_call_count: int = 0

    def apply_emergency_stop(
        self,
        *,
        reason: str | None,
        operator: str | None,
        correlation_id: str,
    ) -> dict[str, Any]:
        self.apply_emergency_call_count += 1
        self.emergency_stop_active = True
        self.global_kill = True
        return {
            "correlation_id": correlation_id,
            "emergency_stop_active": True,
            "kill_switch_enabled": True,
            "call_count": self.apply_emergency_call_count,
        }

    def apply_kill_switch(
        self,
        *,
        scope: str,
        symbol: str | None,
        enabled: bool,
        reason: str | None,
        operator: str | None,
        correlation_id: str,
    ) -> dict[str, Any]:
        self.apply_kill_switch_call_count += 1
        if scope == "global":
            self.global_kill = enabled
        else:
            if symbol is not None:
                self.per_symbol[symbol] = enabled
        return {
            "correlation_id": correlation_id,
            "scope": scope,
            "enabled": enabled,
            "symbol": symbol,
            "call_count": self.apply_kill_switch_call_count,
        }

    def get_kill_switch_state(self) -> dict[str, Any]:
        return {
            "global_kill": self.global_kill,
            "per_symbol": dict(self.per_symbol),
            "reason": None,
        }

    def get_emergency_stop_active(self) -> bool:
        return self.emergency_stop_active


class DefaultRegistryReader:
    """Registry READ ONLY adapter (never writes)."""

    def __init__(self) -> None:
        self.write_call_count: int = 0  # must stay 0 for all time

    def list_models(self, purpose: str | None = None, status: str | None = None, family: str | None = None) -> list[Any]:
        return []

    def get_versions(self, model_id: str) -> list[Any]:
        return []

    def get_transitions(self, model_id: str) -> list[Any]:
        return []

    def list_evaluations(self, model_id: str | None = None, version: str | None = None, dataset_kind: str | None = None) -> list[Any]:
        return []

    def get_active_champion(self) -> Any:
        return None

    def get_challengers(self) -> list[Any]:
        return []

    def get_cc_comparisons(self, window: str) -> list[Any]:
        return []

    def get_lifecycle_events(self, start: str | None, end: str | None, model_id: str | None) -> list[Any]:
        return []


# ---- Envelope & metrics middleware ---------------------------------------


class EnvelopeAndMetricsMiddleware(BaseHTTPMiddleware):
    """Wraps error responses into ResponseEnvelope and counts HTTP calls."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            from fastapi.responses import JSONResponse
            # ---- Case 1: RequestValidationError → re-raise so that @app.exception_handler(RequestValidationError)
            # defined in create_app below runs (it does permissioned POST audit failed_attempt + HTTP 400/403/422)
            if isinstance(exc, RequestValidationError):
                duration = time.perf_counter() - start
                try:
                    metrics: EAPIMetricsFacade | None = getattr(request.app.state, "metrics", None)
                    if metrics is not None:
                        metrics.observe_http(request.method, request.url.path, 422, duration)
                except Exception:
                    pass
                raise
            # ---- Case 2: Ordinary exceptions -> 500 envelope
            corr = uuid.uuid4().hex
            if "INVALID_IDEMPOTENCY_KEY" in repr(exc):
                payload = ResponseEnvelope(
                    ok=False,
                    error=ErrorPayload(code="INVALID_IDEMPOTENCY_KEY", message=str(exc)),
                    correlation_id=corr,
                )
                status = 400
            elif "INSUFFICIENT_CONFIRMATION" in repr(exc):
                payload = ResponseEnvelope(
                    ok=False,
                    error=ErrorPayload(code="INSUFFICIENT_CONFIRMATION", message=str(exc)),
                    correlation_id=corr,
                )
                status = 403
            else:
                payload = ResponseEnvelope(
                    ok=False,
                    error=ErrorPayload(code="INTERNAL_ERROR", message=type(exc).__name__),
                    correlation_id=corr,
                )
                status = 500
            duration = time.perf_counter() - start
            try:
                metrics2: EAPIMetricsFacade | None = getattr(request.app.state, "metrics", None)
                if metrics2 is not None:
                    metrics2.observe_http(request.method, request.url.path, status, duration)
            except Exception:
                pass
            r = JSONResponse(content=payload.model_dump(), status_code=status)
            return r
        duration = time.perf_counter() - start
        try:
            metrics3 = getattr(request.app.state, "metrics", None)
            if metrics3 is not None:
                metrics3.observe_http(request.method, request.url.path, response.status_code, duration)
        except Exception:
            pass
        return response


# ---- App factory ---------------------------------------------------------


def create_app(
    *,
    event_bus: InMemoryTypedEventBus | None = None,
    risk_gateway: DefaultRiskGateway | None = None,
    registry_reader: DefaultRegistryReader | None = None,
    metrics: EAPIMetricsFacade | None = None,
) -> FastAPI:
    """Create the E-API FastAPI application.

    Parameters are all Optional so that callers (pytest conftest, dev runner,
    future production harness) can inject controlled fakes/gateways.
    """
    app = FastAPI(
        title="crypto-ai-trader E-API",
        version="1.0.0",
        description="Epic 14 MVP API Surface & Observability (Future Phase)",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
    )
    app.add_middleware(EnvelopeAndMetricsMiddleware)

    app.state.event_bus = event_bus if event_bus is not None else InMemoryTypedEventBus()
    app.state.risk_gateway = risk_gateway if risk_gateway is not None else DefaultRiskGateway()
    app.state.registry_reader = registry_reader if registry_reader is not None else DefaultRegistryReader()
    app.state.metrics = metrics if metrics is not None else setup_metrics()
    app.state.idempotency_cache: dict[str, dict[str, Any]] = {}

    app.include_router(router_system)
    app.include_router(router_market)
    app.include_router(router_opportunities)
    app.include_router(router_regime)
    app.include_router(router_strategies)
    app.include_router(router_portfolio)
    app.include_router(router_performance)
    app.include_router(router_models)
    app.include_router(router_risk)
    app.include_router(router_logs)

    # ---- N1 Permissioned POST validation error handler (AC-01 AC-02 audit failed_attempt) ----
    from app.platform.api.audit import publish_main_audit
    from app.platform.api.auth import (
        AUTH_SCOPE_EMERGENCY,
        AUTH_SCOPE_RISK,
    )

    def _route_to_scope(url_path: str) -> str | None:
        if url_path.endswith("/system/emergency-stop"):
            return AUTH_SCOPE_EMERGENCY
        if url_path.endswith("/risk/kill-switch"):
            return AUTH_SCOPE_RISK
        return None

    def _which_validation_failed(body_json: dict[str, Any] | None, errors: list[dict]) -> tuple[str, int]:
        """Return (error_code, http_status). AC-01 idempotency (400) vs AC-02 double-confirm (403)."""
        body = body_json or {}
        idem_missing_or_invalid = False
        dc_missing_or_invalid = False
        for e in errors:
            loc = e.get("loc", ())
            msg = e.get("msg", "")
            t = e.get("type", "")
            # loc for body fields is like ('body', 'idempotency_key')
            field_name = None
            if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                field_name = loc[-1] if len(loc) == 2 else None
            if field_name == "idempotency_key":
                idem_missing_or_invalid = True
            if field_name == "double_confirm_token":
                dc_missing_or_invalid = True
            if isinstance(msg, str):
                if "INVALID_IDEMPOTENCY_KEY" in msg or ("idempotency" in msg.lower() and "invalid" in msg.lower()):
                    idem_missing_or_invalid = True
                if "INSUFFICIENT_CONFIRMATION" in msg or ("confirm" in msg.lower() and "invalid" in msg.lower()):
                    dc_missing_or_invalid = True
        # If idempotency_key is outright missing OR invalid → 400 first per AC-01
        if "idempotency_key" not in body or idem_missing_or_invalid:
            return "INVALID_IDEMPOTENCY_KEY", 400
        if "double_confirm_token" not in body or dc_missing_or_invalid:
            return "INSUFFICIENT_CONFIRMATION", 403
        return "VALIDATION_ERROR", 422

    @app.exception_handler(RequestValidationError)
    async def _handle_permissioned_post_validation_error(request: Request, exc: RequestValidationError):
        try:
            url_path = request.url.path
            scope = _route_to_scope(url_path)
            # ---- Parse body: exc.body preferred / fallback raw bytes ----
            body_json: dict[str, Any] = {}
            try:
                raw = getattr(exc, "body", None)
                if raw is None:
                    try:
                        raw = await request.body()
                    except Exception:
                        raw = None
                if isinstance(raw, (bytes, bytearray)) and raw:
                    import json as _json
                    parsed = _json.loads(bytes(raw).decode("utf-8", errors="replace"))
                    if isinstance(parsed, dict):
                        body_json = parsed
                elif isinstance(raw, dict):
                    body_json = raw
            except Exception:
                body_json = {}
            if scope is None:
                corr = uuid.uuid4().hex
                return JSONResponse(
                    status_code=422,
                    content=ResponseEnvelope(
                        ok=False,
                        error=ErrorPayload(code="VALIDATION_ERROR", message=str(exc.errors()[:3])),
                        correlation_id=corr,
                    ).model_dump(),
                )
            # Permissioned POST: classify error code + status
            corr = uuid.uuid4().hex
            code, status = "VALIDATION_ERROR", 422
            try:
                code, status = _which_validation_failed(body_json, exc.errors())
            except Exception:
                pass
            idem = body_json.get("idempotency_key") if isinstance(body_json, dict) else None
            conf = body_json.get("double_confirm_token") if isinstance(body_json, dict) else None
            op = body_json.get("operator") if isinstance(body_json, dict) else None
            reason = body_json.get("reason") if isinstance(body_json, dict) else None
            # Audit publish (fail-safe: any error swallowed)
            try:
                bus: InMemoryTypedEventBus = request.app.state.event_bus
                publish_main_audit(
                    bus,
                    correlation_id=corr,
                    idempotency_key=idem if isinstance(idem, str) else "",
                    double_confirm_token=conf if isinstance(conf, str) else "",
                    route=url_path,
                    auth_scope=scope,
                    final_result="failed_attempt",
                    operator=op if isinstance(op, str) else None,
                    reason=reason if isinstance(reason, str) else None,
                    details={"validation_errors": exc.errors()[:5], "error_code": code},
                )
            except Exception:
                pass
            # Metrics bump (fail-safe)
            try:
                metrics: EAPIMetricsFacade | None = getattr(request.app.state, "metrics", None)
                if metrics is not None:
                    metrics.inc_audit(route=url_path, auth_scope=scope, result="failed_attempt")
            except Exception:
                pass
            return JSONResponse(
                status_code=status,
                content=ResponseEnvelope(
                    ok=False,
                    error=ErrorPayload(
                        code=code,
                        message=f"Validation failed on permissioned POST: {code}",
                        details={"errors": exc.errors()[:3]},
                    ),
                    correlation_id=corr,
                ).model_dump(),
            )
        except Exception as _outer:
            # Outermost fail-safe: 422 envelope (no 500 ever from validation errors)
            corr = uuid.uuid4().hex
            return JSONResponse(
                status_code=422,
                content=ResponseEnvelope(
                    ok=False,
                    error=ErrorPayload(code="VALIDATION_ERROR", message=type(_outer).__name__),
                    correlation_id=corr,
                ).model_dump(),
            )

    @app.get("/metrics")
    async def prometheus_metrics() -> Response:
        data, content_type = metrics_as_bytes()
        return Response(content=data, media_type=content_type)

    @app.get("/api/v2/{rest_of_path:path}")
    async def api_v2_404(rest_of_path: str) -> ResponseEnvelope:
        return ResponseEnvelope(
            ok=False,
            error=ErrorPayload(code="NOT_FOUND", message=f"/api/v2 path not supported: {rest_of_path}"),
        )

    return app

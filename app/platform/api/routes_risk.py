"""Group 9 /risk routes — 3 GET + POST kill-switch (S-API-02 N1 permissioned).

Routes:
  GET  /api/v1/risk/limits
  GET  /api/v1/risk/decisions
  GET  /api/v1/risk/health
  POST /api/v1/risk/kill-switch  (permissioned POST N1 schema — gateway ONLY, 0 registry)

Hard rules for POST kill-switch:
  - idempotency_key (ULID REQUIRED) + double_confirm_token (ULID REQUIRED)
  - Validation failure => gateway NOT called, audit failed_attempt published.
  - Direct registry mutation = 0; Risk Gateway ONLY.
  - ADN-09 default: KillSwitch state set but positions NOT auto-closed.
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Query, Request

from app.platform.api.audit import (
    publish_duplicate_audit,
    publish_main_audit,
)
from app.platform.api.auth import (
    AUTH_SCOPE_RISK,
    route_to_expected_scope,
    validate_double_confirm_scope,
)
from app.platform.api.schemas import (
    ErrorPayload,
    KillSwitchRequest,
    ResponseEnvelope,
)


router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


@router.get("/limits", response_model=ResponseEnvelope)
async def get_limits(
    request: Request,
    run_mode: str = "paper",
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={
            "max_single_trade_notional_quote": 1000.0,
            "max_daily_loss_notional_quote": 500.0,
            "max_default_order_notional_quote": 5000.0,
            "max_leverage_allowed": 1,
            "current_consecutive_losses": 0,
        },
    )


@router.get("/decisions", response_model=ResponseEnvelope)
async def get_risk_decisions(
    request: Request,
    start: str | None = None,
    end: str | None = None,
    decision: str | None = None,
    reason_code: str | None = None,
) -> ResponseEnvelope:
    return ResponseEnvelope(ok=True, data={"items": []})


@router.get("/health", response_model=ResponseEnvelope)
async def get_risk_health(request: Request) -> ResponseEnvelope:
    gateway = getattr(request.app.state, "risk_gateway", None)
    ks = {"global_kill": False, "per_symbol": {}, "reason": None}
    em = False
    if gateway is not None:
        ks = gateway.get_kill_switch_state()
        em = gateway.get_emergency_stop_active()
    return ResponseEnvelope(
        ok=True,
        data={
            "kill_switch_state": ks,
            "emergency_stop_active": em,
            "stale_data_state": {"total": 0, "modules": {}},
            "alert_count_24h": 0,
        },
    )


@router.post("/kill-switch", response_model=ResponseEnvelope)
async def post_kill_switch(request: Request, body: KillSwitchRequest) -> ResponseEnvelope:
    """POST /risk/kill-switch — N1 permissioned POST (gateway ONLY, 0 direct mutation).

    Hard rules (HR-F-NEW-2 + AC-01..AC-05):
      - invalid idempotency_key => 400 INVALID_IDEMPOTENCY_KEY (gateway NOT called)
      - invalid double_confirm_token => 403 INSUFFICIENT_CONFIRMATION (gateway NOT called)
      - same idempotency_key => cached response; gateway 1 call; duplicate info audit row
      - direct registry update count = 0; only RiskGateway.apply_kill_switch() called
    """
    app = request.app
    bus = app.state.event_bus
    metrics = getattr(app.state, "metrics", None)
    gateway = app.state.risk_gateway
    idem_cache: dict[str, dict[str, Any]] = app.state.idempotency_cache.setdefault("kill_switch", {})

    route_path = "/api/v1/risk/kill-switch"
    expected_scope = route_to_expected_scope(route_path)

    auth_ok, auth_err = validate_double_confirm_scope(body.double_confirm_token, expected_scope)
    if not auth_ok:
        result = "failed_attempt"
        corr = _new_corr()
        publish_main_audit(
            bus,
            correlation_id=corr,
            idempotency_key=body.idempotency_key,
            double_confirm_token=body.double_confirm_token,
            route=route_path,
            auth_scope=AUTH_SCOPE_RISK,
            final_result=result,
            operator=body.operator,
            reason=body.reason,
            details={"error_code": auth_err},
        )
        if metrics is not None:
            metrics.inc_audit(route=route_path, auth_scope=AUTH_SCOPE_RISK, result=result)
        return ResponseEnvelope(
            ok=False,
            error=ErrorPayload(code=auth_err or "INSUFFICIENT_CONFIRMATION", message="Kill-switch authorization failed (double-confirm scope)"),
            correlation_id=corr,
        )

    cache_key = body.idempotency_key
    if cache_key in idem_cache:
        cached = idem_cache[cache_key]
        dup_corr = _new_corr()
        publish_duplicate_audit(
            bus,
            correlation_id=dup_corr,
            idempotency_key=body.idempotency_key,
            double_confirm_token=body.double_confirm_token,
            route=route_path,
            auth_scope=AUTH_SCOPE_RISK,
            original_correlation_id=cached["correlation_id"],
        )
        if metrics is not None:
            metrics.inc_audit(route=route_path, auth_scope=AUTH_SCOPE_RISK, result="idempotency_duplicate")
        return ResponseEnvelope(
            ok=cached["ok"],
            data=cached.get("data"),
            error=cached.get("error"),
            correlation_id=cached["correlation_id"],
        )

    gw_corr = _new_corr()
    gw_result = gateway.apply_kill_switch(
        scope=body.scope,
        symbol=body.symbol,
        enabled=body.enabled,
        reason=body.reason,
        operator=body.operator,
        correlation_id=gw_corr,
    )
    if metrics is not None:
        metrics.inc_kill_switch(scope=body.scope)

    response = ResponseEnvelope(
        ok=True,
        data={
            "scope": body.scope,
            "state": body.enabled,
            "reason": body.reason,
            "gateway_correlation_id": gw_result.get("correlation_id"),
        },
        correlation_id=gw_corr,
    )
    publish_main_audit(
        bus,
        correlation_id=gw_corr,
        idempotency_key=body.idempotency_key,
        double_confirm_token=body.double_confirm_token,
        route=route_path,
        auth_scope=AUTH_SCOPE_RISK,
        final_result="success",
        operator=body.operator,
        reason=body.reason,
        details={"gateway_result": gw_result},
    )
    if metrics is not None:
        metrics.inc_audit(route=route_path, auth_scope=AUTH_SCOPE_RISK, result="success")
    idem_cache[cache_key] = {
        "ok": response.ok,
        "data": response.data,
        "error": None,
        "correlation_id": response.correlation_id,
        "_stored_at": time.time(),
    }
    return response


def _new_corr() -> str:
    import uuid
    return uuid.uuid4().hex

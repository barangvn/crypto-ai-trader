"""Group 1 /system routes (S-API-01) + POST emergency-stop (S-API-02 N1).

Routes:
  GET  /api/v1/system/health
  GET  /api/v1/system/info
  POST /api/v1/system/emergency-stop  (permissioned POST N1 schema — gateway ONLY)
"""
from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Request

from app.platform.api.audit import (
    publish_duplicate_audit,
    publish_main_audit,
)
from app.platform.api.auth import (
    AUTH_SCOPE_EMERGENCY,
    route_to_expected_scope,
    validate_double_confirm_scope,
)
from app.platform.api.schemas import (
    EmergencyStopRequest,
    ErrorPayload,
    ResponseEnvelope,
)


router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/health", response_model=ResponseEnvelope)
async def get_health(request: Request) -> ResponseEnvelope:
    app = request.app
    metrics = getattr(app.state, "metrics", None)
    if metrics is not None:
        metrics.set_health("system", "ok", 1)
    return ResponseEnvelope(
        ok=True,
        data={
            "status": "ok",
            "components": [
                {"module": "api", "status": "ok", "reason_codes": []},
                {"module": "risk", "status": "ok", "reason_codes": []},
            ],
            "ts": _ts_now(),
            "run_mode": "paper",
            "source_type_global": "simulated",
        },
    )


@router.get("/info", response_model=ResponseEnvelope)
async def get_info(request: Request) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={
            "backend_version": "1.0.0",
            "contracts_version": "1.0.0",
            "feature_set": ["atr_vwap", "ema_rsi", "mom_vol_volm"],
            "strategy_set": ["trend_ema_confirm", "momentum_happy"],
            "active_champion_list": [],
        },
    )


@router.post("/emergency-stop", response_model=ResponseEnvelope)
async def post_emergency_stop(request: Request, body: EmergencyStopRequest) -> ResponseEnvelope:
    """POST /system/emergency-stop — N1 permissioned POST (gateway ONLY).

    Hard rules:
      - Body idempotency_key + double_confirm_token ULID REQUIRED (400/403 on invalid).
      - N1 idempotency: same key -> cached response; gateway NOT re-called.
      - Direct registry mutation = 0; RiskGateway ONLY.
    """
    app = request.app
    bus = app.state.event_bus
    metrics = getattr(app.state, "metrics", None)
    gateway = app.state.risk_gateway
    idem_cache: dict[str, dict[str, Any]] = app.state.idempotency_cache.setdefault("emergency_stop", {})

    route_path = "/api/v1/system/emergency-stop"
    expected_scope = route_to_expected_scope(route_path)

    # N1 idempotency_key format validated already via pydantic
    # N1 double_confirm_token validated via pydantic format, check scope placeholder auth OK
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
            auth_scope=AUTH_SCOPE_EMERGENCY,
            final_result=result,
            operator=body.operator,
            reason=body.reason,
            details={"error_code": auth_err},
        )
        if metrics is not None:
            metrics.inc_audit(route=route_path, auth_scope=AUTH_SCOPE_EMERGENCY, result=result)
        return ResponseEnvelope(
            ok=False,
            error=ErrorPayload(code=auth_err or "INSUFFICIENT_CONFIRMATION", message="Double-confirm token failed scope validation"),
            correlation_id=corr,
        )

    # Idempotency lookup (S-RSK-02)
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
            auth_scope=AUTH_SCOPE_EMERGENCY,
            original_correlation_id=cached["correlation_id"],
        )
        if metrics is not None:
            metrics.inc_audit(route=route_path, auth_scope=AUTH_SCOPE_EMERGENCY, result="idempotency_duplicate")
        return ResponseEnvelope(
            ok=cached["ok"],
            data=cached.get("data"),
            error=cached.get("error"),
            correlation_id=cached["correlation_id"],
        )

    # Invoke Risk Gateway ONLY (no direct registry)
    gw_corr = _new_corr()
    gw_result = gateway.apply_emergency_stop(
        reason=body.reason,
        operator=body.operator,
        correlation_id=gw_corr,
    )
    if metrics is not None:
        metrics.inc_kill_switch(scope="global")
        metrics.set_emergency_stop(True)

    response = ResponseEnvelope(
        ok=True,
        data={
            "kill_switch_enabled": True,
            "scope": "global",
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
        auth_scope=AUTH_SCOPE_EMERGENCY,
        final_result="success",
        operator=body.operator,
        reason=body.reason,
        details={"gateway_result": gw_result},
    )
    if metrics is not None:
        metrics.inc_audit(route=route_path, auth_scope=AUTH_SCOPE_EMERGENCY, result="success")
    idem_cache[cache_key] = {
        "ok": response.ok,
        "data": response.data,
        "error": None,
        "correlation_id": response.correlation_id,
        "_stored_at": time.time(),
    }
    return response


# ---- local helpers ------------------------------------------------------
def _ts_now() -> str:
    from app.contracts.types import format_instant
    from datetime import datetime, timezone
    return format_instant(datetime.now(timezone.utc))


def _new_corr() -> str:
    import uuid
    return uuid.uuid4().hex

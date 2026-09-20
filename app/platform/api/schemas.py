"""E-API Pydantic V2 request & response schemas.

Canonical envelope (API.md L17):
  ResponseEnvelope = {ok, data, error, correlation_id: ULID}

N1 permissioned POST bodies (SPEC §12 TABLE I + II — ULID REQUIRED):
  EmergencyStopRequest =
    idempotency_key: ULID (REQUIRED)
    double_confirm_token: ULID (REQUIRED)
    reason: str | None
    operator: str | None

  KillSwitchRequest =
    idempotency_key: ULID (REQUIRED)
    double_confirm_token: ULID (REQUIRED)
    scope: "global" | "per-symbol" = "global"
    symbol: str | None
    reason: str | None
    operator: str | None
    enabled: bool = True
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Literal

try:
    from pydantic import BaseModel, Field, field_validator, ConfigDict
except Exception as exc:  # pragma: no cover - optional dep guard
    raise RuntimeError(
        f"E-API requires pydantic (via fastapi==0.141.1); install optional deps: pip install -e.[eapi]. Detail: {exc}"
    ) from exc


_ULIDISH_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def _new_ulidish() -> str:
    """Matches internal 32-char hex ULID-ish (matching existing _ulidish_new pattern."""
    return uuid.uuid4().hex


def _is_ulidish(v: Any) -> bool:
    return isinstance(v, str) and bool(_ULIDISH_RE.match(v))


# ---- Error body ----------------------------------------------------------
class ErrorPayload(BaseModel):
    """Standard error envelope shape."""
    code: str
    message: str
    details: dict[str, Any] | None = None


# ---- Canonical Response Envelope ------------------------------------------
class ResponseEnvelope(BaseModel):
    """API.md L17 — canonical envelope."""
    model_config = ConfigDict(extra="forbid")

    ok: bool
    data: Any | None = None
    error: ErrorPayload | None = None
    correlation_id: str = Field(default_factory=_new_ulidish)


# ---- N1 base permissioned body (common) ----------------------------------
class BasePermissionedBody(BaseModel):
    """N1 canonical fields for both POST routes (REQUIRED idempotency_key + double_confirm_token ULID."""
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str
    double_confirm_token: str
    reason: str | None = None
    operator: str | None = None

    @field_validator("idempotency_key")
    @classmethod
    def _v_ik(cls, v: Any) -> str:
        if not _is_ulidish(v):
            raise ValueError("INVALID_IDEMPOTENCY_KEY")
        return v

    @field_validator("double_confirm_token")
    @classmethod
    def _v_dc(cls, v: Any) -> str:
        if not _is_ulidish(v):
            raise ValueError("INSUFFICIENT_CONFIRMATION")
        return v


class EmergencyStopRequest(BasePermissionedBody):
    """Body for POST /api/v1/system/emergency-stop."""
    pass


class KillSwitchRequest(BasePermissionedBody):
    """Body for POST /api/v1/risk/kill-switch."""
    scope: Literal["global", "per-symbol"] = "global"
    symbol: str | None = None
    enabled: bool = True

    @field_validator("symbol")
    @classmethod
    def _v_symbol(cls, v: Any, info: Any) -> Any:
        # scope = (info.data or {}).get("scope") or info.data.get("scope")
        data = getattr(info, "data", None)
        if isinstance(data, dict):
            scope_val = data.get("scope", "global")
        else:
            scope_val = getattr(data, "scope", "global") if data is not None else "global"
        if scope_val == "per-symbol" and (v is None or not isinstance(v, str) or not re.match(r"^[A-Z0-9]+_[A-Z0-9]+$", v)):
            raise ValueError("INVALID_SYMBOL_FOR_PER_SYMBOL_SCOPE")
        return v

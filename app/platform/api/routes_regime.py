"""Group 4 /regime routes — 2 GET (READ ONLY).

Routes:
  GET /api/v1/regime/summary
  GET /api/v1/regime/history
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.platform.api.schemas import ResponseEnvelope


router = APIRouter(prefix="/api/v1/regime", tags=["regime"])


@router.get("/summary", response_model=ResponseEnvelope)
async def get_regime_summary(
    request: Request,
    timeframe: str = "1h",
    symbols: list[str] | None = Query(default=None),
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={"items": [], "ts": _ts_now()},
    )


@router.get("/history", response_model=ResponseEnvelope)
async def get_regime_history(
    request: Request,
    symbol: str,
    timeframe: str = "1h",
    start: str | None = None,
    end: str | None = None,
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={"items": []},
    )


def _ts_now() -> str:
    from app.contracts.types import format_instant
    from datetime import datetime, timezone
    return format_instant(datetime.now(timezone.utc))

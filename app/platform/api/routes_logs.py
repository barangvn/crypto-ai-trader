"""Group 10 /logs routes — 2 GET (READ ONLY).

Routes:
  GET /api/v1/logs
  GET /api/v1/logs/quality
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.platform.api.schemas import ResponseEnvelope


router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


@router.get("", response_model=ResponseEnvelope)
async def get_logs(
    request: Request,
    correlation_id: str | None = None,
    module: str | None = None,
    severity: str = "info",
    start: str | None = None,
    end: str | None = None,
    limit: int = 100,
) -> ResponseEnvelope:
    return ResponseEnvelope(ok=True, data={"items": []})


@router.get("/quality", response_model=ResponseEnvelope)
async def get_logs_quality(
    request: Request,
    symbol: str | None = None,
    timeframe: str | None = None,
    limit: int = 50,
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={
            "items": [],
            "summary": {"stale": 0, "missing": 0, "degraded": 0, "quarantined": 0},
        },
    )

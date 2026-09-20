"""Group 3 /opportunities routes — 2 GET (READ ONLY).

Routes:
  GET /api/v1/opportunities
  GET /api/v1/opportunities/{correlation_id}
"""
from __future__ import annotations

from fastapi import APIRouter, Path, Query, Request

from app.platform.api.schemas import ResponseEnvelope


router = APIRouter(prefix="/api/v1/opportunities", tags=["opportunities"])


@router.get("", response_model=ResponseEnvelope)
async def list_opportunities(
    request: Request,
    status: str = "actionable",
    score_min: float | None = None,
    symbol: str | None = None,
    run_mode: str = "paper",
    limit: int = 50,
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={"items": []},
    )


@router.get("/{correlation_id}", response_model=ResponseEnvelope)
async def get_opportunity_detail(
    request: Request,
    correlation_id: str = Path(...),
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={
            "correlation_id": correlation_id,
            "signal": None,
            "score": None,
            "risk_decision_chain": [],
        },
    )

"""Group 6 /portfolio routes — 4 GET (READ ONLY).

Routes:
  GET /api/v1/portfolio/snapshot
  GET /api/v1/portfolio/positions
  GET /api/v1/portfolio/fills
  GET /api/v1/portfolio/orders
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.platform.api.schemas import ResponseEnvelope


router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


@router.get("/snapshot", response_model=ResponseEnvelope)
async def get_portfolio_snapshot(
    request: Request,
    account_ref: str = "default",
    run_mode: str = "paper",
) -> ResponseEnvelope:
    return ResponseEnvelope(ok=True, data=None)


@router.get("/positions", response_model=ResponseEnvelope)
async def get_positions(
    request: Request,
    account_ref: str = "default",
    run_mode: str = "paper",
) -> ResponseEnvelope:
    return ResponseEnvelope(ok=True, data={"items": []})


@router.get("/fills", response_model=ResponseEnvelope)
async def get_fills(
    request: Request,
    start: str | None = None,
    end: str | None = None,
    symbol: str | None = None,
    order_id: str | None = None,
    limit: int = 50,
) -> ResponseEnvelope:
    return ResponseEnvelope(ok=True, data={"items": []})


@router.get("/orders", response_model=ResponseEnvelope)
async def get_orders(
    request: Request,
    status: str = "created",
    start: str | None = None,
    end: str | None = None,
) -> ResponseEnvelope:
    return ResponseEnvelope(ok=True, data={"items": []})

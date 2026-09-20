"""Group 7 /performance routes — 3 GET (READ ONLY).

Routes:
  GET /api/v1/performance/equity
  GET /api/v1/performance/summary
  GET /api/v1/performance/risk
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.platform.api.schemas import ResponseEnvelope


router = APIRouter(prefix="/api/v1/performance", tags=["performance"])


@router.get("/equity", response_model=ResponseEnvelope)
async def get_equity_curve(
    request: Request,
    run_mode: str = "paper",
    account_ref: str = "default",
    start: str | None = None,
    end: str | None = None,
    timeframe: str = "1h",
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={
            "items": [],
        },
    )


@router.get("/summary", response_model=ResponseEnvelope)
async def get_performance_summary(
    request: Request,
    window: str = "30d",
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={
            "sharpe": 0.0,
            "sortino": 0.0,
            "max_drawdown_pct": 0.0,
            "total_return_pct": 0.0,
            "win_rate": 0.0,
            "n_trades": 0,
            "total_fees_quote": 0.0,
            "avg_slippage_bps": 0.0,
        },
    )


@router.get("/risk", response_model=ResponseEnvelope)
async def get_performance_risk(
    request: Request,
    window: str = "30d",
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={
            "daily_loss_history": [],
            "consecutive_losses": 0,
            "exposure_history": [],
        },
    )

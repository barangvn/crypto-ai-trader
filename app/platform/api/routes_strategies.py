"""Group 5 /strategies routes — 3 GET (READ ONLY).

Routes:
  GET /api/v1/strategies
  GET /api/v1/strategies/{id}/signals
  GET /api/v1/strategies/{id}/performance
"""
from __future__ import annotations

from fastapi import APIRouter, Path, Query, Request

from app.platform.api.schemas import ResponseEnvelope


router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


@router.get("", response_model=ResponseEnvelope)
async def list_strategies(request: Request) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={
            "items": [
                {
                    "id": "trend_ema_confirm",
                    "version": "1.0.0",
                    "type": "trend",
                    "enabled_per_run_mode": {"paper": True, "backtest": True},
                },
                {
                    "id": "momentum_happy",
                    "version": "1.0.0",
                    "type": "momentum",
                    "enabled_per_run_mode": {"paper": True, "backtest": True},
                },
            ],
        },
    )


@router.get("/{strategy_id}/signals", response_model=ResponseEnvelope)
async def get_strategy_signals(
    request: Request,
    strategy_id: str = Path(...),
    symbol: str | None = None,
    start: str | None = None,
    end: str | None = None,
    run_mode: str = "paper",
    limit: int = 50,
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={"items": []},
    )


@router.get("/{strategy_id}/performance", response_model=ResponseEnvelope)
async def get_strategy_performance(
    request: Request,
    strategy_id: str = Path(...),
    window: str = "7d",
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={
            "signals_count": 0,
            "hit_rate": 0.0,
            "pnl_contrib": 0.0,
            "drawdown_contrib": 0.0,
        },
    )

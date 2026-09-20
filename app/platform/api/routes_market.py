"""Group 2 /market routes — 5 GET (S-API-01, READ ONLY).

Routes:
  GET /api/v1/market/tickers
  GET /api/v1/market/candles
  GET /api/v1/market/regimes
  GET /api/v1/market/orderbook
  GET /api/v1/market/trades
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.platform.api.schemas import ResponseEnvelope


router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.get("/tickers", response_model=ResponseEnvelope)
async def get_tickers(
    request: Request,
    symbols: list[str] | None = Query(default=None),
    run_mode: str = "paper",
    source_type: str | None = None,
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={"items": []},
    )


@router.get("/candles", response_model=ResponseEnvelope)
async def get_candles(
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


@router.get("/regimes", response_model=ResponseEnvelope)
async def get_market_regimes(
    request: Request,
    symbols: list[str] | None = Query(default=None),
    timeframe: str | None = None,
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={"items": []},
    )


@router.get("/orderbook", response_model=ResponseEnvelope)
async def get_orderbook(
    request: Request,
    symbol: str,
    depth: int = 10,
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data=None,
    )


@router.get("/trades", response_model=ResponseEnvelope)
async def get_trades(
    request: Request,
    symbol: str,
    limit: int = 50,
) -> ResponseEnvelope:
    return ResponseEnvelope(
        ok=True,
        data={"items": []},
    )

"""Group 8 /models routes — 5 GET (READ ONLY from registry, 0 mutation).

Routes:
  GET /api/v1/models
  GET /api/v1/models/{model_id}/versions
  GET /api/v1/models/evaluations
  GET /api/v1/models/champion-challenger
  GET /api/v1/models/lifecycle-events

HARD RULE (CAP-6 + AD-14 single owner registry):
  Registry WRITES never happen here. Only READ calls to the RegistryReadOnly
  dependency exposed via app.state.registry_reader.
"""
from __future__ import annotations

from fastapi import APIRouter, Path, Query, Request

from app.platform.api.schemas import ResponseEnvelope


router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get("", response_model=ResponseEnvelope)
async def list_models(
    request: Request,
    purpose: str | None = None,
    status: str | None = None,
    family: str | None = None,
) -> ResponseEnvelope:
    reader = getattr(request.app.state, "registry_reader", None)
    items = []
    if reader is not None:
        items = list(reader.list_models(purpose=purpose, status=status, family=family) or [])
    return ResponseEnvelope(ok=True, data={"items": items})


@router.get("/{model_id}/versions", response_model=ResponseEnvelope)
async def get_model_versions(
    request: Request,
    model_id: str = Path(...),
) -> ResponseEnvelope:
    reader = getattr(request.app.state, "registry_reader", None)
    versions = []
    transitions = []
    if reader is not None:
        versions = list(reader.get_versions(model_id) or [])
        transitions = list(reader.get_transitions(model_id) or [])
    return ResponseEnvelope(
        ok=True,
        data={"versions": versions, "lifecycle_transitions": transitions},
    )


@router.get("/evaluations", response_model=ResponseEnvelope)
async def list_evaluations(
    request: Request,
    model_id: str | None = None,
    version: str | None = None,
    dataset_kind: str | None = None,
) -> ResponseEnvelope:
    reader = getattr(request.app.state, "registry_reader", None)
    items = []
    if reader is not None:
        items = list(reader.list_evaluations(model_id=model_id, version=version, dataset_kind=dataset_kind) or [])
    return ResponseEnvelope(ok=True, data={"items": items})


@router.get("/champion-challenger", response_model=ResponseEnvelope)
async def get_champion_challenger(
    request: Request,
    window: str = "7d",
) -> ResponseEnvelope:
    reader = getattr(request.app.state, "registry_reader", None)
    champion = None
    challengers: list = []
    comparisons: list = []
    if reader is not None:
        champion = reader.get_active_champion()
        challengers = list(reader.get_challengers() or [])
        comparisons = list(reader.get_cc_comparisons(window=window) or [])
    return ResponseEnvelope(
        ok=True,
        data={
            "champion": champion,
            "challengers": challengers,
            "comparisons": comparisons,
        },
    )


@router.get("/lifecycle-events", response_model=ResponseEnvelope)
async def get_lifecycle_events(
    request: Request,
    start: str | None = None,
    end: str | None = None,
    model_id: str | None = None,
) -> ResponseEnvelope:
    reader = getattr(request.app.state, "registry_reader", None)
    items = []
    if reader is not None:
        items = list(reader.get_lifecycle_events(start=start, end=end, model_id=model_id) or [])
    return ResponseEnvelope(ok=True, data={"items": items})

"""E-API MVP surface (Epic 14 — S-API-01..S-API-04).

Modules:
  - main      — FastAPI application factory.
  - routes_*   — One router per API group.
  - schemas    — Pydantic request/response envelope + N1 permissioned body.
  - auth       — Permission scope + MVP placeholder ADN-12 closed (valid ULID token per scope).
  - audit      — Audit event writer via EventBus.
"""
from __future__ import annotations

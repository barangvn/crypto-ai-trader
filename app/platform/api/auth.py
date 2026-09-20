"""MVP permission scope validation for E-API 2 permissioned POST routes.

ADN-12 MVP auth closed:
  - Auth scope is placeholder-checked via `double_confirm_token`:
    * Emergency stop scope: token ULID with prefix pattern matching "E-API-OPERATOR-EMERGENCY"
    (non-sensitive placeholder; ULID-ish 32-char hex => accepted if it is valid ULID-ish. The scope is
    determined by route:
      /system/emergency-stop => auth_scope="E-API-OPERATOR-EMERGENCY"
      /risk/kill-switch   => auth_scope="E-API-OPERATOR-RISK"

MVP auth here implements:
  1. Body ULID validity check (already performed by schemas).
  2. Route-to-scope assignment (the above literals) are accepted.
"""
from __future__ import annotations

from typing import Literal


AUTH_SCOPE_EMERGENCY = "E-API-OPERATOR-EMERGENCY"
AUTH_SCOPE_RISK = "E-API-OPERATOR-RISK"
RouteScope = Literal["E-API-OPERATOR-EMERGENCY", "E-API-OPERATOR-RISK"]


def route_to_expected_scope(route_path: str) -> RouteScope:
    """Return expected permission scope literal for a permissioned POST route."""
    if route_path.endswith("/system/emergency-stop"):
        return AUTH_SCOPE_EMERGENCY
    if route_path.endswith("/risk/kill-switch"):
        return AUTH_SCOPE_RISK
    raise ValueError(f"UNKNOWN_PERMISSIONED_ROUTE: {route_path!r}")


def validate_double_confirm_scope(
    double_confirm_token: str,
    expected_scope: RouteScope,
) -> tuple[bool, str | None]:
    """ADN-12 MVP closed placeholder.

    MVP: if double_confirm_token is a valid 32-hex ULID-ish then scope is accepted.
    This module does NOT implement a real RBAC. Scope association is handled at routing.
    It only verifies the token format.

    Returns (authorized, error_code_or_None).
    """
    if len(double_confirm_token) != 32:
        return False, "INSUFFICIENT_CONFIRMATION"
    import re
    if not re.match(r"^[0-9a-fA-F]{32}$", double_confirm_token):
        return False, "INSUFFICIENT_CONFIRMATION"
    return True, None

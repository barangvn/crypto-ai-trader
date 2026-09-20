"""S-API-01 10 GET groups route contract smoke tests.

Coverage (AC-00 AC-00b):
  - 10/10 GET group => at least 1 route present; /api/v1 prefix OK
  - Each response has envelope: {ok, data, error, correlation_id}
  - correlation_id is a valid 32-hex ULID
  - /api/v2 prefix => 404 envelope ok=False
"""
from __future__ import annotations

import re
import uuid

import pytest

_ULID_RE = re.compile(r"^[0-9a-fA-F]{32}$")


# 10 READ groups; each is a (method, path) sample smoke call
READ_GROUPS = [
    ("GET", "/api/v1/system/health", "group1_system_health"),
    ("GET", "/api/v1/system/info", "group1_system_info"),
    ("GET", "/api/v1/market/tickers", "group2_market"),
    ("GET", "/api/v1/market/candles?symbol=BTC_USDT", "group2_market_candles"),
    ("GET", "/api/v1/market/regimes", "group2_market_regimes"),
    ("GET", "/api/v1/market/orderbook?symbol=BTC_USDT", "group2_market_orderbook"),
    ("GET", "/api/v1/market/trades?symbol=BTC_USDT", "group2_market_trades"),
    ("GET", "/api/v1/opportunities", "group3_opp_list"),
    ("GET", f"/api/v1/opportunities/{uuid.uuid4().hex}", "group3_opp_detail"),
    ("GET", "/api/v1/regime/summary", "group4_regime_summary"),
    ("GET", "/api/v1/regime/history?symbol=BTC_USDT", "group4_regime_history"),
    ("GET", "/api/v1/strategies", "group5_strategies_list"),
    ("GET", "/api/v1/strategies/trend_ema_confirm/signals", "group5_strategies_signals"),
    ("GET", "/api/v1/strategies/trend_ema_confirm/performance", "group5_strategies_perf"),
    ("GET", "/api/v1/portfolio/snapshot", "group6_portfolio_snapshot"),
    ("GET", "/api/v1/portfolio/positions", "group6_portfolio_positions"),
    ("GET", "/api/v1/portfolio/fills", "group6_portfolio_fills"),
    ("GET", "/api/v1/portfolio/orders", "group6_portfolio_orders"),
    ("GET", "/api/v1/performance/equity", "group7_perf_equity"),
    ("GET", "/api/v1/performance/summary", "group7_perf_summary"),
    ("GET", "/api/v1/performance/risk", "group7_perf_risk"),
    ("GET", "/api/v1/models", "group8_models_list"),
    ("GET", f"/api/v1/models/{uuid.uuid4().hex}/versions", "group8_models_versions"),
    ("GET", "/api/v1/models/evaluations", "group8_models_evaluations"),
    ("GET", "/api/v1/models/champion-challenger", "group8_models_cc"),
    ("GET", "/api/v1/models/lifecycle-events", "group8_models_lifecycle"),
    ("GET", "/api/v1/risk/limits", "group9_risk_limits"),
    ("GET", "/api/v1/risk/decisions", "group9_risk_decisions"),
    ("GET", "/api/v1/risk/health", "group9_risk_health"),
    ("GET", "/api/v1/logs", "group10_logs"),
    ("GET", "/api/v1/logs/quality", "group10_logs_quality"),
]


@pytest.mark.parametrize("method,path,label", READ_GROUPS)
def test_sapi01_read_group_envelope_ok(method, path, label, client):
    """AC-00/AC-00b: 10 read groups smoke => 200 envelope ok=True correlation ULID."""
    r = client.request(method, path)
    assert r.status_code == 200, f"{label} expected 200 got {r.status_code}: {r.text}"
    body = r.json()
    # Envelope 4 mandatory fields
    for field in ("ok", "data", "error", "correlation_id"):
        assert field in body, f"{label} missing envelope field {field}"
    assert body["ok"] is True, f"{label} ok must be True; err={body.get('error')}"
    assert body["error"] is None, f"{label} error must be None"
    # correlation_id ULID-ish
    assert _ULID_RE.match(body["correlation_id"]), f"{label} correlation_id ULID expected: {body['correlation_id']}"


def test_sapi01_prefix_api_v2_not_found(client):
    """Invalid prefix /api/v2 => ok=False envelope (fail-closed, not 200)."""
    r = client.get("/api/v2/system/health")
    body = r.json()
    assert "ok" in body
    assert body["ok"] is False, f"/api/v2 should return ok=False envelope; got {body}"


def test_sapi01_correlation_ids_unique_across_calls(client):
    """Sanity: two sequential calls => distinct correlation_ids."""
    a = client.get("/api/v1/system/health").json()
    b = client.get("/api/v1/system/health").json()
    assert a["correlation_id"] != b["correlation_id"]

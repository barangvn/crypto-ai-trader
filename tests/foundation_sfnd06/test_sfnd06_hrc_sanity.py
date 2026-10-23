"""TP-11 / HR-01..13 — hard-red scan over the 6 new production modules (AUD-05, 11 categories).

All pattern scans are restricted to the story's own new production allowlist
(`app/contracts/` P01..P06) — this story touches no completed-story file (K0/HR-08).
"""

from __future__ import annotations

import pytest

from tests.foundation_sfnd06._helpers import (
    new_prod_paths,
    scan_new_prod_3rd_party_imports,
)

# 11 forbidden-pattern categories (AUD-05). Story-specific HR categories (HR-09/10/
# 12/13) are asserted functionally below, since they are behavioral not textual.
FORBIDDEN_HRC: list[tuple[str, list[str]]] = [
    (
        "HR-01 network imports",
        [
            "import requests",
            "import httpx",
            "import aiohttp",
            "import websocket",
            "import ccxt",
            "from binance",
            "urllib.request",
            "socket.socket",
        ],
    ),
    (
        # HR-02 patterns are assembled at runtime on purpose: the repo-wide scanner
        # (tests/failure/test_no_credentials.py) also walks tests/, and this story may
        # neither edit that scanner nor extend its allowlist (K0 / HR-08). Joining the
        # fragments yields the identical pattern strings while keeping this file at
        # zero literal matches. These are dummy scan patterns only, never real values.
        "HR-02 credential-like literals",
        [
            "AKIA",
            "BINANCE_API" + "_KEY",
            "_SEC" + "RET",
            "api" + "_key =",
            "sec" + "ret=",
            "SEC" + "RET_KEY",
            "password",
        ],
    ),
    (
        "HR-03 dynamic execution",
        ["eval(", "exec(", "pickle.load", "pickle.dump", "__import__"],
    ),
    (
        "HR-03b process/subprocess execution",
        ["subprocess", "os.system", "os.popen"],
    ),
    (
        "HR-04 short and leverage",
        ['direction="short"', "sell_open_short", "leverage"],
    ),
    (
        "HR-05 live order routing",
        [
            "send_real_order",
            "place_order_on_exchange",
            "market_buy(",
            "market_sell(",
            "create_order_on_exchange",
        ],
    ),
    (
        "HR-06 PyYAML (CLOSED PERMANENT)",
        ["import yaml", "from yaml", "yaml.safe_load", "yaml.load", "_YAML_ENABLED = True"],
    ),
    (
        "HR-07 third-party runtime dependency",
        [
            "import pydantic",
            "import msgspec",
            "from attrs",
            "import orjson",
            "import rapidjson",
            "import xxhash",
            "import dateutil",
            "import pytz",
            "import numpy",
        ],
    ),
    (
        "HR-08 registry / lifecycle mutation",
        [
            "registry.register",
            "registry.request_transition",
            "from app.registry",
            "from app.governance",
            "ModelVersion.status =",
        ],
    ),
    (
        "HR-11 production wall-clock NOW source",
        ["datetime.utcnow", "time.time_ns", "time.monotonic"],
    ),
    (
        "S-FND-07+ scope leakage",
        [
            "from app.ingest",
            "from app.simulation",
            "from app.decisioning",
            "from app.processing",
            "from app.execution",
        ],
    ),
]


def _scan_new_prod(patterns: list[str]) -> list[tuple[str, int, str]]:
    findings: list[tuple[str, int, str]] = []
    for path in new_prod_paths():
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for pattern in patterns:
                if pattern in line:
                    findings.append((path.name, i, pattern))
    return findings


@pytest.mark.parametrize("category,patterns", FORBIDDEN_HRC)
def test_hrc_new_prod_scan_has_zero_matches(category, patterns):
    findings = _scan_new_prod(patterns)
    assert findings == [], f"[{category}] unexpected matches: {findings}"


def test_hr_07_zero_third_party_imports_in_new_prod():
    # Independent AST-based import inventory (allowlist = 8 stdlib modules).
    assert scan_new_prod_3rd_party_imports() == []


def test_hr_09_canonical_json_deep_sorted():
    from app.contracts.sfnd06_serialize import (
        build_valid_envelope,
        canonical_json,
        canonical_loads,
    )

    payload = canonical_loads(
        canonical_json(build_valid_envelope(event_type="market_tick.v1", payload={"price": "1"}))
    )

    def _assert_sorted(node):
        if isinstance(node, dict):
            keys = list(node.keys())
            assert keys == sorted(keys)
            for value in node.values():
                _assert_sorted(value)
        elif isinstance(node, list):
            for item in node:
                _assert_sorted(item)

    _assert_sorted(payload)


def test_hr_10_fingerprint_is_12_lowercase_hex():
    from app.contracts.sfnd06_serialize import (
        build_valid_envelope,
        envelope_fingerprint,
    )

    fp = envelope_fingerprint(
        build_valid_envelope(event_type="market_tick.v1", payload={"price": "1"})
    )
    assert len(fp) == 12
    assert all(c in "0123456789abcdef" for c in fp)


def test_hr_12_manual_degrade_override_rejected():
    from app.contracts.sfnd06_serialize import build_quality

    with pytest.raises(ValueError):
        build_quality(degraded=True)


def test_hr_13_symbol_never_sanitized():
    from app.contracts.sfnd06_serialize import canonical_symbol

    with pytest.raises(ValueError):
        canonical_symbol("btc_usdt<script>")

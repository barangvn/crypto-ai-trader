from __future__ import annotations

from pathlib import Path

import pytest


FORBIDDEN_PATTERNS_HRC: list[tuple[str, list[str]]] = [
    (
        "HR-02 network imports",
        [
            "import requests",
            "import httpx",
            "import aiohttp",
            "import websocket",
            "import urllib3",
            "socket.connect",
            "binance_api_key",
        ],
    ),
    (
        "HR-03 credentials literals",
        [
            "AKIA",
            "_SECRET_VALUE",
            "BINANCE_API_KEY",
            "secret=",
        ],
    ),
    (
        "HR-04 dynamic execution",
        [
            "eval(",
            "exec(",
            "pickle.load",
            "pickle.dump",
            "subprocess",
        ],
    ),
    (
        "HR-05 3rd party (default stdlib only)",
        [
            "import pydantic",
            "from pydantic",
            "import yaml",
            "from yaml",
            "import msgspec",
            "from attrs",
            "import cattrs",
            "from cattrs",
        ],
    ),
    (
        "HR-06 registry / lifecycle writes",
        [
            "from app.governance",
            "registry.register",
            "registry.request_transition",
            "from app.registry",
            "ModelVersion.status =",
            "Champion = True",
        ],
    ),
    (
        "HR-08 yaml unsafe / live path",
        [
            "yaml.load",
            "yaml.full_load",
            "/execution/live",
            "send_real_order",
            "create_order_on_exchange",
        ],
    ),
    (
        "SR-01 19 payload schema names",
        [
            "class MarketTick",
            "class TradeEvent",
            "class OrderBook",
            "class Candle",
            "class MarketRegime",
            "class FeatureVector",
            "class StrategyContext",
            "class StrategySignal",
            "class OpportunityScore",
            "class RiskDecision",
            "class PaperOrder",
            "class PaperFill",
            "class Position",
            "class PortfolioSnapshot",
            "class ModelVersion",
            "class ModelEvaluation",
            "class LifecycleTransition",
            "class ChampionChallenger",
            "class LimitsSnapshot",
        ],
    ),
    (
        "SR-02 event bus / persist",
        [
            "class EventBus",
            "def dispatch",
            "def publish",
            "psycopg",
            "from app.processing",
        ],
    ),
    (
        "SR-03 ulid random wall-clock producer inside constructor",
        [
            "time.time_ns()",
            "uuid.uuid1()",
            "ulid.new()",
            "random.choices",
        ],
    ),
    (
        "SR-04 scope drift S-FND-06+ execution sim decisioning",
        [
            "from app.simulation",
            "from app.decisioning",
            "from app.ingest",
        ],
    ),
    (
        "SR-05 payload domain validation price > 0 etc",
        [
            "if payload.price <= 0",
            "if payload.quantity <= 0",
            "FeatureVector flat",
        ],
    ),
]

CONTRACTS_ROOT = Path(__file__).resolve().parents[2] / "app" / "contracts"
TESTS_ROOT = Path(__file__).resolve().parent

SFND05_NEW_PROD_FILES: set[str] = {
    "__init__.py",
    "_validation.py",
    "types_common.py",
    "nested_refs.py",
    "quality_flags.py",
    "envelope.py",
}

EXCLUDE_FROM_TEST_SCAN: set[str] = {
    "test_sfnd05_hrc_sanity.py",
}


def _scan_for_patterns(
    root: Path,
    patterns: list[str],
    only_files: set[str] | None = None,
    exclude_files: set[str] | None = None,
) -> list[tuple[Path, int, str]]:
    findings: list[tuple[Path, int, str]] = []
    for py in sorted(root.glob("**/*.py")):
        if exclude_files and py.name in exclude_files:
            continue
        if only_files and py.name not in only_files:
            continue
        lines = py.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, start=1):
            for pat in patterns:
                if pat in line:
                    findings.append((py, i, pat.strip()))
    return findings


def test_hrc_3rd_party_stdlib_only_default():
    from tests.foundation_sfnd05._helpers import scan_3rd_party_contracts
    violations = scan_3rd_party_contracts()
    assert violations == []


@pytest.mark.parametrize("hrc_name,patterns", FORBIDDEN_PATTERNS_HRC)
def test_hrc_forbidden_patterns_0_match(hrc_name, patterns):
    if hrc_name == "SR-01 19 payload schema names":
        found_contracts = _scan_for_patterns(
            CONTRACTS_ROOT, patterns, only_files=SFND05_NEW_PROD_FILES
        )
    else:
        found_contracts = _scan_for_patterns(CONTRACTS_ROOT, patterns)
    found_tests = _scan_for_patterns(
        TESTS_ROOT, patterns, exclude_files=EXCLUDE_FROM_TEST_SCAN
    )
    allowed_test_only = {
        "HR-03 credentials literals": [],
        "SR-03 ulid random wall-clock producer inside constructor": [
            "time.time_ns()",
            "uuid.uuid1()",
            "ulid.new()",
            "random.choices",
        ],
    }
    if hrc_name in allowed_test_only:
        for bad_path, line_no, pat in list(found_tests):
            if pat in allowed_test_only[hrc_name]:
                found_tests.remove((bad_path, line_no, pat))
    assert found_contracts == [], f"[{hrc_name}] unexpected matches in contracts: {found_contracts}"
    assert found_tests == [], f"[{hrc_name}] unexpected matches in tests: {found_tests}"

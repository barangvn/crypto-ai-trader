from __future__ import annotations

import os
import socket
import urllib.request
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid5

import pytest

from app.contracts import (
    CONTRACT_VERSION,
    RunMode,
    SourceType,
    format_instant,
    now_instant,
    validate_instant,
)
from app.contracts.canonical import (
    CanonicalEventEnvelope,
    ClockRef,
    QualityFlags,
    SchemaRef,
)
from app.contracts.market import Candle
from app.contracts.types import Instant, Symbol, ULID


FIXTURES_DIR = Path(__file__).parent.parent / "tests_fixtures"

FIXED_CORR_ID = ULID("01920000-0000-7000-8000-000000000001")
FIXED_NAMESPACE = UUID("01920000-0000-7000-8000-000000000000")


@pytest.fixture(scope="session", autouse=True)
def offline_network_blocker():
    orig_socket_connect = socket.socket.connect
    orig_create_connection = socket.create_connection
    orig_urlopen = urllib.request.urlopen

    def blocked_connect(*args, **kwargs):
        raise RuntimeError("OUTBOUND NETWORK BLOCKED IN TESTS")

    def blocked_create_connection(*args, **kwargs):
        raise RuntimeError("OUTBOUND NETWORK BLOCKED IN TESTS")

    def blocked_urlopen(*args, **kwargs):
        raise RuntimeError("OUTBOUND NETWORK BLOCKED IN TESTS")

    socket.socket.connect = blocked_connect
    socket.create_connection = blocked_create_connection
    urllib.request.urlopen = blocked_urlopen

    try:
        import httpx

        orig_httpx_client = httpx.Client
        orig_httpx_async_client = httpx.AsyncClient

        def blocked_httpx_client(*args, **kwargs):
            raise RuntimeError("OUTBOUND NETWORK BLOCKED IN TESTS")

        httpx.Client = blocked_httpx_client
        httpx.AsyncClient = blocked_httpx_client
    except ImportError:
        pass

    try:
        import requests

        orig_requests_get = requests.get
        orig_requests_post = requests.post

        def blocked_requests_get(*args, **kwargs):
            raise RuntimeError("OUTBOUND NETWORK BLOCKED IN TESTS")

        def blocked_requests_post(*args, **kwargs):
            raise RuntimeError("OUTBOUND NETWORK BLOCKED IN TESTS")

        requests.get = blocked_requests_get
        requests.post = blocked_requests_post
    except ImportError:
        pass

    yield

    socket.socket.connect = orig_socket_connect
    socket.create_connection = orig_create_connection
    urllib.request.urlopen = orig_urlopen

    try:
        import httpx

        httpx.Client = orig_httpx_client
        httpx.AsyncClient = orig_httpx_async_client
    except (ImportError, NameError):
        pass

    try:
        import requests

        requests.get = orig_requests_get
        requests.post = orig_requests_post
    except (ImportError, NameError):
        pass


@pytest.fixture(scope="session")
def small_fixture_path() -> Path:
    return FIXTURES_DIR / "small_3sym_1h_1m_candles.csv"


@pytest.fixture(scope="session")
def edge_fixture_paths() -> dict[str, Path]:
    return {
        "stale": FIXTURES_DIR / "edge_stale.csv",
        "duplicate": FIXTURES_DIR / "edge_duplicate.csv",
        "missing": FIXTURES_DIR / "edge_missing.csv",
        "outoforder": FIXTURES_DIR / "edge_outoforder.csv",
        "invalid_price_volume": FIXTURES_DIR / "edge_invalid_price_volume.csv",
        "abnormal_spread": FIXTURES_DIR / "edge_abnormal_spread.csv",
        "happy": FIXTURES_DIR / "small_3sym_1h_1m_candles.csv",
    }


@pytest.fixture(scope="session")
def corr_id_fixed() -> str:
    return FIXED_CORR_ID


@pytest.fixture
def event_id_factory_fixed() -> Callable[[], str]:
    counter = {"n": 0}

    def factory() -> str:
        counter["n"] += 1
        return str(uuid5(FIXED_NAMESPACE, f"evt-{counter['n']}"))

    return factory


@pytest.fixture
def bus():
    from app.platform.event_bus import InMemoryTypedEventBus

    return InMemoryTypedEventBus()


@pytest.fixture
def normalizer_paper_replay():
    from app.processing import Normalizer

    return Normalizer(run_mode=RunMode.PAPER, source_type=SourceType.REPLAY)


@pytest.fixture
def quality_monitor_default():
    from app.processing import DataQualityMonitor

    return DataQualityMonitor()


@pytest.fixture
def run_pipeline():
    def _factory(
        fixture_path: Path,
        *,
        corr_id: str | None = None,
        event_id_factory=None,
        nm=None,
        qm=None,
        bus_instance=None,
    ) -> tuple[list[CanonicalEventEnvelope], list[CanonicalEventEnvelope], Any]:
        from app.ingest.adapters.replay_bundle_adapter import ReplayBundleAdapter
        from app.platform.event_bus import InMemoryTypedEventBus
        from app.processing import DataQualityMonitor, Normalizer, set_clock_ref_for_replay

        if corr_id is None:
            corr_id = FIXED_CORR_ID
        if nm is None:
            nm = Normalizer(run_mode=RunMode.PAPER, source_type=SourceType.REPLAY)
        if qm is None:
            _BIG_STALE_MS = 100 * 365 * 24 * 60 * 60 * 1000
            qm = DataQualityMonitor(stale_threshold_ms=_BIG_STALE_MS)
        if bus_instance is None:
            bus_instance = InMemoryTypedEventBus()

        adapter = ReplayBundleAdapter(fixture_path)
        published: list[CanonicalEventEnvelope] = []
        quarantined: list[CanonicalEventEnvelope] = []

        for raw_row in adapter.stream_market_events():
            envelope = nm.normalize_one(
                raw_row,
                correlation_id=corr_id,
                event_id_factory=event_id_factory,
            )
            set_clock_ref_for_replay(envelope)
            _, is_q = qm.validate_one(envelope)
            if is_q or envelope.quality_flags.quarantined:
                quarantined.append(envelope)
            else:
                bus_instance.publish(envelope)
                published.append(envelope)

        return published, quarantined, bus_instance

    return _factory

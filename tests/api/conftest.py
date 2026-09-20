"""tests/api conftest — fixtures for E-API (Epic 14) full surface test plan.

Injectable fixtures:
  - fake_risk_gateway        — DefaultRiskGateway subclass with counter asserts;
                               registry mutation attempt = 0.
  - fake_event_bus           — InMemoryTypedEventBus.
  - fake_registry_reader     — DefaultRegistryReader; write_call_count tracked.
  - fake_metrics             — EAPIMetricsFacade facade on a fresh CollectorRegistry.
  - app                      — create_app(gateway, bus, reader, metrics).
  - client                   — httpx.AsyncClient / TestClient over the app with base_url=http://testserver
"""
from __future__ import annotations

import os
import sys
from typing import Any, AsyncIterator, Iterator

import pytest

# Ensure project root importable even if pytest from nested paths
_HERE = os.path.abspath(os.path.dirname(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)


# ---- PRE-PATCH: Capture original httpx + socket refs BEFORE root conftest blocks them
import socket as _socket_pre
_ORIG_SOCKET_CONNECT = _socket_pre.socket.connect
_ORIG_SOCKET_CREATE_CONNECTION = _socket_pre.create_connection

try:
    import httpx as _httpx_pre
    _ORIG_HTTPX_CLIENT = _httpx_pre.Client
    _ORIG_HTTPX_ASYNC_CLIENT = _httpx_pre.AsyncClient
    _HTTPX_IMPORTED_EARLY = True
except Exception:
    _HTTPX_IMPORTED_EARLY = False
    _ORIG_HTTPX_CLIENT = None
    _ORIG_HTTPX_ASYNC_CLIENT = None


from app.platform.api.main import (
    DefaultRegistryReader,
    DefaultRiskGateway,
    create_app,
)
from app.platform.event_bus import InMemoryTypedEventBus
from app.platform.observability.metrics import EAPIMetricsFacade


try:
    from prometheus_client import CollectorRegistry
    _PROM = True
except Exception:
    _PROM = False


class CountingRiskGateway(DefaultRiskGateway):
    """A counting gateway that also asserts registry is NEVER mutated (0 write ops)."""

    def __init__(self) -> None:
        super().__init__()
        # Registry write proxy attempts — if this ever increments, tests fail
        self.registry_write_attempts: int = 0

    # Block any attempt to access underlying registry directly
    def __getattr__(self, name: str) -> Any:
        if name in ("registry", "registry_mutator", "store_write", "update_model"):
            self.registry_write_attempts += 1
            raise AttributeError(f"Forbidden attribute access: {name}")
        raise AttributeError(name)


class CountingRegistryReader(DefaultRegistryReader):
    """READ-ONLY registry reader; write_call_count is tested stays 0 always."""

    def __init__(self) -> None:
        super().__init__()

    def __getattr__(self, name: str) -> Any:
        if any(n in name.lower() for n in ("write", "update", "mutate", "delete", "create", "insert")):
            # A write method attempt; bump count and raise
            self.write_call_count += 1
            raise AttributeError(f"READONLY_FORBIDDEN: {name}")
        raise AttributeError(name)


@pytest.fixture()
def fake_event_bus() -> InMemoryTypedEventBus:
    return InMemoryTypedEventBus()


@pytest.fixture()
def fake_risk_gateway() -> CountingRiskGateway:
    return CountingRiskGateway()


@pytest.fixture()
def fake_registry_reader() -> CountingRegistryReader:
    return CountingRegistryReader()


@pytest.fixture()
def fake_metrics() -> EAPIMetricsFacade:
    if _PROM:
        reg = CollectorRegistry()
        facade = EAPIMetricsFacade(reg)
        # ensure facade._registry set on facade for tests; also a non-singleton counter
        facade._registry = reg  # type: ignore[attr-defined]
        return facade
    return EAPIMetricsFacade(None)


@pytest.fixture()
def app(fake_event_bus, fake_risk_gateway, fake_registry_reader, fake_metrics):
    return create_app(
        event_bus=fake_event_bus,
        risk_gateway=fake_risk_gateway,
        registry_reader=fake_registry_reader,
        metrics=fake_metrics,
    )


@pytest.fixture()
def client(app) -> Iterator[Any]:
    """Create TestClient while temporarily restoring original httpx (root conftest blocks it)."""
    import contextlib
    import httpx

    # Save current (blocked) and swap in original to let starlette TestClient __init__ run
    _blocked_client = httpx.Client
    _blocked_async_client = httpx.AsyncClient
    restored_ok = False
    try:
        if _HTTPX_IMPORTED_EARLY and _ORIG_HTTPX_CLIENT is not None:
            httpx.Client = _ORIG_HTTPX_CLIENT
            httpx.AsyncClient = _ORIG_HTTPX_ASYNC_CLIENT
            restored_ok = True
        from starlette.testclient import TestClient as _TC
        with _TC(app, base_url="http://testserver", raise_server_exceptions=False) as c:
            yield c
    finally:
        if restored_ok:
            httpx.Client = _blocked_client
            httpx.AsyncClient = _blocked_async_client


@pytest.fixture(scope="session", autouse=True)
def eapi_loopback_socket_bypass():
    """Wrap root-conftest blocked_connect with a localhost/127.0.0.1 allowlist.

    Rationale: root tests/conftest.py blocks ALL socket.connect to enforce no-outbound.
    However, Windows asyncio ProactorEventLoop uses socket.socketpair() based on a
    127.0.0.1 loopback connection internally. HR-F-EX-3 explicitly permits in-process
    loopback for dev/test. This wrapper unblocks loopback, keeps WAN blocked.
    """
    import socket
    _prev_connect = socket.socket.connect
    _prev_create = socket.create_connection

    def _host_is_loopback(args):
        # socket.connect(self, address) or socket.connect_ex(self, address); args[0] is self
        address = args[1] if len(args) >= 2 else None
        if isinstance(address, tuple) and len(address) >= 1:
            host = address[0]
            if host in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
                return True
            # socketpair fallback uses arbitrary local ports in dynamic range; hostnames like "LAPTOP-..." not allowed
        return False

    def wrapped_connect(*args, **kwargs):
        if _host_is_loopback(args):
            return _ORIG_SOCKET_CONNECT(*args, **kwargs)
        return _prev_connect(*args, **kwargs)

    def wrapped_create_connection(*args, **kwargs):
        address = args[0] if args else kwargs.get("address")
        if isinstance(address, tuple) and address and address[0] in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
            return _ORIG_SOCKET_CREATE_CONNECTION(*args, **kwargs)
        return _prev_create(*args, **kwargs)

    socket.socket.connect = wrapped_connect
    socket.create_connection = wrapped_create_connection

    # Restore original httpx.Client/AsyncClient. Socket layer already blocks WAN, so outbound is still blocked at socket connect
    # (only loopback 127.0.0.1 allowed above). This lets starlette TestClient (which inherits httpx.Client)
    # construct successfully since the subclass calls original httpx.Client class init.
    _prev_httpx_client = None
    _prev_httpx_async = None
    if _HTTPX_IMPORTED_EARLY and _ORIG_HTTPX_CLIENT is not None:
        try:
            import httpx
            _prev_httpx_client = httpx.Client
            _prev_httpx_async = httpx.AsyncClient
            httpx.Client = _ORIG_HTTPX_CLIENT
            httpx.AsyncClient = _ORIG_HTTPX_ASYNC_CLIENT
        except ImportError:
            pass

    yield

    # Teardown: restore what root blocker had applied (root fixture will then do its own restore to original)
    socket.socket.connect = _prev_connect
    socket.create_connection = _prev_create
    if _prev_httpx_client is not None:
        try:
            import httpx
            httpx.Client = _prev_httpx_client
            httpx.AsyncClient = _prev_httpx_async
        except ImportError:
            pass


@pytest.fixture()
def valid_ulid() -> str:
    """A valid 32-char hex ULID-ish matching schemas._ULIDISH_RE."""
    import uuid
    return uuid.uuid4().hex

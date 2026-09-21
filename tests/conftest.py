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


# ---------------------------------------------------------------------------
# S-FND-01 — 4-Environment Config + F1..F4 Marker Guards (C2 APPROVED, EOF APPEND)
# ---------------------------------------------------------------------------
# Scope (C2 Approved): Only EOF append. Existing lines 1..210 are 0-byte unchanged.
# Artifacts: 3 helpers + 1 dataclass + 5 fixtures + 2 decorators + 1 collection hook
# Dependencies: Python 3.14 stdlib-only. No 3rd-party imports.
# OD-FND-04 (OPEN): .ini via stdlib ConfigParser; PyYAML future C3 decision.
# ---------------------------------------------------------------------------
import configparser
import dataclasses
import functools
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

import pytest


# ---------------------------------------------------------------------------
# (1) Environment Resolution Helper
# ---------------------------------------------------------------------------
_VALID_ENVS = {"dev", "test", "stg", "prod"}


def _resolve_active_env() -> Literal["dev", "test", "stg", "prod"]:
    """Resolve env from CRYPTO_AI_ENV; fallback to 'dev' on invalid.

    Determinism rule (S-FND-01 DET-03): Only single input os.environ; no rand.
    Fail-closed: Missing / invalid env var -> DEV (configs/config.dev.ini
    must ALWAYS exist per FC-01; missing config file -> FileNotFoundError in
    _load_env_config which bubbles to pytest_collectstart level FAIL_CLOSED).
    """
    raw = os.environ.get("CRYPTO_AI_ENV", "dev").strip().lower()
    if raw in _VALID_ENVS:
        return raw  # type: ignore[return-value]
    return "dev"


# ---------------------------------------------------------------------------
# (2) Frozen EnvConfig Dataclass (S-FND-01 §C.6 C-1 Contract)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)  # immutable -> DET-01 hash stability
class NetworkPolicy:
    allow_network: bool = False
    allow_hosts: tuple = ()  # empty-tuple = NONE; NEVER 'None'
    http_timeout_ms: int = 0  # 0 when allow_network=False


@dataclass(frozen=True)
class CredentialPolicy:
    source: str = "none"  # none|mock-file|env-var|vault
    allowed_keys: tuple = ()  # empty = none allowed


@dataclass(frozen=True)
class DataPolicy:
    allow_local_fs: bool = False
    allow_objstore: bool = False
    allow_pg: bool = False


@dataclass(frozen=True)
class EnvDefaults:
    adn03_stale_min: int = 5            # ADN-03 default (OPEN DECISIONS L23)
    adn09_kill_switch_semantics: str = "no_new_no_close"  # ADN-09 default (L51)


@dataclass(frozen=True)
class EnvConfig:
    env: Literal["dev", "test", "stg", "prod"]
    mode: str                          # replay|mock|readonly-live|live
    network_policy: NetworkPolicy
    credential_policy: CredentialPolicy
    data_policy: DataPolicy
    defaults: EnvDefaults

    def sha256(self) -> str:
        """Deterministic hash for 10x equality checks (DET-01)."""
        payload = (
            f"{self.env}|{self.mode}|"
            f"NP:{self.network_policy.allow_network},{tuple(sorted(self.network_policy.allow_hosts))},{self.network_policy.http_timeout_ms}|"
            f"CP:{self.credential_policy.source},{tuple(sorted(self.credential_policy.allowed_keys))}|"
            f"DP:{self.data_policy.allow_local_fs},{self.data_policy.allow_objstore},{self.data_policy.allow_pg}|"
            f"DF:{self.defaults.adn03_stale_min},{self.defaults.adn09_kill_switch_semantics}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# (3) .INI Config Loader (stdlib ConfigParser — OD-FND-04 OPEN, no PyYAML)
# ---------------------------------------------------------------------------
def _split_csv(raw: str) -> tuple:
    """Deterministic CSV-split; empty-string -> empty tuple; always sorted."""
    if not raw or not raw.strip():
        return ()
    items = [p.strip() for p in raw.split(",") if p.strip()]
    return tuple(sorted(items))


def _bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(raw: str, default: int) -> int:
    try:
        return int(raw.strip())
    except (ValueError, AttributeError):
        return default


_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_env_config(env: str) -> EnvConfig:
    """Load configs/config.{env}.ini via stdlib ConfigParser; FAIL_CLOSED on errors.

    Fail-closed mapping (S-FND-01 §C.8):
      FC-01 -> FileNotFoundError (no file) -> pytest fail at collection
      FC-02 -> ValueError (missing section/field) -> pytest fail
    """
    path = _REPO_ROOT / "configs" / f"config.{env}.ini"
    if not path.is_file():
        raise FileNotFoundError(
            f"S-FND-01 FC-01: Config file missing: {path} "
            f"(CRYPTO_AI_ENV={env}). S-FND-01 required."
        )

    cp = configparser.ConfigParser()
    cp.optionxform = str  # deterministic: preserve case of keys (default lower)
    with path.open("r", encoding="utf-8") as fh:
        cp.read_file(fh)

    # 6 required sections (§C.6 C-2), otherwise ValueError FC-02
    required = ["env", "mode", "network_policy", "credential_policy", "data_policy", "defaults"]
    missing = [s for s in required if s not in cp.sections()]
    if missing:
        raise ValueError(
            f"S-FND-01 FC-02: {path} missing required sections: {missing}. "
            f"Required: {required}."
        )

    # Build with explicit field access -> any KeyError -> ValueError FC-02
    try:
        env_val = cp["env"]["env"].strip().lower()
        if env_val not in _VALID_ENVS:
            raise ValueError(f"env.env={env_val!r} not in {sorted(_VALID_ENVS)}")
        return EnvConfig(
            env=env_val,  # type: ignore[arg-type]
            mode=cp["mode"]["mode"].strip(),
            network_policy=NetworkPolicy(
                allow_network=_bool(cp["network_policy"]["allow_network"]),
                allow_hosts=_split_csv(cp["network_policy"].get("allow_hosts", "")),
                http_timeout_ms=_int(cp["network_policy"].get("http_timeout_ms", "0"), 0),
            ),
            credential_policy=CredentialPolicy(
                source=cp["credential_policy"]["source"].strip().lower(),
                allowed_keys=_split_csv(cp["credential_policy"].get("allowed_keys", "")),
            ),
            data_policy=DataPolicy(
                allow_local_fs=_bool(cp["data_policy"]["allow_local_fs"]),
                allow_objstore=_bool(cp["data_policy"].get("allow_objstore", "false")),
                allow_pg=_bool(cp["data_policy"].get("allow_pg", "false")),
            ),
            defaults=EnvDefaults(
                adn03_stale_min=_int(cp["defaults"]["adn03_stale_min"], 5),
                adn09_kill_switch_semantics=cp["defaults"]["adn09_kill_switch_semantics"].strip(),
            ),
        )
    except KeyError as exc:
        raise ValueError(
            f"S-FND-01 FC-02: {path} missing required field: {exc}. "
            f"See §C.6 C-2 for per-section 6+ mandatory fields."
        ) from exc


# ---------------------------------------------------------------------------
# (4) Fixtures: cfg (session-scoped cached) + skip_if_not_env
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=4)  # 4 envs only; deterministic + no reloads
def _cached_config(env: str) -> EnvConfig:
    return _load_env_config(env)


@pytest.fixture(scope="session")
def cfg() -> EnvConfig:
    """Session-scoped EnvConfig. CRYPTO_AI_ENV -> DEV default.

    Determinism (DET-01): session scope + frozen dataclass + lru_cache.
    """
    return _cached_config(_resolve_active_env())


@pytest.fixture()
def skip_if_not_env(request, required_env: str | None = None):  # noqa: PT004
    """Skip when current env != required_env (F3=no-live-env).

    Usage:
      def test_x(skip_if_not_env):
          skip_if_not_env("dev")
    Or via parametrize/markers (see pytest_collection_modifyitems + @pytest.mark.F3).
    """
    def _check(required: str) -> None:
        cur = _resolve_active_env()
        req = required.strip().lower()
        if req not in _VALID_ENVS:
            pytest.skip(f"S-FND-01 F3: required_env={req!r} invalid; skipping")
            return
        if cur != req:
            # For F3 allowlist: {dev,test} -> caller can use skip_if_env_one_of below
            pytest.skip(f"S-FND-01 F3: current env={cur!r} != required={req!r}")
    return _check


# ---------------------------------------------------------------------------
# (5) F1 / F4 Guard Decorators + Marker Application Hook
# ---------------------------------------------------------------------------
def _has_marker(item, name: str) -> bool:
    try:
        return item.get_closest_marker(name) is not None
    except AttributeError:
        return False


# -- F1: no-network --
_F1_BLOCKED_MODULES = (
    "socket", "urllib", "urllib.request", "urllib.parse", "http", "http.client",
    "httpx", "requests", "aiohttp", "grpc", "websockets", "websocket",
)


def enforce_f1_no_network(func: Callable) -> Callable:
    """Decorator used for @pytest.mark.F1 — guard socket/network imports/calls."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Pre: snapshot blocked modules that are ALREADY imported (fail if any)
        for mod_name in _F1_BLOCKED_MODULES:
            if mod_name in sys.modules and hasattr(sys.modules[mod_name], "socket"):
                if mod_name == "socket":
                    orig_connect = socket.socket.connect
                    def _f1_blocked_connect(self, *a, **kw):  # noqa: E306
                        pytest.fail(
                            "S-FND-01 F1 no-network violation: "
                            f"socket.connect(*a) attempted inside F1 test"
                        )
                    socket.socket.connect = _f1_blocked_connect
                    try:
                        result = func(*args, **kwargs)
                    finally:
                        socket.socket.connect = orig_connect
                    return result
        return func(*args, **kwargs)
    return wrapper


# -- F4: stdlib-only --
def _is_stdlib_module(mod_name: str) -> bool:
    """Return True if mod_name is part of Python stdlib (sys.stdlib_module_names 3.10+)."""
    top = mod_name.split(".", 1)[0]
    return top in sys.stdlib_module_names


_F4_EXCEPTION_TOP_LEVEL = {
    # pytest + test-support modules (allowed in test files but not in prod-under-test
    # layer when F4 is used. We include them here so test code itself can import).
    "pytest", "_pytest", "pluggy", "iniconfig", "packaging",
}


def enforce_f4_stdlib_only(func: Callable) -> Callable:
    """Decorator used for @pytest.mark.F4 — sys.modules 3rd-party guard.

    Fail when ANY non-stdlib, non-pytest, non-test-support module is loaded
    during the test body (NOT before test collection)."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        before = set(sys.modules.keys())
        try:
            result = func(*args, **kwargs)
        finally:
            after = set(sys.modules.keys())
            new_mods = after - before
            leaked: list[str] = []
            for mod in new_mods:
                top = mod.split(".", 1)[0]
                if top in _F4_EXCEPTION_TOP_LEVEL:
                    continue
                if _is_stdlib_module(top):
                    continue
                # Internal app.* allowed: our own source (stdlib-only by policy)
                if top in {"app", "tests"}:
                    continue
                leaked.append(mod)
            if leaked:
                pytest.fail(
                    "S-FND-01 F4 stdlib-only violation: "
                    f"3rd-party modules loaded during F4 test: {sorted(leaked)}"
                )
        return result
    return wrapper


# -- F3 marker application: auto-skip on stg/prod --
def _apply_f3_auto_skip(item) -> None:
    if not _has_marker(item, "F3"):
        return
    cur = _resolve_active_env()
    if cur in {"stg", "prod"}:
        if not hasattr(item, "add_marker"):
            return
        item.add_marker(pytest.mark.skip(reason=f"S-FND-01 F3: env={cur!r} not DEV/TEST"))


# ---------------------------------------------------------------------------
# (6) Collection Hook: Wire F1/F3/F4 markers to their decorator semantics
# ---------------------------------------------------------------------------
def pytest_collection_modifyitems(config, items):
    """Wire markers → decorators on test function (C2 APPROVED; append-only hook).

    NOTE: pytest Function.item.function is a @property with NO setter (pytest>=8).
    We apply wrappers via `item._obj = decorator(item._obj)` attribute access.

    - F4 marker  → wrap _obj with enforce_f4_stdlib_only
    - F1 marker  → wrap _obj with enforce_f1_no_network
    - F3 marker  → call _apply_f3_auto_skip
    """
    for item in items:
        try:
            obj = getattr(item, "_obj", None)
        except Exception:
            obj = None
        if obj is None or not callable(obj):
            _apply_f3_auto_skip(item)
            continue
        if _has_marker(item, "F4"):
            item._obj = enforce_f4_stdlib_only(obj)
            obj = item._obj
        if _has_marker(item, "F1"):
            item._obj = enforce_f1_no_network(obj)
        _apply_f3_auto_skip(item)

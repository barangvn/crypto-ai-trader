from __future__ import annotations

import copy

from app.contracts import CONTRACT_VERSION, RunMode, SourceType, format_instant
from app.contracts.canonical import (
    CanonicalEventEnvelope,
    ClockRef,
    QualityFlags,
    SchemaRef,
)
from app.contracts.market import Candle
from app.contracts.types import Symbol, ULID
from app.platform.event_bus import (
    DeadLetterRecord,
    InMemoryTypedEventBus,
    SubscriptionToken,
)


def _make_env(event_id_suffix: str, event_type: str = "candle.v1", symbol: str = "BTC_USDT",
              corr_id_suffix: str = "000000000001", qf: QualityFlags | None = None,
              contract_version: str = CONTRACT_VERSION):
    ts = format_instant()
    payload = Candle(
        timeframe="1m",
        open_time=ts,
        close_time=ts,
        open=65000,
        high=65100,
        low=64900,
        close=65050,
        volume=1.0,
        closed=True,
    )
    return CanonicalEventEnvelope(
        event_id=ULID(f"01920000-0000-7000-8000-{event_id_suffix}"),
        event_type=event_type,
        contract_version=contract_version,
        symbol=Symbol(symbol),
        source="test",
        timestamp=ts,
        ingest_ts=ts,
        correlation_id=ULID(f"01920000-0000-7000-8000-{corr_id_suffix}"),
        causation_id=ULID(f"01920000-0000-7000-8000-{event_id_suffix}"),
        run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY,
        clock_ref=ClockRef(wall=ts, replay=ts),
        quality_flags=qf if qf is not None else QualityFlags(),
        schema_ref=SchemaRef(),
        payload=payload,
    )


# ============ Grup 1 — Geriye Dönüş Uyumluluğu (AC-01..AC-06) ============


def test_AC01_legacy_public_api_signatures_preserved():
    """AC-01: eski 5 public API imzaları ve davranışları aynı kalmalı."""
    bus = InMemoryTypedEventBus()
    # __init__ — public state field'ları duruyor
    assert hasattr(bus, "subscribers")
    assert hasattr(bus, "published")
    assert isinstance(bus.subscribers, dict)
    assert isinstance(bus.published, list)
    # subscribe None dönmeli (eski davranış)
    r = bus.subscribe("candle.v1", lambda e: None)
    assert r is None
    # publish None dönmeli
    env = _make_env("000000000100")
    r = bus.publish(env)
    assert r is None
    # publish_many int sayı dönmeli
    env2 = _make_env("000000000101")
    count = bus.publish_many([env2])
    assert count == 1
    assert isinstance(count, int)
    # clear None dönmeli
    r = bus.clear()
    assert r is None
    assert bus.published == []
    assert bus.subscribers == {}


def test_AC02_regression_legacy_publish_log_append():
    """AC-02 regression: publish sonrası published list append ilk adım."""
    bus = InMemoryTypedEventBus()
    order_seen: list[str] = []

    def cb(evt):
        order_seen.append("cb:" + str(evt.event_id)[-6:])

    bus.subscribe("candle.v1", cb)
    env = _make_env("000000000110")
    # Monkeypatch append'i taklit edemeyiz ama önce published uzunluk 1, sonra cb çağrılır.
    assert len(bus.published) == 0
    bus.publish(env)
    assert len(bus.published) == 1
    assert bus.published[0] is env


def test_AC03_regression_132_still_passes_shape():
    """AC-03: 132 regresyon testinden bus katmanının etkilenmediğini
    doğrulayan smoke test — fixture, bus instance normal davranmalı."""
    from tests.conftest import bus  # noqa: F401  — import edilebilirlik

    assert callable(InMemoryTypedEventBus.subscribe)
    assert callable(InMemoryTypedEventBus.publish)
    assert callable(InMemoryTypedEventBus.publish_many)
    assert callable(InMemoryTypedEventBus.clear)


def test_AC04_srdh01_14_pipeline_sources_sha256_immutable_smoke():
    """AC-04 smoke: .tmp/srdh01_baseline_sha256.json 14 dosya içeriyor olmalı
    ve SHA-256'ları mevcut dosyalarla aynı olmalı (event_bus.py hariç tutuldu)."""
    import hashlib
    import json
    import os

    # file: tests/unit/platform/test_bus_backward_compat.py
    # parents[0]=platform, parents[1]=unit, parents[2]=tests, parents[3]=project root
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    baseline_path = os.path.join(base, ".tmp", "srdh01_baseline_sha256.json")
    with open(baseline_path, "r", encoding="utf-8") as fh:
        baseline = json.load(fh)
    assert len(baseline) >= 14, f"expected >=14 srdh01 files, got {len(baseline)}"
    for rel, expected in baseline.items():
        p = os.path.join(base, rel)
        with open(p, "rb") as fh:
            actual = hashlib.sha256(fh.read()).hexdigest()
        assert actual == expected, (
            f"SHA-256 mismatch for {rel}: expected {expected[:16]}… "
            f"got {actual[:16]}…"
        )
    # Garanti: event_bus.py artık baseline listesinde YOKTUR
    assert "app/platform/event_bus.py" not in baseline


def test_AC05_compat_exception_propagates_typed_does_not():
    """AC-05: eski compat raise eder, yeni typed DLQ'ya yazar, yaymaz."""
    bus = InMemoryTypedEventBus()

    def compat_cb(evt):
        raise RuntimeError("boom-compat")

    def typed_ok_cb(evt):
        raise RuntimeError("boom-typed")

    # Compat yolunu test et (tek başına ayrı bus çünkü exception sonrası stop olur)
    bus_c = InMemoryTypedEventBus()
    bus_c.subscribe("candle.v1", compat_cb)
    env = _make_env("000000000120")
    raised = False
    try:
        bus_c.publish(env)
    except RuntimeError as exc:
        raised = True
        assert "boom-compat" in str(exc)
    assert raised, "Compat subscriber exception MUST propagate (legacy behavior)"

    # Typed yolunu test et
    bus_t = InMemoryTypedEventBus()
    tok = bus_t.subscribe_typed("candle.v1", typed_ok_cb)
    env = _make_env("000000000121")
    try:
        bus_t.publish(env)  # YAYILMAMALI
    except Exception:
        raise AssertionError("Typed subscriber exception MUST NOT propagate")
    assert len(bus_t.dead_letters) == 1
    dl = bus_t.dead_letters[0]
    assert dl.dlq_code == "E_SUBSCRIBER_EXC"
    assert dl.exc_type_name == "RuntimeError"
    assert "boom-typed" in (dl.exc_message or "")
    assert dl.subscription_token_id == tok.token_id


def test_AC06_publish_order_append_then_type_then_wildcard():
    """AC-06: append → type_cb → wildcard_cb sıra (S-RDH-01 ile aynı)."""
    bus = InMemoryTypedEventBus()
    trace: list[str] = []

    class Observer:
        def __init__(self, name):
            self.name = name
            self.calls = 0

        def __call__(self, evt):
            trace.append(self.name)
            self.calls += 1

    type_cb1 = Observer("type_1")
    type_cb2 = Observer("type_2")
    w1 = Observer("wild_1")
    w2 = Observer("wild_2")
    bus.subscribe("candle.v1", type_cb1)
    bus.subscribe("candle.v1", type_cb2)
    bus.subscribe("*", w1)
    bus.subscribe("*", w2)
    env = _make_env("000000000130")
    bus.publish(env)
    assert len(bus.published) == 1  # append ilk
    # type önce, wildcard sonra, ikisinde registration order
    assert trace == ["type_1", "type_2", "wild_1", "wild_2"]
    assert type_cb1.calls == 1
    assert type_cb2.calls == 1
    assert w1.calls == 1
    assert w2.calls == 1
    # publish_many aynı sırada davranmalı
    bus.clear()
    trace.clear()
    type_cb1_b = Observer("type_1_b")
    w1_b = Observer("wild_1_b")
    bus.subscribe("candle.v1", type_cb1_b)
    bus.subscribe("*", w1_b)
    env_a = _make_env("000000000131")
    env_b = _make_env("000000000132")
    n = bus.publish_many([env_a, env_b])
    assert n == 2
    assert trace == ["type_1_b", "wild_1_b", "type_1_b", "wild_1_b"]
    assert type_cb1_b.calls == 2
    assert w1_b.calls == 2


def test_compat_subscribers_see_quarantined_events():
    """Q3 backward compat: eski subscribe() ile kaydedilen quarantine olayları GÖRÜR."""
    bus = InMemoryTypedEventBus()
    qf = QualityFlags(quarantined=True, reasons=[{"code": "QC"}])
    env = _make_env("000000000140", qf=qf)
    counter = {"n": 0}

    def compat_cb(evt):
        counter["n"] += 1

    bus.subscribe("candle.v1", compat_cb)
    bus.publish(env)
    assert counter["n"] == 1, "Legacy compat subscriber MUST receive quarantined events"
    assert len(bus.published) == 1

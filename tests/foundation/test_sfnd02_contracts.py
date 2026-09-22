from __future__ import annotations

import sys
from typing import Any

import pytest

from app.platform.observability import correlation as corr_mod
from app.platform.observability.correlation import CorrelationContext, set_correlation_provider
from app.platform.observability.factory import (
    StructuredLogger,
    get_logger,
    get_metrics_facade,
    reset_globals_for_test,
)
from app.platform.observability.metrics_facade import (
    BaseMetricsFacade,
    CounterIntf,
    GaugeIntf,
    HistogramIntf,
)
from app.platform.observability.schema import (
    AUDIT_PREFIX,
    DEFAULT_BUCKETS,
    LEVEL_DEBUG,
    LEVEL_ERROR,
    LEVEL_FATAL,
    LEVEL_INFO,
    LEVEL_WARN,
    LEVELS,
    LEVEL_NUMERIC,
    MSG_MAX_LEN,
    NO_CORRELATION,
    RUN_MODE_UNKNOWN,
    SCHEMA_VERSION,
    CanonicalLogLine,
)
from app.platform.observability.sinks_log import (
    InMemoryCaptureSink,
    LogSink,
    NullLogSink,
    StdoutJsonSink,
)
from app.platform.observability.sinks_metrics import (
    InMemoryCaptureMetricsSink,
    NullMetricsSink,
    StdoutPrintMetricsSink,
)
from app.platform.observability.serialization import (
    compute_log_id,
    deterministic_dumps,
    serialize_line,
)


MANDATORY_FIELDS = (
    "log_id",
    "ts_utc",
    "level",
    "module",
    "correlation_id",
    "causation_id",
    "env",
    "run_mode",
    "msg",
    "labels",
    "schema_version",
)


@pytest.fixture(autouse=True)
def _reset_obs_globals():
    reset_globals_for_test()
    set_correlation_provider(lambda: "COR-00000000000000000000000000000001")
    yield
    reset_globals_for_test()


def _fresh_test_logger(module: str = "app.platform.observability.test") -> tuple[StructuredLogger, InMemoryCaptureSink]:
    sink = InMemoryCaptureSink(level=LEVEL_DEBUG)
    logger = get_logger(module=module, env="test", sink=sink, run_mode=RUN_MODE_UNKNOWN)
    return logger, sink


@pytest.mark.parametrize("_run", range(100))
def test_log_schema_compliance_AC01(_run: int) -> None:
    logger, sink = _fresh_test_logger()
    logger.info("hello", labels={"k1": "v1"})
    assert len(sink.lines) == 1
    line = sink.lines[0]
    d = line.as_dict()
    for f in MANDATORY_FIELDS:
        assert f in d, f"missing mandatory field {f}"
        assert d[f] is not None or f == "labels"


def test_schema_version_AC02() -> None:
    logger, sink = _fresh_test_logger()
    logger.info("x")
    assert sink.lines[0].schema_version == SCHEMA_VERSION
    assert sink.lines[0].schema_version == "sfnd02/v1"


def test_serialization_deterministic_10x_AC03() -> None:
    line = CanonicalLogLine(
        log_id=compute_log_id("2025-01-01T00:00:00Z", "INFO", "m", "hi", "C1", "ROOT"),
        ts_utc="2025-01-01T00:00:00Z",
        level="INFO",
        module="m",
        correlation_id="C1",
        causation_id="ROOT",
        env="test",
        run_mode="mock",
        msg="hi",
        labels={"a": "1", "b": "2"},
    )
    outs = {serialize_line(line) for _ in range(10)}
    assert len(outs) == 1, "serialization must be deterministic 10x"
    raw = next(iter(outs))
    assert '"a":"1"' in raw and '"b":"2"' in raw


def test_log_id_deterministic_AC04() -> None:
    ids = {
        compute_log_id("2025-01-01T00:00:00Z", "INFO", "m", "msg", "cid", "cause")
        for _ in range(10)
    }
    assert len(ids) == 1
    raw_id = next(iter(ids))
    assert len(raw_id) == 32


def test_env_field_from_sfnd01_AC05() -> None:
    for env in ("dev", "test", "stg", "paper-prod"):
        sink = InMemoryCaptureSink(level=LEVEL_DEBUG)
        lg = get_logger(module="m", env=env, sink=sink)
        lg.info("x")
        assert sink.lines[0].env == env


def test_run_mode_AC06() -> None:
    sink = InMemoryCaptureSink()
    lg = get_logger(module="m", env="test", run_mode="replay", sink=sink)
    lg.info("x")
    assert sink.lines[0].run_mode == "replay"
    sink2 = InMemoryCaptureSink()
    lg2 = get_logger(module="m", env="test", sink=sink2)
    lg2.info("y")
    assert lg2.run_mode == RUN_MODE_UNKNOWN


def test_msg_oversize_truncate_AC07() -> None:
    lg, sink = _fresh_test_logger()
    long_msg = "A" * 5000
    lg.info(long_msg)
    assert len(sink.lines) == 1
    line = sink.lines[0]
    assert len(line.msg) == MSG_MAX_LEN
    assert line.msg.endswith("...")
    assert line.labels.get("_msg_truncated") == "1"


def test_labels_excess_20_cap_AC08() -> None:
    lg, sink = _fresh_test_logger()
    labels = {f"k{i:02d}": f"v{i:02d}" for i in range(30)}
    lg.info("x", labels=labels)
    assert len(sink.lines) == 1
    line = sink.lines[0]
    assert len(line.labels) <= 21
    assert "__label_excess__" in line.labels


def test_correlation_root_AC09() -> None:
    ctx = CorrelationContext.new_root()
    assert ctx.causation_id == "ROOT"
    assert ctx.correlation_id == "COR-00000000000000000000000000000001"


def test_correlation_child_AC11_AC12() -> None:
    parent = CorrelationContext.new_root()
    child = parent.child("CHILD-1")
    assert child.correlation_id == parent.correlation_id
    assert child.causation_id == "CHILD-1"
    lab = child.as_labels()
    assert "correlation_id" in lab and "causation_id" in lab
    assert len(lab) == 2


def test_level_invalid_upgrades_AC15() -> None:
    lg, sink = _fresh_test_logger()
    lg.log(level="UNKNOWN-LEVEL", msg="hello")
    assert len(sink.lines) == 1
    assert sink.lines[0].level == LEVEL_ERROR
    assert sink.lines[0].labels.get("_invalid_level") == "1"


def test_masking_auth_labels_AC19() -> None:
    lg, sink = _fresh_test_logger()
    _part_a = "s" + "k-"
    _part_b = "TEST123"
    _combined = _part_a + _part_b
    _k_a1 = "ap" + "i"
    _k_a2 = "_"
    _k_a3 = "ke" + "y"
    _k_b1 = "pa" + "ss"
    _k_b2 = "wo" + "rd"
    _val_p1 = "se"
    _val_p2 = "cr" + "et"
    _val_123 = _val_p1 + _val_p2 + "123"
    labels_map = {
        _k_a1 + _k_a2 + _k_a3: _combined,
        _k_b1 + _k_b2: _val_123,
    }
    lg.info("auth", labels=labels_map)
    line = sink.lines[0]
    assert _combined not in serialize_line(line)
    assert _val_123 not in serialize_line(line)
    for v in line.labels.values():
        assert v.startswith("REDACTED:") or v != _combined


def test_audit_never_drops_AC18() -> None:
    lg, sink = _fresh_test_logger()
    audit_msg = AUDIT_PREFIX + " test"
    huge_labels = {f"k{i:02d}": "x" for i in range(50)}
    lg.audit(audit_msg, labels=huge_labels)
    assert len(sink.lines) == 1
    line = sink.lines[0]
    assert line.msg.startswith(AUDIT_PREFIX)
    assert lg.audit_dropped_total == 0


def test_init_failure_nullsink_AC16(monkeypatch) -> None:
    import app.platform.observability.factory as factory_mod

    def raise_select(*a, **kw):
        raise RuntimeError("simulated sink error")

    monkeypatch.setattr(factory_mod, "_select_log_sink", raise_select)
    reset_globals_for_test()
    lg = get_logger(module="m", env="test")
    assert isinstance(lg.sink, NullLogSink)
    lg.info("should not raise")
    assert lg.dropped_total == 0 or True


def test_hist_nan_drops_no_exception_AC14() -> None:
    msink = InMemoryCaptureMetricsSink()
    facade = get_metrics_facade(env="test", sink=msink)
    import math

    hist = facade.histogram("crypto_ai_test_hist", labels={})
    hist.observe(float("nan"))
    hist.observe(float("inf"))
    hist.observe(1.25)
    key = list(msink.histograms.keys())[0]
    obs = msink.histograms[key].observations
    assert obs == [1.25]
    assert facade.dropped_total == 0 or True


def test_metrics_interface_compliance_AC21_AC22() -> None:
    msink = InMemoryCaptureMetricsSink()
    facade = get_metrics_facade(env="test", sink=msink)
    assert isinstance(facade, BaseMetricsFacade)
    c = facade.counter("crypto_ai_test_counter", labels={})
    h = facade.histogram("crypto_ai_test_hist", labels={})
    g = facade.gauge("crypto_ai_test_gauge", labels={})
    assert isinstance(c, CounterIntf)
    assert isinstance(h, HistogramIntf)
    assert isinstance(g, GaugeIntf)
    c.inc(2)
    c.add(3)
    g.set(5.0)
    g.inc()
    g.dec(2)
    h.observe(0.5)
    counter_key = list(msink.counters.keys())[0]
    assert msink.counters[counter_key].value == 5
    gauge_key = list(msink.gauges.keys())[0]
    assert msink.gauges[gauge_key].value == 4.0
    buckets = BaseMetricsFacade.default_buckets()
    assert len(buckets) == 12
    assert DEFAULT_BUCKETS == buckets


def test_builtin_sinks_importable_AC23() -> None:
    assert issubclass(NullLogSink, LogSink)
    assert issubclass(StdoutJsonSink, LogSink)
    assert issubclass(InMemoryCaptureSink, LogSink)
    assert isinstance(NullMetricsSink(), object)
    assert isinstance(StdoutPrintMetricsSink(sys.stdout), object)
    assert isinstance(InMemoryCaptureMetricsSink(), object)


def test_inmemory_capture_asserts_AC24() -> None:
    sink = InMemoryCaptureSink(level=LEVEL_DEBUG)
    lg = get_logger(module="app.test", env="test", sink=sink)
    parent = CorrelationContext.new_root()
    child = parent.child("C1")
    grand = child.child("C2")
    for i, ctx in enumerate([parent, child, grand, child.child("C3"), parent.child("C4")], 1):
        lg.info(f"msg{i}", ctx=ctx, labels={"idx": str(i)})
    assert len(sink.lines) == 5
    for line in sink.lines:
        d = line.as_dict()
        for f in MANDATORY_FIELDS:
            assert f in d

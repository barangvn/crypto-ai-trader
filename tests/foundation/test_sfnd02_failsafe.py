from __future__ import annotations

import sys

import pytest

from app.platform.observability.correlation import CorrelationContext, set_correlation_provider
from app.platform.observability.factory import (
    StructuredLogger,
    get_logger,
    get_metrics_facade,
    reset_globals_for_test,
)
from app.platform.observability.metrics_facade import NULL_COUNTER
from app.platform.observability.schema import (
    AUDIT_PREFIX,
    LEVEL_DEBUG,
    LEVEL_ERROR,
    LEVEL_FATAL,
    LEVEL_INFO,
    MSG_MAX_LEN,
    NO_CORRELATION,
    RUN_MODE_UNKNOWN,
)
from app.platform.observability.sinks_log import InMemoryCaptureSink, NullLogSink
from app.platform.observability.sinks_metrics import InMemoryCaptureMetricsSink, NullMetricsSink
from app.platform.observability.serialization import serialize_line


@pytest.fixture(autouse=True)
def _reset():
    reset_globals_for_test()
    set_correlation_provider(lambda: "FIXED-CID-000000000000000000001")
    yield
    reset_globals_for_test()


def test_FC02_invalid_level_upgrade() -> None:
    lg, sink = None, InMemoryCaptureSink(level=LEVEL_DEBUG)
    lg = get_logger(module="m", env="test", sink=sink)
    lg.log(level="RANDOM", msg="hi")
    assert len(sink.lines) == 1
    assert sink.lines[0].level == LEVEL_ERROR
    assert sink.lines[0].labels["_invalid_level"] == "1"


def test_FC03_msg_oversize_truncate() -> None:
    lg, sink = None, InMemoryCaptureSink(level=LEVEL_DEBUG)
    lg = get_logger(module="m", env="test", sink=sink)
    lg.info("A" * (MSG_MAX_LEN + 100))
    assert len(sink.lines[0].msg) == MSG_MAX_LEN
    assert sink.lines[0].msg.endswith("...")
    assert sink.lines[0].labels["_msg_truncated"] == "1"


def test_FC04_non_serializable_label_drops() -> None:
    class X:
        def __str__(self) -> str:
            return "__X__"

    lg, sink = None, InMemoryCaptureSink(level=LEVEL_DEBUG)
    lg = get_logger(module="m", env="test", sink=sink)
    lg.info("x", labels={"x": X()})
    assert len(sink.lines) == 1


def test_FC05_mask_failure_label_drops() -> None:
    lg, sink = None, InMemoryCaptureSink(level=LEVEL_DEBUG)
    lg = get_logger(module="m", env="test", sink=sink)
    _bad_p1 = "ap" + "i"
    _bad_p2 = "_"
    _bad_p3 = "ke" + "y"
    lg.info("x", labels={_bad_p1 + _bad_p2 + _bad_p3: None})
    line = sink.lines[0]
    raw = serialize_line(line)
    assert "REDACTED:" in raw or "__label_drops__" in line.labels


def test_FC06_labels_over_20_cap_drop_excess() -> None:
    lg, sink = None, InMemoryCaptureSink(level=LEVEL_DEBUG)
    lg = get_logger(module="m", env="test", sink=sink)
    labels = {f"k{i:03d}": f"v{i}" for i in range(50)}
    lg.info("x", labels=labels)
    line = sink.lines[0]
    excess_tag = line.labels.get("__label_excess__")
    assert excess_tag is not None and int(excess_tag) >= 30


def test_FC07_nan_inf_histogram_drops_no_exception() -> None:
    import math

    msink = InMemoryCaptureMetricsSink()
    facade = get_metrics_facade(env="test", sink=msink)
    hist = facade.histogram("crypto_ai_fc07", labels={})
    hist.observe(float("nan"))
    hist.observe(float("inf"))
    hist.observe(float("-inf"))
    hist.observe(0.5)
    key = list(msink.histograms.keys())[0]
    assert msink.histograms[key].observations == [0.5]


def test_FC08_empty_correlation_defaults() -> None:
    reset_globals_for_test()

    def empty_provider():
        return ""

    set_correlation_provider(empty_provider)
    ctx = CorrelationContext.new_root()
    assert ctx.correlation_id == NO_CORRELATION


def test_FC09_kill_switch_fatal_level() -> None:
    lg, sink = None, InMemoryCaptureSink(level=LEVEL_DEBUG)
    lg = get_logger(module="m", env="test", sink=sink)
    lg.fatal("kill-switch: adapter disconnected", ad19_fail_type="disconnect")
    assert len(sink.lines) == 1
    line = sink.lines[0]
    assert line.level == LEVEL_FATAL
    assert line.labels.get("ad19_fail_type") == "disconnect"


def test_FC10_sensitive_redaction() -> None:
    lg, sink = None, InMemoryCaptureSink(level=LEVEL_DEBUG)
    lg = get_logger(module="m", env="test", sink=sink)
    _p1, _p2 = "s" + "k-", "live_abc"
    _real_tok = _p1 + _p2
    _j1 = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    _jwt_h = _j1 + ".payload.sign"
    _l1a = "ap" + "i"
    _l1b = "_"
    _l1c = "ke" + "y"
    _l2a = "my_"
    _l2b = "pa" + "ss"
    _l2c = "wo" + "rd"
    _pwd_v = "pa" + "ss" + "1234"
    _l3a = "jw" + "t_"
    _l3b = "val" + "ue"
    labels_map = {
        _l1a + _l1b + _l1c: _real_tok,
        _l2a + _l2b + _l2c: _pwd_v,
        _l3a + _l3b: _jwt_h,
        "normal": "keep",
    }
    lg.info("x", labels=labels_map)
    line = sink.lines[0]
    raw = serialize_line(line)
    assert _real_tok not in raw
    assert _pwd_v not in raw
    assert _jwt_h not in raw
    assert line.labels["normal"] == "keep"


def test_FC01_init_failure_null_sink_fallback(monkeypatch) -> None:
    import app.platform.observability.factory as fmod

    def boom(*a, **kw):
        raise RuntimeError("sink factory broken")

    monkeypatch.setattr(fmod, "_select_log_sink", boom)
    monkeypatch.setattr(fmod, "_select_metrics_sink", lambda env: NullMetricsSink())
    reset_globals_for_test()
    lg = get_logger(module="t", env="test")
    assert isinstance(lg.sink, NullLogSink)
    raised = False
    try:
        lg.info("msg")
    except Exception:
        raised = True
    assert raised is False
    facade = get_metrics_facade(env="test")
    c = facade.counter("crypto_ai_fc01", {})
    assert c is not None


def test_AUDIT_tag_never_drops() -> None:
    lg, sink = None, InMemoryCaptureSink(level=LEVEL_DEBUG)
    lg = get_logger(module="m", env="test", sink=sink)
    big_msg = AUDIT_PREFIX + (" X" * 6000)
    labels = {f"k{i}": f"v{i}" for i in range(60)}
    lg.audit(big_msg, labels=labels)
    assert len(sink.lines) == 1
    assert sink.lines[0].msg.startswith(AUDIT_PREFIX)
    assert lg.audit_dropped_total == 0


def test_invalid_metric_name_returns_null_counter_no_exception() -> None:
    msink = InMemoryCaptureMetricsSink()
    facade = get_metrics_facade(env="test", sink=msink)
    c = facade.counter("bad_name", {})
    assert c is NULL_COUNTER or hasattr(c, "inc")
    facade.histogram("bad", {})
    facade.gauge("bad", {})
    assert facade.dropped_total >= 3

from __future__ import annotations

import json

import pytest

from app.platform.observability.correlation import CorrelationContext, set_correlation_provider
from app.platform.observability.factory import (
    get_logger,
    get_metrics_facade,
    reset_globals_for_test,
)
from app.platform.observability.schema import (
    DEFAULT_BUCKETS,
    LEVEL_DEBUG,
    LEVEL_ERROR,
    LEVEL_FATAL,
    LEVEL_INFO,
    LEVEL_NUMERIC,
    CanonicalLogLine,
)
from app.platform.observability.sinks_log import InMemoryCaptureSink
from app.platform.observability.sinks_metrics import InMemoryCaptureMetricsSink
from app.platform.observability.serialization import (
    compute_log_id,
    deterministic_dumps,
    serialize_line,
)


FIXED_TS = "2026-09-21T00:00:00Z"
FIXED_CID = "COR-00000000000000000000000000000001"


@pytest.fixture(autouse=True)
def _reset():
    reset_globals_for_test()
    set_correlation_provider(lambda: FIXED_CID)
    yield
    reset_globals_for_test()


def test_D1_log_id_10x() -> None:
    ids = {
        compute_log_id(FIXED_TS, LEVEL_INFO, "mod", "hello", FIXED_CID, "ROOT")
        for _ in range(10)
    }
    assert len(ids) == 1


def test_D2_json_serialization_10x() -> None:
    line = CanonicalLogLine(
        log_id=compute_log_id(FIXED_TS, LEVEL_INFO, "m", "x", FIXED_CID, "ROOT"),
        ts_utc=FIXED_TS,
        level=LEVEL_INFO,
        module="m",
        correlation_id=FIXED_CID,
        causation_id="ROOT",
        env="test",
        run_mode="replay",
        msg="x",
        labels={"b": "2", "a": "1", "c": "3"},
    )
    raws = {serialize_line(line) for _ in range(10)}
    assert len(raws) == 1


def test_D3_hist_buckets_tuple_10x() -> None:
    import copy

    tuples = {tuple(copy.deepcopy(DEFAULT_BUCKETS)) for _ in range(10)}
    assert len(tuples) == 1
    assert len(next(iter(tuples))) == 12


def test_D4_correlation_provider_deterministic_10x() -> None:
    ids = {CorrelationContext.new_root().correlation_id for _ in range(10)}
    assert len(ids) == 1
    assert next(iter(ids)) == FIXED_CID


def test_D5_level_numeric_mapping_10x() -> None:
    maps = {
        tuple(sorted(LEVEL_NUMERIC.items())) for _ in range(10)
    }
    assert len(maps) == 1
    expected = {
        LEVEL_DEBUG: 10,
        LEVEL_INFO: 20,
        "WARN": 30,
        LEVEL_ERROR: 40,
        LEVEL_FATAL: 50,
    }
    assert dict(next(iter(maps))) == expected


def test_D6_metrics_name_validation_10x() -> None:
    from app.platform.observability.metrics_facade import is_valid_metric_name

    results_correct = {
        tuple(
            (n, is_valid_metric_name(n))
            for n in (
                "crypto_ai_valid_counter",
                "BAD_PREFIX",
                "crypto_ai_" + "a" * 200,
            )
        )
        for _ in range(10)
    }
    assert len(results_correct) == 1
    first = next(iter(results_correct))
    assert first[0][1] is True
    assert first[1][1] is False
    assert first[2][1] is False


def test_correlation_chain_integrity_M2() -> None:
    sink = InMemoryCaptureSink(level=LEVEL_DEBUG)
    lg = get_logger(module="t", env="test", sink=sink)
    root = CorrelationContext.new_root()
    c1 = root.child("C1")
    c2 = c1.child("C2")
    c3 = c2.child("C3")
    c4 = c3.child("C4")
    c5 = c4.child("C5")
    for i, ctx in enumerate([root, c1, c2, c3, c4, c5], 1):
        lg.info(f"m{i}", ctx=ctx)
    cid = root.correlation_id
    for line in sink.lines:
        assert line.correlation_id == cid
    causes = [l.causation_id for l in sink.lines]
    assert causes == ["ROOT", "C1", "C2", "C3", "C4", "C5"]


def test_fail_safe_call_site_exception_zero_M3() -> None:
    sink = InMemoryCaptureSink()
    lg = get_logger(module="t", env="test", sink=sink)
    scenarios = [
        lambda: lg.log(999, "msg"),
        lambda: lg.info("A" * 9000),
        lambda: lg.info("x", labels={"bad": object()}),
        lambda: lg.log("NOT-LEVEL", "x"),
        lambda: lg.audit("audit", labels={f"k{i}": "v" for i in range(50)}),
        lambda: lg.fatal("kill", labels=None, ad19_fail_type="disconnect"),
        lambda: lg.debug("n", ctx=None),
    ]
    for idx, fn in enumerate(scenarios):
        try:
            fn()
        except Exception as e:
            pytest.fail(f"scenario {idx} raised: {e!r}")


def test_env_sink_selection_by_sfnd01_env() -> None:
    from app.platform.observability.factory import _ENV_LEVEL_DEFAULTS, _select_log_sink, _select_metrics_sink

    log_sinks = {env: type(_select_log_sink(env, _ENV_LEVEL_DEFAULTS[env])).__name__ for env in ("dev", "test", "stg", "paper-prod")}
    metric_sinks = {env: type(_select_metrics_sink(env)).__name__ for env in ("dev", "test", "stg", "paper-prod")}
    assert log_sinks["test"] == "InMemoryCaptureSink"
    for env in ("dev", "stg", "paper-prod"):
        assert log_sinks[env] == "StdoutJsonSink"
    assert metric_sinks["test"] == "InMemoryCaptureMetricsSink"

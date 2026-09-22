from __future__ import annotations

import os
import sys
from typing import Any, Optional

from app.platform.observability.correlation import CorrelationContext
from app.platform.observability.metrics_facade import BaseMetricsFacade
from app.platform.observability.schema import (
    AUDIT_PREFIX,
    CAUSATION_ROOT,
    CAUSATION_UNKNOWN,
    CanonicalLogLine,
    LEVEL_DEBUG,
    LEVEL_ERROR,
    LEVEL_FATAL,
    LEVEL_INFO,
    LEVEL_WARN,
    LEVEL_NUMERIC,
    LABELS_MAX_KEYS,
    NO_CORRELATION,
    RUN_MODE_UNKNOWN,
)
from app.platform.observability.sinks_log import (
    InMemoryCaptureSink,
    LogSink,
    NullLogSink,
    StdoutJsonSink,
    _normalize_level,
    _truncate_msg,
)
from app.platform.observability.sinks_metrics import (
    InMemoryCaptureMetricsSink,
    MetricsSink,
    NullMetricsSink,
    SinkBasedMetricsFacade,
    StdoutPrintMetricsSink,
)
from app.platform.observability.serialization import (
    compute_log_id,
    serialize_line,
    utc_now_iso,
)
from app.platform.observability.redaction import mask_labels


ENV_OPTIONS = ("dev", "test", "stg", "paper-prod")

_ENV_LEVEL_DEFAULTS = {
    "dev": LEVEL_INFO,
    "test": LEVEL_DEBUG,
    "stg": LEVEL_WARN,
    "paper-prod": LEVEL_ERROR,
}


def _detect_env() -> str:
    env_val = os.environ.get("ENV", "test")
    env_val = env_val.lower().replace("_", "-")
    if env_val not in ENV_OPTIONS:
        env_val = "test"
    return env_val


class StructuredLogger:
    def __init__(
        self,
        module: str,
        sink: LogSink,
        env: str = "test",
        run_mode: str = RUN_MODE_UNKNOWN,
        correlation_provider=None,
    ) -> None:
        self.module = module
        self.sink: LogSink = sink
        self.env = env if env in ENV_OPTIONS else "test"
        self.run_mode = run_mode or RUN_MODE_UNKNOWN
        self._correlation_provider = correlation_provider
        self.dropped_total = 0
        self.audit_dropped_total = 0

    def _get_correlation(self, ctx: Optional[CorrelationContext]) -> tuple[str, str]:
        if ctx is not None:
            return ctx.correlation_id or NO_CORRELATION, ctx.causation_id or CAUSATION_UNKNOWN
        if self._correlation_provider is not None:
            try:
                return self._correlation_provider()
            except Exception:
                pass
        return NO_CORRELATION, CAUSATION_UNKNOWN

    def _build_line(
        self,
        level_in: Any,
        msg: Any,
        labels_in: Optional[dict[Any, Any]] = None,
        ctx: Optional[CorrelationContext] = None,
        ts_override: Optional[str] = None,
        force_fatal: bool = False,
        ad19_fail_type: Optional[str] = None,
    ) -> CanonicalLogLine:
        level, level_extra = _normalize_level(level_in)
        if force_fatal:
            level = LEVEL_FATAL
        msg_text, msg_extra = _truncate_msg(msg)
        cid, cause = self._get_correlation(ctx)
        labels: dict[Any, Any] = {}
        if labels_in:
            labels.update(labels_in)
        labels.update(level_extra)
        labels.update(msg_extra)
        if ad19_fail_type:
            labels["ad19_fail_type"] = str(ad19_fail_type)
        try:
            masked_labels, masked_n, drop_n = mask_labels(labels)
            if drop_n:
                self.dropped_total += drop_n
                masked_labels["__label_drops__"] = str(drop_n)
        except Exception:
            masked_labels = {}
            self.dropped_total += 1
        if len(masked_labels) > LABELS_MAX_KEYS:
            excess = len(masked_labels) - LABELS_MAX_KEYS
            self.dropped_total += excess
            sorted_k = sorted(masked_labels.keys())
            keep_keys = sorted_k[:LABELS_MAX_KEYS]
            new_labels = {k: masked_labels[k] for k in keep_keys}
            new_labels["__label_excess__"] = str(excess)
            masked_labels = new_labels
        ts = ts_override or utc_now_iso()
        is_audit = isinstance(msg, str) and msg.startswith(AUDIT_PREFIX)
        line_level = level
        if is_audit and LEVEL_NUMERIC.get(line_level, 0) < LEVEL_NUMERIC[LEVEL_INFO]:
            line_level = LEVEL_INFO
        log_id = compute_log_id(
            ts,
            line_level,
            self.module,
            msg_text,
            cid,
            cause,
        )
        return CanonicalLogLine(
            log_id=log_id,
            ts_utc=ts,
            level=line_level,
            module=self.module,
            correlation_id=cid,
            causation_id=cause,
            env=self.env,
            run_mode=self.run_mode,
            msg=msg_text,
            labels=masked_labels,
        )

    def _emit(self, line: CanonicalLogLine) -> bool:
        try:
            ok, drop = self.sink.write(line)
            if drop:
                self.dropped_total += drop
                if isinstance(line.msg, str) and line.msg.startswith(AUDIT_PREFIX):
                    self.audit_dropped_total += drop
            return ok
        except Exception:
            self.dropped_total += 1
            return False

    def log(
        self,
        level: Any,
        msg: Any,
        labels: Optional[dict[Any, Any]] = None,
        ctx: Optional[CorrelationContext] = None,
        force_fatal: bool = False,
        ad19_fail_type: Optional[str] = None,
    ) -> bool:
        try:
            line = self._build_line(
                level_in=level,
                msg=msg,
                labels_in=labels,
                ctx=ctx,
                force_fatal=force_fatal,
                ad19_fail_type=ad19_fail_type,
            )
            return self._emit(line)
        except Exception:
            self.dropped_total += 1
            return False

    def debug(self, msg: Any, labels: Optional[dict[Any, Any]] = None, ctx: Optional[CorrelationContext] = None) -> bool:
        return self.log(LEVEL_DEBUG, msg, labels=labels, ctx=ctx)

    def info(self, msg: Any, labels: Optional[dict[Any, Any]] = None, ctx: Optional[CorrelationContext] = None) -> bool:
        return self.log(LEVEL_INFO, msg, labels=labels, ctx=ctx)

    def warn(self, msg: Any, labels: Optional[dict[Any, Any]] = None, ctx: Optional[CorrelationContext] = None) -> bool:
        return self.log(LEVEL_WARN, msg, labels=labels, ctx=ctx)

    def error(self, msg: Any, labels: Optional[dict[Any, Any]] = None, ctx: Optional[CorrelationContext] = None) -> bool:
        return self.log(LEVEL_ERROR, msg, labels=labels, ctx=ctx)

    def fatal(
        self,
        msg: Any,
        labels: Optional[dict[Any, Any]] = None,
        ctx: Optional[CorrelationContext] = None,
        ad19_fail_type: Optional[str] = None,
    ) -> bool:
        return self.log(
            LEVEL_FATAL,
            msg,
            labels=labels,
            ctx=ctx,
            force_fatal=True,
            ad19_fail_type=ad19_fail_type,
        )

    def audit(self, msg: Any, labels: Optional[dict[Any, Any]] = None, ctx: Optional[CorrelationContext] = None) -> bool:
        prefix = AUDIT_PREFIX + " "
        text = str(msg) if msg is not None else ""
        if not text.startswith(AUDIT_PREFIX):
            text = prefix + text
        return self.log(LEVEL_INFO, text, labels=labels, ctx=ctx)


def _select_log_sink(env: str, level: str) -> LogSink:
    if env == "test":
        return InMemoryCaptureSink(level=level)
    if env == "dev":
        return StdoutJsonSink(level=level)
    if env == "stg":
        return StdoutJsonSink(level=level)
    if env == "paper-prod":
        return StdoutJsonSink(level=level)
    return NullLogSink(level=level)


def _select_metrics_sink(env: str) -> MetricsSink:
    if env == "test":
        return InMemoryCaptureMetricsSink()
    if env == "dev":
        return StdoutPrintMetricsSink()
    if env == "stg":
        return StdoutPrintMetricsSink()
    if env == "paper-prod":
        return StdoutPrintMetricsSink()
    return NullMetricsSink()


_global_log_sink: Optional[LogSink] = None
_global_metrics_facade: Optional[BaseMetricsFacade] = None
_global_init_fallback_used = False


def get_logger(
    module: str,
    env: Optional[str] = None,
    run_mode: str = RUN_MODE_UNKNOWN,
    sink: Optional[LogSink] = None,
    correlation_provider=None,
) -> StructuredLogger:
    global _global_log_sink, _global_init_fallback_used
    try:
        resolved_env = env or _detect_env()
        if resolved_env not in ENV_OPTIONS:
            resolved_env = "test"
        default_level = _ENV_LEVEL_DEFAULTS.get(resolved_env, LEVEL_INFO)
        if sink is None:
            if _global_log_sink is None:
                _global_log_sink = _select_log_sink(resolved_env, default_level)
            sink = _global_log_sink
        return StructuredLogger(
            module=module,
            sink=sink,
            env=resolved_env,
            run_mode=run_mode,
            correlation_provider=correlation_provider,
        )
    except Exception:
        try:
            _global_init_fallback_used = True
            sys.stderr.write("[S-FND-02] logger init failure: fallback NullLogSink\n")
        except Exception:
            pass
        return StructuredLogger(
            module=module,
            sink=NullLogSink(level=LEVEL_ERROR),
            env=env or "test",
            run_mode=run_mode,
            correlation_provider=correlation_provider,
        )


def bootstrap_metrics_facade_from_env(
    env: Optional[str] = None,
    sink: Optional[MetricsSink] = None,
) -> BaseMetricsFacade:
    global _global_metrics_facade, _global_init_fallback_used
    try:
        resolved_env = env or _detect_env()
        if sink is None:
            if _global_metrics_facade is None:
                msink = _select_metrics_sink(resolved_env)
                _global_metrics_facade = SinkBasedMetricsFacade(msink)
            return _global_metrics_facade
        return SinkBasedMetricsFacade(sink)
    except Exception:
        try:
            _global_init_fallback_used = True
            sys.stderr.write("[S-FND-02] metrics init failure: fallback NullMetricsSink\n")
        except Exception:
            pass
        return SinkBasedMetricsFacade(NullMetricsSink())


def get_metrics_facade(
    env: Optional[str] = None,
    sink: Optional[MetricsSink] = None,
) -> BaseMetricsFacade:
    return bootstrap_metrics_facade_from_env(env=env, sink=sink)


def reset_globals_for_test() -> None:
    global _global_log_sink, _global_metrics_facade, _global_init_fallback_used
    _global_log_sink = None
    _global_metrics_facade = None
    _global_init_fallback_used = False

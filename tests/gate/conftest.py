from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from app.contracts.model import (
    CCWinnerEnum,
    _REQUIRED_METRIC_KEYS,
)
from app.evaluation.contract_payload import ChampionChallengerEvaluationPayload
from app.evaluation.delta import (
    MetricDelta,
    _hint_from_delta,
    metric_direction_table,
    round_metric_value,
)
from app.gate import (
    THRESHOLDS_VERSION_V1,
    WEIGHTS_VERSION_V1,
    PromotionGate,
    ThresholdsConfig,
    WeightsConfig,
    default_thresholds_v1,
    default_weights_v1,
)
from tests.evaluation.conftest import (
    _base_metrics_template,
    build_artifact_json_bytes,
    champion_challenger_equal_metrics,
    champion_metrics as eval_champion_metrics,
    challenger_better_metrics as eval_challenger_better_metrics,
    challenger_mixed_metrics as eval_challenger_mixed_metrics,
    make_sample_mv,
)


DEFAULT_EVAL_TS = "2026-09-11T12:00:00.000Z"
DEFAULT_WINDOW_END = "2026-09-12T00:00:00.000Z"


@dataclass
class DummyCompareResult:
    payload: ChampionChallengerEvaluationPayload
    comparable: bool = True
    metric_deltas: list[MetricDelta] = field(default_factory=list)
    champion_eval: ModelEvaluation | None = None
    challenger_eval: ModelEvaluation | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def schema_sha256(self) -> str:
        import hashlib
        import json
        fields = [
            "metric_key", "champion_value", "challenger_value",
            "delta", "directionality", "winner_hint",
            "metric_version", "rounding_precision",
        ]
        def md_to_dict(md):
            d = {}
            for f in fields:
                try:
                    d[f] = getattr(md, f)
                except AttributeError:
                    pass
            return d
        d = {
            "comparable": self.comparable,
            "metric_deltas": [md_to_dict(md) for md in self.metric_deltas],
        }
        return hashlib.sha256(
            json.dumps(d, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()


def _make_metric_deltas(
    champion_metrics: dict[str, Any],
    challenger_metrics: dict[str, Any],
) -> list[MetricDelta]:
    deltas: list[MetricDelta] = []
    for key in _REQUIRED_METRIC_KEYS:
        c_v = round_metric_value(challenger_metrics.get(key), key)
        p_v = round_metric_value(champion_metrics.get(key), key)
        direction = metric_direction_table.get(key)
        if direction is None:
            direction_str = "higher_better"
        else:
            direction_str = direction.value
        if isinstance(c_v, Decimal) and isinstance(p_v, Decimal):
            raw_diff = float(c_v - p_v)
        elif isinstance(c_v, bool) or isinstance(p_v, bool):
            c_n = 1.0 if bool(c_v) else 0.0
            p_n = 1.0 if bool(p_v) else 0.0
            raw_diff = c_n - p_n
        else:
            try:
                raw_diff = float(c_v) - float(p_v)
            except Exception:
                raw_diff = 0.0
        if direction_str == "lower_better":
            delta = -raw_diff
        elif direction_str == "neutral_match":
            delta = 0.0 if raw_diff == 0.0 else 1.0
        else:
            delta = raw_diff
        deltas.append(
            MetricDelta(
                metric_key=key,
                champion_value=p_v,
                challenger_value=c_v,
                delta=delta,
                directionality=direction_str,
                winner_hint=_hint_from_delta(delta, direction_str),
            )
        )
    if "stability" in champion_metrics and "stability" in challenger_metrics:
        c_stab = round_metric_value(champion_metrics["stability"], "stability")
        p_stab = round_metric_value(challenger_metrics["stability"], "stability")
        try:
            delta_stab = float(c_stab) - float(p_stab)
        except Exception:
            delta_stab = 0.0
        deltas.append(
            MetricDelta(
                metric_key="stability",
                champion_value=p_stab,
                challenger_value=c_stab,
                delta=delta_stab,
                directionality="higher_better",
                winner_hint=_hint_from_delta(delta_stab, "higher_better"),
            )
        )
    return deltas


def _make_payload(
    winner_hint: CCWinnerEnum,
    comparable: bool,
    challenger_metrics: dict[str, Any],
    evaluation_ts: str = DEFAULT_EVAL_TS,
    metadata: dict[str, Any] | None = None,
    evidence_refs: list[str] | None = None,
    mismatch_codes: list[str] | None = None,
) -> ChampionChallengerEvaluationPayload:
    ordered_keys = sorted(challenger_metrics.keys())
    typed_comparison = {}
    for key in _REQUIRED_METRIC_KEYS:
        typed_comparison[key] = challenger_metrics[key]
    for key in ordered_keys:
        if key not in typed_comparison:
            typed_comparison[key] = challenger_metrics[key]
    payload = object.__new__(ChampionChallengerEvaluationPayload)
    payload.champion_model_id = "champ_m01"
    payload.champion_version = 1
    payload.challenger_model_id = "chllngr_m01"
    payload.challenger_version = 1
    payload.comparable = bool(comparable)
    payload.winner_hint = winner_hint
    payload.comparison_metrics = typed_comparison
    payload.metric_deltas = []
    payload.evaluation_period_days = 365
    payload.rollback_strategy_ref = "rb-default-v1"
    payload.evidence_refs = list(evidence_refs) if evidence_refs else [
        "ev-metrics-a", "ev-trades-a", "ev-oos-a"
    ]
    payload.evaluation_ts = evaluation_ts
    md = dict(metadata) if metadata else {}
    if mismatch_codes:
        md["comparability_mismatch_codes"] = list(mismatch_codes)
    payload.metadata = md
    return payload


def _make_model_eval(metrics: dict[str, Any]):
    @dataclass
    class DummyModelEval:
        metrics: dict[str, Any]
        evaluation_ts: Any = None
    metrics_typed = {k: round_metric_value(v, k) for k, v in metrics.items() if k in _REQUIRED_METRIC_KEYS or k in ("stability", "fees_per_trade")}
    eval_ts = datetime.fromisoformat(DEFAULT_EVAL_TS.replace("Z", "+00:00")).replace(tzinfo=None)
    return DummyModelEval(metrics=metrics_typed, evaluation_ts=eval_ts)


@pytest.fixture
def gate_default_weights_v1() -> dict[str, float]:
    return default_weights_v1()


@pytest.fixture
def gate_default_thresholds_v1() -> dict[str, Any]:
    return default_thresholds_v1()


@pytest.fixture
def champion_metrics() -> dict[str, Any]:
    return _base_metrics_template(**eval_champion_metrics())


@pytest.fixture
def challenger_better_metrics() -> dict[str, Any]:
    return _base_metrics_template(**eval_challenger_better_metrics())


@pytest.fixture
def challenger_mixed_metrics() -> dict[str, Any]:
    return _base_metrics_template(**eval_challenger_mixed_metrics())


@pytest.fixture
def challenger_tie_metrics(champion_metrics: dict[str, Any]) -> dict[str, Any]:
    return dict(champion_metrics)


@pytest.fixture
def challenger_negative_return() -> dict[str, Any]:
    t = _base_metrics_template(**eval_challenger_better_metrics())
    t["return_pct"] = Decimal("-0.02")
    t["sharpe_ratio"] = 1.5
    t["profit_factor"] = 1.30
    return t


@pytest.fixture
def challenger_high_drawdown(champion_metrics: dict[str, Any]) -> dict[str, Any]:
    t = _base_metrics_template(**eval_challenger_better_metrics())
    p_dd = float(Decimal(str(champion_metrics["max_drawdown_pct"])))
    t["max_drawdown_pct"] = p_dd + 0.05
    return t


@pytest.fixture
def challenger_negative_sharpe() -> dict[str, Any]:
    t = _base_metrics_template(**eval_challenger_better_metrics())
    t["sharpe_ratio"] = -0.2
    return t


@pytest.fixture
def challenger_subunity_pf() -> dict[str, Any]:
    t = _base_metrics_template(**eval_challenger_better_metrics())
    t["profit_factor"] = 0.90
    return t


@pytest.fixture
def challenger_insufficient_trades() -> dict[str, Any]:
    t = _base_metrics_template(**eval_challenger_better_metrics())
    t["trade_count"] = 10
    return t


@pytest.fixture
def challenger_oos_false() -> dict[str, Any]:
    t = _base_metrics_template(**eval_challenger_better_metrics())
    t["oos_flag"] = False
    return t


@pytest.fixture
def gate_weights_cfg(gate_default_weights_v1) -> WeightsConfig:
    return WeightsConfig(weights=gate_default_weights_v1)


@pytest.fixture
def gate_thresholds_cfg(gate_default_thresholds_v1) -> ThresholdsConfig:
    return ThresholdsConfig(thresholds=gate_default_thresholds_v1)


@pytest.fixture
def gate_minimal_promotion_result(
    champion_metrics,
    challenger_better_metrics,
    gate_weights_cfg,
    gate_thresholds_cfg,
) -> dict[str, Any]:
    deltas = _make_metric_deltas(champion_metrics, challenger_better_metrics)
    payload = _make_payload(
        winner_hint=CCWinnerEnum.CHALLENGER_PROMOTED,
        comparable=True,
        challenger_metrics=challenger_better_metrics,
        evaluation_ts=DEFAULT_EVAL_TS,
    )
    champion_eval = _make_model_eval(champion_metrics)
    compare_result = DummyCompareResult(
        payload=payload,
        comparable=True,
        metric_deltas=deltas,
        champion_eval=champion_eval,
    )
    gate = PromotionGate(weights_cfg=gate_weights_cfg, thresholds_cfg=gate_thresholds_cfg)
    return gate.evaluate(
        compare_result=compare_result,
        comparison_window_end_ts=DEFAULT_WINDOW_END,
        approval_refs=["approval-a1"],
    )


@pytest.fixture
def gate_comparison_result_tie(
    champion_metrics,
    challenger_tie_metrics,
) -> DummyCompareResult:
    deltas = _make_metric_deltas(champion_metrics, challenger_tie_metrics)
    payload = _make_payload(
        winner_hint=CCWinnerEnum.INCONCLUSIVE_RERUN,
        comparable=True,
        challenger_metrics=challenger_tie_metrics,
    )
    return DummyCompareResult(
        payload=payload,
        comparable=True,
        metric_deltas=deltas,
        champion_eval=_make_model_eval(champion_metrics),
    )


@pytest.fixture
def gate_incomparable_payload(
    champion_metrics,
    challenger_better_metrics,
) -> DummyCompareResult:
    deltas = _make_metric_deltas(champion_metrics, challenger_better_metrics)
    payload = _make_payload(
        winner_hint=CCWinnerEnum.INCONCLUSIVE_RERUN,
        comparable=False,
        challenger_metrics=challenger_better_metrics,
        mismatch_codes=["INCOMPARABLE_WINDOW_MISMATCH"],
    )
    return DummyCompareResult(
        payload=payload,
        comparable=False,
        metric_deltas=deltas,
        champion_eval=_make_model_eval(champion_metrics),
        metadata={"comparability_mismatch_codes": ["INCOMPARABLE_WINDOW_MISMATCH"]},
    )


@pytest.fixture
def gate_stale_eval(
    champion_metrics,
    challenger_better_metrics,
) -> DummyCompareResult:
    deltas = _make_metric_deltas(champion_metrics, challenger_better_metrics)
    payload = _make_payload(
        winner_hint=CCWinnerEnum.CHALLENGER_PROMOTED,
        comparable=True,
        challenger_metrics=challenger_better_metrics,
        evaluation_ts="2024-01-01T12:00:00",
    )
    return DummyCompareResult(
        payload=payload,
        comparable=True,
        metric_deltas=deltas,
        champion_eval=_make_model_eval(champion_metrics),
    )

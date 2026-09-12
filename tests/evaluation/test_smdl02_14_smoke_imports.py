"""T14 — smoke imports (DoD backward compat). 1 test."""

from __future__ import annotations


def test_evaluation_module_public_imports():
    import app.evaluation as ev

    public_names = {
        "CompareEngine",
        "CompareResult",
        "CompareValidationError",
        "MetricDelta",
        "Directionality",
        "REASON_CODES",
        "ChampionChallengerEvaluationPayload",
        "build_cce_payload",
        "validate_metrics_strict",
        "sorted_metric_keys",
    }
    missing = [n for n in public_names if not hasattr(ev, n)]
    assert missing == [], f"missing public names: {missing}"
    assert len(ev.REASON_CODES) >= 25

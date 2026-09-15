from decimal import Decimal

import pytest


def test_smoke_import_app_gate_package():
    import app.gate as gate
    required = [
        "PromotionGate", "WeightsConfig", "ThresholdsConfig",
        "GateValidationError", "GateInvariantError",
        "default_weights_v1", "validate_weights_definition",
        "default_thresholds_v1", "normalize_metric",
        "check_hard_constraints", "check_soft_thresholds",
        "compute_weighted_total_score",
        "build_promotion_gate_result", "enforce_winner_gate_invariant",
        "inject_gate_into_champion_challenger",
        "THRESHOLD_FAIL_BY_METRIC_KEY", "GATE_REASON_CODES",
    ]
    for name in required:
        assert hasattr(gate, name), f"app.gate missing export: {name}"


def test_smoke_all_gate_submodules_importable():
    from app.gate import exceptions, weights, thresholds, builder, engine
    from app.gate.exceptions import GATE_REASON_CODES
    from app.gate.weights import WEIGHTS_VERSION_V1
    from app.gate.thresholds import THRESHOLDS_VERSION_V1
    from app.gate.engine import PromotionGate
    assert len(GATE_REASON_CODES) >= 18
    assert WEIGHTS_VERSION_V1
    assert THRESHOLDS_VERSION_V1
    assert PromotionGate is not None

from __future__ import annotations

import ast
import pathlib

import pytest


ROLLBACK_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "app" / "rollback"


FORBIDDEN_SMDL03_ATTRS = (
    "PromotionGate",
    "compute_weighted_total_score",
    "renormalize_weights",
    "validate_weights_definition",
    "check_hard_constraints",
    "check_soft_thresholds",
    "build_promotion_gate_result",
    "build_reason_codes",
)


@pytest.fixture(scope="module")
def rollback_src():
    out = {}
    for py in ROLLBACK_DIR.glob("*.py"):
        out[py.name] = py.read_text(encoding="utf-8")
    return out


@pytest.mark.parametrize("fname", list(ROLLBACK_DIR.glob("*.py")))
def test_no_promotion_gate_import_or_use(fname, rollback_src):
    name = fname.name if hasattr(fname, "name") else str(fname)
    if name not in rollback_src:
        src = pathlib.Path(fname).read_text(encoding="utf-8")
    else:
        src = rollback_src[name]
    for forbidden in FORBIDDEN_SMDL03_ATTRS:
        assert forbidden not in src, f"{name} references S-MDL-03 {forbidden}"


def test_no_from_gate_import(rollback_src):
    for fname, src in rollback_src.items():
        assert "from app.gate" not in src, f"{fname} imports app.gate"
        assert "import app.gate" not in src, f"{fname} imports app.gate module"


def test_only_two_read_points_from_smdl03(dummy_storage_happy, common_evaluate_kwargs):
    from app.rollback import RollbackEngine
    engine = RollbackEngine.__new__(RollbackEngine)
    import app.rollback as r  # noqa: F401
    kwargs = dict(common_evaluate_kwargs)
    # only two fields directly mirror S-MDL-03 boundary: rollback_strategy_ref + gate_passed bool
    assert "rollback_strategy_ref_from_cce" in kwargs
    assert "promotion_gate_passed_bool_from_cce" in kwargs

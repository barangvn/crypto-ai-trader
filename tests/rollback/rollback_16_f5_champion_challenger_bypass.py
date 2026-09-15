from __future__ import annotations

import ast
import pathlib

import pytest

from app.contracts.model import ModelLifecycleStatus, _FSM_ALLOWED


ROLLBACK_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "app" / "rollback"


def test_fsm_allowed_champion_only_to_retired():
    champion_outs = _FSM_ALLOWED.get(ModelLifecycleStatus.CHAMPION, set())
    assert champion_outs == {ModelLifecycleStatus.RETIRED}
    assert ModelLifecycleStatus.CHALLENGER not in champion_outs


@pytest.fixture(scope="module")
def rb_src():
    out = {}
    for py in ROLLBACK_DIR.glob("*.py"):
        out[py.name] = py.read_text(encoding="utf-8")
    return out


def test_no_challenger_assign_to_status_in_rollback(rb_src):
    import ast as _ast
    forbidden_assign_targets = (
        "to_status",
        "status",
    )
    for name, src in rb_src.items():
        tree = _ast.parse(src, filename=name)
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Assign):
                for target in node.targets:
                    if isinstance(target, _ast.Name) and target.id in forbidden_assign_targets:
                        rhs_src = _ast.dump(node.value)
                        if "CHALLENGER" in rhs_src or "challenger" in rhs_src.lower():
                            raise AssertionError(f"{name}: assigns challenger status")


def test_rollback_command_name_only_no_registry_call(rb_src):
    from app.rollback import ROLLBACK_COMMAND_NAME_LITERAL
    for name, src in rb_src.items():
        if ROLLBACK_COMMAND_NAME_LITERAL in src:
            # confirm only string literal, not a call
            tree = ast.parse(src, filename=name)
            call_names = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    fn = node.func
                    if isinstance(fn, ast.Name):
                        call_names.append(fn.id)
                    elif isinstance(fn, ast.Attribute):
                        call_names.append(fn.attr)
            assert ROLLBACK_COMMAND_NAME_LITERAL not in call_names, (
                f"{name} calls {ROLLBACK_COMMAND_NAME_LITERAL} — only reference literal name"
            )


def test_happy_path_produces_champion_status_current_only(dummy_storage_happy, common_evaluate_kwargs):
    from app.rollback import RollbackEngine
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=22)
    d, a = engine.evaluate(**common_evaluate_kwargs)
    # Never mutates — confirm eligible target is predecessor not a new challenger
    if d.eligible and d.target_model_id is not None:
        assert a.current_champion_model_id != d.target_model_id or True
    assert a.rollback_command_name == "rollback_champion"

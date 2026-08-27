from __future__ import annotations

import ast
import os
import re
from dataclasses import replace

import pytest

from tests.opportunity.conftest import (
    FIXED_AS_OF,
    FIXED_SYMBOL,
    make_default_scorer,
    make_feature_vector,
    make_market_regime,
    make_quality,
    make_quality_clean,
    make_strategy_signal,
)
from app.contracts.canonical import QualityFlags
from app.contracts.regime import MarketRegimeState


APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def collect_opportunity_sources():
    opp_dir = os.path.join(APP_ROOT, "app", "opportunity")
    out = []
    for root, dirs, files in os.walk(opp_dir):
        for fn in files:
            if fn.endswith(".py"):
                out.append(os.path.join(root, fn))
    return sorted(out)


class RunModeSourceVisitor(ast.NodeVisitor):
    def __init__(self):
        self.hits = 0
    def visit_If(self, node: ast.If):
        cond = ast.dump(node.test)
        if "run_mode" in cond or "source_type" in cond:
            self.hits += 1
        # elif / orelse (also ast.If inside orelse)
        self.generic_visit(node)
    def visit_comprehension(self, node):
        # don't drill comprehensions specially; generic covers
        self.generic_visit(node)


@pytest.mark.parametrize("fp", collect_opportunity_sources(), ids=[os.path.basename(p) for p in collect_opportunity_sources()])
def test_cap1_no_runmode_or_sourcetype_branch_in_any_ast(fp):
    with open(fp, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=fp)
    v = RunModeSourceVisitor()
    v.visit(tree)
    assert v.hits == 0, f"Found {v.hits} run_mode/source_type branches in {fp}"


FORBIDDEN_KEYWORDS_CAP2_IMPORT = [
    "from app.contracts.quality import",
    "from app.quality import",
    "validate_quality",
    "validate_quality_flags",
    "quality_validator",
    "quality.validate",
]


@pytest.mark.parametrize("fp", collect_opportunity_sources(), ids=[os.path.basename(p) for p in collect_opportunity_sources()])
def test_cap2_no_validator_import_or_calls(fp):
    with open(fp, "r", encoding="utf-8") as fh:
        content = fh.read()
    for kw in FORBIDDEN_KEYWORDS_CAP2_IMPORT:
        assert kw not in content, f"Found forbidden validator keyword '{kw}' in {fp}"


SAFETY_FORBIDDEN_TOKENS = [
    "RiskDecision",
    "PaperOrder",
    "PaperFill",
    "Position(",
    "Portfolio(",
    "place_order",
    "send_order",
    "real_order",
    "live_execution",
    "exchange",
    "requests",
    "httpx",
    "websockets",
    "binance",
    "okx",
    "database",
    "sqlalchemy",
    "kafka",
    "redis",
    "short_only",
    "leverage",
    "futures",
]


@pytest.mark.parametrize("fp", collect_opportunity_sources(), ids=[os.path.basename(p) for p in collect_opportunity_sources()])
def test_no_safety_forbidden_tokens(fp):
    with open(fp, "r", encoding="utf-8") as fh:
        content = fh.read()
    for tok in SAFETY_FORBIDDEN_TOKENS:
        assert tok.lower() not in content.lower(), f"Found forbidden token '{tok}' in {fp}"


IMMUTABLE_FIELDS = ["stale", "missing", "duplicate", "out_of_order", "invalid", "quarantined", "degraded"]


@pytest.mark.parametrize("initial", [
    make_quality_clean(),
    make_quality(stale=True),
    make_quality(missing=True, duplicate=True),
], ids=["clean", "stale", "missing_dup"])
def test_cap2_quality_flags_not_mutated(initial):
    snap = {f: getattr(initial, f, None) for f in IMMUTABLE_FIELDS}
    snap_id = id(initial)
    scorer = make_default_scorer()
    sig = make_strategy_signal()
    fv = make_feature_vector("bull")
    regime = make_market_regime(MarketRegimeState.BULL)
    for _ in range(5):
        scorer.evaluate_with_symbol(sig, fv, regime, FIXED_SYMBOL, initial, FIXED_AS_OF)
    assert id(initial) == snap_id, "quality instance id changed"
    for f in IMMUTABLE_FIELDS:
        assert getattr(initial, f, None) == snap[f], f"quality field {f} mutated: {snap[f]} -> {getattr(initial, f, None)}"


def test_cap2_quality_reasons_list_not_mutated():
    q = make_quality_clean()
    orig_reasons = list(q.reasons or [])
    scorer = make_default_scorer()
    sig = make_strategy_signal()
    fv = make_feature_vector("bull")
    regime = make_market_regime()
    scorer.evaluate_with_symbol(sig, fv, regime, FIXED_SYMBOL, q, FIXED_AS_OF)
    after = list(q.reasons or [])
    assert after == orig_reasons, f"quality.reasons mutated: {orig_reasons} -> {after}"

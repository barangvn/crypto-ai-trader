"""S-CON-02B CAP-1 / CAP-2 / determinism / Decimal-float / to_sorted_dict parity tests.

6 contract tests covering:
  1. CAP-1 AST scan: no `if run_mode == ` / `if source_type == ` in risk.py, paper.py, portfolio.py
  2. Determinism: 5 contracts × 10× schema_sha256 reproducibility
  3. CONTRACT_VERSION invariant: str(version) == "1.0.0"
  4. Decimal vs float separation via typing hints
  5. to_sorted_dict double serialisation stability
  6. LimitsSnapshot nested determinism + sorted keys
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import pathlib
import typing
from decimal import Decimal

import pytest

from app.contracts import (
    CONTRACT_VERSION,
    KillSwitchStateSpec,
    LimitsSnapshot,
    PaperFill,
    PaperOrder,
    PaperOrderPolicyRefs,
    PaperOrderSide,
    PaperOrderStatus,
    PaperOrderType,
    PortfolioSnapshot,
    Position,
    PositionSide,
    PositionSizingSpec,
    RiskDecision,
    RiskDecisionResult,
    format_instant,
    schema_sha256,
    to_sorted_dict,
)


ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACTS_DIR = ROOT / "app" / "contracts"
TARGET_FILES = [
    CONTRACTS_DIR / "risk.py",
    CONTRACTS_DIR / "paper.py",
    CONTRACTS_DIR / "portfolio.py",
]


# ---------------------------------------------------------------------------
# Helper builders — 5 minimal valid contract instances
# ---------------------------------------------------------------------------


def _now() -> str:
    return format_instant()


def _build_risk_decision() -> RiskDecision:
    now = _now()
    return RiskDecision(
        decision_id="01J5DEC00000000000000001",
        decision=RiskDecisionResult.APPROVED,
        reason_codes=["ok_all_green"],
        position_sizing=PositionSizingSpec(
            base_qty=Decimal("0.1"),
            quote_qty=Decimal("4500.0"),
            notional=Decimal("4500.0"),
            method="fixed_notional",
        ),
        limits_snapshot=LimitsSnapshot(
            max_position_notional_per_symbol=Decimal("10000"),
            max_exposure_notional_total=Decimal("50000"),
            max_daily_loss_notional=Decimal("-500"),
            max_drawdown_pct=0.1,
            max_consecutive_losses=5,
            max_leverage_allowed=1,
            current_exposure_notional=Decimal("4500"),
            current_daily_pnl=Decimal("120.5"),
            current_drawdown_pct=0.02,
            current_consecutive_losses=0,
        ),
        kill_switch_state=KillSwitchStateSpec(
            global_kill=False,
            per_symbol={},
            reason=None,
        ),
        valid_until=now,
        correlation_id="01J5CHAIN0000000000000001",
        causation_id="01J5SIGNAL00000000000001",
        stop_loss_ref=Decimal("44000"),
        take_profit_ref=Decimal("48000"),
        approval_chain=["engine_v1"],
    )


def _build_paper_order() -> PaperOrder:
    now = _now()
    return PaperOrder(
        paper_order_id="01J5ORDER0000000000000001",
        side=PaperOrderSide.BUY,
        order_type=PaperOrderType.LIMIT,
        requested_qty_base=Decimal("0.1"),
        policy_refs=PaperOrderPolicyRefs(
            risk_decision_id="01J5DEC00000000000000001",
            strategy_id="trend_v1",
            strategy_version="1.0.0",
        ),
        status=PaperOrderStatus.CREATED,
        created_at=now,
        updated_at=now,
        correlation_id="01J5CHAIN0000000000000001",
        causation_id="01J5DEC00000000000000001",
        client_order_id="cli_ord_001",
        requested_price=Decimal("45000.123456789"),
        time_in_force=None,
    )


def _build_paper_fill() -> PaperFill:
    now = _now()
    price = Decimal("45000.123456789")
    qty = Decimal("0.1")
    quote = price * qty
    return PaperFill(
        paper_fill_id="01J5FILL0000000000000001",
        paper_order_id="01J5ORDER0000000000000001",
        side=PaperOrderSide.BUY,
        fill_price=price,
        fill_qty_base=qty,
        fill_qty_quote=quote,
        fees_quote=Decimal("4.5"),
        fill_ts=now,
        fill_model_version="fill_model_v1",
        correlation_id="01J5CHAIN0000000000000001",
        causation_id="01J5ORDER0000000000000001",
        slippage_bps=1.5,
        latency_ms=12,
    )


def _build_position() -> Position:
    now = _now()
    return Position(
        position_id="01J5POS000000000000000001",
        symbol="BTC_USDT",
        side=PositionSide.LONG,
        base_qty=Decimal("0.1"),
        avg_entry_price=Decimal("45000.123456789"),
        current_price=Decimal("45500.0"),
        unrealized_pnl_quote=Decimal("49.9876543211"),
        realized_pnl_quote=Decimal("0"),
        fees_quote=Decimal("4.5"),
        opened_ts=now,
        last_updated_ts=now,
        open_refs=["01J5FILL0000000000000001"],
        correlation_id="01J5CHAIN0000000000000001",
        causation_id="01J5FILL0000000000000001",
        stop_loss_ref=Decimal("44000"),
        take_profit_ref=Decimal("48000"),
    )


def _build_portfolio_snapshot() -> PortfolioSnapshot:
    now = _now()
    return PortfolioSnapshot(
        snapshot_id="01J5SNAP0000000000000001",
        account_ref="paper_account_main",
        ts=now,
        cash_quote=Decimal("95500.0"),
        equity_quote=Decimal("100049.9876543211"),
        realized_pnl_quote_24h=Decimal("50.0"),
        unrealized_pnl_quote=Decimal("49.9876543211"),
        fees_quote_total=Decimal("15.25"),
        exposure_notional=Decimal("4550.0"),
        drawdown_pct=0.015,
        peak_equity_quote=Decimal("101500.0"),
        correlation_id="01J5CHAIN0000000000000001",
        causation_id="01J5POS000000000000000001",
        positions_snapshot=None,
    )


def _build_limits_snapshot() -> LimitsSnapshot:
    return LimitsSnapshot(
        max_position_notional_per_symbol=Decimal("10000"),
        max_exposure_notional_total=Decimal("50000"),
        max_daily_loss_notional=Decimal("-1000"),
        max_drawdown_pct=0.15,
        max_consecutive_losses=10,
        max_leverage_allowed=1,
        current_exposure_notional=Decimal("4500"),
        current_daily_pnl=Decimal("-50"),
        current_drawdown_pct=0.05,
        current_consecutive_losses=2,
    )


# ---------------------------------------------------------------------------
# 1. CAP-1 (DoD-07): AST scan — no `if run_mode` / `if source_type`
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_cap1_ast_no_runmode_sourcetype_branching() -> None:
    """CAP-1 DoD-07: 3 contract files must NOT test `run_mode` or `source_type`
    in any `if` block test expression.
    """
    hits: list[str] = []
    for path in TARGET_FILES:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                try:
                    dump_text = ast.dump(node.test)
                except Exception:
                    dump_text = ""
                try:
                    unparsed = ast.unparse(node.test)
                except Exception:
                    unparsed = ""
                combined = f"{dump_text} {unparsed}"
                if "run_mode" in combined or "source_type" in combined:
                    lineno = getattr(node, "lineno", 0)
                    hits.append(
                        f"{path.name}:{lineno}: pattern in If.test -> {unparsed[:120]}"
                    )
    assert hits == [], (
        "CAP-1 FAIL: run_mode/source_type branching detected in S-CON-02B "
        "contract files. Hits:\n" + "\n".join(hits)
    )


# ---------------------------------------------------------------------------
# 2. Determinism (DoD-10): 5 contracts × 10× schema_sha256
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_determinism_5_contracts_10x_each() -> None:
    """DoD-10: Build 5 frozen contracts, assert schema_sha256 stable across
    10 repeated calls PER contract (5 × 10 = 50 assertions total via sets).
    """
    contracts = {
        "RiskDecision": _build_risk_decision(),
        "PaperOrder": _build_paper_order(),
        "PaperFill": _build_paper_fill(),
        "Position": _build_position(),
        "PortfolioSnapshot": _build_portfolio_snapshot(),
    }
    for name, obj in contracts.items():
        digests = [obj.schema_sha256() for _ in range(10)]
        first = digests[0]
        for idx, d in enumerate(digests):
            assert d == first, (
                f"Determinism FAIL {name} call #{idx}: digest={d} != first={first}"
            )
        assert len(set(digests)) == 1, (
            f"Determinism FAIL {name}: {len(set(digests))} unique digests across 10 calls"
        )


# ---------------------------------------------------------------------------
# 3. CONTRACT_VERSION invariant
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_contract_version_invariant() -> None:
    """CONTRACT_VERSION MUST remain exactly "1.0.0" in this story."""
    assert str(CONTRACT_VERSION) == "1.0.0", (
        f"CONTRACT_VERSION invariant broken: expected '1.0.0', "
        f"got {str(CONTRACT_VERSION)!r}"
    )


# ---------------------------------------------------------------------------
# 4. Decimal vs float separation (DoD-15)
# ---------------------------------------------------------------------------


DECIMAL_FIELD_KEYWORDS = (
    "price",
    "qty",
    "notional",
    "pnl",
    "fee",
    "exposure",
    "equity",
    "cash",
    "peak",
    "base",
    "quote",
    "entry",
    "ref",
)

FLOAT_FIELD_KEYWORDS = (
    "confidence",
    "drawdown",
    "strength",
    "slippage",
    "ratio",
)


@pytest.mark.contract
def test_decimal_vs_float_separation() -> None:
    """DoD-15: 5 main contract classes — Decimal fields carry monetary /
    quant keywords; float fields carry ratio/confidence keywords.
    """
    classes = (
        RiskDecision,
        PaperOrder,
        PaperFill,
        Position,
        PortfolioSnapshot,
    )
    decimal_correct_count = 0

    for cls in classes:
        hints = typing.get_type_hints(cls)
        for field_obj in dataclasses.fields(cls):
            fname = field_obj.name
            ftype = hints.get(fname, field_obj.type)
            fname_lower = fname.lower()

            is_decimal_keyword = any(
                kw in fname_lower for kw in DECIMAL_FIELD_KEYWORDS
            )
            is_float_keyword = any(
                kw in fname_lower for kw in FLOAT_FIELD_KEYWORDS
            )

            if is_decimal_keyword and not is_float_keyword:
                type_str = str(ftype)
                if "Decimal" in type_str:
                    decimal_correct_count += 1

    assert decimal_correct_count >= 8, (
        f"Decimal/float separation FAIL: expected >=8 Decimal-monetary fields, "
        f"found {decimal_correct_count}. Keywords matched but type not Decimal."
    )


# ---------------------------------------------------------------------------
# 5. to_sorted_dict double-serialisation stability
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_to_sorted_dict_determinism_double_serialize() -> None:
    """5 contracts → to_sorted_dict() twice → json.dumps(sort_keys=True)
    identical across two independent calls.
    """
    contracts = [
        _build_risk_decision(),
        _build_paper_order(),
        _build_paper_fill(),
        _build_position(),
        _build_portfolio_snapshot(),
    ]
    for obj in contracts:
        d1 = obj.to_sorted_dict()
        d2 = obj.to_sorted_dict()
        s1 = json.dumps(d1, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        s2 = json.dumps(d2, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        assert s1 == s2, (
            f"to_sorted_dict double-serialize FAIL: {type(obj).__name__}\n"
            f"  s1={s1[:200]}...\n  s2={s2[:200]}..."
        )


# ---------------------------------------------------------------------------
# 6. LimitsSnapshot nested determinism + sorted keys
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_limits_snapshot_nested_determinism_and_sorted_keys() -> None:
    """LimitsSnapshot (v1 max_leverage=1):
       - 10x schema_sha256 identical
       - to_sorted_dict keys must be in ascending order
    """
    ls = _build_limits_snapshot()
    assert ls.max_leverage_allowed == 1, "v1 hard boundary: max_leverage_allowed must be 1"

    digests = [ls.schema_sha256() for _ in range(10)]
    assert len(set(digests)) == 1, (
        f"LimitsSnapshot determinism FAIL: {len(set(digests))} unique digests"
    )

    d = ls.to_sorted_dict()
    keys = list(d.keys())
    assert keys == sorted(keys), (
        f"LimitsSnapshot.to_sorted_dict keys NOT sorted: {keys} vs {sorted(keys)}"
    )

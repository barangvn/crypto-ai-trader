"""S-CON-02B integration tests — DoD-12 Single-Writer AST + DoD-13 Corr/Caus chain + backward-compat smoke import.

3 integration tests:
  1. DoD-12 Single-Writer AST scan — writer functions ONLY in simulation/portfolio
  2. DoD-13 7-link correlation/causation chain — StrategySignal → RiskDecision → PaperOrder → PaperFill → Position → PortfolioSnapshot (6 entities, 7 links counting corr_id)
  3. Regression smoke import — all __all__ names from app.contracts import cleanly
"""

from __future__ import annotations

import ast
import importlib
import pathlib
import re
from dataclasses import dataclass
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
    SignalDirection,
    StopPolicySpec,
    StrategySignal,
    TakeProfitPolicySpec,
    format_instant,
)


ROOT = pathlib.Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "app"

CORR_ID = "01J5CHAIN0000000000000001"


# ---------------------------------------------------------------------------
# Helpers — build the 7-link chain contracts with shared correlation_id
# ---------------------------------------------------------------------------


def _now() -> str:
    return format_instant()


def _build_signal() -> StrategySignal:
    return StrategySignal(
        strategy_id="trend_chain_v1",
        strategy_version="1.0.0",
        direction=SignalDirection.LONG,
        signal_strength=0.75,
        correlation_id=CORR_ID,
        causation_id="01J5CTX00000000000000001",
        supporting_feature_keys=["rsi", "macd"],
        supporting_regime_evidence={"bull": 0.7, "sideways": 0.3},
        entry_thesis="breakout above resistance",
        entry_price_ref=Decimal("45000.5"),
        stop_policy=StopPolicySpec(
            stop_type="fixed",
            stop_ref_price=Decimal("44000"),
            stop_bps=222.2,
        ),
        take_profit_policy=TakeProfitPolicySpec(
            tp_type="scale",
            tp_levels=[Decimal("46000"), Decimal("47500")],
            tp_bps=[222.2, 555.5],
        ),
        confidence=0.82,
        expected_edge_bps=45.0,
    )


def _build_risk_decision(signal: StrategySignal) -> RiskDecision:
    now = _now()
    return RiskDecision(
        decision_id="01J5DEC000000000000CHAIN",
        decision=RiskDecisionResult.APPROVED,
        reason_codes=["capital_ok", "sizing_ok", "limits_in_band"],
        position_sizing=PositionSizingSpec(
            base_qty=Decimal("0.1"),
            quote_qty=Decimal("4500.05"),
            notional=Decimal("4500.05"),
            method="signal_notional_percent",
        ),
        limits_snapshot=LimitsSnapshot(
            max_position_notional_per_symbol=Decimal("10000"),
            max_exposure_notional_total=Decimal("50000"),
            max_daily_loss_notional=Decimal("-500"),
            max_drawdown_pct=0.1,
            max_consecutive_losses=5,
            max_leverage_allowed=1,
            current_exposure_notional=Decimal("4500.05"),
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
        correlation_id=signal.correlation_id,
        causation_id=signal.causation_id.replace("CTX", "SIG"),
        stop_loss_ref=Decimal("44000"),
        take_profit_ref=Decimal("47500"),
        approval_chain=["risk_v1", "sizing_v1"],
    )


def _build_paper_order(decision: RiskDecision) -> PaperOrder:
    now = _now()
    return PaperOrder(
        paper_order_id="01J5ORD000000000000CHAIN",
        side=PaperOrderSide.BUY,
        order_type=PaperOrderType.LIMIT,
        requested_qty_base=Decimal("0.1"),
        policy_refs=PaperOrderPolicyRefs(
            risk_decision_id=decision.decision_id,
            strategy_id="trend_chain_v1",
            strategy_version="1.0.0",
        ),
        status=PaperOrderStatus.CREATED,
        created_at=now,
        updated_at=now,
        correlation_id=decision.correlation_id,
        causation_id=decision.decision_id,
        client_order_id="cli_chain_001",
        requested_price=Decimal("45000.5"),
        time_in_force=None,
    )


def _build_paper_fill(order: PaperOrder) -> PaperFill:
    now = _now()
    price = Decimal("45000.5")
    qty = Decimal("0.1")
    quote = price * qty
    return PaperFill(
        paper_fill_id="01J5FILL00000000000CHAIN",
        paper_order_id=order.paper_order_id,
        side=PaperOrderSide.BUY,
        fill_price=price,
        fill_qty_base=qty,
        fill_qty_quote=quote,
        fees_quote=Decimal("4.50005"),
        fill_ts=now,
        fill_model_version="fill_model_chain_v1",
        correlation_id=order.correlation_id,
        causation_id=order.paper_order_id,
        slippage_bps=0.8,
        latency_ms=8,
    )


def _build_position(fill: PaperFill) -> Position:
    now = _now()
    return Position(
        position_id="01J5POS000000000000CHAIN",
        symbol="BTC_USDT",
        side=PositionSide.LONG,
        base_qty=fill.fill_qty_base,
        avg_entry_price=fill.fill_price,
        current_price=Decimal("45500.0"),
        unrealized_pnl_quote=Decimal("49.95"),
        realized_pnl_quote=Decimal("0"),
        fees_quote=fill.fees_quote,
        opened_ts=now,
        last_updated_ts=now,
        open_refs=[fill.paper_fill_id],
        correlation_id=fill.correlation_id,
        causation_id=fill.paper_fill_id,
        stop_loss_ref=Decimal("44000"),
        take_profit_ref=Decimal("47500"),
    )


def _build_portfolio_snapshot(position: Position) -> PortfolioSnapshot:
    now = _now()
    return PortfolioSnapshot(
        snapshot_id="01J5SNAP00000000000CHAIN",
        account_ref="paper_account_chain",
        ts=now,
        cash_quote=Decimal("95495.44995"),
        equity_quote=Decimal("100045.4"),
        realized_pnl_quote_24h=Decimal("45.0"),
        unrealized_pnl_quote=position.unrealized_pnl_quote,
        fees_quote_total=Decimal("15.50005"),
        exposure_notional=Decimal("4550.0"),
        drawdown_pct=0.012,
        peak_equity_quote=Decimal("101250.0"),
        correlation_id=position.correlation_id,
        causation_id=position.position_id,
        positions_snapshot=[position],
    )


# ---------------------------------------------------------------------------
# 1. DoD-12 Single-Writer AST scan (AD-7/13/24)
# ---------------------------------------------------------------------------


WRITER_PATTERN = re.compile(
    r"^(save_|write_|persist_|insert_).*(position|portfolio|fill|paper_order)$"
)


def test_dod12_single_writer_ast_scan() -> None:
    """DoD-12 Single-Writer AST scan (AD-7/13/24):

    Search entire app/ folder recursively for .py files. Walk AST collecting
    FunctionDef.name tokens. If any name matches writer-pattern regexp, the
    defining file MUST live under app/simulation/portfolio/ (path contains
    "simulation" AND "portfolio" or sim path segment simulation/portfolio).

    0 matching functions == 0 violations == PASS (writers don't exist yet,
    that's fine — single-writer means ONLY simulator writes, no writer at
    all is trivially compliant).
    """
    violations: list[str] = []
    total_writer_hits = 0

    for py_path in APP_DIR.rglob("*.py"):
        try:
            source = py_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        rel = py_path.relative_to(ROOT).as_posix().lower()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                fname = node.name.lower()
                if WRITER_PATTERN.match(fname):
                    total_writer_hits += 1
                    in_sim_portfolio = (
                        "simulation" in rel and "portfolio" in rel
                    ) or "simulation/portfolio" in rel
                    if not in_sim_portfolio:
                        violations.append(
                            f"{py_path.relative_to(ROOT)}:{node.lineno} "
                            f"function={node.name!r} — writer outside simulation/portfolio"
                        )

    assert violations == [], (
        f"Single-Writer (DoD-12) FAIL — {len(violations)} writer functions "
        f"outside app/simulation/portfolio/ (total writers found: "
        f"{total_writer_hits}). Violations:\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# 2. DoD-13 Correlation / Causation 7-Halka Zincir
# ---------------------------------------------------------------------------


def test_dod13_correlation_causation_7_link_chain() -> None:
    """DoD-13 7-Halka Zincir (Correlation + Causation):

    Build 6 contract entities with the SAME correlation_id ULID-like string.
    Assert:
      (a) All 6 correlation_id fields are EQUAL strings.
      (b) Each downstream causation_id == upstream entity's primary ID
          (chain continuity: signal → decision → order → fill → position → snapshot).
      (c) PaperOrder.policy_refs.risk_decision_id == decision.decision_id
          (CAP-4 explicit link beyond causation).
    """
    signal = _build_signal()
    decision = _build_risk_decision(signal)
    order = _build_paper_order(decision)
    fill = _build_paper_fill(order)
    position = _build_position(fill)
    snapshot = _build_portfolio_snapshot(position)

    all_entities = [signal, decision, order, fill, position, snapshot]

    corr_ids = [e.correlation_id for e in all_entities]
    assert len(set(corr_ids)) == 1, (
        "DoD-13 Chain FAIL: correlation_id NOT uniform across 6 entities. "
        f"Unique values: {sorted(set(corr_ids))}"
    )
    assert all(c == CORR_ID for c in corr_ids), (
        f"DoD-13 Chain FAIL: expected corr_id={CORR_ID!r}"
    )

    assert decision.causation_id == signal.causation_id.replace("CTX", "SIG"), (
        "Chain link 1: RiskDecision.causation_id should trace to signal-level id"
    )
    assert order.causation_id == decision.decision_id, (
        "Chain link 2: PaperOrder.causation_id MUST equal RiskDecision.decision_id"
    )
    assert order.policy_refs.risk_decision_id == decision.decision_id, (
        "CAP-4 link: PaperOrder.policy_refs.risk_decision_id MUST equal "
        "RiskDecision.decision_id (separate from causation_id field)"
    )
    assert fill.causation_id == order.paper_order_id, (
        "Chain link 3: PaperFill.causation_id MUST equal PaperOrder.paper_order_id"
    )
    assert position.causation_id == fill.paper_fill_id, (
        "Chain link 4: Position.causation_id MUST equal PaperFill.paper_fill_id"
    )
    assert snapshot.causation_id == position.position_id, (
        "Chain link 5: PortfolioSnapshot.causation_id MUST equal Position.position_id"
    )

    assert fill.paper_order_id == order.paper_order_id, (
        "PaperFill.paper_order_id back-ref should match order"
    )
    assert len(position.open_refs) >= 1 and fill.paper_fill_id in position.open_refs, (
        "Position.open_refs should contain PaperFill.paper_fill_id"
    )
    if snapshot.positions_snapshot is not None:
        assert len(snapshot.positions_snapshot) >= 1
        assert snapshot.positions_snapshot[0].position_id == position.position_id


# ---------------------------------------------------------------------------
# 3. Regression smoke import — all __all__ names
# ---------------------------------------------------------------------------


def test_regression_smoke_import_all_contract_exports() -> None:
    """Regression smoke import: From app.contracts.__all__, import EVERY
    public name listed. Ensure ImportError count is exactly 0.

    This verifies:
      - Backward-compat (older exports still resolvable)
      - New S-CON-02A + S-CON-02B exports are properly wired in __init__.py
      - No circular-import regressions at module-load time
    """
    contracts_module = importlib.import_module("app.contracts")
    all_names = getattr(contracts_module, "__all__", [])
    assert len(all_names) >= 30, (
        f"__all__ unexpectedly small ({len(all_names)} names) — regression in __init__.py"
    )

    import_failures: list[str] = []
    for name in all_names:
        try:
            obj = getattr(contracts_module, name)
            if obj is None:
                import_failures.append(f"{name} → getattr returned None")
        except AttributeError as exc:
            import_failures.append(f"{name} → AttributeError: {exc}")
        except ImportError as exc:
            import_failures.append(f"{name} → ImportError: {exc}")
        except Exception as exc:  # noqa: BLE001 — capture any module-level issue
            import_failures.append(f"{name} → {type(exc).__name__}: {exc}")

    assert import_failures == [], (
        f"Contract export smoke import FAIL — {len(import_failures)} of "
        f"{len(all_names)} __all__ names broken:\n" + "\n".join(import_failures)
    )

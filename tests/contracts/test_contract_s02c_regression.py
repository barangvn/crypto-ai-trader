from __future__ import annotations

import ast
import os
import re
import pytest
from decimal import Decimal

from app.contracts import (
    StrategySignal,
    StrategyContext,
    SignalDirection,
    StopPolicySpec,
    TakeProfitPolicySpec,
    OpportunityScore,
    RiskDecision,
    RiskDecisionResult,
    PositionSizingSpec,
    LimitsSnapshot,
    KillSwitchStateSpec,
    PaperOrder,
    PaperOrderSide,
    PaperOrderType,
    PaperOrderStatus,
    TimeInForce,
    PaperOrderPolicyRefs,
    PaperFill,
    Position,
    PositionSide,
    PortfolioSnapshot,
    Symbol,
    format_instant,
    __all__,
    CONTRACT_VERSION,
    ClockRef,
    CanonicalEventEnvelope,
    QualityFlags,
    RunMode,
    SourceType,
    SchemaRef,
    ContractVersion,
)

from app.contracts import (
    ModelVersion,
    ModelLifecycleStatus,
    ModelPurposeEnum,
    DatasetKindEnum,
    CCWinnerEnum,
    TrainingDataRange,
    ModelCompatibilityRef,
    PromotionGateResult,
    ModelRef,
    ModelEvaluation,
    ModelLifecycleTransition,
    ChampionChallengerEvaluation,
)


# ---------------------------------------------------------------------------
# Proje kök
# ---------------------------------------------------------------------------


_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

_OPPORTUNITY_PY = os.path.join(_PROJECT_ROOT, "app", "contracts", "opportunity.py")
_MODEL_PY = os.path.join(_PROJECT_ROOT, "app", "contracts", "model.py")

_DECISIONING = os.path.join(_PROJECT_ROOT, "app", "decisioning")
_BACKTEST = os.path.join(_PROJECT_ROOT, "app", "simulation", "backtest") if os.path.isdir(
    os.path.join(_PROJECT_ROOT, "app", "simulation", "backtest")
) else None
_RISK = os.path.join(_PROJECT_ROOT, "app", "risk")


def _read(p: str) -> str:
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# C-48: 7/7 Corr/Caus Zinciri (EN ÖNEMLİ ENTEGRASYON TESTİ)
# StrategySignal → OpportunityScore → RiskDecision → PaperOrder → PaperFill → Position → PortfolioSnapshot
# Uniform correlation_id = COR_001. 6 assertion causation zinciri.
# KANONİK S-CON-02A / S-CON-02B fixture alan isimleri kullanılır.
# ---------------------------------------------------------------------------


def test_C48_7_link_correlation_causation_chain_integration():
    COR = "COR_001_FULL_7_LINK_CHAIN"
    now = format_instant()
    # StrategySignal ID field yoktur; parent referansı olarak benzersiz bir key kullanılır
    SS_PARENT_REF = "SS_PARENT_SIGNAL_REF_001"

    # 1. StrategySignal (link 1) — KANONİK: _make_signal fixture
    ss = StrategySignal(
        strategy_id="trend_following",
        strategy_version="1.0.0",
        direction=SignalDirection.LONG,
        signal_strength=0.9,
        entry_thesis="breakout confirmed",
        entry_price_ref=Decimal("25000.00"),
        stop_policy=StopPolicySpec(
            stop_type="fixed", stop_ref_price=Decimal("24500"), stop_bps=200.0
        ),
        take_profit_policy=TakeProfitPolicySpec(
            tp_type="scale",
            tp_levels=[Decimal("26000"), Decimal("27500")],
            tp_bps=[400.0, 1000.0],
        ),
        confidence=0.88,
        expected_edge_bps=18.0,
        supporting_feature_keys=["feat_1", "feat_2"],
        supporting_regime_evidence={"bull": 0.85},
        correlation_id=COR,
        causation_id=SS_PARENT_REF,
    )
    assert ss.correlation_id == COR
    assert ss.signal_strength == 0.9

    # 2. OpportunityScore (link 2) — causation = SS_PARENT_REF
    OS_ID = "OS_000002"
    os_inst = OpportunityScore(
        score_id=OS_ID,
        score_total=0.83,
        confidence=0.80,
        actionable=True,
        reject_reasons=[],
        score_components={"trend": 0.7, "momentum": 0.9, "value": 0.6},
        expected_edge_bps=17.5,
        expected_cost_bps=4.1,
        symbol_ref="BTC_USDT",
        regime_ref="bull",
        strategy_ref="trend_following@1.0.0",
        policy_version="opp-policy@v1",
        correlation_id=COR,
        causation_id=SS_PARENT_REF,  # zincir 1
        created_ts="2026-08-22T00:00:00.000Z",
    )
    assert os_inst.correlation_id == COR
    assert os_inst.causation_id == SS_PARENT_REF

    # 3. RiskDecision (link 3) — KANONİK: _make_valid_rd fixture
    RD_ID = "RD_000003"
    limits = LimitsSnapshot(
        max_position_notional_per_symbol=Decimal("1000"),
        max_exposure_notional_total=Decimal("5000"),
        max_daily_loss_notional=Decimal("-500"),
        max_drawdown_pct=0.10,
        max_consecutive_losses=5,
        max_leverage_allowed=1,
        current_exposure_notional=Decimal("0"),
        current_daily_pnl=Decimal("0"),
        current_drawdown_pct=0.0,
        current_consecutive_losses=0,
    )
    ks = KillSwitchStateSpec(
        global_kill=False,
        per_symbol=dict([(Symbol("BTC_USDT"), False)]),
        reason=None,
    )
    rd = RiskDecision(
        decision_id=RD_ID,
        decision=RiskDecisionResult.APPROVED,
        reason_codes=["approved_within_limits"],
        position_sizing=PositionSizingSpec(
            base_qty=Decimal("0.001"),
            quote_qty=Decimal("25.00"),
            notional=Decimal("25.00"),
            method="fixed_notional_25",
        ),
        limits_snapshot=limits,
        kill_switch_state=ks,
        valid_until="2026-08-22T00:05:00.000Z",
        correlation_id=COR,
        causation_id=OS_ID,  # zincir 2
        stop_loss_ref=None,
        take_profit_ref=None,
        approval_chain=["risk_engine_v1"],
    )
    assert rd.correlation_id == COR
    assert rd.causation_id == OS_ID

    # 4. PaperOrder (link 4) — KANONİK: _make_valid_order fixture
    PO_ID = "PO_000004_PAPER_ORDER"
    po = PaperOrder(
        paper_order_id=PO_ID,
        side=PaperOrderSide.BUY,
        order_type=PaperOrderType.MARKET,
        requested_qty_base=Decimal("0.001"),
        policy_refs=PaperOrderPolicyRefs(
            RD_ID,
            "trend_following",
            "1.0.0",
        ),
        status=PaperOrderStatus.CREATED,
        created_at="2026-08-22T00:00:00.000Z",
        updated_at="2026-08-22T00:00:00.000Z",
        correlation_id=COR,
        causation_id=RD_ID,  # zincir 3
        client_order_id=None,
        requested_price=None,
        time_in_force=None,
    )
    assert po.correlation_id == COR
    assert po.causation_id == RD_ID

    # 5. PaperFill (link 5) — KANONİK: _make_valid_fill fixture
    PF_ID = "PF_000005_PAPER_FILL"
    pf = PaperFill(
        side=PaperOrderSide.BUY,
        fill_price=Decimal("25000.00"),
        fill_qty_base=Decimal("0.001"),
        fill_qty_quote=Decimal("25.00"),
        fees_quote=Decimal("0.05"),
        fill_ts="2026-08-22T00:00:01.000Z",
        fill_model_version="fill_simple_v1.0.0",
        paper_fill_id=PF_ID,
        paper_order_id=PO_ID,
        correlation_id=COR,
        causation_id=PO_ID,  # zincir 4
        slippage_bps=2.5,
        latency_ms=10,
    )
    assert pf.correlation_id == COR
    assert pf.causation_id == PO_ID

    # 6. Position (link 6) — KANONİK: _make_valid_position fixture
    PS_ID = "POS_000006_POSITION"
    ps = Position(
        position_id=PS_ID,
        symbol="BTC_USDT",
        side=PositionSide.LONG,
        base_qty=Decimal("0.001"),
        avg_entry_price=Decimal("25000.00"),
        current_price=Decimal("25000.00"),
        unrealized_pnl_quote=Decimal("0"),
        realized_pnl_quote=Decimal("0"),
        fees_quote=Decimal("0.05"),
        opened_ts="2026-08-22T00:00:01.000Z",
        last_updated_ts="2026-08-22T00:00:01.000Z",
        open_refs=["01J5OPENREF_C48_001"],
        correlation_id=COR,
        causation_id=PF_ID,  # zincir 5
        stop_loss_ref=None,
        take_profit_ref=None,
    )
    assert ps.correlation_id == COR
    assert ps.causation_id == PF_ID

    # 7. PortfolioSnapshot (link 7) — KANONİK: _make_valid_snapshot fixture
    PORT_ID = "PORT_SNAP_000007"
    port = PortfolioSnapshot(
        snapshot_id=PORT_ID,
        account_ref="paper_main",
        ts="2026-08-22T00:00:01.000Z",
        cash_quote=Decimal("9974.95"),
        equity_quote=Decimal("10000.00"),
        realized_pnl_quote_24h=Decimal("0"),
        unrealized_pnl_quote=Decimal("0"),
        fees_quote_total=Decimal("0.05"),
        exposure_notional=Decimal("25.00"),
        drawdown_pct=0.0,
        peak_equity_quote=Decimal("10000.00"),
        correlation_id=COR,
        causation_id=PS_ID,  # zincir 6
        positions_snapshot=[ps],
    )
    assert port.correlation_id == COR
    assert port.causation_id == PS_ID

    # ===== 7 ADET ZİNCİR ASSERTİYONU (1 corr uniform + 6 parent causation) =====
    all_corr = {ss.correlation_id, os_inst.correlation_id, rd.correlation_id,
                po.correlation_id, pf.correlation_id, ps.correlation_id, port.correlation_id}
    assert all_corr == {COR}, "7/7 zincir: TÜM entity correlation_id AYNI olmalı"

    assert os_inst.causation_id == SS_PARENT_REF, "2/7 zincir: OpportunityScore.causation_id == StrategySignal parent ref"
    assert rd.causation_id == OS_ID, "3/7 zincir: RiskDecision.causation_id == OpportunityScore.score_id"
    assert po.causation_id == RD_ID, "4/7 zincir: PaperOrder.causation_id == RiskDecision.decision_id"
    assert pf.causation_id == PO_ID, "5/7 zincir: PaperFill.causation_id == PaperOrder.paper_order_id"
    assert ps.causation_id == PF_ID, "6/7 zincir: Position.causation_id == PaperFill.paper_fill_id"
    assert port.causation_id == PS_ID, "7/7 zincir: PortfolioSnapshot.causation_id == Position.position_id"


# ---------------------------------------------------------------------------
# C-49 / C-50: Decimal vs Float Ayrımı — type hints + field değerleri kontrol
# ---------------------------------------------------------------------------


def test_C49_Decimal_Float_strict_separation_model_fields():
    # ModelEvaluation.metrics type annotations (alanlarda tutulan değerler zaten enforce):
    # total_fees_quote DECIMAL, avg_slippage_bps FLOAT
    good_metrics = {
        "return_pct": Decimal("10"),
        "max_drawdown_pct": 0.05,
        "sharpe_ratio": 1.5,
        "sortino_ratio": 2.0,
        "profit_factor": 1.5,
        "total_fees_quote": Decimal("100"),
        "avg_slippage_bps": 2.5,
        "trade_count": 50,
        "regime_coverage_count": 3,
        "window_days": 100,
        "oos_flag": True,
    }
    ev = ModelEvaluation(
        eval_id="EVAL_TYPEHINT_01",
        model_id="m1",
        model_version="1",
        dataset_kind=DatasetKindEnum.OUT_OF_SAMPLE,
        metrics=good_metrics,
        evaluation_ts="2026-08-22T00:00:00.000Z",
        thresholds_config_version="t1",
        evaluation_window_days=100,
        oos_flag=True,
        paper_flag=False,
        correlation_id="COR_TYPEHINT_01",
        causation_id="CAU_TYPEHINT_01",
    )
    # fees Decimal type check:
    assert isinstance(ev.metrics["total_fees_quote"], Decimal), (
        "DoD-15 C-49 FAIL: ModelEvaluation.metrics.total_fees_quote Decimal OLMALI"
    )
    assert isinstance(ev.metrics["avg_slippage_bps"], float), (
        "DoD-15 C-49 FAIL: ModelEvaluation.metrics.avg_slippage_bps float OLMALI"
    )

    # Yanlış tip — total_fees float ise RAISE:
    bad_metrics = dict(good_metrics)
    bad_metrics["total_fees_quote"] = 100.0  # float, Decimal değil — RAISE
    bad_metrics["return_pct"] = 10.0  # float, Decimal değil — RAISE
    with pytest.raises(Exception):
        ModelEvaluation(
            eval_id="EVAL_TYPEHINT_BAD",
            model_id="m1", model_version="1",
            dataset_kind=DatasetKindEnum.IN_SAMPLE,
            metrics=bad_metrics,
            evaluation_ts="2026-08-22T00:00:00.000Z",
            thresholds_config_version="t1",
            evaluation_window_days=100,
            oos_flag=False,
            paper_flag=False,
            correlation_id="COR_BAD", causation_id="CAU_BAD",
        )


def test_C50_Decimal_Float_opportunity_fields_float():
    # OpportunityScore — tüm skor/bps/cost fields FLOAT olmalı.
    os = OpportunityScore(
        score_id="SCORE_TYPE_01",
        score_total=0.5,       # float
        confidence=0.6,        # float
        actionable=True,
        reject_reasons=[],
        score_components={"c1": 0.5, "c2": 0.3},  # values float
        expected_edge_bps=5.5,
        expected_cost_bps=2.1,
        symbol_ref="BTC_USDT",
        regime_ref="r1",
        strategy_ref="s1",
        policy_version="p1",
        correlation_id="COR_TYPE_01",
        causation_id="CAU_TYPE_01",
        created_ts="2026-08-22T00:00:00.000Z",
    )
    assert isinstance(os.score_total, float)
    assert isinstance(os.confidence, float)
    assert isinstance(os.expected_edge_bps, float)
    assert isinstance(os.expected_cost_bps, float)
    for k, v in os.score_components.items():
        assert isinstance(v, float), f"score_components[{k}] must be float, got {type(v)}"


# ---------------------------------------------------------------------------
# C-51: Single-Writer / AD-7/13/24 — contract dosyaları ve backtest/risk klasörlerinde
#       model/opportunity writer fonksiyon isimleri 0 match.
# ---------------------------------------------------------------------------


def test_C51_single_writer_no_unauthorized_save_functions():
    forbidden_def = re.compile(
        r"def\s+(save_|write_|persist_|insert_).*(model_version|model_lifecycle|opportunity_score|evaluation|champion_challenger)"
    )
    # 1. Contract dosyaları: model + opportunity — kesin 0 match (contractlar SADECE typed schema — writer YOK)
    for fpath in (_OPPORTUNITY_PY, _MODEL_PY):
        src = _read(fpath)
        matches = forbidden_def.findall(src)
        assert matches == [], f"Single-Writer violated in {fpath}: FOUND writers {matches}"

    # 2. Eğer risk klasörü varsa kontrol et:
    if os.path.isdir(_RISK):
        for root, _dirs, files in os.walk(_RISK):
            for name in files:
                if not name.endswith(".py"):
                    continue
                p = os.path.join(root, name)
                src = _read(p)
                m = forbidden_def.findall(src)
                assert m == [], f"Single-Writer violated in RISK {p}: FOUND {m}"
    # 3. Backtest klasörü varsa:
    if _BACKTEST and os.path.isdir(_BACKTEST):
        for root, _dirs, files in os.walk(_BACKTEST):
            for name in files:
                if not name.endswith(".py"):
                    continue
                p = os.path.join(root, name)
                src = _read(p)
                m = forbidden_def.findall(src)
                assert m == [], f"Single-Writer violated in BACKTEST {p}: FOUND {m}"


# ---------------------------------------------------------------------------
# C-53: Import smoke getattr ile TÜM isimler — Import Error YOK. __all__ len >= 42+13 = 55
# ---------------------------------------------------------------------------


def test_C53_all_names_import_smoke_getattr():
    import app.contracts as contracts

    # S-CON-02B 44 isim + S-CON-02C 13 yeni isim = 57 bekleniyor (en az 55)
    assert len(__all__) >= 55, f"__all__ toplam isim: {len(__all__)} (>= 55 bekleniyordu)"

    errors: list[str] = []
    for name in __all__:
        if not hasattr(contracts, name):
            errors.append(name)
    assert errors == [], f"Import smoke getattr FAIL — {len(errors)} isim Import Error: {errors[:10]}"

    # CONTRACT_VERSION hala 1.0.0 (NO BUMP)
    assert str(CONTRACT_VERSION) == "1.0.0", (
        f"CONTRACT_VERSION NO BUMP kuralı ihlali — '1.0.0' bekleniyordu, bulundu: {CONTRACT_VERSION}"
    )


# ---------------------------------------------------------------------------
# Ek: pyproject.toml dependencies BOŞ — HİÇ değişim YOK (DoD-04)
# ---------------------------------------------------------------------------


def test_pyproject_dependencies_empty_unchanged():
    pyproject_path = os.path.join(_PROJECT_ROOT, "pyproject.toml")
    src = _read(pyproject_path)
    # dependencies = [] section geçmeli
    assert "dependencies = []" in src, (
        "pyproject.toml dependencies=[] kuralı ihlal edildi — stdlib-only kuralı"
    )

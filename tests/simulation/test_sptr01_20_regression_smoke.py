from __future__ import annotations

import pytest


_STORY_MODULES_IMPORT_MAP = {
    "S-RDH-01 replay-data-pipeline": None,
    "S-RDH-02 replay-bundle-registry": None,
    "S-PLN-01 typed event bus": "app.platform.event_bus",
    "S-CON-02A canonical contracts feature/regime/str": "app.contracts",
    "S-CON-02B canonical contracts paper": "app.contracts.paper",
    "S-CON-02C canonical contracts opportunity": "app.contracts.types",
    "S-FEA-01 feature engine": None,
    "S-REG-01 regime detection": None,
    "S-STR-01 strategy engine": None,
    "S-OPP-01 opportunity scoring": None,
    "S-RSK-01 risk engine": None,
    "S-RSK-02 risk gate enforcement": None,
}


class TestRegressionSmoke:
    def test_20_01_platform_eventbus_imports(self):
        from app.platform.event_bus import (
            InMemoryTypedEventBus,
            DeadLetterRecord,
        )
        assert InMemoryTypedEventBus is not None
        assert DeadLetterRecord is not None

    def test_20_02_contracts_paper_imports(self):
        from app.contracts.paper import (
            PaperOrder,
            PaperFill,
            PaperOrderPolicyRefs,
            PaperOrderSide,
            PaperOrderStatus,
        )
        from app.contracts.risk import RiskDecision
        assert PaperFill is not None
        assert PaperOrder is not None
        assert RiskDecision is not None

    def test_20_03_contracts_canonical_imports(self):
        from app.contracts.canonical import (
            QualityFlags,
            CanonicalEventEnvelope,
            SchemaRef,
        )
        assert QualityFlags is not None
        assert CanonicalEventEnvelope is not None

    def test_20_04_contracts_market_imports(self):
        from app.contracts.market import (
            MarketTick,
            Candle,
            OrderBookSnapshot,
        )
        assert MarketTick is not None
        assert Candle is not None
        assert OrderBookSnapshot is not None

    def test_20_05_sim_module_public_api(self):
        from app.simulation import (
            PaperExecutionSimulator,
            FillAssumptionsConfig,
            PaperFillResult,
            PaperFillRejectReason,
            FILL_MODEL_VERSION,
            PipelineReferenceData,
            build_pipeline_reference_data,
            deterministic_latency_ms,
            select_reference_price,
            apply_spread_cost,
            apply_slippage_directional,
            calculate_fee_quote,
            calculate_fill_quantities,
        )
        assert PaperExecutionSimulator is not None
        assert FILL_MODEL_VERSION == "1.0.0"

    def test_20_06_upstream_story_modules_existence_smoke(self):
        import importlib
        for story, mod_path in _STORY_MODULES_IMPORT_MAP.items():
            if mod_path is None:
                continue
            try:
                m = importlib.import_module(mod_path)
            except Exception as e:
                pytest.fail(f"{story} import {mod_path} fail: {e}")
            assert m is not None, story

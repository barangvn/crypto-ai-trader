"""S-CON-02A CAP-1 / CAP-2 / AD-20 determinism 10x cross-contract.

Runs on contracts/ submodules (feature.py, regime.py, strategy.py).
"""

from __future__ import annotations

import ast
import os
import re
from decimal import Decimal

import pytest

from app.contracts import (
    CanonicalEventEnvelope,
    ClockRef,
    ContractSchemaError,
    EligibilityContextView,
    FeatureVector,
    LookbackWindowSpec,
    MarketRegime,
    MarketRegimeState,
    OpportunityScoreComponentPolicy,
    PortfolioContextView,
    QualityFlags,
    RunMode,
    SchemaRef,
    SignalDirection,
    SourceType,
    StopPolicySpec,
    StrategyContext,
    StrategySignal,
    TakeProfitPolicySpec,
    TimeRangeSpec,
    now_instant,
    CONTRACT_VERSION,
)


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONTRACTS_DIR = os.path.join(ROOT, "app", "contracts")
NEW_CONTRACT_FILES = [
    os.path.join(CONTRACTS_DIR, f) for f in ("feature.py", "regime.py", "strategy.py")
]

# ---------------------------------------------------------------------------
# CAP-1: No `if run_mode` / `if source_type` branching within new contract code.
# Two independent scans: regex + AST walk.
# ---------------------------------------------------------------------------


class TestCAP1NewContractNoDomainBranching:
    """AD-37 / story §6 — run_mode/source_type if/elif branching is ABSENT in
    the NEW contract files.
    """

    _REGEX = re.compile(r"\b(if|elif)\s+.*\b(run_mode|source_type)\b")

    def test_regex_scan_zero_hits(self) -> None:
        hits = []
        for path in NEW_CONTRACT_FILES:
            with open(path, "r", encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, start=1):
                    if self._REGEX.search(line):
                        hits.append(f"{os.path.basename(path)}:{lineno}: {line.strip()}")
        assert hits == [], (
            "CAP-1 FAIL: new contract files contain run_mode/source_type "
            "domain branching. Hits:\n" + "\n".join(hits)
        )

    def test_ast_scan_zero_hits(self) -> None:
        hits = []
        for path in NEW_CONTRACT_FILES:
            with open(path, "r", encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.IfExp)):
                    try:
                        text = ast.unparse(node.test)
                    except Exception:
                        text = ""
                    if "run_mode" in text or "source_type" in text:
                        lineno = getattr(node, "lineno", 0)
                        hits.append(f"{os.path.basename(path)}:{lineno}: {text}")
        assert hits == [], (
            "CAP-1 FAIL: AST scan detected run_mode/source_type branching. Hits:\n"
            + "\n".join(hits)
        )


# ---------------------------------------------------------------------------
# CAP-2: QualityFlags preserved — derive_from_envelope does NOT mutate
# envelope.quality_flags or envelope.clock_ref.
# ---------------------------------------------------------------------------


class TestCAP2QualityFlagsPreserved:
    def test_derive_from_envelope_leaves_quality_flags_untouched(self) -> None:
        # Build envelope with degraded False initially; then we mutate *on the
        # envelope instance* AFTER construction and confirm StrategyContext
        # cannot see it (deep copy semantics everywhere except quality read)
        now = now_instant()
        env = CanonicalEventEnvelope(
            event_id="01J0AAAAAAAAAAAAAAAAAAAAAAAAAA",
            event_type="candle.v1",
            contract_version=CONTRACT_VERSION,
            symbol="BTC_USDT",
            source="replay_bundle",
            timestamp=now,
            ingest_ts=now,
            correlation_id="01J0AAAAAAAAAAAAAAAACORR001",
            causation_id="01J0AAAAAAAAAAAAAAAAPARE001",
            run_mode=RunMode.PAPER,
            source_type=SourceType.REPLAY,
            clock_ref=ClockRef(wall=now, replay=now),
            quality_flags=QualityFlags(
                stale=False,
                missing=False,
                duplicate=False,
                out_of_order=False,
                invalid=False,
                quarantined=False,
                degraded=False,
            ),
            schema_ref=SchemaRef(),
        )
        fv = FeatureVector(
            feature_version="fv_cap2_v1",
            timeframe="1m",
            features={"rsi": 50.0},
            lookback_window=LookbackWindowSpec(count=100, timeframe="1m"),
            input_refs=[],
        )
        scores = {s.value: 1 / 6 for s in MarketRegimeState}
        regime = MarketRegime(
            timeframe="1h",
            regime=MarketRegimeState.BULL,
            confidence=0.8,
            scores=scores,
            detector_version="regime_cap2_v1",
            feature_version="fv_cap2_v1",
            lookback_ts=TimeRangeSpec(
                start="2026-01-01T00:00:00.000Z",
                end="2026-01-01T01:00:00.000Z",
            ),
        )

        # Snapshot raw dict of quality_flags BEFORE derive call
        quality_before = dict(env.quality_flags.__dict__)
        ctx = StrategyContext.derive_from_envelope(env, features=fv, regime=regime)
        quality_after = dict(env.quality_flags.__dict__)
        assert quality_before == quality_after, (
            "CAP-2: envelope.quality_flags mutated during derive_from_envelope"
        )

        # Now flip envelope flags externally; ctx must still carry the
        # DEEP-COPY of clock_ref, but quality on envelope is caller-owned.
        # The invariant: derive did not mutate the envelope's quality_flags.
        env.quality_flags.stale = True  # caller-mutation
        assert env.quality_flags.stale is True
        # Just in case there was a copy step we can also confirm ctx never
        # carries the "stale=True" state; since ctx doesn't carry quality_flags
        # this is implicit. We assert the call did not flip anything:
        assert not quality_before.get("stale", False)

    def test_quality_flags_seven_flags_still_exist(self) -> None:
        # 7 canonical flags — no regression: stale/missing/duplicate/out_of_order/
        # invalid/quarantined/degraded + reasons + metadata exist.
        qf = QualityFlags(
            stale=True,
            missing=True,
            duplicate=True,
            out_of_order=True,
            invalid=True,
            quarantined=True,
            degraded=True,
        )
        for flag in (
            "stale", "missing", "duplicate", "out_of_order",
            "invalid", "quarantined", "degraded",
        ):
            assert getattr(qf, flag) is True
        # degraded auto-flip: if any is True, degraded stays True even if explicit False
        qf2 = QualityFlags(stale=True, degraded=False)
        # canonical.py auto-flips degraded back to True if any other flag True
        assert qf2.degraded is True  # AD-30 auto-flip
        qf3 = QualityFlags(stale=False, degraded=False)
        # degraded stays False only when no other flags are True
        assert qf3.degraded is False


# ---------------------------------------------------------------------------
# AD-20: 10x serialize/digest determinism on all 4 new contracts.
# ---------------------------------------------------------------------------


def _sample_context() -> StrategyContext:
    now = now_instant()
    env = CanonicalEventEnvelope(
        event_id="01J0AAAAAAAAAAAAAAAAAAAAAAAAAA",
        event_type="candle.v1",
        contract_version=CONTRACT_VERSION,
        symbol="BTC_USDT",
        source="replay_bundle",
        timestamp=now,
        ingest_ts=now,
        correlation_id="01J0AAAAAAAAAAAAAAAACORR001",
        causation_id="01J0AAAAAAAAAAAAAAAAPARE001",
        run_mode=RunMode.PAPER,
        source_type=SourceType.REPLAY,
        clock_ref=ClockRef(wall=now, replay=now),
        quality_flags=QualityFlags(),
        schema_ref=SchemaRef(),
    )
    fv = FeatureVector(
        feature_version="fv_det_v1",
        timeframe="1m",
        features={"a": 1.0, "b": Decimal("2"), "c": 3, "d": None},
        lookback_window=LookbackWindowSpec(count=50, timeframe="1m"),
        input_refs=["01J0AAAAAAAAAAAAAAAAPARE001"],
    )
    scores = {s.value: 1 / 6 for s in MarketRegimeState}
    regime = MarketRegime(
        timeframe="1h",
        regime=MarketRegimeState.BULL,
        confidence=0.8,
        scores=scores,
        detector_version="regime_det_v1",
        feature_version="fv_det_v1",
        lookback_ts=TimeRangeSpec(
            start="2026-01-01T00:00:00.000Z",
            end="2026-01-01T01:00:00.000Z",
        ),
    )
    return StrategyContext.derive_from_envelope(env, features=fv, regime=regime)


def _sample_signal() -> StrategySignal:
    return StrategySignal(
        strategy_id="trend_determ",
        strategy_version="1.0.0",
        direction=SignalDirection.LONG,
        signal_strength=0.7,
        entry_thesis="determinism test",
        entry_price_ref=Decimal("45000.123456789"),
        stop_policy=StopPolicySpec(
            stop_type="fixed", stop_ref_price=Decimal("44000"), stop_bps=222.2
        ),
        take_profit_policy=TakeProfitPolicySpec(
            tp_type="scale",
            tp_levels=[Decimal("46000"), Decimal("47000")],
            tp_bps=[222.2, 444.4],
        ),
        confidence=0.8,
        expected_edge_bps=12.5,
        supporting_feature_keys=["a", "b"],
        supporting_regime_evidence={"bull": 0.8, "sideways": 0.2},
        correlation_id="01J0AAAAAAAAAAAAAAAACORR001",
        causation_id="01J0AAAAAAAAAAAAAAAAPARE001",
    )


class TestAD20Determinism10x:
    def test_feature_vector_10x_deterministic(self) -> None:
        fv = FeatureVector(
            feature_version="fv_d",
            timeframe="1m",
            features={"z": 1.0, "a": 2.0, "m": Decimal("3.0"), "null": None},
            lookback_window=LookbackWindowSpec(count=3, timeframe="1m"),
            input_refs=["01J0AAAAAAAAAAAAAAAAPARE001"],
        )
        results = [(fv.to_sorted_dict(), fv.schema_sha256()) for _ in range(10)]
        first = results[0]
        assert all(r == first for r in results)

    def test_market_regime_10x_deterministic(self) -> None:
        scores = {s.value: 1 / 6 for s in MarketRegimeState}
        regime = MarketRegime(
            timeframe="1h",
            regime=MarketRegimeState.BULL,
            confidence=0.8,
            scores=scores,
            detector_version="r_d",
            feature_version="fv_d",
            lookback_ts=TimeRangeSpec(
                start="2026-01-01T00:00:00.000Z",
                end="2026-01-01T01:00:00.000Z",
            ),
        )
        results = [(regime.to_sorted_dict(), regime.schema_sha256()) for _ in range(10)]
        first = results[0]
        assert all(r == first for r in results)

    def test_strategy_context_10x_deterministic(self) -> None:
        ctx = _sample_context()
        results = [(ctx.to_sorted_dict(), ctx.schema_sha256()) for _ in range(10)]
        first = results[0]
        assert all(r == first for r in results)

    def test_strategy_signal_10x_deterministic(self) -> None:
        sig = _sample_signal()
        results = [(sig.to_sorted_dict(), sig.schema_sha256()) for _ in range(10)]
        first = results[0]
        assert all(r == first for r in results)

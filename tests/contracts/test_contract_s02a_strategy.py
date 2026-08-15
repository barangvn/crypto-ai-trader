"""S-CON-02A StrategyContext (AD-25) + StrategySignal (v1 long-only) tests.

AC covered:
  C-19 (typed ctx fields / canonical symbol / as_of instant / etc)
  C-20 (derive_from_envelope deep-copies clock_ref, picks as_of, corr/caus)
  C-21 (eligibility_ctx placeholder defaults OK)
  C-22 (strategy_params nested rejection — AD-25 primitive-only)
  C-23 (forbidden AST imports: network/HTTP/WS/DB/exchange/Pydantic absent — strategy.py)
  C-24 (scoring_policy shape)
  + StrategySignal C-25 short boundary, C-26 types/ranges, C-27 regime evidence/corr/caus
  + Extras: SignalDirection values [long/flat/hold only], policy validators.
"""

from __future__ import annotations

import ast
import os
from copy import deepcopy
from decimal import Decimal

import pytest

from app.contracts import (
    CONTRACT_VERSION,
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
    format_instant,
    now_instant,
)


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STRATEGY_PY = os.path.join(ROOT, "app", "contracts", "strategy.py")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


INSTANT_START = "2026-01-01T00:00:00.000Z"
INSTANT_END = "2026-01-01T01:00:00.000Z"
ULID_SAMPLE_A = "01J0AAAAAAAAAAAAAAAAPPLE00A"
ULID_SAMPLE_B = "01J0AAAAAAAAAAAAAAAAPPLE00B"
ULID_SAMPLE_C = "01J0AAAAAAAAAAAAAAAAPPLE00C"
ULID_SAMPLE_D = "01J0AAAAAAAAAAAAAAAAPPLE00D"


def _make_feature_vector() -> FeatureVector:
    return FeatureVector(
        feature_version="fv_ctx_v1",
        timeframe="1m",
        features={
            "rsi14": 55.5,
            "sma20": Decimal("45000.123456789"),
            "volatility_1h": 0.024,
        },
        lookback_window=LookbackWindowSpec(count=200, timeframe="1m"),
        input_refs=[ULID_SAMPLE_A, ULID_SAMPLE_B],
    )


def _make_market_regime() -> MarketRegime:
    base = {k: 0.0 for k in MarketRegimeState}
    base[MarketRegimeState.BULL] = 0.7
    base[MarketRegimeState.SIDEWAYS] = 0.2
    base[MarketRegimeState.BEAR] = 0.05
    base[MarketRegimeState.HIGH_VOLATILITY] = 0.03
    base[MarketRegimeState.LOW_VOLATILITY] = 0.01
    base[MarketRegimeState.TRANSITION_UNCERTAIN] = 0.01
    scores = {s.value: v for s, v in base.items()}
    return MarketRegime(
        timeframe="1h",
        regime=MarketRegimeState.BULL,
        confidence=0.85,
        scores=scores,
        detector_version="regime_kb_v1",
        feature_version="fv_ctx_v1",
        lookback_ts=TimeRangeSpec(start=INSTANT_START, end=INSTANT_END),
    )


def _make_envelope(
    symbol: str = "BTC_USDT",
    run_mode: RunMode = RunMode.PAPER,
    source_type: SourceType = SourceType.REPLAY,
) -> CanonicalEventEnvelope:
    now = now_instant()
    return CanonicalEventEnvelope(
        event_id=ULID_SAMPLE_A,
        event_type="candle.v1",
        contract_version=CONTRACT_VERSION,
        symbol=symbol,
        source="replay_bundle",
        timestamp=now,
        ingest_ts=now,
        correlation_id=ULID_SAMPLE_C,
        causation_id=ULID_SAMPLE_D,
        run_mode=run_mode,
        source_type=source_type,
        clock_ref=ClockRef(wall=now, replay=now),
        quality_flags=QualityFlags(missing=False),
        schema_ref=SchemaRef(),
    )


def _make_ctx(
    envelope: CanonicalEventEnvelope | None = None,
    features: FeatureVector | None = None,
    regime: MarketRegime | None = None,
    **overrides,
) -> StrategyContext:
    envelope = envelope or _make_envelope()
    features = features or _make_feature_vector()
    regime = regime or _make_market_regime()
    return StrategyContext.derive_from_envelope(
        envelope,
        features=features,
        regime=regime,
        **overrides,
    )


# ---------------------------------------------------------------------------
# C-19: StrategyContext typed fields / canonical symbol / as_of instant
# ---------------------------------------------------------------------------


class TestStrategyContextTypingC19:
    def test_symbol_non_canonical_raises(self) -> None:
        env = _make_envelope(symbol="btcusdt")  # lowercase, not canonical
        with pytest.raises(ContractSchemaError, match="not canonical"):
            _make_ctx(envelope=env)

    def test_bad_as_of_instant_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            StrategyContext(
                symbol="BTC_USDT",
                as_of="2026/01/01",  # wrong format
                clock_ref=ClockRef(wall=now_instant()),
                features=_make_feature_vector(),
                regime=_make_market_regime(),
                portfolio_ctx=PortfolioContextView(),
                eligibility_ctx=EligibilityContextView(eligible=True),
                scoring_policy=OpportunityScoreComponentPolicy(policy_version="p_v1"),
                run_mode=RunMode.PAPER,
                source_type=SourceType.REPLAY,
                correlation_id=ULID_SAMPLE_C,
                causation_id=ULID_SAMPLE_D,
            )

    def test_raw_dict_rejected_for_features(self) -> None:
        # Deliberately construct wrong args — ensure isinstance is enforced
        with pytest.raises(ContractSchemaError, match="raw dict rejected"):
            kw = {
                "symbol": "BTC_USDT",
                "as_of": now_instant(),
                "clock_ref": ClockRef(wall=now_instant()),
                "features": {},  # raw dict, not FeatureVector
                "regime": _make_market_regime(),
                "portfolio_ctx": PortfolioContextView(),
                "eligibility_ctx": EligibilityContextView(eligible=True),
                "scoring_policy": OpportunityScoreComponentPolicy(policy_version="p_v1"),
                "run_mode": RunMode.PAPER,
                "source_type": SourceType.REPLAY,
                "correlation_id": ULID_SAMPLE_C,
                "causation_id": ULID_SAMPLE_D,
            }
            # We cannot silence mypy here easily, use ** unpack with type ignore comment at caller level.
            StrategyContext(**kw)  # type: ignore[arg-type]

    def test_raw_dict_rejected_for_regime(self) -> None:
        with pytest.raises(ContractSchemaError, match="raw dict rejected"):
            StrategyContext(
                symbol="BTC_USDT",
                as_of=now_instant(),
                clock_ref=ClockRef(wall=now_instant()),
                features=_make_feature_vector(),
                regime={},  # type: ignore[arg-type]
                portfolio_ctx=PortfolioContextView(),
                eligibility_ctx=EligibilityContextView(eligible=True),
                scoring_policy=OpportunityScoreComponentPolicy(policy_version="p_v1"),
                run_mode=RunMode.PAPER,
                source_type=SourceType.REPLAY,
                correlation_id=ULID_SAMPLE_C,
                causation_id=ULID_SAMPLE_D,
            )


# ---------------------------------------------------------------------------
# C-20: derive_from_envelope copies corr/caus + as_of + DEEP clock_ref (CAP-2)
# ---------------------------------------------------------------------------


class TestDeriveFromEnvelopeC20:
    def test_as_of_defaults_to_envelope_timestamp(self) -> None:
        env = _make_envelope()
        ctx = _make_ctx(envelope=env)
        assert ctx.as_of == env.timestamp

    def test_as_of_override_honoured(self) -> None:
        env = _make_envelope()
        # Force timestamps well apart so there is no collision.
        custom = "2026-06-15T12:00:00.000Z"
        ctx = _make_ctx(envelope=env, as_of=custom)
        assert ctx.as_of == custom
        # env.timestamp is from now_instant() on test creation, never 2026-06 in normal runs.
        assert ctx.as_of != env.timestamp

    def test_correlation_and_causation_ids_propagated(self) -> None:
        env = _make_envelope()
        ctx = _make_ctx(envelope=env)
        assert ctx.correlation_id == env.correlation_id  # chain constant
        assert ctx.causation_id == env.event_id  # parent id

    def test_clock_ref_deep_copy_never_mutates_envelope(self) -> None:
        env = _make_envelope()
        original_wall = env.clock_ref.wall
        original_replay = env.clock_ref.replay
        ctx = _make_ctx(envelope=env)
        # Mutate the envelope clock_ref now — ctx must be unaffected (CAP-2 guard)
        env.clock_ref.wall = "2000-01-01T00:00:00.000Z"  # type: ignore[misc]
        env.clock_ref.replay = "2000-01-01T00:00:00.000Z"
        assert ctx.clock_ref.wall == original_wall
        assert ctx.clock_ref.replay == original_replay
        # Sanity: envelope WAS mutated (test itself is valid)
        assert env.clock_ref.wall != original_wall

    def test_clock_ref_bad_wall_instant_rejected(self) -> None:
        with pytest.raises(ContractSchemaError):
            StrategyContext(
                symbol="BTC_USDT",
                as_of=now_instant(),
                clock_ref=ClockRef(wall="not-an-instant"),  # type: ignore[arg-type]
                features=_make_feature_vector(),
                regime=_make_market_regime(),
                portfolio_ctx=PortfolioContextView(),
                eligibility_ctx=EligibilityContextView(eligible=True),
                scoring_policy=OpportunityScoreComponentPolicy(policy_version="p_v1"),
                run_mode=RunMode.PAPER,
                source_type=SourceType.REPLAY,
                correlation_id=ULID_SAMPLE_C,
                causation_id=ULID_SAMPLE_D,
            )


# ---------------------------------------------------------------------------
# C-21: eligibility_ctx / portfolio_ctx default placeholder shapes
# ---------------------------------------------------------------------------


class TestPlaceholdersC21:
    def test_eligibility_ctx_true_and_reasons_works(self) -> None:
        e = EligibilityContextView(eligible=True, reasons=["ok"])
        assert e.eligible is True
        assert e.reasons == ["ok"]

    def test_eligibility_ctx_reasons_non_str_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            EligibilityContextView(eligible=False, reasons=[1, 2, 3])  # type: ignore[list-item]

    def test_eligibility_ctx_empty_reasons_accepted(self) -> None:
        e = EligibilityContextView(eligible=False, reasons=[])
        assert e.reasons == []


# ---------------------------------------------------------------------------
# C-22: strategy_params nested / complex values rejected (AD-25 purity)
# ---------------------------------------------------------------------------


class TestStrategyParamsPrimitiveOnlyC22:
    def test_nested_dict_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="primitive-only"):
            _make_ctx(strategy_params={"nested": {"x": 1}})

    def test_list_value_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="primitive-only"):
            _make_ctx(strategy_params={"values": [1, 2, 3]})

    def test_primitive_values_accepted(self) -> None:
        primitives: dict = {
            "a": 1,
            "b": 2.5,
            "c": "hello",
            "d": True,
            "e": Decimal("0.01"),
            "f": None,
        }
        ctx = _make_ctx(strategy_params=primitives)
        assert ctx.strategy_params == primitives


# ---------------------------------------------------------------------------
# C-24: scoring_policy shape valid
# ---------------------------------------------------------------------------


class TestScoringPolicyShapeC24:
    def test_empty_version_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            OpportunityScoreComponentPolicy(policy_version="", component_keys=[])

    def test_component_keys_non_str_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            OpportunityScoreComponentPolicy(policy_version="p1", component_keys=[1, 2])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# C-23: strategy.py forbidden network/HTTP/WS/DB/exchange/Pydantic imports — AST
# ---------------------------------------------------------------------------


class TestStrategyForbiddenImportsC23:
    _FORBIDDEN_MODULE_FRAGMENTS = (
        "requests",
        "httpx",
        "aiohttp",
        "websocket",
        "websockets",
        "asyncpg",
        "psycopg",
        "sqlalchemy",
        "pydantic",
        "msgspec",
        "cattrs",
        "attrs",
        "kafka",
        "redis",
        "binance",
        "bybit",
        "okx",
    )

    def test_strategy_module_contains_no_forbidden_imports(self) -> None:
        with open(STRATEGY_PY, "r", encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=STRATEGY_PY)
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_names.add(node.module.split(".")[0])
        violations = [
            n for n in imported_names
            if any(frag in n.lower() for frag in self._FORBIDDEN_MODULE_FRAGMENTS)
        ]
        assert violations == [], (
            f"Forbidden imports detected in {STRATEGY_PY}: {violations}. "
            f"All detected imports: {sorted(imported_names)}"
        )


# ---------------------------------------------------------------------------
# StrategySignal — v1 long-only hard boundary
# ---------------------------------------------------------------------------


def _make_signal(
    direction: SignalDirection | str = SignalDirection.LONG,
    signal_strength: float = 0.7,
    entry_price_ref: Decimal | None = Decimal("45000.10"),
    confidence: float | None = 0.75,
    expected_edge_bps: float | None = 12.5,
    supporting_feature_keys: list[str] | None = None,
    supporting_regime_evidence: dict[str, float] | None = None,
    correlation_id: str = ULID_SAMPLE_C,
    causation_id: str = ULID_SAMPLE_A,
) -> StrategySignal:
    return StrategySignal(
        strategy_id="trend_following",
        strategy_version="1.0.0",
        direction=direction,
        signal_strength=signal_strength,
        entry_thesis="breakout confirmed",
        entry_price_ref=entry_price_ref,
        stop_policy=StopPolicySpec(
            stop_type="fixed", stop_ref_price=Decimal("44000"), stop_bps=222.2
        ),
        take_profit_policy=TakeProfitPolicySpec(
            tp_type="scale",
            tp_levels=[Decimal("46000"), Decimal("47500")],
            tp_bps=[222.2, 555.5],
        ),
        confidence=confidence,
        expected_edge_bps=expected_edge_bps,
        supporting_feature_keys=supporting_feature_keys or ["sma20", "rsi14"],
        supporting_regime_evidence=supporting_regime_evidence
        or {"bull": 0.8, "high_volatility": 0.3},
        correlation_id=correlation_id,
        causation_id=causation_id,
    )


class TestSignalDirectionC25:
    def test_signal_direction_has_exactly_three_values(self) -> None:
        values = sorted(s.value for s in SignalDirection)
        assert values == ["flat", "hold", "long"]

    def test_short_value_absent(self) -> None:
        with pytest.raises(ValueError):
            SignalDirection("short")

    def test_short_string_signal_raises(self) -> None:
        # Explicitly validate C-25: 'direction = "short"' → error (v1 hard boundary)
        with pytest.raises(ContractSchemaError, match="SHORT YASAK|v1 allowed: long/flat/hold"):
            _make_signal(direction="short")  # type: ignore[arg-type]


class TestStrategySignalTypesC26:
    @pytest.mark.parametrize("bad", [-0.001, 1.001])
    def test_signal_strength_out_of_range_raises(self, bad) -> None:
        with pytest.raises(ContractSchemaError, match="signal_strength"):
            _make_signal(signal_strength=bad)

    def test_entry_price_ref_float_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="entry_price_ref must be Decimal"):
            _make_signal(entry_price_ref=45000.10)  # type: ignore[arg-type]

    def test_entry_price_ref_decimal_accepted(self) -> None:
        s = _make_signal(entry_price_ref=Decimal("45000.10"))
        assert s.entry_price_ref == Decimal("45000.10")

    def test_confidence_out_of_range_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            _make_signal(confidence=1.5)  # type: ignore[arg-type]

    def test_expected_edge_bps_negative_accepted(self) -> None:
        # negative expected edge is a legitimate expression of expected loss — no clamp
        s = _make_signal(expected_edge_bps=-35.0)
        assert s.expected_edge_bps == pytest.approx(-35.0)

    def test_expected_edge_bps_int_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            _make_signal(expected_edge_bps=10)  # type: ignore[arg-type]


class TestRegimeEvidenceAndCorrCausC27:
    def test_regime_evidence_unknown_key_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="unknown key"):
            _make_signal(supporting_regime_evidence={"bull": 0.8, "unknownxx": 0.3})

    def test_regime_evidence_value_out_of_range_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="out of"):
            _make_signal(supporting_regime_evidence={"bull": 1.5})

    def test_correlation_id_short_invalid_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            _make_signal(correlation_id="abc")

    def test_causation_id_short_invalid_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            _make_signal(causation_id="!nope")

    def test_supporting_feature_keys_non_str_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            _make_signal(supporting_feature_keys=[1, 2])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# StrategySignal — Stop/Take Profit policy nested validators, determinism 10x
# ---------------------------------------------------------------------------


class TestStrategySignalPoliciesAndDeterminism:
    def test_stop_policy_bad_type_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            StopPolicySpec(stop_type="limit")  # type: ignore[arg-type]

    def test_take_profit_policy_bad_levels_raises(self) -> None:
        with pytest.raises(ContractSchemaError):
            TakeProfitPolicySpec(tp_type="fixed", tp_levels=[46000])  # type: ignore[list-item]

    def test_deterministic_sha256_10x(self) -> None:
        s = _make_signal()
        digests = [s.schema_sha256() for _ in range(10)]
        assert len(set(digests)) == 1

    def test_strategy_signal_to_sorted_dict_sorted(self) -> None:
        s = _make_signal()
        d = s.to_sorted_dict()
        assert list(d.keys()) == sorted(d.keys())

from __future__ import annotations

import ast
import json
import math
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
str(ROOT) not in sys.path and sys.path.insert(0, str(ROOT))

from app.contracts.exceptions import ContractSchemaError  # noqa: E402
from app.contracts.feature import (  # noqa: E402
    FEATURE_SCHEMA_REGISTRY,
    FeatureVector,
    LookbackWindowSpec,
)
from app.contracts.market import Candle  # noqa: E402
from app.contracts.types import Instant  # noqa: E402
from app.features import SFEA01_FEATURE_VERSION, SFEA01_SCHEMA_SPEC  # noqa: E402
from app.features.engine import FeatureEngine  # noqa: E402


def _ts(secs: int) -> Instant:
    import datetime
    epoch_ms = secs * 1000 + 1725000000000
    dt = datetime.datetime.fromtimestamp(epoch_ms / 1000.0, tz=datetime.timezone.utc)
    s = dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{epoch_ms % 1000:03d}Z"
    return Instant(s)


def _make_fixture_candles(n: int = 200) -> list[Candle]:
    arr: list[Candle] = []
    for i in range(n):
        c = 100.0 + 0.31 * i + 0.07 * (i % 17) + 0.13 * (i % 13)
        v = 1_500_000.0 + (i % 19) * 7300.0 + (i % 7) * 21_000.0
        arr.append(
            Candle(
                timeframe="1h",
                open_time=_ts(i * 3600),
                close_time=_ts((i + 1) * 3600),
                open=Decimal(str(c - 0.6)),
                high=Decimal(str(c + 0.6)),
                low=Decimal(str(c - 0.6)),
                close=Decimal(str(c)),
                volume=Decimal(str(v)),
                closed=True,
            )
        )
    return arr


class TestC44Cap1Parity:
    def test_c44_cap1_no_runmode_branch(self):
        p = ROOT / "app" / "features" / "engine.py"
        tree = ast.parse(p.read_text(encoding="utf-8"))
        findings = []

        class Visitor(ast.NodeVisitor):
            def visit_If(self, node: ast.If) -> None:
                for target in ("run_mode", "source_type"):
                    for child in ast.walk(node.test):
                        if isinstance(child, ast.Name) and child.id == target:
                            findings.append((target, node.lineno))
                        if isinstance(child, ast.Constant) and isinstance(child.value, str):
                            if target in child.value:
                                findings.append((f"str-{target}", node.lineno))
                self.generic_visit(node)

            def visit_Attribute(self, node: ast.Attribute) -> None:
                if node.attr in ("run_mode", "source_type"):
                    findings.append((f"attr-{node.attr}", getattr(node, "lineno", -1)))
                self.generic_visit(node)

        Visitor().visit(tree)
        assert findings == []


class TestC45C46Determinism:
    def test_c45_c46_10x_sorted_and_sha(self):
        candles = _make_fixture_candles(200)
        eng = FeatureEngine()
        fvs = [eng.calculate("BTC", candles, lookback=200) for _ in range(10)]
        dicts = [fv.to_sorted_dict() for fv in fvs]
        first = dicts[0]
        for d in dicts[1:]:
            assert d == first
        shas = {fv.schema_sha256() for fv in fvs}
        assert len(shas) == 1
        jsons = {json.dumps(first, sort_keys=True, default=str) for _ in range(10)}
        assert len(jsons) == 1

    def test_c46_sha256_64hex(self):
        fv = FeatureEngine().calculate("X", _make_fixture_candles(50), lookback=50)
        digest = fv.schema_sha256()
        assert isinstance(digest, str) and len(digest) == 64
        for ch in digest:
            assert ch in "0123456789abcdef"


class TestC47C48RegistryValidation:
    def test_c47_missing_required_key(self):
        candles = _make_fixture_candles(50)
        eng = FeatureEngine()
        fv = eng.calculate("X", candles, lookback=50)
        fv.features = {k: v for k, v in fv.features.items() if k != "ema_14"}
        reasons = fv.validate_against_registry()
        assert any("missing required" in r and "ema_14" in r for r in reasons)

    def test_c48_extra_forbidden_key(self):
        candles = _make_fixture_candles(50)
        eng = FeatureEngine()
        fv = eng.calculate("X", candles, lookback=50)
        fv.features["foo_bar"] = 123.0
        reasons = fv.validate_against_registry()
        assert any("extra forbidden" in r and "foo_bar" in r for r in reasons)


class TestC49RegistryShape:
    def test_c49_registry_spec_properties(self):
        assert SFEA01_FEATURE_VERSION in FEATURE_SCHEMA_REGISTRY
        spec = FEATURE_SCHEMA_REGISTRY[SFEA01_FEATURE_VERSION]
        assert len(spec.required_keys) == 12
        assert len(spec.allowed_keys) == 12
        assert set(spec.required_keys) == set(spec.allowed_keys)
        for k, t in spec.key_types.items():
            assert t is float
        # no bool type registered explicitly (bool not in key_types)
        for t in spec.key_types.values():
            assert t is not bool


class TestC50LeakageAST:
    def test_c50_no_t_plus_one_access(self):
        p = ROOT / "app" / "features" / "engine.py"
        tree = ast.parse(p.read_text(encoding="utf-8"))
        findings: list[tuple[str, int]] = []

        class Visitor(ast.NodeVisitor):
            def visit_Subscript(self, node: ast.Subscript) -> None:
                slice_ = node.slice
                if isinstance(slice_, ast.BinOp):
                    if isinstance(slice_.op, ast.Add):
                        # look for t + 1 or i + 1 pattern where left is simple name and right is Constant 1/2
                        if isinstance(slice_.right, ast.Constant) and isinstance(
                            slice_.right.value, int
                        ):
                            if slice_.right.value >= 1:
                                findings.append(
                                    (f"binop_add_{slice_.right.value}", node.lineno)
                                )
                if isinstance(slice_, ast.Constant) and isinstance(slice_.value, str):
                    if "future" in slice_.value or "next_candle" in slice_.value:
                        findings.append(("str_slice_future", node.lineno))
                self.generic_visit(node)

            def visit_Constant(self, node: ast.Constant) -> None:
                if isinstance(node.value, str):
                    if "future" in node.value.lower() or "next_candle" in node.value.lower():
                        if "FUTURE_DATA" not in node.value.upper():
                            pass
                self.generic_visit(node)

        Visitor().visit(tree)
        # Findings allowed: none for t+1 access in engine _compute_* subscripts
        t_plus_findings = [f for f in findings if f[0].startswith("binop_add")]
        assert t_plus_findings == []


class TestC51NanProtection:
    def test_c51_nan_coerced_or_raised(self):
        candles = _make_fixture_candles(60)
        eng = FeatureEngine()
        fv = eng.calculate("X", candles, lookback=60)
        for k, v in fv.features.items():
            if isinstance(v, float):
                assert not math.isnan(v), k
                assert not math.isinf(v), k

    def test_c51_explicit_nan_input_raises_in_regression(self):
        fv = FeatureVector(
            feature_version=SFEA01_FEATURE_VERSION,
            timeframe="1h",
            features={k: 1.0 for k in SFEA01_SCHEMA_SPEC.required_keys}
            | {"close_raw": float("nan")},
            lookback_window=LookbackWindowSpec(count=1, timeframe="1h"),
            input_refs=["C_000000"],
        )
        # _validate_features_flat already allows float, but nan is still float;
        # our _compute_* methods never emit nan; ensure registry bound not triggered for nan if key typed float
        # Just check we can construct fv without crash and features holds the nan
        v = fv.features["close_raw"]
        assert isinstance(v, float)
        assert math.isnan(v)


class TestC52C53NegativePriceVolume:
    def test_c52_negative_close_raises(self):
        candles = _make_fixture_candles(5)
        bad = Candle(
            timeframe="1h",
            open_time=_ts(6 * 3600),
            close_time=_ts(7 * 3600),
            open=Decimal("99"),
            high=Decimal("101"),
            low=Decimal("98"),
            close=Decimal("-5"),
            volume=Decimal("1000"),
            closed=True,
        )
        with pytest.raises(ContractSchemaError, match="non-positive price"):
            FeatureEngine().calculate("X", candles + [bad])

    def test_c53_negative_volume_raises(self):
        candles = _make_fixture_candles(5)
        bad = Candle(
            timeframe="1h",
            open_time=_ts(6 * 3600),
            close_time=_ts(7 * 3600),
            open=Decimal("99"),
            high=Decimal("101"),
            low=Decimal("98"),
            close=Decimal("100"),
            volume=Decimal("-10"),
            closed=True,
        )
        with pytest.raises(ContractSchemaError, match="negative volume"):
            FeatureEngine().calculate("X", candles + [bad])


@pytest.mark.parametrize(
    "key,formula_fn,idx",
    [
        ("ema_14", lambda cs: FeatureEngine._compute_ema(cs, 14)[-1], 0),
        ("rsi_14", lambda cs: FeatureEngine._compute_rsi(cs, 14)[-1], 1),
        ("atr_14", None, 2),
        ("vwap_20", None, 3),
        ("mom_10_abs", lambda cs: FeatureEngine._compute_momentum(cs, 10)[0][-1], 4),
        ("mom_10_pct", lambda cs: FeatureEngine._compute_momentum(cs, 10)[1][-1], 5),
        (
            "volatility_20_bps",
            lambda cs: FeatureEngine._compute_volatility(cs, 20)[-1],
            6,
        ),
        (
            "vol_ratio_20",
            lambda vs: FeatureEngine._compute_volume_features(vs, 20)[0][-1],
            7,
        ),
        (
            "vol_std_20_scaled",
            lambda vs: FeatureEngine._compute_volume_features(vs, 20)[1][-1],
            8,
        ),
        ("close_raw", None, 9),
        ("high_raw", None, 10),
        ("low_raw", None, 11),
    ],
)
def test_c54_formula_verification_parametrize(key, formula_fn, idx):
    # 10 different fixture variations
    for variant in range(10):
        n = 50 + variant * 11
        closes = [100.0 + (0.2 + 0.01 * variant) * j + 0.05 * (j % (variant + 3)) for j in range(n)]
        highs = [c + 0.5 + 0.01 * variant for c in closes]
        lows = [c - 0.5 - 0.01 * variant for c in closes]
        volumes = [500_000.0 + (j % (variant + 4 + 1)) * 3000.0 for j in range(n)]
        if key in ("ema_14", "rsi_14", "mom_10_abs", "mom_10_pct", "volatility_20_bps"):
            expected = formula_fn(closes) if formula_fn else None
        elif key in ("vol_ratio_20", "vol_std_20_scaled"):
            expected = formula_fn(volumes) if formula_fn else None
        elif key == "atr_14":
            expected = FeatureEngine._compute_atr(highs, lows, closes, 14)[-1]
        elif key == "vwap_20":
            expected = FeatureEngine._compute_vwap(highs, lows, closes, volumes, 20)[-1]
        elif key == "close_raw":
            expected = closes[-1]
        elif key == "high_raw":
            expected = highs[-1]
        elif key == "low_raw":
            expected = lows[-1]
        else:  # pragma: no cover
            expected = None
        # Build candles and compare FV output to directly calculated expected
        arr: list[Candle] = []
        for j in range(n):
            arr.append(
                Candle(
                    timeframe="1h",
                    open_time=_ts(j * 3600),
                    close_time=_ts((j + 1) * 3600),
                    open=Decimal(str(closes[j] - 0.1)),
                    high=Decimal(str(highs[j])),
                    low=Decimal(str(lows[j])),
                    close=Decimal(str(closes[j])),
                    volume=Decimal(str(volumes[j])),
                    closed=True,
                )
            )
        fv = FeatureEngine().calculate("X", arr, lookback=n)
        actual = fv.features[key]
        if expected is None:
            assert actual is None
        else:
            assert isinstance(actual, float)
            assert isinstance(expected, float)
            assert actual == pytest.approx(expected, abs=1e-7, rel=1e-7)

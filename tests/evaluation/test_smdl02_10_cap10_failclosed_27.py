"""T10 — CAP-10: Fail-closed coverage for all 27 ERR_* reason codes. 27 tests (1 per code)."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.evaluation.conftest import (  # noqa: E402
    DEFAULT_COMPAT,
    DEFAULT_COST_VERSION,
    DEFAULT_THRESHOLDS_VERSION,
    DEFAULT_UNIVERSE,
    DEFAULT_WINDOW,
    challenger_better_metrics,
    champion_metrics,
    make_engine_with_fixtures,
)
from app.evaluation import (  # noqa: E402
    CompareEngine,
    ERR_ARTIFACT_CORRUPT,
    ERR_ARTIFACT_NOT_FOUND,
    ERR_EMPTY_ARTIFACT_URI,
    ERR_EMPTY_CHALLENGER_MODEL,
    ERR_EMPTY_CHAMPION_MODEL,
    ERR_INCOMPARABLE_COMPATIBILITY,
    ERR_INCOMPARABLE_COST,
    ERR_INCOMPARABLE_DATASET,
    ERR_INCOMPARABLE_FOLD_COUNT,
    ERR_INCOMPARABLE_REGIME_GROUPS,
    ERR_INCOMPARABLE_THRESHOLDS,
    ERR_INCOMPARABLE_UNIVERSE,
    ERR_INCOMPARABLE_WINDOW,
    ERR_INCOMPATIBLE_STATUS_TRANSITION,
    ERR_INTEGRITY_SHA_MISMATCH,
    ERR_INVALID_ROUNDING_PRECISION,
    ERR_METRIC_TYPE_MISMATCH,
    ERR_MISSING_METRIC,
    ERR_MODEL_NOT_FOUND,
    ERR_NAN_NUMERIC,
    ERR_NEGATIVE_TRADE_COUNT,
    ERR_NOT_CHALLENGER_STATUS,
    ERR_NOT_CHAMPION_STATUS,
    ERR_SAME_MODEL_SAME_VERSION,
    ERR_UNKNOWN_METRIC_KEY,
    ERR_VERSION_MISMATCH,
    ERR_DRAWDOWN_OUT_OF_RANGE,
    CompareValidationError,
    compare_metric_delta,
)
from app.contracts.model import (  # noqa: E402
    DatasetKindEnum,
    ModelCompatibilityRef,
    ModelLifecycleStatus,
    TrainingDataRange,
)


ALL_CODES = [
    ERR_MODEL_NOT_FOUND,
    ERR_VERSION_MISMATCH,
    ERR_NOT_CHAMPION_STATUS,
    ERR_NOT_CHALLENGER_STATUS,
    ERR_SAME_MODEL_SAME_VERSION,
    ERR_EMPTY_CHAMPION_MODEL,
    ERR_EMPTY_CHALLENGER_MODEL,
    ERR_ARTIFACT_NOT_FOUND,
    ERR_EMPTY_ARTIFACT_URI,
    ERR_ARTIFACT_CORRUPT,
    ERR_INTEGRITY_SHA_MISMATCH,
    ERR_MISSING_METRIC,
    ERR_UNKNOWN_METRIC_KEY,
    ERR_METRIC_TYPE_MISMATCH,
    ERR_NAN_NUMERIC,
    ERR_NEGATIVE_TRADE_COUNT,
    ERR_DRAWDOWN_OUT_OF_RANGE,
    ERR_INVALID_ROUNDING_PRECISION,
    ERR_INCOMPARABLE_WINDOW,
    ERR_INCOMPARABLE_DATASET,
    ERR_INCOMPARABLE_COST,
    ERR_INCOMPARABLE_UNIVERSE,
    ERR_INCOMPARABLE_COMPATIBILITY,
    ERR_INCOMPARABLE_THRESHOLDS,
    ERR_INCOMPARABLE_FOLD_COUNT,
    ERR_INCOMPARABLE_REGIME_GROUPS,
    ERR_INCOMPATIBLE_STATUS_TRANSITION,
]


def test_all_27_codes_count():
    assert len(set(ALL_CODES)) == 27


def _run_err(code: str, tmp_path: Path):
    if code == ERR_MODEL_NOT_FOUND:
        fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
        with pytest.raises(CompareValidationError) as ex:
            fix["engine"].compare("nonexistent_model_xyz", "1.0.0", fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        return ex.value.reason_code
    if code == ERR_VERSION_MISMATCH:
        # Artifact model_version != registry MV version
        from tests.evaluation.conftest import make_sample_mv, build_artifact_json_bytes, build_registry_with_models
        from app.registry import EvidenceKind

        ch_mv = make_sample_mv(model_id="ver_mis_c", version="1.0.0", status=ModelLifecycleStatus.CHAMPION)
        ct_mv = make_sample_mv(model_id="ver_mis_t", version="2.0.0", status=ModelLifecycleStatus.CHALLENGER)
        # champion artifact has wrong version (9.9.9 vs 1.0.0)
        _ch_sha, ch_hist = build_artifact_json_bytes(ch_mv.model_id, "9.9.9", champion_metrics())
        _ct_sha, ct_hist = build_artifact_json_bytes(ct_mv.model_id, ct_mv.version, challenger_better_metrics())
        c_b = {k: ch_hist for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
        t_b = {k: ct_hist for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
        reg, _p = build_registry_with_models(tmp_path, ch_mv, ct_mv, champion_artifact_bytes=c_b, challenger_artifact_bytes=t_b)
        eng = CompareEngine(registry=reg)
        with pytest.raises(CompareValidationError) as ex:
            eng.compare(ch_mv.model_id, ch_mv.version, ct_mv.model_id, ct_mv.version)
        return ex.value.reason_code
    if code == ERR_NOT_CHAMPION_STATUS:
        # champion status = challenger (wrong)
        fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
        with pytest.raises(CompareValidationError) as ex:
            # challenger has challenger status; load as champion (fail NOT_CHAMPION)
            fix["engine"].compare(fix["challenger_mv"].model_id, fix["challenger_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        if ex.value.reason_code == ERR_SAME_MODEL_SAME_VERSION:
            # different ids: use champion as CT (status OK) and CT as champion
            from tests.evaluation.conftest import make_sample_mv, build_artifact_json_bytes, build_registry_with_models
            from app.registry import EvidenceKind
    
            mv_wrong_status = make_sample_mv(model_id="not_champ", version="1.0.0", status=ModelLifecycleStatus.CHALLENGER)
            ct = make_sample_mv(model_id="ct_ok", version="2.0.0", status=ModelLifecycleStatus.CHALLENGER)
            _s1, h1 = build_artifact_json_bytes(mv_wrong_status.model_id, mv_wrong_status.version, champion_metrics())
            _s2, h2 = build_artifact_json_bytes(ct.model_id, ct.version, challenger_better_metrics())
            b1 = {k: h1 for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
            b2 = {k: h2 for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
            reg2, _p2 = build_registry_with_models(tmp_path, mv_wrong_status, ct, champion_artifact_bytes=b1, challenger_artifact_bytes=b2)
            eng2 = CompareEngine(registry=reg2)
            with pytest.raises(CompareValidationError) as ex2:
                eng2.compare(mv_wrong_status.model_id, mv_wrong_status.version, ct.model_id, ct.version)
            return ex2.value.reason_code
        return ex.value.reason_code
    if code == ERR_NOT_CHALLENGER_STATUS:
        # challenger status = champion (wrong)
        from tests.evaluation.conftest import make_sample_mv, build_artifact_json_bytes, build_registry_with_models
        from app.registry import EvidenceKind

        ch = make_sample_mv(model_id="ch_ok_c", version="1.0.0", status=ModelLifecycleStatus.CHAMPION)
        ct_wrong = make_sample_mv(model_id="ct_wrong_st", version="2.0.0", status=ModelLifecycleStatus.CHAMPION)
        _s1, h1 = build_artifact_json_bytes(ch.model_id, ch.version, champion_metrics())
        _s2, h2 = build_artifact_json_bytes(ct_wrong.model_id, ct_wrong.version, challenger_better_metrics())
        b1 = {k: h1 for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
        b2 = {k: h2 for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
        reg2, _p2 = build_registry_with_models(tmp_path, ch, ct_wrong, champion_artifact_bytes=b1, challenger_artifact_bytes=b2)
        eng2 = CompareEngine(registry=reg2)
        with pytest.raises(CompareValidationError) as ex:
            eng2.compare(ch.model_id, ch.version, ct_wrong.model_id, ct_wrong.version)
        return ex.value.reason_code
    if code == ERR_SAME_MODEL_SAME_VERSION:
        fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
        with pytest.raises(CompareValidationError) as ex:
            fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["champion_mv"].model_id, fix["champion_mv"].version)
        return ex.value.reason_code
    if code == ERR_EMPTY_CHAMPION_MODEL:
        fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
        with pytest.raises(CompareValidationError) as ex:
            fix["engine"].compare("", "1.0.0", fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        return ex.value.reason_code
    if code == ERR_EMPTY_CHALLENGER_MODEL:
        fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics())
        with pytest.raises(CompareValidationError) as ex:
            fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, "", "2.0.0")
        return ex.value.reason_code
    if code == ERR_ARTIFACT_NOT_FOUND:
        # URI points to nonexistent file → ERR_ARTIFACT_NOT_FOUND
        from tests.evaluation.conftest import make_sample_mv
        from app.registry import EvidenceKind, EvidenceRef, ModelRegistry, LocalFSRegistryStorage

        ch = make_sample_mv(model_id="art_not_found_c", version="1.0.0", status=ModelLifecycleStatus.CHAMPION)
        ct = make_sample_mv(model_id="art_not_found_t", version="2.0.0", status=ModelLifecycleStatus.CHALLENGER)
        models_dir = tmp_path / "reg_artnf"
        storage = LocalFSRegistryStorage(root=models_dir)
        reg = ModelRegistry(storage=storage)
        reg.create(ch)
        reg.create(ct)
        # champion evidence points to non-existent file uri
        fake_uri = (tmp_path / "does_not_exist_xyz.json").resolve()
        fake_uri_s = "file://" + str(fake_uri)
        ref = EvidenceRef(kind=EvidenceKind.HISTORICAL_OOS_EVAL, ref_id="REFNF0001", artifact_uri=fake_uri_s, source_created_ts="2026-09-12T10:00:00.000Z", correlation_id="CORRNF0001", integrity_sha256="a" * 64, metadata={})
        reg.append_evidence(ch.model_id, ch.version, ref)
        reg.append_evidence(ch.model_id, ch.version, EvidenceRef(kind=EvidenceKind.WALK_FORWARD_RUN, ref_id="REFNF0002", artifact_uri=fake_uri_s, source_created_ts="2026-09-12T10:00:00.000Z", correlation_id="CORRNF0002", integrity_sha256="a" * 64, metadata={}))
        reg.append_evidence(ch.model_id, ch.version, EvidenceRef(kind=EvidenceKind.PAPER_REPLAY_EVAL, ref_id="REFNF0003", artifact_uri=fake_uri_s, source_created_ts="2026-09-12T10:00:00.000Z", correlation_id="CORRNF0003", integrity_sha256="a" * 64, metadata={}))
        # Challenger: same non-existent
        for i, ek in enumerate((EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)):
            reg.append_evidence(ct.model_id, ct.version, EvidenceRef(kind=ek, ref_id=f"REFNFCT{i:03d}", artifact_uri=fake_uri_s, source_created_ts="2026-09-12T10:00:00.000Z", correlation_id=f"CORRNFCT{i:03d}", integrity_sha256="a" * 64, metadata={}))
        eng = CompareEngine(registry=reg)
        with pytest.raises(CompareValidationError) as ex:
            eng.compare(ch.model_id, ch.version, ct.model_id, ct.version)
        return ex.value.reason_code
    if code == ERR_EMPTY_ARTIFACT_URI:
        from app.evaluation.engine import _load_artifact_bytes

        with pytest.raises(CompareValidationError) as ex:
            _load_artifact_bytes("")
        return ex.value.reason_code
    if code == ERR_ARTIFACT_CORRUPT:
        # artifact bytes not JSON
        from tests.evaluation.conftest import make_sample_mv, write_tmp_artifact
        from app.registry import EvidenceKind, EvidenceRef, ModelRegistry, LocalFSRegistryStorage
        import hashlib

        ch = make_sample_mv(model_id="corrupt_c", version="1.0.0", status=ModelLifecycleStatus.CHAMPION)
        ct = make_sample_mv(model_id="corrupt_t", version="2.0.0", status=ModelLifecycleStatus.CHALLENGER)
        storage = LocalFSRegistryStorage(root=tmp_path / "reg_corr")
        reg = ModelRegistry(storage=storage)
        reg.create(ch); reg.create(ct)
        corrupt_bytes = b"THIS IS NOT JSON!!! {{{\x00\x01"
        p = write_tmp_artifact(tmp_path, "corrupt.json", corrupt_bytes)
        for i, ek in enumerate((EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)):
            uri = "file://" + str(p.resolve())
            integ = hashlib.sha256(corrupt_bytes).hexdigest()
            reg.append_evidence(ch.model_id, ch.version, EvidenceRef(kind=ek, ref_id=f"REFCORC{i:05d}", artifact_uri=uri, source_created_ts="2026-09-12T10:00:00.000Z", correlation_id=f"CCOR{i:05d}", integrity_sha256=integ, metadata={}))
            reg.append_evidence(ct.model_id, ct.version, EvidenceRef(kind=ek, ref_id=f"REFCORT{i:05d}", artifact_uri=uri, source_created_ts="2026-09-12T10:00:00.000Z", correlation_id=f"CTCOR{i:05d}", integrity_sha256=integ, metadata={}))
        eng = CompareEngine(registry=reg)
        with pytest.raises(CompareValidationError) as ex:
            eng.compare(ch.model_id, ch.version, ct.model_id, ct.version)
        return ex.value.reason_code
    if code == ERR_INTEGRITY_SHA_MISMATCH:
        fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), integrity_mismatch_champion_historical=True)
        with pytest.raises(CompareValidationError) as ex:
            fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        return ex.value.reason_code
    if code == ERR_MISSING_METRIC:
        m = dict(champion_metrics())
        m.pop("sharpe_ratio")
        from tests.evaluation.conftest import make_sample_mv, build_artifact_json_bytes, build_registry_with_models
        from app.registry import EvidenceKind

        ch = make_sample_mv(model_id="miss_met_c", version="1.0.0", status=ModelLifecycleStatus.CHAMPION)
        ct = make_sample_mv(model_id="miss_met_t", version="2.0.0", status=ModelLifecycleStatus.CHALLENGER)
        _s1, h1 = build_artifact_json_bytes(ch.model_id, ch.version, m)
        _s2, h2 = build_artifact_json_bytes(ct.model_id, ct.version, challenger_better_metrics())
        b1 = {k: h1 for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
        b2 = {k: h2 for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
        reg, _p = build_registry_with_models(tmp_path, ch, ct, champion_artifact_bytes=b1, challenger_artifact_bytes=b2)
        eng = CompareEngine(registry=reg)
        with pytest.raises(CompareValidationError) as ex:
            eng.compare(ch.model_id, ch.version, ct.model_id, ct.version)
        return ex.value.reason_code
    if code == ERR_UNKNOWN_METRIC_KEY:
        # Trigger with compare_metric_delta unknown key
        with pytest.raises(CompareValidationError) as ex:
            compare_metric_delta("nonexistent_xyz_metric_qwerty", {"nonexistent_xyz_metric_qwerty": 1.0}, {"nonexistent_xyz_metric_qwerty": 2.0})
        return ex.value.reason_code
    if code == ERR_METRIC_TYPE_MISMATCH:
        # sharpe_ratio str literal non-numeric
        m = dict(champion_metrics())
        m["sharpe_ratio"] = "NOT_A_FLOAT_VALUE"
        from tests.evaluation.conftest import make_sample_mv, build_artifact_json_bytes, build_registry_with_models
        from app.registry import EvidenceKind

        ch = make_sample_mv(model_id="mtm_c", version="1.0.0", status=ModelLifecycleStatus.CHAMPION)
        ct = make_sample_mv(model_id="mtm_t", version="2.0.0", status=ModelLifecycleStatus.CHALLENGER)
        _s1, h1 = build_artifact_json_bytes(ch.model_id, ch.version, m)
        _s2, h2 = build_artifact_json_bytes(ct.model_id, ct.version, challenger_better_metrics())
        b1 = {k: h1 for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
        b2 = {k: h2 for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
        reg, _p = build_registry_with_models(tmp_path, ch, ct, champion_artifact_bytes=b1, challenger_artifact_bytes=b2)
        eng = CompareEngine(registry=reg)
        with pytest.raises(CompareValidationError) as ex:
            eng.compare(ch.model_id, ch.version, ct.model_id, ct.version)
        return ex.value.reason_code
    if code == ERR_NAN_NUMERIC:
        import math

        with pytest.raises(CompareValidationError) as ex:
            compare_metric_delta("sharpe_ratio", {"sharpe_ratio": 1.0}, {"sharpe_ratio": float("nan")})
        return ex.value.reason_code
    if code == ERR_NEGATIVE_TRADE_COUNT:
        with pytest.raises(CompareValidationError) as ex:
            compare_metric_delta("trade_count", {"trade_count": 100}, {"trade_count": -5})
        return ex.value.reason_code
    if code == ERR_DRAWDOWN_OUT_OF_RANGE:
        # max_drawdown_pct = 2.0 (>1.0)
        with pytest.raises(CompareValidationError) as ex:
            compare_metric_delta("max_drawdown_pct", {"max_drawdown_pct": 0.1}, {"max_drawdown_pct": 2.5})
        return ex.value.reason_code
    if code == ERR_INVALID_ROUNDING_PRECISION:
        from app.evaluation.delta import round_metric_value

        with pytest.raises(CompareValidationError) as ex:
            round_metric_value(Decimal("sNaN"), "ext_custom_dec_metric")
        return ex.value.reason_code
    if code == ERR_INCOMPARABLE_WINDOW:
        challenger_w = TrainingDataRange(start="2026-01-02T00:00:00.000Z", end="2027-01-01T00:00:00.000Z")
        fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), challenger_window=challenger_w)
        with pytest.raises(CompareValidationError) as ex:
            fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        return ex.value.reason_code
    if code == ERR_INCOMPARABLE_DATASET:
        fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), dataset_kind=DatasetKindEnum.WALK_FORWARD, challenger_dataset_kind=DatasetKindEnum.IN_SAMPLE)
        with pytest.raises(CompareValidationError) as ex:
            fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        return ex.value.reason_code
    if code == ERR_INCOMPARABLE_COST:
        fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), cost=DEFAULT_COST_VERSION, challenger_cost="cost-v2")
        with pytest.raises(CompareValidationError) as ex:
            fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        return ex.value.reason_code
    if code == ERR_INCOMPARABLE_UNIVERSE:
        fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), universe=DEFAULT_UNIVERSE, challenger_universe=["SOL_USDT"])
        with pytest.raises(CompareValidationError) as ex:
            fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        return ex.value.reason_code
    if code == ERR_INCOMPARABLE_COMPATIBILITY:
        chall_compat = ModelCompatibilityRef(feature_version="feature-v99", strategy_version=DEFAULT_COMPAT.strategy_version, regime_version=DEFAULT_COMPAT.regime_version)
        fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), compat=DEFAULT_COMPAT, challenger_compat=chall_compat)
        with pytest.raises(CompareValidationError) as ex:
            fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        return ex.value.reason_code
    if code == ERR_INCOMPARABLE_THRESHOLDS:
        fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), thresholds=DEFAULT_THRESHOLDS_VERSION, challenger_thresholds="thr-v99")
        with pytest.raises(CompareValidationError) as ex:
            fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        return ex.value.reason_code
    if code == ERR_INCOMPARABLE_FOLD_COUNT:
        c_folds = [{"return_pct": Decimal("0.01"), "trade_count": 10}]
        t_folds = [{"return_pct": Decimal("0.01"), "trade_count": 10}, {"return_pct": Decimal("0.02"), "trade_count": 20}]
        fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), per_fold=c_folds, challenger_per_fold=t_folds)
        with pytest.raises(CompareValidationError) as ex:
            fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        return ex.value.reason_code
    if code == ERR_INCOMPARABLE_REGIME_GROUPS:
        c_r = [{"strategy_id": "s1", "regime": "low_vol", "return_pct": Decimal("0.01"), "trade_count": 10}]
        t_r = [{"strategy_id": "s1", "regime": "high_vol", "return_pct": Decimal("0.01"), "trade_count": 10}]
        fix = make_engine_with_fixtures(tmp_path, champion_metrics(), challenger_better_metrics(), regime=c_r, challenger_regime=t_r)
        with pytest.raises(CompareValidationError) as ex:
            fix["engine"].compare(fix["champion_mv"].model_id, fix["champion_mv"].version, fix["challenger_mv"].model_id, fix["challenger_mv"].version)
        return ex.value.reason_code
    if code == ERR_INCOMPATIBLE_STATUS_TRANSITION:
        # artifact model_id mismatch registry MV model_id
        from tests.evaluation.conftest import make_sample_mv, build_artifact_json_bytes, build_registry_with_models
        from app.registry import EvidenceKind

        ch = make_sample_mv(model_id="ch_ok_id", version="1.0.0", status=ModelLifecycleStatus.CHAMPION)
        ct = make_sample_mv(model_id="ct_ok_id", version="2.0.0", status=ModelLifecycleStatus.CHALLENGER)
        # champion artifact has wrong model_id
        _s1, h1 = build_artifact_json_bytes("WRONG_MODEL_ID", ch.version, champion_metrics())
        _s2, h2 = build_artifact_json_bytes(ct.model_id, ct.version, challenger_better_metrics())
        b1 = {k: h1 for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
        b2 = {k: h2 for k in (EvidenceKind.HISTORICAL_OOS_EVAL, EvidenceKind.WALK_FORWARD_RUN, EvidenceKind.PAPER_REPLAY_EVAL)}
        reg, _p = build_registry_with_models(tmp_path, ch, ct, champion_artifact_bytes=b1, challenger_artifact_bytes=b2)
        eng = CompareEngine(registry=reg)
        with pytest.raises(CompareValidationError) as ex:
            eng.compare(ch.model_id, ch.version, ct.model_id, ct.version)
        return ex.value.reason_code
    raise AssertionError(f"Code not implemented in trigger: {code}")


@pytest.mark.parametrize("code", ALL_CODES)
def test_each_reason_code_triggerable(tmp_path, code):
    actual = _run_err(code, tmp_path)
    assert actual == code, f"Expected {code} got {actual}"

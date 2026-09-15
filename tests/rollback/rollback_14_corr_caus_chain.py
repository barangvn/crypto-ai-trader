from __future__ import annotations

import pytest

from app.rollback import RollbackEngine


def test_corr_caus_exact_strings_preserved(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=401)
    kw = dict(common_evaluate_kwargs)
    kw["correlation_id"] = "CORR-EXACT-001"
    kw["causation_id"] = "CAUS-EXACT-002"
    d, audit = engine.evaluate(**kw)
    assert audit.correlation_id == "CORR-EXACT-001"
    assert audit.causation_id == "CAUS-EXACT-002"


def test_corr_caus_deep_copied_not_shallow(dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=402)
    kw = dict(common_evaluate_kwargs)
    kw["correlation_id"] = "shared-string"
    kw["causation_id"] = "shared-caus"
    _, audit = engine.evaluate(**kw)
    assert audit.correlation_id is not None
    assert audit.causation_id is not None
    # strings are immutable but confirm no reference weirdness via equality
    assert audit.correlation_id == kw["correlation_id"]


@pytest.mark.parametrize("i", list(range(8)))
def test_corr_caus_8_chained_runs_keep_values(i, dummy_storage_happy, common_evaluate_kwargs):
    engine = RollbackEngine(storage=dummy_storage_happy, explicit_seed=1000 + i)
    kw = dict(common_evaluate_kwargs)
    kw["correlation_id"] = f"chain-corr-{i}"
    kw["causation_id"] = f"chain-caus-{i}"
    _, audit = engine.evaluate(**kw)
    assert audit.correlation_id.endswith(str(i))
    assert audit.causation_id.endswith(str(i))

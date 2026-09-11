from __future__ import annotations

import pytest

from app.contracts import ModelLifecycleStatus
from app.registry import ERR_VERSION_ALREADY_EXISTS, RegistryError, sha_from_payload
from tests.registry.conftest import sample_mv


def test_smdl01_13_10x_same_payload_sha_identical(tmp_registry_root):
    from app.registry.storage import LocalFSRegistryStorage
    from app.registry import ModelRegistry

    shas = []
    for i in range(10):
        storage = LocalFSRegistryStorage(root=tmp_registry_root) if i == 0 else None
        bus = None
        reg = ModelRegistry(
            storage=LocalFSRegistryStorage(root=tmp_registry_root) if i == 0 else None,
            event_bus=bus,
            root=tmp_registry_root if i == 0 else None,
        )
    mv = sample_mv()
    payload_sha = sha_from_payload(mv)
    assert isinstance(payload_sha, str) and len(payload_sha) == 64

    shas_run = []
    for _ in range(10):
        mv_clone = sample_mv()
        shas_run.append(sha_from_payload(mv_clone))

    assert len(set(shas_run)) == 1


def test_smdl01_13_create_same_mv_10x_raises_version_exists_after_first(fresh_registry):
    reg, _bus, _storage = fresh_registry
    mv = sample_mv()

    created_mv, first_sha = reg.create(mv)
    assert isinstance(first_sha, str) and len(first_sha) == 64

    duplicate_errors = 0
    for _ in range(9):
        mv_again = sample_mv()
        with pytest.raises(RegistryError) as exc_info:
            reg.create(mv_again)
        assert exc_info.value.reason_code == ERR_VERSION_ALREADY_EXISTS
        duplicate_errors += 1

    assert duplicate_errors == 9


def test_smdl01_13_list_canonical_order_10x_identical(tmp_registry_root):
    from app.platform.event_bus import InMemoryTypedEventBus
    from app.registry.storage import LocalFSRegistryStorage
    from app.registry import ModelRegistry

    storage = LocalFSRegistryStorage(root=tmp_registry_root)
    bus = InMemoryTypedEventBus()
    reg = ModelRegistry(storage=storage, event_bus=bus, root=tmp_registry_root)

    mv_specs = [
        ("model_z", "1.0.0", ModelLifecycleStatus.CANDIDATE),
        ("model_a", "2.0.0", ModelLifecycleStatus.TESTED),
        ("model_a", "1.0.0", ModelLifecycleStatus.PAPER),
        ("model_m", "0.5.0", ModelLifecycleStatus.CANDIDATE),
    ]
    for mid, ver, status in mv_specs:
        reg.create(sample_mv(model_id=mid, version=ver, status=status))

    orders = []
    for _ in range(10):
        s2 = LocalFSRegistryStorage(root=tmp_registry_root)
        b2 = InMemoryTypedEventBus()
        r2 = ModelRegistry(storage=s2, event_bus=b2, root=tmp_registry_root)
        result = r2.list()
        order = [(mv.model_id, mv.version) for mv, _sha in result]
        orders.append(order)

    for i in range(1, 10):
        assert orders[i] == orders[0]


def test_smdl01_13_request_transition_10x_tx_id_identical(tmp_registry_root):
    from pathlib import Path
    from app.platform.event_bus import InMemoryTypedEventBus
    from app.registry.storage import LocalFSRegistryStorage
    from app.registry import ModelRegistry

    tx_ids = []
    for i in range(10):
        run_root = tmp_registry_root / f"run-{i}"
        run_root.mkdir(parents=True, exist_ok=True)
        s = LocalFSRegistryStorage(root=run_root)
        b = InMemoryTypedEventBus()
        r = ModelRegistry(storage=s, event_bus=b, root=run_root)
        mv = sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        r.create(mv)
        _nmv, _nsha, tx, _env = r.request_transition(
            model_id=mv.model_id,
            version=mv.version,
            to_status=ModelLifecycleStatus.TESTED,
            transition_command="run_backtest_and_evaluate",
        )
        tx_ids.append(tx.transition_id)

    assert len(set(tx_ids)) == 1


def test_smdl01_13_10x_mv_same_fields_create_same_storage_sha(fresh_registry):
    reg, _bus, storage = fresh_registry

    mv1 = sample_mv()
    c1, sha1 = reg.create(mv1)

    sha_values = []
    for _ in range(9):
        mv_n = sample_mv()
        sha_values.append(sha_from_payload(mv_n))

    all_same = all(s == sha1 for s in sha_values)
    assert all_same, f"SHA mismatch: first={sha1[:12]} others={[s[:12] for s in sha_values]}"

from __future__ import annotations

from app.contracts import ModelLifecycleStatus
from tests.registry.conftest import sample_mv


def test_smdl01_20_transition_correlation_id_matches_mv(created_registry):
    reg, bus, storage, created_mv, _sha = created_registry

    new_mv, new_sha, tx, envelope = reg.request_transition(
        model_id=created_mv.model_id,
        version=created_mv.version,
        to_status=ModelLifecycleStatus.TESTED,
        transition_command="run_backtest_and_evaluate",
    )

    assert str(tx.correlation_id) == str(created_mv.correlation_id)
    assert str(new_mv.correlation_id) == str(created_mv.correlation_id)


def test_smdl01_20_explicit_correlation_id_override(fresh_registry):
    reg, bus, storage = fresh_registry
    mv = sample_mv(status=ModelLifecycleStatus.CANDIDATE)
    created_mv, _ = reg.create(mv)

    explicit_corr = "01920000-0000-7000-8000-000000000999"
    _new_mv, _new_sha, tx, _env = reg.request_transition(
        model_id=created_mv.model_id,
        version=created_mv.version,
        to_status=ModelLifecycleStatus.TESTED,
        transition_command="run_backtest_and_evaluate",
        correlation_id=explicit_corr,
    )
    assert str(tx.correlation_id) == explicit_corr


def test_smdl01_20_causation_id_determinism_same_inputs(tmp_registry_root):
    from app.platform.event_bus import InMemoryTypedEventBus
    from app.registry import ModelRegistry
    from app.registry.storage import LocalFSRegistryStorage

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        root1 = Path(d1) / "reg"
        root2 = Path(d2) / "reg"
        root1.mkdir()
        root2.mkdir()

        bus1 = InMemoryTypedEventBus()
        storage1 = LocalFSRegistryStorage(root=root1)
        reg1 = ModelRegistry(storage=storage1, event_bus=bus1, root=root1)

        bus2 = InMemoryTypedEventBus()
        storage2 = LocalFSRegistryStorage(root=root2)
        reg2 = ModelRegistry(storage=storage2, event_bus=bus2, root=root2)

        mv1 = sample_mv(
            status=ModelLifecycleStatus.CANDIDATE,
            created_ts="2026-09-09T00:00:00.000Z",
        )
        created1, sha1 = reg1.create(mv1)

        mv2 = sample_mv(
            status=ModelLifecycleStatus.CANDIDATE,
            created_ts="2026-09-09T00:00:00.000Z",
        )
        created2, sha2 = reg2.create(mv2)

        assert sha1 == sha2, "Identical ModelVersions must produce identical SHA"

        _r1_mv, _r1_sha, tx1, _e1 = reg1.request_transition(
            model_id=created1.model_id,
            version=created1.version,
            to_status=ModelLifecycleStatus.TESTED,
            transition_command="run_backtest_and_evaluate",
            requested_ts="2026-09-09T12:00:00.000Z",
        )

        _r2_mv, _r2_sha, tx2, _e2 = reg2.request_transition(
            model_id=created2.model_id,
            version=created2.version,
            to_status=ModelLifecycleStatus.TESTED,
            transition_command="run_backtest_and_evaluate",
            requested_ts="2026-09-09T12:00:00.000Z",
        )

        assert tx1.causation_id == tx2.causation_id
        assert tx1.transition_id == tx2.transition_id


def test_smdl01_20_different_commands_produce_different_causation_ids(tmp_registry_root):
    from app.platform.event_bus import InMemoryTypedEventBus
    from app.registry import ModelRegistry
    from app.registry.storage import LocalFSRegistryStorage

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "reg"
        root.mkdir()

        bus_a = InMemoryTypedEventBus()
        storage_a = LocalFSRegistryStorage(root=root / "a")
        reg_a = ModelRegistry(storage=storage_a, event_bus=bus_a, root=root / "a")

        bus_b = InMemoryTypedEventBus()
        storage_b = LocalFSRegistryStorage(root=root / "b")
        reg_b = ModelRegistry(storage=storage_b, event_bus=bus_b, root=root / "b")

        mv_a = sample_mv(status=ModelLifecycleStatus.CANDIDATE, created_ts="2026-09-09T00:00:00.000Z")
        cr_a, sha_a = reg_a.create(mv_a)
        mv_b = sample_mv(status=ModelLifecycleStatus.CANDIDATE, created_ts="2026-09-09T00:00:00.000Z")
        cr_b, sha_b = reg_b.create(mv_b)
        assert sha_a == sha_b

        _, _, tx_a, _ = reg_a.request_transition(
            model_id=cr_a.model_id,
            version=cr_a.version,
            to_status=ModelLifecycleStatus.TESTED,
            transition_command="command_alpha",
            requested_ts="2026-09-09T12:00:00.000Z",
        )
        _, _, tx_b, _ = reg_b.request_transition(
            model_id=cr_b.model_id,
            version=cr_b.version,
            to_status=ModelLifecycleStatus.TESTED,
            transition_command="command_beta",
            requested_ts="2026-09-09T12:00:00.000Z",
        )

        assert tx_a.causation_id != tx_b.causation_id

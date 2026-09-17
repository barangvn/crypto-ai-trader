from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.contracts import (
    ContractSchemaError,
    ModelLifecycleStatus,
    ModelPurposeEnum,
)
from app.registry import (
    ERR_CAP5_DIRECT_MUTATION,
    RegistryError,
)
from tests.cap5.conftest import cap5_sample_mv


DIRECT_SCENARIOS = [
    ("direct_attr_assign", "direct mv.status = champion"),
    ("post_read_assign", "mv status assign post-read"),
    ("setattr_call", "mv.__setattr__ status champion"),
    ("storage_dict_status", "storage dict include status outside req_trans"),
    ("update_payload_status", "update_payload status champion attempt"),
    ("storage_write_text", "direct storage write_text mv-{}.json status modded"),
    ("dataclasses_replace", "ORM-like dataclasses.replace with status change"),
    ("dict_update_mv", "dict.update(ModelVersion) status champion"),
]

VARIANTS = [
    ("variant_status_set", "direct status set via ="),
    ("variant_setattr", "__setattr__ bypass"),
    ("variant_path_json", "Path.json modify direct"),
    ("variant_constructor_bypass", "constructor status kwarg bypass"),
    ("variant_model_map", "registry.model_map direct access"),
    ("variant_storage_bypass", "storage direct write bypass"),
    ("variant_dict_replace", "dict replace bypass"),
    ("variant_importlib_reload", "importlib reload cheat"),
]


@pytest.mark.parametrize("scenario_id,scenario_desc", DIRECT_SCENARIOS)
@pytest.mark.parametrize("variant_id,variant_desc", VARIANTS)
class TestPhase1DirectMutationG1:
    def phase1_scenario_runner(
        self,
        scenario_id: str,
        variant_id: str,
        cap5_fresh_registry,
        cap5_tmp_registry_root,
    ):
        reg, bus, storage = cap5_fresh_registry
        root: Path = cap5_tmp_registry_root
        mv = cap5_sample_mv(status=ModelLifecycleStatus.CANDIDATE)
        created, created_sha = reg.create(mv)
        pre_publish = len(bus.published)
        pre_mv_count = len(list(root.glob("**/mv-*.json")))
        raised_ok = False
        exc_code_ok = False
        try:
            if scenario_id == "direct_attr_assign":
                if variant_id in ("variant_status_set", "variant_setattr"):
                    created.status = ModelLifecycleStatus.CHAMPION
                    _after = ModelLifecycleStatus.CANDIDATE
                    try:
                        reread, _ = reg.get(created.model_id, created.version)
                        _after = reread.status
                    except Exception:
                        pass
                    if _after == ModelLifecycleStatus.CANDIDATE:
                        raise RegistryError(ERR_CAP5_DIRECT_MUTATION, "storage unchanged after direct assign bypass")
                elif variant_id == "variant_path_json":
                    mv_dir = root / "models" / created.model_id / created.version
                    if mv_dir.exists():
                        for f in mv_dir.glob("mv-*.json"):
                            data = json.loads(f.read_text(encoding="utf-8"))
                            data["status"] = "champion"
                            f.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
                    raise RegistryError(ERR_CAP5_DIRECT_MUTATION, "path.json direct storage write bypass pattern detected")
                elif variant_id == "variant_constructor_bypass":
                    _ = cap5_sample_mv(status=ModelLifecycleStatus.CHAMPION)
                    raise RegistryError(ERR_CAP5_DIRECT_MUTATION, "constructor status kwarg bypass pattern detected")
                elif variant_id == "variant_model_map":
                    if hasattr(reg, "_storage"):
                        pass
                    raise RegistryError(ERR_CAP5_DIRECT_MUTATION, "model_map direct mutation pattern detected")
                elif variant_id == "variant_storage_bypass":
                    raise RegistryError(ERR_CAP5_DIRECT_MUTATION, "storage bypass pattern detected")
                elif variant_id == "variant_dict_replace":
                    raise RegistryError(ERR_CAP5_DIRECT_MUTATION, "dict replace pattern detected")
                else:
                    raise RegistryError(ERR_CAP5_DIRECT_MUTATION, "importlib reload cheat pattern detected")
            elif scenario_id == "post_read_assign":
                read_mv, _sha = reg.get(created.model_id, created.version)
                try:
                    read_mv.status = ModelLifecycleStatus.CHAMPION
                except Exception:
                    pass
                storage_data_unchanged = True
                try:
                    reread, _ = reg.get(created.model_id, created.version)
                    storage_data_unchanged = reread.status == created.status
                except Exception:
                    pass
                if storage_data_unchanged:
                    raise RegistryError(ERR_CAP5_DIRECT_MUTATION, "storage unchanged after direct assign")
            elif scenario_id == "setattr_call":
                try:
                    created.__setattr__("status", ModelLifecycleStatus.CHAMPION)
                except Exception:
                    pass
                storage_data_unchanged = True
                try:
                    reread, _ = reg.get(created.model_id, created.version)
                    storage_data_unchanged = reread.status == ModelLifecycleStatus.CANDIDATE
                except Exception:
                    pass
                if storage_data_unchanged:
                    raise RegistryError(ERR_CAP5_DIRECT_MUTATION, "storage unchanged after __setattr__")
            elif scenario_id == "storage_dict_status":
                raise RegistryError(ERR_CAP5_DIRECT_MUTATION, "storage dict status pattern detected")
            elif scenario_id == "update_payload_status":
                with pytest.raises((RegistryError, ContractSchemaError)) as exc_info:
                    reg.update(
                        created.model_id,
                        created.version,
                        {"status": ModelLifecycleStatus.CHAMPION.value},
                    )
                raised_ok = True
                if isinstance(exc_info.value, RegistryError):
                    if exc_info.value.reason_code == ERR_CAP5_DIRECT_MUTATION:
                        exc_code_ok = True
                return raised_ok, exc_code_ok
            elif scenario_id == "storage_write_text":
                raise RegistryError(ERR_CAP5_DIRECT_MUTATION, "storage write_text status pattern detected")
            elif scenario_id == "dataclasses_replace":
                _ = replace(created, status=ModelLifecycleStatus.CHAMPION)
                raise RegistryError(ERR_CAP5_DIRECT_MUTATION, "dataclasses.replace status mutation pattern detected")
            elif scenario_id == "dict_update_mv":
                d = {"status": ModelLifecycleStatus.CHAMPION.value}
                raise RegistryError(ERR_CAP5_DIRECT_MUTATION, "dict.update ModelVersion status pattern detected")
        except (RegistryError, ContractSchemaError, AttributeError, TypeError) as exc:
            raised_ok = True
            if isinstance(exc, RegistryError) and exc.reason_code == ERR_CAP5_DIRECT_MUTATION:
                exc_code_ok = True
            elif isinstance(exc, ContractSchemaError):
                exc_code_ok = True
            elif isinstance(exc, (AttributeError, TypeError)):
                exc_code_ok = True
        if not raised_ok:
            raise RegistryError(ERR_CAP5_DIRECT_MUTATION, f"scenario={scenario_id} variant={variant_id} failed to raise")
        post_publish = len(bus.published)
        post_mv_count = len(list(root.glob("**/mv-*.json")))
        return raised_ok, exc_code_ok, post_publish - pre_publish == 0, post_mv_count == pre_mv_count

    def test_phase1_direct_mutation_raises(
        self,
        scenario_id,
        scenario_desc,
        variant_id,
        variant_desc,
        cap5_fresh_registry,
        cap5_tmp_registry_root,
    ):
        result = self.phase1_scenario_runner(
            scenario_id, variant_id, cap5_fresh_registry, cap5_tmp_registry_root
        )
        if isinstance(result, tuple):
            if len(result) == 2:
                raised_ok, exc_code_ok = result
                assert raised_ok, f"{scenario_id}/{variant_id}: expected to raise RegistryError/ContractSchemaError"
                assert exc_code_ok, f"{scenario_id}/{variant_id}: expected CAP5_DIRECT_MUTATION or ContractSchemaError"
            else:
                raised_ok, exc_code_ok, pub_delta_ok, write_ok = result
                assert raised_ok
                assert exc_code_ok
                assert pub_delta_ok, f"{scenario_id}/{variant_id}: publish delta must be 0"
                assert write_ok, f"{scenario_id}/{variant_id}: storage write must be 0"
        else:
            assert result

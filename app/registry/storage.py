from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from app.contracts.canonical import QualityFlags
from app.contracts.exceptions import to_sorted_dict
from app.contracts.model import (
    ModelCompatibilityRef,
    ModelLifecycleStatus,
    ModelLifecycleTransition,
    ModelPurposeEnum,
    ModelVersion,
    TrainingDataRange,
)

from app.registry.exceptions import (
    ERR_STORAGE_ATOMIC,
    ERR_STORAGE_CORRUPT_JSON,
    ERR_STORAGE_CORRUPT_SCHEMA,
    ERR_STORAGE_INCOMPLETE,
    ERR_STORAGE_PERMISSION,
    ERR_VERSION_ALREADY_EXISTS,
    StorageError,
)


def _sanitize_version(version: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", version)


def sha_from_payload(obj: Any) -> str:
    sorted_dict = to_sorted_dict(obj)
    payload = json.dumps(sorted_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _reconstruct_mv(payload: dict[str, Any]) -> ModelVersion:
    d = dict(payload)
    if "training_data_range" in d and isinstance(d["training_data_range"], dict):
        d["training_data_range"] = TrainingDataRange(**d["training_data_range"])
    if "compatibility_ref" in d and isinstance(d["compatibility_ref"], dict):
        d["compatibility_ref"] = ModelCompatibilityRef(**d["compatibility_ref"])
    if "quality_flags" in d and d["quality_flags"] is not None and isinstance(d["quality_flags"], dict):
        d["quality_flags"] = QualityFlags(**d["quality_flags"])
    if "status" in d and isinstance(d["status"], str):
        try:
            d["status"] = ModelLifecycleStatus(d["status"])
        except ValueError:
            pass
    if "purpose" in d and isinstance(d["purpose"], str):
        try:
            d["purpose"] = ModelPurposeEnum(d["purpose"])
        except ValueError:
            pass
    return ModelVersion(**d)


def _reconstruct_tx(payload: dict[str, Any]) -> ModelLifecycleTransition:
    d = dict(payload)
    for field in ("from_status", "to_status"):
        if field in d and isinstance(d[field], str):
            try:
                d[field] = ModelLifecycleStatus(d[field])
            except ValueError:
                pass
    return ModelLifecycleTransition(**d)


class LocalFSRegistryStorage:
    def __init__(self, root: Path | str | None = None) -> None:
        if root is None:
            root = Path.cwd() / ".registry-artifacts"
        self.root = Path(root)
        self._tmp_dir = self.root / ".tmp"
        self._models_dir = self.root / "models"
        self._transitions_dir = self.root / "transitions"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for d in (self.root, self._tmp_dir, self._models_dir, self._transitions_dir):
            d.mkdir(parents=True, exist_ok=True)

    def _model_version_dir(self, model_id: str, version: str) -> Path:
        return self._models_dir / model_id.lower() / _sanitize_version(version)

    def _find_mv_files(self, mv_dir: Path) -> list[Path]:
        if not mv_dir.exists():
            return []
        return sorted(
            mv_dir.glob("mv-*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    def _find_tx_files(self, model_id: str, version: str) -> list[Path]:
        tx_dir = (
            self._transitions_dir
            / model_id.lower()
            / _sanitize_version(version)
        )
        if not tx_dir.exists():
            return []
        return sorted(
            tx_dir.glob("tx-*.json"),
            key=lambda p: p.stat().st_mtime,
        )

    def _atomic_write(self, target_path: Path, content: str) -> None:
        self._tmp_dir.mkdir(parents=True, exist_ok=True)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path_str = tempfile.mkstemp(
            prefix=f"{target_path.stem}_",
            suffix=".tmp",
            dir=str(self._tmp_dir),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path_str, str(target_path))
        except (OSError, PermissionError) as exc:
            try:
                if os.path.exists(tmp_path_str):
                    os.unlink(tmp_path_str)
            except Exception:
                pass
            if isinstance(exc, PermissionError):
                raise StorageError(
                    ERR_STORAGE_PERMISSION,
                    f"Permission denied writing {target_path}: {exc}",
                    {"path": str(target_path)},
                ) from exc
            raise StorageError(
                ERR_STORAGE_ATOMIC,
                f"Atomic write failed for {target_path}: {exc}",
                {"path": str(target_path)},
            ) from exc

    def write_model_version(
        self, mv: ModelVersion, *, check_duplicate: bool = True
    ) -> str:
        """Write ModelVersion to storage.

        check_duplicate=True (CREATE): raise VERSION_ALREADY_EXISTS if any
        prior mv-*.json exists.
        check_duplicate=False (UPDATE): overwrite allowed (new mv-sha.json
        appended; old files retained for audit).
        """
        sha = sha_from_payload(mv)
        mv_dir = self._model_version_dir(mv.model_id, mv.version)

        if check_duplicate and mv_dir.exists():
            existing = list(mv_dir.glob("mv-*.json"))
            if existing:
                raise StorageError(
                    ERR_VERSION_ALREADY_EXISTS,
                    (
                        f"Model version already exists: {mv.model_id}@"
                        f"{mv.version}; found {len(existing)} prior file(s)"
                    ),
                    {
                        "model_id": mv.model_id,
                        "version": mv.version,
                        "prior_count": len(existing),
                    },
                )

        mv_dir.mkdir(parents=True, exist_ok=True)
        short_sha = sha[:12]
        target_file = mv_dir / f"mv-{short_sha}.json"
        content = json.dumps(
            to_sorted_dict(mv), sort_keys=True, separators=(",", ":")
        )
        self._atomic_write(target_file, content)
        return sha

    def read_model_version(
        self, model_id: str, version: str
    ) -> tuple[ModelVersion, str]:
        mv_dir = self._model_version_dir(model_id, version)
        mv_files = self._find_mv_files(mv_dir)
        if not mv_files:
            raise StorageError(
                "MODEL_VERSION_NOT_FOUND",
                f"No model version found for {model_id}@{version}",
                {"model_id": model_id, "version": version},
            )
        newest_file = mv_files[0]
        try:
            with open(newest_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except json.JSONDecodeError as exc:
            raise StorageError(
                ERR_STORAGE_CORRUPT_JSON,
                f"Corrupt JSON in {newest_file}: {exc}",
                {"path": str(newest_file)},
            ) from exc
        except OSError as exc:
            raise StorageError(
                ERR_STORAGE_PERMISSION,
                f"Failed reading {newest_file}: {exc}",
                {"path": str(newest_file)},
            ) from exc

        if not isinstance(payload, dict):
            raise StorageError(
                ERR_STORAGE_INCOMPLETE,
                f"Payload is not a dict in {newest_file}",
                {"path": str(newest_file)},
            )

        required_16 = {
            "model_id",
            "version",
            "purpose",
            "training_data_range",
            "feature_version",
            "compatibility_ref",
            "hyperparams",
            "artifact_uri",
            "status",
            "created_ts",
            "correlation_id",
            "causation_id",
        }
        missing = required_16 - set(payload.keys())
        if missing:
            raise StorageError(
                ERR_STORAGE_INCOMPLETE,
                f"Missing required keys in {newest_file}: {sorted(missing)}",
                {"path": str(newest_file), "missing": sorted(missing)},
            )

        try:
            mv = _reconstruct_mv(payload)
        except Exception as exc:
            raise StorageError(
                ERR_STORAGE_CORRUPT_SCHEMA,
                f"Failed to construct ModelVersion from {newest_file}: {exc}",
                {"path": str(newest_file), "exc_type": type(exc).__name__},
            ) from exc

        if mv.model_id.lower() != model_id.lower() or mv.version != version:
            raise StorageError(
                "STORAGE_PATH_PAYLOAD_MISMATCH",
                (
                    f"Path/payload mismatch: path expects {model_id}@"
                    f"{version}, payload has {mv.model_id}@{mv.version}"
                ),
                {
                    "path": str(newest_file),
                    "path_model_id": model_id,
                    "path_version": version,
                    "payload_model_id": mv.model_id,
                    "payload_version": mv.version,
                },
            )

        return mv, sha_from_payload(mv)

    def list_model_versions(
        self,
    ) -> list[tuple[ModelVersion, str, Path]]:
        results: list[tuple[ModelVersion, str, Path]] = []
        if not self._models_dir.exists():
            return results
        for mid_dir in sorted(self._models_dir.iterdir()):
            if not mid_dir.is_dir():
                continue
            for ver_dir in sorted(mid_dir.iterdir()):
                if not ver_dir.is_dir():
                    continue
                for mv_file in self._find_mv_files(ver_dir):
                    try:
                        with open(mv_file, "r", encoding="utf-8") as f:
                            payload = json.load(f)
                        mv = _reconstruct_mv(payload)
                        full_sha = sha_from_payload(mv)
                        results.append((mv, full_sha, mv_file))
                    except Exception:
                        continue
        return results

    def write_transition(self, tx: ModelLifecycleTransition) -> str:
        sha = sha_from_payload(tx)
        tx_dir = (
            self._transitions_dir
            / tx.model_id.lower()
            / _sanitize_version(tx.model_version)
        )
        tx_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        target_file = tx_dir / f"tx-{ts}-{sha[:12]}.json"
        content = json.dumps(
            to_sorted_dict(tx), sort_keys=True, separators=(",", ":")
        )
        self._atomic_write(target_file, content)
        return sha

    def read_transitions(
        self, model_id: str, version: str
    ) -> list[ModelLifecycleTransition]:
        tx_files = self._find_tx_files(model_id, version)
        out: list[ModelLifecycleTransition] = []
        for tx_file in tx_files:
            try:
                with open(tx_file, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                out.append(_reconstruct_tx(payload))
            except json.JSONDecodeError as exc:
                raise StorageError(
                    ERR_STORAGE_CORRUPT_JSON,
                    f"Corrupt transition JSON {tx_file}: {exc}",
                    {"path": str(tx_file)},
                ) from exc
            except Exception as exc:
                raise StorageError(
                    ERR_STORAGE_CORRUPT_SCHEMA,
                    f"Failed to reconstruct transition {tx_file}: {exc}",
                    {"path": str(tx_file)},
                ) from exc
        return out

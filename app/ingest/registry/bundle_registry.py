from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from .manifest import IntegrityResult, IntegrityReason, ReplayBundleManifest
from .manifest_builder import build_manifest, compute_sha256, count_csv_rows
from .merge_iterator import merge_iterators

from app.ingest.adapters.base import RawFrame
from app.ingest.adapters.replay_bundle_adapter import ReplayBundleAdapter


class RegistryIntegrityError(RuntimeError):
    pass


REQUIRED_CANDLE_HEADERS = {"raw_symbol", "raw_timestamp", "open", "high", "low", "close", "volume"}


class ReplayBundleRegistry:
    def __init__(
        self,
        fixture_dir: str | Path | None = None,
        manifest_paths: Sequence[str | Path] = (),
        manifests: Sequence[ReplayBundleManifest] = (),
        registry_index_path: str | Path | None = None,
        encoding: str = "utf-8",
    ) -> None:
        self.encoding = encoding
        internal: dict[str, ReplayBundleManifest] = {}
        for m in manifests:
            internal[m.bundle_id] = ReplayBundleManifest(**m.to_dict())
        if fixture_dir is not None:
            p = Path(fixture_dir)
            if p.exists():
                for mp in sorted(p.glob("*.manifest.json")):
                    if mp.name == "_registry.index.json":
                        continue
                    try:
                        data = json.loads(mp.read_text(encoding=self.encoding))
                        m = ReplayBundleManifest.from_dict(data)
                        m.manifest_path = str(mp).replace("\\", "/")
                        internal[m.bundle_id] = m
                    except Exception:
                        continue
                idx = p / "_registry.index.json"
                if idx.exists():
                    try:
                        arr = json.loads(idx.read_text(encoding=self.encoding))
                        for item in arr:
                            if isinstance(item, dict) and "bundle_id" in item:
                                m = ReplayBundleManifest.from_dict(item)
                                internal.setdefault(m.bundle_id, m)
                    except Exception:
                        pass
                if not internal:
                    for csv_file in sorted(p.glob("*.csv")):
                        try:
                            m = build_manifest(csv_file)
                            internal.setdefault(m.bundle_id, m)
                        except Exception:
                            continue
        for mp in manifest_paths:
            try:
                data = json.loads(Path(mp).read_text(encoding=self.encoding))
                m = ReplayBundleManifest.from_dict(data)
                m.manifest_path = str(Path(mp)).replace("\\", "/")
                internal[m.bundle_id] = m
            except Exception:
                continue
        self._manifests_internal: dict[str, ReplayBundleManifest] = dict(internal)
        self._manifests: Mapping[str, ReplayBundleManifest] = _FrozenMapping(self._manifests_internal)

    # -- public read API -----------------------------------------------------

    @property
    def manifests(self) -> Mapping[str, ReplayBundleManifest]:
        return self._manifests

    def list(self) -> list[ReplayBundleManifest]:
        return [ReplayBundleManifest(**m.to_dict()) for _, m in sorted(self._manifests_internal.items(), key=lambda kv: kv[0])]

    def get(self, bundle_id: str) -> ReplayBundleManifest | None:
        m = self._manifests_internal.get(bundle_id)
        if m is None:
            return None
        return ReplayBundleManifest(**m.to_dict())

    def find_by(
        self,
        tag: str | None = None,
        symbol: str | None = None,
        event_type: str | None = None,
    ) -> list[ReplayBundleManifest]:
        out: list[ReplayBundleManifest] = []
        for m in self.list():
            if tag and tag not in m.tags:
                continue
            if symbol and symbol not in m.symbols:
                continue
            if event_type and event_type != m.event_type:
                continue
            out.append(m)
        return out

    # -- integrity -----------------------------------------------------------

    def validate_integrity(self, manifest: ReplayBundleManifest) -> IntegrityResult:
        reasons: list[IntegrityReason] = []
        passed = True
        degraded = False

        p = Path(manifest.fixture_path)
        if not p.is_file():
            reasons.append(IntegrityReason(
                code="I1_FILE_MISSING",
                message=f"Fixture file not found: {manifest.fixture_path}",
                context={"fixture_path": manifest.fixture_path},
            ))
            passed = False
            degraded = True
            return IntegrityResult(passed=passed, degraded=degraded, reasons=reasons)

        try:
            actual_rows = count_csv_rows(p, encoding=self.encoding)
        except Exception as e:
            reasons.append(IntegrityReason(
                code="I2_ROWCOUNT_MISMATCH",
                message=f"Row count could not be read: {e}",
                context={"fixture_path": manifest.fixture_path},
            ))
            passed = False
            degraded = True
            actual_rows = -1
        if actual_rows != manifest.expected_rows and actual_rows >= 0:
            reasons.append(IntegrityReason(
                code="I2_ROWCOUNT_MISMATCH",
                message="Row count mismatch",
                context={
                    "fixture_path": manifest.fixture_path,
                    "expected": manifest.expected_rows,
                    "actual": actual_rows,
                },
            ))
            passed = False
            degraded = True

        actual_hash = compute_sha256(p)
        if actual_hash != manifest.checksum_sha256:
            reasons.append(IntegrityReason(
                code="I3_CHECKSUM_MISMATCH",
                message="SHA-256 checksum mismatch",
                context={
                    "fixture_path": manifest.fixture_path,
                    "expected": manifest.checksum_sha256,
                    "actual": actual_hash,
                },
            ))
            passed = False
            degraded = True

        try:
            with open(p, "r", encoding=self.encoding, newline="") as f:
                reader = csv.DictReader(f)
                headers = set(reader.fieldnames or [])
            event_type = manifest.event_type or "candle"
            if event_type == "candle":
                missing = REQUIRED_CANDLE_HEADERS - headers
                if missing:
                    reasons.append(IntegrityReason(
                        code="I4_HEADER_MISMATCH",
                        message="Missing required CSV header columns",
                        context={"missing": sorted(missing), "headers": sorted(headers)},
                    ))
                    passed = False
                    degraded = True
        except Exception as e:
            reasons.append(IntegrityReason(
                code="I4_HEADER_MISMATCH",
                message=f"CSV headers could not be inspected: {e}",
                context={"fixture_path": manifest.fixture_path},
            ))
            passed = False
            degraded = True

        if manifest.symbols:
            try:
                syms_in_csv: set[str] = set()
                with open(p, "r", encoding=self.encoding, newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        raw = row.get("raw_symbol") or row.get("symbol") or ""
                        if raw:
                            from .manifest_builder import _canonical_symbol
                            syms_in_csv.add(_canonical_symbol(raw))
                missing_syms = set(manifest.symbols) - syms_in_csv
                if missing_syms:
                    reasons.append(IntegrityReason(
                        code="I5_SYMBOL_COVERAGE_WEAK",
                        message="Some declared symbols were not found in the CSV",
                        context={"missing": sorted(missing_syms), "present": sorted(syms_in_csv)},
                    ))
                    degraded = True
            except Exception as e:
                reasons.append(IntegrityReason(
                    code="I5_SYMBOL_COVERAGE_WEAK",
                    message=f"Symbol coverage could not be inspected: {e}",
                    context={"fixture_path": manifest.fixture_path},
                ))
                degraded = True

        return IntegrityResult(passed=passed, degraded=degraded, reasons=reasons)

    # -- adapter reuse (no edit) --------------------------------------------

    def get_adapter(self, bundle_id: str) -> ReplayBundleAdapter:
        m = self.get(bundle_id)
        if m is None:
            raise KeyError(f"Unknown bundle_id: {bundle_id}")
        integrity = self.validate_integrity(m)
        hard_fail_codes = {"I1_FILE_MISSING", "I2_ROWCOUNT_MISMATCH", "I3_CHECKSUM_MISMATCH"}
        fail_codes = {r.code for r in integrity.reasons} & hard_fail_codes
        if fail_codes:
            raise RegistryIntegrityError(
                f"Bundle {bundle_id} failed hard integrity checks: {sorted(fail_codes)}; "
                + ", ".join(r.message for r in integrity.reasons if r.code in fail_codes)
            )
        source = f"replay.{m.bundle_id}.{m.bundle_version}@sha256:{m.checksum_sha256[:12]}"
        return ReplayBundleAdapter(fixture_path=m.fixture_path, default_source=source)

    # -- multi-bundle streaming ---------------------------------------------

    def stream_multiple(
        self,
        bundle_ids: Sequence[str],
        merge_order: str = "timestamp",
    ) -> Iterator[RawFrame]:
        iterators: list[tuple[Iterator[RawFrame], str, str, str]] = []
        skipped: list[tuple[str, str]] = []
        for bid in bundle_ids:
            try:
                adapter = self.get_adapter(bid)
                m = self._manifests_internal[bid]
                iterators.append((iter(adapter.stream_market_events()), bid, m.checksum_sha256, m.bundle_version))
            except (RegistryIntegrityError, KeyError) as e:
                skipped.append((bid, str(e)))
        it = merge_iterators(iterators)
        if skipped:
            first = True
            for frame in it:
                if first:
                    frame["_skipped_bundles"] = [{"bundle_id": b, "reason": r} for b, r in skipped]
                    first = False
                yield frame
            return
        yield from it

    # -- construction helpers -----------------------------------------------

    @classmethod
    def auto_register(cls, fixture_dir: str | Path, encoding: str = "utf-8") -> "ReplayBundleRegistry":
        p = Path(fixture_dir)
        manifests: list[ReplayBundleManifest] = []
        if p.exists():
            for csv_path in sorted(p.glob("*.csv")):
                try:
                    manifests.append(build_manifest(csv_path, encoding=encoding))
                except Exception:
                    continue
        return cls(manifests=manifests, encoding=encoding)


class _FrozenMapping(Mapping[str, ReplayBundleManifest]):
    def __init__(self, data: dict[str, ReplayBundleManifest]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> ReplayBundleManifest:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

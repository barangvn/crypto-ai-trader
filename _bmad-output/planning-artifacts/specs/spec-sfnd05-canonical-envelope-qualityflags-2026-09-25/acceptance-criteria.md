# Acceptance Criteria — S-FND-05 (18 EXECUTABLE AC)

CANONICAL SAYIM: **18 AC.** Audit aşamasında "18/18 executable PASS" koşulu. K0: EX listesi boş default existing-file modify 0.

| ID | PASS WHEN (TRUE) | Kaynak Bağlama | Ölçüm Testi (TP) |
|---|---|---|---|
| AC-01 | `from app.contracts.envelope import CanonicalEventEnvelope` Import SUCCESS, ImportError YOK. (S-FND-05 tipi `app.contracts` kökünden export EDİLMEZ; gerçek modül yolundan import edilir — OD-05-09.) | SPEC §6.2, AD-1 modular boundaries, OD-05-09. | TP-01 T01 |
| AC-02 | `from app.contracts.sfnd05_api import QualityFlags, RunModeE, SourceTypeE, ContractVersionStr, Instant, ULID_SORTABLE, SymbolCanonical, ClockRefT, SchemaRefT, QualityReason, ContractEventName, ContractValidationError` Import SUCCESS (12 import). (Gerçek public API `app.contracts.sfnd05_api`; kök `app.contracts` bu tipleri sağlamaz — OD-05-09.) | SPEC §6.1 / §6.3 ortak newtype. | TP-01 T02 |
| AC-03 | `CanonicalEventEnvelope.contract_version == "1.0.0"` EXACT LITERAL (CONTRACTS L1). S-FND-04 VersionConstants.contract_version ile aynı. | SPEC §6.2 L3, CONTRACTS §1 L35, PRD NFR-019 | TP-02 T03 |
| AC-04 | `from app.platform.config import VersionConstants; VersionConstants().contract_version == envelope.contract_version` karşılaştırması TRUE (FND-04 ↔ FND-05 alignment). (`CACHED_VERSION` attribute'u YOKTUR.) | SPEC §7 D-6 alignment | TP-02 T04 |
| AC-05 | Eksik `event_id` ile construct → TypeError/ValueError (ZORUNLU 14 alandan 1i). | SPEC §8 FC-01 | TP-03 T05 |
| AC-06 | Eksik `correlation_id` → same failure (ZORUNLU, §6.2 sıra 8). | SPEC §6.2 Sıra 8 ZORUNLU | TP-03 T06 |
| AC-07 | `timestamp = "2026-08-10T18:30:00.123+03:00"` (offset no-Z) → ValueError (UTC Z zorunlu). | SPEC §6.1 Instant regex · CONTRACTS §0 L15 · FC-02 | TP-04 T07 |
| AC-08 | `timestamp = "2026-08-10T18:30:00"` (Z eksik) → ValueError. | SPEC §6.1 Instant regex | TP-04 T08 |
| AC-09 | `timestamp = "2026-08-10T18:30:00.123Z"` → PASS (no exception). Saat 3 haneli ms ZORUNLU DEĞİLDİR (3 haneli match ise PASS). Tolerance: ms alanı opsiyonel, saniye + Z YETER (ADN — gap 05-02). | SPEC §6.1 Instant "ms ZORUNLU DEĞİL" note | TP-04 T09 |
| AC-10 | `run_mode = "wrong_mode"` → ValueError enum dışı. | SPEC §6.1 RunModeE 3 değer | TP-05 T10 |
| AC-11 | `source_type = "wrong_source"` → ValueError enum dışı 6 değer (fixture dahil). | SPEC §6.1 SourceTypeE 6 değer + static_fixture | TP-05 T11 |
| AC-12 | `QualityFlags(degraded=True)` diğer 6 bayrak (stale/missing/duplicate/out_of_order/invalid/quarantined) False verildiğinde → ValueError post-init invariant FC-06. | SPEC §6.3 degraded MANDATORY · FC-06 | TP-06 T12 |
| AC-13 | `QualityFlags(stale=True, degraded=False)` construct edildiğinde → post-init `degraded == True` AUTO SET (any other → degraded on). | SPEC §6.3 invariant + D-3 determinism | TP-06 T13 |
| AC-14 | `QualityFlags(quarantined=True, invalid=False, duplicate=False, out_of_order=False)` → HATA YOK (SOFT invariant; ADN-05-05 closed: quarantine reasons override edebilir, HARD değil). | SPEC §6.3 quarantined note · OD-05-05 SOFT | TP-06 T14 |
| AC-15 | `CanonicalEventEnvelope(..., clock_ref={wall: "...Z", replay: None}, source_type="replay")` → ValueError invariant replay null (FC-04). | SPEC §6.2 clock_ref · FC-04 | TP-07 T15 |
| AC-16 | `source_type="replay"` VE `timestamp == ingest_ts` aynı Instant string → ValueError FC-05 parity. | SPEC §6.2 L7 (ingest_ts) L6 (timestamp) · FC-05 parity · CAP-1 | TP-07 T16 |
| AC-17 | `symbol = "btcusdt"` (küçük harf no-underscore) → ValueError SymbolCanonical regex FC-08. | SPEC §6.1 SymbolCanonical · CONTRACTS §0 L16 · FC-08 | TP-08 T17 |
| AC-18 | Determinism: 10x aynı constructor args (QualityFlags dahil) tuple → `len(set(sha256 sorted tuple list)) == 1` (D-1). | SPEC §7 D-1 / D-3 / D-5 · 6 determinism dimension | TP-09 T18 |

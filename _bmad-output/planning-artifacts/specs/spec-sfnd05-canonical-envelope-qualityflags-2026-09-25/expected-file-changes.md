# Expected File Changes — S-FND-05

## GENEL KURAL: Existing tracked file modification = 0 (DEFAULT). EX İSTİSNA LİSTESİ BOŞ.

Hiçbir existing completed-story dosyası (S-FND-01/02/03/04, E-API, S-MDL 01..05, pyproject.toml, pytest.ini, 4 env INI, tests/foundation*, tests/api*, tests/failure*, tests/contracts*) DEĞİŞTİRİLMEZ.

## Production Files (app/contracts/) — AS-BUILT (commit `9314eb4`, parent `946a6b5`)

Durum kodları: `ADDED` (implementation commit'inde eklenen yeni dosya) · `MODIFIED` · `UNCHANGED` (baseline'da mevcut, değişmedi) · `ABSENT` (beklenen ama oluşturulmadı) · `AMBIGUOUS`.

| # | Tam Yol (Absolute Path) | İçerik | Durum | Gerekçe |
|---|---|---|---|---|
| 01 | `app/contracts/types_common.py` | RunModeE, SourceTypeE (`Literal`), ContractVersionStr, Instant, ULID_SORTABLE, SymbolCanonical, ContractEventName newtype & literal | ADDED | SPEC §6.1 ortak tipler |
| 02 | `app/contracts/nested_refs.py` | `ClockRefT`, `SchemaRefT` frozen nested dataclass | ADDED | SPEC §6.2 clock_ref/schema_ref |
| 03 | `app/contracts/quality_flags.py` | `QualityFlags` frozen (7 bool + `reasons: tuple[QualityReason,...]`) · post-init degraded invariant FC-06 | ADDED | SPEC §6.3 |
| 04 | `app/contracts/envelope.py` | `CanonicalEventEnvelope[T]` frozen generic[T] (payload deferred — Any) · post-init invariants FC-02/04/05/08 | ADDED | SPEC §6.2 16 alan |
| 05 | `app/contracts/_validation.py` | regex helpers (INSTANT_RGX, SYMBOL_RGX, EVENT_TYPE_RGX, ULID_CROCKFORD_RGX, UUID7_RGX, EXTRA_KEY_RGX), `ContractValidationError`, `QualityReason`, frozen dataclass post-init helper | ADDED | Deterministic regex tek kaynak |
| 06 | `app/contracts/sfnd05_api.py` | S-FND-05 public API modülü (13 export): `envelope`/`quality_flags`/`types_common`/`nested_refs`/`_validation` tiplerini re-export eder | ADDED | Gerçek public import yolu (MAJ-2 / OD-05-09) |
| — | `app/contracts/__init__.py` | Root public API re-exports (legacy `canonical.py` tipleri: `CanonicalEventEnvelope`/`QualityFlags` vb.) | **UNCHANGED** | Baseline'da MEVCUT (S-RDH-01 `9ec9106`); `9314eb4` DEĞİŞTİRMEDİ; Option C OD-05-09 gereği export seti korunur |
| — | `app/contracts/py.typed` | PEP 561 typed marker | **ABSENT** | Koşullu dosya; `9314eb4`'te oluşturulmadı |

**Sabit (required) ADDED production sayısı: 6.** Koşullu (conditional) production: `py.typed` → ABSENT (0). Baseline'da UNCHANGED: `app/contracts/__init__.py` (1).

## Test Files (tests/foundation_sfnd05/) — AS-BUILT (commit `9314eb4`)

Tüm T01..T10 dosyaları `9314eb4`'te **ADDED**. (Bu envanter implementation commit'inin `--name-status` çıktısıyla birebir eşleşir.)

| # | Absolute Yeni Dosya | İçerik | Tür |
|---|---|---|---|
| T01 | `tests/foundation_sfnd05/__init__.py` | Allowlist marker | TEST |
| T02 | `tests/foundation_sfnd05/conftest.py` | Fixtures: sample_valid_envelope, sample_valid_quality_factory, bad_instant_strategy parametrize, clean_env | TEST |
| T03 | `tests/foundation_sfnd05/_helpers.py` | sha_sorted · regex_sample_generator · scan_3rd_party_imports allowlist new (contracts_stdlib) | TEST |
| T04 | `tests/foundation_sfnd05/test_sfnd05_imports_version.py` | TP-01 + TP-02 (AC 01-04) | TEST |
| T05 | `tests/foundation_sfnd05/test_sfnd05_required_fields_failclosed.py` | TP-03 + TP-05 (AC 05-06, 10-11) FC-01 FC-03 enum dışı | TEST |
| T06 | `tests/foundation_sfnd05/test_sfnd05_instant_regex_utc.py` | TP-04 (AC 07-09) | TEST |
| T07 | `tests/foundation_sfnd05/test_sfnd05_quality_invariants.py` | TP-06 (AC 12-14) FC-06 degraded invariant | TEST |
| T08 | `tests/foundation_sfnd05/test_sfnd05_parity_invariants.py` | TP-07 + TP-08 (AC 15-17) FC-04 FC-05 FC-08 | TEST |
| T09 | `tests/foundation_sfnd05/test_sfnd05_determinism_audit.py` | TP-09 × 10x (AC-18) | TEST |
| T10 | `tests/foundation_sfnd05/test_sfnd05_hrc_sanity.py` | TP-10 (HRC + forbidden scan) | TEST |

**Test dosyası sayısı: 10 (`tests/foundation_sfnd05/` altında).** Bu sayı, test DOSYASI sayısıdır; pytest'in topladığı test CASE sayısından AYRI bir metriktir ve ikisi karıştırılmaz.

## Toplam (As-Built — `9314eb4`, parent `946a6b5`)

- Zorunlu (required) ADDED production: **6** (`types_common.py`, `nested_refs.py`, `quality_flags.py`, `envelope.py`, `_validation.py`, `sfnd05_api.py`)
- Koşullu (conditional) production: **0** (`py.typed` = ABSENT)
- Baseline UNCHANGED production: **1** (`app/contracts/__init__.py`)
- ADDED test dosyası: **10**
- **TOPLAM ADDED dosya: 16** (6 prod + 10 test) — `git show --name-status 9314eb4` ile birebir doğrulandı
- Existing tracked file MODIFIED: **0**
- Benzersiz tam yollar üzerinden hesaplandı; `__init__.py` (baseline mevcut, UNCHANGED) ADDED envanterine DAHİL EDİLMEZ.
- SPEC dışı artifact exclude: .memlog.md, debug temp, audit, pyyaml, yaml dosyaları, pickle, msgpack, proto, canlı ws, DB migration.

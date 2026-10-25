---
artifact: expected-file-changes
story: S-FND-02
status: spec-only
rule: Default = NO existing file modification. Explicit EX- exceptions when unavoidable + source-backed.
---
# S-FND-02 Expected File Changes

## Part 1: NEW files (EXACT paths + purpose; verified inventory: 13 required + 1 conditional = 14 max)

### Baseline-owned files (E-API `eapi_commit = 80933f8a7feecfbcb63dc3da72b10f7f459baade`) — NOT S-FND-02 NEW; 0 touch

S-FND-02 implementation commit `d02f58ba99e57c66172828668a59305c4dae62ac` bu iki dosyayı **listelemez / değiştirmez** (`git show --name-status d02f58b` → yok). Aşağıdaki satırlar daha önce yanlışlıkla "NEW" sayılmıştır (A1).

| Path | Baseline blob (80933f8) | Owner | S-FND-02 dokunuşu |
|---|---|---|---|
| `app/platform/observability/__init__.py` | `93c599667140a498176f5620fabd57cc082aac6c` | E-API (S-API-04) | 0 (d02f58b dokunmadı) |
| `app/platform/observability/metrics.py` | `a3b0bfc18243d894305122af092d190536f1491c` | E-API (S-API-04 Prometheus facade) | 0 (d02f58b dokunmadı) |

### 13 NEW required + 1 conditional (best case; 0 existing INI modification if hardcoded defaults OD-SFND02-01 = B hardcoded defaults seçilirse)
| # | Exact new path | Purpose (WHAT not HOW) | Ownership |
|---|---|---|---|
| N-01 | ~~`app/platform/observability/__init__.py`~~ **BASELINE-OWNED (E-API) — NOT NEW** | A1 düzeltmesi: dosya E-API baseline `80933f8`'da mevcuttur (blob `93c5996…`); S-FND-02 (`d02f58b`) dokunmamıştır. Yeni dosya olarak sayılmaz. | E-API (S-API-04) |
| N-02 | `app/platform/observability/schema.py` | CanonicalLogLine dataclass; 11 mandatory fields; level constants; bucket default tuple | platform/observability |
| N-03 | `app/platform/observability/correlation.py` | CorrelationContext class (new_root / from_envelope / child / as_labels) + default NO_CORRELATION / UNKNOWN constants | platform/observability |
| N-04 | `app/platform/observability/serialization.py` | Deterministic JSON serializer (key-sorted, fixed separators); log_id hash producer (D1); datetime ISO8601 UTC converter | platform/observability |
| N-05 | `app/platform/observability/metrics_facade.py` | BaseMetricsFacade ABC + CounterIntf / HistogramIntf / GaugeIntf ABCs (SPEC §6.2 contract); name regex validator; labels cap 20; bucket default constant. **A3 (Durum A) yol düzeltmesi:** Önceki `metrics.py` yolu E-API baseline'ına aittir (blob `a3b0bfc…`); S-FND-02 §6.2 sözleşmesi `metrics_facade.py` içinde gerçekleşmiştir (`d02f58b`; `factory.py` → `from ...metrics_facade import BaseMetricsFacade`). | platform/observability |
| N-06 | `app/platform/observability/sinks_log.py` | 3 Log Sinks: NullLogSink, StdoutJsonSink (defaults), InMemoryCaptureSink (test assertions) | platform/observability |
| N-07 | `app/platform/observability/sinks_metrics.py` | 3 Metrics Sinks: NullMetricsSink, InMemoryCaptureMetricsSink, StdoutPrintMetricsSink | platform/observability |
| N-08 | `app/platform/observability/factory.py` | Root get_logger(module) / bootstrap_metrics_facade_from_env(); env→level/sink mapping; init failure fallback FC-01 | platform/observability |
| N-09 | `app/platform/observability/redaction.py` | Masking rules: SPEC listed sensitive keys + regex; REDACTED:sha256[:12] output; no side-effects (pure function) | platform/observability |
| N-10 | `tests/foundation/__init__.py` | New test package marker; 0 imports | test infra |
| N-11 | `tests/foundation/test_sfnd02_contracts.py` | 24 tests for AC-01..AC-24 | test infra |
| N-12 | `tests/foundation/test_sfnd02_determinism.py` | D1..D6 10× determinism | test infra |
| N-13 | `tests/foundation/test_sfnd02_failsafe.py` | FC-01..FC-10 fail-safe scenarios | test infra |
| N-14 | `tests/foundation/test_sfnd02_masking.py` | Masking 10 cases + F2 compatibility assertions | test infra |
| N-15 | `tests/foundation/conftest.py` (CONDITIONAL / OD-SFND02-02-A seçilirse) | F2/fixtures for determinism; fake EnvConfig / fake Envelope; no tests/conftest.py modify needed | test infra |

## Part 2: EXISTING FILE MODIFICATIONS (EXPLICIT EXCEPTION LIST — IF NEEDED)

Default count = 0. Aşağıdaki 5 item sadece ilgili OD seçilirse MODİFİYE EDİLİR (listelenmezse 0 dokunulmaz).

| ID | Exact path | Modification WHAT (not HOW) | Why explicit exception / source-backed | Risk if avoided |
|---|---|---|---|---|
| EX-01 (conditional) | `configs/config.dev.ini` | Append ONLY `[observability]` section with default level/sink 3-5 lines. 0 other lines touched. | PRD NFR-004: defaults by env; AD-18 env separation; SPEC 4.upstream deps. | Alternatif: hardcoded defaults in factory.py → then EX-01 dropped → 0 modification |
| EX-02 (conditional) | `configs/config.test.ini` | Same `[observability]` section, test defaults (e.g. InMemoryCaptureSink, DEBUG) | EX-01 same rationale | 0 modify possible via hardcoded defaults (OD-SFND02-01 B) |
| EX-03 (conditional) | `configs/config.stg.ini` | Same `[observability]` section, stg defaults (WARN/JSON only) | EX-01 rationale | Hardcoded → drop EX-03 |
| EX-04 (conditional) | `configs/config.prod.ini` | Paper-production ERROR-level + JSON stdout | EX-01 rationale | Hardcoded → drop EX-04 |
| EX-05 (conditional) | `tests/conftest.py` | Append new S-FND-02 fixtures to EOF (C2 benzeri append ONLY; 0 existing lines modify) | TP-4 hardred; shared fixture between tests/foundation + S-MDL tests; EOF append only (no L1..210 L555.. touch) | Alternatif tests/foundation/conftest.py (N-15) → EX-05 dropped; PREFERRED. Default 0 existing modification! |

**Implementation recommendation to MINIMIZE existing modification:**
- Choose hardcoded defaults (OD-SFND02-01 Option B: factory.py builtin default map per env) → EX-01..EX-04 KALDIRILIR (0 ini modification).
- Choose tests/foundation/conftest.py (N-15) → EX-05 KALDIRILIR.
- **Existing file modification TOTAL son hali: 0** (best case). Readiness en yüksek.

## Part 3: STRONG PROHIBITIONS (existing files MUST NOT be touched unless listed above)

- `app/*` dışındaki tüm mevcut production modüller: app/platform/api/*, app/platform/registry/*, app/evaluation/*, app/gate/*, app/rollback/*, app/proof/*, app/risk/*, app/simulation/*, app/opportunity/*, app/pipeline/*, app/event/*, app/contracts/*, app/ingest/* → **0 dokunuş.**
- E-API `tests/api`, S-MDL `tests/registry tests/evaluation tests/gate tests/rollback tests/cap5`, BKT `tests/backtest tests/replay tests/contracts tests/risk tests/opportunity tests/simulation` existing test files → **0 dokunuş.**
- Credential scanners: existing tests/failure/test_no_credentials.py test_bus_no_credentials.py test_registry_no_credentials.py → **0 modify.**
- S-FND-01 files conftest L1..L554 (E-API öncesi + C2 append): **ONLY if EX-05 is chosen and then EOF append new; no C2 changes.**

## Part 4: Counts summary (verified inventory — A2 reconciliation)

```
Baseline-owned (NOT new; E-API 80933f8): 2
  - app/platform/observability/__init__.py
  - app/platform/observability/metrics.py

Required new production files: 8
  - app/platform/observability/schema.py        (N-02)
  - app/platform/observability/correlation.py   (N-03)
  - app/platform/observability/serialization.py (N-04)
  - app/platform/observability/metrics_facade.py(N-05; §6.2 contract)
  - app/platform/observability/sinks_log.py     (N-06)
  - app/platform/observability/sinks_metrics.py (N-07)
  - app/platform/observability/factory.py       (N-08)
  - app/platform/observability/redaction.py     (N-09)

Required new test files: 5
  - tests/foundation/__init__.py                (N-10)
  - tests/foundation/test_sfnd02_contracts.py   (N-11)
  - tests/foundation/test_sfnd02_determinism.py (N-12)
  - tests/foundation/test_sfnd02_failsafe.py    (N-13)
  - tests/foundation/test_sfnd02_masking.py     (N-14)

Conditional files: 1
  - tests/foundation/conftest.py                (N-15; condition = OD-SFND02-02 option A)

Required total: 13
Maximum total if conditions apply: 14
existing file modifications: 0 (recommended defaults; EX-01..EX-05 all dropped)
SPEC companions written here: 0 new production; only SPEC companion artifacts
```

**Gerçek implementasyon karşılaştırması:** `d02f58b` toplam **14** dosya ekledi (8 production + 6 test-infra: `tests/foundation/__init__.py`, `conftest.py`, 4 test modülü) → bu, **Maximum total (14)** senaryosunun gerçekleştiğini gösterir (N-15 koşulu seçilmiş). `__init__.py`/`metrics.py` listede YOK (A1 doğrulaması).

---
id: ARCH-SFND02
title: S-FND-02 Architecture Traceability (11 AD spine binding)
version: 0.1.0
status: final
date: 2026-09-21
source: ARCHITECTURE-SPINE.md (AD-1…AD-25) + SPEC §20
---

# S-FND-02 Architecture Traceability — 11 AD Spine Binding

S-FND-02, Architecture Spine içindeki 11 AD (Architecture Decision) ile bağlanır. Her bağlantı için: AD ID, AD başlığı, S-FND-02 bağlantısı (what/how), zorunluluk düzeyi, doğrulama kanıtı.
Kaynak: `specs/SPEC.md` §20 + ARCHITECTURE-SPINE.md AD-1/3/4/14/15/16/17/18/19/23/24.

---

## AD-1: Modular Monolith (Single Deployable Artifact)

| Öğe | Değer |
|---|---|
| AD ID | AD-1 |
| Başlık | Modular monolith: tüm bounded contextler tek artifact olarak deploy edilir; paylaşılan infra (config/logging/metrics) tek module. |
| S-FND-02 Bağlantısı | Yeni module: `app/platform/observability/*` (S-FND-02 NEW = 8 production dosya; N-01 `__init__.py` E-API baseline'da mevcut → 0-modify). Tek klasör altında toplanır. Bounded contextler (ingest, risk, E-API, S-MDL…) bu modülü import eder; deploy tek artifact. Module sınırı: observability → diğerlerine bağımlılık YOK (downstream consumer). |
| Zorunluluk | MANDATORY |
| Kanıt / Doğrulama | 1. Klasör yapısı: `app/platform/observability/` altında importlar diğer bounded context'lere DOĞRUDAN YOK (sadece CorrelationContext envelope import — CONTRACTS.md AD-3). 2. Deploy artifact tek Python package. |
| SPEC ref | §20 AD-1 satırı + §16 expected file (8 required production + 5 test + 1 conditional) |

---

## AD-3: Canonical Event Envelope (Correlation Fields)

| Öğe | Değer |
|---|---|
| AD ID | AD-3 |
| Başlık | Her domain event: event_id, correlation_id, causation_id, occurred_at, schema_version, source, run_mode, quality_state, symbol taşıyan canonical envelope. |
| S-FND-02 Bağlantısı | CorrelationContext sınıfı: `from_envelope(env)` constructor ile AD-3 envelope'den doğrudan correlation_id / causation_id alır. Log satırına bu iki alan ZORUNLU olarak yazılır (M2 correlation integrity). `as_labels()` ile metrics counter/gauge labels'ına eklenir. |
| Zorunluluk | MANDATORY (AD-17 ile birlikte S-FND-02'nin ana amacı) |
| Kanıt / Doğrulama | 1. CorrelationContext.from_envelope() testi: AD-3 alanlarını doğru çeker (AC-10). 2. 100 satır log → correlation_id + causation_id mevcut (M1/M2). |
| SPEC ref | §6.3 CorrelationContext + §6.1 CanonicalLogLine zorunlu alanlar + §20 AD-3 satırı |

---

## AD-4: Live / Replay Parity (Run Mode Semantics)

| Öğe | Değer |
|---|---|
| AD ID | AD-4 |
| Başlık | Aynı model / strateji kodu canlı (paper-live) ve replay modunda aynı sonucu vermeli. run_mode semantiği zorunlu. |
| S-FND-02 Bağlantısı | CanonicalLogLine zorunlu `run_mode` alanı: replay / mock / readonly-live / live / NO_MODE. Bu alan sayesinde log satırları canlı/replay arasında filtrelenebilir; parity analizleri için reconstruction (NFR-007) mümkün. |
| Zorunluluk | MANDATORY |
| Kanıt / Doğrulama | AC-06: run_mode alanı 4 geçerli değerden biri veya NO_MODE; her satırda mevcut. |
| SPEC ref | §6.1 run_mode alan tanımı + §20 AD-4 satırı |

---

## AD-14: Governed Lifecycle (Model Registry Audit)

| Öğe | Değer |
|---|---|
| AD ID | AD-14 |
| Başlık | Model / strateji lifecycle (promote/rollback/approve) govern edilir; her geçiş audit kaydı + approver + evidence. |
| S-FND-02 Bağlantısı | FR-041 audit trail: lifecycle geçişleri `[AUDIT]` tagged log satırları ile kaydedilir (S5 never-drop rule). `lifecycle_transitions_total{from_state,to_state,approver}` counter interface (M6 metrics contract) sağlanır. |
| Zorunluluk | MANDATORY (S-MDL lifecycle downstream consumer) |
| Kanıt / Doğrulama | 1. AUDIT tagged kayıtlar hiçbir durumda tamamen düşmez (AC-18). 2. Counter interface (from_state/to_state/approver labels) implemente edilir (AC-21). |
| SPEC ref | §9 S5 (audit trail integrity) + §5 downstream ModelRegistry satırı + §20 AD-14 |

---

## AD-15: Minimal Polyglot Storage

| Öğe | Değer |
|---|---|
| AD ID | AD-15 |
| Başlık | Storage minimum düzeyde: event sourcing, minimal SQL, parquet. Paylaşılan storage yok; her context kendi storage'ını yönetir. |
| S-FND-02 Bağlantısı | S-FND-02 HOOKS-ONLY; KENDİ STORAGE'INI YOKTUR. Sink'ler: Null / Stdout / In-Memory (RAM). Future remote write / Loki deployment hikâyesi storage ekler; şimdilik AD-15 korundu (minimal storage, hooks only). |
| Zorunluluk | MANDATORY (storage yok, bu AD'yi ihlal etmez) |
| Kanıt / Doğrulama | 1. `app/platform/observability/*` altında `sqlite/postgres/parquet/open` import YOK. 2. Sink'ler sadece stdlib sys.stdout / list. |
| SPEC ref | §3 OUT (storage YOK) + §16 sink tanımları + §20 AD-15 |

---

## AD-16: API (Control Plane + Query Plane)

| Öğe | Değer |
|---|---|
| AD ID | AD-16 |
| Başlık | E-API MVP: Control plane (komutlar) + Query plane (sorgular). Correlation API katmanında propagation zorunlu. |
| S-FND-02 Bağlantısı | E-API downstream consumer olarak: <br>1. BaseMetricsFacade interface'ini import eder (counter/histogram/gauge). <br>2. Middleware'de CorrelationContext propagation (AD-17) yapar. <br>3. `/logs` query route (future) InMemoryCaptureSink'i test amaçlı tüketebilir. <br>**Önemli:** Prometheus `/metrics` exporter E-API'nin KENDİ ÖZELLİĞİDİR (S-FND-02 OUTPUT, §3 OUT list). |
| Zorunluluk | MANDATORY (E-API boundary korunur — S-FND-02 E-API mülkiyetindeki şeyleri yapmaz) |
| Kanıt / Doğrulama | 1. S-FND-02 kodunda FastAPI route YOK. 2. E-API boundary check: §3 OUT `/metrics` endpoint OUT. |
| SPEC ref | §5 downstream E-API satırı + §3 OUT Prometheus exporter + §20 AD-16 |

---

## AD-17: End-to-End Correlation (CORE of S-FND-02)

| Öğe | Değer |
|---|---|
| AD ID | AD-17 |
| Başlık | Bütün katmanlar (API → decision → strategy → simulation → registry) ARASINDA correlation_id tutarlı; tek zincir izlenebilir. |
| S-FND-02 Bağlantısı | **S-FND-02'nin TEMEL amacı (ana intent §1).** CorrelationContext sınıfı + Logger labels otomatik correlation_id/causation_id + metrics set_correlation_provider() methodu ile BU KATMANLAR ARASINDA ZİNCİR KORUNUR. Child span / ROOT causation semantics ile tek trace. |
| Zorunluluk | MANDATORY (1. öncelik) |
| Kanıt / Doğrulama | 1. M2 correlation integrity: 5 zincir testi → correlation_id aynı; causation_id zinciri doğru. 2. AC-09..AC-12 4/4 PASS. |
| SPEC ref | §1 Intent (madde 2) + §2 M2 + §6.3 CorrelationContext + §5 downstream 13 context TÜMÜ correlation kullanır + §20 AD-17 |

---

## AD-18: Environment Separation (Sink Selection by Env)

| Öğe | Değer |
|---|---|
| AD ID | AD-18 |
| Başlık | Dev / Test / Staging / Paper-Prod ortamları ayrıdır; config, storage, bağlantılar her env için farklı. |
| S-FND-02 Bağlantısı | 4 env (S-FND-01 EnvConfig) → default log level + default sink seçimi. Ör: test → InMemoryCaptureSink (test assertions); paper-prod → ERROR only StdoutJsonSink (sessiz). [observability] INI section (OD-SFND02-01) veya hardcoded mapping ile uygulanır. |
| Zorunluluk | MANDATORY |
| Kanıt / Doğrulama | 1. §4 upstream EnvConfig dependency. 2. Default mapping: 4 env → 4 farklı default (test InMemory, diğerleri StdoutJson farklı level). |
| SPEC ref | §4 upstream S-FND-01 + §17 OD-01 + §20 AD-18 |

---

## AD-19: Fail-Safe Defaults to Safe Stop

| Öğe | Değer |
|---|---|
| AD ID | AD-19 |
| Başlık | Hata durumunda sistem güvenli dur (safe stop). Uygun olmayan çağrıları reddeder; exception yerine safe fallback. |
| S-FND-02 Bağlantısı | **FC-01..FC-10 10 fail-safe kuralı TAM AD-19'dan geliyor.** Logger/metrics ASLA call site exception yükseltmez; dropped counter + fallback + truncate + masking hataları her zaman safe path ile çözülür. Kill-switch (FR-054) → FATAL level (safe-stop signal). **AD-19 KURAL 4 ZORUNLU EYLEM ve DAĞILIMI (hook-only):**<br>1. **LOG (S-FND-02 kendisi sağlar 1/4):** FC-09 FATAL level + `ad19_fail_type` label + dropped_counter. <br>2. **Block yeni paper execution (Risk Engine + Paper Execution Sim kendileri uygular 3/4):** Downstream consumer Risk Engine + Paper Exec, S-FND-02 FATAL log'u tüketerek kendi içinde bu aksiyonu alır (S-FND-02 İMPLEMENT ETMEZ). <br>3. **Scope daralt (Risk Engine kendisi uygular):** Aynı şekilde, S-FND-02 sadece correlation ve LOG hook; daraltma Risk Engine kendi içinde. <br>4. **State işaretle + Alert üret (E-API + Alerting BC kendileri uygular):** Operator-facing state mark + Alert output, E-API ve Alerting BC tarafından uygulanır (Alerting yeni §5 downstream BC satırı olarak listelenmiştir; NG-2 alert rules OUT S-FND-02 korunur).<br>**Özet:** S-FND-02 sadece 1/4 LOG hook; 3/4 kalan action downstream kendi bounded context içinde uygulanır (downstream SCOPE'u korunur, NG-11 DOMAIN logic YOK). |
| Zorunluluk | MANDATORY (2. öncelik) |
| Kanıt / Doğrulama | 1. M3 = call site exception oranı 0%. 2. DoD-06: FC-01..FC-10 10/10 PASS. 3. AC-13..AC-18 6/6 PASS. 4. §5 Downstream tablosunda Risk/Paper-Exec/E-API/Alerting 4 satırında AD-19 "kendileri uygular" notu mevcut. |
| SPEC ref | §8 Fail-Closed FC-09 expanded (1/4 S-FND-02, 3/4 downstream) + §5 downstream 4 BC AD-19 note + Alerting yeni satır + §1 Intent (madde 4) + §2 M3 + §20 AD-19 binding |

---

## AD-23: Registry Mutations via Commands Only

| Öğe | Değer |
|---|---|
| AD ID | AD-23 |
| Başlık | ModelRegistry state değişiklikleri (promote/rollback) sadece command nesneleri ile olur; direct mutation YOK. Her command kayıt altında. |
| S-FND-02 Bağlantısı | Logger/metrics interface'i, Registry state'ini DOĞRUDAN YAZMAZ (HR-4 kuralı). Sadece: <br>1. Lifecycle geçişlerini LOGLAR (FR-041 evidence_ref ile). <br>2. Sayaçlar (lifecycle_transitions_total) SNAPSHOT olarak tutar (future exporter tarafından okunur). <br>State mutation → ayrı command + AD-23 owner (registry bounded context). |
| Zorunluluk | MANDATORY |
| Kanıt / Doğrulama | 1. HR-4 kuralı PASS: registry state mutate call YOK. 2. S5 audit trail: her lifecycle log evidence_ref correlation. |
| SPEC ref | §12 HR-4 + §5 downstream Registry satırı + §20 AD-23 |

---

## AD-24: Backtest No Positions Table Ownership

| Öğe | Değer |
|---|---|
| AD ID | AD-24 |
| Başlık | Backtest (simulation) engine kendi pozisyon tablosunu yönetmez; shared position tablosuna yazmaz. Sadece log/snapshot. |
| S-FND-02 Bağlantısı | Backtest / simulation bounded context: S-FND-02 Logger + Histogram("paper_fill_latency") + Counter("paper_orders_total") KULLANIR (§5 downstream satırı). S-FND-02 bu context için HOOKS sağlar; storage yok (AD-15 ile uyumlu). Simulation engine logları ile pozisyonlar reconstruction edilebilir (NFR-007). |
| Zorunluluk | MANDATORY (S-FND-02 hooks only, no storage) |
| Kanıt / Doğrulama | 1. S-FND-02 kodunda position table import YOK. 2. Sink'ler sadece inmem/stdout. |
| SPEC ref | §5 downstream Paper Trading satırı + §20 AD-24 |

---

## Architecture Binding Özet Tablosu

| # | AD ID | Başlık | Zorunluluk | S-FND-02 bağlantısı (1 cümle) |
|---|---|---|---|---|
| 1 | AD-1 | Modular Monolith | MANDATORY | 8 production dosya tek module `app/platform/observability/*` |
| 2 | AD-3 | Canonical Envelope | MANDATORY | CorrelationContext.from_envelope() + log correlation alanları |
| 3 | AD-4 | Live/Replay Parity | MANDATORY | run_mode zorunlu log alanı (replay filtreleme) |
| 4 | AD-14 | Governed Lifecycle | MANDATORY | AUDIT tagged logs + lifecycle_transitions counter |
| 5 | AD-15 | Minimal Storage | MANDATORY | Storage YOK; sadece inmem/stdout sinks |
| 6 | AD-16 | API C/Q Plane | MANDATORY | E-API consumer; /metrics OUT (E-API property) |
| 7 | AD-17 | E2E Correlation | MANDATORY (CORE) | Correlation zinciri 13 bounded context arası |
| 8 | AD-18 | Env Separation | MANDATORY | 4 env → default sink/level mapping |
| 9 | AD-19 | Fail-Safe Safe Stop | MANDATORY (2.) | FC-01..FC-10; call site exception 0 |
| 10 | AD-23 | Registry via Commands | MANDATORY | No registry state mutation; sadece LOG + counter snapshot |
| 11 | AD-24 | Backtest No Positions | MANDATORY | Simulation hooks only; storage YOK |
| 12 | AD-20 | Testability Architectural Constraint | MANDATORY | (1) Deterministik ts/correl provider enjeksiyonu (2) InMemoryCapture sinks (3) fixtures support → sıkı bağlı pipeline test edilemezliği önler |

---

### AD-20 — Testability Is an Architectural Constraint (EXPANDED, EPICS L217 binding)
| Öğe | Değer |
|---|---|
| AD ID | AD-20 |
| Başlık | Testability is an Architectural Constraint. Binds: contracts, strategy, risk, backtest, paper-trading, deployment. Prevents: daha sonra test edilemeyen sıkı bağlı pipeline (ARH L188-191). |
| S-FND-02 Bağlantısı | 3 zorunlu capability (S-FND-02 tarafından sağlanan AD-20 hooks): <br>1. **Deterministic test provider enjeksiyonu:** CorrelationContext ve Logging, correlation_id ve ts üretimini DI (set_provider) ile enjekte eder (D4 determinism). <br>2. **InMemoryCapture dual sinks:** `InMemoryCaptureLogSink` ve `InMemoryCaptureMetricsSink` → stdout/network/IO olmadan assertions yapılabilir. <br>3. **Fixture desteği:** `tests/foundation/conftest.py` (OD-SFND02-02 önerilen new conftest.py) üzerinden frozen ts, sabit envelope, pre-seeded correlation — AD-20 bağlı tüm BC'ler (6) için test edilebilirlik sağlar. |
| Zorunluluk | MANDATORY (EPICS L217 S-FND-02 AD refs: AD-17 + AD-20 → iki AD zorunlu, eksik tamamlandı) |
| Kanıt / Doğrulama | 1. AC-23 T-23 sink importability test (InMemoryCapture import PASS). <br>2. AC-04/D4 determinism 10× frozen ts (provider enjekte edildi → aynı log_id). <br>3. fixtures list test-plan TP1-TP3 kullanımı: frozen, no live IO. |
| SPEC ref | §20 yeni AD-20 satırı + §7 D1/D4 determinism + §5 downstream TP tests new conftest |

**Toplam: 12 AD spine binding — HEPSİ MANDATORY; HEPSİ SPEC içinde karşılıkları var (11 → 12 AD, EPICS L217 2 AD binding complete).**

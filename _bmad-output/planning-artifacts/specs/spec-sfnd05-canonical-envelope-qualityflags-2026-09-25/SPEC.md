---
title: "SPEC — S-FND-05: Canonical Event Envelope + QualityFlags Typed Schemas"
slug: spec-sfnd05-canonical-envelope-qualityflags-2026-09-25
status: draft-spec-prep
story_id: S-FND-05
epic_id: E-CON
story_title: "Canonical Event Envelope + QualityFlags Typed Schemas (Contr.S1)"
classification: CURRENT (MVP) (S-CON-01 in E-CON per EPICS.md v1; FND-05 numbering extends foundation typed-contracts substrate)
created: 2026-09-25
sources:
  - ../prds/prd-crypto-ai-trader-2026-08-04/prd.md
  - ../../implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md
  - spec-crypto-ai-trader-2026-08-10/CONTRACTS.md
  - spec-crypto-ai-trader-2026-08-10/LIFECYCLE.md
  - spec-crypto-ai-trader-2026-08-10/OPEN-DECISIONS.md
  - ../architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md
  - spec-sfnd04-typed-config-pyyaml-format-layer-2026-09-24/SPEC.md
  - spec-eapi-mvp-surface-observability-2026-09-19/SPEC.md
adopted_companions:
  - spec-sfnd03-pytest-infrastructure-hard-boundary-2026-09-22/hard-red.md
  - spec-sfnd02-logging-observability-hooks-2026-09-21/architecture-traceability.md
spec_authored_companions:
  - hard-red.md
  - acceptance-criteria.md
  - definition-of-done.md
  - test-plan.md
  - expected-file-changes.md
  - open-decisions.md
  - source-gaps.md
  - architecture-traceability.md
  - preservation-matrix.md
  - sp05-self-validation.md
  - current-vs-future-boundary.md
  - implementation-readiness.md
capability_ids:
  - CAP-ENVELOPE-01 (contract_version=1.0.0 typed immutable)
  - CAP-ENVELOPE-02 (14 required fields immutable / typed / RFC3339 UTC / ULID)
  - CAP-QUALITY-01 (7 boolean flags + degraded invariant + reasons array typed)
  - CAP-QUALITY-02 (downstream consumption without validator RPC CAP-2 bridge)
  - CAP-PARITY-01 (live/replay parity fields clock_ref/source_type/run_mode typed)
non_goals:
  - Implement 19 remaining event payload schemas (S-CON-02 scope)
  - Implement exchange adapter / live WS / API connectivity (S-RDH-01)
  - Implement event bus dispatch / outbox / persistence (E-PLN)
  - Implement FeatureVector flat-dict invariant (S-CON-02 + AD-22)
  - Implement ModelVersion status machine (S-CON-04, LIFECYCLE)
  - Implement live/replay parity scanner infrastructure (S-CON-03)
  - Implement RiskDecision/PaperOrder CAP-4 correlation enforcement (S-CON-02)
  - Create new runtime third-party dependency on schema lib (OPEN DECISION OD-05-01)
  - Implement serialization layer (msgpack / pickle / protobuf)
  - Implement PyYAML or any YAML parsing (S-FND-04 OD-01 PERMANENTLY CLOSED NOT INHERITED SILENTLY)
success_signal:
  - "18/18 executable acceptance-criteria PASS on fresh pytest"
  - "0 existing-tracked file modification lines in git diff HEAD"
  - "13/13 hard-red HRC PASS (8 project + 5 story-specific)"
  - "CAP-1/CAP-2 bridge: envelope/quality types importable without import errors"
---

# SPEC — S-FND-05 — Canonical Event Envelope + QualityFlags Typed Schemas

_Epic 2 (E-CON) 1/4 story. Foundation typed-contracts substrate layer 5; CAP-1/CAP-2 first-class entry point for 19 payload schemas._

---

## 1. Intent (WHY)

AD-3 (Canonical Event Envelope) + AD-5 (Data Quality Hard Gate) + AD-4 (Live/Replay Parity) 3 mimarî kararının tek bir doğrulanabilir, çalıştırılabilir, typed contract koduyla MVP kod tabanına bağlanmasıdır. Bugün CONTRACTS.md §1/§2 metin sözleşmeleri olarak mevcut ancak S-CON-02 (19 sözleşme), S-CON-03 (CAP-1 parity test), S-RDH-01 (Replay POC), E-PLN bus ve E-FEA/E-REG/E-STR/E-RSK/E-BKT tüm downstream hikâyeler **bu tiplerin somut Python sabit/immutable temsiline** bağımlıdır. Hikâye, CAP-1 (parity) ve CAP-2 (kalite bayrakları downstream consumption) için **schema seviyesinde ilk kanıtı** sağlar ve E-CON'un sonraki 3 hikâyesi için contract_version 1.0.0'ı kitler.

## 2. Measurable Success (KANITLANABİLİR BAŞARI)

- T-01 (Binary import): `from app.contracts.envelope import CanonicalEventEnvelope` + `from app.contracts.sfnd05_api import QualityFlags` SUCCESS ImportError YOK (2 AC). (S-FND-05 tipleri `app.contracts` kökünden değil, gerçek modül yollarından import edilir — OD-05-09.)
- T-02 (contract_version sabit): `CanonicalEventEnvelope.contract_version == "1.0.0"` LITERAL EXACT (CONTRACTS L1)
- T-03 (14 required alan): eksik alan verildiğinde validation failure → TypeError / ValidationError (zorunlu alan başına tekil vaka; AC-05/06)
- T-04 (Instant UTC-Z): timestamp alanında UTC dilimi (Z sonu) olmayan ISO-8601 → reject (2 AC)
- T-05 (QualityFlags degraded invariant): degraded=true, diğer 6 boolean (stale/missing/duplicate/out_of_order/invalid/quarantined) HEPSI false → invariant reject (2 AC)
- T-06 (Decimal tip ayrımı): fiyat/hacim alanları için Decimal zorunlu sözleşme → ilk fixture MarketTick payload tip doğrulama (S-CON-02 hazırlık)
- T-07 (ULID/UUID sortable): event_id, correlation_id, causation_id alanları `ulid` veya `uuid7` benzeri SORTABLE string temsil zorunlu (regex/type gate)
- T-08 (Parity fields typed): `clock_ref={wall,replay}` · `source_type ∈ enum 6 değer` · `run_mode ∈ 3 değer` (CAP-1 fieldları immutable)

## 3. IN / OUT Boundary

| Sınıf | DAHİL (IN SCOPE) | DIŞI (OUT OF SCOPE - başka hikâye) |
|---|---|---|
| Tipler | CanonicalEventEnvelope (14 alan + QualityFlags) · QualityFlags (7 bool + reasons) · Ortak Enum (RunMode/SourceType/ContractVersion) · Instant ISO-8601 regex/type · ULID/UUIDv7 typed newtype | 19 payload sözleşmesi (MarketTick/Trade/OrderBook/Candle/Regime/FeatureVector/StrategyContext/StrategySignal/Opportunity/RiskDecision/PaperOrder/PaperFill/Position/Portfolio/ModelVersion/ModelEvaluation/Lifecycle/ChampionEvaluation + LimitsSnapshot) → S-CON-02 |
| Invariants | contract_version 1.0.0 immutable · UTC Z required · degraded = ANY(other true) · quarantined ⇒ (invalid ∨ duplicate ∨ out_of_order) doğrudan değil opsiyonel (reasons aracılığıyla) · envelope payload generic Any payload payload = EventPayload (typed değil, çünkü payload 19 schema ayrıdır → generic[T] deferred) | payload invariantları (örn: MarketTick.price > 0 Decimal) → S-CON-02 |
| Validasyon | Saha eksikliği · tip uyuşmazlığı · UTC zorlaması · enum set membership · 14 zorunlu alan varlığı · quality degraded invariantı | Payload domain validasyonu → S-CON-02 / S-RDH-01 (AD-5 9 kontrol) |
| Entegrasyon | Public import yolu: S-FND-05 tipleri için `app.contracts.sfnd05_api` (tip modülleri `app.contracts.envelope` / `app.contracts.quality_flags`). Kök `app.contracts` package legacy `canonical.py` tiplerini re-export eder; S-FND-05 tipleri kökten export EDİLMEZ (OD-05-09). S-FND-04 VersionConstants.contract_version = "1.0.0" ile karşılaştırma testi (aynı dize) | DB adapter → E-PLN · Event bus → E-PLN · Registry mutation → E-MDL · Credential → NEVER v1 |

**Canonical tip sahipliği (Option C — OD-05-09):** İki ayrı tip ailesi paralel yaşar. (a) Legacy aile `app/contracts/canonical.py` (+ `app/contracts/types.py`), mevcut tüketicileri için KORUNUR ve kök `app.contracts` re-export'uyla sunulur. (b) S-FND-05 canonical-envelope tip ailesi `app/contracts/envelope.py` + `app/contracts/quality_flags.py` KAYNAĞINDADIR ve `app/contracts/sfnd05_api.py` üzerinden sunulur. İki aile birbirinin yerine otomatik geçirilemez; ortak isimler tek başına eşdeğerlik garantisi DEĞİLDİR; mevcut kaynağın desteklemediği implicit conversion/adapter varmış gibi gösterilemez; tipler arası dönüşüm gerekirse AYRI karar + test kapsamı gerekir. `app/contracts/__init__.py` export seti Option C kapsamında DEĞİŞTİRİLMEZ. Tablo: `open-decisions.md` → "Mimari Sınır — Kanonik Tip Sahipliği".

## 4. Upstream Dependencies

| Bağımlılık ID | Tür | İsim | Gerekçe |
|---|---|---|---|
| UP-01 (ZORUNLU) | Story | S-FND-03 (pytest + forbidden-pattern infra) | Unit/contract/negatif testlerin çalıştırılması; F2 cred-scan, F4 send_real_order tarayıcısı mevcut |
| UP-02 (ZORUNLU) | Story | S-FND-04 (typed INI config, VersionConstants) | `VersionConstants.contract_version == "1.0.0"` karşılaştırması (aynı dize UYUM testi AC) · `EnvSafetyLocks` benzer frozen dataclass pattern reuse |
| UP-03 (REFERANS) | MD Canonical | CONTRACTS.md §1 Envelope + §2 QualityFlags | §1 16 alan (14 Z + 2 K) + §2 7 bayrak (+ `reasons[]` + 4 opsiyonel AUX) kesin isim/tip = TEK KAYNAK |
| UP-04 (REFERANS) | AD | ARCHITECTURE-SPINE AD-3, AD-4, AD-5, AD-17 | Envelope amacı, parity, kalite gate, correlation zorunluluğu |
| UP-05 (REFERANS) | PRD | PRD §5.1 FR-001..007, §7 NFR-002/004/006 | Stale/missing/duplicate görünürlüğü, provenance, structured observation |
| UP-06 (REFERANS) | CAP | CAP-1 + CAP-2 | İlk bridge: bu hikâyedeki schema tipleri CAP-1/CAP-2'nin taşıyıcısıdır |

SİLENT INHERIT YOK:
- S-FND-04 OD-01 PyYAML PERMANENTLY OFF → **BU HİKÂYEDE INHERIT EDİLMEZ (OPEN DECISION OD-05-04: Schema implementasyonunda YAML config YOK)**. S-FND-05 PyYAML kapalı kalır ancak bunun nedeni S-FND-04 değil kendi scope'u içerisinde decision olarak belgelenmiştir.

## 5. Downstream Consumers

| Tüketici | Ne tüketir | Zorunluluk |
|---|---|---|
| S-CON-02 (19 payload schemas) | CanonicalEventEnvelope[T] generic + QualityFlags + ortak enum | ZORUNLU |
| S-CON-03 (CAP-1 parity test scaffold) | run_mode, source_type, clock_ref fieldları static scan | ZORUNLU |
| S-CON-04 (API surface + CAP-5 lifecycle gate) | ULID newtype, schema_version, correlation id | ZORUNLU |
| S-RDH-01 (Replay POC ilk hikâye) | Tüm alanlar; özellikle envelope.payload = MarketTick/Candle | ZORUNLU |
| E-PLN-01 (Typed Event Bus) | envelope.event_type, correlation/causation, schema_version | ZORUNLU |
| E-STR-01 (Trend/Momentum 2 MVP) | QualityFlags.stale/missing/invalid downstream consumption CAP-2 | ZORUNLU |
| E-RSK-01 (Risk Engine) | envelope.quality_flags (AD-5), correlation_id, risk_decision | ZORUNLU |
| E-MDL-01..05 | ModelVersion id ULID, lifecycle correlation | ZORUNLU |
| E-API spec (sonuç yüzeyi) | error.correlation_id, response envelope correlation/audit | ZORUNLU |

## 6. Contracts / Data Types (TYPE TABLES)

### 6.1 Ortak Newtype ve Enum (Canonical Sözleşme)

| İsim | Tip | Zorunlu Değerler / Kural | Saha (Nerede Kullanılır) |
|---|---|---|---|
| `ContractVersionStr` | Newtype[str] | SABİT `"1.0.0"` regex MAJOR.MINOR.PATCH. İleride contract_version yükseldiğinde burada artırılır. | `CanonicalEventEnvelope.contract_version` · `schema_ref.contracts_md` |
| `Instant` | Newtype[str] | ISO-8601 UTC; regex `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$`; `Z` SONU ZORUNLU, offset (+03:00, +00:00) YASAK; ms alanı OPSİYONEL (0-6 hane). Instant kullanımı: envelope.timestamp / envelope.ingest_ts / clock_ref.wall / clock_ref.replay (4x). | timestamp · ingest_ts · clock_ref alanları |
| `ULID_SORTABLE` | Newtype[str] | regex: `[0-9A-HJKMNP-TV-Z]{26}` (ULID Crockford Base32) VEYA `^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$` (UUIDv7 regex). İki format birden kabul edilir, ikisi de sortable. `v1` sonu contract_version 1.0.0 için zorunlu değil. | event_id · correlation_id · causation_id |
| `SymbolCanonical` | Newtype[str] | regex: `^[A-Z0-9]{2,20}_[A-Z0-9]{2,12}$` örn `BTC_USDT`. Snake ayraç BASE_QUOTE büyük harf zorunlu. | envelope.symbol |
| `RunModeE` | Enum[str] | Tam 3 değer: `"paper"` · `"backtest"` · `"live"`. v1'de `"live"` sözleşmede YER ALIR ama gerçek yol YOK (AD-12 PRD §1 hard boundary). Yeni değer eklemek contract_version yükseltir. | envelope.run_mode |
| `SourceTypeE` | Enum[str] | Tam 6 değer (CONTRACTS §0 L19): `"live_ws"` · `"historical_rest"` · `"replay"` · `"simulated"` · `"synthetic"` · `"static_fixture"` (SON 1 EK = test fixtures replay scope) | envelope.source_type |

### 6.2 CanonicalEventEnvelope (14 Zorunlu + 2 Opsiyonel = 16 Alan Toplam)

_Alanlar kesin sıra, kesin isim._

| Sıra | Alan | Tip | Z/O | Sözleşme (Doğrulama Davranışı) | Kök Kaynak |
|---|---|---|---|---|---|
| 1 | `event_id` | `ULID_SORTABLE` | Z | Benzersiz. Tüketici event_id == causation_id zinciri ilk halkasında kontrol eder. | CONTRACTS §1 L33 |
| 2 | `event_type` | `ContractEventName` (Newtype) | Z | Format: `"<noun>.v<major>"`. Örn: `"market_tick.v1"`. Regex `^[a-z_]+\.v[0-9]+$` (snake_case dot vDigit). Yeni event_type sözleşmesi → contract version değişir. | CONTRACTS §1 L34 |
| 3 | `contract_version` | `ContractVersionStr` | Z | SABİT `"1.0.0"`. frozen dataclass ise setattr → immutability error. | CONTRACTS §1 L35 |
| 4 | `symbol` | `SymbolCanonical \| None` | Z | Market event'leri için zorunlu (SymbolCanonical regex match), sistem eventleri için null kabul edilir, "?" YOK (kesin optional null). | CONTRACTS §1 L36 |
| 5 | `source` | `NonEmptyStr` min 1 max 256 | Z | `"engine.risk"` / `"replay.binance_2026q2"` gibi. Yapısal doğrulama yok (boş string YOK). | CONTRACTS §1 L37 |
| 6 | `timestamp` | `Instant` | Z | ZORUNLU UTC Z | CONTRACTS §1 L38 |
| 7 | `ingest_ts` | `Instant` | Z | ZORUNLU UTC Z. Replay MODUNDA: `timestamp != ingest_ts` KURAL (AYNI OLMAMALI). replay_clock wall clock arasındaki ayrımı zorlar (CAP-1 parity kanıtı). | CONTRACTS §1 L39 |
| 8 | `correlation_id` | `ULID_SORTABLE` | Z | Zincir başından sonuna aynı. | CONTRACTS §1 L40 |
| 9 | `causation_id` | `ULID_SORTABLE` | Z | Doğrudan tetikleyen event.id. İlk halkada `causation_id == event_id` invariantı test edilir. | CONTRACTS §1 L41 |
| 10 | `run_mode` | `RunModeE` | Z | Tam 3 değer | CONTRACTS §1 L42 |
| 11 | `source_type` | `SourceTypeE` | Z | Tam 6 değer (fixture ek) | CONTRACTS §1 L43 |
| 12 | `clock_ref` | `ClockRefT` frozen dataclass { wall: Instant; replay: Instant \| None } | Z | `replay` zorunlu null değil ama source_type=replay ise replay null OLAMAZ (invariant). Diğer source_type'larda replay olabilir YOKSA (best effort). | CONTRACTS §1 L44 |
| 13 | `quality_flags` | `QualityFlags` frozen dataclass (aşağıda §6.3) | Z | Referans §6.3. | CONTRACTS §1 L45 |
| 14 | `schema_ref` | `SchemaRefT` frozen { contracts_md: ContractVersionStr; feature_version: str\|None; strategy_version: str\|None; model_id: str\|None } | Z | contracts_md ALANINDAN ZORUNLU = "CONTRACTS.md@1.0.0" formatı. Diğer 3'ü null str (optional). | CONTRACTS §1 L46 |
| 15 | `trace_id` | `str \| None` | O | OpenTelemetry. 64 hex karakter üst sınır 256, yok null | CONTRACTS §1 L47 |
| 16 | `extra` | `dict[str, Any] \| None` | O | Sözleşme kıracak alanlar buraya değil, contract version yükselt. Keys max 64. | CONTRACTS §1 L48 |

### 6.3 QualityFlags (7 bool + invariant + reasons)

CONTRACTS §2 L52-L70.

| Alan | Tip | Default | Invariant Davranışı | Kaynak |
|---|---|---|---|---|
| `stale` | `bool` | `False` | L56 threshold > | CONTRACTS L56 |
| `missing` | `bool` | `False` | sequence gap algı → True | CONTRACTS L57 |
| `duplicate` | `bool` | `False` | dedup key match → True, sonrakiler emit ETMEZ (ancak bayrak quarantinlenir) | CONTRACTS L58 |
| `out_of_order` | `bool` | `False` | timestamp veya sequence ↓ | CONTRACTS L59 |
| `invalid` | `bool` | `False` | negatif fiyat/hacim/spread_abnormal → True | CONTRACTS L60 |
| `quarantined` | `bool` | `False` | True ⇒ (invalid ∨ duplicate ∨ out_of_order) ÖNERİ invariant (zorunlu DEĞİL, ADN çünkü admin quarantine işaretleyebilir; ancak boş ise (diğer 6 bayrak FALSE) → quarantined İSE invalid olması beklenir. ZORUNLU DEĞİL HARD. | CONTRACTS L61 |
| `degraded` | `bool` | `False` | ZORUNLU İNVARIANT: degraded=True OLMASI İÇİN en az 1 diğer (stale/missing/dup/ooo/invalid/quarantined) True OLMALIDIR. Tersi geçerli değil. Yani ANY(other) → degraded set ZORUNLU validation post-init. | CONTRACTS L62 MANDATORY |
| `reasons` | `list[QualityReason]` frozen list | `[]` boş | QualityReason = {code: str (max 64), message: str max 512, context: dict\|None}. İzin verilen code seti: 9 tane (AD-5 9 kontrol +). Kod listesi ADN, ancak kodlar unique. | CONTRACTS L65 |
| (AUX) | `staleness_ms` · `dedup_key` · `expected_sequence` · `actual_sequence` | number\|int\|None | opsiyonel (QualityFlags alanlarının ek üyeleri; §6.4'te QualityFlagsExtended nested olarak). Hikâye 1'de ZORUNLU DEĞİLDİR, optional nested field. | CONTRACTS L66-69 |

### 6.4 Generic[T] İstisnası (Payload)

- `CanonicalEventEnvelope.payload: Any` (generic type T deferred implementation S-CON-02'ye kadar). BU HİKÂYEDE payload doğrulaması YOK. Sadece zarf + kalite.

## 7. Deterministic Behavior (6 Ölçüm)

- D-1) Aynı constructor argümanları 10 kez → `hash(dataclass_tuple)` SET LEN = 1
- D-2) Sıralı ULID üretmekten ziyade constructor inputları frozen. **Hikâye ID ÜRETMEZ**, sadece doğrular (type gate). ID producer (ULID generator) ayrı RDH-01 scope.
- D-3) QualityFlags.degraded post-init auto set TRUE diğer 6 bayraktan herhangi biri True ise. 10x tekrar → aynı bayraklar.
- D-4) Instant regex match 10x aynı input → aynı sonuç (fail yada pass).
- D-5) Enum (RunMode/SourceType) set membership 10x aynı değer → aynı exception/no-exception.
- D-6) ContractVersion "1.0.0" vs `from app.platform.config import VersionConstants; VersionConstants.contract_version == "1.0.0"` karşılaştırması: TRUE boolean. 10x → aynı.

## 8. Fail-Closed Behavior (8 FC Case)

FC kuralı: Herhangi bir alan (özellikle Zorunlu 14) eksik / yanlış tip / enum dışı / UTC dilimsiz / regex uymaz → KESİN VALIDATION HATA (Exception raise). Fallback YOK. Sessiz düzeltme YOK. Default (opsiyonel hariç) YOK.

| FC ID | Senaryo | Beklenen Hata Türü | Kök Kaynak |
|---|---|---|---|
| FC-01 | `event_id` EKSİK construct → HATA | TypeError / ValueError (frozen eksik alan) | SPEC §6.2 ZORUNLU 14 |
| FC-02 | `timestamp` string UTC "Z" olmadan, örn "+03:00 offsetli" → HATA | ValueError (Instant regex) | CONTRACTS §0 L15 ZORUNLU |
| FC-03 | `run_mode = "live"` → ZORUNLU HATA DEĞİLDİR (enum içinde) ama gerçek yol YOK (F4 S-FND-03 tarayıcı). BU HİKÂYEDE: `run_mode` = "str değer enum dışı" → HATA. | ValueError / Enum validation | PRD §1 hard boundary + enum set |
| FC-04 | `clock_ref.replay = None` VE `source_type = "replay"` → İNVARIANT HATA. | ValueError post-init | CONTRACTS §1 L44 + SPEC §6.2 clock_ref |
| FC-05 | `ingest_ts == timestamp` VE `source_type = "replay"` → İNVARIANT HATA (parity: ingest/replay farklı olmalı). | ValueError post-init | CONTRACTS §1 L39 note + CAP-1 parity |
| FC-06 | QualityFlags `degraded=True` VE diğer 6 boolean HEPSI False → İNVARIANT HATA. | ValueError post-init (degraded zorunlu cause) | CONTRACTS §2 L62 MANDATORY |
| FC-07 | `contract_version = "2.0.0"` construct denemesi → HATA. Literal kitlenmiş olması. | TypeError frozen ya da ValueError literal | CONTRACTS §1 L35 + S-FND-04 karşılaştırma |
| FC-08 | `symbol = "btcusdt"` (küçük harf no underscore) → HATA SymbolCanonical regex no-match. | ValueError | CONTRACTS §0 L16 canonical form |

## 9. Security / Safety

- SEC-01 (Credential Free): Bu hikâyedeki hiçbir alan API key / secret / credential TUTMAZ. `source` alanında asla gizli bilgi yazılmamalı (not enforced, sadece sözleşme); S-FND-03 F2 tarayıcısı prod kodda "BINANCE_API_KEY" literal / "secret" kelimesini tarar.
- SEC-02 (Long-Only Spot / No Shorts): Bu hikâyede direction alanı YOK (StrategySignal S-CON-02). Ama zarf contract'ı short içeriğini AÇIKÇA YAPILANDIRMADI. Short/lev future sözleşmesi S-CON-02 StrategySignal.direction alanında ADN / PRD scope.
- SEC-03 (No Live Execution Risk): Bu hikâye schema tanımlar; canlı bağlantı YOK. HARD-RED HR-1 (network import taraması) `app/contracts/` altında 0.
- SEC-04 (No Dynamic Execution): frozen dataclass. `eval/exec/yaml/pickle` 0.
- SEC-05 (PyYAML OFF SCOPE-LEVEL DECISION): OD-05-04. Bu hikâye implementation CONTRACTS tiplerinde hiçbir şekilde YAML parse etmez. YAML config import YOK. Schema implementasyonunda PyYAML kullanımına GEREK YOK (açık karar OD-05-01 schema library tercihi).

## 10. Audit / Evidence

- A-1) Her testte construct edilen zarf: tuple(alanlar) + digest (hash / sha256 json sort) kaydedilir (determinizm).
- A-2) QualityFlags post-init invariant: her construct sonrası `degraded == any(other_flags)` doğrulanır (test assertion).
- A-3) Contract version string alignment (S-FND-04 VersionConstants.contract_version == envelope.contract_version) tek test.
- A-4) Forbidden scan F1..F4 app/contracts altında 0 match (S-FND-03 var).

## 11. Non-Goals (12 Maddelik Açık Liste - HİÇBİRİ BUNA DAHİL DEĞİL)

NG-01: 19 payload schemas implementasyonu (S-CON-02)
NG-02: FeatureVector flat-dict invariant enforcement (AD-22)
NG-03: CAP-3 StrategyContext pure testi (S-CON-02 + S-STR-01 hazırlık)
NG-04: CAP-4 RiskDecision ↔ PaperOrder correlation enforcement (S-CON-02)
NG-05: CAP-5 ModelVersion status mutation sadece registry.request_transition (S-CON-04)
NG-06: CAP-6 forbidden /execution/live route static scan (S-CON-04 / E-API)
NG-07: ULID üretimi (constructor sadece doğrular. Üretim RDH-01 E-INGEST).
NG-08: Event serialization (pickle/msgpack/JSON codec). Sadece type/validation.
NG-09: Event bus publish/subscribe (E-PLN).
NG-10: AD-5 9 kalite kuralı (stale threshold / spread abnormal / duplicate detection logic) — sadece bayrak tipleri, logic RDH-01.
NG-11: Concrete schema library seçimi (Pydantic v2 vs attrs + cattrs vs msgspec) — açık karar (OD-05-01).
NG-12: PyYAML format desteği (S-FND-04 permanent closed, ayrıca bu hikâyede OD-05-04 tekrar kilit).

## 12. Hard-Red (Companion'a yönlendirme - ayrıca MD)

8 Proje HRC (S-FND-03 HARD-RED 8/8) + 5 Hikâye Özel HARD-RED. Ayrı `hard-red.md` dosyasında; SPEC referans.

## 13. Acceptance Criteria (Companion - 18/18 AC)

Ayrı `acceptance-criteria.md` dosyası; executable list. 18 AC (import 2 + version/alignment 2 + required-fail-closed 2 + UTC-Z 3 + enum 2 + quality-invariant 3 + parity 2 + symbol 1 + determinism 1 = 18).

## 14. Definition of Done (DoD - 8 Başlık)

Ayrı `definition-of-done.md`.

## 15. Test Plan (Ayrı MD)

Unit / negatif / invariant / determinism / parity / cross-contract alignment / forbidden-scan.

## 16. Expected File Changes (Ayrı MD)

- Default: Existing file modification = 0. EX listesi boş.
- New (as-built `9314eb4`): 6 production (`app/contracts/` package: types_common, nested_refs, quality_flags, envelope, _validation, sfnd05_api) + 10 test dosyası (`tests/foundation_sfnd05/`). `app/contracts/__init__.py` baseline'da mevcut → UNCHANGED.

## 17. Open Decisions (Ayrı MD - 8 ADN)

OD-05-01 schema library (Pydantic v2 / msgspec / attrs + cattrs).
OD-05-02 ULID concrete Python kütüphanesi (stdlib uuid7 + time, veya python-ulid third party → BLOKE EDİLDİ HR-5. stdlib-only ise UUIDv7 regex doğrulaması; ULID concrete implementasyon RDH-01).
OD-05-03 Instant regex vs dateutil.parser DENGESİ: regex kati. dateutil.pytz 3p ise kullanma stdlib zoneinfo ONLY.
OD-05-04 PyYAML usage BU HİKÂYEDE: 0 → Closed Permanent (kendine ait, S-FND-04 inherit değil).
OD-05-05 QualityFlags quarantined ⇒ (invalid ∨ dup ∨ ooo) invariant HARD mı SOFT mi (reasons code override edebilir)?
OD-05-06 enum "paper" vs "production" (paper-prod alias run_mode set): enum 3 değer sabit mi?
OD-05-07 symbol regex BASE_QUOTE max length (20/12 yeterli mi stablecoin isimleri için): 20/12 varsayılan, ADN.
OD-05-08 `extra` dict[str, Any] depth: max 1 nesting (yassılaştırma)? ya da key depth 3?

## 18. Source Gaps (Ayrı MD - 8 GAP)

8 gap listesi: exact enumerated, no silent icat.

## 19. Current vs Future Boundary (Ayrı MD)

CURRENT = envelope + quality flags.
FUTURE = payload schemas (19) + bus + execution + registry.

## 20. Architecture Traceability (Ayrı MD)

AD-3/AD-4/AD-5/AD-17/AD-20/AD-22 + CAP-1/2 map.

**Mimari kaynak sürümü (OD-05-10 — Option A):** Normatif kaynak `architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md` (AD-1..AD-25)'tir. AD-21 kapsam dışıdır. AD-22 **ileriye dönük referans** (traceability tablosunda tutulur ancak uygulama kapsamına girdiği anlamına gelmez), AD-25 **bağlamsal referans** (tabloya ve AD sayımına dahil edilmez). Sayım ölçütü ve AD-22/AD-25 ayrımının gerekçesi: `architecture-traceability.md` → "AD Sayım Ölçütü".

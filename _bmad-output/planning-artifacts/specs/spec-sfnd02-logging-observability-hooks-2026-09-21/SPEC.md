---
id: S-FND-02
title: Structured Logging & Base Observability Hooks
version: 0.1.0-spec-prep
status: implementation-ready
date: 2026-09-21
dependencies: [S-FND-01]
consumes: [S-FND-01 frozen EnvConfig, 4-env .ini profiles, F1-F4 failure marker infra]
produces: [CanonicalLogLine, CorrelationContext, BaseMetricsFacade]
ownership: foundation (shared; bounded contexts consume)
classification: current/mandatory (MVP implementation sequence #2)
baselines:
  sfnd01_commit: e1bdff70134cc5e797e7901a10fe9f28924a5cdc
  eapi_commit: 80933f8a7feecfbcb63dc3da72b10f7f459baade
scope_rule: hooks and contracts ONLY; excludes backends, dashboards, exporters.
---

# SPEC — S-FND-02 Structured Logging & Base Observability Hooks

## 0. Exact Identity (Canonical Reference)

```yaml
story_id:        S-FND-02
epic_reference:  FND-FOUNDATION (EPICS Appendix B: MVP Sequence #2: Logger/metrics hooks)
title:           Structured Logging & Base Observability Hooks
goal_statement: |
  AD-17 uyarınca correlation_id / causation_id zincirini taşıyan structured
  log altyapısını ve tüm bounded context'lerin ortak kullanacağı base sayaç
  metrik arayüzünü (counter/histogram/gauge soyut contract) kurar.
owner:           foundation (shared infra)
current_vs_future: CURRENT mandatory for MVP; no S-FND-03 scope creep.
```

**Current vs Future:**
- **CURRENT (S-FND-02 delivers):** Log record schema, correlation propagation helper, base metrics abstract contract (interface), in-memory/dev sinks, deterministic formatter, fail-safe (error never breaks the pipeline).
- **FUTURE (outside S-FND-02):** Prometheus exporter, Grafana dashboards, alert routing, APM trace vendor, tracing SDK, OpenTelemetry collector, log aggregation service, log rotation policy, audit log tamper protection, remote write auth. Delivered by E-API / S-FND-03+ / future deployment stories.

---

## 1. Intent (What)

- Bütün bounded context'lerin (ingest/contracts/processing/decisioning/simulation/governance/platform/API) **aynı log kayıt şemasını** kullanmasını garanti altına al.
- Her domain event/decision/paper order/risk kararının geri izlenebilir olabilmesi için AD-3 canonical envelope içindeki `correlation_id` ve `causation_id` ile log kayıtlarını otomatik ilişkilendir.
- Gelecekteki metrik toplama altyapıları (Prometheus vb.) ile **tek seferde birleştirilebilen** bir soyut metrik contract (interface) sağla; gerçek export S-FND-02'de değil downstream hikâyelerde/e-API'de yapılır.
- Hatalı log / metrik çağrısı asla domain pipeline'ını kırmaz (fail-safe + fail-closed safety).
- Bütün gözlemlenebilirlik çıktıları (log/metrik) deterministik ve yeniden üretilebilir olsun; reconstruction kolaylığı (NFR-007) için hashable/deterministic formata sahip olsun.

## 2. Measurable Success (Sayılabilir)

Success sayımsal olarak şu şekildedir:

1. **M1 — Schema compliance:** SPEC tanımlı her zorunlu `CanonicalLogLine` alanı (11 tane) yazılan her log satırında mevcuttur (eksik alan oranı = 0%).
2. **M2 — Correlation integrity:** Verilen bir `correlation_id` için aynı zincir boyunca basılan bütün log satırları aynı `correlation_id` değerine sahiptir; `causation_id` önceki event id ile tutarlıdır (zincir kırılması = 0).
3. **M3 — Fail-safe (no-op on error):** Logger/metrics içinde herhangi bir exception oluştuğunda (ör. serialize error, invalid value) call site exception yükselmez; dropped_count sayaç 1 artar (call site exception oranı = 0).
4. **M4 — Deterministic format:** Aynı girdi (log line alanları, level, ts) için aynı hash değeri döner; 10× tekrar `len(set(hashes))=1`.
5. **M5 — No secrets leak (S-FND-01 F2 compatibility):** Log satırları hiçbir durumda `api_key/secret/token/password/credential` değerlerini düz metin içermez; value hash or masked only (S-FND-01 F2 uyumluluğu = 100%).
6. **M6 — Metrics contract parity:** Counter / Histogram / Gauge soyut interface'leri 3 bounded context (platform + API + örnek simulation) tarafından implemente edilir; her birinin `labels={}` ve `correlation_id` propagation desteği vardır (missing method oranı = 0).
7. **M7 — Sinks coverage:** 3 built-in sink aktif: null_sink (test), stdout_json_sink (dev), inmem_list_sink (test assertions). 100% cover.

## 3. IN / OUT Boundary (Scope)

### IN — kesin olarak dahil edilir:
- `CanonicalLogLine` schema (zorunlu + opsiyonel alanlar)
- `CorrelationContext` helper: yeni zincir başlat, parent zinciri devral, alt işlemler için child span id üret
- `BaseMetricsFacade` soyut interface: Counter (inc/add), Histogram (observe), Gauge (set/inc/dec)
- 3 built-in log sink: NullLogSink / StdoutJsonSink / InMemoryCaptureSink (test için)
- 3 built-in metric sink: NullMetricsSink / InMemoryCaptureMetricsSink / StdoutPrintMetricsSink (dev)
- Structured logger root factory: `get_logger(module_name, context_provider)` — env göre sink seçimi
- Redaction / masking utility: hassas alan (value) için maskelenmiş çıktı + SHA-256 referans (eşik olmayan, S-FND-01 F2 uyumluluğu)
- Deterministic JSON serializer: key sıralı, float/bool/int/str/None + datetime ISO-8601 UTC zorunlu format
- Log level semantiği: DEBUG/INFO/WARN/ERROR/FATAL + numeric değerler (AD-19 fail-close ERROR)

### OUT — kesin olarak dahil EDİLMEZ (future scope / diğer hikâyeler):
- Prometheus / OpenMetrics HTTP exporter (E-API scope)
- Grafana dashboard, alert manager, PrometheusRule CRDs (E-API deployment)
- OpenTelemetry / Zipkin / Jaeger vendor entegrasyonu (future)
- Log aggregation backend (Loki/ELK) deployment (CI/CD future)
- Log retention, rotation policy, archival (future deployment story)
- Audit-log immutability / append-only storage / hash chain (future security story)
- Trace sampling ratios, SLO tanımları, alert threshold (ADN-03'e bağlı future)
- APM vendor, remote write auth, TLS config (future)
- S-FND-03 forbidden test infrastructure (`F1..F4` already delivered by S-FND-01)
- E-API HTTP metrics middleware (`/metrics` route: E-API kendi property si)
- PyYAML/yaml import (OD-FND-04 OPEN; S-FND-02 defaults to JSON stdlib only)

## 4. Upstream Dependencies (Gerekenler)

1. **S-FND-01 frozen EnvConfig**:
   - `env` (dev/test/stg/paper-prod) → default log level + default sink selection
   - `defaults.adn09_kill_switch` → kill-switch eventi ERROR/FATAL olarak loglanması
   - 4 env INI configuration file: section `[observability]` yeni izin verilen alanlar (default values belirlenecek, OD altı)
   - `F2 no-credentials` guard: log/metric output PII/key masking zorunlu
2. **AD-3 Canonical Event Envelope (CONTRACTS.md)**:
   - `event_id`, `correlation_id`, `causation_id`, `schema_version`, `occurred_at`, `source`, `run_mode`, `quality_state`, `symbol` alanları doğrudan log satırına taşınabilir
3. **PRD NFR references (kaynak bağlantısı):**
   - NFR-002 Reliability: "disconnect / rate-limit / malformed / gap" — DETECTABLE and LOGGED (AD-19)
   - NFR-004 Observability: Structured logs + health metrics + decision traces + risk events + model drift signals
   - NFR-006 Data integrity: immutable raw event provenance + timestamp semantics → log replay reconstruction
   - NFR-007 Reproducibility: log/records allow reconstruction from versioned inputs
   - NFR-008 Security (v1): "v1 shall operate without secrets or trading credentials; future privileged paths must default deny and remain separately gated" → FC-10 masking rule, HR-3, SEC-1 compliance (S-FND-02 NO secrets, default deny behavior)
   - FR-056 (audit logged): "Risk policy values / overrides / exceptions / rejection decisions versioned and audit logged"
   - FR-041 (audit trail): approver/rationale/evidence/timestamp/prior-state
4. **ARCH SPINE AD references:**
   - AD-17 End-to-End Observability by Correlation ID (MANDATORY — binds observability/api/decisioning/simulation)
   - AD-3 Envelope
   - AD-19 Failure Defaults to Safe Stop (WARN/ERROR/FATAL log semantics)
   - AD-18 Environment Separation (sink selection by env)

## 5. Downstream Consumers (Tüketenler)

S-FND-02 çıktısını kullanan tüketiciler (KESİNLİKLE; S-FND-02 only provides hooks, does NOT implement any downstream logic):

| Bounded context | Ne tüketir? | Neden? |
|---|---|---|
| Ingest / adapters | Logger + CorrelationContext + NFR-002 error/rategap metrics | Adapter disconnect / malformed msg / data gap LOG |
| Event bus / contracts | envelope correlation fields → CorrelationContext propagation helper | AD-3/AD-17 zincir integrity |
| Processing / feature engine | Counter("features_computed_total"), Histogram("feature_latency_ms"), Logger on errors | NFR-004, NFR-001 latency measurement |
| Strategy / regime | Logger + Counter("strategy_signals_total", labels={strategy, regime, action}) | FR-050 rejection terminates pipeline + LOG reason |
| AI / learning | Logger + Counter("model_inferences_total") + Histogram("inference_latency") | Model drift signals (NFR-004) |
| Risk Engine | **FR-056 AUDIT LOG** rejection reason; Counter("risk_rejections_total", labels={reason, scope}); FATAL on kill-switch (FR-054). **AD-19 hook: Risk Engine, FC-09 FATAL log'u tüketerek kendi içinde "action 2 (engelle)" + "action 3 (scope daralt)" + "action 4 (state işaretle)" uygular (S-FND-02 IMPLEMENT ETMEZ)** | AD-19 fail-close 4 action (Risk owns 3/4; S-FND-02 only FATAL hook) + NFR-004 |
| Paper Trading / Execution Simulator | Histogram("paper_fill_latency_ms") + Counter("paper_orders_total") + audit order decision log. **AD-19 hook: Exec Sim, FC-09 FATAL log'u tüketerek yeni paper emirleri ENGELLEME (action 2)'yi kendi içinde uygular (S-FND-02 IMPLEMENT ETMEZ)** | FR-047/FR-048 + FR-149 pipeline LOG + AD-19 block exec (action 2) |
| Model Registry / lifecycle | FR-041 audit log promotion+rollback; Counter("lifecycle_transitions_total", labels={from_state, to_state, approver}) | AD-23 registry-only mutations; evidence ref correlation |
| Champion / Challenger | Comparison logs; Counter("champion_challenger_evaluations_total") | Promotion gate evidence |
| E-API MVP | E-API middleware correlation context propagation; metrics facade; `/logs` query route can consume InMemoryCaptureSink for testing; **metrics Prometheus exporter = E-API (future)**. **AD-19 hook: E-API, FC-09 FATAL log'u tüketerek operator-facing "action 4 state işaretle" endpointini kendi içinde uygular (S-FND-02 IMPLEMENT ETMEZ)** | AD-17 correlation across API; NFR-004 + AD-19 state mark (action4) |
| **Alerting (ARCH Appendix BC: AD-19 binds alerting)** | Counter("alert_events_total", labels={severity, source}) + FATAL log'u correlation_id ile tüketir; kendi alert routing/output uygular (S-FND-02 sadece counter interface + correlation hook sağlar; NG-2 alert rule OUT S-FND-02 scope) | AD-5/AD-11/AD-17/AD-19 alert üret (action 4); S-FND-02 sadece 1/4 LOG hook, Alerting BC kendi 4. action alert üretir (NG-2 preserved) |
| S-MDL (01..05) tests | InMemoryCaptureSink assertions; registry audit log count assertions | S-MDL-01/02/03/04/05 evidence chain |
| All failure / security audits | Redaction checker; masked count assertions; M5=F2 compliance | S-FND-01 F1..F4 + scanner tests |

## 6. Contracts / Data Types (Schema)

### 6.1 CanonicalLogLine (JSON, deterministic, key-sorted)

Zorunlu alanlar (11 tane — M1 schema compliance 100%):
| Alan | Tür | Açıklama | Kaynak kuralı |
|---|---|---|---|
| `log_id` | str (hex 32) | Unique kayıt id, deterministik seed alanların SHA-256 ilk 128 bit | `sha256(ts+level+module+msg+correlation_id+causation_id).hexdigest()[:32]` |
| `ts_utc` | str ISO-8601 | UTC zaman damgası; saat dilimi Z; saniye hassasiyeti | Deterministic test: freeze ts via provider |
| `level` | str | DEBUG / INFO / WARN / ERROR / FATAL. Büyük harf zorunlu. | FATAL = AD-19 kill-switch / pipeline durdur |
| `module` | str | "app.platform.observability.logger" gibi full modül yolu | Logger factory'den |
| `correlation_id` | str (uuid-like veya hex 32) | AD-3/AD-17; aynı zincir içinde aynı değer | Varsayılan: "NO_CORRELATION" (yoksa); NEVER null/empty string |
| `causation_id` | str | Bir önceki event id; "ROOT" ise zincir başlangıcı (ilk olay) | Zincir başı => ROOT |
| `env` | str | dev/test/stg/paper-prod (S-FND-01 env) | EnvConfig.env |
| `run_mode` | str | replay / mock / readonly-live / live (AD-4 Live/Replay Parity) | Envelope veya config'ten |
| `msg` | str | İnsan okunabilir kısa mesaj; max 4096 unicode codepoint | Truncate at 4096. |
| `labels` | dict[str, str] | Anahtar-değer ek bağlam; keys lowercase snake_case; values str | Deterministic: key sorted; maskeli değerler |
| `schema_version` | str | "sfnd02/v1" — bu hikâye contract revizyonu | sabit |

Opsiyonel alanlar (istenirse eklenebilir, downstream kırıcı değil):
- `trace_id`, `span_id`, `parent_span_id` (future OTel — optional, NOT mandatory S-FND-02)
- `source` (event envelope source)
- `symbol`, `run_id`, `model_id`, `strategy_id`, `evidence_ref` (bounded context specific)
- `quality_state` (from envelope: valid/invalid/gap/stale)

### 6.2 BaseMetricsFacade — Interface (what)

```python
class BaseMetricsFacade:  # ABC veya benzer soyut contract; S-FND-02 defines interface only
    def counter(self, name: str, labels: dict[str,str]|None=None) -> CounterIntf: ...
    def histogram(self, name: str, labels: dict[str,str]|None=None, buckets: tuple[float,...]|None=None) -> HistogramIntf: ...
    def gauge(self, name: str, labels: dict[str,str]|None=None) -> GaugeIntf: ...
    def set_correlation_provider(self, fn: Callable[[], tuple[str,str]]) -> None: ...

class CounterIntf:
    def inc(self, n: float=1) -> None: ...
    def add(self, n: float) -> None: ...  # n>=0. Fail-safe: negatif değer atılır ve counter artmaz + logged.

class HistogramIntf:
    def observe(self, value: float) -> None: ...   # non-finite NaN/Inf atılır; safe

class GaugeIntf:
    def set(self, value: float) -> None: ...
    def inc(self, n: float=1) -> None: ...
    def dec(self, n: float=1) -> None: ...
```

Kurallar:
- `name`: lowercase snake_case, max 128 chars, prefix `crypto_ai_` (kendisi S-FND-02 contract sabiti)
- `labels`: keys lowercase snake_case, str değerler. 20 label den fazla izin verilmez; excess log drop + dropped_counter artar
- `buckets`: histogram default = SPEC sabit `(.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10, float('inf'))` (yoksa). Sabit ve aynı sıra — determinizm için.
- Method çağrıları CALLER'da exception yükseltmez. Her zaman fail-safe (M3). Hata → "metrics_dropped_total" sayaç (internal) +1.

### 6.3 CorrelationContext interface (what)

```python
class CorrelationContext:
    correlation_id: str
    causation_id: str
    # helpers
    @staticmethod
    def new_root() -> "CorrelationContext":  # causation_id="ROOT", yeni correlation_id üret
    @staticmethod
    def from_envelope(env: Envelope) -> "CorrelationContext":  # AD-3 → correlation/causation
    def child(self, new_causation: str) -> "CorrelationContext":  # aynı correlation_id, yeni causation_id
    def as_labels(self) -> dict[str,str]:  # labels={correlation_id, causation_id}
```

### 6.4 Deterministic Serialization Rule (what)
- JSON output: keys SORTED ascending (unicode code point), separators `(",",":")`, `ensure_ascii=False`, booleans `true/false`, ints no leading zeros, floats **str() değil** (basit floatlar; NaN/Inf → dropped, yerine `{"_dropped":"NaN"}` + dropped counter).
- `labels` dict: içi de aynı şekilde sıralı.
- datetime: ISO8601 `YYYY-MM-DDTHH:MM:SSZ` zorunlu UTC.

## 7. Deterministic Behavior (DET)

| Property | How | Measurement 10× |
|---|---|---|
| D1 — `CanonicalLogLine.log_id` | SHA-256 over same alanlar → ilk 32 hex | 10 kez aynı girdi → tek hash |
| D2 — JSON serialization | key sorted, fixed separators, ts injected from provider | 10 kez serialize → byte eşleşme |
| D3 — Histogram default buckets order | tuple constant (never reordered) | set(tuple) len(set)=1 10× |
| D4 — CorrelationContext.new_root: correlation id üretme deterministic? No (random). Ama **test provider enjekte edilebilir** → Deterministic UUID provider test için belirle. | Test: provider `lambda: "COR-00000000000000000000000000000001"` → her çağrı aynı. | 10× set len=1 |
| D5 — Log level numeric mapping | DEBUG=10 INFO=20 WARN=30 ERROR=40 FATAL=50 (sabit) | 10× map denetle len(set)=1 |
| D6 — Metrics name + label validation | Name/length regex ve limitler sabit; geçersiz isim + drop_counter. İsim aynı → aynı counter (aynı labels → identity preserved). | 10× counter identity len(set)=1 |

## 8. Fail-Closed Behavior (FC)

Fail-closed = domain pipeline güvenli şekilde durur; logger hata oluşursa exception yükseltilmez, ama **AD-19** scope'u dışında işlem yapılmaz.

- **FC-01 (Logger init failure):** Logger root factory, sink config veya import failure → "fallback NullLogSink + Console.warn(stderr)" kullanılır. Hiçbir modül exception almaz; fallback kullanıldı flag'i `logger_init_fallback` = True → dropped_counter artar.
- **FC-02 (Invalid log level string):** Geçersiz level → seviye ERROR yükseltilir + `_invalid_level=1` label eklenir; mesaj korunur, düşürülmez (zincir kırılmaz).
- **FC-03 (Oversize msg > 4096 chars):** truncate len(4093) + "..." ekle; `_msg_truncated=1` label; call site exception yok.
- **FC-04 (Serialization non-serializable value in labels):** Değer drop edilir; yerine `{"__dropped__":"type:<typename>"}` + dropped_counter artar; log satır yazılır; call site exception YOK.
- **FC-05 (Masking failure):** Hassas alan (api_key/token…) maskelenemedi → alan tamamen drop edilir; log satırı yine de yazılır (M5 compliance önceliği: veriyi düşürmektense maskeleyemediğini düşürmek daha güvenli).
- **FC-06 (Metrics invalid name / labels count > 20):** counter creation skip; metrik adı + hash label olarak internal dropped counter'a aktarılır; call site EXCEPTION YOK.
- **FC-07 (NaN / Inf histogram observe):** Değer düşürülür; dropped counter artar; no call site err.
- **FC-08 (Correlation id empty):** Default "NO_CORRELATION" (never None); causation id empty → "UNKNOWN".
- **FC-09 (Kill-switch signal log level / AD-19 fail-safe 4 actions hook-only):** FR-054 kill-switch eventi veya AD-19 failure (disconnect/stale/missing/malformed/DB-unavail/model-unavail/strategy-fail/risk-fail/sim-fail/API-fail) → seviye FATAL zorunlu (log level yükseltilemez, düşürülemez). **Önemli: S-FND-02 (obs-hooks) sadece 1/4 aksiyonu (1. LOG) sağlar; kalan 3 aksiyon (2. yeni paper execution ENGELLE, 3. scope DARALT, 4. state İŞARETLE + alert ÜRET) downstream bounded context (Risk Engine, Paper Trading Execution Simulator, Alerting, E-API) tarafından kendi içinde uygulanır. S-FND-02 downstream action'ları İMPLEMENT ETMEZ, SADECE FATAL log + dropped_counter + "ad19_fail_type" label hook'u sağlar.** (ARCH SPINE AD-19 rule L186 → 4 eylem, 1/4 S-FND-02, 3/4 downstream hook consumer.)
- **FC-10 (Secrets redaction default mask):** ANY value labels değeri `api_key/secret/password/token/credential/private_key` key içeriyor veya value starts with pattern `xox/sk/ak/eyJhbGciO` (JWT) → otomatik masked. **MASK RULE:** `SHA-256(value)[:12]` + prefix "REDACTED:" (ör. `"REDACTED:9f86d081884c"`).

## 9. Security / Safety (SEC)

*(SEC başlığı normatif bağlantı: **PRD NFR-008 Security v1** → v1 çalışma sırasında secrets veya trading credentials olmadan çalışır; gelecekteki ayrıcalıklı yollar varsayılan olarak reddedilir ve ayrı geçit altında tutulur. S-FND-02 bu NFR'nin obs-hook katmanındaki karşılığını sağlar.)*

- **S1 — Secrets leak prevention (M5 / F2 compliance / NFR-008):** Bütün label value'lar "masking utility" den geçer; anahtar isimleri yukarıda list, ayrıca regex `r'(?i)(api[_-]?key|secret|password|token|credential|private[_-]?key)'` — match ise REDACTED hash; no plain value. Ayrıca full line "static no_api_key_strings" (S-FND-01 F2 test) taraması yine geçmeli — çünkü gerçek değerler masked olarak saklanıyor. NFR-008'in "operate without secrets" zorunluluğudur.
- **S2 — No unsafe dynamic execution:** Logger ve metrics soyut interfaceler eval/exec/yaml_loader kullanmaz; stdlib JSON.
- **S3 — Fail-safe never raises call site (M3):** Özellikle risk/kill-switch pathlerinde logger exceptionı asla emülasyonu durdurmaz; her zaman düşür + counter.
- **S4 — Sink access scope:** Log sinks S-FND-02 dışında değiştirilemez (immutable registry). Yeni sink ekleme tek yerden (root factory).
- **S5 — Audit trail integrity (FR-041 / FR-056):** "AUDIT" log type — msg prefix `[AUDIT]` ile belirtilir; dropped counter ayrı tutulur; audit kayıtlarını masking hariç düşürme izni YOK (FC-01..FC-03 uygulanabilir ama kayıt düşürülmez: düşürme yerine FC-02/03/04 label + satır kaydedilir).
- **S6 — Env separation (AD-18):** paper-prod ortamında default StdoutJsonSink; dev ortamında InMemoryCaptureSink debuggable ama kaçağı önlemek için stdout_json de default olabilir.
- **S7 — Correlation id tahmin edilemez canlı ortamlar için:** Production/paper use `os.urandom(16).hex()`; testlerde deterministic provider; risk of correlation id prediction: future scope (audit log append only — S-FND-02 dışı).

## 10. Audit / Evidence (AUD)

S-FND-02 sonrası bağımsız audit tarafından şu kanıtlar toplanabilir:

1. **Schema compliance (M1):** Rastgele 100 satır log → 11 zorunlu alan her biri için 0 eksik.
2. **Correlation chain integrity (M2):** InMemoryCaptureSink üzerinden 5 zincir test; her zincir aynı correlation_id; child causation parent event/cause doğru.
3. **Fail-safe (M3):** Invalid value / oversizes msg / invalid level → call site exception 0; dropped counters >0.
4. **Deterministic serialization (M4):** 10 kez serialize, set size 1; log_id aynı.
5. **Masking / F2 compatibility (M5):** Hassas value injected test → REDACTED prefix; S-FND-01 test_f2 çalıştırıldığında 0 new F2 hit.
6. **Metrics interface contract (M6):** Counter/Histogram/Gauge 3 test class (platform + simulation + API test fixture) tarafından implement edilmiş; methodlar çağrıldığında call eksikliği 0.
7. **Sinks coverage (M7):** 3 built-in sink testlerden en az 1 kez assert edilmiş.
8. **Audit log type integrity (S5):** AUDIT tagged mesajlar hiçbir koşulda tamamen düşmez; oversizing truncate, yanlış level → upgrade + satır kaydedilir.

## 11. Non-Goals (NG)

S-FND-02 kesin olarak YAPMAZ (what not):

- **NG-1:** Prometheus exporter veya /metrics HTTP endpoint kurmaz (E-API property — future).
- **NG-2:** Alert kuralları, Grafana dashboard, SLO tanımlamaz (ADN-03 + future deploy).
- **NG-3:** Remote write, log gönderme client ı, Kafka/Loki/ELK entegrasyonu yapmaz.
- **NG-4:** APM / trace sampling politikası veya OTel SDK import etmez.
- **NG-5:** Storage layer veya audit-log immutability (hash chain, append-only file) implement etmez (future security).
- **NG-6:** PyYAML veya herhangi 3rd-party log framework (loguru structlog) import etmez — stdlib JSON + ABC only. OD-FND-04 OPEN korur; hiçbir config YAML dosyası oluşturulmaz.
- **NG-7:** S-FND-03 F1/F2/F3/F4 boundary testlerini yeniden tanımlama veya ekleme — S-FND-01 teslim etti; B1 zaten giderildi.
- **NG-8:** Log retention / rotation / archival politikası.
- **NG-9:** Real-trading credential/vault integration (S-FND-01 + future).
- **NG-10:** Dashboard UI veya operatör görünümü (NFR-004 future dashboard story).
- **NG-11:** Herhangi bir bounded context için DOMAIN logic (ör: risk policy, promotion gate vb.) tanımlama.

## 12. Hard-Red (HR)

S-FND-02, hard-red kurallarını:

- **HR-1 (0 production code outside approved scope?):** S-FND-02 *yeni kod* üretir ama bu kod **observability hooks / contracts** dir; app/ klasöründe yeni modüller oluşabilir, ama:
  - *Existing* app/ klasör kodlarına dokunma kuralı (S-FND-01 / E-API / S-MDL existing modification YOK). Yeni dosyalar; existing dosyalara dokunma kuralı (existing file modification = explicit exception ise ayrı listele — *default: NO existing modification*; tr boundary.
- **HR-2 (No network / live execution):** Logger/metrics hooks tarafından outbound HTTP/socket çağrısı yapılmaz; sadece null/stdout/in-memory sink.
- **HR-3 (No credentials / NFR-008 default deny):** Masking utility REDACTED rule + no direct value access; F2 compliance aynen korunur. Kaynak: **PRD NFR-008 Security** = "v1 operate without secrets; future privileged default deny + separately gated" (S-FND-02 hook katmanı, hiçbir credential üretmez veya saklamaz; sadece maskeler).
- **HR-4 (No registry mutation):** Logger/metrics interfaceleri ModelRegistry state'ine doğrudan yazmaz; counter/gauge'ler bir facade üzerinden snapshot — future exporter.
- **HR-5 (No 3rd-party runtime dependency):** stdlib-only.
- **HR-6 (No unsafe exec):** JSON stdlib; eval/exec/yasak.

## 13. Acceptance Criteria (AC) — Measurable 1–24

Zorunlu 24 AC (sayısal, ölçülebilir):

**LOG SCHEMA & FORMATTING (AC-01..AC-08)**
- AC-01. Zorunlu 11 `CanonicalLogLine` alanı (bölüm 6.1 listesi) her satırda mevcuttur: eksik alan oranı 0/100 satır.
- AC-02. `schema_version` alanı = "sfnd02/v1" olarak yazılır; her satırda.
- AC-03. JSON serialization key-sorted ve sabit ayırıcılarla yapılır; aynı girdi 10 kez serialize → 10/10 byte olarak identik.
- AC-04. `log_id` aynı alanlar için değişmez; 10× üretilen log_id set len=1.
- AC-05. `env` alanı S-FND-01 EnvConfig.env değeridir (4 geçerli değerden biri).
- AC-06. `run_mode` alanı AD-4 dört değerinden biri veya NO_MODE (tanımsız ise "NO_MODE").
- AC-07. msg alanı 4096 karakter sınırına uçar; aşanlar truncate edilir; FC-03 label eklenir (satır düşmez).
- AC-08. Oversize labels 20 key > olunca dropped counter +1 artar; satır yazılır (FC-06).

**CORRELATION INTEGRITY (AC-09..AC-12)**
- AC-09. Root zincir (CorrelationContext.new_root()) → causation_id = "ROOT".
- AC-10. from_envelope constructor kullandığında correlation_id & causation_id AD-3 envelope'den birebir alınır.
- AC-11. child() çağrısı: correlation_id DEĞİŞMEZ; causation_id = new_causation parametresi.
- AC-12. as_labels() her zaman 2 anahtar ("correlation_id", "causation_id") ve str değer döner.

**FAIL-SAFE (AC-13..AC-18)**
- AC-13. Logger JSON serialization hatasında: call site exception = 0.
- AC-14. NaN/Inf histogram observe: call site exception 0; dropped counter artar.
- AC-15. Invalid level: seviye ERROR + invalid_level label.
- AC-16. FC-01 init failure: NullLogSink + stderr warn; hiçbir modül exception almaz.
- AC-17. Oversize msg > 4096: satır düşmez; truncate edilir.
- AC-18. "AUDIT" tagged bir kayıt hiçbir durumda tamamen düşmez; hatalar truncate/label ile çözülür, satır mutlaka yazılır.

**MASKING & F2 COMPATIBILITY (AC-19..AC-20)**
- AC-19. Label anahtarı "api_key" veya value "sk-..." veya value JWT → output "REDACTED:<sha256[:12]>".
- AC-20. S-FND-01 F2 testleri (test_f2) S-FND-02 kurulumundan sonra 0 NEW false positive (B1 hala RESOLVED).

**METRICS CONTRACT (AC-21..AC-22)**
- AC-21. Counter/Histogram/Gauge interface method eksikliği = 0; her biri labels + correlation provider enjekte desteği var.
- AC-22. Histogram default buckets SPEC sabiti ile aynı sıra ve 12 bucket sayısı (inf dahil).

**SINKS (AC-23..AC-24)**
- AC-23. 3 built-in log sink (Null/StdoutJson/InMemoryCapture) ve 3 built-in metric sink (Null/InMemory/StdoutPrint) import edilebilir ve çalışır durumdadır.
- AC-24. InMemoryCaptureSink.test: 5 zincir log capture + her satırda 11 zorunlu alan doğrulaması PASS (AC-01 ile entegre).

## 14. Definition of Done (DoD)

S-FND-02 DONE sayılması için gerekli:
- DoD-01: Schema (6.1), Interface (6.2), Context (6.3), Serial (6.4) implement edildi.
- DoD-02: 24 AC (bölüm 13) — 24/24 PASS; 0 FAIL.
- DoD-03: S-FND-01 regression 60 PASS / 1 SKIP / 0 FAIL preserved; 0 new F2 false pos.
- DoD-04: E-API baseline 56 test PASS; S-MDL01-05 (1100 PASS 26 SKIP 1 XFAIL 1 XPASS) regression preserved; 0 existing modification source diff.
- DoD-05: Determinism 10×: D1–D6 her biri için `len(set)=1` 6/6 PASS.
- DoD-06: Fail-safe 10 scenario FC-01..FC-10 10/10 PASS.
- DoD-07: Masking 8 positive case + 2 negative case (random value maskenmez) 10/10 PASS.
- DoD-08: Existing file modification = 0 (veya explicit exception list 1 item ≤ — default 0).
- DoD-09: 3rd-party dependency import sayısı 0; stdlib-only.
- DoD-10: Audit 8 evidence (bölüm 10) hazır; 8/8 PASS.

## 15. Test Plan (TP) — 3 seviye

### TP-1: Unit / contract tests — Yeni dosya `tests/foundation/test_sfnd02_contracts.py`
- `test_log_schema_compliance`: 100 satır, 11 alan eksiksiz.
- `test_serialization_deterministic_10x`: M4.
- `test_log_id_deterministic`: D1.
- `test_level_invalid_upgrades_AC15`: FC-02.
- `test_msg_oversize_truncate_AC07`: FC-03 / AC-07.
- `test_correlation_root_child_from_envelope_AC09_AC10_AC11_AC12`.
- `test_masking_api_key_jwt_prefix_AC19`.
- `test_audit_never_drops_AC18`.
- `test_init_failure_nullsink_AC16`: FC-01.
- `test_hist_nan_drops_no_exception_AC14`.
- `test_metrics_interface_compliance_AC21_AC22` (ABC subclass check).
- `test_builtin_sinks_importable_AC23`.
- `test_inmemory_capture_asserts_AC24`.

### TP-2: F2 compatibility / regression tests
- Run `pytest tests/failure/test_f2_no_credentials.py -v` (S-FND-01) → 0 new F2 hit (AC-20).
- Run existing credential scanners (test_no_credentials, test_bus_no_credentials, test_registry_no_credentials) — S-FND-02 dahilinde 0 new false pos.

### TP-3: Integration / determinism testleri
- `test_correlation_chain_integrity_M2`: 5 zincir via InMemoryCaptureSink.
- `test_fail_safe_call_site_exception_zero_M3`: 10 scenario try-except.
- `test_metrics_bucket_defaults_D3`: 10 kez bucket tuple set len=1.
- `test_env_sink_selection_by_sfnd01_env`: 4 env → hangi sink default'u (deterministic mapping).

### TP-4: Hardred boundary
- `test_fnd02_stdlib_only_pyproject_deps_empty`: S-FND-01 gibi F4 stdlib-only marker; marker PASS or F4 fail.

## 16. Expected File Changes (Scope: exact paths + purpose)

**KURAL:** Existing file modification MÜMKÜN OLDUĞUNCA AZALTILIR. Default 0 existing modification. Aşağıdaki listeden sapmalar EXPLICIT exception olarak C1/C2 style ayrılır.

### NEW files (EXPECTED — verified inventory: 13 required + 1 conditional; NOT listed = not new)

**Baseline-owned (E-API `eapi_commit` `80933f8a7feecfbcb63dc3da72b10f7f459baade`) — S-FND-02 tarafından YENİ SAYILMAZ (A1):**
- `app/platform/observability/__init__.py` — E-API sahipliği (S-API-04); baseline blob `93c5996…`; S-FND-02 commit'i `d02f58b` dokunmadı.
- `app/platform/observability/metrics.py` — E-API sahipliği (Prometheus facade); baseline blob `a3b0bfc…`; S-FND-02 commit'i `d02f58b` dokunmadı.

**NEW — production (`app/platform/observability`):**
1. ~~`app/platform/observability/__init__.py`~~ → **BASELINE-OWNED; yeni dosya DEĞİL (A1).** Re-export amacı gerçekleşmemiştir (dosya `d02f58b`'de değişmedi); modül sınırı doğrudan importlarla sağlanır.
2. `app/platform/observability/schema.py` → CanonicalLogLine dataclass, mask regex, FC-10 constants
3. `app/platform/observability/correlation.py` → CorrelationContext helper
4. `app/platform/observability/serialization.py` → Deterministic JSON serializer + log_id producer (D1/D2)
5. `app/platform/observability/metrics_facade.py` → BaseMetricsFacade ABC + CounterIntf/HistIntf/GaugeIntf + default buckets (**A3 Durum A:** gerçek yol; §6.2 sözleşmesi. Önceki `metrics.py` yolu E-API baseline'ına ait — bkz. yukarıdaki baseline-owned blok.)
6. `app/platform/observability/sinks_log.py` → NullLogSink / StdoutJsonSink / InMemoryCaptureSink (3)
7. `app/platform/observability/sinks_metrics.py` → NullMetricsSink / InMemoryCaptureMetricsSink / StdoutPrintMetricsSink (3)
8. `app/platform/observability/factory.py` → root get_logger() + MetricsFacade default bootstrap
9. `app/platform/observability/redaction.py` → masking helper + sha256 prefix

**NEW — test (`tests/foundation`):**
10. `tests/foundation/__init__.py` → test package marker (N-10)
11. `tests/foundation/test_sfnd02_contracts.py` → TP-1 unit/contract testleri (new)
12. `tests/foundation/test_sfnd02_determinism.py` → D1–D6 10x (new)
13. `tests/foundation/test_sfnd02_failsafe.py` → FC-01..FC-10 (new)
14. `tests/foundation/test_sfnd02_masking.py` → masking + F2 regression (new)

**CONDITIONAL (koşul: OD-SFND02-02 option A):**
15. `tests/foundation/conftest.py` → F2/fixtures (d02f58b'de seçilip eklendi) (CONDITIONAL)

**EXISTING config dosyaları — bunlar NEW DEĞİL, koşullu MODIFICATION (EX-01..EX-04):** `configs/config.dev.ini`, `configs/config.test.ini`, `configs/config.stg.ini`, `configs/config.prod.ini` ADD `[observability]` section (yukarıda EXCEPTION list).

**Existing File Modifications — EXPLICIT EXCEPTION LIST (backed by PRD/SOURCE, OPTIONAL if can avoid):**
- EX-01 (mandatory likely): 4 S-FND-01 `.ini` configlerinin içine YENİ `[observability]` section eklenmesi. Neden: AD-18 env separation'a göre env'e göre sink/level mapping config gerekiyor. PRD NFR-004 requires config-based defaults; SPEC'te başka yol yok. **ALTERNATIVE possible:** If implementers decide that SFND02 defaults are hardcoded in factory (dev: INFO+stdout; test: DEBUG+InMemory; stg: WARN+stdout; paper-prod: ERROR only) — THEN INI modification = 0 and EX-01..04 are DROPPED, 0 existing modification. Open Decision OD-SFND02-01 item (aşağı).

### EXISTING FILES TOUCHED — 0 DEFAULT (existing file modification yok), AYRICA:
- `tests/conftest.py` → S-FND-02 fixtures eklemek için EOF append (C2 benzeri). **CONDITIONAL — sadece test infrastructure ihtiyacı ise 1 explicit more EX-05:** Eğer TP-1 new test klasöründe new conftest kullanılırsa tests/foundation/conftest.py yeni dosya, o zaman tests/conftest.py modify gerekmez. Açık karar OD-SFND02-02.

**TOTAL (verified inventory — A2):**
- Required new production files: **8** (`schema.py`, `correlation.py`, `serialization.py`, `metrics_facade.py`, `sinks_log.py`, `sinks_metrics.py`, `factory.py`, `redaction.py`)
- Required new test files: **5** (`tests/foundation/__init__.py` + 4 `test_sfnd02_*.py`)
- Conditional files: **1** (`tests/foundation/conftest.py`, koşul OD-SFND02-02 option A)
- Required total: **13**  ·  Maximum total if conditions apply: **14**
- Existing file modifications: **0** (best case; EX-01..EX-05 dropped)
- Baseline-owned (NOT new): `app/platform/observability/__init__.py`, `app/platform/observability/metrics.py` (E-API `80933f8`)

## 17. Open Decisions (OD-SFND02-*)

*Her decision specification tarafından ÇÖZÜLMEZ; karar sayısı ve etkisi belirtilir. Future implementation çözebilir.*

1. **OD-SFND02-01: Observability section INI var mı, yoksa default hardcoded?**
   - Impacts: 4 existing config ini (dev/test/stg/paper-prod.ini) modification (4 items) or 0 modification
   - Owner: foundation implementer
   - Şiddet: MINOR — tradeoff between configurability vs existing modification count

2. **OD-SFND02-02: Test fixtures NERDE? tests/foundation/conftest.py new vs tests/conftest.py EOF append?**
   - Impacts: 0 new file + 1 existing append OR 1 new file + 0 existing
   - Önerilen: tests/foundation/conftest.py (yeni klasör) + 0 existing modification
   - Risk: fixture discovery. pytest 9.1.1 default: FOUND.

3. **OD-SFND02-03: PyYAML kullanımı — log format config YAML?**
   - Karar: S-FND-02 **KESİNLİKLE JSON stdlib.** YAML yok; OD-FND-04 = PyYAML FUTURE C3 kararını bu hikâye taşımaz. YAML kullanılırsa; explicit exception ayrıca. Bu OD-FND-04 açılımını etkilemez; Open olarak kalır. **S-FND-02'de KESİNLİKLE JSON.**

4. **OD-SFND02-04: Histogram default bucket thresholds EXACT values — Do we need different ones per simulation latency?**
   - Şimdiki SPEC sabiti (12 bucket) yeter. Gelecekte override labels bucket override izni ama default = constant.

5. **OD-SFND02-05: AUDIT tagged kayıtların storage/retention policy (append only / hash chain) — S-FND-02 dışı. Future SEC story.**

## 18. Source Gaps (8 law check — NO fabrication, gaps admitted explicitly)

Aşağıdaki konular SOURCE (PRD/EPICS/ARCH) tarafından S-FND-02 için TANIMLANMAMIŞ, bu hikâye içinde çözülmeyecek (deferred):
1. **Gap-01: Logger output format (human readable vs JSON-only)** — EPICS "Structured logger (JSON)" diyor → JSON-only; gap değil.
2. **Gap-02: Metric name REGEX pattern precisely — SPEC regex yazıldı (`^crypto_ai_[a-z0-9_]{1,124}$`). Kabul.**
3. **Gap-03: Masking rule regex pattern tam listesi — SPEC positive list + regex (?i) ek; exhaustive değil. F2 uyumluluğu korunur; future exception ekle. Kabul.**
4. **Gap-04: Redaction rule'da SHA-256 or BLAKE3 hash?** — SHA-256 stdlib hashlib. 3rd-party yok. Kabul.
5. **Gap-05: Correlation id üretimi canlı paper-prod için CSPRNG vs uuid4?** — 16 bytes urandom.hex; testlerde deterministic provider. UUID4 stdlib uuid var; her ikisi de OK. Karar implementer. Kabul.
6. **Gap-06: Default log level mapping per env — open decision OD-SFND02-01**
7. **Gap-07: Sink selection config formatı — YAML/JSON/INI? INI section OD-SFND02-01**
8. **Gap-08: Label anahtarları list exhaustive mi? No — 20 anahtar sınırı, free-form but masked. YOK, sorun değil.**

## 19. Current vs Future Boundary (Lean Kernel)

Lean kernel = S-FND-02 scope yalnızca hooks/contracts.

| # | Capability | Current (S-FND-02) | Future (S-FND-03+, E-API, deploy) |
|---|---|---|---|
| 1 | Log schema contract | ✅ | Immutable |
| 2 | Correlation helper | ✅ | Immutable + OTel trace_id optional |
| 3 | Metrics interface (ABC) | ✅ | Immutable |
| 4 | 3× Log sinks + 3× Metrics sinks (null/inmem/stdout) | ✅ | +Prometheus +Loki/ELK future |
| 5 | Masking utility (F2 compatible) | ✅ | +custom regex config allowlist future |
| 6 | Deterministic serialization | ✅ | Immutable |
| 7 | Fail-safe 10 rules | ✅ | Immutable |
| 8 | Prometheus exporter | ❌ | E-API MVP extension |
| 9 | Log aggregation dashboard | ❌ | Future deploy story |
| 10 | Alert / SLO thresholds | ❌ | ADN-03 sonrası |
| 11 | Audit storage immutability | ❌ | Future SEC |
| 12 | APM / distributed tracing | ❌ | Future |
| 13 | Retention / rotation | ❌ | Future deploy |
| 14 | PyYAML or third-party logger | ❌ | OD-FND-04 + future optional |

## 20. Architecture Traceability (AD bindings list)

| AD spine kodu | S-FND-02 nasıl bağlanır? |
|---|---|
| **AD-1 (Modular monolith)** | Yeni module: `app/platform/observability/*` tek klasör; bounded contextler import eder, deploy tek artifact. |
| **AD-3 (Canonical envelope)** | CorrelationContext.from_envelope; log satırında correlation/causation. |
| **AD-4 (Live/Replay parity)** | run_mode = replay/mock/readonly-live/live; log satırı alanı. |
| **AD-14 (Governed lifecycle)** | FR-041 AUDIT tagged logs; lifecycle_transitions_total counter (M6 interface sağlar). |
| **AD-17 (End-to-End correlation)** | TÜM story'nin ana amacı; CorrelationContext + Logger + labels. |
| **AD-18 (Env separation)** | 4 env config default level/sink; [observability] section INI (OD-01). |
| **AD-19 (Fail-safe defaults to safe stop)** | Fail-safe FC-01..FC-10; FATAL level kill-switch signal; dropped counter; call site exception YOK. |
| **AD-23 (Registry mutations via commands only)** | Logger/metrics counter INC sadece; registry state direkt mutate etmez (evidence_ref correlation). |
| **AD-24 (Backtest does not own positions table)** | Backtest engine logging; schema/interface kullanır, storage yok. |
| **AD-16 (API: control plane + query plane)** | E-API consumes BaseMetricsFacade, `/logs` (future); logger yapmaz → consumer. |
| **AD-15 (Storage polyglot minimal)** | S-FND-02 hooks only; NO storage; sinks inmem/stdout. |
| **AD-20 (Testability: Architectural Constraint)** | S-FND-02, AD-20 binding'ini 3 şekilde sağlar: (1) CorrelationContext deterministik test provider enjeksiyonu (D4), (2) InMemoryCaptureLogSink + InMemoryCaptureMetricsSink → assertions without stdout/network, (3) frozen ts + fixed envelope fixtures support (tests/foundation/conftest.py new). Böylece contracts/strategy/risk/backtest/paper/deployment BC'leri sıkı bağlı olmadan test edilebilir (AD-20 prevents). |

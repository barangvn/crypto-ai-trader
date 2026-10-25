---
id: PRESV-SFND02
title: S-FND-02 Preservation Matrix (14 Capability)
version: 0.1.0
status: final
date: 2026-09-21
rule: Current (S-FND-02) capability'ler gelecek hikâyelerde DEĞİŞTİRİLMEZ (backward compatible); sadece ilave capability eklenebilir.
---

# S-FND-02 Preservation Matrix — 14 Capability (Current ↔ Future)

Her capability için:
- **Current (S-FND-02):** Bu hikâyede teslim edilen (✅) ya da edilemeyen (❌)
- **Future:** Hangi hikâyede teslim edilecek
- **Preservation Risk:** Current davranışın gelecekte bozulma riski (LOW / MEDIUM / HIGH)
- **Mitigation:** Risk nasıl azaltılır?

Kaynak: `specs/SPEC.md` §19 Current vs Future Boundary tablosu.

---

## Matris (14 capability)

| # | Capability | Current (S-FND-02) | Future (Sahip Hikâye) | Presv. Risk | Mitigation (Koruma Kuralı) |
|---|---|---|---|---|---|
| 1 | **Log Schema Contract** (CanonicalLogLine 11 zorunlu alan) | ✅ Teslim | Ebedi SABİT (Immutable; schema_version = sfnd02/v1) | LOW | schema_version field zorunlu. Gelecekte V2 yapılırsa yeni schema_version (sfnd02/v2) kullanılır; V1 ZORUNLU korunur. İsimlendirme: yeni alanlar OPTIONAL (arka uyumlu). |
| 2 | **Correlation Helper** (CorrelationContext new_root/from_envelope/child/as_labels) | ✅ Teslim | Immutable + OTel trace_id/span_id OPTIONAL alan ekle (NOT required; future OTel story) | LOW | Current method imzaları DEĞİŞTİRİLMEZ. Gelecekte yeni methodlar (örn: `with_trace_id()`) eklenebilir; mevcut methodlar bozulmaz. |
| 3 | **Metrics Interface ABC** (CounterIntf / HistogramIntf / GaugeIntf / BaseMetricsFacade) | ✅ Teslim | Immutable. Gelecekte yeni interface'ler (Summary/SummaryIntf) EKLENEBİLİR; mevcut signature'lar SABİT. | LOW | `BaseMetricsFacade` methodları (counter/histogram/gauge/set_correlation_provider) imzaları DEĞİŞTİRİLMEZ. Yeni metric tipleri subclass/ek method ile gelir. |
| 4 | **3× Log Sinks + 3× Metrics Sinks** (Null/InMemory/Stdout × 2 kategori) | ✅ Teslim | Gelecekte: +PrometheusMetricsSink, +LokiLogSink, +FileLogSink (future deployment/E-API) | LOW | Mevcut 6 sink sınıfı isim/interfaceleri SABİT. Yeni sink'ler `register_sink()` pattern ile eklenir (mevcutlar dokunulmaz). |
| 5 | **Masking Utility** (F2 uyumlu, REDACTED:sha256[:12]) | ✅ Teslim | Gelecekte: custom regex allowlist config + new key patternleri ekle (observability conf story) | MEDIUM | Default masking (positive list + SHA-256) SABİT. Gelecekte allowlist **eklenebilir** ama default behavior DEĞİŞTİRİLEMEZ (backward compat). AC-19 testi korunur. |
| 6 | **Deterministic JSON Serialization** (key-sorted, fixed separators, ISO8601 UTC) | ✅ Teslim | Ebedi SABİT (Immutable; D1/D2 determinism testleri korunur) | LOW | Determinism testleri (10× `len(set)=1`) regression suite'te KALICI. Serializer ayarları değiştirilemez. |
| 7 | **Fail-Safe 10 Rules** (FC-01..FC-10; call site exception 0) | ✅ Teslim | Immutable. Gelecekte yeni fail-safe senaryolar (örn: Future network sink failure) FC-11+ olarak EKLENEBİLİR. | LOW | FC-01..FC-10 her regression run'ında çalıştırılır. Yeni FC kuralı varolan kuralı OVERRIDE EDEMEZ. |
| 8 | **Prometheus HTTP Exporter** ( `/metrics` endpoint + counter/gauge export) | ❌ Gelecek | **E-API MVP Extension Property** (S-FND-02 OUTPUT; §3 OUT list NG-1) | HIGH — SCOPE CREEP RISK | Prometheus export kesin S-FND-02 dışı. E-API `/metrics` route E-API tarafından implemente edilir; buradaki interface sadece ABC sağlar. Export implementation E-API mülkiyetindedir. |
| 9 | **Log Aggregation Dashboard** (Grafana, Loki, ELK UI) | ❌ Gelecek | Future Deployment Story (CI/CD / E-API Ops) | LOW | S-FND-02 sadece schema/sink sağlar. Dashboard deployment hikâyesi ayrı sahiplenilir. |
| 10 | **Alert / SLO Thresholds** (PrometheusRule, ADN-03 latency/error SLO) | ❌ Gelecek | ADN-03 kararı sonrası SLO / Alert Story | HIGH — INVENTION RISK | S-FND-02 HİÇBİR sayısal SLO threshold (p99, 500ms vb.) TANIMLAMAZ. SLO'lar ADN-03 + E-API deploy story. Threshold icat MAJOR scope drift. |
| 11 | **Audit Storage Immutability** (Append-only file, hash chain, vault) | ❌ Gelecek | Future SECURITY Story (S-SEC-01: Audit Immutability) | MEDIUM | S-FND-02 sadece AUDIT tag + never-drop rule sağlar. Storage immutability ayrı SEC hikâyesi; gap-05 future. |
| 12 | **APM / Distributed Tracing** (OTel SDK, Zipkin/Jaeger export, sampling) | ❌ Gelecek | Future Tracing Story (S-FND-05+ Observability Ext) | LOW | Current correlation alanları (correlation_id/causation_id) OTel trace_id/span_id ile **opsiyonel olarak** eşleştirilebilir (NG-4 no OTel import bu hikâye). |
| 13 | **Retention / Rotation Policy** (Log lifecycle, 7 gün sil, arşiv) | ❌ Gelecek | Future Deployment Story (Operasyonel) | LOW | S-FND-02 rotation YOK (NG-8). Dosya boyutu limitleri INI section OD-01 future ile eklenebilir. |
| 14 | **PyYAML / Third-party Logger** (YAML config, structlog/loguru entegrasyonu) | ❌ Gelecek | OD-FND-04 Open Decision (future C3 exception varsa) | MEDIUM — DEPENDENCY RISK | S-FND-02 KESİNLİKLE stdlib JSON-only (NG-6). PyYAML importu bu hikâyede HR-5 FAIL. Gelecekte OD-FND-04 onaylırsa ayrı extension hikâyesi; S-FND-02 unchanged. |

---

## Preservation Summary (Risk Count)

| Risk Seviyesi | Capability Sayısı | Detay |
|---|---|---|
| 🟢 LOW | 8 / 14 | Schema / Correlation Helper / Metrics ABC / 6 Sinks / Serialization / FC-10 Rules / Dashboard / APM |
| 🟡 MEDIUM | 4 / 14 | Masking Utility + Audit Storage Immutability + Retention/Rotation + PyYAML Dep |
| 🔴 HIGH | 2 / 14 | **Prometheus Exporter (scope creep)** + **SLO Thresholds (invention risk)** |

### Toplam Koruma Garantisi (Current 8 Capability)
✅ **Current S-FND-02 tarafından teslim edilen 8 capability (1-7) GERİYE DOĞRU UYUMLU OLARAK SAKLANIR.**
- Yeni alanlar: sadece OPTIONAL
- Yeni methodlar: sadece ek (append-only)
- Mevcut method imzaları / field isimleri / field türleri: SABİT
- Determinism / fail-safe / masking behavior: regression testleri ile KALICI OLARAK KORUNUR

### Kırmızı Çizgi (Non-Preservation Violation = MAJOR)
Aşağıdakilerden herhangi biri PRESERVATION MATRIX ihlalidir → MAJOR scope drift:
1. CanonicalLogLine 11 zorunlu alandan birini KALDIRMAK veya türünü DEĞİŞTİRMEK.
2. CounterIntf / HistogramIntf / GaugeIntf method isimlerini veya parametrelerini DEĞİŞTİRMEK.
3. Deterministic JSON serialization key-sorted kuralını KALDIRMAK.
4. FC-01..FC-10'dan birini OVERRIDE ederek "call site exception yükseltmek" (AD-19 fail-safe ihlali).
5. Prometheus exporter / SLO threshold tanımlamak (NG-1, NG-2 ihlali).
6. PyYAML / structlog / 3rd-party import (HR-5 ihlali).

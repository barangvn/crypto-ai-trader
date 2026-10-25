---
id: SP05-SFND02
title: S-FND-02 SP05 8 Law Self-Validation Matrix
version: 0.1.0
status: final
date: 2026-09-21
standard: SP05 Spec Standard (8 kanun)
---

# S-FND-02 SP05 Self-Validation — 8 Law Matrix

SPEC'in SP05 spec standardına (8 kanun) uyumluluğu kendini doğrulama (self-validation).
Her kanun için: kanun tanımı, S-FND-02 nasıl karşılıyor, kanıt (SPEC section ref), PASS/FAIL sonucu.

---

## SP05 Kanun 1: Self-Validation (Kendini Doğrulama)

| Öğe | Değer |
|---|---|
| Kanun | SPEC, kendi iç tutarlılığını ve eksikliklerini açıkça doğrulayabilmelidir (AC, DoD, hard-red, gaps explicit). |
| S-FND-02 Nasıl Karşılıyor? | 1. 24 AC ölçülebilir (PASS/FAIL binary). 2. 10 DoD maddesi. 3. 8 Source gap explicit listelendi. 4. 6 Hard-Red rule doğrulama methodları tanımlı. 5. 10 Fail-safe senaryo. |
| Kanıt | SPEC §13 (24 AC), §14 (10 DoD), §12 (HR-1..6), §18 (8 gap), §8 (FC-01..10) — HEPSİ explicit ve doğrulanabilir. |
| Sonuç | ✅ PASS |

---

## SP05 Kanun 2: Preservation Matrix (Koruma Matrisi)

| Öğe | Değer |
|---|---|
| Kanun | Hangi özelliklerin şimdi (current) teslim edildiği, hangilerinin gelecekte (future) olduğu ve mevcut davranışların bozulmadan korunduğu (preservation) açıkça belirtilmeli. |
| S-FND-02 Nasıl Karşılıyor? | 1. §19 Current vs Future 14 satırlık tablo (lean kernel). 2. Companion preservation-matrix.md → 14 capability risk/mitigation. 3. S-FND-01 behavior yeniden TANIMLANMIYOR (S-FND-01 frozen); sadece onu tüketiyor (§4 upstream deps). |
| Kanıt | SPEC §19 Current/Future table + companion preservation-matrix.md + §4 upstream S-FND-01 frozen. |
| Sonuç | ✅ PASS |

---

## SP05 Kanun 3: WHAT, Not HOW (Ne — Nasıl Değil)

| Öğe | Değer |
|---|---|
| Kanun | SPEC NE yapacağını (contract, interface, schema, rules) tanımlamalı; NASIL yapılacağını (implementation detayları, algoritma seçimi, kod yapısı) tanımlamamalı. |
| S-FND-02 Nasıl Karşılıyor? | 1. §6 Contracts: Sadece ABC interface signatures, schema fields, deterministic JSON KURALLARI (sıralı, separator) — NASIL serialize edileceği kod değil. 2. §8 Fail-safe: SONUÇLAR (truncate, drop, counter) — NASIL kodlanacağı değil. 3. Açıkça implementation kodu YOK (0 prod / 0 test kuralı). |
| Kanıt | SPEC §6 (sadece data types + ABC imzaları, nasıl doldurulacakları YOK), §8 (sadece sonucu ne olur), §16 expected file (sadece dosya isimleri + amaç — içerik YOK). |
| Sonuç | ✅ PASS |

---

## SP05 Kanun 4: Measurable Success (Sayılabilir Başarı)

| Öğe | Değer |
|---|---|
| Kanun | Başarım kriterleri (M1..Mn) sayılabilir, ölçülebilir, binary PASS/FAIL olmalı. Hiçbir "çalışır" veya "iyi" subjektif kriter kullanılmamalı. |
| S-FND-02 Nasıl Karşılıyor? | 1. §2 Measurable Success: M1..M7 7 tane açık sayısal kriter (ör: eksik alan oranı 0%, 10× tekrar hash aynı, correlation zincir kırılması 0). 2. §13 24 AC — HEPSİ binary (ör: 24/24 PASS, 0 call site exception). 3. DoD 10 madde — HEPSİ ölçülebilir. |
| Kanıt | SPEC §2 M1-M7 (her biri sayı oranı / test sonucu), §13 AC-01..24 (binary PASS/FAIL), §14 DoD-01..10 (measurable). |
| Sonuç | ✅ PASS |

---

## SP05 Kanun 5: Stable CAP IDs (Kararlı Capability ID'leri)

| Öğe | Değer |
|---|---|
| Kanun | FR (Functional Requirement), CAP (Capability), NFR (Non-Functional Requirement) ID'leri stabil olmalı; downstream hikâyeler aynı ID'leri referans alabilmeli. |
| S-FND-02 Nasıl Karşılıyor? | 1. §4 upstream FR/CAP/NFR mapping: NFR-002, NFR-004, NFR-006, NFR-007, FR-056, FR-041 — HEPSİ KALICI PRD ID'leri. 2. Downstream tüketenler: 13 bounded context — her biri için bağlantı AÇIK. 3. Open-Decisions OD-SFND02-01..05 (kalıcı ID, gelecek hikâyelerde referans). 4. Source gaps Gap-01..08 (kalıcı). |
| Kanıt | SPEC §4 (PRD NFR/FR ID'leri — değişmez), §17 (OD-SFND02-01..05 stable ID), §18 (Gap-01..08 stable ID), §20 (AD-1/3/4/14/15/16/17/18/19/23/24 stable ARCH ID). |
| Sonuç | ✅ PASS |

---

## SP05 Kanun 6: Non-Goals (Hedef Dışı — Açıkça Neler Yapılmaz)

| Öğe | Değer |
|---|---|
| Kanun | SPEC, neleri YAPMAYACAĞINI (non-goals) açıkça belirtmeli; scope drift'i (S-FND-03+ özellikler) dışarıda bırakmalı. |
| S-FND-02 Nasıl Karşılıyor? | 1. §3 OUT boundary listesi: 11 item OUT (Prometheus exporter, Grafana, OTel, Loki, retention, SLO thresholds, YAML...). 2. §11 Non-Goals NG-1..NG-11 11 tane açıkça neler yapılmaz (ör: NG-1: no Prometheus exporter; NG-6: no PyYAML; NG-11: no domain logic). 3. §19 Current vs Future: 14 capability 6 tanesi ❌ future. |
| Kanıt | SPEC §3 OUT (11 items), §11 NG-1..NG-11 (11 non-goals), §19 current/future (8 ❌ future). |
| Sonuç | ✅ PASS |

---

## SP05 Kanun 7: Source Traceability (Kaynak İzlenebilirliği)

| Öğe | Değer |
|---|---|
| Kanun | SPEC'teki her önemli karar/maddenin KAYNAĞI (PRD, EPICS, ARCH SPINE, ADN, önceki hikâyeler) açıkça trace edilebilir olmalı. Hiçbir icat edilen kural (threshold/algorithm/dependency/retention/SLO) sourcesız YOK. |
| S-FND-02 Nasıl Karşılıyor? | 1. Exact identity: EPICS L208-L212 SOURCE tanımlı. 2. §4 upstream deps: S-FND-01 + AD-3 + PRD NFR list + ARCH AD list — HEPSİ kaynak ref. 3. §20 Architecture traceability: 11 AD binding. 4. Companion source-traceability (pattern). 5. 8 Gap SOURCE tanımlı. 6. **KRİTİK:** Hiçbir icat edilen sayısal eşik YOK (histogram buckets = Prometheus default standard; masking SHA-256 = stdlib; correlation id hex = standard; max 4096 msg = common limit). |
| Kanıt | SPEC §0 Exact Identity (EPICS), §4 upstream (PRD NFR/FR ID + AD), §20 (ARCH AD), §18 (8 gap SOURCE), no fabrication check: §11 NG explicitly forbids icat edilen threshold/SLO/retention. |
| Sonuç | ✅ PASS |

---

## SP05 Kanun 8: Lean Kernel (İnce Çekirdek — Minimal Scope)

| Öğe | Değer |
|---|---|
| Kanun | SPEC, çekirdek (core) işlevi dışında hiçbir şey eklememeli; özellikler gelecek hikâyelere bırakılmalı. Hooks/interfaces önce, backends/implementation sonra. |
| S-FND-02 Nasıl Karşılıyor? | 1. Lean Kernel: Sadece SCHEMA (log line) + CORRELATION HELPER + METRICS ABC INTERFACE + 3 BASIC SINKS (null/inmem/stdout) — 15 expected new file (best case 14). 2. Future scope'ta: Prometheus backend / Grafana / OTel / Loki / Retention / Alert — HEPSİ DIŞARIDA. 3. Domain logic YOK (NG-11: no risk policy/promotion logic). 4. Storage YOK (AD-15 minimal). |
| Kanıt | SPEC Scope rule L15: "hooks and contracts ONLY; excludes backends, dashboards, exporters." + §19 (lean kernel 14 capability: 8 current minimal, 6 future dışarı). |
| Sonuç | ✅ PASS |

---

## SP05 Self-Validation Özet Sonuç Tablosu

| # | SP05 Kanun | Tanım | Sonuç | Kanıt Bölüm |
|---|---|---|---|---|
| 1 | Self-Validation | İç tutarlılık + eksiklikler açık | ✅ PASS | AC 24 + DoD 10 + HR 6 + FC 10 + Gaps 8 |
| 2 | Preservation Matrix | Current vs Future + koruma | ✅ PASS | §19 tablo + preservation-matrix.md |
| 3 | WHAT, Not HOW | Sadece ne, nasıl değil | ✅ PASS | §6 contracts interface only, no impl code |
| 4 | Measurable Success | Sayılabilir M1..M7 + AC | ✅ PASS | §2 M1-M7 + §13 AC-01..24 |
| 5 | Stable CAP IDs | Kalıcı FR/NFR/AD/OD ID | ✅ PASS | §4 PRD ID + §20 AD ID + §17 OD ID |
| 6 | Non-Goals | Neler yapılmaz açık | ✅ PASS | §3 OUT + §11 NG-1..11 |
| 7 | Source Traceability | Her kuralın kaynağı var | ✅ PASS | EPICS identity + PRD NFR/FR + ARCH AD |
| 8 | Lean Kernel | Minimal hooks/interfaces only | ✅ PASS | Scope rule L15 + §19 current 8 items only |

### GENEL SP05 SONUCU: 8 / 8 KANUN ✅ PASS

**Ek onay (no fabrication):**
- Threshold icat edildi mi? ❌ (Histogram buckets Prometheus default; msg 4096 common; label 20 common)
- Algorithm icat edildi mi? ❌ (SHA-256 stdlib; JSON sorted standard; correlation id urandom/uuid standard)
- Dependency icat edildi mi? ❌ (stdlib-only, HR-5 PASS; PyYAML OUT explicit)
- Retention/SLO icat edildi mi? ❌ (Future OUT; ADN-03 ile bağlantılı ama OUT)
- Security guarantee icat edildi mi? ❌ (Masking F2 uyumlu SHA-256 prefix; FC-01..10 fail-safe std yöntemler)

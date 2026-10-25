---
id: OD-SFND02
title: S-FND-02 Açık Kararlar (Open Decisions)
version: 0.1.0
status: active
date: 2026-09-21
resolution: Implementation aşamasında çözülür (tavsiye edilen defaultlar belirtilmiş)
---

# S-FND-02 Open Decisions (5 karar)

SPEC bu kararları çözmez; her karar için: etki, sahibi, şiddet, önerilen çözüm (varsa) belirtilir.
Tüm kararlar `specs/SPEC.md` §17 kaynağından türetilmiştir.

---

## OD-SFND02-01: Observability INI Section vs Hardcoded Defaults

| Öğe | Değer |
|---|---|
| Decision ID | OD-SFND02-01 |
| Kaynak | SPEC §17 OD-01 + §16 EX-01..EX-04 + §4 upstream AD-18 |
| Problem | 4 env (dev/test/stg/paper-prod) için observability default (log level, sink seçimi) — INI dosyalarına `[observability]` section eklensin mi, yoksa factory içinde hardcoded map mi? |
| Etki - Seçenek A (INI section) | 4 existing dosya MODIFY → EX-01..EX-04 4 istisna aktif. Configurability yüksek, ama existing modification sayısı 4. |
| Etki - Seçenek B (Hardcoded factory defaults) | 0 existing modification. Defaultlar: <br>• dev → INFO + StdoutJsonSink <br>• test → DEBUG + InMemoryCaptureSink <br>• stg → WARN + StdoutJsonSink <br>• paper-prod → ERROR + StdoutJsonSink <br>**(ÖNERİLEN SEÇENEK)** |
| Sahibi | Foundation implementer |
| Şiddet | MINOR. Tradeoff: configurability ↔ existing modification count. |
| Önerilen | SEÇENEK B — Hardcoded defaults. HR-1 (0 existing modify) ihlal etmez; EX-01..EX-04 HEPSİ DROP edilir. Gelecek sürümde INI section ekleme C1 explicit onayı ile yapılır. |
| Çözüm Zamanı | Implementation start (C1/C2 approval phase) |
| Bağımlı ADN | ADN-03 (alerts SLO thresholds) — gelecekte INI section'a ek threshold gelebilir, ama şimdilik YOK. |

---

## OD-SFND02-02: Test Fixtures Location

| Öğe | Değer |
|---|---|
| Decision ID | OD-SFND02-02 |
| Kaynak | SPEC §17 OD-02 + §16 EX-05 (tests/conftest.py append) |
| Problem | S-FND-02 test fixtures (correlation provider mock, frozen ts provider, test logger) — `tests/conftest.py` EOF append mi, yoksa yeni `tests/foundation/conftest.py` mi? |
| Etki - Seçenek A (tests/conftest.py append) | 1 existing modification (EX-05, S-FND-01 C2 benzeri EOF append). Fixture visibility global TÜM test suite. |
| Etki - Seçenek B (tests/foundation/conftest.py YENİ) | 0 existing modification (yeni dosya). Fixture discovery: pytest 9.1.1 → FOUND (alt klasör conftest.py otomatik). **(ÖNERİLEN)** |
| Sahibi | Foundation test implementer |
| Şiddet | MINOR. Fixture discovery riski (pytest config) yok. |
| Önerilen | SEÇENEK B — Yeni klasör + yeni conftest.py. EX-05 DROP edilir, HR-1 = PASS (0 modify). |
| Çözüm Zamanı | Implementation phase test setup |

---

## OD-SFND02-03: PyYAML / YAML Log Config?

| Öğe | Değer |
|---|---|
| Decision ID | OD-SFND02-03 |
| Kaynak | SPEC §17 OD-03 + §11 NG-6 (no YAML) + §3 OUT (PyYAML OUT) + S-FND-01 OD-FND-04 |
| Problem | Log format/level config YAML ile yapılır mı? OD-FND-04 (PyYAML future optional) kararı bu hikâyeye otomatik taşınır mı? |
| Etki - YAML kullanılırsa | 1. C3 explicit exception (new bağımlılık) + pyproject.toml modify + HR-5 FAIL riski. 2. OD-FND-04 SPEC onayı (CONDITIONAL) S-FND-02 için TEKRAR açılmalı. 3. Scope drift riski. |
| Etki - YAML KULLANILMAZSA | HR-5 = PASS (stdlib-only), OD-FND-04 bu hikâye için GEÇERLİ DEĞİLDİR (isolated decision), S-FND-02 JSON stdlib-only. **(ÖNERİLEN)** |
| Sahibi | Foundation implementer + OD-FND-04 kararı sahibi |
| Şiddet | MAJOR if violated. HR-5 ihlal + scope creep. |
| Önerilen | S-FND-02 KESİNLİKLE JSON + INI (ops) / hardcoded (önerilen). **YAML KESİNLİKLE DİŞARIDA.** OD-FND-04 kararı bu hikâyeye TAŞINMAZ; her hikâye kendi YAML kararını verir. Bu hikâye: JSON-only. |
| Çözüm Zamanı | SPEC aşaması KAPATILDI (kesin JSON-only) → implementation phase'te değişmez. |
| Bağımlı ADN | OD-FND-04 (global YAML future optional) — S-FND-02 bu kararı ihlal ETMEZ, çünkü S-FND-02 YAML kullanmıyor. |

---

## OD-SFND02-04: Histogram Default Bucket Override?

| Öğe | Değer |
|---|---|
| Decision ID | OD-SFND02-04 |
| Kaynak | SPEC §17 OD-04 + §6.2 metrics buckets sabit |
| Problem | Histogram default bucket thresholds (12 adet, `(.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10, inf)`) — farklı bounded context (ör: AI inference latency / paper fill latency) için farklı bucketlar izin verilmeli mi? |
| Etki - Sabit buckets (override YOK) | Determinism (D3) 100% garanti. Her context aynı bucket. Prometheus exporter future'da aggregation kolay. |
| Etki - Override izni (histogram(..., buckets=...)) | SPEC §6.2 zaten izin veriyor (buckets parametresi optional). Ama **DEFAULT** = sabit; override sadece explicit parametre varsa. Determinism preserved: same input buckets → same histogram. **(ÖNERİLEN)** |
| Sahibi | Foundation + downstream context owners |
| Şiddet | TRIVIAL. SPEC §6.2 zaten override param veriyor. Karar = default sabit, override opsiyonel. |
| Önerilen | Default = SPEC sabit 12 bucket. Override opsiyonel, ama buckets tuple sırası ve türü check edilir (geçersizse FC-06 + default fallback). |
| Çözüm Zamanı | Implementation phase metrics interface |
| Bağımlı ADN | ADN-03 (SLO thresholds/alerts) — bucket seçimi SLO tanımlarını etkiler ama şimdilik default sabit. |

---

## OD-SFND02-05: Audit Log Immutability / Storage

| Öğe | Değer |
|---|---|
| Decision ID | OD-SFND02-05 |
| Kaynak | SPEC §17 OD-05 + §11 NG-5 (no immutability impl) + §3 OUT |
| Problem | FR-041/FR-056 AUDIT tagged kayıtlar — append-only storage, hash chain immutability, vaulting — bu hikâyede yapılır mı? |
| Etki - Bu hikâyede yapılırsa | 1. Scope creep (NG-5 ihlal). 2. Storage bağımlılığı (AD-15 minimal polyglot) → risk. 3. Future SEC story ile duplication. |
| Etki - Gelecek SEC hikâyesine bırakılırsa | S-FND-02 sadece AUDIT tagged mesajları `[AUDIT]` prefix + özel dropped counter + FC-01..FC-10 (düşürülmez, truncate/label ile kaydedilir) garantiler. Storage/immutability → gelecek. **(ÖNERİLEN)** |
| Sahibi | Future SECURITY hikâyesi (S-SEC-01?) |
| Şiddet | MAJOR if implemented here. NG-5 / §3 OUT ihlali. |
| Önerilen | S-FND-02: AUDIT tag semantiği + "never drop" rule + counter. Storage immutability → DEFERRED future security story. |
| Çözüm Zamanı | Future SEC story (out of S-FND-02 scope) |

---

## Open Decisions Özet Matrisi

| # | ID | Başlık | Şiddet | Önerilen | Existing Mod Impact | Bağımlı ADN |
|---|---|---|---|---|---|---|
| 1 | 01 | INI section vs Hardcoded | MINOR | Hardcoded (0 EX) | 0 (Drop EX-01..04) | ADN-03 |
| 2 | 02 | Fixtures location | MINOR | tests/foundation yeni (0 EX) | 0 (Drop EX-05) | — |
| 3 | 03 | PyYAML usage | MAJOR if violated | JSON-only (YAML OUT) | 0 | OD-FND-04 |
| 4 | 04 | Bucket override | TRIVIAL | Default sabit + override ops | 0 | ADN-03 |
| 5 | 05 | Audit immutability | MAJOR if in scope | Future SEC story | 0 | Future S-SEC |

**Default kararlara göre: 0 existing modification (HR-1 PASS), 0 new dependency (HR-5 PASS).**

---
id: HR-SFND02
title: S-FND-02 Hard-Red Kuralları
version: 0.1.0
status: final
date: 2026-09-21
binding: MANDATORY (her biri için ihlal MAJOR scope drift)
---

# S-FND-02 Hard-Red Rules (6 kural)

S-FND-02 Structured Logging & Base Observability Hooks hikâyesi için kesin, değişmez kurallar.
Herhangi bir ihlal, "MAJOR scope drift" olarak sınıflandırılır ve hikâyenin kabulünü REDACTED eder.
Tüm kurallar `specs/SPEC.md` §12 kaynağından türetilmiştir.

---

## HR-1: Existing File Modification Default = 0

| Öğe | Değer |
|---|---|
| Kural ID | HR-1 |
| Kaynak | SPEC §12 HR-1 + §16 Expected File Changes policy |
| Kural | S-FND-02 implementation aşamasında **mevcut repo dosyalarına (S-FND-01 / E-API / S-MDL tarafından sahiplenilen) varsayılan olarak DOKUNULMAZ.** Existing dosyaların değiştirilmesi, **yalnız ve yalnız** explicit EX-prefix ile listelenmiş, source-backed exception'lar ile mümkündür. |
| Nasıl Doğrulanır | `git diff HEAD --name-only` çıktısındaki M (modified) dosyaları: <br>1. Her M dosyası için EX- listesinde kayıtlı mı kontrol et <br>2. Kayıtlı değilse → FAIL <br>3. Default (önerilen) durum: M sayısı = 0 |
| PASS | Mevcut değişiklik sayısı = 0 VEYA tüm M'ler EX-01..EX-05 listesinde explicit olarak izin verilmiş ve change miktarı EX tanımı ile sınırlı |
| FAIL | EX listesinde olmayan herhangi bir existing dosya modify edilmesi |
| İstisna | EX-01: 4 INI dosyasına [observability] section ekle (OPTIONAL — hardcoded defaults ile DROP edilebilir) <br>EX-05: tests/conftest.py EOF append (OPTIONAL — tests/foundation/conftest.py yeni dosya ile DROP edilebilir) |

---

## HR-2: No Network / No Live Execution

| Öğe | Değer |
|---|---|
| Kural ID | HR-2 |
| Kaynak | SPEC §12 HR-2 + §3 OUT (no Prometheus exporter / remote write) + S-FND-01 F1 no-network marker |
| Kural | Logger ve metrics hooks tarafından **hiçbir outbound HTTP/socket/network çağrısı yapılmaz.** Sadece Null / Stdout / In-Memory built-in sink'ler kullanılır. Remote write, exporter, backend entegrasyonu kesin olarak OUT. |
| Nasıl Doğrulanır | 1. Static analiz: `socket/httpx/requests/urllib3/aiohttp` import sayısı = 0 <br>2. Runtime: pytest F1 no-network fixture ile tüm testler PASS <br>3. Sink sınıflarında network erişimi YOK |
| PASS | Network import sayısı = 0; F1 marker testleri PASS; sink'ler sadece local |
| FAIL | Herhangi bir outbound çağrı veya network kütüphanesi importu |

---

## HR-3: No Credentials / No Secrets Leak (F2 Uyumlu)

| Öğe | Değer |
|---|---|
| Kural ID | HR-3 |
| Kaynak | SPEC §12 HR-3 + §9 SEC-1 (NFR-008 bağlantılı) + §8 FC-10 + S-FND-01 F2 no-credentials kuralı + B1 remediation rules + **PRD NFR-008 Security v1 "operate without secrets; future privileged default deny separately gated"** (zorunlu upstream bağlantı) |
| Kural | 1. Logger/metrics içindeki label değerleri, NEVER düz metin credential içerir. <br>2. Hassas anahtar (api_key/secret/password/token/credential/private_key) veya değer (JWT/sk/ak/xox prefix) → otomatik REDACTED:sha256[:12] maskelenir. <br>3. S-FND-01 F2 testleri (test_f2_no_credentials.py) 0 NEW false positive verir (B1 hala RESOLVED). |
| Nasıl Doğrulanır | 1. Credential scanner: SPEC §9 S1 regex'ini tüm code + test output üzerinde çalıştır <br>2. Masking utility AC-19 testleri PASS <br>3. `pytest tests/failure/test_f2_no_credentials.py -v` → 0 NEW hit (mevcut legacy 2 match S-MDL-01, out-of-scope ignore edilir) |
| PASS | Masking pozitif case 10/10 PASS; F2 suite 0 NEW false positive; credential scanner 0 SFND02-scope match |
| FAIL | Herhangi bir düz metin hassas value (maskesiz) veya NEW F2 hit |
| İstisna | YOK. Masking failure durumunda FC-05: value DROP edilir (satır değil, sadece değer). |

---

## HR-4: No Direct Registry Mutation

| Öğe | Değer |
|---|---|
| Kural ID | HR-4 |
| Kaynak | SPEC §12 HR-4 + AD-23 (Registry mutations via commands only) + §5 downstream ModelRegistry kullanımı |
| Kural | Logger ve metrics facade, **ModelRegistry veya herhangi bir bounded context state'ini DOĞRUDAN YAZMAZ.** Sadece counter/gauge snapshot üretir; future exporter tarafından okunur. Değişiklikler (registry promotion/rollback) → FR-041 audit LOG ile kaydedilir, state mutate EDİLMEZ. |
| Nasıl Doğrulanır | 1. Static analiz: `app/platform/observability/*` altında `registry/set_state/modify_state/transit` import veya çağrı sayısı = 0 <br>2. Code review: metrics sadece interface + inmem/stdout sink; registry write path YOK |
| PASS | Import count = 0; logger/metrics kodunda registry state mutation YOK |
| FAIL | Doğrudan registry state modify eden call veya import |

---

## HR-5: Stdlib-Only Runtime Dependency (F4 Uyumlu)

| Öğe | Değer |
|---|---|
| Kural ID | HR-5 |
| Kaynak | SPEC §12 HR-5 + §11 NG-6 (no PyYAML / loguru / structlog) + S-FND-01 F4 stdlib-only marker |
| Kural | S-FND-02 app/ kodunda **sadece Python stdlib kullanılır.** 3rd-party runtime bağımlılığı (structlog, loguru, PyYAML, prometheus-client, otel-sdk) 0. `prometheus-client` entegrasyonu E-API scope'undadır; bu hikâyede YOK. |
| Nasıl Doğrulanır | 1. `pyproject.toml` dependencies (S-FND-01 sonrası) list: [] (boş) — SFND02 sonrası da boş kalmalı <br>2. Static analiz: stdlib dışı import sayısı = 0 (app/platform/observability altında) <br>3. pytest F4 stdlib-only marker → PASS |
| PASS | Stdlib dışı import 0; pyproject deps []; F4 marker PASS |
| FAIL | 3rd-party library import veya pyproject bağımlılığı ekleme |
| İstisna | YOK. OD-FND-04 PyYAML kararı bu hikâyeye TAŞINMAZ; S-FND-02 JSON stdlib-only. |

---

## HR-6: No Unsafe Dynamic Execution

| Öğe | Değer |
|---|---|
| Kural ID | HR-6 |
| Kaynak | SPEC §12 HR-6 + §9 SEC-2 |
| Kural | Logger/metrics kodunda **eval(), exec(), compile(), pickle.loads(), yaml.unsafe_load()** gibi dinamik execution veya arbitrary code yükleme YOK. Sadece stdlib `json.dumps/loads` kullanılır; custom serializer safe. |
| Nasıl Doğrulanır | 1. Static regex: `\beval\(|\bexec\(|\bcompile\(|\bpickle\.|\block_config` sayısı = 0 <br>2. Code review: serialization sadece JSON stdlib safe calls |
| PASS | Yöntemlerden hiçbiri kullanılmamış |
| FAIL | Dinamik execution veya unsafe deserializer kullanımı |

---

## Özet Hard-Red Compliance Kontrol Listesi

| # | Kural | Default PASS? | İstisna Sayısı |
|---|---|---|---|
| 1 | HR-1 — 0 existing modify | ✅ (Önerilen: hardcoded defaults + tests/foundation/conftest.py yeni → 0 EX) | 5 optional (EX-01..05) |
| 2 | HR-2 — No network | ✅ (Sadece Null/InMem/Stdout sinks) | 0 |
| 3 | HR-3 — No credentials (F2) | ✅ (FC-10 masking + B1 preserved) | 0 |
| 4 | HR-4 — No registry mutation | ✅ (Interface only, no write) | 0 |
| 5 | HR-5 — Stdlib-only (F4) | ✅ (JSON + ABC + hashlib + uuid + os) | 0 |
| 6 | HR-6 — No unsafe exec | ✅ (Safe JSON only) | 0 |

**Toplam: 6/6 default PASS (0 EXceptions accepted).**

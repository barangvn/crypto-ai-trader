---
id: GAP-SFND02
title: S-FND-02 Source Gaps (8)
version: 0.1.0
status: explicit-deferred
date: 2026-09-21
resolution: TÜM gap'ler ya SPEC içinde kısmen çözüldü ya da future hikâyelere DEFER edildi. HİÇBİRİ bu hikâyeye gizlice çekilmedi.
---

# S-FND-02 Source Gaps (8 gap — explicit, NO fabrication)

PRD/EPICS/ARCHITECTURE-SPINE kaynaklarında S-FND-02 için tam olarak tanımlanmamış, bu hikâye içinde çözülmeyen (ya da SPEC içinde kısmi çözülen) konular.
**KRİTİK KURAL:** Hiçbir gap bu hikâyeye "gizlice" çekilmez; her gap için: durum, etki, sahibi, gelecek hikâyesi belirtilir.
Tüm gap'ler `specs/SPEC.md` §18 kaynağından türetilmiştir.

---

## Gap-01: Logger Output Format (Human-Readable vs JSON-Only)

| Öğe | Değer |
|---|---|
| Gap ID | Gap-01 |
| Açıklama | EPICS: "Structured logger (JSON)" diyor, ama human-readable fallback (geliştirici konsolu) izin veriliyor mu? Source belirsiz. |
| Kaynak | EPICS L208: "Structured logger JSON"; NFR-004: "Structured logs" |
| Durum | **ÇÖZÜLDÜ (SPEC içinde)** — SPEC §3 IN list + §6.1 "JSON, deterministic" → KESİNLİKLE JSON-only. Human-readable formatter OUT. |
| Etki | Hiç. SPEC açıkça JSON-only. |
| Hikâye | S-FND-02 (kendisi çözdü) |
| Sahibi | Foundation (resolved) |

---

## Gap-02: Metric Name Regex Pattern (Precise)

| Öğe | Değer |
|---|---|
| Gap ID | Gap-02 |
| Açıklama | Kaynaklarda "metrics name lowercase snake_case" var ama tam regex pattern (izin verilen karakterler, uzunluk sınırı) yok. |
| Kaynak | SPEC §6.2 metrics rules (kural 1-2) |
| Durum | **ÇÖZÜLDÜ (SPEC içinde)** — Regex: `^crypto_ai_[a-z0-9_]{1,124}$` (prefix crypto_ai_ + lowercase + digit + underscore, max 128 total chars). |
| Etki | Hiç. Deterministic validation var. |
| Hikâye | S-FND-02 (kendisi çözdü) |
| Sahibi | Foundation (resolved) |

---

## Gap-03: Masking Rule Regex / Exhaustive Key List

| Öğe | Değer |
|---|---|
| Gap ID | Gap-03 |
| Açıklama | Hassas alan masking için tam exhaustive key list source'ta YOK. Sadece örnekler (api_key, secret, password...) veriliyor. Regex pattern tam mı? |
| Kaynak | SPEC §8 FC-10 + §9 SEC-1 |
| Durum | **KISMİ ÇÖZÜLDÜ (SPEC + F2 COMPAT DEFERRED)** — SPEC içinde: <br>1. Positive list: `api_key/secret/password/token/credential/private_key` (case-insensitive, -/_ varyasyonları) <br>2. Value pattern: `xox/sk/ak/eyJhbGciO` (JWT prefix) <br>3. Ek: F2 uyumluluğu için S-FND-01 B1 rule'ları korunur. Gelecekte custom regex allowlist config (allowlist — EKLENECEK, future scope) bu gap'i tam kapatır. |
| Etki | MINOR. Gelecekte false negative (maskelenmemiş yeni key tipi) riski var ama F2 testleri ile yakalanır. |
| Hikâye | Gelecek Observability Config story (S-FND-04+ / E-API extension) |
| Sahibi | Future Observability owner |

---

## Gap-04: Redaction Hash Algorithm (SHA-256 vs BLAKE3)

| Öğe | Değer |
|---|---|
| Gap ID | Gap-04 |
| Açıklama | REDACTED referans hash'i hangi algoritma? Kaynak belirtmemiş. |
| Kaynak | SPEC §8 FC-10 masking rule |
| Durum | **ÇÖZÜLDÜ (SPEC içinde + HR-5)** — SPEC: `SHA-256(value)[:12]`. Neden? Python stdlib `hashlib.sha256` var; BLAKE3 3rd-party bağımlılık gerektirir (HR-5 FAIL). SHA-256 seçimi = stdlib-only + security yeterli (12 hex prefix collision riski pratikte 0). |
| Etki | Hiç. stdlib-only olduğu için HR-5 korunur. |
| Hikâye | S-FND-02 (kendisi çözdü) |
| Sahibi | Foundation (resolved) |

---

## Gap-05: Correlation ID Production Generator (CSPRNG vs UUID4)

| Öğe | Değer |
|---|---|
| Gap ID | Gap-05 |
| Açıklama | Canlı (paper-prod/stg) ortamda correlation_id üretimi: os.urandom CSPRNG mi, yoksa uuid4 mü? Source spesifik değil. |
| Kaynak | SPEC §9 SEC-7 + §6.3 CorrelationContext |
| Durum | **KISMİ ÇÖZÜLDÜ (SPEC + OPEN IMPL)** — SPEC iki seçeneği de İZİN VERİR (ikisi de stdlib): <br>1. Önerilen: `os.urandom(16).hex()` (32 hex char) → CSPRNG, tahmin edilemezlik yüksek. <br>2. Alternatif: `uuid.uuid4().hex` (32 hex char) → stdlib uuid. <br>Testlerde: deterministic provider enjekte edilir (D4 determinism). |
| Etki | TRIVIAL. İki yöntem de güvenli ve stdlib. Implementer seçer. |
| Hikâye | S-FND-02 (implementation anında çözülür, SPEC seçimi özgür bırakır) |
| Sahibi | Foundation implementer |

---

## Gap-06: Default Log Level Mapping per Env

| Öğe | Değer |
|---|---|
| Gap ID | Gap-06 |
| Açıklama | 4 env (dev/test/stg/paper-prod) için default log level (DEBUG/INFO/WARN/ERROR) — hangisi? Source yok. |
| Kaynak | SPEC §4 upstream S-FND-01 AD-18 env separation |
| Durum | **OPEN DECISION altına alındı (OD-SFND02-01)** — İki seçenek: <br>1. INI section ekle (4 existing modify, EX-01..04) <br>2. Hardcoded defaults (önerilen): <br>• dev=INFO, test=DEBUG, stg=WARN, paper-prod=ERROR <br>DEFAULT: hardcoded (0 existing modify) → bu gap OD-01 ile çözülür. |
| Etki | MINOR. HR-1 (0 existing mod) için önerilen hardcoded. |
| Hikâye | OD-SFND02-01 (implementation C1 phase) |
| Sahibi | Foundation implementer (OD-01) |

---

## Gap-07: Sink Selection Config Format (INI/JSON/YAML?)

| Öğe | Değer |
|---|---|
| Gap ID | Gap-07 |
| Açıklama | Env'e göre sink seçimi config formatı ne? INI section mı, JSON config mi, YAML mı? Source yok. |
| Kaynak | SPEC §4 AD-18 env separation + §16 EX-01 |
| Durum | **OPEN DECISION + ÇÖZÜLDÜ (OD-SFND02-01 + OD-SFND02-03)** — 2 karar birleşti: <br>1. Format: INI (eğer EX-01 seçilir) VEYA hardcoded (önerilen). YAML KESİNLİKLE OUT (OD-SFND02-03). <br>2. Önerilen: hardcoded mapping (dev=StdoutJson, test=InMemory, stg=StdoutJson, paper-prod=StdoutJson). |
| Etki | MINOR. OD-01 + OD-03 ile çözülür. |
| Hikâye | OD-SFND02-01/03 |
| Sahibi | Foundation implementer |

---

## Gap-08: Label Keys Exhaustive List / Allowlice

| Öğe | Değer |
|---|---|
| Gap ID | Gap-08 |
| Açıklama | Labels dict key'leri için exhaustive allowlist var mı? Yoksa free-form? Source yok. |
| Kaynak | SPEC §6.1 labels field tanımı + §6.2 labels rule |
| Durum | **ÇÖZÜLDÜ (SPEC içinde)** — Free-form, ama 2 sınırlama var: <br>1. Keys: lowercase snake_case (regex validation) <br>2. Count: max 20 key (FC-06, excess DROP edilir) <br>3. Masking: her key/value FC-10 regex'inden geçer. <br>Allowlist YOK. Gelecekte E-API config allowlist eklenebilir ama şimdilik gerek yok. |
| Etki | TRIVIAL. Downstream bounded context istediği key'i ekleyebilir ama sayı sınırı + masking var. |
| Hikâye | S-FND-02 (kendisi çözdü). Gelecekte E-API. |
| Sahibi | Foundation (resolved); future E-API |

---

## Source Gaps Özet Matrisi (8)

| # | ID | Açıklama | Durum | Çözüm / Future | Risk Seviyesi |
|---|---|---|---|---|---|
| 1 | 01 | Output format? | ✅ RESOLVED (SPEC) | JSON-only (S-FND-02) | YOK |
| 2 | 02 | Metric name regex? | ✅ RESOLVED (SPEC) | `^crypto_ai_[a-z0-9_]{1,124}$` | YOK |
| 3 | 03 | Masking key list exhaustive? | ⏳ DEFERRED (future) | Şimdilik positive list + F2 test; Gelecek: allowlist config | MINOR |
| 4 | 04 | Hash algoritması? | ✅ RESOLVED (SPEC+HR5) | SHA-256 (stdlib) | YOK |
| 5 | 05 | Correlation ID generator? | ⚠️ OPEN IMPL | `os.urandom` / `uuid4` (ikisi de OK) | TRIVIAL |
| 6 | 06 | Default log level env map? | ⚠️ OD-01 | Hardcoded (önerilen) / INI | MINOR |
| 7 | 07 | Sink config format? | ⚠️ OD-01+03 | Hardcoded (önerilen) / INI; YAML OUT | MINOR |
| 8 | 08 | Label keys exhaustive? | ✅ RESOLVED (SPEC) | Free-form + 20 key limit + masking | TRIVIAL |

**Toplam:**
- RESOLVED (SPEC içinde): 4/8 (Gap-01, 02, 04, 08)
- OPEN IMPL (implementer seçer): 2/8 (Gap-05, 06, 07 → 3, OD bağlantılı)
- DEFERRED future: 1/8 (Gap-03)
- **NO fabrication → NO gap gizlice bu hikâyeye çekildi.** ✅

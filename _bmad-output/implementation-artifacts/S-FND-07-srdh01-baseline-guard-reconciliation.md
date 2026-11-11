---
story_id: S-FND-07
title: "SRDH-01 Baseline Guard Reconciliation (F1/F2) — Tracked Baseline + Fail-Closed Contract + EOL-Normalized Hash"
story_key: "sfnd07-srdh01-baseline-guard-reconciliation"
epic: E-FND (Project Foundation & Environment)
status: approved-for-implementation
created: 2026-11-11
updated: 2026-11-11
sources:
  - ../../planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/OPEN-DECISIONS.md
  - ../../planning-artifacts/specs/spec-sfnd03-pytest-infrastructure-hard-boundary-2026-09-22/SPEC.md
  - ../../planning-artifacts/specs/spec-sfnd06-deterministic-contract-serialization-builders-2026-09-27/hard-red.md
  - ../epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md
  - ../INDEX.md
reference_commit: "7fdb1f63d07a17811640d2483d5136167080e218"
contract_version: "1.0.0"
---

# Story S-FND-07 — SRDH-01 Baseline Guard Reconciliation (F1/F2)

## 1. Story ID
`S-FND-07` (Epic E-FND — Project Foundation & Environment)

Not: `S-RDH-03` EPICS.md'de "Market Scanner (Universe Evaluation)" olarak rezerve edilmiştir; bu nedenle F1/F2 baseline guard reconciliation işi için `S-FND-07` kimliği kullanılır (Project Owner onaylı, bkz. §12).

## 2. Title
**SRDH-01 Baseline Guard Reconciliation (F1/F2) — Tracked Baseline + Fail-Closed Contract + EOL-Normalized Hash**

## 3. Goal
S-RDH-01 pipeline kaynaklarını koruyan iki regresyon testini (F1 ve F2) ortak, Git tarafından izlenen, fail-closed bir baseline sözleşmesine taşımak:

1. Baseline `.tmp/` (git-ignore, provenance'sız) yerine **Git-izlenen** `tests/baselines/srdh01_baseline_sha256.json` olur.
2. Baseline içeriği **referans commit `7fdb1f63d07a17811640d2483d5136167080e218`** ağacından üretilir (çalışma ağacından değil).
3. Baseline tam olarak **14 dosya** içerir (14 kayıt, ek anahtar yok).
4. Eksik baseline / bozuk JSON / eksik listelenen dosya / hash uyuşmazlığı → **explicit FAIL** (silent skip yasak).
5. F1 ve F2 **aynı** baseline sözleşmesini ve **aynı** EOL-normalizasyonunu uygular.

## 4. Context
- F1: [test_bus_backward_compat.py](../../tests/unit/platform/test_bus_backward_compat.py) → `test_AC04_srdh01_14_pipeline_sources_sha256_immutable_smoke` (S-PLN-01 tarafından eklendi).
- F2: [test_regression_srdh01_protection.py](../../tests/unit/ingest/registry/test_regression_srdh01_protection.py) → `test_srdh01_files_sha256_unchanged_regression_f2`, `test_baseline_has_15_entries`, `test_each_srdh01_file_exists`.
- Her iki test de `.tmp/srdh01_baseline_sha256.json` (16 giriş) dosyasını okur. 16 girişin 14'ü HEAD ile eşleşir; yalnız `pyproject.toml` ve `tests/conftest.py` drift eder (bayat baseline; gerçek kod regresyonu DEĞİL).
- F1 eksik baseline'da `FileNotFoundError` ile fail ederken F2 **sessiz skip** eder → sözleşme tutarsızlığı.
- `.tmp/srdh01_baseline_sha256.json` **tarihsel kanıt** olarak korunur; değiştirilmez/silinmez.

## 5. Scope
- Yeni baseline dosyasının üretilmesi (referans commit'ten, Git blob içeriğinden).
- F1 ve F2 testlerinin yeni baseline yoluna yönlendirilmesi, fail-closed davranışın uygulanması ve EOL-normalize hash karşılaştırmasının eklenmesi.
- Ortak helper dosyası **oluşturulmaz**.

## 6. Expected File Changes (Allowlist — AUTHORITATIVE)
Bu hikâye **yalnızca** aşağıdaki 3 dosyayı kapsar. Bu listenin dışındaki hiçbir tracked dosya new/modified olamaz.

### CREATE (1)
| # | Dosya | Amaç |
|---|---|---|
| N-01 | `tests/baselines/srdh01_baseline_sha256.json` | 14 dosyalık SRDH-01 baseline (referans commit `7fdb1f63…`) |

### MODIFY (2) — K0/HR-08 story-specific istisna gerektirir
| # | Dosya | Amaç |
|---|---|---|
| M-01 | `tests/unit/platform/test_bus_backward_compat.py` | F1: yeni baseline yolu + fail-closed + `==14` + EOL normalize |
| M-02 | `tests/unit/ingest/registry/test_regression_srdh01_protection.py` | F2: yeni baseline yolu + skip kaldırma + `==14` + EOL normalize + `SRDH01_FILES` 14'e hizalanır |

### DO NOT CREATE
- Ortak helper dosyası (`tests/_helpers*`, `conftest` eklentisi vb.) — **YOK**.

### DO NOT TOUCH (kapsam dışı)
- `pyproject.toml`, `tests/conftest.py`, `app/contracts/market.py`, `app/ingest/adapters/base.py`, `tests/integration/test_cap1_live_replay_parity.py`, `tests/integration/test_cap2_quality_in_envelope.py`, `app/platform/event_bus.py`
- `.tmp/srdh01_baseline_sha256.json` (tarihsel kanıt)
- `tests/failure/test_no_credentials.py`, `tests/failure/test_bus_no_credentials.py` (Option A2 — kesinlikle dokunulmaz)

## 7. Baseline Design
- **Konum:** `tests/baselines/srdh01_baseline_sha256.json` (Git-izlenen; `.tmp/` git-ignore'dur).
- **Şema:** düz `{"<repo-relative-path>": "<sha256-hex>"}` map. **Metadata alanı YOK** (testler tüm anahtarları dosya yolu sanar).
- **Kayıt sayısı:** tam **14**.
- **Hash kaynağı:** `git cat-file blob 7fdb1f63…:<path>` ham blob byte'ları (working tree değil).

### 14 dosya ve referans commit SHA-256 değerleri
| # | Yol | SHA-256 @ `7fdb1f63` |
|---|---|---|
| 1 | `app/contracts/canonical.py` | `a5a0ceb3d38b99edf95b237b09512b571636d5349a2dc2927ad25e1c7eeb9a00` |
| 2 | `app/contracts/types.py` | `258c4aca1a4b8ef7c65c8f1c19c0de249bde774b2decb5e699a2c8d890fc5c5a` |
| 3 | `app/ingest/adapters/replay_bundle_adapter.py` | `4eea47d7fbcfc6995ed1d4ee58bd196316ca3f969e3ae69e736389807bf59852` |
| 4 | `app/platform/__init__.py` | `5384bfdb2df380b6557cc7a71d16891415bccaa87699406e236f752c6415389f` |
| 5 | `app/processing/normalizer.py` | `44f81c278826785ef622bc7b0c6c1679a6173d8f8b37494e8ff4c7057177bcd9` |
| 6 | `app/processing/quality_monitor.py` | `9f0a2c57c4e342f627ce6c50a96fcc8c6ced27e5e83444459ca8953ecc493f86` |
| 7 | `app/processing/replay_clock.py` | `77c357d14fc596585523cdf01c37c19d984ca4aace3403ac80ba28759199ff84` |
| 8 | `tests/integration/test_pipeline_happy_path.py` | `0f5fa53c5cabb27dff1eaf317e9cfa8fda939e5b9e829243270d714d3fb5fedf` |
| 9 | `tests/unit/ingest/test_replay_bundle_adapter.py` | `fe39e9a8253cb812a51440d3ec96e49f5074422e442a2e5191a1f3b7659aa9dc` |
| 10 | `tests/unit/platform/test_event_bus.py` | `b9033377bf3cbdef19c1d9132a0f056a8b4959224b3130c5fb757180df2142d6` |
| 11 | `tests/unit/processing/test_validator_9checks.py` | `746d07f3c49d09445727f6170abc1d2386d99dc2a4e852538cfee8679a71bd8e` |
| 12 | `app/contracts/__init__.py` | `a78b793dda54f6a105706d9cc7db4cb1f0b83add2cc7f96b9a56fe878674ccd1` |
| 13 | `app/contracts/model.py` | `ccdae968c392ec682c0f2300b96686f37b1fcb3854c331ba0b34b3f27d5db904` |
| 14 | `app/contracts/opportunity.py` | `bf82addc057535fe4a666c55ad3367bc9272ffaae1887a16be2e8eb9a2df1613` |

- `app/platform/event_bus.py` baseline dışında kalır (F1 bunu açıkça assert eder).

## 8. EOL / Hash Contract
- Baseline üretiminde **Git blob içeriği** esas alınır (LF).
- Testler çalışma ağacındaki dosyayı okurken **yalnızca `CRLF → LF`** normalizasyonu uygular, sonra SHA-256 hesaplar:
  ```python
  hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
  ```
- Amaç: `core.autocrlf=true` kaynaklı sahte hash uyuşmazlığını önlerken içerikteki **gerçek** değişiklikleri yakalamaya devam etmek.
- Başka hiçbir içerik normalizasyonu yapılmaz (whitespace, encoding, trailing newline vb. dokunulmaz).
- Not: `.gitattributes` yoktur; repo LF saklar. Blob'da CR içermeyen dosyalarda normalizasyon no-op'tur.

## 9. Acceptance Criteria
- **AC-01:** `tests/baselines/srdh01_baseline_sha256.json` Git-izlenen yolda oluşturulur ve tam **14** kayıt içerir; metadata/ek anahtar yoktur.
- **AC-02:** 14 kaydın SHA-256 değerleri referans commit `7fdb1f63…` blob içerikleriyle birebir eşleşir.
- **AC-03 (F1 missing):** Baseline yoksa F1 **explicit FAIL** eder (skip yok).
- **AC-04 (F1 malformed):** Bozuk JSON'da F1 **explicit FAIL** eder.
- **AC-05 (F1 count):** F1 `== 14` kesin eşitlik kontrolü uygular.
- **AC-06 (F1 mismatch msg):** Hash uyuşmazlığında mesaj tam yol + tam expected + tam actual içerir.
- **AC-07 (F1 eol):** F1 CRLF→LF normalizasyonlu hash karşılaştırması yapar.
- **AC-08 (F1 exclusion):** F1 `app/platform/event_bus.py` kaydının baseline'da olmadığını doğrular.
- **AC-09 (F2 missing):** F2'de `skipif`/`pytest.skip` kaldırılır; eksik baseline **explicit FAIL** eder.
- **AC-10 (F2 malformed):** Bozuk JSON'da F2 **explicit FAIL** eder.
- **AC-11 (F2 missing file / mismatch):** Eksik dosya ve hash uyuşmazlığı **explicit FAIL** eder; mesajlar tam yol + tam hash içerir.
- **AC-12 (F2 eol):** F2, F1 ile **aynı** EOL normalizasyonunu kullanır.
- **AC-13 (F2 count):** `test_baseline_has_15_entries` → `test_baseline_has_14_entries` olarak yeniden adlandırılır ve `== 14` kontrolü yapar.
- **AC-14 (F2 list):** `SRDH01_FILES` aynı 14 dosyalık kapsama hizalanır.
- **AC-15 (parity):** F1 ve F2 aynı baseline dosyasını ve aynı hash sözleşmesini kullanır.

## 10. Test Plan
| # | Test | AC | Beklenen |
|---|---|---|---|
| T1 | `pytest tests/unit/platform/test_bus_backward_compat.py` | AC-01..AC-08 | PASS |
| T2 | `pytest tests/unit/ingest/registry/test_regression_srdh01_protection.py` | AC-01, AC-02, AC-09..AC-14 | PASS |
| T3 | F1/F2 davranış doğrulaması (eksik baseline, bozuk JSON, hash uyuşmazlığı, eksik dosya) | AC-03..AC-06, AC-09..AC-11 | Kod düzeyinde explicit FAIL yolları mevcut |

Kısıt: Yalnızca bu iki dosya çalıştırılır. Paket kurulumu yapılmaz. Zero-mutation: `PYTHONDONTWRITEBYTECODE=1` ve `-p no:cacheprovider`.

## 11. Definition of Done (DoD)
1. ✅ Expected-file allowlist tam eşleşme: **3 dosya** (1 CREATE + 2 MODIFY); başka new/modified tracked dosya yok.
2. ✅ Baseline tam **14** kayıt; değerler referans commit blob'larıyla birebir.
3. ✅ F1 ve F2 aynı baseline yolu + aynı EOL sözleşmesi + fail-closed.
4. ✅ Silent skip kalmadı (F2 `skipif`/`pytest.skip` kaldırıldı).
5. ✅ İki test dosyası PASS.
6. ✅ Kapsam dışı 9 dosyaya (7 hariç + `.tmp/` + 2 Option A2) dokunulmadı.
7. ✅ Git: stage boş, HEAD/branch/dirty sayısı korunur; commit/push yok.

## 12. Governance References
- OPEN-DECISIONS.md → **PLD-02 — F1/F2 SRDH-01 Baseline Guard Reconciliation (K0/HR-08 Story-Specific Exception, APPROVED)**; ayrıca önceki `# F1/F2 — SRDH-01 Baseline Kapsam ve Tasarım Kararı` DRAFT kaydının onayı.
- HR-08 (K0 ZERO BYTE DIFF) — S-FND-06 `hard-red.md`.
- K0 / 0 existing modification — S-FND-03 `SPEC.md`.

## 13. Risks
| # | Risk | Seviye | Azaltma |
|---|---|---|---|
| R-01 | F1/F2 modifikasyonu K0/HR-08 ihlal eder | Yüksek | Story-specific istisna (PLD-02) + 3-dosyalık allowlist |
| R-02 | EOL normalizasyonu blob'da CR içeren dosyayı yanlış değerlendirir | Düşük | `.gitattributes` yok, repo LF saklar; yalnız `CRLF→LF` |
| R-03 | Baseline'a metadata eklenirse testler anahtarı yol sanar | Orta | Düz map şeması, metadata YOK |
| R-04 | Test yürütmesi `.pytest_cache`/`.pyc` üretir | Orta | `-p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1` |

## 14. Developer Notes
- Baseline JSON anahtar sırası: §§7 tablosundaki sıra ile yazılır (insan-okunur tutarlılık; testler sıraya bağlı değildir).
- F1 `os.path` tabanlı; F2 `pathlib` tabanlıdır — helper dosyası açmadan her biri kendi içinde normalize eder.
- Testler çalıştırılırken repo kökünden `python -m pytest` kullanılır.

# Expected File Changes — S-FND-04

AUTHORITATIVE SAYIM: **TOPLAM 13 DOSYA.**
- NEW Production under `app/platform/config/`: 6
- NEW Test package under `tests/foundation_sfnd04/`: 7
- Existing file modifications: **KALICI 0 (EXCEPTION LIST 2 items → 2/2 PERMANENTLY DROPPED via CLOSED CANONICAL OD-01/02)**

---

## §1 — Toplam Summary
| Category | Count | Location |
|---|---|---|
| NEW Production | 6 | `app/platform/config/` (NEW package, AD-1 platform klasörü altı — S-FND-02 app/platform/observability/ komşu) |
| NEW Test | 7 | `tests/foundation_sfnd04/` (NEW test package parallel to S-FND-02 tests/foundation/, S-FND-03 tests/foundation_sfnd03/) |
| **Existing Modify (KALICI)** | **EXACT 0** | OD-01 CLOSED (PyYAML OFF) + OD-02 CLOSED (EX-01 dropped). 4 INI × 0 modify; pyproject.toml × 0 modify. K0 tam compliance. |
| Debug/Temp/Generated | 0 STRONG ZERO | `audit_*.json`, `_tmp_*.py`, `config.yaml.bak`, `__pycache__`, `.pytest_cache` allowlist dışı. |

---

## §2 — Conditional Exceptions (EX list) — 2/2 PERMANENTLY DROPPED (CLOSED CANONICAL DECISIONS)

| EX-ID | Existing Path | Why Need? | Closed Decision Evidence | Final Status (Canonical) | Post-Close Impact |
|---|---|---|---|---|---|
| EX-01 | `configs/config.{dev,test,stg,prod}.ini` × 4 dosya (⚠ AS-BUILT §21 MINOR-6: gerçek dosya adları `config.dev.ini`/`config.test.ini`/`config.stg.ini`/`config.prod.ini`; `config.paper-prod.ini` YOKTUR — loader `_CONFIG_ALIAS` `paper-prod → prod` eşler) | İçlerine `[platform_contract]` + `[observability]` section 2 + 6 satır EOF append (24 satır total). | **OD-FND-04-02 CLOSED = 4 kaynak evidence:** (1) S-FND-02 EX-01..04 DROPPED ACCEPTED L106/150; (2) S-FND-02 OD B seçeneği hardcoded defaults; (3) GERÇEK 4 INI okundu: sectionlar HALİHAZIRDA YOK + 3 commit PASS; (4) K0 default=0. | **PERMANENTLY DROPPED. KALICI 0 MODIFY.** Section yoksa AppConfig loader defaults düşer (3 optional section: safety/observability/platform_contract; sadece [env] zorunlu FC-2). Gelecekte override → YENİ Config Overlay v2 hikâyesi; bu SPEC geri dönülmez. | 4 INI byte-diff 0 preservation invariant. BLACKOUT commit filtered diff 0 lines against 4 paths. |
| EX-02 | `pyproject.toml` [project.dependencies] tek satır `pyyaml` ekleme. | PyYAML açıkken gerekli. | **OD-FND-04-01 CLOSED = 5 kaynak evidence:** (1) pyproject.toml L5 `dependencies=[]` boş; (2) S-FND-03 F4 marker L27 `pyyaml` FAIL_CLOSED list; (3) S-FND-02 HR-5 L82 OD-FND-04 bu hikâyeye taşınmaz JSON-only; (4) SPEC §3.1/§12 HR-5 stdlib default; (5) EPICS L185 format zorunluluk YOK. | **PERMANENTLY DROPPED. KALICI 0 MODIFY.** PyYAML 3p dep S-FND-04'e EKLENMEZ. YAML nested ergonomik workaround: INI comma-separated string + downstream extension JSON parse. Gelecekte YAML ihtiyacı → YENİ C3 Phase hikâyesi; bu SPEC geri dönülmez. | pyproject.toml byte-diff 0. S-FND-03 F4 marker PASS against config NEW 6 files. No new runtime dependency. |
| EX-03..N | — | — | K0 KURAL: existing-file modification default=0. 0 explicit future exception. | **TÜMÜ KALICI DROPPED.** Başka hiçbir existing dokunulmaz. | 0 existing modification GARANTİ. |

---

## §2.1 — Post-Closure Existing Scope Guarantee (K0 AUDIT)

```
K0 EXISTING MODIFY EXACT = 0.
GARANTİ: 4 INI + pyproject.toml + S-FND-01/02/03 app/tests + E-API = HİÇBİR existing dosya S-FND-04 implementation fazında MODIFY EDİLMEZ.
Eğer implementation fazında herhangi bir existing modify BLACKOUT diff'te görülürse → Hemen ROLLBACK (MAJOR scope drift violation).
Sadece 13 NEW dosya (N-01..13) allowlist.
```

## §3 — Debug / Temp / Generated — FORBIDDEN

| Pattern | Status | Neden? |
|---|---|---|
| `_tmp_config_*.py`, `_audit_cfg_*.py`, `cfg_scan_*.bak` | STRICT NO | Temp artifacts = allowlist dışı. K0 güzergahında audit script içinde transient oluştur → sil. |
| `app/platform/config/__pycache__/*.pyc`, `.pytest_cache/**` | Gitignore'd — allowlist sayılmaz | Runtime generated, NO commit. |
| Config dosyalarının YAML yedekleri (`*.yaml`, `*.yml.bak`) | STRICT NO — PyYAML kapalı default. | OD-01 açılmadan YAML dosya var = scope ihlali. |

## §4 — CANONICAL ALLOWLIST (N-01..N-13) — 13 NEW

| N-Id | Path (relative repo root) | Role | Prod/Test | Not |
|---|---|---|---|---|
| N-01 | `app/platform/config/__init__.py` | Module entry: public API re-exports (VersionConstants, ConfigFactory, AppConfig, ConfigValidationError). 3rd-party import YAML only if OD. | Production (platform/AD-1) | NEW. S-FND-02 app/platform/observability komşu klasör; 0 existing dokunulmaz. |
| N-02 | `app/platform/config/constants.py` | ONLY VersionConstants frozen dataclass + LITERAL 4 env list. Sadece hard-coded 4 sabit. | Production | NEW. |
| N-03 | `app/platform/config/models.py` | Typed dataclasses: EnvSafetyLocks, ObservabilitySection, PlatformContractSection, AppConfig. Stdlib dataclasses — 0 pydantic. | Production | NEW. |
| N-04 | `app/platform/config/loader.py` | ConfigFactory: read_env(), INI → typed mapper, extension_sections downstream register hook, optional yaml gate (_YAML_ENABLED flag). | Production | NEW. Core logic. |
| N-05 | `app/platform/config/validation.py` | validate_safety() fail-closed FC-3; validate_required_sections() FC-2; coerce strict (OD-04 strict); ConfigValidationError üretici. ✔ RESOLVED (§21 MAJOR-2, Package B / D-02): fonksiyonlar `parse_safety` / `validate_required_env_section` / `coerce_bool` / `coerce_int`; `coerce_bool` artık STRICT (native `bool` + `true`/`false`/`1`/`0`; `yes`/`no`/`on`/`off`/`y`/`n`, boş string, `None`, sayısal tipler → fail-closed). | Production | NEW. |
| N-06 | `app/platform/config/errors.py` | ConfigValidationError custom exception + dataclass. | Production | NEW. |
| N-07 | `tests/foundation_sfnd04/__init__.py` | Test package owner docstring. 0 code. | Test | NEW. |
| N-08 | `tests/foundation_sfnd04/conftest.py` | Fixtures: tmp_ini_factory, monkeypatch_constants_disabled, yaml_enabled_override fixture (test için monkeypatch _YAML_ENABLED). | Test-Fixture | NEW. Root conftest.py / tests/foundation/conftest.py DOKUNULMAZ (K0 HR-1). |
| N-09 | `tests/foundation_sfnd04/_helpers.py` | Test helpers: ini_write(dict → INI bytes), sha_json(obj) compact+sorted, count_imports(module) for HR audit. Stdlib only. | Test Library | NEW. |
| N-10 | `tests/foundation_sfnd04/test_sfnd04_version_constants.py` | TP-01: 6 test. Version constants values + frozen immutability. | Test (AC-01..06) | NEW. AS-BUILT: 6 fonksiyon / 6 collected. |
| N-11 | `tests/foundation_sfnd04/test_sfnd04_config_typed.py` | TP-02: 6 test. 4 env typed mapping / unknown env error / default section drops. | Test (AC-07..12) | NEW. ⚠ AS-BUILT (§21 MINOR-1, Package A / D-01 sonrası; aritmetik tutarlılık düzeltmesi 2026-10-26): 8 fonksiyon (3'ü parametrize) / 17 collected. |
| N-12 | `tests/foundation_sfnd04/test_sfnd04_validation.py` | TP-03 + TP-04: 8+3 test. Safety 4 locks fail-closed / missing section / missing file / yaml gate (kapalı) 3 test. | Test (AC-13..21) | NEW. ⚠ AS-BUILT (Package B / D-02 sonrası, §21 MINOR-1): 19 fonksiyon / 46 collected (TP-03+TP-04 aynı dosyada; Package B STRICT coercion kabul/ret testleri dahil). |
| N-13 | `tests/foundation_sfnd04/test_sfnd04_determinism_audit.py` | TP-05 + TP-06: 6D × 10 parametrize + audit record + regression smoke (imports). | Test (AC-22..24 + FC) | NEW. ⚠ AS-BUILT (§21 MINOR-8, Package C / K-3 sonrası): 18 fonksiyon / 21 collected; determinism yalnız `read_env` için 4 env parametrize × inner 10 = 40 iterasyon, "6D×10=60" DEĞİL. (Package C / K-3: 11 public audit API testi eklendi.) |

## §5 — SANITY COUNT (Post-Closure Canonical)

Production (N01..N06 = 6) + Test (N07..N13 = 7) → **13 NEW total.**
Existing modify = **KALICI 0**. EX-01/02 PERMANENTLY DROPPED → 0 modify.
**TOPLAM: 13/13 NEW + 0 EXISTING MODIFY = CANONICAL FINAL.**
Gelecekte EX-01/02 açmak için: YENİ HİKÂYE (Config Overlay v2 / C3 YAML Config). Bu SPEC'in 13/13 sayımı DEĞİŞMEZ.

## §6 — ⚠ AS-BUILT DOĞRULAMASI (2026-10-25 doc reconciliation; 2026-10-26 Package A/B/C güncellemesi)

| İddia | As-built kanıt | Durum |
|---|---|---|
| 13 NEW dosya (6 prod + 7 test) | `app/platform/config/` → 6 `.py`; `tests/foundation_sfnd04/` → 7 dosya. Commit `946a6b5` (13 files, 948 insertions, hepsi `A`). | ✅ DOĞRU |
| Existing modify = 0 (KALICI) | No production/test/config dosyası S-FND-04 fazında değiştirilmedi; K0 korunur. | ✅ DOĞRU |
| 4 env INI dosyası `config.{dev,test,stg,prod}.ini` | `configs/` içinde gerçek dosyalar: `config.dev.ini`, `config.test.ini`, `config.stg.ini`, `config.prod.ini`; `config.paper-prod.ini` yok. | ✅ DÜZELTİLDİ (MINOR-6) |
| Test dosya/fonksiyon sayıları (N-10..N-13) | 4 test modülü / 51 test fonksiyonu / 90 collected (Package C / K-3 sonrası). | ✅ DÜZELTİLDİ (MINOR-1, Package C güncellemesi) |

**NOT:** Bu tablo yalnız dosya envanteri ile ilgilidir. Davranış sözleşmesi uyuşmazlıkları: MAJOR-1 (Package A / D-01), MAJOR-2 (Package B / D-02) ve MAJOR-3 (public audit API → Package C / K-3 implementation) **RESOLVED**; MINOR-7 (A-2/A-3/A-4 → Package D) `SPEC.md §21`'de **KALIR AÇIK** gap olarak kayıtlıdır (Package D'de UYGULANMADI; kapatılmış gösterilmez).

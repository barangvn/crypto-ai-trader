---
companions:
  - acceptance-criteria.md
  - dod.md
  - test-plan.md
  - expected-file-changes.md
  - hard-red.md
  - open-decisions.md
  - source-gaps.md
  - architecture-traceability.md
  - preservation-matrix.md
  - sp05-self-validation.md
  - current-vs-future-boundary.md
  - implementation-readiness.md
  - reuse-map.md
  - risks-open.md
sources:
  - ../../../../implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md
  - ../../spec-crypto-ai-trader-2026-08-10/CONTRACTS.md
  - ../../spec-sfnd02-logging-observability-hooks-2026-09-21/SPEC.md
  - ../../spec-crypto-ai-trader-2026-08-10/OPEN-DECISIONS.md
---

# SPEC — S-FND-04: Typed Config Layer + Version Constants (INI/JSON stdlib + PyYAML Optional)

SPEC VERSION: v1.0-impl-ready (2026-09-24)
EPIC: Epic 1 — E-FND (Foundation Stories, completed 01/02/03 @ e1bdff7 / d02f58b / 55fd13e)
UPSTREAM: S-FND-01 Env Separation @ e1bdff7 + S-FND-02 Observability @ d02f58b + S-FND-03 Pytest Gates @ 55fd13e
AUDIT GATE (PLANNED snapshot): Pre-impl (Phase 1 SPEC prep, NO production/test code yet, 0 existing modify, 0 git ops)
AS-BUILT STATUS (2026-10-25 doc reconciliation; 2026-10-26 Package A/D-01 + Package B/D-02 + Package C/K-3): Implementation COMPLETE @ commit `946a6b5` (13 files, 948 insertions, all status "A" → K0). Story tests: `pytest -p no:cacheprovider tests/foundation_sfnd04/ -q` → 90 passed, exit 0 (this covers ONLY the S-FND-04 group; it is NOT full-regression evidence). Package A (D-01) aligned the dataclass attribute to `allow_api_keys`; Package B (D-02) implemented STRICT boolean coercion and closed OD-04; Package C (K-3) added the public audit API `read_env(env, return_audit=True) → (cfg, records)` in `loader.py` and its tests (MAJOR-3 as-built kod gap KAPANDI). Remaining contract↔implementation gaps (A-2/A-3/A-4 only) are retained inline with `⚠ AS-BUILT` and consolidated in §21.

## §1 — Intent (WHAT not HOW)

Tüm downstream hikâyelerin (S-CON, E-RDH, E-FEA, E-REG, E-STR, E-AIS, E-RSK, E-BKT, E-PTR, E-PTF, E-MDL, E-API) ihtiyaç duyduğu tek-sahip typed config katmanını kurar:
- 4 env (dev/test/stg/paper-prod) INI dosyalarını typed contract + schema validation ile okur
- contract_version 1.0.0 / app_version / schema_version gibi MVP sürüm sabitlerini tek noktadan çıkarır (EPICS E-FND L185)
- PyYAML bağımlılığını **CLOSED PERMANENTLY OFF (OD-FND-04-01 KAPALI)** olarak tanımlar. YAML kapak mekanizması (FC-5 gate) defense-in-depth olarak mevcut ancak KALICI DEVRE DIŞI. YAML gerekiyorsa YENİ C3 PHASE HİKÂYE. (default: INI/JSON stdlib only, PyYAML YOK 3p dep EKLENMEZ)
- S-FND-01 mevcut 4 INI dosyasını typed okur; yeni INI sectionları için future-proof extension noktaları bırakır (OD-02 CLOSED → section yoksa defaults düşer, 0 modify; gelecek overlay hikâyesi possible)

Özgün sahiplik (AD-7 tek yazarlık):
- **S-FND-04 SAHIP:** `app/platform/config/` typed loader, VersionConstants, ConfigSchema validation, typed Config dataclass.
- **SAHIP DEĞİL:**
  - 4 env INI dosyalarının section içeriği / field isimleri / default değerleri (sahiplik: ilgili hikâye, örn RSK limits = S-RSK owner; FND sadece typed okuma + validation sunar)
  - Logger/metric format (S-FND-02 property, OD-FND-04 SFND02 için JSON-only)
  - Pytest marker/gates (S-FND-03)
  - Pydantic/tomllib 3rd-party schema engine (E-CON isterse kullanır; FND stdlib attrs benzeri yok)

## §2 — Measurable Success (Sayılabilir)

Aşağıdaki 6 sayılabilir koşulun HEPSİ gerçekleşirse hikâye başarılıdır:

M-1 `from app.platform.config import VersionConstants; assert VersionConstants.contract_version == "1.0.0"` doğrular (NFR-019 / CONTRACTS).
M-2 ConfigFactory.read_env("dev") çağırdığında: typed dataclass döner; [env] section fields (db_namespace, artifact_path, run_mode_default) ve safety kilitleri (trading_permission_default, allow_api_keys, max_leverage_allowed, allow_short) S-FND-01 ile aynı değerler üzerinden mapping doğrulanır. ✔ RESOLVED (Package A / D-01): dataclass attribute adı `allow_api_keys` (INI option ve `exc.fields` ile aynı). Bkz. §21 MAJOR-1.
M-3 Validation: dev INI içine `max_leverage_allowed = 2` yazdığınızda schema validation HATA verir (v1 hard boundary S-FND-01 C2 safety kilidi).
M-4 PyYAML **CLOSED PERMANENTLY OFF (OD-FND-04-01)**: `yaml` import attempt SFND-04 katmanında ImportError yakalanır ve **sessizce INI fallback** OLMAZ; FC-5 gate kilidi açıkça `RuntimeError("PyYAML disabled by OD-FND-04")` verir. Geçersiz kılma için YENİ C3 PHASE HİKÂYE gerekir.
M-5 Her Config read sonucu json.dumps(sort_keys=True) ile 10 kez seri hale getirildiğinde AYNI SHA256[:12] üretir (determinism, D1..D4).
M-6 Tüm hikâye K0 (0 existing modification) ile tamamlanır. S-FND-01 4x INI dosyaları: EX-01 PERMANENTLY DROPPED (CLOSED OD-02) → KALICI 0 MODIFY, HİÇBİR existing DOKUNULMAZ.

## §3 — IN / OUT Scope Boundary

### 3.1 IN Scope (S-FND-04 implemente EDER)

| Kategori | İçerik | Kaynak Referans |
|---|---|---|
| Version Constants | `VersionConstants`: contract_version = "1.0.0", app_version = "0.1.0-mvp", schema_version = 1, build_metadata = "local-mvp" | EPICS L185 "contract_version (1.0.0) ve proje sürüm sabitleri" explicit scope + CONTRACTS §1 envelope schema_version zorunlu |
| Typed Config Dataclass | `AppConfig` / `EnvConfig` typed dataclass (stdlib dataclasses, 0 pydantic). Section alanları: [env], [observability], [platform_contract], [safety]. Gelecek sectionlar OD. | S-FND-01 C2 safety kilitleri + S-FND-02 OD-SFND02-01 observability section var |
| ConfigParser Layer | Stdlib `configparser.ConfigParser` → typed AppConfig mapper. INI dosyası okuma + section var mı kontrol + type coerce (int/bool/Decimal vs). | S-FND-03 OD-04 "parse INI ConfigParser stdlib, 0 tomllib/toml/pyproject import" default, FND-04'te carry doğrulandı (source: SFND03 OD-04 stdlib) |
| Schema Validation (stdlib-only) | Safety invariants: leverage>1 / allow_short=true / allow_api_keys=true / trading_permission_default=true → validation ERROR (S-FND-01 C2, v1 hard boundary PRD §1). ✔ RESOLVED (Package A / D-01): INI option `allow_api_keys` aynen okunur; ihlalde `exc.fields` = `allow_api_keys` ve dataclass attribute = `allow_api_keys` (§21 MAJOR-1). | PRD §1 v1 spot-only + S-FND-01 AC-21 safety kilidi |
| OD-FND-04 PyYAML Optional Gate | `_YAML_ENABLED = False` (default, kapalı). OD kararı verilmeden önce KESİNLİKLE: PyYAML import = DENY, RuntimeError. OD resolved onaylandığında (true): YAML config okuma opsiyonel. OD-04'ün S-FND-02 için "JSON-only" kararı burayı etkilemez (OD-FND-04 Ayrı scope: FND genel config formatı). | S-FND-02 L411 "OD-FND-04 = PyYAML FUTURE C3 kararını bu hikâye taşımaz" + L84 + L262 OPEN korur |
| Config Read Factory | `ConfigFactory.read_env(env_name: str) -> AppConfig` tek giriş noktası. Defaults: env_from_CRYPTO_AI_ENV override | S-FND-01 AC-22 env fallback |

### 3.2 OUT Scope (S-FND-04 HİÇ implemente ETMEZ)

| Kategori | Sahiplik / Neden |
|---|---|
| Pydantic / msgspec / tomllib 3rd-party typed schema | E-CON downstream, own scope. S-FND-04 stdlib dataclasses + manual validation. |
| pyproject.toml `[tool.config]` / TOML config | S-FND-03 OD-04 "pyproject import 0" carry → S-FND-04 ConfigParser INI stdlib ONLY. PyYAML PERMANENTLY OFF CLOSED OD-01. TOML HİÇ. |
| YAML'a geçiş / 4 INI → YAML dosyası conversion | **OD-FND-04-01 = CLOSED PERMANENTLY OFF.** Bu hikâye conversion YAPMAZ + YAML GATE KAPALI. YAML config gerekiyorsa YENİ C3 PHASE HİKÂYE açılır; bu SPEC geri dönülmez. |
| Her downstream bölümüne özgü config field tanımı (örn: RiskEngine limitleri, FeatureEngine lookback window, Strategy params) | Sahip ilgili hikâye (S-RSK, S-FEA-01, S-STR-01). FND sadece typed okuma + extension mekanizması (register_section) sunar, içerik TANIMLAMAZ. |
| DB Connection String / Object Storage (AD-15) / persistence path creds | E-PLN / S-MDL scope. FND safety sadece NO creds in config (S-FND-01 C2, F2 rule) |
| Hot reload / file watcher / dynamic config update | Future story. MVP v1 read-once startup. |
| CI YAML (.github/workflows), docker-compose, deployment config | OD-SFND03-02 CI = OPEN (S-FND-03). FND yok. |
| Config UI / dashboard write endpoint (MVP API write 2: emergency stop/kill switch) | E-API scope |
| S-FND-05+ (Alerting, registry foundation, storage bootstrap, concurrency primitives) | Lean kernel. Out of scope P01. |
| E-MDL ModelRegistry / ChampionChallenger config (FR-036, FR-037, AD-14) | Sahip E-MDL 4 story |

## §4 — Upstream Dependencies

| ID | Sahiplik | Neden gerekli? | Kesin commit SHA |
|---|---|---|---|
| UP-01 S-FND-01 Env Config Skeleton | Foundation | `configs/config.{dev,test,stg,paper-prod}.ini` 4 dosya mevcut; safety kilit alanları var. S-FND-04 typed okuma yapar (DEĞİŞTİRMEZ, EX-01 hariç) | `e1bdff70134cc5e797e7901a10fe9f28924a5cdc` |
| UP-02 S-FND-02 Observability Section | Foundation | S-FND-02 OD-SFND02-01: [observability] section planlandı. S-FND-04 AppConfig alanında optional section mapping (yoksa defaults). S-FND-02 JSON-only karar bu katmanın varsayılan davranışını (INI stdlib) etkilemez. | `d02f58ba99e57c66172828668a59305c4dae62ac` |
| UP-03 S-FND-03 Pytest Gates | Foundation | S-FND-04 production code (app/platform/config) için: F1/F2/F3/F4 hard-red testler S-FND-03 tarayıcısı çalışırken 0 finding üretmeli. F3 short/lev config field = 0 expected (leverage allowed=1, short false). F2: config key field names "allow_*" = allowlist (len <3 meaningful değil, C2 F2 rule uyumlu test) | `55fd13e5c794c748b5268bfd891d37968cf407b9` |
| UP-04 E-API MVP Surface | Platform | E-API 2 write endpoint kill-switch & emergency-stop — config içinde [safety] kill switch default state okunabilir (mapping optional). E-API NEW files 0 diff. | `80933f8a7feecfbcb63dc3da72b10f7f459baade` |

HARİÇ BAĞIMLILIK (EXTERNAL DEP DEFAULT): **YOK (INI/JSON STDLIB ONLY). PyYAML = OPTIONAL, OD-FND-04 KAPALI BY DEFAULT.** Eğer OD-FND-04 açılırsa PyYAML = tek 3rd-party dep; onaysız 0. Source-backed dep: PyYAML opsiyonelliği kaynaksız değil, OD altı.

## §5 — Downstream Consumers (Tüketen Hikâyeler)

| Tüketici Hikâye | Neden ConfigLayer/VersionConstants'a ihtiyacı var? | EPICS line |
|---|---|---|
| S-CON-01 Envelope + QualityFlags typed schemas | envelope contract_version / schema_version field → VersionConstants sabiti; symbol_namespace config; validation tolerances (gelecek OD) | L257 |
| S-CON-02 19 contracts | Decimal precision (config [platform_contract] decimal_precision = 8); limits snapshot (RiskEngine limits config section) | L271-283 |
| S-CON-03 CAP-1 Parity Test Infra | run_mode_default config alanı; parity test için env seçimi | L285-296 |
| S-RDH-01 Omur POC Replay Pipeline | replay_clock resolution config; data health thresholds (gelecek OD altında); adapter public url placeholder | L331-342 |
| S-FEA-01 Feature Engineering | lookback_window, indicator params defaults section | E-FEA (Epic 5) L160 |
| S-REG-01 Market Regime Detector | regime_model_weights path, regime confidence thresholds (gelecek OD) | Epic 6 L162 |
| S-STR-01 Trend/Momentum Strategy | strategy param defaults; regime compatibility mapping | Epic 7 L163 |
| S-RSK-01/02 Independent Risk Engine | limits section (position_max, leverage_margin_allowed_via_config = 1), kill_switch_enabled default | Epic 9 L164 |
| E-MDL 4 stories (Model Lifecycle/Registry) | artifact_path default storage prefix; model_registry db_namespace env prefix | Epic 13 L168 FR-036 |
| E-API MVP API Surface | observability section metrics_enabled, log_level default; write endpoint permission defaults | Epic 14 L169 |

## §6 — Contracts / Data Types

S-FND-04, dışa açık 4 tip sözleşme tanımlar (stdlib dataclasses, 0 pydantic):

### 6.1 `VersionConstants` frozen dataclass (single source of truth)
```python
# invariant: değerler runtime'da DEĞİŞMEZ (frozen=True)
# contract_version:  "1.0.0"  — CONTRACTS §1 envelope zorunlu
# app_version:       "0.1.0-mvp"
# schema_version:    1 — int, envelope şema revizyonu
# build_metadata:    "local-mvp" — CI varsa override OD (gelecek)
```

### 6.2 `EnvSafetyLocks` (S-FND-01 C2 kilidi doğrudan typed mapping)
```python
trading_permission_default: bool  # dev: false; stg/prod: ayrı (false default)
allow_api_keys: bool              # false (v1 PRD hard boundary)
max_leverage_allowed: int         # 1 (PRD leverage maks 1)
allow_short: bool                 # false (PRD spot-only short yok)
```
Validation invariant: `max_leverage_allowed > 1` veya `allow_short == True` veya `allow_api_keys == True` → `ConfigValidationError`. v1 MVP'de 3/3 = strict closed.

✔ RESOLVED (§21 MAJOR-1, Package A / D-01): dataclass alanı `EnvSafetyLocks.allow_api_keys` (`models.py` L17); INI option adı `allow_api_keys` (`validation.py` `parse_safety`) ve `exc.fields` adı da `allow_api_keys`. [HISTORICAL] Önceki as-built dataclass alanı `allow_external_creds` idi; normatif sözleşme (`allow_api_keys`) lehine hizalandı, gap KAPATILDI.

### 6.3 `AppConfig` (top-level typed config)
```python
env_name: Literal["dev", "test", "stg", "paper-prod"]  # AD-18 4 ortam
db_namespace: str
artifact_path: str
run_mode_default: Literal["replay", "paper"]
safety: EnvSafetyLocks
observability: Optional[ObservabilitySection]  # (S-FND-02 OD): log_level, metrics_enabled
platform_contract: PlatformContractSection  # decimal_precision: int = 8
extension_sections: dict[str, Any]  # downstream section register; tür downstream owner
```

### 6.4 `ConfigValidationError` (exception türü)
Custom exception. `fields: list[str]`, `reason: str`, `source_file: str`. Deterministik message sort.

Tüm dataclass'lar: JSON-serializable (json.dumps sort_keys=True + separators compact → SPEC §7 determinizm).

## §7 — Deterministic Behavior (Determinizm)

D-1 ConfigFactory.read_env("dev") → 10 kez ardışık → `json.dumps(result, sort_keys=True, separators=(",",":"))` SHA256[:12] AYNI.
D-2 VersionConstants 4 alanı: hard-coded source; her import AYNI.
D-3 YAML kapalıyken, PyYAML import denemesi → tam olarak RuntimeError message: `"PyYAML disabled by OD-FND-04. No YAML config parsed unless open decision resolved YAML=true."` (sabit metin, varyant yok).
D-4 ConfigParser preserve_invalid_values = False; keys order = ConfigParser default insertion order (sorted, 3.7+ dict ordered). Serileştirme sonrası sort_keys → stable.
D-5 ValidationError field list → sorted → message tuple len(set 10x) == 1.
D-6 Rastgele/çevre: `os.environ["CRYPTO_AI_ENV"]` HARİÇ okunmaz; no wall-clock timestamp; no uuid/random; no filesystem order (tek dosya okuma).

## §8 — Fail-Closed Behavior

FC-1 INI dosya bulunamazsa → `FileNotFoundError` config layer tarafından RAISE edilir (sessiz fallback defaults YOKTUR). Çünkü missing config = unsafe silent defaults.
FC-2 Zorunlu section `[env]` eksikse → `ConfigValidationError("Section [env] missing")`.
FC-3 Safety lock ihlali (örn max_leverage_allowed = 2) → `ConfigValidationError`, NEVTER "silently clamp =1". clamp ihlal record + fail.
FC-4 Type coerce başarısız → `ConfigValidationError` (sessiz fallback bool = false OLMAZ). **STRICT Boolean coercion (OD-04 / Package B / D-02):** bool alana **kabul edilen** girdiler = native `bool` (`True`/`False`) + kanonik literaller `true`/`false`/`1`/`0` (büyük/küçük harfe duyarsız; baştaki/sondaki whitespace trim edilir). **Reddedilen** girdiler = `yes`/`no`/`on`/`off`/`y`/`n`, açıkça verilen boş string, `None`, sayısal tipler (int/float) ve desteklenmeyen diğer token'lar. Eksik config alanının default kullanması, `coerce_bool`'a açıkça geçersiz girdi verilmesinden AYRI davranıştır. (Önceki `yes`/`y` kabul ifadesi STRICT sözleşme lehine ÇÖZÜLMÜŞTÜR.)
FC-5 PyYAML kapalıyken yaml_path çağırılır → RuntimeError (FC-3/FC-5 OD kilidi fail-closed).
FC-6 ConfigParser ConfigParser.MAX_INTERPOLATION_DEPTH exceeded (INI include patlaması) → exception RAISE, sessizce ignore OLMAZ.
FC-7 `extension_sections` downstream register hatası → ana config validasyonu HATA (sessizce extension skip OLMAZ).
FC-8 Frozen VersionConstants runtime mutate (setattr) → dataclass FrozenInstanceError.

## §9 — Security & Safety (F' Fences + invariants)

S-1 F2' credential string taraması: `app/platform/config/` içinde ANY hard-coded api_key / binance_api_key / secret_key value literal → 0. Config, credential DEĞİLDİR. Placeholder template key name varsa F2 tarayıcısında allowlist (finding yok). Placeholder VALUE: "MOCK_READONLY_ACCESS_ID_A" benzeri ise S-FND-01 C4 configler ile match; F2 finding yok.
S-2 F3 short/leverage config layer içinde: `max_leverage_allowed == 1` + allow_short=false varsayılan. Safety invariant ihlal FAIL-CLOSED FC-3.
S-3 F4 gerçek emir isimleri: ConfigModule içinde ANY send_real_order / place_order_on_exchange → 0. Config okuma, emir YOK.
S-4 F1 network: config layer `requests/httpx/aiohttp/websocket` import = 0. Sadece stdlib configparser/json (PyYAML = PERMANENTLY OFF CLOSED OD-FND-04-01). No network çağrısı.
S-5 All safety lockları false/clamped → validation error raise. Never silent; never default allow; operator görür.
S-6 Dynamic code: NO eval/exec/pickle/yaml.load(unsafe). PyYAML = CLOSED PERMANENTLY OFF (OD-FND-04-01). YAML parsing NEVER enabled in S-FND-04. Gelecek story C3 required to re-open YAML gate.

## §10 — Audit & Evidence

A-1 **Public audit API dönüş sözleşmesi (K-3 / Package C — NORMATİF HEDEF; ✔ AS-BUILT):** Varsayılan `read_env(env_name=None)` → `AppConfig` döndürür (AC-07 canonical; mevcut varsayılan davranış KORUNUR). Opt-in audit için `read_env(env_name=None, return_audit=True)` → `(cfg, records)` döndürür: `cfg: AppConfig`; `records: list[ConfigReadAuditRecord]` (`source_file`, `md5`, `valid_safety`, `correlation_id`). Kayıtlar config işleme sırasını izler; her çağrı BAĞIMSIZ bir public liste döndürür (private `_audit_trail`'ı veya başka çağrı sonucunu etkilemez); validation hatasında kısmi sonuç DÖNDÜRÜLMEZ; public kayıtlara ham credential/secret EKLENMEZ. Yeni parametre `return_audit: bool = False`.
  ✔ AS-BUILT (Package C / K-3 — MAJOR-3 KAPANDI): `loader.py` L99-173 `read_env(env_name=None, return_audit=False) -> Union[AppConfig, tuple[AppConfig, list[ConfigReadAuditRecord]]]`. `return_audit=False` → `AppConfig` (legacy korunur); `return_audit=True` → `copy.deepcopy` ile bağımsız public liste `(cfg, records)`. `ConfigReadAuditRecord` alanları: `source_file, md5, valid_safety, correlation_id`. Test kanıtı: `tests/foundation_sfnd04/test_sfnd04_determinism_audit.py` (public sözleşme + mutability/determinism/hata/hassas-veri/legacy testleri); `tests/foundation_sfnd04/` → 90 passed, exit 0. Legacy private `_audit_trail` davranışı korunur.
A-2 Safety lock ihlal → audit record includes violated field + raw value repr maskeli (sayısal ise number length, credential ise YOK).
  ⚠ AS-BUILT (§21 MINOR-7, IMPLEMENTATION GAP): ihlalde violated field listesi `ConfigValidationError.fields` içinde taşınır (`validation.py` `failed` listesi); `ConfigReadAuditRecord` başarılı read'de üretilir ve violated field/maskeli raw value ALANI İÇERMEZ. Gereksinim korunur, karşılanmadı → gap.
A-3 VersionConstants her build → `sha256(VersionConstants json)[:8]` fingerprint; testlerde hard-code beklenen değer ile karşılaştırılabilir.
  ⚠ AS-BUILT (§21 MINOR-7, IMPLEMENTATION GAP): production'da `VersionConstants` fingerprint fonksiyonu YOK. Test helper `tests/foundation_sfnd04/_helpers.py: sha_json()` sha256[:12] prefix üretir; bu sadece test tarafıdır ve [:8] değil [:12]'dir. Gereksinim korunur, karşılanmadı → gap.
A-4 4 env INI dosyaları MD5 hash: S-FND-01 commit ile aynıysa (EX-01 modify edilmediyse) preservation PASS; farklıysa audit WARNING.
  ⚠ AS-BUILT (§21 MINOR-7, IMPLEMENTATION GAP): `read_env` her okumada md5 hesaplayıp `ConfigReadAuditRecord.md5` içine koyar (32-hex), ANCAK S-FND-01 baseline commit ile otomatik karşılaştırma / WARNING üretimi YOKTUR. Gereksinim korunur, karşılanmadı → gap.

## §11 — Non-Goals (NG)

NG-1 Pydantic, pydantic-settings, msgspec, attrs, tomllib 3rd-party library EKLEMEZ — stdlib dataclasses + ConfigParser.
NG-2 Migration script 4 INI → 4 YAML conversion YAZMAZ. OD resolve → yeni hikâye.
NG-3 Canlı config hot-reload / file watcher / SIGHUP reload UYGULAMAZ. Başlangıçta bir kez oku.
NG-4 Environment variable OVERRIDE önceliği mapping ini > env var: implemente ETMEZ. Gelecek (C-phase) story; MVP INI dosyası öncelikli, env var seçimi sadece env_name.
NG-5 Dashboard config WRITE endpoint (Admin UI): YOK. E-API scope.
NG-6 AES Encrypted config / KMS / Vault credential secrets: YOK. PRD §5.7 future secrets manager; v1 YOK (C2: allow_api_keys=false).
NG-7 14 Epic'in HER bir section field default value tanımlama: SADECE FND sahipliği 4 section + extension hook. Diğerleri ilgili hikâyeye aittir.

## §12 — Hard-Red (HR) 8 / 8 Project-Wide

HR-1 0 Existing Modify (K0): Existing 4x config INI → EX list boş ise 0 modify. S-FND-01/02/03 app/tests → 0 diff.
HR-2 No Live Network NEW module: 0 network import.
HR-3 No Credentials in Config: config layer NEVER write/return credential values. Placeholder "MOCK_" → allowlist.
HR-4 No Registry Mutation: 0 governance/registry import.
HR-5 Stdlib Default: PyYAML KAPALI; açılırsa tek 3p dep, onaysız 0. Pydantic=0.
HR-6 No Unsafe: NO eval/exec/pickle/subprocess shell=True. YAML safe_load only.
HR-7 Completed-Story 0 Diff: 01/02/03 + E-API commit file count unchanged + 0 byte diff.
HR-8 AD-7 Mutation Ownership: config tek owner app/platform/config; başka module overwrite YOK (import only).

(Detaylı per-HR kanıt / audit ölçümü: companion `hard-red.md`.)

## §13 — Acceptance Criteria (24 AC, executable)

(Detaylı liste ve her AC için test bağlama: companion `acceptance-criteria.md`.)

Özet:
- 24 AC = 6 version constants (6 AC) + 6 typed mapping (6 AC) + 6 safety validation fail-closed (6 AC) + 6 PyYAML gate / determinism / audit / K0 (6 AC).

## §14 — Definition of Done (DoD)

(Detaylı kriter: companion `dod.md`.)

1. `app/platform/config/` NEW dosyalar: `__init__.py`, `constants.py`, `loader.py`, `models.py`, `validation.py`, `errors.py` → 6 file.
2. S-FND-04 test suite `tests/foundation_sfnd04/` 7 dosya (4 test modülü + `__init__.py` + `conftest.py` + `_helpers.py`), 0 FAIL. ⚠ AS-BUILT (§21 MINOR-2, Package C / K-3 sonrası): 7 dosya mevcut; 4 test modülünde toplam 51 test fonksiyonu → pytest 90 test toplar (Package A öncesi 42; Package B validation dosyasına 36 STRICT coercion testi ekledi → 79; Package C determinism/audit dosyasına 11 public audit API testi ekledi → 90).
3. Regression: S-FND-01 (72/74, 2 pre-existing fail unchanged), S-FND-02 (144/144), S-FND-03 (85/85), E-API (API smoke) → 0 NEW failing.
4. K0 HR-1: `git diff HEAD -- configs app/platform tests/ pyproject.toml` → existing tracked files: 0 diff. (SADECE new file'lar allowed.)
5. K0 HR-5: pyproject.toml dependencies = EMPTY []. PyYAML = CLOSED PERMANENTLY OFF (OD-FND-04-01). 3p dep EKLENMEZ. EX-02 DROPPED.
6. Determinism test: 6D ×10 → len(set) = 1.
7. FC1..8 fail-closed 8/8 test PASS.
8. SFND03 F1'..F4' PR gate tarayıcı: S-FND-04 NEW app/config files → 0 BLOCKER.

## §15 — Test Plan (TP-01..TP-06)

(Companion: `test-plan.md`. TP başlıkları: TP-01 Version Constants, TP-02 Env INI → Typed, TP-03 Validation Fail-Closed ×6, TP-04 PyYAML Gate Assertion (KAPALI → RuntimeError exact message), TP-05 Determinism 6D×10, TP-06 Audit+Regression.)

## §16 — Expected File Changes

(Companion: `expected-file-changes.md`. Authoritative sayım: TOPLAM 13 DOSYA (6 prod NEW under `app/platform/config/` + 7 test NEW under `tests/foundation_sfnd04/`). Existing modification: KALICI 0 (EXCEPTION LIST 2 items → 2/2 PERMANENTLY DROPPED via CLOSED CANONICAL OD-01/02).)

## §17 — Open Decisions (4 OD TOTAL, 3 CLOSED CANONICAL + 1 TRULY OPEN, 0 silent resolved)

(Companion: `open-decisions.md`. 3 OD CLOSED (OD-01/02 kalıcı canonical; OD-04 STRICT Package B / D-02 ile uygulandı); 1 OD TRULY OPEN (OD-03) MINOR.)

**OD-FND-04-01 PyYAML Etkinleştirilsin mi? (CLOSED = PERMANENTLY OFF)** — 5 kaynak evidence ile kalıcı kapandı. PyYAML 3.p dep S-FND-04'e EKLENMEZ. EX-02 = KALICI DROPPED. YAML config ihtiyacı → YENİ C3 PHASE HİKÂYE.
**OD-FND-04-02 4 env INI dosyalarına section append EX-01? (CLOSED = PERMANENTLY DROPPED 0 modify)** — 4 kaynak evidence ile kalıcı kapandı. Section yoksa AppConfig defaults düşer. EX-01 = KALICI DROPPED. Gelecek override → YENİ Config Overlay v2 hikâyesi.
OD-FND-04-03 ObservabilitySection S-FND-02 ile mapping (log_level mapping env→level enum): Default: DEV=DEBUG / TEST=DEBUG / STG=WARN / PAPER-PROD=INFO — S-FND-02 OD-SFND02-01 ile aynı. S-FND-04 copy etmez; referans. (TRULY OPEN MINOR.)
OD-FND-04-04 TypeCoerce strict mi veya lenient mi? **CLOSED = STRICT (Package B / D-02 ile UYGULANDI).** Kabul: native `bool` + `true`/`false`/`1`/`0` (case-insensitive, whitespace trim). Ret: `yes`/`no`/`on`/`off`/`y`/`n`, boş string, `None`, sayısal tipler → fail-closed.
  ✔ RESOLVED (§21 MAJOR-2): `coerce_bool` STRICT kabul kümesine uyarlandı (`app/platform/config/validation.py`); izin `EX-K0-SFND04-D02`. Eski LENIENT davranış ve `yes`/`on` kabulü kaldırıldı. [HISTORICAL] Önceki AS-BUILT notu: `coerce_bool` LENIENT idi (`("true","1","yes","on")→True`, `("false","0","no","off","")→False`).

## §18 — Source Gaps (8 MADDELİ KANIT: NO FABRICATION)

(Companion: `source-gaps.md`. Her gap → "explicitly deferred / open / not this story". 8 kaynak eksiği ZORUNLULUĞA DÖNÜŞTÜRÜLMEDİ.)

## §19 — Current vs Future Boundary (Lean Kernel)

(Companion: `current-vs-future-boundary.md`. Şu an = minimal typed wrapper + validation + version constants. Gelecek = hot reload / vault / migration / pydantic upgrade / multi-config merge / CI env vars — all future, none mandatory now.)

## §20 — Architecture Traceability

(Companion: `architecture-traceability.md`. Doğrudan bağlanan (12): AD-1 / AD-4 / AD-5 / AD-7 / AD-15 / AD-18 / AD-19 / AD-20 / AD-22 / AD-23 / AD-24 / AD-25. Explicit DEFERRED (5, bu hikâyede kapsam dışı): AD-6 (E-PLN) / AD-8 (E-REG) / AD-13 (E-PTF) / AD-14 (E-MDL) / AD-16 (E-API). Unrelated/no-touch (8): AD-2/3/9/10/11/12/17/21. Toplam 25. ⚠ AS-BUILT (§21 MINOR-4): planlanan kısa liste AD-13'ü "mapping" gibi gösteriyordu; traceability `AD-13`'ü DEFERRED sayar → §20 ile traceability arasındaki bu uyuşmazlık düzeltildi.

## §21 — AS-BUILT RECONCILIATION (2026-10-25, evidence-first, no Git mutations)

Bu bölüm, bağımsız denetimde saptanan 4 MAJOR + 8 MINOR bulgunun kanıta dayalı ele alınışını kaydeder. Normatif sözleşme maddeleri KORUNDU; yalnızca açıkça kanıtlanan doküman hataları düzeltildi, gereksinim↔implementasyon farkları gizlenmeden gap olarak kaydedildi.

Sınıflar: **DOCS INCORRECT** (doküman kaynağa aykırı, düzeltildi) / **AS-BUILT DRIFT** (kod sözleşmeden farklı, iki taraf da kaydedildi) / **IMPLEMENTATION GAP** (gereksinim karşılanmadı, kod değiştirilmedi) / **RESOLVED BY TRACEABILITY** / **SCOPE-OWNER DECISION REQUIRED**.

**Durum (Package A / D-01 + Package B / D-02 + Package C / K-3 design gate + Package C implementation sonrası):** MAJOR-1 RESOLVED (Package A / D-01), MAJOR-2 RESOLVED (Package B / D-02). MAJOR-3 **normatif sözleşmesi K-3 ile RESOLVED** ve **as-built KOD gap'i Package C ile KAPANDI** (public audit API + testler). MINOR-7 KALIR AÇIK (Package D). Kapatılmamış kod gap'i kapatılmış gibi gösterilmez.

### MAJOR
| ID | Bulgu | Sınıf | Karar |
|---|---|---|---|
| MAJOR-1 | Dataclass alan adı: sözleşme `allow_api_keys`, as-built `allow_external_creds` | ✔ RESOLVED (Package A / D-01) | Dataclass attribute, INI option ve `exc.fields` `allow_api_keys` ile hizalandı; eski `allow_external_creds` KALDIRILDI. İzin: `EX-K0-SFND04-D01`. |
| MAJOR-2 | OD-04 STRICT default ↔ as-built LENIENT `coerce_bool` | ✔ RESOLVED (Package B / D-02) | Scope owner Seçenek (A) = STRICT onayladı; `coerce_bool` STRICT kabul kümesine uyarlandı, LENIENT davranış ve `yes`/`on` kabulü kaldırıldı. İzin: `EX-K0-SFND04-D02`. OD-04 RESOLVED kapandı. |
| MAJOR-3 | Public `read_env(return_audit=True)` audit dönüş iddiası (A-1/AC-23/T23/CAP-09) | ✔ RESOLVED (Package C / K-3 implementation) | Normatif dönüş sözleşmesi **K-3** ile RESOLVED: varsayılan `read_env(env)` → `AppConfig`; `read_env(env, return_audit=True)` → `(cfg, records)`. As-built (Package C): `loader.py` `read_env(env_name=None, return_audit=False)`; `True` durumunda `copy.deepcopy` ile bağımsız public liste döner. Test kanıtı: `test_sfnd04_determinism_audit.py`; grup → 90 passed, exit 0. İzin: `EX-K0-SFND04-D03`. Legacy private `_audit_trail` korunur. |
| MAJOR-4 | Reuse-map `coerce_strict_bool` / `coerce_strict_int` import yolu | DOCS INCORRECT | Birebir doğrulanan gerçek API `coerce_bool` / `coerce_int` ile hizalandı (`validation.py`). Bu isim düzeltmesi davranış sözleşmesini ÇÖZMEZ (MAJOR-2 ayrı ve ayrıca Package B / D-02 ile RESOLVED). |

### MINOR
| ID | Bulgu | Sınıf | Karar |
|---|---|---|---|
| MINOR-1 | Test sayıları | DOCS INCORRECT | As-built (Package C / K-3 sonrası) 4 test modülü / 51 test fonksiyonu / 90 toplanan test. (Tarihsel: Package A öncesi 42 toplanan; Package B validation dosyasına 36 STRICT coercion testi ekledi → 79; Package C determinism/audit dosyasına 11 public audit API testi ekledi → 90.) |
| MINOR-2 | Test dosya sayısı (§14 vs DoD-2) | DOCS INCORRECT | 7 dosya (4 test + __init__ + conftest + _helpers). |
| MINOR-3 | Marker/test adı iddiaları (contract/replay/failure_injection; TestYamlGate) | DOCS INCORRECT | As-built yalnız `@pytest.mark.parametrize`; özel marker ve sınıf YOK. |
| MINOR-4 | §20 AD listesi | DOCS INCORRECT | Traceability ile hizalandı (12 direct + 5 deferred + 8 unrelated). |
| MINOR-5 | E-API yolu + S-FND-02 dosya sayısı | DOCS INCORRECT | As-built `app/platform/api/` (15 dosya) + `tests/api/` (5); observability 10 dosya. |
| MINOR-6 | `config.paper-prod.ini` ↔ `config.prod.ini` | DOCS INCORRECT | As-built dosya `config.prod.ini`; loader alias `paper-prod→prod`. |
| MINOR-7 | A-2/A-3/A-4 | IMPLEMENTATION GAP | Gereksinim korundu, as-built karşılamıyor (§10 notları). |
| MINOR-8 | DoD-6 "6D×10 = 60 subtest" | DOCS INCORRECT | `read_env` determinism = 4 env × inner 10 = 40 iterasyon; 6 boyut ayrı testlerle kapsanır. |

### Kalan açık konular
- **RESOLVED:** MAJOR-1 (dataclass alan adı → Package A / D-01), MAJOR-2 (STRICT coercion / OD-04 → Package B / D-02), MAJOR-3 normatif dönüş sözleşmesi (→ Package C / K-3 design gate) **ve MAJOR-3 as-built kod gap'i** (→ Package C implementation, public audit API + testler).
- **IMPLEMENTATION GAP (KALIR AÇIK):** MINOR-7 (A-2/A-3/A-4 → Package D). Bu gap kapatılmış GİBİ GÖSTERİLMEZ.
- **Kalan SCOPE-OWNER DECISION REQUIRED:** yok (MAJOR-1, MAJOR-2 ve MAJOR-3 kapandı; K-3 onaylı).
- MINOR-7 yalnızca doküman düzenlemesiyle kapatılamaz → COMMIT READY etkilenir (bkz. implementation-readiness.md).

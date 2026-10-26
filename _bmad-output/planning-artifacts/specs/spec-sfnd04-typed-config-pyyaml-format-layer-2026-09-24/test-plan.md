# Test Plan — S-FND-04 (TP-01..06)

CANONICAL: 6 TP (Test Plan Package). Each TP maps to AC rows. Total 24 AC → 24 tests minimum. Parametrize TP-05 determinism = 6D × 10 = 60 parametrize iterations (1 unique assertion, count toward unique test functions = 1).
⚠ AS-BUILT (2026-10-25 §21 MINOR-1/3/8; 2026-10-26 Package B / D-02 + Package C / K-3 güncellemesi): As-built test paketi bu planlanan tabloyla birebir eşleşmez. Gerçek envanter (Package C / K-3 sonrası): 4 test modülü, 51 test fonksiyonu, pytest 90 test toplar (Package B sonrası 79 idi). Özel marker (`contract`/`replay`/`failure_injection`) KULLANILMAZ; yalnız `@pytest.mark.parametrize`. TP-05 determinism as-built: `read_env` 4 env × inner 10 = 40 iterasyon (6×10=60 değil). Package B / D-02, `test_sfnd04_validation.py` içine STRICT Boolean coercion kabul/ret testleri ekledi. Package C / K-3, `test_sfnd04_determinism_audit.py` içine 11 public audit API testi (T23) ekledi. Aşağıdaki satırlar PLANNED'dır; as-built farkları ilgili satırlarda `⚠` ile işaretlidir.

## TP-01 — Version Constants Frozen (AC-01..06)
LOCATION: `tests/foundation_sfnd04/test_sfnd04_version_constants.py`
SAYIM: 6 explicit tests. Marker: `contract` + `foundation_sfnd04`. ⚠ AS-BUILT: 6 test fonksiyonu; özel marker YOK (tüm dosya markerless).

| T-Id | Test Name (Snake) | Assertion | AC Map |
|---|---|---|---|
| T01 | test_version_constants_import_public_api | `from app.platform.config import VersionConstants` raises nothing. `dataclasses.is_dataclass(VersionConstants) is True`. | AC-01 |
| T02 | test_contract_version_exact_1_0_0 | `assert VersionConstants.contract_version == "1.0.0"`. Semantic format: regex `^\\d+\\.\\d+\\.\\d+$`. | AC-02 |
| T03 | test_app_version_exact_mvp | `assert VersionConstants.app_version == "0.1.0-mvp"`. Exact literal, not substring. | AC-03 |
| T04 | test_schema_version_exact_int_1 | `assert VersionConstants.schema_version == 1`. Type: `type(VersionConstants.schema_version) is int`. | AC-04 |
| T05 | test_build_metadata_exact_local_mvp | `assert VersionConstants.build_metadata == "local-mvp"`. | AC-05 |
| T06 | test_version_constants_frozen_immutable | Attempt `VersionConstants.contract_version = "2.0.0"` → raises `FrozenInstanceError`. Dataclass field frozen=True. | AC-06 / FC-8 |

## TP-02 — Typed Config 4 Env Mapping (AC-07..12)
LOCATION: `tests/foundation_sfnd04/test_sfnd04_config_typed.py`
SAYIM: 6 tests. Marker: `contract`. ⚠ AS-BUILT: 7 test fonksiyonu (3'ü parametrize) → 17 toplanan test (Package A / D-01 sonrası); özel marker YOK.

| T-Id | Test Name | Assertion | AC Map |
|---|---|---|---|
| T07 | test_read_env_dev_returns_typed_appconfig | `cfg = ConfigFactory.read_env("dev")`. `cfg.env_name == "dev"`, `cfg.safety.max_leverage_allowed == 1`, `cfg.safety.allow_short is False`, `cfg.safety.allow_api_keys is False`. Type check `isinstance(cfg, AppConfig)`. ✔ RESOLVED (§21 MAJOR-1, Package A / D-01): dataclass attribute artık `cfg.safety.allow_api_keys`; gerçek test (`test_sfnd04_read_env_dev_returns_appconfig`) `max_leverage_allowed` ve `allow_short` doğrular. | AC-07 / §6.3 |
| T08 | test_4_env_db_namespace_distinct_not_empty | 4 calls `["dev","test","stg","paper-prod"]` each `db_namespace`. Assert: `len(set([c.db_namespace for c in cfgs])) == 4` AND all `len(ns) > 0`. | AC-08 / AD-18 |
| T09 | test_run_mode_default_mapping_env_specific | `dev.run_mode == "replay"`, `test.run_mode == "replay"`, `stg.run_mode == "paper"`, `paper-prod.run_mode == "paper"`. (Source: S-FND-01 4env defaults.) | AC-09 |
| T10 | test_default_sections_not_none | `cfg.safety is not None`, `cfg.platform_contract is not None`, `cfg.platform_contract.decimal_precision == 8`. | AC-10 / §6.3 |
| T11 | test_observability_section_defaults_when_missing | Use tmp INI with NO [observability] section. Assert: `cfg.observability.log_level` falls to env-mapped default (dev → DEBUG, test → DEBUG, stg → WARN, paper-prod → INFO). | AC-11 / OD-03 |
| T12 | test_unknown_env_raises_value_error | `ConfigFactory.read_env("production_real_live")` → raises `ValueError`. Msg contains: "Unknown env. Allowed: dev/test/stg/paper-prod". | AC-12 / §6.3 Literal 4 |

## TP-03 — Validation Fail-Closed 8 Tests (AC-13..18)
LOCATION: `tests/foundation_sfnd04/test_sfnd04_validation.py`
SAYIM: 6 validation + 2 missing = 8 tests. Marker: `failure_injection`. ⚠ AS-BUILT (Package B / D-02 sonrası): bu dosya (`test_sfnd04_validation.py`) TP-03+TP-04 toplam 19 test fonksiyonu → 46 toplanan test içerir (Package B STRICT coercion testleri dahil); özel marker YOK.

| T-Id | Test Name | Injection (tmp INI) | Assertion | AC Map |
|---|---|---|---|---|
| T13 | test_leverage_gt_1_raises_validation_error | `max_leverage_allowed = 2` under [env] | Raises `ConfigValidationError`. "max_leverage_allowed" in str(e). No silent clamp. | AC-13 / FC-3 |
| T14 | test_allow_short_true_raises_validation_error | `allow_short = true` case-insensitive INI | Raises `ConfigValidationError`. "allow_short" in str(e). | AC-14 / FC-3 |
| T15 | test_allow_api_keys_true_raises_validation_error | `allow_api_keys = true` | Raises. "allow_api_keys" in str(e). | AC-15 / FC-3 |
| T16 | test_trading_permission_true_raises_validation_error | `trading_permission_default = true` | Raises. "trading_permission_default" in str(e). | AC-16 / FC-3 |
| T17 | test_missing_env_section_raises_validation_error | Remove `[env]` header entirely from tmp INI | Raises `ConfigValidationError("Section [env] missing")`. Exact substring. No auto-create defaults. | AC-17 / FC-2 |
| T18 | test_missing_ini_file_raises_file_not_found_error | Pass non-existent path via env override fixture | Raises `FileNotFoundError`. No silent `{}` fallback. | AC-18 / FC-1 |
| T13b | test_type_coerce_int_fail_raises | `max_leverage_allowed = not_an_int` → `ConfigValidationError` "type coerce failed" | §8 FC-4 |
| T14b | test_type_coerce_bool_fail_raises | `allow_short = yep` → `ConfigValidationError` (strict coerce, OD-04: only true/false/1/0 allowed) | §8 FC-4 / OD-04 |

✔ RESOLVED (Package B / D-02): As-built `coerce_bool` artık STRICT'tir. Kabul: native `bool` + `true`/`false`/`1`/`0` (case-insensitive, whitespace trim). Ret: `yes`/`no`/`on`/`off`/`y`/`n`, boş string, `None`, sayısal tipler → `ConfigValidationError` ("Boolean coerce failed ... (strict bool only: true/false/1/0)"). `test_sfnd04_validation.py` içinde STRICT kabul/ret testleri eklendi: `test_sfnd04_coerce_bool_strict_accepts_canonical_literals`, `..._accepts_native_bool`, `..._rejects_legacy_tokens`, `..._rejects_empty_and_none`, `..._rejects_unsupported_types`, `..._rejection_via_read_env`, `..._preserves_allow_api_keys_field`, `..._observability_metrics_rejected`, `test_sfnd04_missing_safety_section_uses_defaults` (default ↔ açıkça geçersiz ayrımı). T13b adlı ayrı bir int-coerce test fonksiyonu hâlâ YOKTUR (MINOR-3: `coerce_int` ayrı testle kapsanmaz). [HISTORICAL] Önceki AS-BUILT notu: `coerce_bool` LENIENT idi (`true/1/yes/on` → True; `false/0/no/off/""` → False) ve `yes`/`on` kabul EDİLİYORDU — bu OD-04 STRICT default'una aykırıydı (MAJOR-2, artık kapatıldı).

## TP-04 — YAML Optional Gate (AC-19..21 = 3 Tests)
LOCATION: Same `test_sfnd04_validation.py` (TP-04 same file, separate test class `TestYamlGate`).
SAYIM: 3 tests. 2 with yaml OFF (default), 1 with yaml ON via monkeypatch. ⚠ AS-BUILT (§21 MINOR-3): `TestYamlGate` sınıfı YOK; 3 yaml testi modül düzeyinde fonksiyon olarak aynı dosyada (`test_sfnd04_yaml_permanently_off_runtime_error`, `test_sfnd04_yaml_import_wrap_runtimeerror`, `test_sfnd04_yaml_gate_defense_indepth_safe_load`).

| T-Id | Test Name | Setup | Assertion | AC Map |
|---|---|---|---|---|
| T19 | test_yaml_disabled_default_runtimeerror_exact_msg | Default (no fixture patch). Call `ConfigFactory.try_yaml("any.yml")`. | RuntimeError EXACT message = `"PyYAML disabled by OD-FND-04. No YAML config parsed unless open decision resolved YAML=true."`. String equality `==` not `in`. | AC-19 / D-3 / FC-5 |
| T20 | test_yaml_disabled_no_silent_ini_fallback | Default off. Call yaml path attempt → RuntimeError RAISED. NOT returns INI silently. | `pytest.raises(RuntimeError)` NOT wrap catch → no fallback AppConfig returned. | AC-20 / FC-5 |
| T21 | test_yaml_enabled_uses_safe_load_only | Fixture: `monkeypatch.setattr(app.platform.config.loader, "_YAML_ENABLED", True)`. Mock `yaml.safe_load` return dict. Also mock `yaml.load` → callable NEVER. | Assert `yaml.safe_load` called 1x. `yaml.load` called 0x. If yaml.load found called → FAIL (unsafe yaml). | AC-21 / S-6 / HR-6 |

## TP-05 — Determinism 6D × 10 Parametrize (AC-22)
LOCATION: `tests/foundation_sfnd04/test_sfnd04_determinism_audit.py`
SAYIM: 1 parametrize test. Iteration count 10 (min). Marker: `replay`. ⚠ AS-BUILT (§21 MINOR-8): as-built `test_sfnd04_determinism_read_env_10x` 4 env üzerinden parametrize edilir; her run içinde inner 10-loop vardır → 40 iterasyon. `replay` marker YOK.

| T-Id | Test Name | Assertion | AC Map |
|---|---|---|---|
| T22 | test_determinism_read_env_dev_10x_same_sha | `results = [sha_json(ConfigFactory.read_env("dev")) for _ in range(10)]`. `assert len(set(results)) == 1`. (sha_json = json.dumps sort_keys + separators compact → sha256[:12].) → D-1 / D-2 / D-4 / D-5 / D-6 + 10x required. ⚠ AS-BUILT: aynı mantık 4 env için parametrize; `_audit_trail` flat-dict'ten çıkarılır. | AC-22 / §7 D1..6 |

EXPLICIT DETERMINISM SUB-ASSERTIONS (all implicitly covered via 10x same sha but documented for audit):
- D-1: 10x same → passes (main assertion).
- D-2: VersionConstants 4 fields hard-coded → sha varies NOT across imports → test imports twice.
- D-3: YAML OFF error message literal string equality → TP-04 T19 separate.
- D-4: `ConfigParser` keys order + `sort_keys` → stable.
- D-5: ValidationError `sorted(fields)` → message deterministic (10x same field list → same str).
- D-6: No `time.time()`, no `uuid.uuid4()`, no `os.listdir()` order variance. Test: `disallow_imports(["time", "uuid"], app.platform.config)` (via _helpers import scanner).

## TP-06 — Audit + Regression Smoke (AC-23, AC-24)
LOCATION: Same `test_sfnd04_determinism_audit.py` class `TestAuditRegression`.
SAYIM: 2 tests.

| T-Id | Test Name | Assertion | AC Map |
|---|---|---|---|
| T23 | test_audit_record_valid_safety_true | EXACT tuple: `cfg, records = ConfigFactory.read_env("dev", return_audit=True)` — `cfg` `AppConfig`; `records` `list[ConfigReadAuditRecord]`. `len(records) >= 1`. `records[-1].source_file` ends with `configs/config.dev.ini`. `records[-1].valid_safety is True`. **Kayıt sırası:** kayıtlar config işleme sırasını izler ve aynı girdi için deterministiktir (nondeterministik sıralama YOK). **Mutability/sahiplik:** dönen `records` listesi ve içindeki mutable kayıtlar değiştirildiğinde private `_audit_trail` durumu ve başka bir `read_env(..., return_audit=True)` çağrısının sonucu DEĞİŞMEZ; her audit çağrısı bağımsız bir public liste döndürür. **Hata:** (`return_audit=True` dahil) config validation başarısızsa mevcut validation exception yükseltilir; kısmi `(cfg, records)` DÖNDÜRÜLMEZ. **Hassas veri:** public kayıtlara ham credential/secret/hassas config değeri EKLENMEZ (yalnız `source_file`/`md5`/`valid_safety`/`correlation_id`). ✔ AS-BUILT (Package C / K-3 — MAJOR-3 KAPANDI): `read_env(env_name=None, return_audit=False)` uygulandı; `return_audit=True` → `copy.deepcopy` ile bağımsız public liste. Test kanıtı: `test_sfnd04_determinism_audit.py` (exact tuple, tipler, şema, mutability izolasyonu, 10x determinism, çağrı-izolasyonu, hata+kısmi-tuple-yok, hassas-veri, legacy default); grup → 90 passed, exit 0. Legacy `test_sfnd04_audit_record_list_returned` (private `_audit_trail`) KORUNUR. | AC-23 / §10 A-1 A-4 / K-3 |
| T24 | test_regression_imports_no_network_creds | Import scanner helper: count_network_imports("app.platform.config") → 0. count_credential_literals("app/platform/config/") → 0. Helper scans AST (S-FND-03 F4/F2 pattern). | AC-24 / §9 S-1 S-4 FENCE |

## Total Test Count Summary (Audit phase cross-check)

PLANNED (bu dokümandaki tablolar):
- TP-01 → 6 tests
- TP-02 → 6 tests
- TP-03 → 8 tests
- TP-04 → 3 tests
- TP-05 → 1 parametrize (10 runs but 1 unique test function)
- TP-06 → 2 tests
- PLANNED TOPLAM: 26 unique test functions (AC says 24 — extra 2 = FC-4 type coerce T13b/T14b explicit. Non-negotiable: HR safety.)

⚠ AS-BUILT (2026-10-25 §21 MINOR-1/2/8; 2026-10-26 Package A/B/C güncellemesi — gerçek envanter):
- Modül/dosya: 4 test modülü + 3 destek dosyası (`__init__.py`, `conftest.py`, `_helpers.py`) = 7 dosya.
- Test fonksiyonu: **51 toplam** → version_constants 6 + config_typed 8 + validation 19 + determinism_audit 18.
- pytest toplanan test (Package C / K-3 sonrası): **90** (config_typed 17, determinism_audit 21, version_constants 6, validation 46). (Tarihsel: Package B / D-02 sonrası 79 idi.)
- Özel marker (`contract`/`replay`/`failure_injection`) KULLANILMAZ; yalnız `@pytest.mark.parametrize` (config_typed 3 + determinism_audit 1 + validation 5).
- Determinism as-built: `read_env` 4 env × inner 10 = 40 iterasyon; ayrıca `version_constants` 10x ve `validation fields` 10x döngüleri. `6D×10=60` tek bir parametrize DEĞİLDİR.
- Test toplama kanıtı (bu doküman turunda `--collect-only` ile doğrulandı): `pytest -p no:cacheprovider tests/foundation_sfnd04/ --collect-only -q` → 90 tests collected; alt gruplar: version_constants 6, config_typed 17, validation 46, determinism_audit 21. Önceki taze çalıştırma kanıtı (90 passed, exit 0) Package C / K-3 turunda raporlandı.

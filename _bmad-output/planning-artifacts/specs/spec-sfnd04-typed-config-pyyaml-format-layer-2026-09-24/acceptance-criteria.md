# Acceptance Criteria — S-FND-04 (24 AC executable)

CANONICAL SAYIM: **24 AC.** Audit aşamasında "24/24 executable PASS" koşulu zorunlu.
K0: HİÇBİR existing file modification (EX list boş ise; EX list varsa sadece izin verilen).

| AC | Başlık (Pass When = TRUE) | Kaynak Bağlama | Ölçüm Testi (TP) |
|---|---|---|---|
| AC-01 | `from app.platform.config import VersionConstants` import SUCCESS, ImportError YOK. Module path matches AD-1 `app/platform/` | SPEC §6.1, §3.1 | TP-01 T01 |
| AC-02 | `VersionConstants.contract_version == "1.0.0"` EXACT (NFR-019 / CONTRACTS L1 envelope zorunlu). LEN 5 chars + semantic MAJOR.MINOR.PATCH format | SPEC §2 M-1, EPICS L185 explicit | TP-01 T02 |
| AC-03 | `VersionConstants.app_version == "0.1.0-mvp"` EXACT. SPEC ile contract. | SPEC §6.1 | TP-01 T03 |
| AC-04 | `VersionConstants.schema_version == 1` EXACT. int tür. | SPEC §6.1 | TP-01 T04 |
| AC-05 | `VersionConstants.build_metadata == "local-mvp"` EXACT. | SPEC §6.1 | TP-01 T05 |
| AC-06 | `dataclasses.is_dataclass(VersionConstants)` AND `frozen=True` → denemek `VersionConstants.contract_version="2.0"` → FrozenInstanceError. | SPEC §8 FC-8 | TP-01 T06 |
| AC-07 | `ConfigFactory.read_env("dev")` → **varsayılan (return_audit=False)** çağrıda AppConfig döner, `env_name == "dev"`, `safety.max_leverage_allowed == 1`, `safety.allow_short == False`. (DEFAULT return canonical kabul kriteri — K-3; audit satırı AC-23.) ✔ AS-BUILT (Package C): default `read_env(env)` → `AppConfig` döndürür; hiçbir çağrı yeni API eklendi diye tuple almaz. | SPEC §3.1 / §6.2/6.3, S-FND-01 C2 | TP-02 T07 |
| AC-08 | 4 env için (`dev`,`test`,`stg`,`paper-prod`) → her biri için `db_namespace` alanı FARKLI string (AD-18 env ayrımı, boş string yok) | SPEC §4 UP-01 / AD-18 | TP-02 T08 |
| AC-09 | `run_mode_default` 4 env için: dev=replay, test=replay, stg=paper, paper-prod=paper (mapping; source: S-FND-01 env config vars). | SPEC §6.3 / S-FND-01 | TP-02 T09 |
| AC-10 | AppConfig içinde `safety` (EnvSafetyLocks) ve `platform_contract` (decimal_precision=8) alanları mevcut (None değil). | SPEC §6.3 | TP-02 T10 |
| AC-11 | `observability` alanı: mevcut INI'de section YOKSA → default değerleri (log_level mapping env→DEBUG/DEBUG/WARN/INFO) ile düşer (none YOK). | SPEC §17 OD-03 default, UP-02 SFND-02 mapping | TP-02 T11 |
| AC-12 | Unknown env "production_real_live" → read_env raises ValueError (4 env dışı izin yok: AD-18) | SPEC §6.3 Literal 4 env | TP-02 T12 |
| AC-13 | INI içine `max_leverage_allowed = 2` → `ConfigFactory.read_env("dev")` raise ConfigValidationError (fail-closed FC-3). NO silent clamp 1 | SPEC §8 FC-3, §9 S-2 | TP-03 T13 |
| AC-14 | INI: `allow_short = true` (case-insensitive) → ConfigValidationError (FC-3, PRD no-short). No silent False. | SPEC §8 FC-3 | TP-03 T14 |
| AC-15 | INI: `allow_api_keys = true` → ConfigValidationError. No silent False. (PRD C2 no credentials in v1). ✔ RESOLVED (Package A / D-01): INI option adı, `exc.fields` ve dataclass attribute adı `allow_api_keys` (§21 MAJOR-1). | SPEC §8 FC-3, PRD §1 | TP-03 T15 |
| AC-16 | INI: `trading_permission_default = true` → ConfigValidationError (C2 dev:false). No silent False. | SPEC §8 FC-3 | TP-03 T16 |
| AC-17 | INI: `[env]` section silinip replaced → ConfigValidationError("Section [env] missing") (FC-2). No default create. | SPEC §8 FC-2 | TP-03 T17 |
| AC-18 | INI dosya yolu yanlış / yok → FileNotFoundError (FC-1). No silent {} defaults. | SPEC §8 FC-1 | TP-03 T18 |
| AC-19 | PyYAML **CLOSED PERMANENTLY OFF (OD-FND-04-01)**. `ConfigFactory.try_yaml("any.yml")` çağır → RuntimeError message EXACT `"PyYAML disabled by OD-FND-04. No YAML config parsed unless open decision resolved YAML=true."` (sabit metin, FC-5 gate). | SPEC §7 D-3, §8 FC-5, §17 CLOSED OD-01 | TP-04 T19 |
| AC-20 | PyYAML **CLOSED PERMANENTLY OFF (OD-FND-04-01)**: `import yaml` denemesi FND-04 scope module içinden exec edildiğinde → ImportError yakalanıp RuntimeError'a çevrilir; sessizce INI fallback OLMAZ. | SPEC §8 FC-5, §17 CLOSED OD-01 | TP-04 T20 |
| AC-21 | PyYAML GATE defense-in-depth invariant test (OD closed permanent; test monkeypatch _YAML_ENABLED=True to verify FC-5 mechanism). GATE İÇİNDE: `yaml.safe_load` kullanılır (unsafe yaml.load YOK). S-FND-04 production'da OD kapalı olduğu için bu path ASLA ÇALIŞMAZ; sadece gelecek C3 hikâyesi için gate mechanism doğrulaması. | SPEC §9 S-6, §12 HR-6, §8 FC-5, §17 CLOSED OD-01 | TP-04 T21 |
| AC-22 | Determinism: ConfigFactory.read_env("dev") 10 kez ardışık, `sha256(json sort+compact)[:12]` list → `len(set(sha_list)) == 1`. | SPEC §7 D-1, §2 M-5 | TP-05 T22 |
| AC-23 | Audit (**K-3 / Package C**): `read_env("dev", return_audit=True)` → `(cfg, records)` tuple döner; `cfg` `AppConfig`; `records` `list[ConfigReadAuditRecord]`, `records[-1].source_file` mevcut INI yolu, `records[-1].valid_safety == True`. BU SATIR YALNIZ **opt-in audit** (`return_audit=True`) durumunu tanımlar; varsayılan `read_env("dev")` (return_audit=False) → `AppConfig` (AC-07 ile tutarlı; eski "varsayılan liste döner" ifadesi K-3 ile DÜZELTİLDİ). ✔ AS-BUILT (Package C / K-3 — MAJOR-3 KAPANDI): `loader.py` `read_env(env_name=None, return_audit=False)`; `return_audit=True` → bağımsız public liste (`copy.deepcopy`) döner. Test kanıtı: `test_sfnd04_determinism_audit.py` (public sözleşme + mutability/determinism/hata/hassas-veri); grup → 90 passed, exit 0. Legacy private `_audit_trail` korunur. | SPEC §10 A-1, K-3 | TP-06 T23 |
| AC-24 | Regression smoke: `python -m pytest tests/foundation tests/foundation_sfnd03 tests/foundation_sfnd04 tests/failure tests/contracts -q` → Exit 0 or 0 NEW fail (S-FND-01 2 pre-existing FAIL unchanged). K0 HR-1 + HR-7 | SPEC §12 HR-1/HR-7, DoD-3 | DoD |

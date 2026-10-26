# Reuse Map — S-FND-04 (Downstream Consumer Reuse Paths)

S-FND-04 tarafından sunulan 5 yapıtaşının (building blocks), 14 Epic içindeki 10+ downstream hikâye tarafından nasıl yeniden kullanılacağı (reuse). Tüm reusable öğeler: stdlib dataclass / factory fonksiyonları, NO copy-paste.

## Reuse Matrix (5 Reuse Path × 14 Consumer Stories)

| Reuse Path ID | S-FND-04 Export (Ne sağlar?) | Tür (Data / Factory / Contract) | Hangi hikâyeler kullanır? (Downstream Consumers) | Kullanım Amacı (WHAT, not HOW) |
|---|---|---|---|---|
| R-1 | `VersionConstants.contract_version`, `schema_version`, `app_version` | Frozen Data (read-only sabitler) | S-CON-01 (Envelope schema), S-CON-02 (19 contracts), S-CON-03 (Parity), S-RDH-01 (Replay), S-MDL (Registry 4), E-API | Her S-CON-01 envelope header'da `contract_version="1.0.0"` + `schema_version=1` set edilir. Herhangi bir downstream: VERSION header. S-RDH-01: replay artifact file meta. |
| R-2 | `EnvSafetyLocks` 4 safety bool/int + validation invariant | Data + Validation Contract | S-RSK-01/02 (Risk Engine kill switch + limits), E-API MVP write endpoint, S-FEA-01 Feature Engine | S-RSK-01 kill switch: default kill_switch_enabled = not trading_permission (INVERT). E-API write 2 endpoint izni: `trading_permission_default == False` ise 403 reject. S-FEA: lookback window = `max_leverage_allowed ==1` ise leverage-aware feature yok. |
| R-3 | `AppConfig.artifact_path` + `db_namespace` + `run_mode_default` | Config Path Data | S-RDH-01 (Replay pipeline storage path), E-MDL-01 (Model Registry storage prefix), S-CON-03 (Parity test mode selection) | S-RDH replay CSV okuma/yazma: prefix = `artifact_path + /replay/{symbol}/`. E-MDL model weights kayıt: prefix = `artifact_path + /models/{schema_version}/`. S-CON-03 parity test: env=stg → mode="paper" true; parity 2x cost compare. |
| R-4 | Strict Type Coerce bool/int (OD-04 strict) + `ConfigValidationError` custom exception | Utility Contract (reuse helper import) | S-FND-02 Observability (config section value doğrulaması), E-REG-01 (Regime model threshold coerce), S-STR-01 (Strategy param coerce) | S-FND-02 [observability] log_level: strict (DEBUG/INFO/WARN/ERROR yoksa validation error — FND-04 strict coerce fonksiyonu reuse, rewrite yok). E-REG: regime threshold "0.75" → float coerce strict; S-STR: strategy lookback_window int strict coerce. ✔ RESOLVED (§21 MAJOR-2/4, Package B / D-02): export edilen gerçek helper'lar `coerce_bool`/`coerce_int`; `coerce_bool` artık STRICT kabul kümesi (native `bool` + `true`/`false`/`1`/`0`) ile çalışır. |
| R-5 | `ConfigFactory.register_section(name: str, parser_fn: Callable[[RawConfigParser], dict])` → downstream section'ı AppConfig.extension_sections dict'e inject eder. | Factory Hook (plugin pattern, stdlib-only) | S-RSK-01 (Risk limits section), S-FEA-01 (Feature engineering section), S-STR-01 (Strategy params section), E-MDL (Model registry config), E-BKT (Backtest section), E-PTR (Portfolio section), E-PTF (Performance section) — 7 consumer. | Her hikâye kendi section adını (örn: "risk_limits") + parser fonksiyonunu (ConfigParser raw section → typed dict) register eder. S-FND-04 ConfigFactory okuma esnasında extension'ları çağırır. Result: `cfg.extension_sections["risk_limits"]` → typed dict. Validation fail → ConfigFactory FC-7 error. |

## R-1: VersionConstants → S-CON Envelope Header Reuse (DETAIL)
- **Kullanılan Alanlar:** `VersionConstants.contract_version`, `.schema_version`.
- **S-CON-01 Envelope contract (CONTRACTS §1):** Her typed contract mesajı envelope ile başlar. Envelope: `contract_version = VersionConstants.contract_version` ve `schema_version = VersionConstants.schema_version`.
- **Reuse Benefit:** Herhangi bir contract'ta envelope yazarken hard-code "1.0.0" string literal → VERSION sabitini import edersin. Tek değişiklik noktası (single source of truth): `constants.py` tek dosya.
- **Değişiklik Yapılırsa:** Sadece VersionConstants → Tüm downstream consumer 0 code change.

## R-2: EnvSafetyLocks → S-RSK Kill Switch (DETAIL)
- **Kullanılan Alanlar:** `EnvSafetyLocks.trading_permission_default` (default false), `.allow_api_keys`, `.max_leverage_allowed`. ✔ RESOLVED (§21 MAJOR-1, Package A / D-01): dataclass attribute adı, INI option adı ve `exc.fields` artık `allow_api_keys`. [HISTORICAL] Önceki as-built attribute adı `allow_external_creds` idi.
- **S-RSK-01 Kill Switch default state:** Kill switch default = `NOT trading_permission_default`. Yani dev/test/stg/paper-prod 4 ortamda trading_permission = false → kill switch enabled = true. Risk engine canlı emir göndermeden önce: `if cfg.safety.trading_permission_default is False: raise RiskKillSwitchError(...)`. Başka bir yerde default state YAZILMAZ, tekrar kullanılmaz.
- **E-API MVP Write 2 endpoint permission:** `/api/v1/emergency-stop` ve `/api/v1/kill-switch` authsuz çağrıldığında bile safety kilidi ön kontrol. 4/4 ortam trading yok → write endpoint'leri sadece state change OK (canlı emir gönderimi 0 anyway).

## R-3: artifact_path + db_namespace → S-RDH Replay Storage (DETAIL)
- **Kullanılan Alanlar:** `AppConfig.artifact_path`, `AppConfig.db_namespace`, `run_mode_default`.
- **S-RDH-01 Omur Replay Pipeline:** Veri kaynağı CSV → okuma prefix: `cfg.artifact_path / "replay" / cfg.db_namespace`. Run mode replay ise; artifact_path dev/test yerel local klasör (tempdir tmp_path fixture); S-RDH-01 replay exit code 0 → yazma path = `artifact_path / "replay_output"`. Storage persistence: AD-15 minimal, ama prefix path FND'den gelir, S-RDH kendi AD-15 kararını veriri (sadece prefix).

## R-4: Strict Coerce Utility → S-FND-02 Observability Section (DETAIL)
- **Kullanılan Yöntem:** `from app.platform.config.validation import coerce_bool, coerce_int`. 2 yardımcı fonksiyon FND-04 tarafından export edilir. İmzalar: `coerce_bool(value: str | bool, source: str, field: str) -> bool`, `coerce_int(value: str, source: str, field: str) -> int`.
  - ✔ RESOLVED (Package B / D-02, §21 MAJOR-2/4): Gerçek public isimler `coerce_bool` / `coerce_int` (`app/platform/config/validation.py` L16/L37). [HISTORICAL] Önceki doküman `coerce_strict_bool` / `coerce_strict_int` adlarını iddia ediyordu; bunlar KODDA YOKTU (DOCS INCORRECT → düzeltildi). As-built `coerce_bool` artık STRICT: kabul = native `bool` + `true`/`false`/`1`/`0` (case-insensitive, trim); ret = `yes`/`no`/`on`/`off`/`y`/`n`, boş string, `None`, sayısal tipler → `ConfigValidationError`.
- **S-FND-02 [observability] log_level mapping:** FND-02 validation sırasında: `log_level` alanı yalnız "DEBUG"/"INFO"/"WARN"/"ERROR" kabul edilir. ⚠ AS-BUILT (DÜZELTİLDİ): Önceki doküman `coerce_strict_enum(...)` yardımcı fonksiyonu iddia ediyordu; bu fonksiyon KODDA YOKTUR. As-built davranış: geçersiz `log_level` → hata DEĞİL, env-mapped default'a düşer (`parse_observability` L92-93). Log level default mapping (dev→DEBUG, test→DEBUG, stg→WARN, paper-prod→INFO) FND-04 OD-03 referans default.

## R-5: Register Extension Hook → 7 Downstream (DETAIL)
- **Kullanılan Hook:** `ConfigFactory.register_section(name, parser_callable)`.
- **Örnek Kullanım (S-RSK-01 Risk Limits):**
  - S-RSK-01 kendi init'inde: `ConfigFactory.register_section("risk_limits", _parse_risk_section)`
  - `_parse_risk_section`: ConfigParser raw section → `{ "position_max_usd": int(...), "daily_loss_pct": float(...) }`
  - AppConfig read sonrası: `cfg.extension_sections["risk_limits"]["position_max_usd"]` → erişim.
  - Parser hatası → FC-7: `ConfigValidationError("Extension section risk_limits parse failed: ...")`. Fail-closed.
- **7 Hikâye Extension Section Adları:**
  - S-RSK → "risk_limits"
  - S-FEA-01 → "feature_engineering"
  - S-STR-01 → "strategy_params"
  - E-MDL → "model_registry"
  - E-BKT → "backtest"
  - E-PTR → "portfolio"
  - E-PTF → "performance_tracking"

## Non-Reuse (Öğeler reuse edilmez, herkes kendi yazar)
- `ConfigValidationError` message sınıfı reuse (R-4). Ama exception mesajı içeriği OWNER HİKÂYE tarafından doldurulur (FND template).
- YAML import: Eğer OD-FND-04-01 açılırsa, YAML okuma tekniği FND-04 tarafından yazılır (reuse) ama herkes kendi YAML schema schema doğrulamasını kendi yapar.

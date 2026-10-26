# Current vs Future Boundary — S-FND-04 (Lean Kernel Now / Phase C Future)

SP05 "lean kernel" kuralı: Şimdiki (current) hikâyede SADECE gerekli minimum 10 CAP (mandatory). Gelecek (future) phase C öğeleri: HİÇBİRİ mandatory değil. Hepsi açıkça DEFERRED / NOT THIS STORY.

## Boundary Matrix (10 Capability Rows)

| Capability | Current (S-FND-04 NOW — MANDATORY exactly this) | Future (Phase C — DEFERRED / NOT THIS STORY) | Future Owner Story (when it becomes needed) | Gap Id? |
|---|---|---|---|---|
| 1. Version Constants frozen 4 sabit | ✅ NOW: contract_version=1.0.0, app_version=0.1.0-mvp, schema_version=1, build_metadata=local-mvp. Frozen immut. | FUTURE: build_metadata override via CI env var (GITHUB_SHA); contract_version auto-bump on release; pre-release semver suffix (-rc1). | E-RELEASE (new future epic, not in MVP 14 epics) | GAP-02? No. Numeric thresholds GAP-02 = separate. |
| 2. Typed Config stdlib dataclasses + ConfigParser | ✅ NOW: dataclasses + configparser (stdlib only). 4 typed section: env, safety, observability, platform_contract. Extension_sections dict hook (downstream kendi türünü koyar, FND validasyon YOK). | FUTURE: Pydantic / Pydantic-settings 3rd-party upgrade; nested model deep validation; TOML support; tomllib 3.11+; Union discriminator. | E-CON-01 downstream own scope; NG-1 deferred now | — |
| 3. 4 Env (dev/test/stg/paper-prod) Literal Enum | ✅ NOW: sadece 4 env. Unknown env raises ValueError. 4 INI dosyası hard-coded path. | FUTURE: "prod" canlı ortam (kağıt değil); per-developer dev-overlay local.ini; dynamic env registration. | S-FND-X (future foundation story, not 05+ yet defined) | — |
| 4. Safety Lock 4 kural strict closed (fail-closed) | ✅ NOW: 4 kural violation → ConfigValidationError. No silent clamp. allow_api_keys=false, max_leverage=1, allow_short=false, trading_perm=false. ✔ RESOLVED (§21 MAJOR-1, Package A / D-01): normatif ad `allow_api_keys`; INI option adı ve dataclass attribute adı da `allow_api_keys`. | FUTURE: stg/paper-prod'da allow_short true via config (PRD v2 futures); leverage_max >1 on prod; whitelist-based allow_api_keys true (vault). | PRD v2 hard boundary relax story (new epic); S-RSK-01 kill switch. | — |
| 5. PyYAML GATE (CLOSED PERMANENTLY OFF OD-01) | ✅ NOW: **PERMANENTLY CLOSED OFF**, RuntimeError exact message (FC-5). PyYAML 3p dep EKLENMEZ. Gate mechanism = defense-in-depth only. | FUTURE: YAML include directive (!include); YAML anchors/alias; multi-file YAML merge; .yaml -> .ini sync script. | **YENİ C3 PHASE HİKÂYE (S-FND-X)** ile tekrar açılır; bu SPEC geri dönülmez. NG-2 şimdilik ZERO. | GAP-03 YAML include pattern explicitly deferred. |
| 6. Startup Read-Once (no hot reload) | ✅ NOW: process başlangıcında ConfigFactory.read_env() 1 kez çağır. Sonra cache frozen. | FUTURE: SIGHUP / file watcher hot reload; partial section güncelleme; kill switch dinamik toggle (E-API write endpoint #2 → live modify). | E-API MVP write endpoint + S-RSK kill switch kill-switch live modify. | — |
| 7. Env var Override (sadece env_name) | ✅ NOW: SADECE os.environ["CRYPTO_AI_ENV"] → env_name seçimi. Diğer tüm override: INI dosyası içinden (section/field YOKSA defaults). | FUTURE: her field için env var override (örn CRYPTO_AI__SAFETY__MAX_LEVERAGE_ALLOWED → ini > env var önceliği mapping); .env file. | Phase C new config-overlay story; NG-4 şimdilik yok | — |
| 8. Audit Record (memory-only list) | ✅ NOW: her read → ConfigReadAuditRecord list. memory only; 0 log write; 0 append to file. ✔ RESOLVED (§21 MAJOR-3, Package C / K-3): as-built `read_env(env, return_audit=True)` → `(cfg, records)` public liste döndürür (`copy.deepcopy` ile bağımsız kopya; sıra deterministik); varsayılan `read_env(env)` → `AppConfig`. Legacy private `_audit_trail` korunur. | FUTURE: audit immutable hash chain (SHA256 zinciri); dosyaya append; SIEM export; AWS CloudTrail benzeri signed receipt. | S-OBS-02 audit trail future; NG-6 vault + immut chain related | GAP-04 audit immut hash chain deferred. |
| 9. Extension Sections Hook (register_section) | ✅ NOW: downstream (örn S-RSK-01 limitler) kendi section adını + dict schema belirterek register eder. Hook: register_section(name, parser_fn). | FUTURE: section priority order; cross-section dependency graph; cyclic dependency detection; section-level read timeout. | ALL downstream 14 stories use hook now; priority/graph future generic. | — |
| 10. Strict Type Coerce (OD-04 strict) | ✅ NOW: bool alan → sadece "true/false/1/0" (case-insensitive, whitespace trim). İnt alan → int(..., 10) base 10. Başka her şey → ConfigValidationError. ✔ RESOLVED (§21 MAJOR-2, Package B / D-02): as-built `coerce_bool` STRICT'tir (native `bool` + `true`/`false`/`1`/`0`); `yes`/`no`/`on`/`off`/`y`/`n`, boş string, `None`, sayısal tipler fail-closed. | FUTURE: lenient coerce ("yes"/"no" bool); Enum coerce; unit coerce ("1s" → 1000 ms); regex field validation. | Phase C config UX story; OD-04 strict şimdilik açık default | — |

## 8 Additional Future Items (Source GAPs — ALL Deferred / NOT THIS STORY)
Kaynakta (PRD/EPICS/ARCH/SPEC) tanımsız kalan 8 gap item, SPEC companion source-gaps.md GAP-01..08 içinde hepsi NOT THIS STORY / DEFERRED. Hiçbiri bu hikâyede ZORUNLU değil. User kuralı: "8 source gap requirement'a dönüştürülmeyecek."

| Future Item (Deferred) | Gap ID | Not Mandatory Reason |
|---|---|---|
| Config load latency SLO / threshold (<10 ms?) | GAP-01 | PRD/EPICS içinde latency SLO hiç yok. Fabricate etme. |
| Numeric validation thresholds (decimal min/max) | GAP-02 | Sadece safety 4 tane sabit, diğer tüm numeric threshold downstream. |
| YAML !include / multi-file merge pattern | GAP-03 | OD-FND-04 kapalı default. YAML izni olsa bile include pattern kaynakta belirtilmemiş. |
| Audit immutable hash chain + file append | GAP-04 | Kaynak A-1: "list return edilir" (memory). File append + hash chain icat edilmez. |
| CI YAML workflow test configs | GAP-05 | OD-SFND03-02 CI = OPEN (S-FND-03). S-FND-04 CI değmez. |
| Multi-user RBAC config write permissions | GAP-06 | v1 MVP: tek kullanıcı (developer). RBAC write API E-API scope (not FND). |
| Vault/KMS encrypted config fields (AES-GCM) | GAP-07 | PRD §5.7 future secrets manager; v1 allow_api_keys=false → creds configte YOK → encrypt gerek yok. |
| Exhaustive 14 epic config field list | GAP-08 | Her epic kendi field'ını kendi hikâyesinde tanımlar. FND extension hook sağlar, içerik TANIMLAMAZ (NG-7). |

---

## Summary Current vs Future:
- **MANDATORY (Now):** 10 CAP yukarıdaki tablonun "Current" sütunu — tam tamına o. Ne eksik ne fazla.
- **DEFERRED (Future):** 10 future satır + 8 GAP = 18 future item. HEPSI NOT THIS STORY / gelecek hikâyelere havale.
- **Lean Kernel Compliance (SP05 Law-8):** ✅ PASS — minimum zorunlu 10 CAP, scope bloat YOK.

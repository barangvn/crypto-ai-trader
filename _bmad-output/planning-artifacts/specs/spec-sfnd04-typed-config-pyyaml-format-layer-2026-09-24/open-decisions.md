# Open Decisions — S-FND-04 (4 OD. 3/4 CLOSED CANONICAL RESOLUTION. 0 Silent Resolved.)

KURAL: 3 OD (OD-01/02/04) SOURCE-BACKED CANONICAL DECISION ile KAPANDI (RESOLVED). Audit izi bırakıldı. 1 OD (03) HALA AÇIK (Truly Open, future override possible). 0 Silent Resolved.

---

## OD-FND-04-01: PyYAML 3rd-party dependency ENABLE mi?
STATUS: **✔ CLOSED — RESOLVED: OFF (KAPALI, KALICI)** — Source-Backed Normative Decision (Not Open Anymore)

| Öğe | Detay |
|---|---|
| Decision Closure Evidence (A NORMATIVE SOURCE) | 1. `pyproject.toml` L5 `dependencies = []` (boş) — no runtime 3p dep. 2. S-FND-03 F4 marker `pyproject.toml` L27: `pyyaml` FAIL_CLOSED listed (import → test fail). 3. S-FND-02 HR-5 L82: "OD-FND-04 PyYAML kararı bu hikâyeye TAŞINMAZ; S-FND-02 JSON stdlib-only." 4. SPEC kernel §3.1 IN: "default INI/JSON stdlib only, PyYAML YOK" + §12 HR-5 stdlib default. 5. EPICS L185: sadece contract_version sabitleri; format YAML ZORUNLU DEĞİL. 5 A kaynak → KAPALI kalıcı. |
| **Final Canonical Decision** | **PERMANENTLY OFF = False.** PyYAML 3.p dep S-FND-04'e EKLENMEZ. EX-02 = KALICI DROPPED. Nested config workaround: INI comma-separated string + downstream extension_sections JSON string parse. YAML config requirement doğarsa: **YENİ C3 PHASE HİKÂYE (S-FND-X)** açılır; bu hikâyeye geri dönülmez / spec revize EDİLMEZ. |
| Eski Alternative A (Açık) | **REDDEDILDI.** New 3p dep HR-5 + S-FND-03 F4 gate violation (pyyaml listed fail_closed). Gelecekteki hikâye izniyle ayrı scope. |
| Alternative B (Kapalı + FC-5) | **KABUL EDİLDİ KALICI.** `loader.py` `_YAML_ENABLED = False` module-level. try_yaml çağır → EXACT RuntimeError message = `"PyYAML disabled by OD-FND-04. No YAML config parsed unless open decision resolved YAML=true."` (§7 D-3 literal). Sessiz INI fallback YOK (FC-5). |
| Kalıcı Etki | 0 new 3p dep. pyproject.toml K0 0 modify. F4 marker PASS. INI stdlib + JSON only. Nested ergonomik workaround INI extension. |
| Artık Sahibi | N/A. Kapandı. Gelecekteki yeni hikâye (C3) → new story new OD. |
| Şiddet (closed) | **0 (artık risk yok). MAJOR→REDUCTED TO 0.** |
| Kodda Nasıl Korunur? | `_YAML_ENABLED = False` (sabit, değiştirilemez; import guard try-except → ImportError yakala RuntimeError raise). FC-5 fail-closed. |
| Silent Resolved Risk | ✅ **0 Silent.** 5 kaynak explicitly kapatıldı; decision closure bu dosyada yazıldı. Reddenme izi = bu bölüm. |
| Re-open Zamanı | HİÇ. Yeni C3 hikâyesi new OD. Bu hikâyede OD-01 = CLOSED PERMANENTLY. |

---

## OD-FND-04-02: 4 env INI dosyalarına [platform_contract] + [observability] Section EKLENSİN Mİ? (EX-01)
STATUS: **✔ CLOSED — RESOLVED: DROPPED (KALICI 0 MODIFY) — Source-Backed Normative Decision**

| Öğe | Detay |
|---|---|
| Decision Closure Evidence (A NORMATIVE SOURCE) | 1. S-FND-02 kendi implementation readiness L106/150: **EX-01..04 DROPPED ACCEPTED.** Hardcoded defaults kullan. Aynı pattern S-FND-04 için NORMATİF. 2. S-FND-02 OD-SFND02-01 B seçeneği ÖNERİLEN ve KABUL EDİLDİ = Hardcoded factory defaults (0 modify). 3. GERÇEK 4 INI dosyası (config.dev/test/stg/prod.ini) OKUNDU: [safety], [observability], [platform_contract] BÜTÜN SECTIONLAR HALİHAZIRDA YOK. S-FND-01/S-FND-02/S-FND-03 3 commit sonrası çalışıyor (PASS). Section yoksa defaults pattern ZATEN UYGULANIYOR. 4. SPEC §6.3 AppConfig: safety (EnvSafetyLocks) / platform_contract (decimal_precision 8) / observability (mapping defaults) — HEPSİ için default constructor değerleri mevcut. Section YOKSA defaults düşer (CAP-07). 5. K0 KURAL: Existing-file modification DEFAULT = 0. 4 source → DROPPED kalıcı. |
| **Final Canonical Decision** | **EX-01 = PERMANENTLY DROPPED. 4 env INI dosyalarına HİÇBİR MODIFY (0 satır append).** Section [env] HARİÇ diğer section ([safety], [observability], [platform_contract]) AppConfig loader içinde HARD-CODED defaults ile düşer. Geliştirici değerleri değiştirmek isterse: YENİ HİKÂYE (Config Overlay v2) → explicit EX list onayı; bu hikâyede geri dönülmez. |
| Eski Alternative A (Açık, 24 satır append) | **REDDEDILDI.** K0 ihlali (existing modify) + 4 completed story byte-diff-0 preservation invariant risk. S-FND-02 aynı tradeoff'ta 0 modify seçti (aynı pattern). |
| Alternative B (Kapalı defaults düşer) | **KABUL EDİLDİ KALICI.** ConfigFactory loader her section için: has_section(X)? → parse / YOKSA → `SectionDefaultsDict[env_name][X]` constructor apply. [env] hariç diğerleri OPTIONAL: section missing = NO ERROR, defaults uygula. [env] ZORUNLU (FC-2 raise). |
| Kalıcı Etki | 0 existing file modification. S-FND-01 4 INI byte-diff 0 (preservation matrix ZBD ✅). Default değerler tek yerde: `loader.py` SectionDefaults. Gelecekte değiştirmek için tek yer update (yeni hikâye). |
| Sahibi (Closed) | N/A. Kapandı. Gelecekte section append → new story new OD. |
| Şiddet (Closed) | **0 (artık risk yok). MAJOR→REDUCTED TO 0.** |
| Kodda Nasıl Korunur? | `loader.py`: 3 optional section (safety/observability/platform_contract) için explicit `if section_present: parse_from_ini else: apply_default_dict(env_name)`. [env] section absent → FC-2 ConfigValidationError("Section [env] missing"). |
| Silent Resolved Risk | ✅ **0 Silent.** 4 kaynak explicitly kapattı; audit izi = bu bölüm. |
| Re-open Zamanı | HİÇ. Gelecekte override → new story. |

---

## OD-FND-04-03: Default Log Level Mapping 4 Env (DEVIATION FROM S-FND-02?)
STATUS: **⚠️ TRULY OPEN — Implementation phase coordination** — Closed değil; 0 Silent Resolved.

| Öğe | Detay |
|---|---|
| Problem | S-FND-02 OD-SFND02-01 Observability Section default log level: S-FND-02 implementasyonunda son durum HARDCODED 4 env → level mapping DEV=INFO/TEST=DEBUG/STG=WARN/PAPER-PROD=INFO (veya farklı). Bizim S-FND-04 mapping aynı mı olmalı? |
| **Default** | **S-FND-02 ile AYNI mapping KULLANILIR.** S-FND-02'nin son OD kararı neyse aynısı (read from S-FND-02 final artifact; biz duplicate etmeyiz; referans veririz; farklıysa S-FND-02'nin kararı OVERRIDE eder). FND-04 kendi yeni mapping İCAT ETMEZ. |
| Alternative A: Explicit 4 enum sabit AppConfig observability.log_level mapping SFND02'ye AYNEN → implementasyon sırasında S-FND-02 production logger.py içindeki son mapping okunup kopyalanır. Referans: S-FND-02 SPEC L400 OD-SFND02-01. |
| Alternative B: Boş bırak, testte noop default debug. |
| Etki | ZERO if identical; drift between layers if different. |
| Sahibi | Cross-cutting: SFND02 Observability + this layer owner (coordinate on implementation). |
| Şiddet | MINOR. Sadece log seviyesi; güvenlik sınırı değil. |
| Kaynak | SPEC §4 UP-02 S-FND-02 OD-SFND02-01 reference; carry decision doğrulandı. |
| Silent Resolved Risk | ✅ Biz duplicate mapping yazmadık, only reference. Gelecekte FND-02 mapping değişirse bizim de updatemiz gerekir. OD-03: future coordination required. |
| Çözüm Zamanı | Implementation Aşaması A explicit fixturedan S-FND-02 log level extract → karşılaştır → aynıysa PASS. |

---

## OD-FND-04-04: Type Coerce Strict veya Lenient?
STATUS: **✔ CLOSED — RESOLVED: STRICT (Package B / D-02 ile UYGULANDI)** — Source-Backed Normative Decision (Not Open Anymore)

| Öğe | Detay |
|---|---|
| Problem | `max_leverage_allowed = "1"` (string) INI value → AppConfig int field. ConfigParser str döner. Biz STRICT (sadece int("1") success; "1.0" → ERROR) mi YOKSA lenient ("1.0" → int(1.0) via Decimal) mı? Safety kilidi için önemlidir: `max_leverage_allowed = "1.999"` lenient 1 floor vs strict hata. |
| **Default** | **STRICT.** Tam sayı bekliyorsa tam sayı parse. String bool: sadece "True"/"False"/"1"/"0" kabul. "yes"/"no"/"y"/"n" → ConfigValidationError. Gelecek OD-04 açılırsa lenient tanımlanır. |
| Alternative A: STRICT (default). Güvenlik amacıyla: `allow_short = "1"` → True OK; "y" → Error. |
| Alternative B: LENIENT with warning + coerce. Risk: accidental 1.999→1 for leverage silently. |
| Etki - Strict | Config dosyası yazım hatası → hızlı fail. Config dosyası sıkı denetim. |
| Sahibi | Foundation Owner. |
| Şiddet | MINOR - Config format ergonomisi. |
| Silent Resolved Risk | ✅ STRICT = default selected explicitly. Gelecekte LENIENT'e geçmek için yeni OD kararı. |

⚠ **[HISTORICAL] AS-BUILT NOTE (2026-10-25, §21 MAJOR-2 — o tarihte SCOPE-OWNER DECISION REQUIRED + IMPLEMENTATION GAP):** O tarihte as-built `validation.py: coerce_bool` LENIENT davranıyordu: `("true","1","yes","on")→True`, `("false","0","no","off","")→False`; hata mesajı "(strict bool only: true/false/1/0/yes/no/on/off)" diyordu. Bu, OD-04 STRICT default'u (`sadece True/False/1/0`) ile ÇELİŞİYORDU. Karar sahibi seçenekleri sunulmuştu: **(A)** STRICT'e dön; **(B)** LENIENT'i yeni bir OD kararı ile NORMATİF yap.

✔ **RESOLUTION (Package B / D-02 — 2026-10-26):** Scope owner **Seçenek (A) = STRICT**'i onayladı ve uygulandı. `coerce_bool` artık STRICT sözleşme ile çalışır:
- **Kabul:** native `bool` (`True`/`False`) + kanonik literal `true`/`false`/`1`/`0` (büyük/küçük harfe duyarsız karşılaştırma; baştaki/sondaki whitespace trim edilir).
- **Ret (fail-closed):** `yes`/`no`/`on`/`off`/`y`/`n`, açıkça verilen boş string, `None`, sayısal tipler (int/float) ve desteklenmeyen diğer token'lar → `ConfigValidationError`.
- **Hata mesajı:** `"Boolean coerce failed for value '<v>' (strict bool only: true/false/1/0)"`.
- **Default ↔ geçersiz ayrımı:** Eksik config alanının default kullanması (coerce çağrılmaz), `coerce_bool`'a açıkça geçersiz girdi verilmesinden AYRI davranıştır.
Kod/test izni: `EX-K0-SFND04-D02`. `allow_api_keys` adı (Package A / D-01) ve `exc.fields` INI option adı korunmuştur. FC-4'ün eski `yes` kabulü iddiası STRICT lehine çözülmüştür (bkz. `SPEC.md` §8 FC-4). OD-04 böylece **RESOLVED** kapanmıştır.

---

# OD Summary (3 CLOSED CANONICAL / 1 TRULY OPEN)

| OD ID | Title | Status (Closed/Open) | Decision Closure Evidence Source-Count | Truly Open Anymore? | Silent Resolved? | MAJOR risk reducted? |
|---|---|---|---|---|---|---|
| OD-01 | PyYAML Enabled (3p dep) | **CLOSED = PERMANENTLY OFF (False)** | 5 source (pyproject deps=[], F4 pyyaml fail_closed, SFND02 HR5 L82, SPEC §3.1/§12 HR5, EPICS L185 no yaml req) | ❌ NO — Closed permanently. New story C3 required re-open. | ✅ NO silent — explicit audit izi bu dosyada. | **MAJ-01 → 0 (YES)** |
| OD-02 | INI Section Append EX-01 (4 file 24 satır) | **CLOSED = PERMANENTLY DROPPED (0 modify)** | 4 source (SFND02 EX-01 DROPPED ACCEPTED L106/150, SFND02 OD B selected, 4 real INI sections missing PASS, K0 default=0) | ❌ NO — Closed permanently. New Config Overlay v2 story required. | ✅ NO silent — explicit audit izi bu dosyada. | **MAJ-02 → 0 (YES)** |
| OD-03 | LogLevel Mapping Ref SFND02 | **TRULY OPEN (default: SFND02 identical ref)** | 1 default carry (reference only, no dupe) | ✅ YES — drift coordinate implementation phase. | ✅ NO silent — explicit ref not invention. | N/A (MINOR) |
| OD-04 | Strict Type Coerce bool/int | **CLOSED = STRICT (Package B / D-02 ile UYGULANDI)** | 1 default selected (safety fail-fast) + Package B kod/test/doküman kanıtı (`coerce_bool` STRICT; `test_sfnd04_validation.py`) | ❌ NO — Closed. Future lenient requires NEW OD. | ✅ NO silent — STRICT explicit + test kanıtı bu dosyada ve test dosyasında. | N/A (MINOR) — resolved. |

**3/4 CLOSED (OD-01/02 source-backed canonical 5+4 evidence; OD-04 STRICT Package B / D-02 ile uygulandı). 1/4 TRULY OPEN (OD-03). 0/4 Silent Resolved. MAJOR risk count REDUCTED 2→0.** ✅

---

# KEY DECISION REGISTER (OD DIŞI) — S-FND-04

Bu bölüm OD sayısını (4) DEĞİŞTİRMEZ; OD dışı, scope owner onaylı ayrı bir key decision'dır.

## K-3: `read_env(return_audit=True)` Public Audit API Dönüş Sözleşmesi
STATUS: **✔ RESOLVED (Package C / K-3 design gate — 2026-10-26)** — Scope Owner Onaylı Public API Sözleşmesi

| Öğe | Detay |
|---|---|
| Onay | Scope owner **K-3** public audit API dönüş sözleşmesini onayladı. Bu, A-1/AC-23/T23/CAP-09 arasındaki dönüş tipi çelişkisini çözer. |
| Varsayılan dönüş | `read_env(env)` → **`AppConfig`**. Mevcut varsayılan davranış KORUNUR; AC-07 bu varsayılanın canonical kabul kriteridir. |
| Opt-in audit dönüşü | `read_env(env, return_audit=True)` → **`(cfg, records)`** tuple. `cfg: AppConfig`; `records: list[ConfigReadAuditRecord]`. |
| Yeni parametre | `return_audit: bool = False`. Mevcut `env_name: Optional[str] = None` korunur; positional çağrı davranışı ve default config yükleme davranışı DEĞİŞMEZ. |
| Audit sırası | Kayıtlar aynı config işleme sırasını izler; aynı girdinin aynı sırada işlenmesi farklı sonuç veya nondeterministik sıralama üretmez. |
| Liste/kayıt sahipliği | Her audit çağrısı BAĞIMSIZ bir public liste döndürür. Public listenin veya kayıtların değiştirilmesi private `_audit_trail` durumunu ya da başka bir çağrının sonucunu DEĞİŞTİRMEZ. |
| Public kayıt şeması | YALNIZCA mevcut implementation ile doğrulanan alanlar: `source_file` (str), `md5` (str, 32-hex), `valid_safety` (bool), `correlation_id` (Optional[str]) — `models.py` L33-46 `ConfigReadAuditRecord` (frozen). Yeni alan adı / event türü / metadata UYDURULMAZ. |
| Hassas veri | Public kayıtlara ham credential, secret veya hassas config değeri EKLENMEZ. |
| Hata davranışı | `return_audit=False` ve `True` her ikisinde de config validation başarısızsa mevcut validation exception YÜKSELTİLİR; hata durumunda kısmi `(cfg, records)` DÖNDÜRÜLMEZ. |
| Normatif kaynak | Varsayılan dönüş: `acceptance-criteria.md` AC-07. Audit çağrısı: `acceptance-criteria.md` AC-23 (AC-23 bu kararla opt-in'e daraltıldı), `test-plan.md` T23, `SPEC.md` §10 A-1. |
| K0 / Package C | Implementation AYRI Package C kod turunda YAPILDI (izin `EX-K0-SFND04-D03`). |
| Package D kapsam dışı | A-2/A-3/A-4 (violated-field audit, VersionConstants fingerprint, baseline MD5 comparison) BU kapsam DIŞINDADIR; çözümlenmiş gösterilemez. |
| As-built durum | ✔ **KAPANDI (Package C / K-3 implementation — 2026-10-26):** `loader.py` `read_env(env_name=None, return_audit=False)`; `return_audit=True` → `(cfg, records)` (`copy.deepcopy` ile BAĞIMSIZ public liste). Legacy private `_audit_trail` KORUNUR. Test kanıtı: `test_sfnd04_determinism_audit.py`; grup → 90 passed, exit 0. (Design-gate kararı 2026-10-26'da alınmıştı; kod aynı gün Package C turunda uygulandı.) |
| Silent Resolved Risk | ✅ **0 Silent** — K-3 kararı ve istisna bu dosyada explicit kayıt altına alındı. |

---

# EXCEPTION REGISTER (K0 İSTİSNASI) — S-FND-04

KURAL: K0 = existing-file modification DEFAULT 0. Aşağıdaki kayıt, scope owner onayıyla verilen TEK (scoped) K0 istisnasıdır. Bu bölüm mevcut OD kayıtlarını DEĞİŞTİRMEZ; yalnız ek audit izi bırakır.

## EX-K0-SFND04-D01: Dataclass attribute + validation keyword `allow_api_keys` hizalaması
STATUS: **✔ APPROVED — SCOPED K0 EXCEPTION (S-FND-04 Package A / D-01)** — Scope Owner Option A Onayı

| Öğe | Detay |
|---|---|
| Onay | Scope owner **Option A**'yı ve bu sınırlı K0 istisnasını onayladı. |
| Normatif sözleşme | Dataclass attribute adı = `allow_api_keys`; INI/config option adı = `allow_api_keys` (değişmeyecek); validation exception `exc.fields` adı = `allow_api_keys` (değişmeyecek). Eski dataclass/validation keyword adı `allow_external_creds` KALDIRILIR. |
| Gerekçe | Mevcut kaynaklardaki as-built dataclass attribute (`models.py` L17 `allow_external_creds`) ve validation keyword (`validation.py` L80 `allow_external_creds=api_b`) normatif sözleşmeyle (`allow_api_keys`) hizalanmalıdır. INI option (`validation.py` L47/L56) ve `exc.fields` (L60/L69) zaten `allow_api_keys`; DEĞİŞMEZ. |
| İzin verilen kod/test dosyaları | 1. `app/platform/config/models.py`  2. `app/platform/config/validation.py`  3. `tests/foundation_sfnd04/test_sfnd04_config_typed.py` |
| İzin verilen değişiklik | Dataclass attribute ve ilgili validation keyword'ünü `allow_api_keys` ile hizalamak; mapping ve exception alan davranışını test etmek. |
| Açık kapsam dışı konular | STRICT boolean coercion uygulaması (OD-04 / D-02), `read_env(return_audit=True)` public API'si, A-2/A-3/A-4, diğer story'ler. |
| Git sınırı | Bu aşamada **stage = 0, commit = 0, push = 0**. |
| Kaynak | `SPEC.md` §6.2 L129/L133/L135 (MAJOR-1); `open-decisions.md` OD-04; PRD §1 v1 hard boundary. |
| Silent Resolved Risk | ✅ 0 Silent — istisna bu dosyada explicit kayıt altına alındı. |

---

## EX-K0-SFND04-D02: `coerce_bool` normatif STRICT davranışına uyarlama
STATUS: **✔ APPROVED — SCOPED K0 EXCEPTION (S-FND-04 Package B / D-02)** — Scope Owner D-02 Onayı

| Öğe | Detay |
|---|---|
| Onay | Scope owner, **D-02 STRICT davranışını** ve Package B için gerekli bu sınırlı K0 istisnasını onayladı. |
| Gerekçe | Mevcut `coerce_bool` davranışını (LENIENT: `true/1/yes/on` ve `false/0/no/off/""` kabul) normatif **STRICT** sözleşmesine uyarlamak, mevcut kod/test dosyalarında sınırlı değişiklik gerektiriyor. |
| Normatif sözleşme (STRICT) | Kabul: native `bool` (True/False) + kanonik literal `true/false/1/0` (case-insensitive, baş/son whitespace trim). Ret: `yes/no/on/off/y/n`, boş string, `None`, sayısal tipler (int/float) ve diğer desteklenmeyen token'lar → fail-closed `ConfigValidationError`. Eksik config alanının default kullanması, açıkça geçersiz girdinin reddedilmesinden AYRI davranıştır. |
| İzin verilen tracked dosyalar | 1. `app/platform/config/validation.py`  2. `tests/foundation_sfnd04/test_sfnd04_validation.py`  3. `tests/foundation_sfnd04/test_sfnd04_config_typed.py` (yalnız gerekli entegrasyon testi ise) |
| İzin verilen dokümanlar | STRICT/FC-4/OD-04 sözleşmesinin hizalanması için gereken S-FND-04 spec dizini belgeleri (`SPEC.md`, `test-plan.md`, `risks-open.md`, `sp05-self-validation.md`, `implementation-readiness.md`, `reuse-map.md`, `expected-file-changes.md`, `current-vs-future-boundary.md`, bu dosya). |
| Kapsam dışı | Package C public audit API (`read_env(return_audit=True)`); Package D A-2/A-3/A-4 (fingerprint / violated-field / MD5 compare); diğer hikâyeler. |
| Git sınırı | Bu aşamada **stage = 0, commit = 0, push = 0**. |
| Uygulama Durumu | ✔ **UYGULANDI (Package B / D-02):** `validation.py` `coerce_bool` STRICT kabul kümesine çevrildi; `tests/foundation_sfnd04/test_sfnd04_validation.py` STRICT kabul/ret testleriyle genişletildi (10 → 46 collected). Package A'nın `allow_api_keys` sözleşmesi korundu. `coerce_int`, `read_env`, `_audit_trail`, fingerprint ve MD5 karşılaştırma kapsamı DEĞİŞTİRİLMEDİ. Kapsam: yalnız bu EX'te izin verilen dosyalar. |
| Silent Resolved Risk | ✅ 0 Silent — istisna ve OD-04 kapanışı bu dosyada explicit kayıt altına alındı. |

---

## EX-K0-SFND04-D03: `read_env(return_audit=True)` public audit API sözleşmesinin uygulanması
STATUS: **✔ APPROVED — SCOPED K0 EXCEPTION (S-FND-04 Package C / K-3)** — Scope Owner K-3 Onayı

| Öğe | Detay |
|---|---|
| Onay | Scope owner **K-3** public audit API dönüş sözleşmesini ve Package C için gerekli bu sınırlı K0 istisnasını onayladı. |
| Gerekçe | Normatif public audit API sözleşmesini (`read_env(env, return_audit=True) → (cfg, records)`) gerçek implementation'a eklemek, mevcut `loader.py` ve hedef test dosyasında sınırlı değişiklik gerektirir. |
| Normatif hedef sözleşme | Varsayılan `read_env(env)` → `AppConfig` (AC-07). Opt-in `read_env(env, return_audit=True)` → `(cfg, records)`; `cfg: AppConfig`, `records: list[ConfigReadAuditRecord]`. Yeni parametre `return_audit: bool = False`; mevcut imza/positional davranış korunur. |
| Planlanan izinli production dosyası | `app/platform/config/loader.py` |
| Öncelikli test dosyası | `tests/foundation_sfnd04/test_sfnd04_determinism_audit.py` (T23 konumu; test-plan.md TP-06) |
| Ek test dosyası | Gerçek test envanteri incelemesi bu turda ek zorunlu dosya göstermedi. İhtiyaç doğarsa yalnızca zorunlu dosya tam yolu ve ayrı gerekçeyle eklenir; aksi halde `SCOPE EXPANSION REQUIRED` olarak raporlanır. |
| Public kayıt şeması güvenlik/determinism | Yalnız doğrulanmış alanlar (`source_file`, `md5`, `valid_safety`, `correlation_id`; `models.py` L33-46). Ham credential/secret/hassas config değeri YOK. Sıra deterministik; her çağrı bağımsız liste döndürür (private `_audit_trail` ve diğer çağrılar etkilenmez). |
| Kapsam dışı | Package D A-2/A-3/A-4 (violated-field audit, VersionConstants fingerprint, baseline MD5 comparison/WARNING); diğer hikâyeler. Bu EX yalnız K-3 davranışını uygulamak/doğrulamak için gereken dosyaları kapsar. |
| Test/SPEC dokümanları | Gerekli S-FND-04 SPEC/test dokümanları bu EX'in KOD kapsamına DEĞİL, Package C'nin sözleşme/izlenebilirlik kapsamına aittir. |
| Git sınırı | **Stage, commit ve push izni VERİLMEDİ** (stage = 0, commit = 0, push = 0). |
| Uygulama Durumu | ✔ **UYGULANDI (Package C / K-3 — 2026-10-26):** `loader.py` `read_env(env_name=None, return_audit=False)` eklendi; `return_audit=True` → `copy.deepcopy` ile bağımsız `(cfg, records)` döner; legacy `_audit_trail` ve validation davranışı korundu. Hedef test `tests/foundation_sfnd04/test_sfnd04_determinism_audit.py` public sözleşme/mutability/determinism/hata/hassas-veri/legacy testleriyle genişletildi; grup → 90 passed, exit 0. Kapsam: yalnız bu EX'te izin verilen dosyalar (`loader.py`, `test_sfnd04_determinism_audit.py`). Package D UYGULANMADI. |
| Silent Resolved Risk | ✅ **0 Silent** — K-3 kararı, EX kaydı ve as-built gap bu dosyada explicit. Package D kapsam dışıdır ve kapatılmış gösterilmez. |

---

# DEFERRAL REGISTER (SCOPE-OWNER ONAYLI ERTELEME) — S-FND-04

KURAL: Aşağıdaki kayıt, Package D maddelerinin scope owner onayıyla AYRI bir takip işine ERTELENDİĞİNİ belgeleyen resmi erteleme kaydıdır. Bu bölüm mevcut OD/K-3/EX kayıtlarını DEĞİŞTİRMEZ; yalnız ek audit izi bırakır. Erteleme, maddelerin UYGULANDIĞI veya ÇÖZÜLDÜĞÜ anlamına GELMEZ.

## DEF-SFND04-D04: Package D (A-2/A-3/A-4) Ayrı Takip İşine Erteleme
STATUS: **⏸ DEFERRED — NOT IMPLEMENTED** — Scope Owner Onaylı Erteleme Kaydı

| Öğe | Detay |
|---|---|
| Karar | Package D (A-2/A-3/A-4), Package A/B/C kapsamından AYRILARAK ayrı bir takip işine ERTELENİR. Bu maddeler mevcut teslimin bir parçası DEĞİLDİR ve tamamlanmış/çözümlenmiş olarak sunulamaz. |
| Kapsam (ertelenen maddeler) | **A-2** violated-field audit alanı (`ConfigReadAuditRecord`'a ihlal edilen alan + maskeli raw value). **A-3** `VersionConstants` fingerprint fonksiyonu (`sha256(VersionConstants json)[:8]`). **A-4** 4 env INI baseline MD5 comparison / WARNING davranışı. |
| Kaynak (SPEC / AC / DoD traceability) | **SPEC.md §10 L187-192:** her madde `⚠ AS-BUILT (§21 MINOR-7, IMPLEMENTATION GAP)` notuyla "Gereksinim korunur, karşılanmadı → gap" olarak işaretli. **SPEC.md §21:** L273 "MINOR-7 KALIR AÇIK (Package D). Kapatılmamış kod gap'i kapatılmış gibi gösterilmez."; L292 `| MINOR-7 | A-2/A-3/A-4 | IMPLEMENTATION GAP |`; L297 "IMPLEMENTATION GAP (KALIR AÇIK): MINOR-7 (A-2/A-3/A-4 → Package D)"; L299 "MINOR-7 yalnızca doküman düzenlemesiyle kapatılamaz". **acceptance-criteria.md:** A-2/A-3/A-4 için AC satırı YOK (AC-01..AC-24 içinde eşleşme yok). **dod.md:** A-2/A-3/A-4 için DoD satırı YOK (DoD-1..DoD-8 içinde eşleşme yok). |
| Normatif olarak zorunlu mu? | **HAYIR.** A-2/A-3/A-4, SPEC §10'da KORUNAN gereksinimdir ancak bağlayıcı bir AC veya DoD maddesi DEĞİLDİR (AC/DoD'de satır yokluğu doğrulandı). Dolayısıyla Package A/B/C kabulünü ENGELLEMEZ; ancak SPEC gereksinimi olarak açık kalır. Bu nedenle erteleme, "non-blocking" gerekçesiyle sessizce kapatma değil, **scope owner tarafından açıkça onaylanan resmi erteleme**dir. |
| Mevcut implementation durumu | **UYGULANMADI.** Production'da violated-field audit alanı YOK (`ConfigReadAuditRecord` ihlal alanı/maskeli raw value içermez); `VersionConstants` fingerprint fonksiyonu YOK (yalnız test helper `sha_json()` sha256[:12] üretir); baseline MD5 comparison / WARNING üretimi YOK (`read_env` md5 hesaplar ama S-FND-01 baseline ile karşılaştırma yapmaz). |
| Package A/B/C kabulüne etkisi | **ETKİLEMEZ.** Package A (D-01)/B (D-02)/C (K-3) implementasyonu `d4ec0ae`, dokümantasyonu `adcebc7` commit'lerinde kayıtlıdır; A-2/A-3/A-4 bu commit içeriklerinin parçası değildir. |
| Gerekçe | Bu özellikler mevcut A/B/C implementasyon commit'inin bir parçası DEĞİLDİR. Ayrı uygulama kapsamı, açık test planı, kabul kriterleri ve bağımsız doğrulama gerektirir. Ayrıca bu maddeler AC/DoD kapsamında bağlayıcı olmadığından A/B/C teslimi engellenmeden ayrı bir takip işine ertelenebilir. |
| Onay | Scope owner tarafından onaylanan erteleme (Package D → ayrı takip işi). |
| Takip koşulları | 1. Ayrı bir takip işi veya story açılması. 2. Her madde (A-2/A-3/A-4) için SPEC/AC/DoD izlenebilirliğinin kurulması. 3. K0 veya benzeri mevcut dosya değişikliklerini yöneten kurallar gerekiyorsa açık istisnanın kaydedilmesi. 4. Public API ve audit schema (özellikle `ConfigReadAuditRecord`) etkisinin belirlenmesi. 5. Test planı ve gerçek runtime kanıtının üretilmesi. 6. Ayrı implementasyon ve bağımsız final audit. **7. S-FND-04 story kapanışında bu erteleme YENİDEN DEĞERLENDİRİLMELİDİR; takip işi, uygulama kanıtı ve kabul koşulları doğrulanmadan A-2/A-3/A-4 çözülmüş SAYILMAZ.** |
| Kapsam sınırı | Bu erteleme `d4ec0ae` veya `adcebc7` commit içeriklerini DEĞİŞTİRMEZ; Package A/B/C test sonuçlarını yeniden TANIMLAMAZ; hiçbir başka story'yi KAPSAMAZ. |
| Diğer kayıtlarla ilişki | K-3 kaydındaki "Package D kapsam dışı" (L119) ve EX-K0-SFND04-D03 "Kapsam dışı" (L175) hükümleriyle ÇELİŞMEZ; aksine bu erteleme onları teyit eder. Erteleme, MINOR-7 gap'ini kapatmış saymaz. |
| Git sınırı | Bu aşamada **stage = 0, commit = 0, push = 0**. |
| Silent Resolved Risk | ✅ **0 Silent** — erteleme kararı ve kapsam sınırı bu dosyada explicit kayıt altına alındı; maddeler açık ve uygulanmamış olarak görünür kalır. |

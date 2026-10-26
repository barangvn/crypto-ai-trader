# Risks Open — S-FND-04 (1 Active Risk R-3 MINOR. 2 Risks RESOLVED via CLOSED CANONICAL DECISIONS. 0 Silent Resolved.)

KURAL: 4 Open Decision (OD-01/02/04 CLOSED RESOLVED; OD-03 TRULY OPEN). Riskler: 2 risk R-1/R-2 RESOLVED. 1 risk R-3 ACTIVE (MINOR, acceptable). 0 Silent Resolved.

## Risk Summary Table (Post-Closure Canonical)

| Risk ID | Open Decision Source | Risk Short | Status (Open/Resolved) | Severity | Closure Evidence (if Resolved) |
|---|---|---|---|---|---|
| R-1 | OD-FND-04-01 (PyYAML OFF) | Nested dict/list INI string-split workaround gerekir. | **✔ RESOLVED VIA CLOSED CANONICAL OD** | N/A (REDUCTED 0) | OD-FND-04-01 CLOSED 5 source: pyproject.toml `deps=[]`, S-FND-03 F4 pyyaml fail_closed, S-FND-02 HR5 L82, SPEC §3.1/§12 HR5, EPICS L185 no yaml req. → Workaround INI comma-separated stdlib JSON parse KALICI. YAML isteği → yeni C3 hikâye; risk bu story için RESOLVED. |
| R-2 | OD-FND-04-02 (EX-01 DROPPED, INI 0 modify) | Geliştirici INI section eksik debug kaybeder. | **✔ RESOLVED VIA CLOSED CANONICAL OD** | N/A (REDUCTED 0) | OD-FND-04-02 CLOSED 4 source: S-FND02 EX-01..04 DROPPED ACCEPTED L106/150, SFND02 OD B hardcoded defaults, GERÇEK 4 INI sections missing PASS (3 commit), K0 default=0. → Section yoksa defaults kalıcı pattern. Docstring __init__.py içinde KALICI not. Risk bu story için RESOLVED. |
| R-3 | OD-FND-04-04 (Strict Type Coerce) | Bool/int yanlış değer → ConfigValidationError → Deploy erken fail. | **⚠️ ACTIVE (ACCEPTABLE RISK)** | **MINOR** (Strict = fail-fast FEATURE, NOT a bug. Safety kazanımı > UX kaybı.) | ✔ STRICT sözleşme Package B / D-02 ile UYGULANDI; R-3 beklenen fail-fast davranıştır (bkz. R-3 ACTIVE DETAIL). |

## R-1 CLOSED DETAIL (PyYAML OFF Nested Workaround)
KALICI ÇÖZÜM: INI comma-separated string + downstream extension_sections dict value JSON parse.
- Gelecekte YAML native list ihtiyacı → YENİ C3 Phase hikâyesi.
- Bu SPEC için R-1 riski: KALICI RESOLVED.

## R-2 CLOSED DETAIL (Section Append Dropped 0 Modify)
KALICI ÇÖZÜM: 3 Optional Section [safety]/[observability]/[platform_contract] → Loader DefaultDict düşer. Sadece [env] ZORUNLU (FC-2 raise).
- Gelecekte INI explicit section append ihtiyacı → YENİ Config Overlay v2 hikâyesi.
- Bu SPEC için R-2 riski: KALICI RESOLVED.
- Mitigation kalıcı: `app/platform/config/__init__.py` docstring → Section yoksa hata değil defaults düşer.

## R-3 ACTIVE DETAIL: Strict Coerce Deployment Early Fail (ACCEPTABLE)
### Scenario
Dev `allow_short = yes` veya `max_leverage_allowed = 1.9` → ConfigValidationError. Uygulama kalkmaz. Dev 5 dk düzeltir.
### Why Strict = Feature (Risk Acceptable, MINOR):
- Fail-fast development öncesi catch. Lenient olsaydı `allow_short=yes→True` S-FND-01 C2 safety ihlali. Daha kötü: Prod short açık.
- OD-04 **CLOSED = STRICT** (Package B / D-02 ile uygulandı). Gelecekte lenient ihtiyacı → YENİ OD kararı + yeni hikâye.
### Security/Safety Impact
POZİTİF (Safety kilidi ihlallerini fail-fast yakalar). R-3 kabul edilebilir MINOR risk → Implementation başlamasına ENGEL DEĞİL.

### ✔ RESOLVED / CONFIRMED (Package B / D-02 — 2026-10-26)
As-built `coerce_bool` artık **STRICT**'tir ve OD-04 default'u ile tutarlıdır (bkz. `validation.py`): kabul = native `bool` + `true`/`false`/`1`/`0` (case-insensitive, whitespace trim); ret = `yes`/`no`/`on`/`off`/`y`/`n`, boş string, `None`, sayısal tipler → `ConfigValidationError`. Bu nedenle yukarıdaki "Strict Coerce" senaryosu artık gerçek as-built davranıştır ve fail-fast beklenen sonuçtur:
- OD-04 = **CLOSED** (STRICT), risks-open bunu resolved olarak kaydeder.
- R-3 sınıfı MINOR kalır: bu bir "risk" değil, kasıtlı fail-fast güvenlik davranışıdır.
- [HISTORICAL] Önceki AS-BUILT notu (2026-10-25): as-built `coerce_bool` LENIENT idi (`true/1/yes/on` → True; `false/0/no/off/""` → False) ve OD-04 STRICT default'u ile çelişiyordu (MAJOR-2, artık kapatıldı).

---

## 4 OPEN DECISIONS — Post-Closure (3 CLOSED CANONICAL / 1 TRULY OPEN)
OD-01/02: **CLOSED RESOLVED** (audit izi open-decisions.md L7-L39 + Summary L77-L84). 0 Silent Resolved.
OD-04: **CLOSED = STRICT** (Package B / D-02 ile uygulandı; audit izi open-decisions.md OD-04 RESOLUTION + EX-K0-SFND04-D02).
OD-03: **TRULY OPEN** (default preserved; future new OD kararı gerek).

| OD ID | Status (Closed/Open) | Risk if Default Kept | Silent Resolved? |
|---|---|---|---|
| OD-01 PyYAML 3p Dep | **CLOSED = PERMANENTLY OFF** | R-1 Nested workaround → RESOLVED. | ❌ NO Silent. 5 kaynak explicitly kapattı. |
| OD-02 EX-01 INI Append | **CLOSED = PERMANENTLY DROPPED (0 Modify)** | R-2 Section eksik confusion → RESOLVED. | ❌ NO Silent. 4 kaynak explicitly kapattı. |
| OD-03 LogLevel Mapping SFND02 Ref | TRULY OPEN (Identical Ref default) | MINOR mapping drift (implementation phase coordinate). | ❌ NO Silent — explicit ref not invention. |
| OD-04 Strict Coerce bool/int | **CLOSED = STRICT** (Package B / D-02 ile UYGULANDI) | R-3 deployment early fail (MINOR ACCEPTABLE, beklenen fail-fast). | ❌ NO Silent — STRICT explicit + as-built kod/test kanıtı (§21 MAJOR-2 RESOLVED). |

---

## Summary of Security Risks: **0**
3 riskten 2'si CLOSED CANONICAL ile RESOLVED. 1 tanesi MINOR ACCEPTABLE ACTIVE (safety kazanımı).
HİÇBİRİ: credential sızıntısı / network unsafe exec / allow_short leverage safety violation.
Scope drift YOK. Implementation başlaması için risk engeli: **YOK (FULL PASS risk eligibility).**

# SPEC — S-FND-03: Pytest Infrastructure + Hard Boundary Contract Tests (v1 Safety Gates)

SPEC VERSION: v1.0-impl-ready (2026-09-22)
EPIC: Epic 1 — E-FND (Foundation Stories, completed stories: S-FND-01 @ e1bdff7, S-FND-02 @ d02f58b)
UPSTREAM: E-API MVP Surface @ 80933f8 + S-FND-01 + S-FND-02
AUDIT GATE: Pre-impl (Phase 1 SPEC prep, NO production/test code, 0 existing modify, 0 git ops)
AS-BUILT: S-FND-03 delivered in commit `55fd13e5c794c748b5268bfd891d37968cf407b9` (2026-09-23 22:43:47 +0300) — `10 files changed, 1332 insertions(+), 0 existing modification`. All 10 allowlist files are git-tracked. This document preserves the pre-impl (PLANNED) snapshot; inline `AS-BUILT:` notes record realized deltas (B1/M1–M6). No PLANNED text is deleted.

## §1 — Intent (WHAT not HOW)

MVP v1 boundary güvenliğini her çalıştırmada ve her PR'da kilitli tutacak Pytest altyapısını kurar. Sınır ihlalleri (canlı ağ/anahtarlar/short/max kaldıraç/gerçek emir isimleri) pytest koleksiyon + çalıştırma aşamasında marker ve adanmış tarayıcı suite'leri ile görünür kılınır.

Özgün sahiplik (AD-7 tek yazarlık):
- **S-FND-03 SAHİP:** Pytest marker tanımı/kayıt/doğrulama + PR-gate amaçlı YENİ forbidden-pattern AST/grep tarayıcı suite (F1'..F4').
- **SAHİP DEĞİL:** S-FND-01'e ait `tests/failure/` altındaki F1..F4 mevcut SAFETY CONTRACT testlerinin aynen korunması (§11 Non-goals P-04).

## §2 — Measurable Success (Sayılabilir)

Aşağıdaki 6 sayılabilir koşulun HEPSİ gerçekleşirse hikâye başarılıdır:

M-1 `python -m pytest --markers | findstr /R "contract replay failure_injection"` 3 marker'ı listeler (Exit 0).
M-2 `python -m pytest tests/foundation_sfnd03 -v --tb=short` → S-FND-03 marker doğrulama + PR-gate tarayıcı testlerinin tamamı PASS (0 FAIL, 0 XFAIL/XPASS dışında).
M-3 Herhangi bir test dosyasına yanlış `@pytest.mark.contract` yerine `@pytest.mark.contract_wrong` eklendiğinde → pytest unknown marker uyarısı VERİR veya fail eder (marker kaydı kilitli).
M-4 `pytest.ini` `markers=` alanında 3 zorunlu marker (contract, replay, failure_injection) HARİCİNDE başka custom marker yoktur; gelecekte ek marker ancak OPEN DECISION (OD-01) ile.

> **AS-BUILT (RESOLVED BY TRACEABILITY).** `pytest.ini` `markers=` alanında **7 kayıt** bulunur = S-FND-03 tarafından **EKLENEN 3 marker** (contract/replay/failure_injection) + **P-06** (`pyproject.toml` 0-diff) nedeniyle yeniden kaydedilmesi ZORUNLU olan **4 miras S-FND-01 marker'ı** (F1..F4). Gerekçe: pytest tek config dosyası kullanır ve `pytest.ini` mevcut olduğunda `pyproject.toml [tool.pytest.ini_options]` bloğu geçersiz kalır; `--strict-markers` ile S-FND-01 marker'ları kayıtsız kalamazdı. SFND-03 tarafından eklenen YENİ marker sayısı tam **3**'tür (M-1 sağlanır); toplam kayıt 7'dir. Bu bir requirement değişikliği değil, P-06 + pytest config precedence'ın zorunlu sonucudur.
M-5 PR-gate tarayıcı suite (F1'..F4') çalıştığında: mevcut S-FND-01 `tests/failure/` 7 dosyası ile duplicate çalıştırılmaz, kendi teşhis çıktısını üretir, assertion mesajları exact path+line numarası verir.
M-6 Tüm hikâye 0 existing modification (K0) ile tamamlanır; tests/conftest.py, tests/foundation/conftest.py (S-FND-02), tests/failure/*.py, tests/registry/...test_smdl01_19_safety_boundary.py (S-MDL 01) hiç dokunulmaz.

## §3 — IN / OUT Scope Boundary

### 3.1 IN Scope (S-FND-03 implemente EDER)

| Kategori | İçerik | Kaynak Referans |
|---|---|---|
| Config | Yeni `pytest.ini` dosyası (3 marker kaydı) | EPICS L224 explicit "marker `pytest.ini`" |
| Fixture infra | Yeni test paketi `tests/foundation_sfnd03/` → özel conftest, marker attach doğrulama hook, helpers | Non-goals P-05: existing conftest dokunulmaz, YENİ paket |
| Markers | `@pytest.mark.contract` (sözleşme doğrulamaları), `@pytest.mark.replay` (replay-data bağımlı testler), `@pytest.mark.failure_injection` (arıza enjeksiyonu senaryoları) | EPICS L224 üç marker isimleri |
| PR-gate tarayıcı (F1'..F4') | AST/grep tabanlı, AD-1/AD-12/AD-18/AD-19/AD-20 amaçlı YENİ suite — adlandırma F1',F2',F3',F4' (mevcut S-FND-01 F1..F4 ile karışmaması için prime) | EPICS L225-230 kriterler, F1'..F4' implementasyonu (new, owned by SFND03) |
| Marker verification | Testlerde marker attach olup olmadığını doğrulayan smoke testler (her marker 1 pozitif 1 negatif) | M-3 above |

### 3.2 OUT Scope (S-FND-03 HİÇ implemente ETMEZ)

| Kategori | Sahiplik / Neden |
|---|---|
| Gerçek safety assertion F1..F4 (network blocker fixture, credential actual assert tarayıcı vb.) | S-FND-01 tests/failure/ altındaki 7 dosya. K0 0 diff. |
| Logger/observability altyapısı | S-FND-02, 0 touch |
| Env/klasör ayrımı, INI config safety kilitleri | S-FND-01 |
| Contract schema validation + typed contracts (Pydantic vb.) | S-CON-01 / S-CON-02 downstream |
| Adapter altyapısı, market data contract | E-API + S-CON-01 downstream |
| Herhangi bir production kod (app/...) | Foundation Pytest hikayesi OLDUKÇA test-altyapı odaklı |
| pytest.ini dışında pyproject.toml `[tool.pytest.ini_options]` marker ekleme | pyproject.toml 0 diff kuralı. |
| CI pipeline .github/workflows/ ya da .gitlab-ci.yml yazımı | K0: SPEC izni, explicit OD-02 open |
| S-FND-04+ (Platform Alerting, Persistence, Dashboard UI vb.) | Non-goals P-01 |

## §4 — Upstream Dependencies

| ID | Sahiplik | S-FND-03 için neden gerekli? | Kesin commit SHA |
|---|---|---|---|
| UP-01 S-FND-01 Env Separation | Foundation | `development/test/stg/paper` ortam ayrımı var — marker lar ORTAM AYIRIMI yapmadan tüm env'lerde çalışır; ama pytest.ini markerlarının mevcut env klasörleriyle uyumlu olması S-FND-01'den miras | `e1bdff70134cc5e797e7901a10fe9f28924a5cdc` |
| UP-02 S-FND-02 Observability Hooks | Foundation | PR-gate tarayıcı testleri çalışırken S-FND-02 `ad19_fail_type` label + correlation ID kullanır (mevcut yapıyı tekrar etmez) | `d02f58ba99e57c66172828668a59305c4dae62ac` |
| UP-03 E-API MVP Surface | Platform | E-API mevcut `app/platform/observability/__init__.py` + `metrics.py` 0 diff (S-FND-03 app production dokunmaz) | `80933f8a7feecfbcb63dc3da72b10f7f459baade` |

HARİÇİ BAĞIMLILIK (EXTERNAL DEP): YOK. Stdlib (re, ast, pathlib, json, subprocess pytest dahili). Pytest zaten pyproject.toml'da mevcut — YENİ bağımlılık EKLENMEZ.

## §5 — Downstream Consumers (Tüketen Hikâyeler)

| Tüketici Hikâye | Neden marker / tarayıcıya ihtiyacı var? | EPICS line |
|---|---|---|
| S-CON-01 Canonical Envelope Schemas | `@pytest.mark.contract` = contract testleri etiketlemek için, PR run seçimi `-m contract` | L260 |
| S-CON-02 19 Market/Decision/Portfolio Entity Schemas | Aynı contract marker + marker doğrulaması için; S-FEA-01 FİXTURE yükleme failure injection | L288 |
| S-FEA-01 Deterministic Feature Engine Foundation | `failure_injection` marker ile quality_flags bozuk path testi + `replay` marker ile replay bundle bağımlı koşular | L345 |
| S-REG-01 Market Regime Detection | replay marker (rejimler replay veri üzerinde deterministic) | L370-? (EPICS arama) |
| S-STR-01 Trend/Momentum Strategy | replay + contract marker | L380-? |
| S-RSK-01/02 Risk Engine | failure_injection (risk timeouts) + contract marker | L388-? |
| S-PTR-01 Paper Fill Engine + S-PTF-01/02/03 | replay marker + contract marker | L404-? |
| S-BKT-01/02/03 Backtest | replay marker (hepsi replay bağımlı) | L420-? |
| S-RDH-01/02 Replay Data Pipeline | failure_injection (corrupt bundle testleri) | L434-? |

## §6 — Contracts / Data Types

S-FND-03, dışa açık 3 tip sözleşme tanımlar (stdlib dataclass, 0 pydantic bağımlılık):

> **AS-BUILT (M4/m4 — dosya adı düzeltmesi, DOCS INCORRECT).** PLANNED dosya adı `types.py` idi; teslim edilen (AS-BUILT) dosya **`tests/foundation_sfnd03/_helpers.py`**'dir (533 satır). `types.py` repo'da yoktur. Bu ad düzeltmesi `expected-file-changes.md` N-04 ile uyumludur.

### 6.1 `MarkerCatalog` (enumeration)
```python
# values: "contract" | "replay" | "failure_injection"
# invariant: tam 3 değer, her bir marker pytest.ini [pytest] markers= alanında kayıtlıdır.
```

### 6.2 `PatternScanFinding` (tek bir F1'..F4' scan sonucu)
```python
{
  "rule_id": "F1_PRIME_NETWORK" | "F2_PRIME_CREDSTR" | "F3_PRIME_SHORT_LEV" | "F4_PRIME_REAL_ORDER",
  "severity": "BLOCKER" | "MAJOR" | "MINOR",
  "file_path": "absolute posixlike (pathlib)",
  "line_no": 1-based int,
  "snippet": str  # 80 char max,
  "allowed_owner_paths": ["app/ingest/adapters/", "tests_*/fixtures/"]  # sadece F1', F2' için geçerli
}
```

> **AS-BUILT (M6 — AS-BUILT DRIFT, çözüldü).** Teslim edilen `PatternScanFinding` (`_helpers.py`, frozen dataclass) alan adları PLANNED'dan farklıdır: `rule_id, severity, file, line, snippet, allowlist_hit: bool = False, message: str = ""` (+ `as_tuple()`). PLANNED'daki `file_path`→ AS-BUILT `file`, `line_no`→`line`, `allowed_owner_paths` yerine `allowlist_hit`/`message`. AS-BUILT `rule_id` değerleri (8): `F1P-NET-IMPORT`, `F2P-CRED-LITERAL`, `F3P-SHORT-DIR`, `F3P-LEV-GT1`, `F3P-SYNTAX`, `F4P-REAL-ORDER-DEF`, `F4P-ORDER-MIMIC`, `F4P-REAL-ORDER-REF`. Fonksiyonel sözleşme (deterministik `as_tuple`, sort_keys JSON) korunur.

### 6.3 `PRGateScanReport` (aggregate)
```python
{
  "scan_id": sha256[:16],
  "total_files_scanned": int,
  "findings": list[PatternScanFinding],
  "skipped_allowlist_paths": list[str],
  "summary_counts": {F1':N, F2':N, F3':N, F4':N},
  "pass_fail": bool  # True = no BLOCKER/MAJOR outside allowlist
}
```

> **AS-BUILT (M6 — AS-BUILT DRIFT, çözüldü).** Teslim edilen `PRGateScanReport` (`_helpers.py`, dataclass) alanları: `scan_id: str`, `scanned_files: list[str]`, `findings: list[PatternScanFinding]`, `allowlist_read_errors: list[str]`; ayrıca `passed` (property; BLOCKER yoksa True) ve `deterministic_sha256()` (tam sha256 hexdigest, sort_keys canonical payload). PLANNED'daki `total_files_scanned`→ AS-BUILT `scanned_files` (sayı `len()` ile), `skipped_allowlist_paths`→`allowlist_read_errors`, `summary_counts`/`pass_fail`→ `passed` property. **PLANNED/AS-BUILT'te `schema_version` ve `contract_version` alanları YOKTUR** (bkz. test-plan.md TP-8 düzeltmesi).

Tüm tipler S-FND-02 ile aynı convention: 11 ZORUNLU alan yok, ama JSON serileştirilebilir (sort_keys) ve deterministik şekilde SPEC §7 uyarınca.

## §7 — Deterministic Behavior (Determinizm)

D-1 `pytest.ini` marker listesi: Dosyaya yazılan sırayla (contract → replay → failure_injection) SABİT, alfabetik değil; yine de parser order-independent olsa da yazım sırası canonical.
D-2 Tarayıcı scan sonuçları: AST parse sırası dosya listesi `pathlib.Path.rglob(pattern)` ardından `sorted(paths)` kesin; keşif sırası DOS/Windows klasör sırasına BAĞLI DEĞİL.
D-3 PatternScanFinding karşılaştırması: (rule_id, file_path, line_no) tuple anahtarı üzerinden duplicate detection, sort edildikten sonra set benzerliği.
D-4 Hashing scan_id: `hashlib.sha256(("\n".join(sorted(per_file_inputs))).encode()).hexdigest()[:16]` — aynı repo state için scan_id 10x aynı.
D-5 Marker catalog enumeration: set sırasını kullanma; list ORDER = MarkerCatalog sınıfı field order.
D-6 Rastgele/çevre bağımlılığı: `os.environ` OKUMAZ (hariç OD-03 karar verene kadar PYTEST_DISABLE_PLUGIN_AUTOLOAD default okunmaz).

Determinism için canonical test koşulu: Her D senaryosu 10 kez çalıştırıldığında tam output tuple (liste, report hash, exit code) `len(set)==1`.

## §8 — Fail-Closed Behavior (FC-01..10 Benzeri 8 Kural)

FC-1 Marker kaydında EXTRA 4. marker yanlışlıkla eklenirse → pytest --markers sonrası testlerde "unknown marker list diff" test FAIL olur (M-3 M-4).
FC-2 PR-gate scan path allowlist okunamaz → scan BLOCKED olur, pass_fail=False (sessizce PASS dönmez).
FC-3 `ast.parse()` SyntaxError (bozuk Python dosyası, ama biz testler 3. party import etmiyoruz) → SyntaxError SKIP değil finding olarak F1'..F4' için ayrı raporlama, severity MAJOR, scan tamamlanır, sonraki dosyalar devam eder.
FC-4 Bir pattern regex (F2') derlenemiyorsa → pytest koleksiyon aşamasında FAIL, marker testleri çalıştırmadan önce koleksiyon abort; düzeltme zorunlu.
FC-5 `pytest.ini` 3 markerdan biri yazım hatası ise (ör "faillure_injection") → `python -m pytest tests/foundation_sfnd03/test_markers_catalog.py` FAIL olur exact mismatch mesajı.
FC-6 Marker decorator yanlış yazılırsa → pytest collection warning/error, S-FND-03 marker doğrulama testi bu yanlışı yakalamak için explicit negatif parametre.
FC-7 Test runner subprocess çağırdığında (AST scan isolation için) stdout/stderr okuma timeout → finding BLOCKER "scan_runner_timeout", session fail.
FC-8 S-FND-01 mevcut `tests/failure/*.py` F1..F4 testleri ile SFND03 F1'..F4' scan arasında assertion mesajı ve sahiplik ayrımı net yapılır; duplicate assertion varsa negatif test fail olur (Sahplik ayrımı zorunlu, §3.1).

## §9 — Security / Safety (v1 Hard-Boundary Uyumlu)

S-1 F2' PRIME scan "api_key" "secret" benzeri hassas LITERAL substringler için — S-FND-02 concat-split pattern uygulayan production/test kodu FALSE POSITIVE VERMEMELİDİR (helper false_positive_safelist EXPLICIT tanımlanır).
S-2 F3' PRIME Short/Leverage tarayıcı: sadece `app/contracts/`, `app/risk/`, `app/simulation/`, `app/strategies/` domain klasörlerini tarar; `tests/` ya da `configs/` short parametreli fixture isimlerini rapor ETMEZ.
S-3 F4' GERÇEK EMİR isim tarayıcı: "send_real_order", "place_order_on_exchange" string — isimleri test fonksiyon isimlerinde doğruluk için değil, sadece production app/... altında BLOCKER; tests/ altında MINOR (sahiplik işareti).
S-4 F1' NETWORK import tarayıcı: import X, from X import Y olmak üzere; `app/ingest/adapters/` ve `tests_*/fixtures` SAFE, diğer app/ altında BLOCKER, test klasörlerinde MINOR.
S-5 Credential plaintext: PR-gate scan hiçbir durumda VALUE kısmını stdout/stderr loglamaz, sadece (dosya, satır, maskeli 0******) gösterir. Hassas string keyler F2' scan içinde S-FND-02 redaction pattern kopyalanmaz (open gap G-3).
S-6 Pytest 3rd party plugin otomatik yüklemesi (pytest-django, vb.): default bu hikâyede DEĞİŞTİRİLMEDİ (OD-03). Plugin injection güvenlik açığına karşı marker testleri STDLIB ve mevcut pytest.mark dışı özelliği kullanmaz.

## §10 — Audit / Evidence

A-1 Her çalışan `tests/foundation_sfnd03/test_sfnd03_prgate_report.py` çıktısında `PRGateScanReport` JSON dosyası yazılır (deterministic sort_keys). Testte bu raporun SHA hash 10x aynı.
A-2 Marker doğrulama testi: `test_markers_exact_3_in_inventory.py` pytest --markers subprocess çıktısını parse eder ve exact 3 marker listesiyle karşılaştırır (extra marker MAJOR fail).
A-3 Sahplik ayrımı kanıtı: `test_sfnd03_preserves_fnd01_ownership_separation.py` → tests/failure/ klasöründeki mevcut 7 F dosyasını listeler ve SFND03 F1'..F4' testlerinin onları IMPORT ETMEDİĞİNİ (AST import graph) ispatlar.
A-4 0 existing modification kanıtı (implementation audit phase): `git diff HEAD --stat -- tests tests/conftest.py tests/foundation tests/failure` BOŞTUR.

> **AS-BUILT (M5 — DOCS INCORRECT, çözüldü).** A-1/A-2/A-3'te atıf yapılan test dosya adları repo'da **YOKTUR** (phantom); gerçek eşlemeler (onaylanmış eşdeğerlik, `git ls-files` + collected doğrulaması):
> - **A-1 →** `tests/foundation_sfnd03/test_sfnd03_determinism_and_audit.py::TestDeterminism10x::test_D1_report_sha256_unique_set_len_one` (+ `test_D6_deterministic_dumps_same_across_10_runs`). **Not:** AS-BUILT'te testler **diske JSON dosyası YAZMAZ**; determinizm kanıtı in-memory `run_full_scan(...).deterministic_sha256()` çıktısının 10× `len(set)==1` olmasıyla sağlanır (`_helpers.PRGateScanReport.deterministic_sha256`).
> - **A-2 →** `tests/foundation_sfnd03/test_sfnd03_markers_catalog.py::TestIniMarkersRegistered` (`test_pytest_ini_has_three_contract_replay_failure_injection`, `test_cli_registered_markers_contains_catalog`, `test_sfnd01_markers_preserved`).
> - **A-3 →** `tests/foundation_sfnd03/test_sfnd03_determinism_and_audit.py::TestAuditAndOwnership::test_A1_ownership_sfnd03_no_imports_of_failure` (+ `conftest.sfnd03_ownership_invariant_count` fixture).

## §11 — Non-Goals (11 Maddelik Lean Kernel List — NG)

P-01 S-FND-04+ (Platform Alerting, Persistence, Deployment, Dashboard UI) hiçbir şey implemente EDİLMEZ.
P-02 S-FND-01 tests/failure/* 7 dosyanın yeniden yazılması veya assertion güncellenmesi — K0 yasak.
P-03 CI pipeline (Github Actions, GitLab CI) konfigürasyonu yazmak — OD-02 açık karar.
P-04 S-FND-01 F1..F4 "actual" safety testlerinin yerine SFND03 F1'..F4' koymak — Aksine iki ayrı katman: (1) S-FND-01 RUNTIME assertion / fixture block, (2) SFND-03 STATIC/COLLECTION TIME scan + marker yönetim. Aynı isimler olmaz (prime ' eklenir).
P-05 Existing tests/conftest.py (S-FND-01 offline_network_blocker) veya tests/foundation/conftest.py (S-FND-02) dosyalarına import / fixture ekleme — K0 0 diff; YENİ `tests/foundation_sfnd03/conftest.py` kullanılır.
P-06 Pytest.ini dışında pyproject.toml `[tool.pytest.ini_options]` alanını değiştirmek / marker eklemek — pyproject 0 diff kuralı.
P-07 Yeni bağımlılık eklemek (rich, pydantic, tomllib 3.11 sonrası stdlib tomllib eğer yoksa ConfigParser INI kullanılır — stdlib).
P-08 Production app/ koduna herhangi bir şey eklemek — SFND03 PURE infra/test.
P-09 SLO / Retention / Threshold / Algorithm / Security Guarantee uydurmak — SPEC 9 bölümünde olmayan herhangi bir eşik değeri uydurulmaz.
P-10 Gelecekte S-FND-04 alerting için event bus kullanımı — bu kapsamda YOK.
P-11 8 tane miras alınan source gap (Vault Sec, registry immut hash, audit rotation, OTel, F1-F4 redefinition, remote write, dashboard UI, retention) — SPEC §18'de GAPS olarak korunur, bu hikâye tarafından kapatılmaz.

## §12 — Hard-Red (HRC-1..8 — 8 Kural)

HR-1 **K0 (0 Existing Modify):** Mevcut **1,720** git-tracked dosya (`git ls-files` = 1720; app/ 125, tests/ 412, configs/ 5), tests/conftest.py, tests/foundation/conftest.py (S-FND-02), tests/failure/*, tests/registry/...test_smdl01_19_safety_boundary.py, pyproject.toml, configs/*.ini, app/ production S-FND-01/02/E-API aittir. S-FND-03 bu dosyaların HİÇBİRİNİ DEĞİŞTİRMEZ (0 byte diff). AYRINTI: EX-01 (pytest.ini NEW → existing olarak kabul etmiyoruz, zaten YOK). EX-02 YOK. Yani EXCEPTION LIST EMPTY DEFAULT olarak kabul edilir (tüm NEW). **AS-BUILT (m1):** önceki "1400+" doğrulanmamış tahmindi; gerçek baseline 1,720 tracked dosya.
HR-2 **No Network Live:** SFND03 test/infra kodunda `requests/httpx/aiohttp/websocket/urllib/socket` importları YOKTUR (sadece tarayıcı FINDS them, kendi kendine AĞ KULLANMAZ).
HR-3 **No Credential Bypass:** F2' scan sonuçları credential değerini asla basmaz; `REDACTED:sha256[:6]` gibi maskeli.
HR-4 **No Registry Mutation:** app/governance/registry yazma YOK (P-08 production kod YOK).
HR-5 **Stdlib Only:** 12 stdlib. Pytest (mevcut) + stdlib (ast, re, pathlib, hashlib, json, subprocess, dataclasses, typing, os, sys, collections, itertools). 3. parti YENİ bağımlılık YOK (HR-5 ihlal → BLOCKER).
HR-6 **No Unsafe Dynamic Exec:** `eval/exec/pickle/yaml.load(pyyaml)/subprocess shell=True` YOK. subprocess `capture_output=True, text=True, shell=False` yalnızca `pytest --markers` çağrısında KULLANILIR (güvenli arg listesi).
HR-7 **Completed-Story 0 Diff Continue:** SFND02 commit (`d02f58b`) sonrası production app/platform/observability **8** NEW dosya + **6** test (tests/foundation/) = **14 dosya** — S-FND-03 tarafından 0 diff.
> **AS-BUILT (M3 — DOCS INCORRECT, çözüldü).** `git show --stat d02f58b` = `14 files changed, 2020 insertions(+)` (8 app/platform/observability + 6 tests/foundation). Önceki "9 production + 6 test = 15" ifadesi aritmetik olarak yanlıştı; gerçek envanter 8+6=14. `hard-red.md` HR-7 de aynı kanıta göre düzeltildi.
HR-8 **Registry General Write No:** AD-23 registry komutları dışında YOK.

## §13 — Acceptance Criteria (24 AC, Tamamlayıcı: acceptance-criteria.md)

24 AC listesi: companion acceptance-criteria.md dosyasına taşınmıştır (SP05-3 prensibi: tek yer, tek sayım). Aşağıda başlıklar:

> **AS-BUILT (M1/M5 — DOCS INCORRECT, çözüldü).** acceptance-criteria.md'de düzeltilen 3 başlık burada da geçerlidir: (a) **AC-02** — S-FND-03'e ait marker sayısı 3'tür, ancak pytest.ini toplam 7 kayıt içerir (3 + 4 miras F1..F4); (b) **AC-21** — kaynak referansı "SPEC §21" DEĞİL, SPEC §13/§4 UP-02'dir (SPEC yalnız §1..§20 içerir); (c) **AC-24** — kaynak referansı "SPEC §13" DEĞİL, SPEC §14 DoD-3'tür; "1888+" stale planning snapshot'ıdır (repo-wide collected = 6,678).

AC-01 pytest.ini dosyası mevcuttur ve [pytest] section markers= 3 zorunlu marker içerir.
AC-02 `pytest --markers` çıktısında contract/replay/failure_injection exact listelenir, başka custom marker yoktur.
AC-03 MarkerCatalog 3 değer exact = pytest.ini kayıtlarıyla 1-1 match.
AC-04 Yanlış marker `contract_wrong` → pytest unknown marker test FAIL.
AC-05 F1' prime network scan: app/ modül importlarını listeler ve app/ingest/adapters HARİCİ app/ pathlerinde `requests` BLOCKER finding üretir.
AC-06 F1' scan: app/ingest/adapters/*.py import = allowed, finding üretmez.
AC-07 F2' prime credential string scan: S-FND-02 concat-split pattern uygulanan stringler false positive üretmez.
AC-08 F2' scan: test fixture yolu `tests_fixtures/api_keys_dummy.json` gibi ALLOWLISTED path = finding üretmez.
AC-09 F3' prime short/leverage tarayıcı: app/contracts/ PaperOrder direction="short" BLOCKER (v1 long-only).
AC-10 F3' scan: tests/ altında test fonksiyon isimlerinde "short" substringi → finding YOK (S-2 safety).
AC-11 F4' prime gerçek emir isimleri: app/ altında "send_real_order" function tanımı BLOCKER.
AC-12 F4' scan: tests/ altında aynı isim mock function = MINOR, not blocker.
AC-13 PatternScanFinding JSON serialize sort_keys ile 10x deterministik aynı hash.
AC-14 PRGateScanReport toplam scan dosya sayısı deterministic (sorted path).
AC-15 Marker `contract` decorator attach → test_* fonksiyonunda marker item.key == "contract" doğrulanır.
AC-16 Marker `replay` attach → item.key "replay"; failure_injection için aynı.
AC-17 Sahplik ayrımı: SFND03 F1'..F4' dosyaları AST import graph'ta tests/failure/*.py IMPORT ETMEZ.
AC-18 0 existing mod: implementation sonrası git diff HEAD --stat tests tests/conftest.py tests/foundation tests/failure pyproject.toml configs app/ = EMPTY.
AC-19 Determinism: scan report hash len(set(runs_10))==1.
AC-20 Fail-closed: ini parse hatası → testler FAIL, sessizce continue ETMEZ.
AC-21 S-FND-02 correlation label kullanımı: PRGateScanReport findinglerde opsiyonel correlation_id eklenebilir (mevcut yapıyı tekrar etmez).
AC-22 FC-8 duplicate assertion yok: her bir finding sadece bir kere raporlanır (tuple key dedup).
AC-23 New folder tests/foundation_sfnd03 import edilebilir (pytest koleksiyonu).
AC-24 Regression: mevcut test suite `python -m pytest -q` fail olmaksızın çalışır (S-FND-03 yeni dosyaları mevcut suite ihlal ETMEZ). Repo-wide collected = 6,678 (AS-BUILT; önceki "1888+" stale).

## §14 — Definition of Done (DoD, companion dod.md detaylı)

DoD-1 **1 CONFIG + 9 TEST = 10** (CONFIG: `pytest.ini`; TEST paketi `tests/foundation_sfnd03/`: `__init__.py`, `conftest.py`, `_helpers.py` + 6 `test_*.py`) exact allowlist companion expected-file-changes.md §4 listesi ile 1:1 match.
> **AS-BUILT (M2 — DOCS INCORRECT, çözüldü).** Önceki "3 dosya CONFIG ... 8 TEST" ifadesi hatalıydı; DoD-1 dosya listesi gerçek allowlist ile 1 config + 9 test = 10'dur (bkz. §16 ve expected-file-changes.md §6 AS-BUILT VERIFICATION).
DoD-2 Yeni testler S-FND-03 OWNED ACs PASS (0 FAIL).
DoD-3 Mevcut regression PASS (yeni dosyalar 0 regression).
> **AS-BUILT (M1/M2 — DOCS INCORRECT, çözüldü).** Repo-wide `python -m pytest --collect-only -q` = **6,678 test** toplanır; önceki "1888+" stale planning snapshot'tır. Bu turda YALNIZCA `--collect-only` çalıştırıldı; runtime PASS/FAIL sayısı DOĞRULANMADI (kanıtsız PASS iddiası üretilmez).
DoD-4 0 existing modify (git diff HEAD HEAD~1 --stat = Sadece NEW 10 dosya).
DoD-5 Marker sayımı 3.
DoD-6 Sahplik ayrımı (P-04): S-FND-01 F1..F4 tests/failure/ import graph 0 bağlantı.
DoD-7 Hard-red 8/8 HRC.
DoD-8 Determinism: 6 D senaryosu × 10x len(set) = 1.
DoD-9 Fail-closed: 8 FC test PASS.
DoD-10 Audit: A-1..A-4 kanıtları mevcut.

## §15 — Test Plan (TP-1..TP-8, companion test-plan.md)

TP-1 Marker Smoke — 10 test: AC-01,02,03,04,15,16,23,18 subset (dosya var), 23 import.
TP-2 F1' Network Scan Prime Static — 8 test: AC05,06 + 2 edge empty dir, 2 nested, 2 adapter vs non-adapter.
TP-3 F2' Credential String Prime — 8 test: AC07 concat false_positive, 08 fixture allow, +2 negative normal strings BTCUSDT, +1 mixed, +1 nested dict, +1 regex örn, +1 no credential.
TP-4 F3' Short Leverage Boundary Prime — 6 test: AC09,10 + 2 leverage>1 domain blocked, 2 configs/test allowed.
TP-5 F4' Order Function Name Prime — 6 test: AC11,12 + 2 paper_order allowed, 2 test mock func minör, 1 empty.
TP-6 Determinism 10x — 6 group (D1..D6).
TP-7 Fail-Closed 8 Kural — 8 test (FC-1..8).
TP-8 Ownership/Audit Evidence — 4 test (A-1,2,3,4 subset AC-17,18,13,14).

TOTAL 56+ AC parametreleri → planlanan "80+" test. **AS-BUILT (M1 — DOCS INCORRECT, çözüldü):** runtime `python -m pytest tests/foundation_sfnd03 --collect-only -q` = **85 collected** (statik `def test_` = 61); parametrize genişlemesi (F2' 7→22, determinism 21→30) nedeniyle collected ≠ statik sayı. Ayrıntı: test-plan.md.

## §16 — Expected File Changes (§4 companion expected-file-changes.md)

Companion expected-file-changes.md §4 listesi AUTHORITATIVE. Özet (10 total NEW file, 0 existing modification, EX LIST EMPTY):
NEW TEST INFRA (1 pytest.ini)
NEW TEST PACKAGE (9 test files) = 10 total NEW. (§4 companion: N-01..N-10 list.)

## §17 — Open Decisions (OD)

OD-01 Gelecekte 4. marker eklenmesi (ör `@pytest.mark.performance`): Şu an YOK. Yeni marker açmak için PRD change request + SPEC update gerekir. Default M-4 uyarınca fail olur.
OD-2 CI pipeline (Github Actions/GitLab CI) `-m contract and not replay` gibi select komutu yazımı: şu an SFND03 scope dışı. Çalışma: user pipeline ekleyebilir. SFND03 markerları doğru şekilde kayıtlıysa `-m` çalışır, CI config SFND03 tarafından yazılmaz.
OD-3 PYTEST_DISABLE_PLUGIN_AUTOLOAD: 3rd party plugin injection riski. Şu an dokunulmuyor (pytest default). Eğer plugin ile marker collision olursa test fail olur, bu OD kapatılır.
OD-4 Tomllib (Python 3.11+) vs ConfigParser INI: pytest.ini INI format → ConfigParser stdlib Python 3.8+ uyumlu, tercih edilir (tomllib 3.11 sonrası stdlib, version restriction risk yok, ConfigParser kullan).

## §18 — Source Gaps (8 Adet MİRAS — KAPATILMAZ)

G-1 Vault / Secrets Manager integration: S-FND-03 YÖNETMEZ. Future SEC-01 story.
G-2 Registry immutable hash chain audit trail: AD-23 + Model Registry future, SFND03 yok.
G-3 Unified Redaction S-FND-02 redaction pattern import edilerek paylaşılabilir — §9 S-5 not ediyor, şu an YOK duplicate minimal risk kabul (open gap G-3). Gelecekte foundation/shared REDACTION lib S-FND-04+ olabilir.
G-4 OTel / Prom exporter remote write: observability export E-API S-FND-02 gap, SFND03 yok.
G-5 F1-F4 CONTRACT redefinition — S-FND-01 4 safety testleri redefine: P-04, NON-GOAL, açık GAP tutulur.
G-6 Dashboard UI: SFND03 marker/pr-gate tarayıcı çıktıları dashboard gelecekte tüketebilir, şu an JSON report export eder.
G-7 Data retention / scan report arşivleme: retention policy uydurulmaz (P-09).
G-8 Audit rotation / append-only log: SFND03 testi JSON yazar, rotation yok.

## §19 — Current vs Future Boundary

CURRENT (S-FND-03 v1):
- 3 marker (contract, replay, failure_injection)
- 4 Prime PR-gate scan (F1'..F4')
- Local pytest.ini — CI pipeline YOK (P-03)
- Stdlib only, pytest existing dep, 0 Yeni dep

FUTURE (S-FND-04+ veya sonraki DECISIONS):
- Yeni markers OD-01
- CI pipeline kurulum (OD-02)
- Plugin sandboxing OD-03
- Unified redaction library (G-3) kapatılması
- Sonraki F5'..FN' prime scans (registry mutation, champion bypass vb.)

## §20 — Architecture Traceability (AD → CAP mapping companion)

Companion architecture-traceability.md → **15 CAP** (CAP-1..CAP-15): 9 AD bağlaması (AD-1, AD-7, AD-10, AD-11, AD-12, AD-17, AD-18, AD-19, AD-20) + 5 NFR (NFR-002 reliability, NFR-004 observability, NFR-006 integrity, NFR-007 reproducibility determinism, NFR-008 security) + CAP-15 (Marker Stability Contract, ekstra NFR) = **total 15 CAP mappings** for SFND03 (see companion file matrix table).
> **AS-BUILT (M4 — DOCS INCORRECT, çözüldü).** Companion dosyada CAP satırı sayısı = 15 (doğrulandı); önceki "14 CAP matrix ... total 15" iç tutarsızlığı giderildi (9 AD + 6 NFR = 15).

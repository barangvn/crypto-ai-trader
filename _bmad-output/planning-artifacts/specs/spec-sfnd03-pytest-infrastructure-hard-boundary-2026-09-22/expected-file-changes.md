# Expected File Changes — S-FND-03

AUTHORITATIVE SAYIM: **TOPLAM 10 DOSYA.**
- NEW Config (pytest.ini): 1
- NEW Test package under `tests/foundation_sfnd03/`: 9
  - `__init__.py` + conftest.py (2)
  - 4 PRIME scan test dosyaları (F1',F2',F3',F4') + marker_catalog test + determinism/failclose audit (4 + 2 = 6 test_*py)
  - Yardımcı `_helpers.py` (1) — Tarama yardımcıları (AST/grep/parse)
  - TOTAL: 2 + 6 + 1 = 9 (test paketi)
- Existing file modifications: **0 (EXCEPTION LIST BOŞ — EX-01..EX-N YOK, OD kararı EX YOKTUR)**

> **AS-BUILT STATUS (verified).** Bu bölüm PLANNED (pre-impl, 2026-09-22) planını korur. Gerçek teslimat: commit **`55fd13e5c794c748b5268bfd891d37968cf407b9`** (`feat: implement S-FND-03 foundation test contracts`, 2026-09-23 22:43:47 +0300), **10 files changed, 1332 insertions(+), 0 existing modification**. Allowlist'teki 10 dosyanın TAMAMI artık git-tracked (`git ls-files` doğrulandı). Bu nedenle aşağıdaki "NEW/untracked" ifadeleri PLANNED durumuna aittir; AS-BUILT durumda 10/10 dosya tracked'dır. Ayrıntı için §6.

---

## §2 — Conditional Exceptions (EX list) — EMPTY
**Hiçbir existing dosya modifiye EDİLMEZ.**
- EX-01 (modify pyproject.toml [tool.pytest.ini_options]): DROPPED. Yeni pytest.ini file ile çözülür (0 existing mod).
- EX-02 (append marker fixture to root tests/conftest.py): DROPPED. Yeni conftest under NEW `tests/foundation_sfnd03/` → kendi fixture ve hook larını orada tanımlar.
- EX-03 (import test_failure 7 file for reuse): DROPPED. Non-goals P-04. Sahplik ayrımı.

## §3 — Debug / Temp / Generated — ALLOWED DEĞİL
Aşağıdaki dosyalar NEW/EXISTING olamaz:
- `tests/__pycache__/`, `*.pyc`, `*.pyo`, `.pytest_cache/` (generated default, .gitignore tarafından zaten ignore — bu dosyalar allowlist sayılmaz, repo dışındadır)
- `audit_scan_temp.json`, `scan_report_*.bak` (temp dosyalar)
- fixture üretmek için `tests_fixtures/sfnd03_*.py` dışında generated herhangi bir şey

## §4 — CANONICAL ALLOWLIST (N-01..N-10) — 10 NEW
| N-Id | Path (relative repo root) | Role | Üretim/Test | Not |
|---|---|---|---|---|
| N-01 | `pytest.ini` | Config: SFND-03 3 marker kaydı (pytest.ini toplam 7 kayıt: 3 SFND-03 + 4 miras SFND-01 F1..F4) + `--strict-markers` | Config (test altyapı) | PLANNED: mevcut YOKTU. **AS-BUILT:** `55fd13e`'de oluşturuldu ve git-tracked. |
| N-02 | `tests/foundation_sfnd03/__init__.py` | Test package marker (boş 0 content veya marker docstring) | Test | NEW |
| N-03 | `tests/foundation_sfnd03/conftest.py` | S-FND-03 özel pytest hooks (pytest_configure, collection custom markers doğrulaması, prgate scan fixture) | Test Fixture (AD-20) | NEW. Mevcut root conftest / tests/foundation/conftest dokunulmaz. |
| N-04 | `tests/foundation_sfnd03/_helpers.py` | PR-gate scanner helpers: AST + regex scanner, PatternScanFinding / PRGateScanReport dataclass, sort/parse/hash yardımcıları | Test Library (shared code) | NEW (TEST yardımıcı, prod değil. Stdlib only.) |
| N-05 | `tests/foundation_sfnd03/test_sfnd03_markers_catalog.py` | TP-1 Marker smoke/catalog/negatif typo/strict marker AC-01..04/15/16/23 | Test (marker) | NEW |
| N-06 | `tests/foundation_sfnd03/test_sfnd03_f1prime_network.py` | TP-2 F1' prime network scan 12 test | Test (scan) | NEW |
| N-07 | `tests/foundation_sfnd03/test_sfnd03_f2prime_credentials.py` | TP-3 F2' credential string scan 14 test (concat split pattern false positive guard) | Test (scan) | NEW |
| N-08 | `tests/foundation_sfnd03/test_sfnd03_f3prime_short_lev.py` | TP-4 F3' short/leverage 10 test (domain only) | Test (scan) | NEW |
| N-09 | `tests/foundation_sfnd03/test_sfnd03_f4prime_order_names.py` | TP-5 F4' gerçek emir isimleri 10 test | Test (scan) | NEW |
| N-10 | `tests/foundation_sfnd03/test_sfnd03_determinism_and_audit.py` | TP-6 Determinism 6×10x + TP-7 FC 8 + TP-8 Audit/ownership 6 (combined — veya N-10a/N-10b olarak ayrı. NOT: SAYIM KILIDI. Yukarı 9 tane test var (N05..N10 = 6 test dosyası + N02/N03/N04 = 3 → 9 doğru. N10 = determinism/fail/audit birleşik, 6 tane test dosyası sayımı: 05 marker, 06 F1', 07 F2', 08 F3', 09 F4', 10 det/fc/audit = 6 test dosyası. 6+3+1(N01 ini) = 10. TAM) | Test (audit) | NEW |

## §5 — SANITY COUNT
1 pytest.ini (N01) + 9 `tests/foundation_sfnd03/` dosyaları (N02..N10) = **10 NEW**. 0 existing modify. Sayı toplam: **10/10**.

---

## §6 — AS-BUILT VERIFICATION (evidence, 2026-10-25)

**Commit:** `55fd13e5c794c748b5268bfd891d37968cf407b9` — `feat: implement S-FND-03 foundation test contracts` (2026-09-23 22:43:47 +0300) — `10 files changed, 1332 insertions(+)`.

**`git ls-files` (tracked) doğrulaması — 10/10 tracked:**

| N-Id | Path (tracked) | AS-BUILT satır | Collected test | Not |
|---|---|---|---|---|
| N-01 | `pytest.ini` | 13 | — | 7 marker kaydı |
| N-02 | `tests/foundation_sfnd03/__init__.py` | 6 | — | package marker |
| N-03 | `tests/foundation_sfnd03/conftest.py` | 96 | — | 5 session fixture + `pytest_collection_modifyitems` |
| N-04 | `tests/foundation_sfnd03/_helpers.py` | 533 | — | `MarkerCatalog`, `PatternScanFinding`, `PRGateScanReport`, 8 rule_id, `run_full_scan` |
| N-05 | `tests/foundation_sfnd03/test_sfnd03_markers_catalog.py` | 93 | 12 | |
| N-06 | `tests/foundation_sfnd03/test_sfnd03_f1prime_network.py` | 80 | 8 | |
| N-07 | `tests/foundation_sfnd03/test_sfnd03_f2prime_credentials.py` | 122 | 22 | parametrize genişlemesi |
| N-08 | `tests/foundation_sfnd03/test_sfnd03_f3prime_short_lev.py` | 110 | 6 | |
| N-09 | `tests/foundation_sfnd03/test_sfnd03_f4prime_order_names.py` | 79 | 7 | |
| N-10 | `tests/foundation_sfnd03/test_sfnd03_determinism_and_audit.py` | 200 | 30 | 21 `def test_` (D1×10 parametrize + FC + A) |
| | **TOPLAM** | **1332** | **85** | `python -m pytest tests/foundation_sfnd03 --collect-only` |

**Bulgular:**
- **B1-A (AS-BUILT DRIFT, çözüldü):** N-01 "mevcut YOKTUR" ifadesi PLANNED durumdur; AS-BUILT'te `pytest.ini` `55fd13e`'de oluşturulup tracked olmuştur.
- **B1-B (DOCS INCORRECT, çözüldü):** N-06..N-09 "Role" kolonundaki PLANNED test sayıları (12/14/10/10) plan değerleridir; AS-BUILT collected sayıları 8/22/6/7'dir. Dosya (file) sayımı 10/10 korunur — yalnız test-case sayıları farklıdır.
- **Dosya sayımı doğru:** 10/10 tracked, 0 existing modification. Bu belgenin AUTHORITATIVE sayımı geçerlidir.

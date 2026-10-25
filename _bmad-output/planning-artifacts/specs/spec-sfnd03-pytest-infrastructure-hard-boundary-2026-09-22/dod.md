# Definition of Done — S-FND-03 (DoD-1..10)

| DoD # | Madde | Ölçüm Kriteri | Kabul Edilemez Durum |
|---|---|---|---|
| DoD-1 | Allowlist file count match | `expected-file-changes.md §4` NEW=10 (1 pytest.ini + 9 tests under foundation_sfnd03/). Toplam 10. AS-BUILT: 10/10 dosya `55fd13e`'de git-tracked. | 10 dan az veya fazla; existing dosya M sayısı 1+. |
| DoD-2 | 24 AC Executable PASS | `python -m pytest tests/foundation_sfnd03 -v --tb=no` 24 AC karşılayan test suite 0 FAIL. AS-BUILT: collected = 85 (önceki "80+" planning tahmini). | 1+ AC FAIL (XFails EXCEPT if explicitly AC tagged XFAIL explicit. |
| DoD-3 | Regression No New Failure | Toplam regression (S-FND-01, S-FND-02, E-API, Contracts, Registry, Eval/Gate/Rollback/CAP5, Risk, BKT smoke) — RUN exit code 0, mevcut SKIP/XFAIL/XPASS sayıları değişmeden. AS-BUILT: repo-wide collected = 6,678; önceki "27 SKIP / 1 XFAIL / 1 XPASS" sayıları doğrulanmamış planning snapshot'ıdır (bu turda yalnız `--collect-only` çalıştırıldı). | 1+ yeni FAIL veya Exit !=0. |
| DoD-4 | 0 Existing Modify (K0 HR-1) | `git diff HEAD~1 --stat -- tests tests/conftest.py tests/foundation tests/failure tests/registry tests/api tests/simulation tests/risk tests/contracts tests/backtest pyproject.toml configs/*.ini app/platform app/contracts app/risk app/simulation app/strategies app/features app/regime app/processing app/ingest app/governance app/proof` BOŞTUR, sadece NEW dosyalar görünür. | 1+ existing dosya M/|
| DoD-5 | Marker Count Exact 3 | `python -m pytest --markers | grep -E "^\s*contract|^\s*replay|^\s*failure_injection" | wc -l == 3`. AS-BUILT: S-FND-03'e ait 3 marker korunur; pytest.ini TOPLAM 7 kayıt içerir (+4 miras S-FND-01 F1..F4, P-06 zorunluluğu). | 4+ veya 2- S-FND-03 marker. |
| DoD-6 | Ownership Separation Invariant | AST import graph: `tests/foundation_sfnd03` test modüllerinden `tests.failure.*` import eden modül sayısı 0. | Bir test dosyası tests/failure içinden import ederse BLOCKER. |
| DoD-7 | Hard-red 8/8 HRC | Audit section Hard-red 8 madde 8/8 PASS. | 1+ HRC fail (özellikle HR-5 stdlib-only / HR-6 unsafe exec). |
| DoD-8 | Determinism 10× All Groups | D1 marker list sırası D2 dosya tarama D3 findings tuple D4 report_hash D5 MarkerCatalog enum sırası D6 pytest.ini parse — 6 grup, her grup 10× `len(set(outputs)) == 1`. | Herhangi bir senaryoda len(set) ≥2. |
| DoD-9 | Fail-closed 8/8 | FC-1..FC-8 8 test 8/8 PASS. | 1+ FC FAIL. |
| DoD-10 | Audit Evidence Closed | A-1 JSON report, A-2 3 marker exact parse, A-3 ownership import graph, A-4 0 existing diff 4/4 kanıt mevcut. | 1+ evidence eksik. |

---

## AS-BUILT Reconciliation Notları (Görev H)

> Kanıt: commit `55fd13e5c794c748b5268bfd891d37968cf407b9` (10 files, 1332 insertions, 0 existing modification); `git ls-files`; `python -m pytest tests/foundation_sfnd03 --collect-only` = 85.
>
> - **DoD-1 (M2):** doğru liste 1 CONFIG (`pytest.ini`) + 9 TEST (`__init__.py`, `conftest.py`, `_helpers.py`, 6 `test_*.py`) = 10. SPEC §14'teki eski "3 dosya CONFIG ... 8 TEST" ifadesi düzeltildi; dod.md DoD-1 zaten doğruydu ve AS-BUILT notuyla doğrulandı.
> - **DoD-2 (M1):** "80+" planning tahminidir; AS-BUILT collected = 85. Runtime PASS sayısı bu turda doğrulanmadı.
> - **DoD-3 (M2):** "27 SKIP / 1 XFAIL / 1 XPASS" doğrulanmamış planning snapshot'ıdır; repo-wide collected = 6,678.
> - **DoD-4 (B1):** "sadece NEW dosyalar görünür" ifadesi as-built'de geçerlidir; ancak 10 dosya untracked değil, `55fd13e`'de git-tracked'dır.

# Acceptance Criteria — S-FND-03 (24 AC, 1-source)

**CANONICAL SAYIM:** 24 AC. Audit aşamasında "24/24 executable PASS" koşulu zorunlu.

| AC | Başlık (Pass When = TRUE) | Kaynak Bağlama | Ölçüm Testi (TP) |
|---|---|---|---|
| AC-01 | `pytest.ini` mevcut, içinde `[pytest]` bölümü + `markers =` satırı vardır | SPEC §3.1, EPICS L224 | TP-1 T01 |
| AC-02 | `markers=` alanında S-FND-03'e ait tam 3 marker listelenir: contract, replay, failure_injection. Sıra contract→replay→failure_injection'dır. pytest.ini TOPLAM 7 kayıt içerir (3 S-FND-03 + 4 miras S-FND-01 F1..F4; P-06 + pytest config precedence) | SPEC §2 M-4, §7 D-1 | TP-1 T02 |
| AC-03 | Python `MarkerCatalog` enum/liste değerleri tam 3 adettir ve pytest.ini kayıtlarıyla birebir aynıdır (case-sensitive) | SPEC §6.1, §13 | TP-1 T03 |
| AC-04 | Test dosyasına yanlış `@pytest.mark.contract_wrong` (typo) konulduğunda, pytest --strict-markers modunda koleksiyon aşamasında FAIL verir veya marker doğrulama testi tarafından FAIL tespit edilir | SPEC §2 M-3, §8 FC-6 | TP-1 T04 |
| AC-05 | F1' prime NETWORK scan: `app/` altında `requests` import eden `app/processing/quality_monitor.py` dosyası BLOCKER finding üretir (BLOCKER severity) | SPEC §9 S-4, §3.1 PR-gate | TP-2 T05 |
| AC-06 | F1' prime: `app/ingest/adapters/binance_adapter.py` (dummy test fixture path) import `urllib3` → ALLOWLIST nedeniyle finding YOKTUR (0 finding) | SPEC §9 S-4, §6.2 allowlist | TP-2 T06 |
| AC-07 | F2' prime CRED scan: S-FND-02 concat-split pattern `"ap"+"i"+"_"+"ke"+"y"` = substring AST/grep tarayıcıda MATCH YAPMAZ, false positive 0 | SPEC §9 S-1, F2' | TP-3 T07 |
| AC-08 | F2' prime: fixture klasörü `tests_fixtures/api_keys_dummy.json` (ALLOWLIST) → hassas key name match etse bile finding YOK (0) | SPEC §9 S-1, §6.2 allowlist | TP-3 T08 |
| AC-09 | F3' prime SHORT/LEV: `app/contracts/paper.py` içinde `PaperOrder.direction = "short"` assignment BLOCKER finding üretir | SPEC §9 S-2, EPICS L228 | TP-4 T09 |
| AC-10 | F3' prime: test dosyası `test_risk_short_path.py` fonksiyon ismi `test_short_position_rejected` substring → finding YOK (sadece domain/contract klasörlerinde F3' aktif) | SPEC §9 S-2 | TP-4 T10 |
| AC-11 | F4' prime REAL ORDER: `app/simulation/execution.py` içinde `def send_real_order(symbol,qty): ...` function DEF → BLOCKER finding üretir | EPICS L229, SPEC §9 S-3 | TP-5 T11 |
| AC-12 | F4' prime: TEST mock dosyası `tests/unit/processing/test_order.py` içinde mock `def send_real_order(): pass` → MINOR severity finding (app altı DEĞİL) | SPEC §9 S-3 minör | TP-5 T12 |
| AC-13 | PatternScanFinding dataclass → `json.dumps(sort_keys=True, separators=(",",":"))` 10 kez çalıştırıldığında SHA256[:12] AYNI (deterministic) | SPEC §6.2, §7 D-5 | TP-6 D-1 |
| AC-14 | PRGateScanReport `total_files_scanned`: 2 farklı run aynı repo state için AYNI sayıyı verir | SPEC §7 D-2,D-4 | TP-6 D-2 |
| AC-15 | Dekoratör: `@pytest.mark.contract` test fonksiyonu → `pytest_collection_modifyitems` sonrası `item.keywords.__contains__("contract") == True` ve marker listede `name=="contract"` | SPEC §6 Marker | TP-1 T15 |
| AC-16 | Aynı şekilde `@pytest.mark.replay` / `failure_injection` için yukarıdaki marker testleri doğru döner | SPEC §6 Marker | TP-1 T16 |
| AC-17 | Sahplik ayrımı: `tests/foundation_sfnd03/` altında 6 test dosyası AST import graph — `tests/failure/*.py` isimli modül IMPORT SAYISI tam 0. | SPEC §10 A-3, Non-goals P-04 | TP-8 T-own |
| AC-18 | Implementation audit sonrası `git diff HEAD --stat -- tests tests/conftest.py tests/foundation tests/failure pyproject.toml configs app/` çıktısı EMPTY; allowlist'teki 10 dosya (AS-BUILT: `55fd13e`'de git-tracked) dışında existing değişiklik yoktur | SPEC §12 HR-1, §10 A-4 | DoD-4 |
| AC-19 | Determinism: scan report 10 kez run `hash_list = [sha(report_json) for _ in range(10)]` → `len(set(hash_list)) == 1` | SPEC §7 D-4 | TP-6 D-3-6 |
| AC-20 | Fail-closed: pytest.ini [pytest] section silinip bozuk INI yapıldığında marker doğrulama testleri FAIL olur; sessizce continue ETMEZ. | SPEC §8 FC-1, FC-5 | TP-7 FC-5 |
| AC-21 | S-FND-02 correlation: PatternScanFinding için opsiyonel correlation_id label helper fonksiyonu mevcuttur; factory logger correlation provider ile uyumludur (mevcut S-FND-02 fonksiyon TEKRAR EDİLMEDİR, import edilebilirse kullanılır, yoksa no-op) | SPEC §13 AC-21, §4 UP-02, Non-goals P-08 | TP-8 T-opt |
| AC-22 | FC-8 duplicate finding: (rule_id, file_path, line_no) tuple KEY ile dedup yapılır. 3 kez overlapping pattern aynı satıra çarparsa TAM 1 finding vardır (3 defa raporlanmaz) | SPEC §8 FC-8, §6.2 tuple key | TP-7 FC-8 |
| AC-23 | Import smoke: `import tests.foundation_sfnd03` (pytest collects) hiçbir ImportError/SyntaxError üretmez, koleksiyon 0 hata | SPEC §3.1 NEW folder | TP-1 T-23 |
| AC-24 | Regression smoke: `python -m pytest tests/foundation tests/failure tests/foundation_sfnd03 tests/contracts -q` → Exit0 (ya da 0 NEW fail; mevcut XFAIL/XPASS sayıları değişmez) | SPEC §14 DoD-3 | DoD-3 |

---

## AS-BUILT Reconciliation Notları (Görev H)

> Bu bölüm, SPEC audit'inde (Görev G) saptanan as-built drift bulgularının kanıt temelli çözümünü kaydeder. Kanıt kaynağı: `55fd13e5c794c748b5268bfd891d37968cf407b9` (`feat: implement S-FND-03 foundation test contracts`, 10 files, 1332 insertions, 0 existing modification), `git ls-files`, `python -m pytest tests/foundation_sfnd03 --collect-only`.
>
> - **AC-02 (M5/m2 — DOCS INCORRECT, çözüldü):** Önceki "tam 3 marker" ifadesi pytest.ini'nin toplam kayıt sayısını yanlış ima ediyordu. Gerçek: S-FND-03'e ait 3 marker + 4 miras S-FND-01 marker (`F1..F4`) = 7 kayıt. Zorunlu marker sayısı (3) DEĞİŞMEDİ; yalnızca kayıt sayısı netleştirildi (P-06 + pytest config precedence nedeniyle zorunlu).
> - **AC-18 (B1 — AS-BUILT DRIFT, çözüldü):** "NEW untracked 10 dosya" yanlıştı; allowlist'teki 10 dosyanın TAMAMI `55fd13e`'de git-tracked'dır (`git ls-files` doğrulandı).
> - **AC-21 (m2 — DOCS INCORRECT, çözüldü):** "SPEC §21" kırık referanstı (SPEC yalnız §1..§20 içerir). Doğru hedef: SPEC §13 AC-21 tanımı + §4 UP-02 (S-FND-02 upstream).
> - **AC-24 (m2 — DOCS INCORRECT, çözüldü):** "SPEC §13 regression" yanlış atıftı (§13 = AC listesidir); doğru hedef SPEC §14 DoD-3. Ölçüm testi kolonu DoD-2 → DoD-3 yapıldı.
> - **Test PASS durumu:** Bu turda hiçbir test ÇALIŞTIRILMADI (yalnızca `--collect-only`); "24/24 executable PASS" iddiası audit çalıştırmasına bırakılmıştır (kanıtsız PASS üretilmedi).

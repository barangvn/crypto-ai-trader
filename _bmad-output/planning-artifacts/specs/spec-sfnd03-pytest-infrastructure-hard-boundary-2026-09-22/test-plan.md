# Test Plan — S-FND-03 (TP-1..TP-8, ~80+ test)

TOPLAM TEST: TP-1 (18) + TP-2 (12) + TP-3 (14) + TP-4 (10) + TP-5 (10) + TP-6 (6 determinism 10× sayılmaz) + TP-7 (8 fail-close) + TP-8 (6 audit/ownership) = planlanan 84 test + 6 determinism (10× count değil).

> **AS-BUILT (M1 — DOCS INCORRECT, çözüldü).** Gerçek runtime collected = **85** (`python -m pytest tests/foundation_sfnd03 --collect-only -q`), statik `def test_` = 61. Fark tamamen **parametrize genişlemesinden** kaynaklanır (plan vaka sayısı ≠ pytest'in çalıştırdığı test sayısı). Dosya bazında collected: `test_sfnd03_markers_catalog.py` 12, `test_sfnd03_f1prime_network.py` 8, `test_sfnd03_f2prime_credentials.py` 22, `test_sfnd03_f3prime_short_lev.py` 6, `test_sfnd03_f4prime_order_names.py` 7, `test_sfnd03_determinism_and_audit.py` 30 → toplam 85. Bu turda testler ÇALIŞTIRILMADI; PASS sayısı iddia edilmez.

> **Toplam kapsam tablosu (kaynak kümesi):** | Değer | Ne sayıyor? | Kaynak | |---|---|---| | 84 | Test planındaki planlanan TP vaka toplamı | bu dosya (planlama) | | 61 | Statik `def test_` sayısı (6 test dosyası) | `grep -c "def test_"` | | **85** | pytest'in `--collect-only` ile topladığı runtime test sayısı | `55fd13e` as-built | | 6,678 | Repo-wide collected (regresyon kapsamı) | `python -m pytest --collect-only -q` |

---

## TP-1 Marker Smoke & Catalog (18 test)
| T-Id | Test | AC Map |
|---|---|---|
| T01 | `pytest.ini` dosyası mevcut + [pytest] section | AC-01 |
| T02 | Markers 3 tane + sıra (contract, replay, failure_injection) | AC-02 |
| T03 | MarkerCatalog list == pytest.ini parse list, 1-1 match | AC-03 |
| T04a | Negatif: typo `contract_wrong` → strict modda FAIL veya doğrulayıcı fail | AC-04 |
| T04b | Negatif: typo `faillure_injection` → marker parse mismatch | FC-5 |
| T04c | Negatif: 4. marker ekledik → M-4 fail | M-4 |
| T05 | T15 @pytest.mark.contract attach doğrula | AC-15 |
| T06 | @pytest.mark.replay attach doğrula | AC-16 |
| T07 | @pytest.mark.failure_injection attach doğrula | AC-16 |
| T08 | `pytest -m contract` collects sadece marked — sayı diff | Smoke marker select |
| T09 | `pytest -m "replay or failure_injection"` Aynı şekilde | Smoke marker select |
| T10 | `pytest --strict-markers` no unknown marker warning 0 | Strict marker |
| T11 | Test dosyası __init__ var mı? tests/foundation_sfnd03/__init__.py | Smoke package |
| T12 | Import smoke | AC-23 |
| T13 | conftest.py mevcut (tests/foundation_sfnd03/conftest.py) | Smoke structure |
| T14 | helpers.py mevcut (prgate_scanner, pattern definitions) | Smoke structure |
| T15-T18 | Marker decorator tuple parametrize 3 marker × 2 durum positive/negative (6 test) |  |

## TP-2 F1' PRIME NETWORK SCAN (12 test)
| T | Senaryo |
|---|---|
| 01 | Empty `app/empty/` → 0 finding |
| 02 | `app/risk/gate.py` import requests → BLOCKER finding 1 |
| 03 | `app/ingest/adapters/okx.py` import aiohttp → allowlist 0 finding |
| 04 | `app/ingest/adapters/bybit/` nested subdir import httpx → 0 finding |
| 05 | `tests/failure/test_f1_no_network.py` (test içinde import) → MINOR severity 1 finding, app degil |
| 06 | `tests_fixtures/mock_network.py` fixture → allowlist 0 finding |
| 07 | `import socket` (stdlib, S-FND-01 offline blocker uses it, OK) → F1' BLOCK YOK (F1' sadece requests/httpx/aiohttp/websocket 4 external library için) |
| 08 | `import websocket` external third party (NOT stdlib lib socket) → BLOCKER finding app altında |
| 09-12 | Parametrized 4 library × 2 path (nonadapter vs adapter) → 8 test (üstteki 4 tane ile overlap etmesin diye ayrı parametrize — 4 ek test total 12) |

## TP-3 F2' PRIME CREDENTIAL STRING (14 test)
### Positive (should find if not allowlist/concat pattern):
1. `api_key = ...` (raw) → finds
2. `my_secret = ...` → finds
3. `"BINANCE_API_KEY"` → finds
4. `"OKX_KEY"` → finds
5. nested dict `{"access_token": "x"}` → finds (key token pattern)
6. `Authorization` header key (regex insensitive) → finds
### Negative (should NOT find, false positive guard):
7. Concat split pattern `"ap"+"i" + "_" + "ke"+"y"` → NO finding
8. Test fixture `tests_fixtures/keys.json` → NO (allowlist)
9. Symbol `"BTCUSDT"` → NO (normal)
10. Strategy name `"key_insight_strategy_v1"` → substring "key" ama false-pos 0
11. `private` (no "key") substring match → NO
12. `my_password` → finds (key list password var)
13. Value starts with `sk-` (starts with prefix) → finds (F2' sadece key adları için, value prefix S-FND-02 masking redaction için, F2' prime key names scan, value prefix için GAP G-3 not: optional future. YOK. Sadece KEY. 14 test: 6 positive 7 negatif 1 parametrize = 14)

## TP-4 F3' PRIME SHORT & LEVERAGE (10 test)
### Positive BLOCKER (app/contracts, app/risk, app/simulation, app/strategies):
1. `PaperOrder(direction="short")` in app/contracts → BLOCKER
2. `position.side = "sell_open_short"` → BLOCKER (exact EPICS L228 pattern)
3. `max_leverage = Decimal("3.5")` > 1 domain → BLOCKER
4. `leverage = 2` configs app defaults → BLOCKER
### Negative ALLOWED:
5. `tests/risk/test_short_reject.py` → app/classification YOK, F3' çalışmaz
6. `configs/config.test.ini` paper → 0 scan (test config; domain not)
7. `strategies LONG_ONLY comment` → 0 (string)
8. leverage = 1 (1 eşitse long-only kabul) → 0
9. `direction="long"` → 0
10. Parametrized (4 positive × nested/flat 2 path = 8, minus overlap = 10 total)

## TP-5 F4' PRIME REAL ORDER FUNCTION NAMES (10 test)
### Positive BLOCKER (app/ production path):
1. `def send_real_order(symbol, qty): pass` app/simulation/execution.py → BLOCKER
2. `def place_order_on_exchange(): return True` app/platform/api/routes → BLOCKER
3. `async def execute_real_trade(order_id): pass` app/... → BLOCKER (gerçek emir isim varyasyonu, EPICS L229 isimli pattern 2 tane + 1 varyasyon = 3)
### Negative:
4. `def paper_create_order(): pass` → paper prefix OK 0 finding
5. `def simulate_fill(order): pass` → simulate prefix OK
6. `tests/unit/mocks.py` içinde `def send_real_order(): raise MockException("mock")` → MINOR (test, not app)
7. Comment out: `# def send_real_order(): pass` → AST tarayıcı, comment YOK
8. string literal `"send_real_order"` (string, not def) → AST finding NO (def line için)
9. 10 empty/edge parametrize → 2 ek test = 10

## TP-6 DETERMINISM 6 × 10x (6 scenario, 10 runs, len(set)==1)
- D1: pytest.ini markers list sort order (doğrudan ConfigParser)
- D2: pathlib sorted() scan (mevcut durumda kaç dosya tarandı: fixed fixture tmpdir)
- D3: (rule_id, file, line_no) tuple dedup (3 kez aynı satır → output 1 finding)
- D4: PRGateScanReport JSON hash (10x aynı)
- D5: MarkerCatalog enum (3 eleman, 10 kez aynı liste)
- D6: `ast.parse` + node.lineno for F1' imports, identical input → same finding list

## TP-7 FAIL-CLOSED FC 8 test
1. FC-1 extra marker → M-4 fail
2. FC-2 allowlist yaml okunamaz → scan blocked pass_fail=False
3. FC-3 syntax error py → skip değil finding MAJOR sonra scan devam
4. FC-4 regex F2' derleme hatası → collection fail
5. FC-5 typo marker in ini → marker test FAIL
6. FC-6 wrong decorator name → strict markers collection err (or test catches)
7. FC-7 subprocess timeout (scan runner) → finding BLOCKER + fail
8. FC-8 duplicate finding: 3 pattern same line → output 1 finding dedup

## TP-8 OWNERSHIP & AUDIT EVIDENCE (6 test)
1. A-1 report json yazılır, SHA 10x aynı (AC-13 subset)
2. A-2 `pytest --markers` subprocess stdout parse eder ve exact 3 + sıra match
3. A-3: AST import graph: `tests/foundation_sfnd03/*.py` içinde `import tests.failure` veya `from tests.failure` → COUNT = 0
4. A-4 (simülasyon - implementation phase): git diff assertion (şu an spec phase, bu test impl Aşamasında koşulur, şu an PLANLANMIŞTIR)
5. Markers/catalog: 3 marker exact import test
6. ~~PRGateScanReport schema_version 1 zorunlu, contract_version 1.0.0 zorunlu~~ — **AS-BUILT (M6 — DOCS INCORRECT, çözüldü):** teslim edilen `PRGateScanReport` (`_helpers.py`) `schema_version` / `contract_version` alanlarını İÇERMEZ (bkz. SPEC §6.3 AS-BUILT notu). Gerçek alanlar: `scan_id`, `scanned_files`, `findings`, `allowlist_read_errors` (+ `passed` property, `deterministic_sha256()`). Bu TP8-6 maddesi AS-BUILT'te karşılıksız (phantom alan) kalır; ilgili doğrulama as-built `deterministic_sha256()` üzerinden yapılır.

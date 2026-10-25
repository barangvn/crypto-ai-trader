# Hard-Red (HRC 13 Kurallar) — S-FND-06

## 8 Proje Genel HRC (Inherit from S-FND-03 HARD-RED)

| HR ID | Kural | Uygulama | Fail Criterion |
|---|---|---|---|
| HR-01 (NETWORK) | Üretim kod (app/*) içinde `requests`, `httpx`, `aiohttp`, `websocket-client`, `ccxt`, `binance`, `exchange` importları YASAK (SADECE `app/ingest/adapters` + test fixtures izinli). S-FND-06 helper layer → `app/contracts/` new modül under contracts bound → **kesin 0 network import** | Grep HEAD new production 6 module | FAIL >0 |
| HR-02 (CREDENTIAL) | `"AKIA"`, `"BINANCE_API_KEY"`, `"_SECRET"`, `"api_key ="`, `"secret="`, `"SECRET_KEY"`, password gibi 8+ credential pattern üretim kodda YASAK (dummy test fixture string only under tests/foundation_sfnd06/ with explicit guard). → 0 match in 6 new prod | git grep 10 credential patterns HEAD new prod | FAIL >0 |
| HR-03 (DYNAMIC EXEC) | `eval(`, `exec(`, `pickle.loads`, `getattr(__import__)`, `subprocess.Popen` / `subprocess.run` dinamik kod yürütme YASAK. | AST scan new 6 prod | FAIL any match |
| HR-04 (SHORT/LEV) | `direction="short"`, `side=sell_open_short`, `leverage>1`, `lev =`, `SHORT` kelimeleri üretim katmanında YASAK (StrategySignal payload scope, helper layer no-touch). | grep 6 prod | FAIL >0 |
| HR-05 (LIVE ORDER) | `send_real_order`, `place_order_on_exchange`, `market_buy()`, `market_sell()` gerçek emir fonksiyon isimleri YASAK. Tüm isimler simulate/paper önekli. | grep 6 prod | FAIL >0 |
| HR-06 (PyYAML) | `import yaml`, `from yaml import`, `yaml.safe_load`, `_YAML_ENABLED = True` → **S-FND-06 için KAPALI (OD-06-03 CLOSED PERMANENT)**. Sessiz inherit değil kendi hard-red kural. | grep 6 new prod | FAIL >0 (MANDATORY — no future yaml in helpers) |
| HR-07 (3RD PARTY) | Default = YALNIZCA Python stdlib. 3rd party import (pydantic, msgspec, attrs, orjson, rapidjson, xxhash, dateutil, pytz, numpy) YASAK. Default stdlib-only. Explicit EXCEPTION required pyproject.toml + OD-06-01 set to 3p (default stdlib). | grep 6 prod imports non stdlib | FAIL >0 (default path) |
| HR-08 (K0 ZERO BYTE DIFF) | Completed story dosyaları (S-FND-01..05, E-API, S-MDL01..05, pyproject.toml, pytest.ini, env.ini 4 adet, tests/foundation*, tests/api*, tests/contracts*, tests/failure*, tests/smdl*) → MODİFİKASYON YASAK. New files only. Existing modify 0 satır. | git diff parent→HEAD -- existing listed paths | FAIL any line diff |

---

## 5 Hikâye Özel HRC (S-FND-06 Özel)

| HR ID | Kural | Fail Criterion |
|---|---|---|
| HR-09 (SER FROZEN ORDER) | Canonical JSON key ordering: DICT KEYS NESTED DE 100% SORTED. `json.dumps(obj, sort_keys=True)` zorunlu. sort_keys=False → HARD RED FAIL. | canonical_json output deep parse key order not sorted test | FAIL |
| HR-10 (DETERMINISTIC FINGERPRINT) | Fingerprint 12-hex lowercase SHA-256 prefix ZORUNLU. MD5/RIPEMD160/other algoritma YASAK; 12 char tam sayısı. | fingerprint length !=12 veya non-hex | FAIL |
| HR-11 (NO NOW SOURCE IN PROD) | Production code path CANONICAL helpers içinde `time.time_ns()`, `datetime.utcnow()`, `datetime.now(datetime.timezone.utc)` GERÇEK ZAMAN OKUMA YASAK. Sadece `now_instant_utc_fixture()` fixture-only (test & replay helper) function içinde olabilir; production call path fixture helper çağırmaz. | AST scan new prod: imports datetime/dateutil for live now calls | FAIL >0 (fixture-only explicitly marked) |
| HR-12 (MANUAL DEGRADE REJECT DEFAULT — Non-binding Safety Choice / Optional Future Explicit) | QualityFlags builder: manual degraded=True set parameter → RAISE (default safety: degraded bayrağını yalnız diğer 6 kalite bayrağından biri true olunca otomatik set etmesini tercih ettik; downstream contract açılımıyla gelecek sürümlerde builder parametre olarak erişime açılabilir. Geçersiz kılma: sadece güvenlik gerekçesiyle default davranış; AC-17 bunu test eder ancak upstream CONTRACTS§2'de açıkça zorunlu normatif bir kural değildir. → FC-16 test.) | `build_quality(degraded=True)` no raise → FAIL (default safety) |
| HR-13 (SYMBOLS NO SANITIZE) | `canonical_symbol`: ACCEPT ONLY strict regex subset (uppercase + underscore + max len). NEVER SANITIZE user input; reject ambiguous or invalid (no HTML remove, no sanitize — only strict accept/reject gate). | `canonical_symbol("btc_usdt<script>")` no raise → FAIL (must raise; no silent sanitize) |

---

Toplam HRC: 13. 8 proje genel + 5 hikâye özel.

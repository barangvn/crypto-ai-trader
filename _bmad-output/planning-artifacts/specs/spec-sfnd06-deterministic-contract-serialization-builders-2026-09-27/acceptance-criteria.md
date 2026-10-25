# Acceptance Criteria — S-FND-06 (20 AC)

Tüm AC executable (Given / When / Then + Pass/Fail boolean sonuç).

## G0 Import & Version

| AC # | Given | When | Then (Pass) |
|---|---|---|---|
| AC-01 | Fresh import context | `from app.contracts.sfnd06_serialize import canonical_json, envelope_fingerprint, canonical_symbol, validate_instant, build_valid_envelope, build_quality, append_quality_reason, ulid_compare, CanonicalSerializationError` | ImportError/ModuleNotFoundError YOK. Tüm 9 isim import edilebilir. |
| AC-02 | S-FND-04 VersionConstants | `from app.platform.config import VersionConstants as VC; from app.contracts.sfnd05_api import ContractVersionStr; str(VC.contract_version)` | EXACT `"1.0.0"` match. Helperlar serialize ettiklerinde contract_version field = bu değer (AC-12 ile final assert). |

## G1 Canonical JSON & Fingerprint Determinism

| AC # | Given | When | Then |
|---|---|---|---|
| AC-03 | Valid envelope `env` (12 alan dolu) | `digests = {canonical_json(env) for _ in range(10)}` | `len(digests) == 1` (10 kez aynı byte) |
| AC-04 | Aynı envelope `env` | `fps = {envelope_fingerprint(env) for _ in range(10)}` | `len(fps) == 1`; fingerprint 12 karakter; tüm karakter hex lowercase. |
| AC-05 | Shuffled dict order input `d_a` vs sorted keys `d_b` (aynı key-value pairs, order farklı) | `canonical_json(d_a) == canonical_json(d_b)` → karşılaştır | `True`. sort_keys etkisini doğrula. |
| AC-06 | Decimal `Decimal("123.456")` → nested olarak `obj` içinde | `s = canonical_json(obj)` çıktısını string yap | Decimal string `"123.456"` (exponent E+ yok). Float `123.456` ile karıştırılmamalı (Decimal→str kuralı). |
| AC-07 | Circular ref obj `a={'b': None}; a['b']=a` | `canonical_json(a)` çağır | Raise `CanonicalSerializationError` (ValueError subclass). No infinite hang. |

## G2 Symbol Canonicalizer (Strict Gate — No Sanitize)

| AC # | Given | When | Then |
|---|---|---|---|
| AC-08 | raw = `"btcusdt"` (no sep) | `canonical_symbol(raw)` | `"BTC_USDT"` (returned SymbolCanonical type match regex). |
| AC-09 | raw = `"BTC/USDT"` (slash sep) / `"BTC-USDT"` (dash) / `"btc_usdt"` lowercase | Her biri için `canonical_symbol` | `"BTC_USDT"`. 3 case tek AC içinde parametrize. |
| AC-10 | raw = `"<script>alert(1)</script>"` veya `"BTC/USDT'; DROP TABLE symbols--"` (ambiguous / invalid) | `canonical_symbol(raw)` çağır | Raise ValueError. HİÇBİR ZAMAN sessizce "sanitize" edip geçerli sembol döndürme (strict accept/reject only). |

## G3 Instant Validate & Fixture Generator

| AC # | Given | When | Then |
|---|---|---|---|
| AC-11 | s = `"2026-01-01T00:00:00.123Z"` (UTC Z + 3 digit fractional) | `validate_instant(s)` → return | Same string dön; hata YOK. |
| AC-12 | s = `"2026-01-01T00:00:00+03:00"` (offset, no Z) | `validate_instant(s)` | Raise ValueError. UTC Z mandatory. |
| AC-13 | Fixture-only generator çağrılır: `now_instant_utc_fixture()` | Validate result string | Ends with `"Z"`; match fractional digit 1-6 ISO regex. |

## G4 Builders + Invariants

| AC # | Given | When | Then |
|---|---|---|---|
| AC-14 | Partial kwargs: `event_type="candle.v1"`, `payload={"close":"1.0"}` (12 required'tan 10 tanesi override edilmedi → default fixtures) | `env = build_valid_envelope(event_type="candle.v1", payload=payload)` | Tüm 16 alan non-null (opsiyonel trace_id/extra olabilir ama builder default None atar); envelope post-init S-FND-05 invariants raise YOK. quality_flags.degraded=False default (all flags False). run_mode default="backtest" OK. |
| AC-15 | `build_valid_envelope(event_type="")` empty string event_type override | Constructor çağır | Raise ValueError (S-FND-05 EVENT_TYPE_RGX no-match → fail closed builder). FC-11 |
| AC-16 | `qf = build_quality(stale=True)` → then append reason code "STALE_MS", message "stale >5m", context={"threshold_ms":300000} | `qf2 = append_quality_reason(qf, "STALE_MS", "stale>5m", {"threshold": 300_000})` | qf2.degraded=True (auto); qf2.reasons list len = 1 (ilk ekle). Aynı code ile 2. append → len değişmez (idempotent). code="" → raise ValueError (FC-12). |
| AC-17 | `build_quality(degraded=True)` param ile çağrılır (manual degraded override denemesi) | Constructor | Raise ValueError (default safety behavior: degraded auto-set ONLY. **Classification:** Non-binding Optional Future Safety Choice — upstream CONTRACTS §2 quality bayraklarında zorunlu normatif MANDATORY kural değildir; downstream API genişlemesiyle future izin verilebilir. Mevcut default raise = valid safety choice korunur.) |

## G5 ULID Compare & Version Alignment

| AC # | Given | When | Then |
|---|---|---|---|
| AC-18 | `a = "01ARZ3NDEKTSV4RRFFQ69G5FAV"` (older ULID) / `b = "01ARZ3NDEKTSV4RRFFQ69G5FB2"` (1 sonraki) | `ulid_compare(a, b)` → return negatif; `ulid_compare(b, a)` → pozitif; `ulid_compare(a, a)` → 0 | Tam -1/+1/0 değil ama sign doğru. Sırala `sorted([b, a], key=functools.cmp_to_key(ulid_compare))` → [a, b] sonucu. |
| AC-19 | `env = build_valid_envelope(event_type="market_tick.v1", payload={"price": "1"})` serialize | `contract_version = json.loads(canonical_json(env))["contract_version"]; sr = json.loads(canonical_json(env))["schema_ref"]["contracts_md"]` | contract_version = EXACT `"1.0.0"` (AC-02 karşılaştır). schema_ref.contracts_md = EXACT `"CONTRACTS.md@1.0.0"`. Version alignment AC-12 extension 1/2. |
| AC-20 (REG) | Run upstream regression: S-FND-05 45 test suite unchanged | `pytest tests/foundation_sfnd05/` exit code | Exit 0; 45 PASS 0 FAIL. Zero regression. Helper importları S-FND-05 public API kullandığı için changesiz. |

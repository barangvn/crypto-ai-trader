---
story_id: "S-PTF-03"
story_key: "S-PTF-03"
title: "Deterministic 24h Rolling Performance & PnL (Separate from Session-Cumulative S-PTF-02, AD-20 Determinism, CAP-1/CAP-2, Single-Writer AD-7/13/24, Typed EventBus S-PLN-01)"
epic: "E-PTF — Portfolio Simulator & Deterministic PnL Accounting (Epic 11 — Portfolio Snapshot + Rolling 24h Window Layer)"
status: "ready-for-dev"
created: 2026-08-31
updated: 2026-08-31
author: "bmad-create-story v1"
tags: [portfolio_snapshot, rolling_performance, rolling_24h, pnl, deterministic, stdlib_only, long_only, v1, typed_eventbus, CAP-1, CAP-2, AD-7, AD-13, AD-17, AD-19, AD-20, AD-24, single_writer, no_network, no_db, no_credentials, equity, drawdown, exposure, realized_pnl, fees_quote, return]
baseline_commit: "8eb78a9 feat: implement deterministic portfolio snapshot and drawdown"
previous_story: "S-PTF-02 Deterministic Portfolio Snapshot, Equity & Drawdown (333 NEW PASS / 3 NEW SKIP, Toplam 3316 PASS + 7 SKIP = 3323 collected — COMMIT READY)"
next_stories:
  - "S-PTF-04: Portfolio Simulator End-to-End Replay Orchestrator (OOS bu hikâyede)"
  - "S-PTF-05: Performance Attribution Decomposition (Symbol, Strategy, Regime — OOS)"
contract_version_preserved: "1.0.0"
contracts_used:
  - "PortfolioSnapshot (app/contracts/portfolio.py S-CON-02B §3.5) — S-PTF-02 tek-yazarı, S-PTF-03 SALT-OKUNUR view tüketir, YAZAMAZ. realized_pnl_quote_24h = SESSION CUMULATIVE preserve edilir."
  - "Position (app/contracts/portfolio.py S-CON-02B §3.4) — S-PTF-01 tek-yazarı, S-PTF-03 OKUR, DEĞİŞTİREMEZ."
  - "QualityFlags (app/contracts/quality.py S-CON-02A §2) — frozen 7 bayrak + abnormal_spread, CAP-2 salt-okunur, MUTATE YOK, VALIDATOR TEKRAR ÇAĞIRMA YOK."
  - "InMemoryTypedEventBus (app/platform/event_bus.py S-PLN-01) — subscribe_typed, publish_with_causation(parent), DLQ isolation, causation max_depth=32, external broker YOK."
  - "CanonicalEventEnvelope + Correlation/Causation fields (S-CON-02A §1) — S-PTF-03 result correlation_id = upstream PortfolioSnapshot.correlation_id zinciri preserved."
test_baseline_count: 3323
test_baseline_passed: 3316
test_baseline_skip: 7
test_baseline_fail: 0
per_story_baseline_breakdown:
  S-RDH-01: 68
  S-RDH-02: 64
  S-PLN-01: 42
  S-CON-02A: 104
  S-CON-02B: 71
  S-CON-02C: 93
  S-FEA-01: 120
  S-REG-01: 302
  S-STR-01: 401
  S-OPP-01: 611
  S-RSK-01: 233
  S-RSK-02: 250
  S-PTR-01: 365
  S-PTF-01: 259
  S-PTF-02: 333
test_target_new_min: 250
test_target_total_collected_min: 3573
test_target_total_passed_min: 3566
runtime_dependencies_new_allowed: 0
v1_hard_boundary_long_only: true
new_contract_allowed: false
paper_only: true
no_real_exchange_api_credentials: true
pyproject_dependencies_expected: "[] (EMPTY — stdlib-only)"
single_writer_invariant_scope: "S-PTF-03 SADECE rolling metric HESAPLAR (aggregation). PortfolioSnapshot (S-PTF-02), Position (S-PTF-01), RiskDecision (S-RSK-01), PaperOrder/Fill (S-RSK-02/S-PTR-01) — TEK YAZARLARI korunduğu gibi; S-PTF-03 HİÇBİRİNİ YAZAMAZ / MUTATE EDEMEZ."
correlation_causation_chain: "10-halka: StrategySignal (S-STR-01) → OpportunityScore (S-OPP-01) → RiskDecision (S-RSK-01) → PaperOrder (S-RSK-02) → PaperFill (S-PTR-01) → Position (S-PTF-01) → PortfolioSnapshot (S-PTF-02) → RollingPerformance (S-PTF-03 THIS). correlation_id ZİNCİR SABİT; rolling_result.causation_id = portfolio_snapshot.snapshot_id (parent event id)."
---

# S-PTF-03 — Deterministic 24h Rolling Performance & PnL

> **HARD KURAL (KULLANICI VERBATİM §1 ANA KURAL + §24 OUT OF SCOPE + §16 SINGLE WRITER — İHLAL EDİLEMEZ):**
>
> 1. **SEPARATION S-PTF-02 vs S-PTF-03 (BLOK):** S-PTF-02 = **session-cumulative** (no window). S-PTF-03 = **exactly 24-hour rolling window**. İki kavram KARIŞTIRILMAYACAK. S-PTF-02 kaynak kodu (PortfolioSnapshotEngine, realized_pnl_quote_24h session alanı, peak equity state) GEREKSİZ YERE DEĞİŞTİRİLMEMELİ.
> 2. **PortfolioSnapshot + Position CONTRACTS IMMUTABLE (BLOK §24):** `app/contracts/portfolio.py` PortfolioSnapshot + Position dataclassları, public alanları, enumları, __post_init__ validasyonları, contract_version 1.0.0 — %100 KORUNUR. BU HİKÂYEDE YENİ CONTRACT ZORLA OLUŞTURULMAZ (§8 user). Eğer rolling result publish gerekiyorsa → S-PLN-01 typed eventbus payload (sorted dict) veya event-level payload; PortfolioSnapshot contract'ına yeni alan EKLENMEZ.
> 3. **SINGLE WRITER AD-7/13/24 (§16):** S-PTF-03 → PortfolioSnapshot state YENİDEN YAZAMAZ; Position state DEĞİŞTİREMEZ; RiskDecision YAZAMAZ; PaperOrder/PaperFill ÜRETEZ. SADECE 24h window içindeki sample'lardan türetilmiş rolling metric HESAPLAR (aggregate/pure fonksiyon). Rolling sonucu "çıktı dataclass" eğer mevcut contract yoksa ZORLA OLUŞTURULMAZ → `build_rolling_24h(*args) -> dict[str, Any]` (sorted keys deterministik) veya helper-level frozen dataclass (app/simulation/portfolio.py içinde, contracts KLASÖRÜNE YAZILMAZ).
> 4. **PYPROJECT.TOML DEPS=[] (§23):** Yeni runtime dependency 0. Stdlib-only. Pydantic/msgspec/cattrs/numpy/pandas/ta-lib/ccxt/requests/websockets YASAK.
> 5. **SAFETY 8 KATEGORİ (§19 — AST 0 MATCH):** exchange YOK, network YOK, DB YOK, credentials YOK, real execution YOK, short YOK, futures YOK, leverage>1 YOK.
> 6. **CAP-1 AST 0 (§14):** `run_mode` / `source_type` branch YOK (if/elif/Attribute 0 match). `datetime.now` / `time.time` / `time.sleep` / `Instant.now` YOK — GERÇEK CLOCK KULLANILMAZ. Window end_ts = dışarıdan argüman olarak verilen UTC Instant.
> 7. **CAP-2 QF IMMUTABLE (§15):** QualityFlags MUTATE YOK (setattr 0); `validate_quality`, `validate_position`, `validate_market` fonksiyonları TEKRAR ÇAĞIRILMAZ (import/call sayısı 0).
> 8. **MIN 250 YENİ TEST (§20):** Bu hikâyeye özgü EN AZ 250 YENİ test yazılacak (boundary ±1ms window, OoO/dup samples, multi-symbol, return edge, peak/drawdown rolling, exposure, EventBus corr/caus, CAP-1/2 AST, Single Writer AST, determinism 10x, replay, safety 8 kategori, regression).
> 9. **REGRESSION 3316 PASS + 7 SKIP = 3323 KORUNUR (§21):** S-RDH-01/02 S-PLN-01 S-CON-02A/02B/02C S-FEA-01 S-REG-01 S-STR-01 S-OPP-01 S-RSK-01/02 S-PTR-01 S-PTF-01 S-PTF-02 — TAM 15 HİKÂYE, 3316 PASS + 7 SKIP %100 KORUNUR (total target ≥ 3323 + 250 = 3573 collected).
> 10. **GIT (§24):** BU HİKÂYEDE commit OLUŞTURULMAZ. Başka bir story (S-PTF-04) GEÇİLMEZ.

---

## 1. Amaç ve Genel Bakış (BDD User Story + İş Değeri)

**User Story (BDD — KULLANICI VERBATİM AMAÇ + ANA KURAL):**
> *Bir Portfolio Simulator Operatorü / Analytics Consumer (Risk Engine downstream, Replay pipeline, Paper Execution observer) olarak,*
> *S-PTF-02'nin ürettiği session-cumulative PortfolioSnapshot nesnelerini DEĞİŞTİRMEDEN ve onların metriklerini bozmadan,*
> *Tam olarak 24 saatlik (86400000 ms) UTC timestamp tabanlı DETERMINISTIC ROLLING WINDOW filtresi uygulanarak,*
> *ayrı ve bağımsız bir rolling performance katmanı istiyorum,*
> *Öyle ki:*
> - SAMPLE INPUT (read-only PortfolioSnapshot listesi + end_ts UTC Instant) verildiğinde; S-PTF-02 session cumulative alanlarını OKUYUP, window ts filtresi sonrası **rolling 24h** sonuçlarını AYRI hesapla
> - **Realized PnL 24h:** window içindeki SON sample realized - İLK sample realized (sadece window içi, session cumulative FİLTRE, karıştırma)
> - **Fees 24h:** window içindeki SON sample fees - İLK sample fees (double-count YOK, Decimal)
> - **24h Performance Return:** (end_equity - start_equity) / start_equity — start equity policy = window İLK sample equity; zero-baseline / missing / no-sample edge → fail-safe davranış
> - **Rolling 24h Peak Equity:** max(window equity samples) — S-PTF-02'nin peak_equity (session) state'inden TAMAMEN BAĞIMSIZ, KARIŞTIRMA
> - **Rolling 24h Drawdown:** (rolling_peak_equity - window_end_equity) / rolling_peak_equity — peak 0 ise 0
> - **24h Exposure (3 alan explicit):** max exposure (window), average exposure (window avg Decimal mean), ending exposure (window son sample exposure_notional)
> - **Multi-symbol (1, 2, 5, mixed):** Aggregation sırasında Position.symbol ASC sort (AD-20 determinizm → S-PTF-02 kanıtlanmış pattern)
> - **Sample Handling:** Out-of-order → ASC (ts, snapshot_id ULID) sort normalize; duplicate timestamps → snapshot_id ULID ASC tie-break (deterministik); missing samples → NO interpolation (sadece var olanları kullan, empty window → safe-zero result)
> - **Quality (§11):** QualityFlags read-only; validator tekrar çağırma; invalid/quarantine/stale samples için deterministic window behavior
> - **Correlation/Causation (§12):** Rolling result metadata → upstream PortfolioSnapshot snapshot_id ve correlation_id/causation_id zinciri BOZULMAZ
> - **EventBus (§13):** S-PLN-01 typed bus → `portfolio_snapshot.v1` subscribe → Rolling Performance Engine consume + compute → opsiyonel `rolling_performance.v1` publish (DLQ izole, external broker YOK)
> - **Determinism (§17):** Aynı sample set + aynı end_ts → 10x AYNI rolling values (realized24, fees24, return, peak, drawdown, exposure 3'lü, sorted dict, SHA256)
> - **Replay (§18):** Replay fixture (json/list of snapshot) → 100x aynı input → aynı rolling performance output (idempotent)
> - **Yeni runtime dependency 0; pyproject.toml dependencies=[] korunur; stdlib-only; 15 hikâye regression (3316 PASS + 7 SKIP = 3323) KORUNUR.**

**Ayrım Özeti (SESSİON vs ROLLING — TEKRAR VURGU):**
| Boyut | S-PTF-02 (Session Cumulative) | S-PTF-03 (Rolling 24h) |
|---|---|---|
| Zaman penceresi | Tüm session (no window filter) | Tam 24h (86400000 ms) end_ts - 24h |
| Realized PnL 24h field adı | PortfolioSnapshot.realized_pnl_quote_24h = Σ positions (SESSION, DEĞİŞMEZ) | Yeni çıktı: rolling_realized_pnl_quote_24h = window delta |
| Peak Equity | PortfolioSnapshot.peak_equity (session lifetime, S-PTF-02 state) | Rolling 24h Peak: max(window equities) — BAĞIMSIZ |
| Drawdown | Session lifetime drawdown (S-PTF-02) | Rolling 24h drawdown (rolling peak vs end) — BAĞIMSIZ |
| S-PTF-02 kod | S-PTF-03 yazılırken MUTABLE EDİLMEMELİ | S-PTF-02 kodunu SONUNA EKLE pattern — değişiklik Yok |

### Hedef
Mevcut **S-PTF-02 PortfolioSnapshotEngine** (app/simulation/portfolio.py L546-1040 approx) ve **S-PTF-01 PositionEngine** (L1-523) kaynak kodlarını **DEĞİŞTİRMEDEN** (mevcut method/fonksiyon/class isimleri, parametreleri, return tipleri — NO BREAKING CHANGES), aynı dosyanın **SONUNA** yeni bir **pure RollingPerformanceEngine** class + `build_rolling_24h(*, snapshot_samples: list[PortfolioSnapshot], end_ts: Instant, ...) -> dict[str, Any]` fonksiyonu eklenir. Bu fonksiyon:
- Input (typed, salt-okunur snapshot_samples listesi + end_ts + optional flags) alır
- 5-phase deterministic pipeline (Guard → Normalize/Sort → Window Filter → Aggregate → Invariant Check) uygular
- Return: `sorted_dict[str, Any]` (keys ASC, Decimal→str, Enum→value, nested ordered) + `schema_sha256` digest + corr/caus metadata

---

## 2. Ön Koşullar (Non-Negotiable — Başlangıçta Doğrulanacak)

```
✅ 3316 PASS + 7 SKIP = 3323 collected FULL regression PASS
   15 HİKÂYE SIRASIYLA:
   (1) S-RDH-01 Data Replay Pipeline (68 PASS)
   (2) S-RDH-02 Canonical Tick/Candle Normalizasyon (64 PASS)
   (3) S-PLN-01 Typed EventBus + Correlation/Causation (42 PASS)
   (4) S-CON-02A FeatureVector/Regime/StrategyContext Canonicals (104 PASS)
   (5) S-CON-02B RiskDecision/PaperOrder/PaperFill/Position/PortfolioSnapshot (71 PASS)
   (6) S-CON-02C OpportunityScore + Model Lifecycle Canonicals (93 PASS)
   (7) S-FEA-01 Deterministic Feature Engine (120 PASS)
   (8) S-REG-01 6-State Market Regime Detection (302 PASS)
   (9) S-STR-01 Trend + Momentum Strategy Engine (401 PASS)
   (10) S-OPP-01 Net-of-Cost Opportunity Scoring (611 PASS)
   (11) S-RSK-01 Independent Fail-Closed Risk Engine (233 PASS)
   (12) S-RSK-02 RiskDecision→PaperOrder Gate Enforcement (250 PASS)
   (13) S-PTR-01 Paper Execution & Fill Engine (365 PASS)
   (14) S-PTF-01 Deterministic Position Engine + PnL (259 PASS)
   (15) S-PTF-02 Portfolio Snapshot Equity & Drawdown (333 PASS / 3 SKIP)
   → BU HİKÂYE SONRASI TOTAL ≥ 3573 collected (3323 + ≥250 new)
   → TÜM 3316 PASS + 7 SKIP %100 KORUNUR (0 regression break)
✅ app/simulation/portfolio.py MEVCUT:
   S-PTF-01 PositionEngine (L1-523), S-PTF-02 PortfolioSnapshotEngine (L546-L1040) — S-PTF-03
   S-PTF-03 AYNI DOSYAYA SONUNA EKLENECEK (S-PTF-01→S-PTF-02 pattern korunur).
✅ app/contracts/portfolio.py MEVCUT:
   Position (L94-214) + PortfolioSnapshot (L221-318) dataclass.
   realized_pnl_quote_24h = SESSION CUMULATIVE preserved (AC-01 doğrula).
✅ app/platform/event_bus.py MEVCUT (S-PLN-01):
   subscribe_typed, publish_with_causation(parent_event_id), DLQ, causation max_depth=32,
   quarantine isolation. External broker YOK.
✅ QUALITY FLAGS MEVCUT (CAP-2):
   QualityFlags frozen, 7 bayrak + abnormal_spread fallback getattr kullanılır.
✅ pyproject.toml dependencies = [] (EMPTY, CONTRACT_VERSION = 1.0.0 SABİT)
✅ v1 SAFETY 8 KATEGORİ KİLİTLİ (S-PTF-02 audit sonrası mevcut, S-PTF-03 de doğrulama):
   short YOK, futures YOK, leverage>1 YOK, exchange/REST/WS/credential/DB/network YOK, real-order YOK
```

---

## 3. Değişmez Mimari Kurallar (HİÇBİR KOŞULDA İHLAL EDİLEMEZ)

| Kural Kodu | Kaynak | Davranış / Zorunluluk (NON-NEGOTIABLE) |
|---|---|---|
| **AD-20 Determinism + 10x** | ARCH AD-20 + §17 user | Aynı sample set + aynı end_ts → 10 run → 10× aynı rolling output. `to_sorted_dict()` (ASC keys) → eşit; `schema_sha256()` set len=1. |
| **AD-17 Corr/Caus 10/10** | AD-17 + §12 user | 10-halka zincir: Strategy→Opportunity→Risk→PaperOrder→PaperFill→Position→PortfolioSnapshot→RollingResult. `rolling_result.correlation_id = last_snapshot.correlation_id`. `rolling_result.causation_id = last_snapshot.snapshot_id` (parent). |
| **AD-7/13/24 Single Writer** | §16 user BLOK | S-PTF-03 PortfolioSnapshot / Position / RiskDecision / PaperFill YAZAMAZ. Sadece okur. Rolling output = helper dict veya non-contract dataclass (app/simulation içi, contracts/ DEĞİL). |
| **AD-19 Fail-Closed** | §6 user Edge G1 | Herhangi bir BaseException (ts parse, Decimal overflow, div-by-zero, sort error, type mismatch) → `safe-zero result` + INFO_CODES[] (INTERNAL_CALCULATION_ERROR) |
| **CAP-1 Live/Replay Parity** | §14 user BLOK | `app/simulation/portfolio.py` S-PTF-03 kod bloğunda `if run_mode == ` / `if source_type == ` AST 0 match. `datetime.now`, `time.time`, `time.sleep` → 0 match. Gerçek clock YOK. |
| **CAP-2 Quality Immutable** | §15 user BLOK | QualityFlags setattr = 0; `validate_quality`, `validate_position`, `validate_market` import/call = 0. Sadece okuma. |
| **v1 Hard Safety 8 kategori** | §19 user BLOK | exchange, network, DB, credentials, real execution, short, futures, leverage>1 → AST 0 match. |
| **Decimal Monetary + Float Return/DD** | SPEC §Constraints | Parasal (realized24, fees24, equity, exposure) → Decimal (8dp quantize). Oransal (rolling_return_pct, rolling_drawdown_pct) → float. |
| **AD-22 Contracts Preserved** | ARCH AD-22 + §8 user | PortfolioSnapshot/Position contractları public fieldları, enumları, sırası, invariants → %100 KORUNUR. Yeni contract ZORLA OLUŞTURULMAZ. |
| **Symbol ASC Aggregation** | AD-20 + S-PTF-02 kanıt | Window içindeki her sample'ın positions_snapshot → symbol ASC sort oncesi agg. Determinizm garantisi. |
| **ASC Sample Sort Key** | §10 user OoO/Dup | Sample'lar `(sample.ts_epoch_ms ASC, sample.snapshot_id ULID ASC)` ile normalize. |
| **Replay Idempotent** | §18 user | Aynı fixture json (samples + end_ts) → 100 run → 100 aynı sorted dict. |

---

## 4. Exact 24h Window Policy (BOUNDARY KESİN — §3 user VERBATIM)

> **ZORUNLU:** Tüm timestamps ISO-8601 UTC (Instant). 24h = 86400 saniye = 86400000 ms.

### 4.1 Sabitler
```python
WINDOW_SECONDS: int = 86_400          # 24 * 60 * 60
WINDOW_MS: int = 86_400_000           # 24 * 60 * 60 * 1000
TZ: str = "UTC"                       # SADECE UTC, timezone conversion YOK.
```

### 4.2 Hesap (Evaluation Time = end_ts → dışarıdan argüman, GERÇEK CLOCK YOK)
1. `end_instant: Instant` → dışarıdan verilir (örneğin: son PortfolioSnapshot'ın ts'si veya replay ilerletilmiş clock_ref).
2. `end_epoch_ms = to_epoch_ms(end_instant)`
3. `start_boundary_epoch_ms = end_epoch_ms - WINDOW_MS`
4. Bir sample **WINDOW DAHİLİ** ise: `(end_epoch_ms - sample_ts_epoch_ms) <= WINDOW_MS`
   > **INCLUSION POLICY:** `≤` KULLANILIR (exactly 24h = DAHİL). `>` ise HARIÇ.

### 4.3 Boundary Matrix (DOĞRULANACAK TESTLERLE)
| # | `end - sample_ts` (ms) | Window Inclusion | Neden |
|---|---|---|---|
| B-1 | `= 0` (timestamp equality) | ✅ INCLUDED | equality dahil (user §3) |
| B-2 | `= 43_200_000` (12 saat önce) | ✅ INCLUDED | window içinde |
| B-3 | `= 86_399_999` (24h - 1ms) | ✅ INCLUDED | diff < 24h → dahil |
| B-4 | `= 86_400_000` (EXACTLY 24h) | ✅ INCLUDED | diff == 24h → `≤` dahil (user §3) |
| B-5 | `= 86_400_001` (24h + 1ms) | ❌ EXCLUDED | diff > 24h → hariç (user §3) |
| B-6 | `= 86_401_000` (24h + 1s) | ❌ EXCLUDED | diff > 24h |
| B-7 | `= -1` (gelecek, end_ts sonrası sample) | ❌ EXCLUDED | ts > end_ts olmamalı, dışarıda kabul |

---

## 5. Rolling Metrics Hesap Pipeline (5 FASE — DETERMINISTIC)

```
┌─────────────────────────────────────────────────────────────────────┐
│ S-PTF-03 build_rolling_24h() 5-Phase Pure Pipeline                 │
├─────────────────────────────────────────────────────────────────────┤
│ PHASE G1 — INPUT GUARDS (Fail-Closed AD-19)                         │
│   G1.1: end_ts non-null, UTC, parse OK                             │
│   G1.2: snapshot_samples list type (None → [])                     │
│   G1.3: her sample PortfolioSnapshot type                          │
│   G1.4: her sample.ts non-null UTC                                 │
│   G1.5: symbol ASC invariant (her sample içi positions snapshot)   │
│   → İHLAL: safe-zero result + INFO_CODES[]                         │
├─────────────────────────────────────────────────────────────────────┤
│ PHASE N2 — NORMALIZE / SORT (OoO/DUP §10)                          │
│   N2.1: DEEP COPY input list (orijinali mutate ETME)               │
│   N2.2: SORT by (ts_epoch_ms ASC, snapshot_id ULID ASC)            │
│         → Out-of-order SORT EDİLİR (reject DEĞİL)                  │
│         → Duplicate ts (aynı ms): snapshot_id ULID ASC tie-break   │
│   N2.3: NONE interpolation (missing samples → atla, sadece var olan)│
├─────────────────────────────────────────────────────────────────────┤
│ PHASE W3 — WINDOW FILTER (§4 EXACT 24h)                             │
│   W3.1: her sample için diff_ms = end_epoch_ms - sample_ts_epoch_ms│
│   W3.2: window_samples = [s for s in sorted if 0 <= diff_ms <= WINDOW_MS]│
│   W3.3: empty window → EMİR: Phase A4 → safe-zero result policy   │
├─────────────────────────────────────────────────────────────────────┤
│ PHASE A4 — ROLLING AGGREGATION (realized/fees/return/peak/dd/expo) │
│   Eğer window_samples EMPTY ise:                                   │
│     → rolling_realized_pnl_quote_24h = Decimal("0")                │
│     → rolling_fees_quote_24h = Decimal("0")                        │
│     → rolling_return_pct = 0.0                                     │
│     → rolling_peak_equity = Decimal("0")                           │
│     → rolling_drawdown_pct = 0.0                                   │
│     → exposure_max = Decimal("0"); exposure_avg = 0; exposure_end = 0│
│     → info_codes += ["EMPTY_WINDOW"]                               │
│   EĞER window_samples BOS DEĞİLSE:                                 │
│     A4.1 first_sample = window_samples[0]; last_sample = window_samples[-1]│
│     A4.2 rolling_realized_pnl_24h = last - first (realized_pnl)    │
│     A4.3 rolling_fees_24h = last - first (cumulative_fees)         │
│     A4.4 start_equity = first.equity_quote; end_equity = last.     │
│          if start_equity > 0 → return = (end-start)/start;         │
│          else → 0.0 + info_codes "ZERO_BASELINE_EQUITY"            │
│     A4.5 rolling_peak_equity = max(s.equity_quote for s in window) │
│          S-PTF-02 peak_equity state KULLANILMAZ! (Ayrı)            │
│     A4.6 if rolling_peak>0 → rolling_dd=(peak-end)/peak else 0     │
│     A4.7 exposure_max = max(s.exposure_notional for s in window)   │
│          exposure_end = last.exposure_notional                     │
│          exposure_avg = mean(s.exposure_notional for s in window)  │
│          (mean Decimal küsürat: quantize 8dp — AÇIK KARAR)         │
│     A4.8 Her sample içi positions symbol ASC agg. doğrula (invar)  │
├─────────────────────────────────────────────────────────────────────┤
│ PHASE V5 — INVARIANTS + OUTPUT BUILD                                │
│   V5.1: rolling_realized_24h type Decimal; fees24h Decimal         │
│   V5.2: return float; drawdown float [0,1] aralığı clamp (negatif? │
│         → drawdown asla negatif (peak ≥ end_eq always)             │
│   V5.3: exposure_* Decimal non-negative                            │
│   V5.4: correlation_id = last_sample.correlation_id                │
│   V5.5: causation_id = last_sample.snapshot_id                     │
│   V5.6: OUTPUT = sorted_dict[str,Any] + schema_sha256              │
│         → keys ASC sıralı (json.dumps sort_keys=True)              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. EventBus Flow (§13 — S-PLN-01 typed bus)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ S-PTF-03 EventBus Integration (External broker YOK, InMemoryTyped)       │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│ [portfolio_snapshot.v1] ──typed publish──► (S-PTF-02 yazar)              │
│         │                                                                │
│         ▼ subscribe_typed("portfolio_snapshot.v1", RollingPerfConsumer) │
│   ┌───────────────────────────────┐                                      │
│   │ RollingPerformanceSubscriber  │ (S-PLN-01 subscriber isolation)      │
│   │  - DLQ: exception → dead_letter_queue, re-publish başka subscriber'ı │
│   │    etkilemez (S-PLN-01 spec)  │                                      │
│   │  - içeride çağırılan: build_rolling_24h(snapshot samples listesi,    │
│   │    end_ts = new_snapshot.ts, corr, caus_from envelope)               │
│   └──────────────┬────────────────┘                                      │
│                  │ rolling_result_ready                                  │
│                  ▼ (opsiyonel)                                           │
│   [rolling_performance.v1] publish_with_causation(parent=new_snapshot_id)│
│   payload = rolling_sorted_dict (ASC keys)                               │
│   external broker YOK. publish True/False bayrak ile enable/disable.     │
└──────────────────────────────────────────────────────────────────────────┘
```

**Not:** `rolling_performance.v1` event tipini mevcut S-PLN-01 EventBus sözleşmesine (event_type snake_case.vN) uygun oluştur, AMA yeni canonical contract dataclass OLUŞTURMA (§8 user: zorla contract oluşturma). Publish payload = sorted_dict. Eğer downstream subscriber yoksa, bu event publish edilmeyebilir (fail-safe).

---

## 7. Sample Handling Policy (§10 — OoO / Dup / Missing)

### 7.1 Out-of-Order Samples (POLICY: SORT & NORMALIZE)
- Davranış: `REJECT YOK` — SORT edilir.
- Sıralama anahtarı: `(to_epoch_ms(sample.ts) ASC, sample.snapshot_id ULID ASC)`
- Neden: Typed EventBus üzerinden gelen asenkron snapshotlar bazen sıra dışı gelebilir (S-PLN-01 DLQ/async order). Deterministik sort → aggregation doğru.

### 7.2 Duplicate Timestamps (POLICY: Deterministic Tie-Break — ULID ASC)
- Eğer 2+ sample → aynı `ts_epoch_ms` → DETERMINISTIC tie-break: `snapshot_id ULID ASC` (ULID monoton zamanlı, unique)
- Aynı ts + aynı snapshot_id → duplicate → Sadece İLKİ tut? (AÇIK KARAR ADN-PTF03-01: DEFAULT = keep first)

### 7.3 Missing Samples (POLICY: NO INTERPOLATION)
- Window içinde 1 sample veya 1000 sample fark etmez — NO linear interpolation, NO forward fill, NO backfill.
- Sadece WINDOW içine düşen **var olan** sample'lar ile hesaplanır.
- Eğer window_samples boş (0 sample) → safe-zero result (Phase A4).
- `info_codes.append("NO_INTERPOLATION_MISSING_SAMPLES")` (eğer caller debugging isterse — opsiyonel info).

### 7.4 Empty Window Edge Cases
- Eğer end_ts, tüm sample'lardan 24h öncesi → boş → safe-zero.
- Eğer window'a tek sample düşer (first = last) → realized delta = 0, fees delta = 0, return = 0 (start = end, end - start = 0 / start > 0 → 0.0).

---

## 8. Quality Handling (§11 — CAP-2 Read-Only)

> **ZORUNLU:** QualityFlags MUTATE YOK (setattr = 0); `validate_quality` çağrısı YOK.

### 8.1 Quality Flag Policy Matrix (SALT-OKUNUR)
| Flag | Window Inclusion? | Not |
|---|---|---|
| `quality_flags.valid == False` → `invalid = True` | ❌ sample window'dan DIŞARIDA BIRAKILIR | fail-closed: invalid veri window'a dahil değil. Bu sample agg'a GİRMEZ. `info_codes += ["INVALID_SAMPLES_EXCLUDED"]` |
| `quarantined = True` | ❌ dışarıda bırakılır | Karantina sample window agg için KULLANILMAZ. |
| `stale = True` | ⚠️ Dahil EDİLİR ama info_code ekle | Stale = gecikmiş gelmiş ama ts'leri mevcut window dahil olabilir. Dahil edilir + `info_codes += ["STALE_SAMPLES_INCLUDED"]` |
| `degraded = True` | ✅ Dahil EDİLİR ama degrade info | |
| `duplicate = True` | ✅ Dahil (yukarıda §7.2 dup tie-break zaten) | |
| `out_of_order = True` | ✅ SORT edildiği için sorun yok (§7.1) | |
| `missing = True` (snapshot'ın price/data eksiği varsa upstream) | ❌ dışarıda bırakılır | S-PTF-02 fail-closed sonucu missing sample = güvenilmez, dışarıda. |

> **AÇIK KARAR ADN-PTF03-02:** invalid / quarantined / missing flaglerinden HERHANGİ BİRİ = True → sample, window_samples dışında tutulur. (Diğer 4 flag dahil).

---

## 9. Correlation/Causation Chain (§12 — BOZULMAZ)

Zincir: **StrategySignal (corr_id X) → OpportunityScore → RiskDecision → PaperOrder → PaperFill → Position → PortfolioSnapshot → RollingPerformanceResult**

- `rolling_result.correlation_id = last_snapshot.correlation_id` (ZİNCİR SABİT — upstream ile AYNI)
- `rolling_result.causation_id = last_snapshot.snapshot_id` (parent event id — bir önceki snapshot'ın event id'si)
- `rolling_result.parent_event_type = "portfolio_snapshot.v1"` (bilgi amaçlı metadata)

---

## 10. CAP-1 / CAP-2 / SAFETY 8 KATEGORİ (AST KANITLANACAK)

### 10.1 CAP-1 Forbidden Pattern (AST Visitor 0 Finding)
```
FORBIDDEN AST NODES:
  - If / elif → test: Attribute(id == "run_mode") or Name(id == "run_mode")
  - If / elif → test: Attribute(id == "source_type") or Name(id == "source_type")
  - Call: func Attribute(datetime, "now") / Name("datetime_dot_now")
  - Call: func Attribute(time, "time") / Attribute(time, "sleep")
  - Call: func Attribute(Instant, "now")
EXPECTED: 0 finding (S-PTF-03 kaynak kod bloğunda).
```

### 10.2 CAP-2 Quality Immutable
```
FORBIDDEN:
  - QualityFlags field SETATTR (Assign targets → Attribute qf.* )
  - Import or Call: "validate_quality", "validate_position", "validate_market"
EXPECTED: 0 finding.
```

### 10.3 Safety 8 Kategori
```
FORBIDDEN IMPORTS / CALLS / STRING LITERAL (hassas concat dışında):
  - exchange: ccxt, binance, bybit, exchange_client
  - network: requests, httpx, aiohttp, websockets, socket(connect), urllib
  - DB: sqlite3, psycopg, asyncpg, sqlalchemy, pymongo, redis
  - credentials: api_key, secret, "sk-", password, PRIVATE KEY
  - real execution: place_order, cancel_order, create_order, submit
  - short: PositionSide.SHORT, "short", side == "short" (S-PTF-01 long/flat var zaten invariant)
  - futures: futures, perpetual, contract_type
  - leverage>1: max_leverage_allowed > 1, leverage * 2 (S-CON-02B limits max=1 zorunlu)
EXPECTED: AST 0 finding.
```

---

## 11. Acceptance Criteria (AC Listesi — Tahmini ≥ 330 Maddelik)

### 11.1 G1 — Input Guards (14 AC)
| AC | Tanım |
|---|---|
| AC-G1-01 | `build_rolling_24h(end_ts=None)` → safe-zero result + info_code |
| AC-G1-02 | end_ts non-UTC → guard → safe-zero |
| AC-G1-03 | snapshot_samples None → empty list olarak ele alınır → empty window safe-zero |
| AC-G1-04 | snapshot_samples [Non-PortfolioSnapshot obj (int)] → safe-zero + type_error info |
| AC-G1-05 | Bir sample.ts None → dışarıda tutulur veya safe-zero (matrix test 2 varyant) |
| AC-G1-06 | end_ts > sample.ts gelecek sample → hariç |
| AC-G1-07 | BaseException (ZeroDivision mock) → safe-zero AD-19 |
| AC-G1-08 | TypeError Decimal cast hatası → fail-closed |
| AC-G1-09 | ValueError ts parse hatası → fail-closed |
| AC-G1-10 | S-PTF-02 session realized_pnl alanı field name korunur (doğrulama: PortfolioSnapshot dataclass fieldları değişmedi import check) |
| AC-G1-11 | S-PTF-02 peak_equity state DEĞİŞTİRİLMEDİ (import check) |
| AC-G1-12 | pyproject.toml dependencies=[] boş doğrulama (import sys check: import ast parse pyproject) |
| AC-G1-13 | CONTRACT_VERSION = "1.0.0" sabit doğrulaması |
| AC-G1-14 | Helper-level RollingResult dataclass (eğer kullanılıyorsa) → app/contracts/ altında DEĞİL, app/simulation/ altında doğrulanır |

### 11.2 W — Exact 24h Window Boundary ±1ms (22 AC)
- AC-W-01: B-1 equality ts = end → included
- AC-W-02: B-2 12h → included
- AC-W-03: B-3 exactly 24h - 1ms → included (matrix 3 kez varyant)
- AC-W-04: B-4 exactly 24h (86_400_000 ms) → included (5 parametrize tekrar)
- AC-W-05: B-5 24h + 1ms → excluded (5 parametrize)
- AC-W-06: B-6 24h + 1s → excluded
- AC-W-07: B-7 gelecek (end < sample) → excluded
- AC-W-08: 30 sample karışık (0 ms den 30h öne kadar, 1'er saat aralık) → window içine düşen = tam 25 (0..24h dahil) doğrula
- AC-W-09: window_samples boyut doğru, her biri inclusion check
- AC-W-10: UTC timezone conversion YOK → Instant ts'ler farklı timezone gelirse (garanti ama test) UTC parse sonrası aynı epoch ms
- AC-W-11..22: Diğer matrix varyantları (±1s, ±60s, ±30dk, ±1h boundary)

### 11.3 N — Normalize / Sort OoO / Dup (18 AC)
- AC-N-01: 5 sample reverse order (en yeni başta) → sort sonrası sıra doğru (ts ASC)
- AC-N-02: 3 sample OoO karışık sıra → sort sonrası ASC
- AC-N-03: 2 sample aynı ts_epoch_ms, farklı snapshot_id (ULID) → tie-break ULID ASC doğru
- AC-N-04: 3 sample aynı ts, 3 farklı ULID → ULID ASC sırayla
- AC-N-05: Orijinal sample listesi MUTATE EDİLMEDİ (deep copy + sort öncesi list id korundu)
- AC-N-06: Keep-first duplicate removal same snapshot_id → 1 kere tutulur
- AC-N-07: Missing samples NO INTERPOLATION → 24h window içinde 1000 sample olması beklenen yerde 100 sample var → agg doğru (100 ile)
- AC-N-08..18: Diğer OoO / dup / missing varyant (parametrize)

### 11.4 R — Rolling Realized PnL 24h (22 AC)
- AC-R-01: Empty window → rolling_realized = 0
- AC-R-02: Window'a tek sample düşer (first=last) → delta 0
- AC-R-03: 2 sample, 12h ara, first_realized=100, last_realized=250 → delta=150 Decimal
- AC-R-04: 5 sample 4h ara, monotonic artan realized → last - first doğru
- AC-R-05: Realized NEGATİF delta (loss) → delta doğru signed
- AC-R-06: Realized önce + sonra - (kar sonra kayıp) → net delta doğru
- AC-R-07: 30 sample window, her sample realized değişik → delta doğru (hesap test)
- AC-R-08: Session cumulative (S-PTF-02 alanı) ile KARIŞMAYAN doğrulama: session_realized = 5000, window delta = 150 → rolling 150 ≠ 5000 (assert NE)
- AC-R-09: Decimal 8dp quantize doğrulaması
- AC-R-10: Double-count YOK: aynı sample 2 kere agg edilmez (sort dedup var)
- AC-R-11..22: Multi-symbol delta aggregation (positions symbol ASC sort → agg test 12 parametrize)

### 11.5 F — Rolling Fees 24h (18 AC)
- AC-F-01: Empty → fees_24=0
- AC-F-02: Tek sample → fees delta=0
- AC-F-03: 2 sample first=10 last=25 → delta=15
- AC-F-04: 10 sample 2.4h ara → fees_24 doğru
- AC-F-05: Fees non-negative (sample delta negatif olamaz — upstream S-PTF-02/01 invariant). Eğer first fees > last fees → bu data error mu? info code + 0 clamp (AÇIK KARAR ADN-PTF03-03)
- AC-F-06: Decimal 8dp
- AC-F-07: Double-count YOK
- AC-F-08..18: Matrix parametrize

### 11.6 RET — Performance Return (24 AC)
- AC-RET-01: Empty window → return_pct = 0.0
- AC-RET-02: Tek sample → start=end → return=0.0
- AC-RET-03: start_eq=1000, end_eq=1100 → return=0.1 (10%)
- AC-RET-04: start=1000, end=900 → return=-0.1
- AC-RET-05: start_eq = 0 → return=0.0 + info_code ZERO_BASELINE_EQUITY (div-by-zero clamp)
- AC-RET-06: missing baseline (first sample eşik altı) → return=0.0
- AC-RET-07: start > 0, end = 0 → return=-1.0
- AC-RET-08: 20 sample window, equity artış azalış karışık → return (last-first)/first doğru
- AC-RET-09: Return type FLOAT (Decimal DEĞİL) doğrulaması
- AC-RET-10..24: Matrix (start 1000 varyant, ±0.001%, large numbers, small numbers, near-zero)

### 11.7 P — Rolling Peak Equity (18 AC)
- AC-P-01: Empty → peak=0
- AC-P-02: 1 sample eq=100 → peak=100
- AC-P-03: 5 sample [100, 120, 90, 150, 130] → peak = 150
- AC-P-04: Rolling peak S-PTF-02 peak equity'den FARKLI olabilir. Örnek: S-PTF-02 session peak 500, window içinde MAX 150 → rolling peak = 150 (SESSION peak KULLANILMAZ)
- AC-P-05: Azalan monoton equity → peak = first sample equity
- AC-P-06: Artan monoton → peak = last sample equity
- AC-P-07: 30 sample (max 10. orta, max 20. sample) → doğrula
- AC-P-08..18: Parametrize

### 11.8 DD — Rolling Drawdown (18 AC)
- AC-DD-01: Empty → rolling_drawdown=0.0
- AC-DD-02: 1 sample eq=100, peak=100 → dd=0.0
- AC-DD-03: peak=150, last_eq=120 → dd=30/150=0.2
- AC-DD-04: last_eq == peak → dd=0.0
- AC-DD-05: Rolling peak = 0 → dd=0.0 (div-by-zero guard)
- AC-DD-06: S-PTF-02 session drawdown (örnek=0.35) ile rolling drawdown (0.2) KARIŞMAZ → assert NE
- AC-DD-07: 10 sample, peak 5. sample, son sample = en düşük → dd doğru
- AC-DD-08: Drawdown [0,1] clamp doğrula (asla negatif olmaz, asla >1)
- AC-DD-09..18: Matrix parametrize

### 11.9 E — Exposure 24h (Max / Avg / End) (24 AC)
- AC-E-01: Empty → expo_max/avg/end = 0
- AC-E-02: 1 sample expo=100 → max=avg=end=100
- AC-E-03: 3 sample [100, 50, 150] → max=150, avg=100, end=150
- AC-E-04: 5 sample non-negative (leverage>1 YOK → Position side LONG/FLAT → exposure ≥0)
- AC-E-05: Ending exposure = last sample.exposure_notional (Ayrıca: Position.symbol ASC agg her sample için var)
- AC-E-06: Average quantize 8dp Decimal (mean of Decimals)
- AC-E-07: Exposure türü Decimal (float DEĞİL) doğruluğu
- AC-E-08: 2-symbol mixed portfolio, exposure aggregation symbol ASC sırasıyla → doğru topla (AD-20 determinizm)
- AC-E-09..24: Matrix

### 11.10 M — Multi-Symbol Deterministic Aggregation (30 AC)
- AC-M-01: 1 symbol (BTC/USDT) → realized24/fees/exposure doğru
- AC-M-02: 2 symbol (BTC + ETH), positions ASC sort → aggregation doğru
- AC-M-03: 5 symbol (BTC, ETH, SOL, ADA, DOT) positions ASC sort → agg doğru
- AC-M-04: Mixed portfolio (2'si FLAT qty=0, 3'ü LONG) → exposure flat olanlar 0 etkisi
- AC-M-05: Symbol sırası reverse input → agg output (sorted symbol ASC → aynı sonuç. Determinizm.)
- AC-M-06: 5 symbol 10 sample window, her symbol farklı PnL profile → 10x run aynı → determinizm (10x test DET altında)
- AC-M-07..30: Parametrize matrix (2×10 sample, 5×20 sample, mixed long/flat, different orderings)

### 11.11 Q — Quality CAP-2 Immutable (20 AC)
- AC-Q-01: invalid=True sample → window dışında tutulur
- AC-Q-02: quarantined=True → dışarıda
- AC-Q-03: missing=True → dışarıda
- AC-Q-04: stale=True → dahil, info_code var
- AC-Q-05: degraded=True → dahil
- AC-Q-06: duplicate=True → dahil (§7.2 tie-break)
- AC-Q-07: out_of_order=True → dahil (sort §7.1)
- AC-Q-08: QualityFlags setattr denendi → ContractSchemaError veya read-only frozen error → doğrulama test
- AC-Q-09: `app/simulation/portfolio.py` S-PTF-03 bloğunda `validate_quality` kelimesi greplendi → 0 match (AST grep)
- AC-Q-10..20: 7 flag tek tek + karışık varyantlar

### 11.12 BUS — EventBus Integration (S-PLN-01) (20 AC)
- AC-BUS-01: subscribe_typed("portfolio_snapshot.v1") token alınır → doğrula
- AC-BUS-02: Yeni snapshot yayınla → RollingSubscriber consume etti → build_rolling_24h çağırıldı
- AC-BUS-03: rolling_performance.v1 opsiyonel publish → parent causation_id = snapshot.id doğru
- AC-BUS-04: correlation_id subscriber → output'a taşınır (upstream ile aynı)
- AC-BUS-05: Subscriber exception → DLQ'ye düşer, başka subscriber'ı etkilemez (S-PLN-01 isolation)
- AC-BUS-06: Causation max depth 32 test (S-PLN-01 invariant)
- AC-BUS-07: External broker YOK → publish, InMemory bus üstünden doğrula (no socket/connection)
- AC-BUS-08..20: Typed event isimleri, payload sorted dict, envelope integrity, replay idempotency

### 11.13 CORR — Correlation/Causation Chain (18 AC)
- AC-CORR-01: 10-link zincirde correlation_id SABİT (StrategySignal → RollingResult — test mock chain)
- AC-CORR-02: rolling_result.causation_id = last_snapshot.snapshot_id
- AC-CORR-03: Farklı correlation_id'li sample'lar → sonuncununki kullanılır (doğru)
- AC-CORR-04: Causation parent_event_type = portfolio_snapshot.v1 (metadata)
- AC-CORR-05: EventBus publish_with_causation → causation chain trace doğru (trace_causation_chain S-PLN-01 method)
- AC-CORR-06..18: Matrix

### 11.14 CAP-1 / CAP-2 / SAFETY AST SCANS (20 AC)
- CAP1-01: AST run_mode branch → 0 finding
- CAP1-02: AST source_type branch → 0 finding
- CAP1-03: AST datetime.now → 0
- CAP1-04: AST time.time → 0
- CAP1-05: AST time.sleep → 0
- CAP1-06: AST Instant.now → 0
- CAP2-01: QF setattr → 0
- CAP2-02: validate_quality import/call → 0
- CAP2-03: validate_position import/call → 0
- SAFETY-01: exchange libs import → 0
- SAFETY-02: network import (requests/httpx/aiohttp/ws) → 0
- SAFETY-03: DB imports (sqlite3/psycopg/sqlalchemy) → 0
- SAFETY-04: credential literal regex → 0
- SAFETY-05: real-order pattern (place_order/create_order) → 0
- SAFETY-06: short pattern → 0
- SAFETY-07: futures pattern → 0
- SAFETY-08: leverage>1 pattern → 0
- CAP1SAF-19/20: Ekstra cross-check parametrize

### 11.15 SW — Single Writer AST (8 AC)
- SW-01: PortfolioSnapshot constructor call (sorted) S-PTF-03 bloğunda → 0 (SADECE okur)
- SW-02: Position constructor call → 0
- SW-03: RiskDecision constructor call → 0
- SW-04: PaperOrder / PaperFill constructor → 0
- SW-05: S-PTF-02 PortfolioSnapshotEngine methodlarının source code değiştirilmediği (sha256 orijinal ile aynı doğrulama — S-PTF-02 kod bloğu L546-1040 unchanged)
- SW-06: S-PTF-01 PositionEngine L1-523 unchanged
- SW-07: app/contracts/portfolio.py dosyasının sha'sı değişmedi (unchanged)
- SW-08: S-PTF-03 SADECE aggregation ve sort/filter → WRITE YOK (AST Assign targets for PortfolioSnapshot/Position/RiskDecision attributes → 0)

### 11.16 DET — Determinism 10x (12 AC)
- DET-01: 1 symbol + 5 sample → 10 run → rolling dict AYNI → set len=1
- DET-02: 2 symbol + 10 sample OoO → 10 run → aynı
- DET-03: 5 symbol + 30 sample, mixed flag → 10 run → aynı (sha256 set len=1)
- DET-04: Edge exact 24h boundary sample → 10 run → aynı
- DET-05: Empty window → 10 run aynı
- DET-06: Single sample window → 10 run aynı
- DET-07: Realized pozitif/negatif karışık → 10 run
- DET-08: Zero baseline return edge → 10 run
- DET-09: Rolling peak/dd exposure → 10 run
- DET-10: Sorted dict keys ASC 10 run AYNI (json.dumps sort_keys)
- DET-11: schema_sha256 10 run AYNI (digest karşılaştır)
- DET-12: 25 parametrize karma matrix (minimum — coverage)

### 11.17 REP — Replay Fixture Idempotency (8 AC)
- REP-01: json fixture (100 sample 28h replay, 5'şer dk aralık) → 1 kez build_rolling_24h ile → end_ts her step = her 30dk → output dict doğru
- REP-02: Aynı fixture 100 kez → 100 kez aynı (idempotent)
- REP-03: Replay ileri/geri sar (aynı samples list farklı end_ts'ler) → window filter doğru
- REP-04: Replay S-PLN-01 event publish (portfolio_snapshot.v1 adımlar) → rolling subscriber her adımda doğru output
- REP-05: Replay invalid sample'lar fixture dahil → dışarıda bırakma doğru
- REP-06: Correlation/causation preserved per-step
- REP-07: 1000 sample 42 gün (5dk aralık) replay subset: rolling 24h her gün 1 kez → memory bloat YOK (large list handling test)
- REP-08: Rolling result sorted dict schema_sha256 fixture SHA sabitle — hardcode assertion (fixture sha değişmezse test geçer)

### 11.18 AD19 — Fail-Closed Exception Matrix (12 AC)
- AD19-01: ZeroDivisionError (return hesap) → safe-zero
- AD19-02: TypeError Decimal → safe-zero
- AD19-03: ValueError → safe-zero
- AD19-04: OverflowError (çok büyük Decimal) → safe-zero
- AD19-05: IndexError (empty sample access) → safe-zero
- AD19-06: KeyError (field missing getattr fallback yoksa) → safe-zero
- AD19-07: AttributeError → safe-zero
- AD19-08: MemoryError (simülasyon) → safe-zero (mock)
- AD19-09: Exception hierarchy herhangi BaseException → yakalanır (AD-19)
- AD19-10..12: Üç adet mixed exception (info_codes'da error code doğru)

### 11.19 EDGE — Top-level Edge / Regression Smokes (18 AC)
- EDGE-01: S-RDH-01 (68 PASS) regression smoke import check: 1 key import passes
- EDGE-02: S-RDH-02 (64 PASS) — aynı
- EDGE-03: S-PLN-01 (42 PASS) EventBus unchanged
- EDGE-04: S-CON-02A (104 PASS)
- EDGE-05: S-CON-02B (71 PASS)
- EDGE-06: S-CON-02C (93 PASS)
- EDGE-07: S-FEA-01 (120 PASS)
- EDGE-08: S-REG-01 (302 PASS)
- EDGE-09: S-STR-01 (401 PASS)
- EDGE-10: S-OPP-01 (611 PASS)
- EDGE-11: S-RSK-01 (233 PASS)
- EDGE-12: S-RSK-02 (250 PASS)
- EDGE-13: S-PTR-01 (365 PASS)
- EDGE-14: S-PTF-01 (259 PASS)
- EDGE-15: S-PTF-02 (333 PASS / 3 SKIP unchanged)
- EDGE-16: pyproject.toml hash unchanged
- EDGE-17: contracts/portfolio.py sha unchanged
- EDGE-18: NEW TEST COUNT ≥ 250 doğrulama

### 11.20 INFO — Info Codes Doğrulama (8 AC)
- INFO-01: EMPTY_WINDOW info code eklenir mi?
- INFO-02: ZERO_BASELINE_EQUITY
- INFO-03: INVALID_SAMPLES_EXCLUDED
- INFO-04: STALE_SAMPLES_INCLUDED
- INFO-05: INTERNAL_CALCULATION_ERROR
- INFO-06: NO_INTERPOLATION
- INFO-07: NEGATIVE_FEES_DELTA_CLAMPED (ADN-PTF03-03)
- INFO-08: info_codes list ASC sorted deterministik (AD-20)

---

## 12. Definition of Done (28 DoD — S-PTF-01/02 Pattern)

| # | DoD | Kriter |
|---|---|---|
| DoD-01 | Story AC Tamamlandı | 11.1-11.20 bölüm AC'lerinin ≥%95 kadarı yazılmış ve uygulanmış. Minimum AC sayısı = ≥ 330. |
| DoD-02 | S-PTF-02 SEPARATION KORUNDU | S-PTF-02 PortfolioSnapshotEngine kaynak kodu değişmedi (sha256 blok L546-1040 değişmedi). S-PTF-03 kod S-PTF-03 bloğu sonuna append. |
| DoD-03 | PortfolioSnapshot/Position Contracts Immut | contracts/portfolio.py dosyasının sha'sı değişmedi. Public fieldlar, sırası, enum, __post_init__ — aynı. Contract_version = 1.0.0. |
| DoD-04 | New Contract Yok (§8) | app/contracts/ altında YENİ dosya YOK. Yeni rolling helper dataclass app/simulation/portfolio.py içinde (eğer kullanıldıysa). |
| DoD-05 | Stdlib-Only / pyproject DEPS=[] | pyproject.toml dependencies=[] doğrulandı. S-PTF-03 içindeki importlar: SADECE stdlib (dataclasses, decimal, enum, hashlib, json, re, copy, datetime, typing, ast, math, statistics — 3rd party YOK). |
| DoD-06 | Exact 24h Window ±1ms Doğrulandı | AC-W-01..22 (22) PASS. Inclusion/Exclusion matrix 100% coverage. |
| DoD-07 | Realized / Fees Delta Correct | Double-count YOK. Decimal 8dp. 1/2/5/multi-symbol doğru agg. |
| DoD-08 | Return Formül Edge Doğrulandı | start = window ilk sample equity. start=0 → 0 + info. (end-start)/start. |
| DoD-09 | Rolling Peak / DD BAĞIMSIZ | S-PTF-02 peak_equity state KULLANILMAZ. Rolling peak max(window samples). DD [0,1] clamp. |
| DoD-10 | Exposure 3'lü Hesap | max / avg / end — tüm Decimal non-negative. avg quantize 8dp. |
| DoD-11 | OoO / Dup / Missing Policy | OoO sort (ts ASC, ULID ASC). Dup ULID tie-break. Missing NO interpolation. Empty → safe-zero. |
| DoD-12 | Quality CAP-2 Immutable | QF setattr 0. Validate kalitesi call 0. invalid/quarantine/missing dışarıda; stale/degraded dahil. |
| DoD-13 | Corr/Caus 10/10 Zincir | correlation_id = last_snapshot.correlation_id. causation_id = snapshot_id. EventBus causation chain doğruluğu. |
| DoD-14 | EventBus Integration | subscribe_typed("portfolio_snapshot.v1") DLQ izole. Opsiyonel rolling_performance.v1 publish parent_id doğru. |
| DoD-15 | CAP-1 AST 0 Finding | run_mode/source_type branch 0. datetime.now/time.time/sleep 0. Gerçek clock YOK. |
| DoD-16 | CAP-2 AST 0 Finding | Quality mutate 0. Quality/Position/Market validator call 0. |
| DoD-17 | Single Writer AD-7/13/24 | Position/PortfolioSnapshot/RiskDecision/PaperOrder/PaperFill constructor call AST 0 match. S-PTF-03 sadece aggregation. |
| DoD-18 | Safety 8 Kategori AST 0 | exchange/network/DB/credentials/real-order/short/futures/leverage>1 → 0 match. |
| DoD-19 | Determinism 10x Kanıt | 12+ AC (DET) 10 run set len=1. sha256 aynı. sorted dict keys ASC. |
| DoD-20 | Replay Idempotent Fixture | 8+ REP test. Aynı fixture → 100 kez aynı çıktı. |
| DoD-21 | Fail-Closed AD-19 | 12+ AD19 matrix. Her exception → safe-zero result + error info code. |
| DoD-22 | Multi-Symbol (1/2/5/mixed) ASC Agg | Symbol ASC sorting öncesi agg. 30+ AC (M serisi). |
| DoD-23 | Regression NO BREAK | 3316 PASS + 7 SKIP unchanged. (Doğrulama: S-PTF-02 audit regression ile karşılaştırma). |
| DoD-24 | NEW TESTS ≥ 250 | `NEW_TOTAL_PASS - 3316 = SPTF03_NEW_PASS ≥ 250`. SKIP ≤ 3 (ekstra intentional SKIP yok ise). |
| DoD-25 | TOTAL COLLECTED ≥ 3573 | 3323 + ≥ 250 NEW. |
| DoD-26 | AST Pattern Pass Count | CAP1: 6/6, CAP2: 3/3, SW: 8/8, SAFETY8: 8/8 → TOTAL 25/25 AST 0 finding. |
| DoD-27 | No New Runtime Deps | Pip listesinde 3rd party importlar (pydantic/numpy vs) 0. sys.modules kontrol. |
| DoD-28 | Implementation Readiness 10/10 | Açık kararlar (ADN-PTF03-01..03) fixture defaultlarında kararlandı. HIKÂYEYE ÖZEL KALAN BLOKLANMAMIŞ DECISION YOK. |

---

## 13. Test Planı (MIN 250 TEST — Fixtures / Sınıflar / Matrix)

### 13.1 Test Dosyaları
| Dosya | Test Sınıfı | Hedef Sayı | Konu |
|---|---|---|---|
| `tests/simulation/test_sptf03_g1_guards.py` | TestSPTF03G1Guards | 14 | G1 input guard + contracts/pyproject unchanged |
| `tests/simulation/test_sptf03_w2_window_boundary.py` | TestSPTF03W2Window | 22 | Exact 24h ±1ms matrix |
| `tests/simulation/test_sptf03_n3_normalize_oqo_dup.py` | TestSPTF03N3Normalize | 18 | OoO/Dup/Missing + Sort |
| `tests/simulation/test_sptf03_r4_realized24.py` | TestSPTF03R4Realized24 | 22 | Rolling realized delta + session ayrımı |
| `tests/simulation/test_sptf03_f5_fees24.py` | TestSPTF03F5Fees24 | 18 | Fees delta, double-count, neg clamp |
| `tests/simulation/test_sptf03_ret6_return.py` | TestSPTF03RET6Return | 24 | Return, zero baseline, missing, edge |
| `tests/simulation/test_sptf03_p7_peak_equity.py` | TestSPTF03P7PeakEquity | 18 | Rolling peak session peak ayrımı + max |
| `tests/simulation/test_sptf03_dd8_drawdown.py` | TestSPTF03DD8Drawdown | 18 | Rolling dd, peak 0 guard, [0,1] clamp, session dd NE |
| `tests/simulation/test_sptf03_e9_exposure.py` | TestSPTF03E9Exposure | 24 | Max/Avg/End, ASC symbol agg, non-neg |
| `tests/simulation/test_sptf03_m10_multisymbol.py` | TestSPTF03M10Multi | 30 | 1/2/5/mixed, ASC determinizm |
| `tests/simulation/test_sptf03_q11_quality.py` | TestSPTF03Q11Quality | 20 | 7 bayrak + invalid/quar/missing dışarı + CAP-2 |
| `tests/simulation/test_sptf03_bus12_eventbus.py` | TestSPTF03BUS12Bus | 20 | Subscribe, publish, DLQ, corr, parent |
| `tests/simulation/test_sptf03_corr13.py` | TestSPTF03CORR13Chain | 18 | 10-link corr/caus zinciri, trace |
| `tests/simulation/test_sptf03_cap1_cap2_safety14.py` | TestSPTF03CAP1CAP2Safety14 | 20 | AST scans: CAP1 6, CAP2 3, Safety 8, + ek cross |
| `tests/simulation/test_sptf03_sw15_singlewriter.py` | TestSPTF03SW15SW | 8 | AST 0 constructor call, unchanged bloklar |
| `tests/simulation/test_sptf03_det16_determinism.py` | TestSPTF03DET16Det | 12 | 10x aynı çıktı, sha, sorted dict |
| `tests/simulation/test_sptf03_rep17_replay.py` | TestSPTF03REP17Replay | 8 | Replay fixtures 100x idem |
| `tests/simulation/test_sptf03_ad19_18_exc.py` | TestSPTF03AD19Matrix | 12 | Exception matrix fail-closed |
| `tests/simulation/test_sptf03_regression19.py` | TestSPTF03REG19Smoke | 18 | 15 hikâye regression smoke, new count, total |

### 13.2 Ortak Fixtures (conftest.py altında)
- `fixture_1symbol_5samples_24h_window`: 1 symbol BTC, 5 sample 6h aralık
- `fixture_2symbol_10samples_oOo`: 2 symbol, 10 sample, sırasız (OoO test)
- `fixture_5symbol_30samples_mixedflags`: 5 symbol, kalite bayrakları karışık
- `fixture_boundary_exact_24h`: exact 24h -1ms / 0ms / +1ms 3 sample
- `fixture_empty_window_samples`: tüm sample'lar 25h+ eski
- `fixture_replay_100samples_28h`: json load 100 sample 28h
- `fixture_sptf02_portfolio_engine_unchanged_sha`: S-PTF-02 kod blok sha sabitle

### 13.3 Toplam Tahmini Yeni Test: 14+22+18+22+18+24+18+18+24+30+20+20+18+20+8+12+8+12+18 = **386 (≥ 250 Hedef) ✓**

---

## 14. Değişecek / Eklenecek Dosyalar (Kesin)

| # | Yol | Tür | Not |
|---|---|---|---|
| 1 | `app/simulation/portfolio.py` | **EKLE (SONUNA, L1040+) — DEĞİŞTİRME (S-PTF-01/02 blokları)** | RollingPerformanceEngine (opsiyonel) + `build_rolling_24h(...)` pure fonksiyonu. S-PTF-01 (L1-523) ve S-PTF-02 (L546-1040) bloklarının içeriği DEĞİŞMEZ. |
| 2 | `tests/simulation/conftest.py` | Opsiyonel ek — fixtures 13.2 | Eğer mevcut conftest yoksa veya fixtures eksik ise, sadece fixtures ekle. |
| 3-21 | `tests/simulation/test_sptf03_*.py` | 19 yeni dosya (§13.1 listesi) | ≥ 386 yeni test (hedef ≥250 fazlasıyla karşılanır) |

### 14.1 KESİNLİKLE DEĞİŞTİRİLMEYECEK DOSYALAR (REGRESSION 3323 KORU)
- ❌ `app/contracts/portfolio.py` — CONTRACTS IMMUTABLE
- ❌ `pyproject.toml` — deps=[]
- ❌ S-PTF-01 PositionEngine kaynak kodu (L1-523)
- ❌ S-PTF-02 PortfolioSnapshotEngine kaynak kodu (L546-1040 approx)
- ❌ Tüm 15 hikâye (S-RDH-01 → S-PTF-02) özgü kaynak/test dosyaları
- ❌ `app/contracts/` — Yeni file YOK, mevcutlar unchanged
- ❌ Git add/commit/push (§24)

---

## 15. Previous Story Learnings (S-PTF-01 / S-PTF-02 — AKTARILAN)

1. **S-PTF-01 Fees Close Sonrası Reset YOK:** S-PTF-01'de Position kapatma sonrası realized_pnl session cumulative reset YOK — aynı şekilde S-PTF-03 window delta hesap, ilk ve son sample delta üzerinden gider; intermediate close/open olaylarını doğrudan handle ETMEZ (yeter ki sample'lar doğru gelsin upstream).
2. **S-PTF-02 Realized 24h alanı = Session Cumulative (PRESERVE):** `PortfolioSnapshot.realized_pnl_quote_24h = Σ position.realized_pnl_quote` (SESSION TÜMÜ). S-PTF-03 **window delta = last.window.realized - first.window.realized** (tamamen farklı). İki alan aynı isimde olabilir ama FARKLI şeyler ifade eder — AC-R-08 ile AYRIM test edilir.
3. **S-PTF-02 Peak Equity = Session Lifetime (PRESERVE):** S-PTF-02 peak_equity field session max. S-PTF-03 rolling peak = window MAX. AC-P-04 ile AYRIM test edilir.
4. **Determinism için Symbol ASC Sort ZORUNLU:** S-PTF-02 multi-symbol aggregation SHA-256 determinizmi however Position snapshot'lar symbol ASC → aynı input → aynı sıra → aynı agg. S-PTF-03'ün A4.8 phase'inde her sample positions ASC kontrol + window agg sonrası rolling sonuç ASC key dict — 10x run aynı.
5. **Fail-Closed AD-19 Pattern:** S-PTF-01/02 de outer try-except BaseException, info_codes. Aynısı S-PTF-03'te.
6. **AST Forbidden Patterns Regex / Visitor:** S-PTF-02 audit'te çalışan ast.NodeVisitor patternleri S-PTF-03 için birebir (CAP1/CAP2/Safety8) — fixture copy-paste.
7. **AST Single Writer Checks:** S-PTF-02'de Position ve PortfolioSnapshot constructor call AST 0 match doğrulaması — aynısı S-PTF-03 için 8 SW AC (§11.15).

---

## 16. Out of Scope (§22 KULLANICI VERBATİM — HİÇBİRİ YAPILMAYACAK)

- ❌ Risk Engine değişikliği
- ❌ daily-loss policy değişikliği
- ❌ Backtest
- ❌ AI/ML
- ❌ exchange
- ❌ live trading
- ❌ database
- ❌ dashboard
- ❌ strategy
- ❌ opportunity
- ❌ PaperFill
- ❌ Position Engine
- ❌ PortfolioSnapshot contract değişikliği (yeni field, yeni contract ZORLA OLUŞTURMA)
- ❌ S-PTF-04 veya başka story geçiş (§24)
- ❌ Git commit oluşturma (§24)

---

## 17. Dependencies (§23 — Stdlib-Only, 0 Yeni Runtime Dep)

```
pyproject.toml dependencies = []  # DEĞİŞMEZ.
S-PTF-03 İÇİ KULLANILAN STANDART KÜTÜPHANELER (ALLOWED):
  - dataclasses
  - decimal
  - enum
  - re
  - hashlib
  - json
  - copy (deepcopy)
  - datetime (SADECE UTC Instant parse — datetime.now YASAK CAP-1)
  - typing (Any, Optional, Union, list, dict, tuple, Type)
  - ast (test AST scan için import allowed source; production kod allowed)
  - math / statistics (exposure avg, mean Decimal)
  - string
FORBIDDEN (3rd Party — 0 match):
  - pydantic, msgspec, cattrs, attrs
  - numpy, pandas
  - ta, ta-lib
  - ccxt, requests, httpx, aiohttp, websockets, aiohttp
  - sqlalchemy, psycopg2, asyncpg, sqlite3 (DB)
  - redis, kafka
  - sklearn, tensorflow, torch, catboost (AI/ML)
```

---

## 18. Açık Kararlar (ADN-PTF03-01..05 — Hikâye Seviyesinde Fixture Default Kararlar)

> Her AÇIK KARAR default fixture ile yazılır; geliştirici/operatör isterse parametre override edebilir. Bunlar story seviyesinde BLOCK DEĞİL; implementasyonda defaultları kesinleştirilmeli.

| ADN | Konu | Default Karar (Fixture) | Not / Gerekçe |
|---|---|---|---|
| ADN-PTF03-01 | **Duplicate same snapshot_id keep policy** | Keep first (daha önce gelen tutulur, sonrakiler drop) | Determinism için ilk veya son önemli; ilk tutmak S-PTF-02 S-PTR-01 ile tutarlı. |
| ADN-PTF03-02 | **Quality hangi flag'ler window'dan dışarı atılır?** | invalid / quarantined / missing (3 flag True → dışarı). Diğer 4 (stale/degraded/dup/out_of_order) → dahildir. | Fail-closed: invalid/quarantine/missing = güvenilmez veri → dışarı. Stale/degraded: dahil ama info code. |
| ADN-PTF03-03 | **Negative fees delta clamp (first > last)** | Clamp to 0 + info_code NEGATIVE_FEES_DELTA_CLAMPED. Negatif fees upstream invariant ihlali (fees monotonik artmalı S-PTF-01/02), fakat S-PTF-03 fail-safe → 0. Aksi takdirde negatif rolling_fees (kazanç) yanlış sinyal. | |
| ADN-PTF03-04 | **Empty window'da correlation_id / causation_id nasıl doldurulur?** | Eğer orijinal input snapshot_samples boş değil ama window boş ise (tüm 25h+ eski) → correlation_id/causation_id = EN YENİ sample'ın (input samples listesinin sonuncusu, ts olarak en yeni). Eğer input tamamen boş ise → corr="CORR_UNKNOWN_ROLLING", caus="CAUS_UNKNOWN_ROLLING" (sabit ULID-like string 8+ chars). | Determinizm için sabit stringler. |
| ADN-PTF03-05 | **Rolling_performance.v1 opsiyonel publish — default?** | `publish_enabled: bool = False` (default OFF). Caller argüman olarak True verirse publish. | No out-of-scope: external consumer olmadığı için default kapalı. DoD-14 AC-BUS testi publish_enabled=True/False 2 varyant. |

---

## 19. Implementation Readiness Check (10+ Item Checklist — READY)

| # | Hazırlık Öğesi | Durum | Not |
|---|---|---|---|
| 1 | Contracts PortfolioSnapshot/Position READY (IMMUTABLE) | ✅ READY | S-CON-02B v1.0.0 — field list, invariants, import path biliniyor. |
| 2 | S-PLN-01 EventBus READY | ✅ READY | subscribe_typed, publish_with_causation, DLQ — API mevcut. |
| 3 | S-PTF-02 Session Cumulative Samples READY | ✅ READY | Üst story'den PortfolioSnapshot üretimi mevcut (input ready). |
| 4 | Baseline PASS/SKIP Biliniyor | ✅ READY | 3316 PASS + 7 SKIP = 3323 collected |
| 5 | Test Altyapısı (pytest, parametrize, fixtures, AST scan helpers) | ✅ READY | S-PTF-01/02 test patternleri mevcut, copy-paste adaptasyon. |
| 6 | Determinism Pattern (10x/sha256/sorted dict) | ✅ READY | S-PTF-01/02'den kanıtlanmış pattern. |
| 7 | OoO/Dup/Edge Sample Handling Defaultları (ADN-01/02/03/04/05) | ✅ READY | Default fixture kararları §18'de listeli. |
| 8 | Yeni Dosya Sayısı (1 kaynak + 19 test) — Boyut Planlanabilir | ✅ READY | S-PTF-01/02 pattern — kolay uygulanır. |
| 9 | pyproject deps=[] boş, stdlib-only zorunluluk biliniyor | ✅ READY | 3rd party forbidden list §17 |
| 10 | Regression 15 hikâye isimleri ve baseline test breakdown'ı | ✅ READY | Ön koşullar §2'de tek tek listeli. |
| 11 | No Breaking Changes for S-PTF-01/02 pattern | ✅ READY | Sonuna append — S-PTF-01/02 kod blokları unchanged (sha karşılaştırma) |
| 12 | Safety 8 Kategori + CAP1/CAP2/SW AST test methodları biliniyor | ✅ READY | S-PTF-02 audit patternleri kopyalanabilir. |

**Toplam Implementation Readiness: 12/12 (100%) — READY FOR IMPLEMENTATION (bmad-dev-story sonrası)**

---

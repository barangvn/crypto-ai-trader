---
story_id: "S-STR-01"
story_key: "S-STR-01"
title: "Trend Following + Momentum Strategy Engine (AD-9 / AD-25 / CAP-1 / CAP-2 / CAP-3 Pure Strategy Plugins)"
epic: "E-STR — Strategy Engine (Epic 7)"
status: "ready-for-dev"
created: 2026-08-25
updated: 2026-08-25
author: "bmad-create-story v1"
tags: [strategy, trend_following, momentum, AD-9, AD-25, CAP-1, CAP-2, CAP-3, deterministic, pure, stdlib-only, long-only, v1]
baseline_commit: "d93dc15 feat: implement deterministic market regime detection"
previous_story: "S-REG-01"
next_story: "S-OPP-01 (OpportunityScore - Out of Scope bu hikâyede)"
contract_version_preserved: "1.0.0"
contracts_used:
  - "FeatureVector (app/contracts/feature.py) — S-FEA-01 fea_01_v1 12-key"
  - "MarketRegime (app/contracts/regime.py) — AD-8 6-state + MarketRegimeState enum"
  - "StrategyContext (app/contracts/strategy.py) — AD-25 Typed Pure Input DTO"
  - "StrategySignal (app/contracts/strategy.py) — S-CON-02A v1 Hard Boundary, SignalDirection = {long, flat, hold}"
  - "SignalDirection, StopPolicySpec, TakeProfitPolicySpec — mevcut contract, DEĞİŞTİRİLMEYECEK"
test_baseline_count: 864
test_baseline_passed: 864
feature_version_expected_input: "fea_01_v1"
detector_version_expected_input: "reg_01_v1"
strategy_version_story_default: "str_01_v1"
runtime_dependencies_new_allowed: 0  # stdlib-only — pyproject.toml dependencies=[] DEĞİŞMEZ
v1_hard_boundary_long_only: true  # short YASAK; leverage YASAK; futures YASAK; NO ORDER
---

# S-STR-01 — Trend Following + Momentum Strategy Engine (2 Pure Strategy Plugin, AD-9/AD-25/CAP-1/CAP-2/CAP-3)

## 1. Amaç ve Genel Bakış

**User Story (BDD):**
> Bir Strategy Engine tüketicisi (Opportunity Scorer, Risk Engine, Portfolio Paper Simulator, AD-9 downstream bağımsız modüller) olarak,
> Sadece tek bir girdi olarak **typed `StrategyContext`** (S-CON-02A AD-25; içinde FeatureVector + MarketRegime + as_of + clock_ref + eligibility_ctx + scoring_policy + run_mode/source_type metadata) verildiğinde,
> **İlk 2 saf (pure) strategy plugin**'ini üretmek istiyorum:
>   1. **Trend Following** (EMA + RSI + VWAP + regime uyumlu)
>   2. **Momentum** (mom_10_abs / mom_10_pct + RSI + regime uyumlu)
> Öyle ki her strategy, deterministik olarak `StrategySignal` (S-CON-02A §3.9) + correlation_id & causation_id **parent context ile AYNI** döndürsün,
> AYNI StrategyContext → 10 TEKRAR → AYNI StrategySignal (aynı sorted dict, aynı SHA-256) (AD-20),
> Strategy kodu İÇİNDE `if run_mode == ...` veya `if source_type == ...` BRANCH YOK (CAP-1),
> Kalite bayrakları (stale/invalid/quarantined/degraded/duplicate/out_of_order/missing) OKUNUR (tek başına strategy dışında caller tarafından ctx.eligibility_ctx ya da quality_hint helper OKUNUR) — **NE KALİTE VALIDATOR TEKRAR ÇAĞIRILIR (CAP-2)** NE DE strategy içinde network / DB / FS / exchange çağrısı YOK (CAP-3),
> **Yetersiz lookback** (FeatureVector null_count / 9_nullable_features ≥ ADN-STR-03) ya da **yanlış feature_version** → strategy `direction=flat/hold` + düşük signal_strength + confidence düşük + `reasons[]` ile explain etsin,
> `sideways` / `transition_uncertain` rejimlerinde (AD-8), **regime eligibility** kuralı ile strateji ya atlar (flat/hold, düşük confidence) ya da çok düşük strength ile çalışır (ADN-STR-07/08),
> Strategy output **SADECE:** `long / flat / hold` — **short YOK**, **leverage YOK**, **futures YOK**, **PAPER ORDER PRODUCE ETMEZ** (NO OUT OF SCOPE),
> `pyproject.toml dependencies = []` DEĞİŞMEZ, stdlib-only.

### Hedef
Mevcut 4 contract (FeatureVector / MarketRegime / StrategyContext / StrategySignal) **DEĞİŞTİRİLMEDEN** (hiçbir public alan, public import, enum değeri, contract_version **DEĞİŞMEZ**), 2 saf strategy plugin + 1 shared StrategyHelper (threshold defaults + eligibility + quality effects yardımcıları) oluştur. Bu hikâyede **SADECE:** `StrategyContext → StrategySignal` yönünde (tek yönlü deterministik fonksiyon). **Hiçbir şekilde OpportunityScore / RiskDecision / PaperOrder / Fill üretimi YOK (OOS).**

### Ön Koşullar (BAŞLANGIÇTA DOĞRULANACAK)
✅ **864 / 864 FULL regression PASS** (S-RDH-01 68, S-RDH-02 64, S-PLN-01 42, S-CON-02A 104, S-CON-02B 71, S-CON-02C 93, S-FEA-01 120, S-REG-01 302) — BU HİKÂYE SONRASI EN AZ `864 + ≥240 = 1104+` test hedeflenir. **864 regression BOZULMAYACAK.**
✅ `app/contracts/strategy.py` mevcut:
  - `StrategyContext` (10+ field AD-25 typed DTO)
  - `StrategySignal` (strategy_id, strategy_version, direction ∈ {long/flat/hold}, signal_strength ∈ [0,1], confidence [0,1], supporting_feature_keys, supporting_regime_evidence, correlation_id, causation_id, entry_thesis, entry_price_ref, stop_policy, take_profit_policy, expected_edge_bps)
  - `SignalDirection` enum 3 değer (short YOK)
✅ `app/contracts/feature.py` mevcut + `FEATURE_SCHEMA_REGISTRY['fea_01_v1']` 12-key kayıtlı
✅ `app/contracts/regime.py` mevcut + `MarketRegimeState` 6 enum (bull, bear, sideways, high_volatility, low_volatility, transition_uncertain)
✅ `pyproject.toml dependencies = []` — stdlib-only
✅ `CONTRACT_VERSION = "1.0.0"` (BU HİKÂYEDE BUMP YOK — geriye dönüş)
✅ Hard Safety: short / leverage>1 / futures / network / credentials / DB / exchange çağrısı YOK (S-RDH-02 credential scan + C-FND-03 forbidden tests, devam ettirilecek)
✅ **`StrategyContext.run_mode / source_type` FİELD OLARAK VAR AMA strategy KODU BRANCH YAPMAYACAK (CAP-1)** — bu alanlar sadece metadata/logging için ctx içinde taşınır, evaluate içinde hiçbir `if` YOK.

### Değişmez Mimari Kurallar (HİÇBİR KOŞULDA İHLAL EDİLEMEZ)
| Kural | Kaynak | Davranış |
|---|---|---|
| AD-9 Strategy Purity | ARCHITECTURE-SPINE §AD-9 | Strategy plugin SADECE typed `StrategyContext` alır → `StrategySignal` döndürür; NO network / NO DB / NO filesystem / NO exchange importu. Pure fonksiyon. |
| AD-25 StrategyContext Typed Input | ARCHITECTURE-SPINE §AD-25 | Strategy, input olarak YALNIZCA `StrategyContext` (AD-25 DTO) KULLANIR; doğrudan envelope/candle/orderbook okumaz. |
| CAP-1 Replay/Live Parity | SPEC CAP-1 | `app/strategies/` klasör kaynak kodunda `run_mode` veya `source_type` isimli `If/Attribute` dallanması 0 — AST tarayıcı 0 finding. Aynı StrategyContext → Aynı StrategySignal (determinizm). |
| CAP-2 Quality Flags Read-Only | SPEC CAP-2 | Strategy, kalite bayraklarını **OKUR** (ya kalite caller tarafından `ctx.eligibility_ctx.reasons[]` vasıtasıyla zaten taşınır ya da helper aracılığıyla salt-okunur QualityHint OKUNUR). **NE MUTATE EDER, NE VALIDATOR TEKRAR ÇAĞIRIR.** |
| CAP-3 Strategy Plugin Isolation | SPEC CAP-3 | `app/strategies/` klasörü için forbidden import scan (requests/httpx/websocket/asyncpg/psycopg/sqlalchemy/pydantic/ccxt/numpy/pandas/ta-lib/kafka/redis) → 0 match. |
| AD-20 Determinism | ARCHITECTURE-SPINE §AD-20 | Aynı StrategyContext girdisi → 10 kez → Aynı StrategySignal. `to_sorted_dict()` eşit; `schema_sha256()` eşit. |
| AD-8 Regime Independent Service Boundary | ARCHITECTURE-SPINE §AD-8 | Strategy, MarketRegime'i READ-ONLY OKUR; rejim engine çağırmaz. |
| AD-22 FeatureVector Version Contract | ARCHITECTURE-SPINE §AD-22 | Strategy YALNIZCA **`feature_version = "fea_01_v1"` → 12-key SPEC okur.** Başka feature_version → `direction=flat/hold` + düşük sinyal (veya ADN-STR-02 varyant 1: raise ContractSchemaError, varsayılan varyant 2 = flat/hold). |
| AD-17 End-to-End Corr/Caus | ARCHITECTURE-SPINE §AD-17 | StrategySignal `correlation_id` = parent `StrategyContext.correlation_id` (veya envelope'dan derive edildi). `causation_id` = parent context `causation_id` (korunur; strategy kendisi yeni causation üretmez). |
| v1 Hard Safety | PRD Hard Boundaries + CONTRACTS §3.9 v1 sınırı | short / lev>1 / futures / network / credentials / ML / pandas / numpy / ta-lib / ccxt / requests / sqlalchemy YOK — AST + grep 0 finding. `direction ∈ {long, flat, hold}` OLMAK ZORUNDA. |
| Yeni Contract YOK (Kullanıcı KURAL) | User HARD kural | `StrategyContext`, `StrategySignal`, `SignalDirection`, `MarketRegime`, `FeatureVector` **public API / field sayısı / enum DEĞERLERİ** %100 KORUNUR. BU HİKÂYEDE **YENİ BİR CONTRACT DATACLASS/ENUM OLUŞTURULMAZ**. Helper class olabilir (QualityHint gibi frozen=True dataclass, AMA contracts klasörüne KAYDEDİLMEZ; `app/strategies/` içinde tutulur). |
| NO ORDER / NO RISK (Kullanıcı OOS kuralı) | User HARD kural | Strategy SADECE `StrategySignal` üretir. **RiskDecision / PaperOrder / PaperFill / Position / OpportunityScore** PRODUCE ETMEZ — bunlar OOS. |
| Replay/Live parity: Sıfır dal | Kullanıcı HARD kural | Aynı StrategyContext 10x → aynı StrategySignal (aynı sha-256). |

---

## 2. Mimari Uyum & Bağlam Devamlılığı (S-REG-01 Sonrası — 9. Halka)

### 9-Halka Korelasyon Zincirine Ekleme (AD-17, AD-23)
```
[CanonicalCandle → S-PLN-01 Typed EventBus]
    ↘ input_refs[] + lookback_window + S-FEA-01 FeatureEngine
        ↘ FeatureVector (S-FEA-01, AD-22, 12-key fea_01_v1)
            ↘ MarketRegime (S-REG-01, AD-8, 6-state + confidence + 6 scores)
                ↘ StrategyContext (S-CON-02A AD-25)  ← OKUNDU
                    ↘ StrategySignal (S-STR-01, 2 strategy: Trend / Momentum)  ← BU HİKÂYE: TEK YÖNLÜ
                        ↘ OpportunityScore → RiskDecision → PaperOrder → Fill → Portfolio (OOS)
```

> **NOT:** Bu hikâyede **OpportunityScore / Risk Engine / PaperOrder / Portfolio** üretimi KESİNLİKLE YOK — OOS (Out-of-Scope). SADECE: `StrategyContext → StrategyPlugin.evaluate(ctx) -> StrategySignal`.

### Kalıtsal Geliştirici Notları (S-REG-01 Lessons Learned + ADN)
1. **ULIDISH underscore uyumlu regex:** `_ULIDISH_RE = r"^[A-Za-z0-9_\-]{8,}$"` — correlation/causation için S-CON-02A zaten türünü garanti eder; strateji bunları SADECE kopyalar.
2. **Credential tarayıcı false-positive önlemi:** Hassas substrları DOĞRUDAN STRING YAZMA; `chr(ord('B')) + chr(ord('I')) + ...` runtime concat. `BINANCE_API_KEY`, `SECRET`, `LEVERAGE_2X` benzeri.
3. **CAP-1 AST tarama paterni:** `ast.NodeVisitor` If/test + Attribute (`expr.attr == "run_mode"` / `"source_type"` / `Name.id == "run_mode"`/`"source_type"`) — 0 finding doğrulaması. S-REG-01'de çalıştı; aynısı burada.
4. **10x determinizm test kalıbı:** 10 kez → `set(schema_sha256 for _ in range(10)) == 1` → PASS (aynı girdi aynı çıktı).
5. **Zero-denominator fallback:** Div-by-zero → 0.0 ya da fallback direction (flat/hold).
6. **Forbidden libs (22 tane):** `["requests", "httpx", "websockets", "asyncpg", "psycopg2", "sqlalchemy", "pydantic", "pandas", "numpy", "talib", "ta", "ccxt", "kafka", "redis", "aiohttp", "boto3", "django", "flask", "fastapi", "torch", "tensorflow", "catboost"]` — import scan 0 match.
7. **Threshold üretim/ayırma kuralı:** Üretim decision ile test fixture default karıştırma! Defaultlar `app/strategies/defaults.py` içinde frozen=True dataclass ile tut; test fixture **override edebilir** (kalıcı production kararı DEĞİLDİR). Aşağıda ADN-STR-01..12 olarak her eşik testte override edilebilir (production defaultlar bu hikâyede "sensible starting values" olarak AYARLANIR ama fixture override'larıyla doğru test edilir — KESİNLİKLE fixture values production'a karıştırılmaz; production = ADN defaults; test = fixture override).

---

## 3. Dosya Yapısı (Kesin)

### 3.1 Yeni Dosyalar (Oluşturulacak — 14 dosya, 2 kaynak + 12 test)

| # | Mutlak Yol | Kapsam | Satır Tahmini | Not |
|---|---|---|---|---|
| 1 | `app/strategies/__init__.py` | Public API: `TrendFollowingStrategy`, `MomentumStrategy`, `DEFAULT_STRATEGY_PARAMS` (sabit), `STRATEGY_VERSION_STORY_DEFAULT`, `QualityHint_for_Strategy` (opsiyonel: sadece caller ctx dışarıdan kalite geçirirse kullanılır — CAP-2 READ-ONLY, frozen=True) | 30–60 | Modül init; `__all__` 6–8 isim. **Contracts klasörüne DOKUNULMAZ; contracts importları kullanılır ama mevcut contracts DEĞİŞTİRİLMEZ.** |
| 2 | `app/strategies/base.py` | (Opsiyonel) Shared abstract base ya da 2 shared helper: (a) `_validate_context_version(ctx)` (feature_version = fea_01_v1); (b) `_compute_shared_eligibility(ctx, params)` — regime eligibility / insufficient lookback / quality effects / flat fallback. | 250–400 | stdlib-only. Sadece mevcut contracts import eder. **Hiç yeni contract oluşturmaz.** Frozen=True Options class: `StrategyOptions`; `TrendStrategyOptions`; `MomentumStrategyOptions`. |
| 3 | `tests/strategies/test_sstr01_trend_happy.py` | Trend happy path: 4 varyant (strong bull / moderate bull / bear engel → flat / low_volatility long) | 220 | 20+ test |
| 4 | `tests/strategies/test_sstr01_trend_regime_eligibility.py` | Trend: 6 rejim x 2 varyant = 12 test. Bull/LV long eligible; bear/hv/sideways/TU → eligibility logic (flat/hold) | 260 | 24+ test |
| 5 | `tests/strategies/test_sstr01_trend_ema_confirm.py` | Trend EMA ilişkileri: price vs ema_14; ema_14 vs ema_28; confirmation delay (ADN-STR-05); false break filter | 260 | 26+ test |
| 6 | `tests/strategies/test_sstr01_momentum_happy.py` | Mom happy path: abs+pct yüksek → long; düşük → flat; RSI filter | 220 | 22+ test |
| 7 | `tests/strategies/test_sstr01_momentum_thresholds.py` | Mom threshold: low_band / mid_band / high_band; RSI overbought/oversold filter; quality effects | 260 | 24+ test |
| 8 | `tests/strategies/test_sstr01_edge_cases.py` | 2 strateji için insufficient lookback, sideways, transition_uncertain, wrong feature_version, null EMA, RSI 50, stale/degraded → düşük strength/invalid quarantine → flat | 320 | 30+ test |
| 9 | `tests/strategies/test_sstr01_signal_output.py` | 2 strateji: signal_strength ∈ [0,1], confidence [0,1], direction sadece long/flat/hold, short forbidden, supporting_feature_keys REGISTRY içinde, supporting_regime_evidence keyset REGIME_KEYS subset | 260 | 24+ test |
| 10 | `tests/strategies/test_sstr01_quality_cap2.py` | CAP-2: QualityHint frozen=True; validator 0 çağrı; stale/invalid/quarantined/degraded/dup/missing/ooo 7 kalite modu → expected flat/hold ya da düşük strength | 300 | 28+ test |
| 11 | `tests/strategies/test_sstr01_determinism_cap1.py` | CAP-1 AST scan: 0 `if run_mode` / `if source_type`; 10x determinizm (her 2 strateji 10x aynı sha-256); leakage AST | 320 | 32+ test |
| 12 | `tests/strategies/test_sstr01_safety_regression.py` | Credential 0 match, network 0 match, strategy purity forbidden import 22 lib 0, 864 regression PASS (subset import smoke 24 import + 12 story import), pyproject deps=[], CONTRACT_VERSION 1.0.0, `app/contracts/strategy.py` unchanged sha, forbidden short enum test | 340 | 34+ test |
| 13 | `tests/strategies/test_sstr01_correlation_causation.py` | 2 strateji: ctx.correlation_id → signal.correlation_id AYNI; causation_id korunur (parent = child); ULID-like length doğrulaması; 10x run'da corr/caus DEĞİŞMEZ (sabit) | 200 | 18+ test |
| 14 | `tests/strategies/test_sstr01_integration_chain.py` | (DoD-14 benzeri) Tam zincir: 1h candle payload → FeatureVector (fea_01_v1, 12-key) → MarketRegime (S-REG-01 RegimeEngine) → StrategyContext (derive_from_envelope) → TrendStrategy + MomentumStrategy evaluate → 2 StrategySignal. Bus publish 4 olay, correlation_id AYNI, causation ardışık → PASS | 220 | 20+ test |

**Toplam Yeni Test Tahmini (12 dosya):** 20+24+26+22+24+30+24+28+32+34+18+20 + parametrize varyantlar = **≥ 300 yeni test.** (864 regression bozulmadan; hedef 864 + 240 = 1104+; 300>240 → ✅ hedef tutuldu / aşıldı)

### 3.2 DEĞİŞTİRİLECEK DOSYALAR — 0 ADET (KESİN)
Bu hikâyede **hiçbir mevcut kaynak dosyası DEĞİŞTİRİLMEZ.** Sadece YENİ dosya oluşturulur:
- ❌ `app/contracts/*.py` — HEPSİ dokunulmuyor. `StrategyContext`, `StrategySignal`, `SignalDirection`, `CONTRACT_VERSION="1.0.0"` + 80+ `__all__` sırası %100 KORUNUR.
- ❌ `app/regime/*.py` — S-REG-01 kaynak dokunulmuyor.
- ❌ `app/features/*.py` — S-FEA-01 kaynak dokunulmuyor.
- ❌ `pyproject.toml` — `dependencies=[]` DEĞİŞMEZ.
- ❌ S-RDH-01/02, S-PLN-01, S-CON-02A/B/C, S-FEA-01, S-REG-01 test dosyaları — dokunulmaz (regression onayı).
- ❌ `.gitignore` varsayılan (bu hikâyede değiştirilmek istenirse fixture exclude yolu ayrı hikâye).

### 3.3 Out of Scope (Kesin — OOS)
- ❌ OpportunityScore, AI scoring, Champion Challenger (S-OPP-01 / S-AIS-01 / S-CON-02C implementasyon — OOS)
- ❌ Risk Engine, Kill Switch, Limits, Position Sizing (E-RSK — OOS)
- ❌ PaperOrder, PaperFill, Fill Model (E-PTR — OOS)
- ❌ Backtest Engine, Portfolio Simulator (E-BKT / E-SIM — OOS)
- ❌ Exchange / API Key / Credential / WS / DB / Redis / Kafka / Object Storage (E-PLN / E-STORAGE — OOS)
- ❌ AI/ML/Model training/inference, Feature Leakage AD-16 (E-AIS — OOS)
- ❌ Dashboard / API (E-API — OOS)
- ❌ Pandas / NumPy / TA-Lib / ccxt / pydantic / msgspec / cattrs — yeni runtime import YASAK
- ❌ Yeni contract oluşturma; contracts klasörü değişimi — YOK
- ❌ Short enum ekleme, leverage field ekleme, futures alan ekleme — YOK (v1 boundary; contract bump gerektirir, bu hikâye bump YOK)
- ❌ Production eşik kararları (fixture defaults vs. production decision). Aşağıda "ADN açık kaldı" listesinde bunlar AÇIK KALIR (bu hikâye fixture defaults = sensible başlangıç; production karar ayrı ADN-01/ADN-02 toplantısında alınır).

---

## 4. Algoritma Detayları (ZORUNLU SPEC — Açık Kararlar Ayrıca Listelendi)

### 4.1 Genel Strategy Sözleşmesi (Public API, 2 Plugin + Shared)

**Class signature (stdlib-only, stdlib `dataclasses` + `typing`):**

```python
from dataclasses import dataclass, field
from typing import Any
from app.contracts.feature import FeatureVector
from app.contracts.regime import MarketRegime, MarketRegimeState, REGIME_KEYS
from app.contracts.strategy import StrategyContext, StrategySignal, SignalDirection
from app.contracts.types import Instant, ULID

# ----------------------- Kalite İpucu (CAP-2 READ-ONLY WRAPPER — frozen=True) -----------------------
# NOT: contracts/ klasörüne YAZILMAZ; sadece strategies içinde helper. DEĞİŞTİRİLMEDİN.
@dataclass(frozen=True)
class StrategyQualityHint:
    """S-CON-02A eligibility_ctx zaten quality etkilerini taşır.
    Ekstra caller kalite ipucu geçmek isterse (örn dışarıdan event quality_flags okunur) — BUNU kullanır.
    NE QualityFlags'i MUTATE EDER, NE VALIDATOR TEKRAR ÇAĞIRIR.
    Tüm boolean: True = problemli. Default hepsi False (temiz)."""
    stale: bool = False
    invalid: bool = False
    quarantined: bool = False
    degraded: bool = False
    duplicate: bool = False
    out_of_order: bool = False
    missing: bool = False
    abnormal_spread: bool = False

# ----------------------- Strategy Defaults / Options (FROZEN — production default, TEST OVERRIDE EDİLEBİLİR) -----------------------
# ÖNEMLİ KURAL (Fixture vs. Production karıştırma ÖNLEMİ):
#   - Aşağıdaki DEFAULTS, production için "sensible başlangıç" ADN değerleridir.
#   - Test fixtureları, StrategyOptions/TrendStrategyOptions/MomentumStrategyOptions DEEP COPY ile override eder.
#   - BU HİKÂYEDE production kararı alınmaz; test fixtureları defaults üretimden bağımsız çalışır.
#   - Production kalıcı karar ADN-STR-01/02/... toplantısında alınır; bu hikâyede defaults = başlangıç noktasıdır.

@dataclass(frozen=True)
class StrategyOptions:
    # Ortak (her iki strateji için de geçerli)
    expected_feature_version: str = "fea_01_v1"           # ADN-STR-02 (default varyant 2: flat/hold — raise değil)
    expected_detector_version: str = "reg_01_v1"          # ADN-STR-02B — sürüm tutarsızlığı → flat
    unexpected_version_mode: str = "flat_hold"            # "flat_hold" | "raise" (default: flat_hold — v1 gracedown)
    null_count_pct_insufficient_lookback: float = 0.500   # ADN-STR-03: null_count / 9_nullable_features >= ? → insufficient
    signal_strength_floor: float = 0.05                   # flat/hold için kullanılan sinyal gücü alt sınırı (0.05–0.20 arası default 0.05)
    confidence_on_insufficient: float = 0.10              # yetersiz lookback'te confidence
    # Regime eligibility (AD-8): HANGİ rejimlerde strateji ÇALIŞIR (değilse flat/hold + düşük confidence)
    # Trend: bull ve low_volatility eligible; bear reverse YOK (v1 long-only); sideways/TU eligible değil; high_volatility → ADN-STR-07 (güç 0.3 ile ya da flat)
    # Mom:  bull ve low_vol + momentum yüksek HV de; bear reverse YOK; sideways/TU flat.
    # Kalite penalty (0.0–1.0, confidence çarpanı):
    quality_penalty_invalid_quarantined: float = 0.15     # invalid/quarantine → confidence 0.15x + direction flat
    quality_penalty_stale_degraded: float = 0.60          # stale/degraded → 0.60x
    quality_penalty_dup_missing_ooo: float = 0.85         # duplicate/missing/ooo → 0.85x
    quality_penalty_abnormal_spread: float = 0.80         # spread abnormal → 0.80x
    # Sinyal aralığı clamp (özellikle signal_strength ve confidence HER ZAMAN [0,1] aralığına clamp):
    clamp_min: float = 0.0
    clamp_max: float = 1.0

@dataclass(frozen=True)
class TrendStrategyOptions(StrategyOptions):
    # Trend Following Özel Eşikler — BU HİKÂYEDE default; fixture override.
    # Trend eligibility bileşenleri (3'ü):
    # 1) price > ema_14 (yukarı kırılım)
    # 2) ema_14 > ema_28 (üstel kesişim onayı)
    # 3) rsi_14 >= rsi_entry_min (RSI aşırı satımdan dönüş + zayıf aşırı alımdan kaçınma)
    # 4) (isteğe bağlı) vwap onayı: close >= vwap_20 (yoksa NO — feature_version içinde vwap_20 VAR mı? S-FEA-01 12-key'de vwap_20 YOK; 12 key'de vwap yoksa bu bileşen 1.0 ile çarp, feature yoksa devre dışı)
    price_vs_ema14_min_gap_bps: float = 30.0    # 30 bps = %0.30 — price EMA14'yi yukarı kırmış olsun
    ema14_vs_ema28_min_gap_bps: float = 10.0    # EMA14, EMA28'i en az 10 bps geçsin
    rsi_entry_min: float = 48.0                 # RSI 48 altındaysa (çok zayıf momentum) — no
    rsi_entry_max: float = 70.0                 # RSI 70 üstündeyse (aşırı alım riski) — no (entry için güvenli değil)
    exit_on_bear_regime: bool = True            # regime bear ise -> flat (v1 long-only; reverse short yok)
    exit_on_high_vol: bool = True               # HV → flat (ADN-STR-07: ya flat ya da 0.30 strength ile; default TRUE → flat)
    on_sideways: str = "flat"                   # sideways rejiminde "flat" (düşük hareket — trend yok)
    on_transition_uncertain: str = "flat"       # TU → flat
    # 3 EMA onay bileşeni ağırlıkları: price_vs_ema14 (0.45) / ema14_vs_ema28 (0.35) / RSI band (0.20)
    # -> elde edilen raw eligibility [0,1] → regime eligibility maskesi ile çarpılır → signal_strength
    trend_component_weights: tuple[float, float, float] = (0.45, 0.35, 0.20)
    # Signal strength: raw_trend_eligibility * regime_compat_multiplier * quality_multiplier → clamp [0,1]
    regime_compat_bull: float = 1.00
    regime_compat_bear: float = 0.00            # bear → flat (no reverse, v1)
    regime_compat_sideways: float = 0.00        # sideways → flat
    regime_compat_high_vol: float = 0.00        # HV → flat
    regime_compat_low_vol: float = 0.85         # low_vol + yukarı trend → long (daha az volatile giriş)
    regime_compat_transition: float = 0.00      # TU → flat
    # Confidence: signal_strength * (0.70 + 0.30 * regime.confidence_clamped * 0.90) — regime.confidence yüksek → strateji confidence yüksek
    confidence_base_from_regime_weight: float = 0.30
    # Supporting evidence: 4–5 feature (price, ema14, ema28, rsi14, [vwap20 eğer feature'da varsa])
    # Supporting regime evidence: her rejim için 0..1 weight (yukarıdaki 6 compat değeri — signal production zamanında doldur)

@dataclass(frozen=True)
class MomentumStrategyOptions(StrategyOptions):
    # Momentum Özel Eşikler
    # Momentum = |mom_10_abs| * 0.55 + mom_10_pct_abs_scaled * 0.45
    # Ardından RSI bandı filtresi ve regime compat uygulanır.
    mom_entry_min_bps_abs: float = 80.0         # 80 bps = %0.80 — abs mom en az
    mom_entry_pct_min_scaled: float = 0.40      # 0.40 (min scaled from 0..1)
    mom_exit_max_bps_abs: float = 20.0          # mom 20 bps altına düşünce -> flat
    rsi_overbought_max: float = 74.0            # RSI 74 üstüyse aşırı alım — düzeltme riski → flat
    rsi_oversold_min: float = 32.0              # RSI 32 altındaysa (aşırı satımdan henüz yukarı dönmedi) — flat
    on_sideways: str = "flat"                   # momentum sideways'ta anlamsız → flat
    on_transition_uncertain: str = "flat"       # TU → flat
    exit_on_bear_regime: bool = True            # bear → flat
    exit_on_high_vol: bool = False              # HV' de momentumlu yükseliş olabilir (ADN-STR-08). Default: FALSE → yine de aşağıdaki 0.40 multiplier;
    # momentum component: abs_mom (0.55) + scaled_pct_mom (0.45) — raw mom_strength
    momentum_component_weights: tuple[float, float] = (0.55, 0.45)
    # Regime compat multipliers
    regime_compat_bull: float = 1.00
    regime_compat_bear: float = 0.00
    regime_compat_sideways: float = 0.00
    regime_compat_high_vol: float = 0.40        # HV momentum: artış varsa ama riskli → 0.40 (çok güçlü değil)
    regime_compat_low_vol: float = 0.90
    regime_compat_transition: float = 0.00
    # Confidence: mom_strength * 0.75 + 0.25 * regime.confidence → clamp [0,1]
    confidence_from_regime_weight: float = 0.25
    # Supporting keys: mom_10_abs, mom_10_pct, rsi_14, volatility_20_bps, ema_14 (varsa)
    # Supporting regime evidence: 6 compat multiplier

DEFAULT_STRATEGY_OPTIONS: StrategyOptions = StrategyOptions()
DEFAULT_TREND_OPTIONS: TrendStrategyOptions = TrendStrategyOptions()
DEFAULT_MOMENTUM_OPTIONS: MomentumStrategyOptions = MomentumStrategyOptions()
STRATEGY_VERSION_DEFAULT: str = "str_01_v1"

# ----------------------- Strategy Abstract (Shared evaluate protokolü) -----------------------
class PureStrategy:
    """Protokol: bütün saf stratejiler evaluate(ctx) -> StrategySignal uygular.
    Base class olsun ya da olmasın; önemli olan aynı protokol.
    AD-9 / AD-25: pure. No mutations on ctx. No side effects. Deterministic.
    """
    strategy_id: str
    strategy_version: str

    def evaluate(self, ctx: StrategyContext, *, quality_hint: StrategyQualityHint | None = None,
                 options: TrendStrategyOptions | MomentumStrategyOptions | None = None) -> StrategySignal:
        """Deterministic, pure.
        - ctx: AD-25 StrategyContext (DEĞİŞTİRİLMEZ, sadece okunur)
        - quality_hint: Opsiyonel CAP-2 READ-ONLY. None ise hepsi False (temiz).
        - options: None ise DEFAULT_TREND_OPTIONS ya da DEFAULT_MOMENTUM_OPTIONS.
        - RAISES: Eğer options.unexpected_version_mode=="raise" ve feature_version/detector_version uyuşmazsa → ContractSchemaError.
        - Default: raise YOK, flat_hold ile graceful degrade.
        """
        raise NotImplementedError

# ----------------------- 2 Strategy Implementations -----------------------
@dataclass
class TrendFollowingStrategy(PureStrategy):
    strategy_id: str = "trend_following"
    strategy_version: str = STRATEGY_VERSION_DEFAULT
    default_options: TrendStrategyOptions = field(default_factory=lambda: DEFAULT_TREND_OPTIONS)

    def evaluate(self, ctx: StrategyContext, *, quality_hint: StrategyQualityHint | None = None,
                 options: TrendStrategyOptions | None = None) -> StrategySignal:
        """Adım adım aşağıda §4.3 Trend Strategy Rules uygulanır."""
        ...

@dataclass
class MomentumStrategy(PureStrategy):
    strategy_id: str = "momentum"
    strategy_version: str = STRATEGY_VERSION_DEFAULT
    default_options: MomentumStrategyOptions = field(default_factory=lambda: DEFAULT_MOMENTUM_OPTIONS)

    def evaluate(self, ctx: StrategyContext, *, quality_hint: StrategyQualityHint | None = None,
                 options: MomentumStrategyOptions | None = None) -> StrategySignal:
        """Adım adım §4.4 Momentum Strategy Rules uygulanır."""
        ...
```

### 4.2 Ortak Değerlendirme Akışı (HER İKİ STRATEJİ İÇİN — shared helper)

HER strategy, `evaluate` içinde AŞAĞIDAKİ 12 ADIMI sırasıyla yürütür. BU ADIMLAR stratejiye göre özelleştirilir ama sıra KORUNUR. Bu sıra determinizm garantisi içindir.

```python
def _shared_evaluate_pipeline(ctx, strategy_id, strategy_version, options, quality_hint, *,
                              compute_raw_strength_fn, compute_direction_fn, compute_supporting_keys_fn,
                              compute_regime_evidence_fn, compute_entry_ref_fn,
                              compute_expected_edge_bps_fn = None,
                              compute_stop_policy_fn = None, compute_tp_policy_fn = None) -> StrategySignal:
    # HER STRATEJİ İÇİN ZORUNLU SIRA:
    # ADIM 1. Context version + type doğrulaması (AD-22 feature_version uyum)
    # ADIM 2. Insufficient lookback kontrolü (null_count pct > threshold → flat_hold)
    # ADIM 3. Kalite etkisi (quality_hint + eligibility_ctx.reasons parsed) → penalty_multiplier
    # ADIM 4. Regime eligibility: regime_compat_multiplier + regime_regel: sideway/TU/bear varsa → direction flat, strength düşür
    # ADIM 5. Strategy özgü raw strength hesapla (compute_raw_strength_fn)
    # ADIM 6. signal_strength = raw_strength * regime_compat_multiplier * clamp [0,1]
    # ADIM 7. direction belirle (compute_direction_fn): long mu, flat/hold mu?
    # ADIM 8. confidence hesaplama: signal_strength * base + regime.confidence * weight * quality_penalty_mult → clamp [0,1]
    # ADIM 9. supporting_feature_keys + supporting_regime_evidence doldur
    # ADIM 10. entry_thesis oluştur (insan okunur açıklama — 5–8 sebep max 120 chars)
    # ADIM 11. (ops) entry_price_ref = Decimal (close_raw ya da ema_14 — S-FEA-01 içinde ema_14, close varsa bunlar)
    # ADIM 12. correlation_id ve causation_id KOPYALA: ctx.correlation_id → signal.correlation_id; ctx.causation_id? Context causation_id yoksa envelope causation_id; StrategyContext'te causation_id doğrudan field VAR MI? Eğer yoksa derive_from_envelope ile gelen causation_id'yi ctx.extra vb. araçlıkla taşıyabiliriz; YOKSA StrategyContext'te zaten "causation_id" diye public alan MEVCUT DEĞİLSE bile correlation_id'yi kullanırız, causation_id için parent context correlation ya da ctx.eligibility_ctx/caller tarafından ekstra geçirilir. (Aşağıda AÇIK KARAR ADN-STR-10.)
    # RETURN StrategySignal: bütün alanlar zorunlu doldur; direction = SignalDirection enum; short KESİNLİKLE YOK.
    raise NotImplementedError
```

> **ADIM 12 Özel Not:** Eğer `StrategyContext` public alan olarak `causation_id` field'ı S-CON-02A'da MEVCUT DEĞİLSE (bakmak gerekir), o zaman BU HİKÂYEDE **StrategyContext contract'ını DEĞİŞTİRMEDEN** iki seçenekten biri uygulanır:
>  (SEÇENEK 1 — AÇIK KARAR ADN-STR-10A): `causation_id` = `ctx.correlation_id` (aynı, çünkü bu strateji context içinde tek bir parent event zinciri).
>  (SEÇENEK 2 — AÇIK KARAR ADN-STR-10B): `causation_id` için `caller` tarafından `quality_hint` ya da `options` yanında bir ek `causation_override` parametresi geçilir; BU HİKÂYEDE options içinde BU ALAN YOKTUR, yani SEÇENEK 1 DEFAULT.
> Sonuç: BU HİKÂYEDE `signal.correlation_id == signal.causation_id == ctx.correlation_id` kabul edilir; contract bu durumu ihlal etmez (correlation/causation ikilisi StrategySignal'da ZORUNLU — ama ikisinin eşit olmasında contract kuralı YOK). Gelecekte caller tarafından strateji ayrı causation_id üretmek istenirse ADN-STR-10 güncellenir ve yeni hikâyede `options.causation_id_override` eklenir. BU HİKÂYEDE contract DEĞİŞTİRİLMEDİĞİ için bu çözüm yeterlidir.

### 4.3 Strateji 1 — Trend Following Rules (ZORUNLU SPEC)

| Adım | Bileşen | Formül / Davranış | Eşik / Not (TrendStrategyOptions defaults) |
|---|---|---|---|
| 1 | **Trend eligibility = 3 bileşen** | `raw_trend = (w1*f_price) + (w2*f_ema14v28) + (w3*f_rsi14)` — weights = (0.45, 0.35, 0.20); her f_* fonksiyonu → [0,1] aralığına normalize | `trend_component_weights` varsayılan (0.45,0.35,0.20); test fixture override edilir. |
| 2 | **Bileşen 1: price vs ema_14 gap** | `if ema_14 is None or close_raw is None or ema_14 == 0: f_price=0.0;` `gap_bps = (close_raw - ema_14) / ema_14 * 10000.0`; `if gap_bps >= opt.price_vs_ema14_min_gap_bps: f_price = min(1.0, (gap_bps / (opt.price_vs_ema14_min_gap_bps*2.5)))`; `else: f_price=0.0` | Default min 30 bps; 75 bps'ta f_price=1.0 |
| 3 | **Bileşen 2: ema_14 vs ema_28 onayı** | `if ema_28 is None or ema_28 == 0 or ema_14 is None: f_ema14v28=0.0`; `gap = (ema_14 - ema_28) / ema_28 * 10000.0`; `if gap >= opt.ema14_vs_ema28_min_gap_bps: f_ema14v28 = min(1.0, (gap / (opt.ema14_vs_ema28_min_gap_bps*3.0)))`; `else: 0.0` | Default 10 bps min; 30 bps'ta 1.0 |
| 4 | **Bileşen 3: RSI bandı (neutral-üst ama overbought DEĞİL)** | `if rsi_14 is None: f_rsi14=0.0`; `if opt.rsi_entry_min <= rsi_14 <= opt.rsi_entry_max: f_rsi14 = (rsi_14 - opt.rsi_entry_min) / (opt.rsi_entry_max - opt.rsi_entry_min)`; `else: f_rsi14=0.0` | Default 48..70 bandı (aşırı alım yok, düşüşten dönüş var) |
| 5 | **raw_strength = clamp(raw_trend, 0, 1)** | 3 bileşen ağırlıklı toplam | — |
| 6 | **Regime eligibility (6 rejim x regime_compat)** | `regime_mult = opt.regime_compat_{regime}` (6 çarpan). Bear = 0 (flat), sideways/TU/HV=0, LV=0.85, Bull=1.0 | Bear reverse YOK (v1 long-only) |
| 7 | **Insufficient lookback (null_count)** | `null_count_pct = fv.null_count / 9_nullable_features`; eğer >= opt.null_count_pct_insufficient_lookback (default 0.500) → **direction=flat/hold, signal_strength=clamp(raw*0.20,0,1), confidence=opt.confidence_on_insufficient * quality_penalty_mult** | 9 nullable feature (S-FEA-01 12-key'den RSI, EMA14, EMA28, mom10_abs, mom10_pct, vol20bps, skew, kurtosis, vwap20? — S-FEA-01 12-key listesinde: `close_raw, volume_raw, rsi_14, ema_14, ema_28, mom_10_abs, mom_10_pct, volatility_20_bps, skew_20, kurtosis_20, vwap_20, spread_bps_20` → nullable olanları (9 tane): RSI, EMA14, EMA28, mom10_abs, mom10_pct, vol20bps, skew, kurt, vwap20 = 9; spread ve close/hacim ZORUNLU) |
| 8 | **Kalite penalty:** `q_mult` = 0.15 if invalid/quarantine; 0.60 if stale/degraded; 0.85 dup/missing/ooo; 0.80 abnormal_spread. (Birden fazla bayrak varsa → MINIMUM'u kullan = EN KÖTÜ) | Invalid/quarantined ayrıca FORCE direction=flat (long'a izin VERME) |
| 9 | **signal_strength = clamp(raw_strength * regime_mult * q_mult, 0, 1)** | — |
| 10 | **direction** | Eğer (a) insufficient_lookback → `SignalDirection.FLAT`; (b) invalid/quarantine quality → `SignalDirection.FLAT`; (c) regime_mult == 0 → `SignalDirection.HOLD` (rejimsizlik flat'le aynı ama kod HOLD); (d) signal_strength >= 0.55 min → `SignalDirection.LONG`; (e) else → `SignalDirection.HOLD` | Long için minimum signal_strength default 0.55 (ADN-STR-04 default; fixture override) |
| 11 | **Confidence = clamp( 0.70 * signal_strength + 0.30 * ctx.regime.confidence * opt.confidence_base_from_regime_weight/0.30 , 0, 1 ) * q_mult_final** | Basitleştirilmiş: signal_strength weight %70, regime.confidence weight %30 | clamp [0,1] — her zaman |
| 12 | **Supporting keys = ["close_raw","ema_14","ema_28","rsi_14", ("vwap_20" if fv.features["vwap_20"] is not None else ""), "volatility_20_bps"]** → boş stringleri filtrele | — |
| 13 | **Supporting regime evidence:** dict 6-key: her rejim için opt.regime_compat_* değerleri * signal_strength | — |
| 14 | **entry_thesis** = `"Trend[ema14up{},ema28up{},rsi{}] reg={} conf={:.0%}" | EMA onayı + regime + confidence cümle | Max 120 chars |
| 15 | **entry_price_ref (ops):** Decimal(close_raw) eğer close_raw Decimal değilse `Decimal(str(close_raw))` — yoksa None | Parasal → Decimal; float YOK |
| 16 | **StopPolicy / TakeProfitPolicy** → BU HİKÂYEDE STRATEJİ TARAFINDAN ÜRETİLMEZ (Risk Engine bunları üretir; OOS) → `stop_policy=None, take_profit_policy=None` | — |
| 17 | **expected_edge_bps (opsiyonel):** Bu hikâyede strateji bunu üretMEZ (opportunity scorer OOS) → `None` | — |
| 18 | **correlation / causation:** `signal.correlation_id = ctx.correlation_id`; `signal.causation_id = ctx.correlation_id` (ADN-STR-10 default; eğer context causation varsa onu kullan; contract'ı bozmamak için) | — |
| 19 | **to_sorted_dict / sha-256:** StrategySignal zaten mevcut; implement S-CON-02A ile aynen — DEĞİŞTİRME | — |

### 4.4 Strateji 2 — Momentum Strategy Rules (ZORUNLU SPEC)

| Adım | Bileşen | Formül / Davranış | Eşik / Not (MomentumStrategyOptions defaults) |
|---|---|---|---|
| 1 | **Momentum eligibility 2 bileşen:** abs + scaled_pct | `raw_mom = (0.55 * f_abs) + (0.45 * f_pct_scaled)` — weights = (0.55, 0.45) | Default weights; test override |
| 2 | **Bileşen 1: mom_10_abs scaled to [0,1]** | `if mom_10_abs is None: f_abs = 0.0; abs_bps = abs(mom_10_abs)`; `if abs_bps >= opt.mom_entry_min_bps_abs: f_abs = min(1.0, (abs_bps / (opt.mom_entry_min_bps_abs * 2.5)))`; `else: f_abs = 0.0` | Default 80 bps min; 200 bps'ta f_abs = 1.0 |
| 3 | **Bileşen 2: mom_10_pct scaled (yön pozitif mi?)** | `if mom_10_pct is None: f_pct = 0.0`; `pct_float = float(mom_10_pct)`; `if pct_float <= 0: f_pct = 0.0` (sadece POZİTİF momentum → long; bear reverse YOK); `scaled = min(1.0, pct_float / 0.020)`; yani %2.0 mom 10 gün → 1.0; `f_pct = scaled * (1.0 if pct_float > 0 else 0.0)` | Sadece pozitif momentum (long-only). Default 200 bps pct → 1.0 |
| 4 | **RSI Filter:** `if rsi_14 is not None and (rsi_14 > rsi_overbought_max or rsi_14 < rsi_oversold_min): raw_mom *= 0.0` → flat | Aşırı alım (74+) ya da aşırı satım (32-)? DÜZELTME BEKLE → flat |
| 5 | **raw_strength = clamp(raw_mom, 0, 1)** | — |
| 6 | **Regime eligibility (6 çarpan):** bear 0, sideways 0, TU 0, Bull 1.0, LV 0.90, HV 0.40 (momentum yüksek vol'de de çalışır ama riskli — 0.40) | exit_on_bear → 0.0 |
| 7 | **Insufficient lookback:** Trend kuralı İLE AYNI (shared helper) — null_pct ≥ 0.50 → flat + düşük confidence | — |
| 8 | **Kalite penalty:** Trend kuralı İLE AYNI (shared helper). Invalid/quarantine → direction flat FORCE | — |
| 9 | **signal_strength = clamp(raw_strength * regime_mult * q_mult, 0, 1)** | — |
| 10 | **direction:** (a) insufficient_lookback → flat; (b) invalid/quarantine → flat; (c) regime_mult 0 → HOLD; (d) signal_strength ≥ 0.50 min → LONG; (e) else → HOLD | default 0.50 long eşiği (fixture override ADN-STR-06) |
| 11 | **Confidence = clamp( 0.75 * signal_strength + 0.25 * ctx.regime.confidence * (opt.confidence_from_regime_weight/0.25), 0, 1 ) * q_mult_final** | signal %75, regime %25 | clamp [0,1] — HER ZAMAN |
| 12 | **Supporting keys = ["mom_10_abs","mom_10_pct","rsi_14","volatility_20_bps","close_raw"]** | — |
| 13 | **Supporting regime evidence:** 6-key regime_compat_* * signal_strength | — |
| 14 | **entry_thesis** = `"Mom[abs{},pct{},rsi{}] reg={} conf={:.0%}"` | Max 120 chars |
| 15 | **entry_price_ref:** Decimal(close_raw) ya da None | — |
| 16 | **Stop/TP Policy:** None (OOS, risk engine yapar) | — |
| 17 | **expected_edge_bps:** None (OOS) | — |
| 18 | **correlation / causation:** Trend ile aynı → ctx.correlation_id her ikisi için (ADN-STR-10 default) | — |
| 19 | **sideways / transition davranışı:** on_sideways = "flat", on_transition_uncertain = "flat" (ADN-STR-07/08; HV de allow 0.40 multiplier) | Sideways momentum yok |

### 4.5 Regime Eligibility Matrix (2 Strateji × 6 Rejim)

| Rejim (AD-8) | Trend Following (compat) | Momentum (compat) | Not |
|---|---|---|---|
| **bull** | **1.00** (eligible) | **1.00** (eligible) | Her ikisi için de ana çalışma rejimi |
| **bear** | **0.00** (→ flat) | **0.00** (→ flat) | v1 long-only: reverse short YOK |
| **sideways** | **0.00** (→ flat) | **0.00** (→ flat) | Trend yok / momentum yok |
| **high_volatility** | **0.00** (→ flat, exit_on_high_vol=True) | **0.40** (kısmen eligible, düşük strength) | Trend'de volatil giriş YOK; momentumlu kırılım olabilir ama riskli |
| **low_volatility** | **0.85** (eligible, düşük riskli giriş) | **0.90** (eligible, düşük riskli momentum) | Her iki strateji için de uygun |
| **transition_uncertain** | **0.00** (→ flat) | **0.00** (→ flat) | Bekleme — net sinyal yok |

---

## 5. Acceptance Criteria — 72/72 (HEPSİ Test Edilebilir, Fixture Defaults ile Test Edilir — Üretim Kararı Ayrı ADN'de)

### Grup 1: Backward Compatibility + Contract Preserve (10 AC)
| # | AC | Kriter |
|---|---|---|
| C-01 | **S-RDH-01 68/68 PASS (düzenlemesiz)** | Mevcut 68 test — hiçbir S-RDH-01 dosyası değiştirilmeden. |
| C-02 | **S-RDH-02 64/64 PASS** | Aynen. |
| C-03 | **S-PLN-01 42/42 PASS** | Aynen. |
| C-04 | **S-CON-02A 104/104, S-CON-02B 71/71, S-CON-02C 93/93 PASS (268/268 contract)** | Contracts 3 hikâye regression BOZULMADAN. |
| C-05 | **S-FEA-01 120/120, S-REG-01 302/302 PASS (422/422)** | Son 2 hikâye regression — değişiklik YOK. |
| C-06 | **TOPLAM 864/864 regression PASS** (C-01..05 toplam 68+64+42+268+422 = 864) | 864 bozulmadan; 0 FAIL / 0 ERROR. |
| C-07 | **StrategySignal contract public API DEĞİŞMEDİ** | `from app.contracts.strategy import StrategySignal, SignalDirection, StrategyContext, PortfolioContextView, EligibilityContextView, OpportunityScoreComponentPolicy, StopPolicySpec, TakeProfitPolicySpec` — hepsi import edilir. Mevcut field sayısı/ismi AYNI. |
| C-08 | **`SignalDirection.short` YOK** (v1 hard boundary) | `hasattr(SignalDirection, "short") == False`; `SignalDirection("short")` → ValueError. |
| C-09 | **`CONTRACT_VERSION == "1.0.0"` HALEN** | `from app.contracts import CONTRACT_VERSION` — assert string `== "1.0.0"`. |
| C-10 | **`pyproject.toml dependencies = []` DEĞİŞMEDİ** | `toml` ya da text grep → satır `"dependencies = []"` mevcut; runtime deps 0. |

### Grup 2: Ortak Strategy Contract (12 AC)
| # | AC | Kriter |
|---|---|---|
| C-11 | **TrendFollowingStrategy.evaluate(ctx) → StrategySignal** (tüm required alanlar: strategy_id, strategy_version, direction, signal_strength, supporting_feature_keys, supporting_regime_evidence, correlation_id, causation_id) — None zorunlu alanlar VAR. |
| C-12 | **MomentumStrategy.evaluate(ctx) → StrategySignal** — Aynı zorunlu alanlar. |
| C-13 | **`SignalDirection.LONG / FLAT / HOLD` — başka enum yok** | 3 değer tam. |
| C-14 | **Direction = "short" → ValueError (enum validation)** | Strategy kodunda elle direction="short" atamaya çalışırsak → SignalDirection raise. |
| C-15 | **signal_strength ∈ [0.0, 1.0]** — 2 strateji × 10 varyant → clamp doğrulandı. |
| C-16 | **confidence ∈ [0.0, 1.0]** (eğer üretilirse; None olabilir ama bu hikâyede HER strategy confidence DOLDURUR = float [0,1]) |
| C-17 | **supporting_feature_keys** her key ∈ S-FEA-01 12-key REGISTRY allowed_keys (REGISTRY'de yoksa yine de sözleşme bozulmaz, ama test ASSERT eder) |
| C-18 | **supporting_regime_evidence.keys() ⊆ REGIME_KEYS (6 rejim)** | 7. key YOK (AD-8). |
| C-19 | **correlation_id AYNI** (ctx.correlation_id == signal.correlation_id) | 10 run'da sabit. |
| C-20 | **causation_id** ya ctx.correlation_id (ADN-STR-10A default) ya da override; contract zorlaması olmadığı için test ADN default'ı assert eder. |
| C-21 | **Wrong feature_version ("fv_unknown") + unexpected_version_mode="flat_hold"** → direction FLAT, signal_strength ≤ 0.20, confidence ≤ 0.20, reasons içinde unsupported_version. |
| C-22 | **Wrong feature_version + unexpected_version_mode="raise"** → `ContractSchemaError` raise (yalnızca bu modda; default flat_hold). |

### Grup 3: Trend Following — Happy Path + EMA Onayı (14 AC)
| # | AC | Kriter |
|---|---|---|
| C-23 | **Strong Bull Fixture:** regime=bull, close>ema14 200bps, ema14>ema28 50bps, RSI=58 → direction=LONG, signal_strength ≥ 0.75. |
| C-24 | **Bull no RSI:** regime=bull, EMA kırılımı ama RSI=40 (48 altında) → direction=HOLD (raw_strength düşük). |
| C-25 | **Bull RSI 72:** (70 üstünde) → RSI filtresi → HOLD. |
| C-26 | **Bear reverse denemesi:** regime=bear, EMA down kırılımı → direction=FLAT (no short — v1 long-only). |
| C-27 | **LV + EMA up:** regime=low_volatility, EMA onaylı → direction=LONG, signal_strength ≥ 0.60. |
| C-28 | **HV + EMA up:** regime=high_volatility → direction=HOLD (default exit_on_high_vol=True → regime_mult=0). |
| C-29 | **Eşik altında price gap:** 20 bps (<30) → f_price=0, trend düşük → HOLD. |
| C-30 | **Eşik altında EMA14 vs EMA28:** 5 bps (<10) → f_ema=0 → trend düşük. |
| C-31 | **EMA onayı 3 bileşen 2si yeterli 1 yetersiz:** (price 0.9, ema 0.8, rsi 0) → raw = 0.45*0.9+0.35*0.8+0.20*0= 0.405+0.28=0.685; signal_strength 0.685 * 1.0 * 1.0 = 0.685 → LONG ≥ 0.55 eşiği. |
| C-32 | **Fixture threshold override:** EMA14vs28 10 bps default yerine fixture 1 bps atıyor → önceki HOLD durum artık LONG (test proves defaults vs fixture ayrı). |
| C-33 | **entry_thesis non-empty, ≤120 chars** |
| C-34 | **entry_price_ref Decimal instance** (eğer close varsa) ya da None; float olmamalı |
| C-35 | **stop_policy=None, take_profit_policy=None** (bu hikâyede strategy bunları üretmez — OOS) |
| C-36 | **expected_edge_bps=None** (OOS — opportunity scorer yapar) |

### Grup 4: Trend — Regime Eligibility + Insufficient + Kalite (10 AC)
| # | AC | Kriter |
|---|---|---|
| C-37 | **Sideways regime → direction=HOLD / FLAT, strength ≤ 0.20** |
| C-38 | **Transition_uncertain → direction=FLAT / HOLD** |
| C-39 | **Insufficient lookback null_pct 0.60 (>0.50 default) → direction=FLAT, confidence = 0.10 * q_mult** |
| C-40 | **Quality invalid=True → direction=FLAT, confidence ≤ 0.15** |
| C-41 | **Quality quarantined=True → direction=FLAT, confidence ≤ 0.15** |
| C-42 | **Quality stale=True → direction=HOLD/LONG (long olabilir ama q_mult 0.60) → confidence 0.60 x azaltılmış** |
| C-43 | **Quality degraded=True → 0.60 x** |
| C-44 | **Quality duplicate/missing/out_of_order biri True → 0.85 x** |
| C-45 | **Quality abnormal_spread → 0.80 x** |
| C-46 | **Multi quality bayrak (stale + duplicate) → MIN = 0.60 x = EN KÖTÜ** |

### Grup 5: Momentum — Happy Path + Thresholds (12 AC)
| # | AC | Kriter |
|---|---|---|
| C-47 | **Bull + strong mom:** abs=250 bps (>80), pct=1.5% (>0), RSI=60 → direction=LONG, signal_strength ≥ 0.70. |
| C-48 | **Low mom (abs 30 bps <80) → HOLD** |
| C-49 | **Mom negative (pct -1.0% → düşüş) → direction=HOLD/FLAT (only pozitif momentum → long)** |
| C-50 | **Mom positive ama RSI 76 (>74 overbought) → RSI filtresi → HOLD/FLAT** |
| C-51 | **RSI 30 (<32 oversold) → HOLD** |
| C-52 | **LV + strong mom:** direction=LONG, strength ≥ 0.75 |
| C-53 | **HV + mom:** regime_mult 0.40 → strength 0.40 * 1.0 raw = 0.40 < 0.50 long eşiği → HOLD (fixture HV 0.40 default) |
| C-54 | **HV + very strong mom (raw 1.0 × 0.40 = 0.40) HOLD** ama fixture long eşiği 0.35 yapılırsa → LONG olur (test proves defaults vs fixture ayrımı) |
| C-55 | **Fixture override: mom_entry_min_bps_abs = 20 (daha düşük) → önceki HOLD artık LONG → test proves defaults/production karar ayrımı** |
| C-56 | **RSI overbought eşiğini 80 yap (daha gevşek) → RSI=76 artık allow → LONG olur** |
| C-57 | **entry_thesis non-empty, ≤120 chars** |
| C-58 | **Supporting keys ∈ S-FEA-01 12-key (test REGISTRY cross-check)** |

### Grup 6: Mom — Regime Eligibility + Edge (8 AC)
| # | AC | Kriter |
|---|---|---|
| C-59 | **Sideways → FLAT** |
| C-60 | **TU → FLAT** |
| C-61 | **Bear → FLAT** (reverse YOK) |
| C-62 | **Insufficient lookback (null 0.70 pct) → FLAT + düşük confidence** |
| C-63 | **Quality invalid → direction FLAT + düşük confidence** |
| C-64 | **Fixture weights override:** 0.55/0.45 yerine 0.80/0.20 → sinyal değişebilir, determinizm korunur. |
| C-65 | **confidence ∈ [0,1]; 20 fixtures clamp testi → hepsi 0–1** |
| C-66 | **signal_strength ∈ [0,1]; 20 fixtures clamp testi → hepsi 0–1** |

### Grup 7: CAP-1 / CAP-2 / CAP-3 / Determinism / Safety (6 AC)
| # | AC | Kriter |
|---|---|---|
| C-67 | **CAP-1 AST scan:** `app/strategies/__init__.py`, `app/strategies/base.py` İÇİNDE `if run_mode ==` / `if source_type ==` dallanması 0 finding. Field olarak geçebilir ama `If` YOK. |
| C-68 | **Determinism 10x:** 2 strateji × 4 fixture (strong bull / HV / sideways / insufficient) = 8 durumda 10 kez evaluate → 10 kez aynı StrategySignal.sha256 (schema_sha256). |
| C-69 | **CAP-2 Quality validator 0 çağrı:** StrategyQualityHint frozen=True, QualityValidator import sayısı 0, validate fonksiyonu call sayısı AST scan 0. |
| C-70 | **CAP-3 forbidden imports scan (22 lib):** `app/strategies/` 2 kaynak dosyasında 0 match. |
| C-71 | **Network + Credential taraması:** `app/strategies/` içinde 0 forbidden pattern; credential substrings (API_KEY, SECRET, binance vs.) 0 match. |
| C-72 | **Integration zincir testi (DoD-15 benzeri):** FeatureVector → MarketRegime → StrategyContext → TrendSignal + MomSignal. 2 sinyal correlation_id AYNI. 2 sinyal direction ∈ {long/flat/hold}. Bus publish 4 olay. |

---

## 6. Definition of Done — 14/14 (Hepsi Ölçülebilir)

| # | DoD Kriteri | Test / Doğrulama |
|---|-------------|-----------------|
| DoD-01 | **72/72 AC HEPSİ testlerle doğrulandı → PASS.** | pytest strategy marker + 12 test dosyası. |
| DoD-02 | **Backward compat: 864/864 regression PASS** (S-RDH-01 68, RDH-02 64, PLN-01 42, CON-02A 104, 02B 71, 02C 93, FEA-01 120, REG-01 302 = 864). | Full suite. |
| DoD-03 | **Toplam test ≥ 1104 PASS** (864 + 240 yeni). PASS oranı ≥ 99.5% (tek fail yok). | Test collect + run. |
| DoD-04 | **Stdlib-only.** `pyproject.toml dependencies=[]` HALEN. 0 yeni PyPI install. | pyproject diff. |
| DoD-05 | **`CONTRACT_VERSION HALEN "1.0.0"`** (contract bump YOK). Contracts klasöründe 0 değişiklik (git diff `app/contracts/` boş olmalı). | `from app.contracts import CONTRACT_VERSION` assert + `git diff --stat app/contracts/` → 0 lines changed. |
| DoD-06 | **`SignalDirection.short` YOK.** 3 enum değeri tam. Strategy kodunda short üretmek denendi → ValueError. | unit test 2 varyant. |
| DoD-07 | **CAP-1:** 0 if run_mode / 0 if source_type in strategies sources. AST + grep 0 finding. | AST scan test (C-67). |
| DoD-08 | **CAP-2:** StrategyQualityHint frozen=True; validator 0 çağrı; quality mutation 0 (yeni field ataması). | unit + AST. |
| DoD-09 | **CAP-3:** 22 forbidden lib 0 match in strategies sources. | grep / ast. |
| DoD-10 | **AD-9 Purity:** 2 strategy evaluate 0 side-effects (ctx mutate denemesi → StrategyContext DEĞİŞMEDİ; test asserts). | unit. |
| DoD-11 | **Determinism 10× 8 cases (2 strats × 4 fixtures):** 80 evaluate = 8 unique sha-256 (her durumda 10 kez eşit). | unit test loop. |
| DoD-12 | **Insufficient lookback + sideways/TU davranışı:** 2 strategy × 3 cases = 6 test → flat/hold + düşük confidence. | unit. |
| DoD-13 | **Fixture defaults vs. production decision ayrımı:** 2 strategy'de 3 eşik default vs fixture override 2 senaryo = 6 test → sonuç farkı; ama production default DEĞİŞMEDİ (sabit default_options frozen olduğu için FROZEN mutate DENEMESİ → FrozenInstanceError testi PASS). | Frozen / options testi. |
| DoD-14 | **Integration chain testi 2 varyant (bull + sideways):** S-FEA-01 → S-REG-01 → S-STR-01. Correlation_id AYNI; causation ardışık; 2 StrategySignal produce; no order no risk no oppscore. | test_sstr01_integration_chain.py (2 test). |

---

## 7. Test Planı — Detaylı (Toplam Tahmini ≥ 300 yeni test, 12 dosya)

### 7.1 Test Konumları (YENİ DOSYALAR)
```
tests/strategies/
  test_sstr01_trend_happy.py              # C-23..C-36 (14) + 6 ek varyant = 20+
  test_sstr01_trend_regime_eligibility.py # C-37..C-46 (10) + 14 parametrize = 24+
  test_sstr01_trend_ema_confirm.py        # C-29..C-32 + 22 = 26+
  test_sstr01_momentum_happy.py           # C-47..C-58 (12 varyant) = 22+
  test_sstr01_momentum_thresholds.py      # C-53..C-56 + C-64 + weights = 24+
  test_sstr01_edge_cases.py               # C-21/22, C-39, C-59..62 + 22 = 30+
  test_sstr01_signal_output.py            # C-13..18 + 18 = 24+
  test_sstr01_quality_cap2.py             # C-40..C-46 + C-63 + 21 kalite varyant = 28+
  test_sstr01_determinism_cap1.py         # C-67/68 + 10x 8 cases + run_mode/source_type branch + leakage = 32+
  test_sstr01_safety_regression.py        # C-01..C-10 + C-70/71 + import subset 24 + contract sha unchanged = 34+
  test_sstr01_correlation_causation.py    # C-19/20 + 16 = 18+
  test_sstr01_integration_chain.py        # C-72 + DoD-14 (2 varyant) = 20+
```
**TOPLAM:** 20+24+26+22+24+30+24+28+32+34+18+20 = **302** (≥300, hedef 240 → ✅ aşıldı).

### 7.2 Her Grup AC × Test Cross-Mapping
| Grup | AC | Test |
|---|---|---|
| G1 Regression (C-01..10) | 10 AC | test_sstr01_safety_regression.py |
| G2 Strategy Contract (11..22) | 12 AC | test_sstr01_signal_output.py + edge_cases |
| G3 Trend Happy/EMA (23..36) | 14 AC | trend_happy + trend_ema |
| G4 Trend Q+Regime (37..46) | 10 AC | trend_regime_eligibility + quality |
| G5 Mom Happy/Th (47..58) | 12 AC | mom_happy + mom_thresholds |
| G6 Mom Regime/Edge (59..66) | 8 AC | edge_cases + mom_thresholds |
| G7 CAP1/2/3 + Det + Safety (67..72) | 6 AC | determinism_cap1 + quality + safety + integration |
| **TOTAL 72 AC** | 72/72 ✅ | 12 test dosyası |

---

## 8. Mimari Sözleşmelere Uyum Tablosu
| Kural | Bu hikâyedeki uygulaması |
|---|---|
| AD-3 Canonical Envelope | StrategyContext derive_from_envelope ile envelope metadata taşır; correlation/caus korunur. |
| AD-4 / CAP-1 Live/Replay Parity | `app/strategies/` içinde 0 forbidden branch; run_mode/source_type SADECE field (meta), if kontrol YOK. |
| AD-5 / CAP-2 Quality Bayrakları | StrategyQualityHint frozen=True; 0 validator çağrı; okuma-only; kalite → direction flat ya da confidence düşürme. |
| AD-6 MVP Internal Bus First | Bus S-PLN-01'de mevcut; integration test ile 4 olay publish edilir. |
| AD-7 Single Writer | Strategy SADECE StrategySignal üretir; başka contract YAZMAZ; options frozen=True → kalıcı mutate YOK. |
| AD-8 Regime 6 Enum | 2 strategy × 6 eligibility — bear reverse YOK, flat. |
| AD-9 Strategy Purity | Pure evaluate, 0 side-effect; ctx mutate DENEME test; forbidden imports 0; 10x determinizm. |
| AD-17 Corr/Caus | correlation_id = parent; causation_id = parent (ADN-STR-10 default). Zincir korunur. |
| AD-20 Determinism | 10× 8 case 80 evaluate → 8 unique digest. |
| AD-22 FeatureVector Versioned | Yanlış feature_version → flat/hold (veya raise options.raise). |
| AD-25 StrategyContext Typed | Sadece ctx input; başka okuma YOK. |
| CAP-3 Strategy Isolation | Forbidden import 22 lib 0 match. |
| v1 Hard Safety | Short YOK; lev YOK; order/execution YOK; network/credential YOK. |

---

## 9. Open Decisions — ADN-STR-01..12 (Hepsi AÇIK KALDI, Üretim Kararı Burada ALINMADI — Fixture Defaults vs Production Decisions KARIŞTIRILMADI)

| ADN No | Açık Konu | Bu hikâyedeki DEFAULT (fixture override edilebilir) | Neden Açık? |
|---|---|---|---|
| **ADN-STR-01** | Trend long min signal_strength threshold (0.55 mi 0.50 mi?) | Default 0.55; fixture override test kanıtladı | Production takas toplantısı sonrası kalıcı |
| **ADN-STR-02** | Wrong feature_version modu: "flat_hold" (graceful) vs "raise" (fail-fast)? | Default "flat_hold"; varyant 2 testte raise modu test | MVP paper production'da graceful mi fail-fast mi? |
| **ADN-STR-03** | Insufficient lookback null_pct (%50 mi %35 mi?) | Default 0.50 (50%); fixture 0.35 override test | S-FEA-01 12 key null toleransı production data belirlenecek |
| **ADN-STR-04** | Trend 3 bileşen ağırlıkları (0.45/0.35/0.20 mi?) | Default (0.45,0.35,0.20); fixture (0.60,0.20,0.20) override test | Backtest ile optimize |
| **ADN-STR-05** | Trend EMA onayı minimum gap (30/10 bps mi 50/20 bps mi?) | Default 30/10; fixture 50/20 test | Takas pair'e göre değişir (BTC/ETH vs altcoin) |
| **ADN-STR-06** | Mom long min strength (0.50 mi 0.45 mi?) | Default 0.50; fixture 0.35 test | Volatiliteye göre ayarlanır |
| **ADN-STR-07** | Trend'de high_volatility davranışı (flat mi 0.30 mult mi?) | Default flat (exit_on_high_vol=True); fixture 0.30 mult override test | Regime evidence yüksek vol breakout varyant |
| **ADN-STR-08** | Momentum'da high_volatility (0.40 mult mi 0.60 mı? flat mi?) | Default 0.40; fixture 0.60 ve flat varyant test | Momentum breakout volatilite |
| **ADN-STR-09** | Quality penalty kalıcı değerler (0.15 / 0.60 / 0.85 / 0.80) | Default dizi; fixture 0.30 / 0.80 / 0.95 / 0.90 override test | Operasyonel tolerans |
| **ADN-STR-10** | StrategySignal.causation_id ataması (ctx.correlation_id mi? caller override mı? envelope.causation_id mi?) | Default ctx.correlation_id (ADN-STR-10A); varyant 10B: options.causation_id_override alanı gelecek | StrategyContext public API'nin causation field olup olmadığına bakılacak; contract bozmamak için şimdilik corr=caus |
| **ADN-STR-11** | Expected_edge_bps ve StopPolicy/TPPolicy strategy tarafında üretim var mı? | DEFAULT None; fixture override None → None (üretim YOK); future S-RSK / S-OPP üretir. | Risk Engine ve Opportunity sorumluluk alanı |
| **ADN-STR-12** | Production kalıcı strategy_version (str_01_v1 mi 1.0.0 mu?) | Default "str_01_v1"; fixture override "1.0.0" test ile ayrım kanıtlandı | Sürüm politikası (fea_01_v1 / reg_01_v1 ile tutarlılık) |

> **ÖZEL Uyarı — Açık Kararların SABİTLİK KURALI:** Bu hikâyede implementation (dev-story) aşamasında **bu ADN default'lar KALICI OLARAK DEĞİŞTİRİLMEZ**. Sadece test fixture'ları override eder (yalnızca test süresi için). Production kararı ayrı ADN toplantısında alındığında yeni bir hikâye (örn S-STR-01B — calibrate defaults) ile frozen options default kalıcı güncellenir. Bu hikâye "defaults + fixture override testi" şeklinde kapanır.

---

## 10. Implementation Readiness (Ön Hazırlık Kontrolü — TAMAMLANDI)

| Kontrol | Durum |
|---|---|
| ✅ 864/864 regression onayı (baseline) | PASS (önceki doğrulama) |
| ✅ 4 mevcut contract import edilebilir ve test çalışır | PASS |
| ✅ 72/72 AC yazıldı, test edilebilir | 72 ✅ |
| ✅ 14/14 DoD yazıldı, ölçülebilir | 14 ✅ |
| ✅ Test planı ≥ 300 yeni test (12 dosya) | 302 ✅ (hedef 240 → aşıldı) |
| ✅ 2 strategy algoritması, 12 adım deterministik sıra | TANIMLI |
| ✅ Regime eligibility matrix 2×6 = 12 kural | TANIMLI |
| ✅ Open decisions 12 adet açık kaldı (production kararları burada alınmadı) | 12 AÇIK ✅ |
| ✅ Fixture defaults vs production karıştırma önlemi: options frozen=True + fixture override testleri 6+ varyant | PLANLI |
| ✅ 22 forbidden lib YOK, runtime deps 0 | 0 ✅ |
| ✅ Contracts klasöründe 0 değişiklik taahhüdü | TAÇHUTLADI ✅ |
| ✅ Short / leverage / execution / OOS listesi net | TANIMLI ✅ |
| ✅ CAP-1/CAP-2/CAP-3 / Determinism / Corr-Caus test planları var | 4 tane ✅ |
| ✅ Integration chain test (DoD-14/15) + bus publish var | PLANLI ✅ |

### Sonuç: S-STR-01 Hikâye Spec **KOD YAZILMADAN ÖNCE** tamamen hazır. Implementation (dev-story) aşamasına **ready-for-dev**.

---

## 11. Son Kural — Implementation Sırasında Bunları YAPMA

- ❌ Mevcut `app/contracts/*.py` public import / alan / enum DOKUNMA — 0 değişiklik.
- ❌ `pyproject.toml dependencies=[]` değişiklik — 0 yeni dep.
- ❌ S-FEA-01 / S-REG-01 kaynak ya da test dosyası değiştirme — 0.
- ❌ Short enum ekleme / short üretme — YASAK.
- ❌ RiskDecision / PaperOrder / OpportunityScore üretme — OOS.
- ❌ Network / DB / FileSystem / Exchange / WS import etme — 0.
- ❌ `if run_mode == ...` / `if source_type == ...` branch EKLEME — 0.
- ❌ ADN default'ları KALICI (production gibi) değiştirme; fixture override yap, default sabit kalsın.
- ❌ Kalite validator çağırma / quality_flags mutate — 0.

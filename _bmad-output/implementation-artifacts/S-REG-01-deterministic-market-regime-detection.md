---
story_id: "S-REG-01"
story_key: "S-REG-01"
title: "Deterministic Market Regime Detection (6-State AD-8 + Confidence + Transition Uncertain)"
epic: "E-REG — Market Regime Detector (Epic 6)"
status: "ready-for-dev"
created: "2026-08-25"
updated: "2026-08-25"
author: "bm-create-story v1"
tags: [regime, detection, 6-state, deterministic, stdlib-only, AD-8, CAP-1, CAP-2, transition_uncertain, confidence]
baseline_commit: "d955755 feat: implement deterministic feature engine foundation"
previous_story: "S-FEA-01"
next_story: "S-STR-01"
contract_version_preserved: "1.0.0"
contract_used: "MarketRegime (app/contracts/regime.py) + MarketRegimeState (6 enum) + TimeRangeSpec — TÜMÜ mevcut S-CON-02A ürünü, YENİ SÖZLEŞME OLUŞTURULMAYACAK"
test_baseline_count: 562
test_baseline_passed: 562
feature_version_expected_input: "fea_01_v1"
detector_version_story_default: "reg_01_v1"
---

# S-REG-01 — Deterministic Market Regime Detection (AD-8 6-State + Confidence + Transition Uncertain)

## 1. Amaç ve Genel Bakış

**User Story (BDD):**
> Bir Market Regime Detector tüketicisi (Strategy Engine, Risk Engine, AI Scoring, Portfolio Simulator, AD-8 downstream bağımsız modüller) olarak,
> Sadece tek bir girdi olarak `FeatureVector` (S-FEA-01 `fea_01_v1` 12-key + provenance) + quality_flags (yalnızca OKU, MUTATE ETME — CAP-2) verildiğinde,
> Deterministik olarak `MarketRegime` (mevcut S-CON-02A `app/contracts/regime.py` AD-8 6-state) + confidence + 6 ayrı skor + lookback_ts + detector_version + feature_version üretmek istiyorum,
> Öyle ki 6 rejim BULL/BEAR/SIDEWAYS/HIGH_VOLATILITY/LOW_VOLATILITY/TRANSITION_UNCERTAIN'den herhangi biri seçilsin,
> Her biri için 6 ayrı `scores: Dict[str,float] ∈ [0,1]` (toplam 1.0 olmak zorunda DEĞİL) ve `confidence ∈ [0,1]` için açıkça tanımlı olsun,
> AYNI FeatureVector → 10 TEKRAR → AYNI MarketRegime (aynı sorted dict, aynı SHA-256) (AD-20),
> Rejim detection kodu İÇİNDE `if run_mode == ...` veya `if source_type == ...` BRANCH YOK (CAP-1),
> Yetersiz lookback (null_count yüksek) / yakın skorlar (tie/near-tie) / çelişkili trend+vol sinyalleri / düşük confidence → HEP `transition_uncertain` + düşük confidence + belirli SKORLAMA,
> Kalite bayrakları (stale / invalid / quarantined / degraded) OKUNUR, geçici olarak transition veya düşük confidence olarak AKTARILIR, AMA NE KALİTE BAYRAKLARINI MUTATE EDER NE DE VALIDATOR TEKRAR ÇAĞIRIR (CAP-2),
> Mevcut `MarketRegime` SÖZLEŞMESİNİ %100 KULLAN (yeni alan EKLEME, yeni contract OLUŞTURMA — correlation_id/causation_id Alan Mevcut MarketRegime'de YOK → AÇIK KARAR ADN-REG-01 ile envelope seviyesinde kalır, bu hikâyede REJİM PUBLIK PAKETİNİN payload olarak döndüğü çıktıda bunları ayrıca yaz),
> YENİ RUNTIME DEPENDENCY 0 — stdlib-only (`pyproject.toml dependencies=[]` koru).

### Hedef
Mevcut (S-CON-02A `MarketRegime` + `MarketRegimeState` enum AD-8 6 state + `TimeRangeSpec`) KULLANARAK, **Sıfır yeni sözleşme** ile ilk gerçek Market Regime detection katmanını kur. Bu hikâye YALNIZCA `FeatureVector → MarketRegime` yönünde (tek yönlü deterministik fonksiyon). **Hiçbir şekilde strategy / risk / AI / execution çağrısı YOK (OOS).**

### Ön Koşullar (Mevcut System Under Test — BAŞLANGIÇTA DOĞRULANACAK)
✅ **562 / 562 FULL regression PASS** (S-RDH-01 68, S-RDH-02 64, S-PLN-01 42, S-CON-02A 104, S-CON-02B 71, S-CON-02C 93, S-FEA-01 120) — BU HİKÂYE SONRASI EN AZ `562 + ≥240 = 802+` test hedeflenir (562 regression BOZULMAYACAK).
✅ `app/contracts/regime.py` mevcut ve AD-8 sözleşmelerini içeriyor:
  - `MarketRegimeState` (6 enum: `bull`/`bear`/`sideways`/`high_volatility`/`low_volatility`/`transition_uncertain`)
  - `MarketRegime` dataclass (7 alan: `timeframe, regime, confidence, scores, detector_version, feature_version, lookback_ts`)
  - `TimeRangeSpec(start: Instant, end: Instant)` nested
  - `to_sorted_dict()`, `schema_sha256()` mevcut
  - Invariant: `scores` 6 key TAM, her değer `float` ∈ `[0,1]`, `confidence` ∈ `[0,1]`
✅ `app/contracts/feature.py` + `FEATURE_SCHEMA_REGISTRY['fea_01_v1']` 12-key kayıtlı (S-FEA-01 kanıtlandı)
✅ pyproject.toml `dependencies=[]` — stdlib-only
✅ CONTRACT_VERSION = `"1.0.0"` (BU HİKÂYEDE BUMP YOK — geriye dönüş)
✅ Hard Safety: short / leverage>1 / futures / network / credentials / DB / exchange çağrısı YOK (S-RDH-02 credential scan, C-FND-03 forbidden tests, devam ettirilecek)

### Değişmez Mimari Kurallar (HİÇBİR KOŞULDA İHLAL EDİLEMEZ)
| Kural | Kaynak | Davranış |
|---|---|---|
| AD-8 Regime Independent Service Boundary | ARCHITECTURE-SPINE AD-8 | Regime detection, strategy / risk / AI'dan AYRı modül; Strategy/Risk SADECE `MarketRegime` event/reference üzerinden tüketir; rejim engine'in içinde Strategy/Risk kod çağrısı YOK. |
| CAP-1 Replay/Live Parity | SPEC CAP-1 | `app/regime/` klasör kaynak kodunda `run_mode` veya `source_type` isimli `If/Attribute` dallanması 0 — AST tarayıcı 0 finding. Aynı FeatureVector → Aynı MarketRegime (determinizm). |
| CAP-2 Quality Flags Read-Only | SPEC CAP-2 | Regime engine, `quality_flags` (stale/invalid/quarantined/degraded/out_of_order/duplicate/missing) OKUR (isteğe bağlı girdi); AMA **NE MUTATE EDER, NE VALIDATOR TEKRAR ÇAĞIRIR**. Eğer bozuk veri → transition_uncertain + confidence düşür. |
| AD-20 Determinism | ARCHITECTURE-SPINE §AD-20 | Aynı FeatureVector girdisi → 10 kez → Aynı MarketRegime. `to_sorted_dict()` eşit; `schema_sha256()` eşit. |
| AD-22 FeatureVector Version Contract | ARCHITECTURE-SPINE §AD-22 | Engine YALNIZCA **`feature_version = "fea_01_v1"` → 12-key SPEC okur.** Başka feature_version → raise `ContractSchemaError` veya `transition_uncertain`? → **AÇIK KARAR ADN-REG-02** (default: raise, fixture test 2 varyant). |
| AD-5 Data Quality Gate (referans) | ARCHITECTURE-SPINE §AD-5 | 9 kalite modu: `valid, stale, invalid, quarantined, degraded, duplicate, out_of_order, missing, abnormal_spread`. Bu engine: `invalid / quarantined` → transition + confidence LOW; `stale / degraded` → confidence 25% azalt; `duplicate/missing/out_of_order` → 10% azalt (aşağıda sayısal eşik defaultlar ADN). |
| v1 Hard Safety | PRD Hard Boundaries | short / lev>1 / futures / network / credentials / ML / pandas / numpy / ta-lib / ccxt / requests / sqlalchemy YOK — AST + grep 0 finding. |
| Yeni Contract YOK (Kullanıcı KURAL) | User HARD kural | `MarketRegime` contract public API / field sayısı DEĞİŞTİRİLMEZ; `MarketRegimeState` 6 enum 7'ye çıkarılmaz — contract bump YOK. correlation_id/causation_id → AÇIK KARAR ADN-REG-01. |

---

## 2. Mimari Uyum & Bağlam Devamlılığı (S-FEA-01 Sonrası — 8. Halka)

### 8-Halka Korelasyon Zincirine Ekleme (AD-17, AD-23)
```
[CanonicalCandle → S-PLN-01 Typed EventBus]
    ↘ input_refs[] + lookback_window + S-FEA-01 FeatureEngine
        ↘ FeatureVector (S-FEA-01, AD-22, 12-key fea_01_v1)  ← OKUNDU
            ↘ MarketRegime (S-REG-01, AD-8, 6-state + confidence + 6 scores)   ← BU HİKÂYE: TEK YÖNLÜ
                ↘ StrategyContext (S-CON-02A AD-25)   ← OOS (S-STR)
                    ↘ StrategySignal → OpportunityScore → RiskDecision → PaperOrder → Fill → Portfolio
```

> **NOT:** Bu hikâyede **StrategyContext / OpportunityScore / Risk Engine** üretimi KESİNLİKLE YOK — OOS (Out-of-Scope). SADECE: `FeatureVector (+optional quality_flags read-only) → RegimeEngine.detect() → MarketRegime`.

### Kalıtsal Geliştirici Notları (S-FEA-01 / S-CON-02C Lessons Learned)
1. **ULIDISH underscore uyumlu regex:** `_ULIDISH_RE = r"^[A-Za-z0-9_\-]{8,}$"` — lookback_ts Instant'lar `Instant(str)` ISO-8601 format (market types.py mevcut)
2. **Credential tarayıcı C56 False-positive önlemi:** Hassas substrları DOĞRUDAN STRING YAZMA; `chr(ord('B')) + chr(ord('I')) + ...` ile runtime concat. `BINANCE_API_KEY`, `LEVERAGE_2X`, `SECRET` benzeri.
3. **CAP-1 AST tarama paterni:** `ast.NodeVisitor` If/test + Attribute (`expr.attr == "run_mode"` / `"source_type"` / `Name.id == "run_mode"`/`"source_type"`) — 0 finding doğrulaması
4. **Look-ahead bias tarama (benzer REGIME):** t+1 yerine burada "gelecekteki feature"; bu hikâyede YOK, çünkü input sadece tek FeatureVector (t anı snapshot). Ancak **AST taraması YAPILACAK:** `future`, `next_bar`, `forward`, `source_type == "live"` branch YOK.
5. **10x determinizm test kalıbı:** 10 kez → set(schema_sha256 for _ in range(10)) == 1 unique → PASS
6. **Zero-denominator fallback:** RSI avg_loss=0→100 gibi (S-FEA-01 C20), burada: tie threshold / normalize div-by-zero → 0.0 veya transition.
7. **`pyproject.toml dependencies=[]` + 0 Yeni Runtime Dep:** Stdlib `dataclasses`, `math`, `statistics`, `typing`, `hashlib`, `json`, `ast`, `re`, `copy` — başka import YOK. pandas/numpy/pydantic/ccxt/ta YASAK.

---

## 3. Dosya Yapısı (Kesin)

### 3.1 Yeni Dosyalar (Oluşturulacak — 9 dosya)
| # | Mutlak Yol | Kapsam | Satır Tahmini | Not |
|---|---|---|---|---|
| 1 | `app/regime/__init__.py` | Public API: `RegimeEngine`, `SREG01_DETECTOR_VERSION`, `SREG01_INPUT_FEATURE_VERSION`, `DetectOptions`, `QualityHint` (salt-okunur kalite sarıcı, NO mutate) | 20–40 | Modül init; `__all__` 3–6 isim. YENİ contract exportları YOK; `app/contracts/` dokunulmuyor. |
| 2 | `app/regime/engine.py` | Ana class: `RegimeEngine` (dataclass veya class) + nested 3 axis hesaplama + 6 skorlama + tie/transition heuristiği + confidence hesaplama + kalite davranışı + SORTED 6-key scores sözlüğü + `detect(symbol, fv: FeatureVector, quality_hint: QualityHint | None = None, correlation_id: str | None=None, causation_id: str | None=None, *, lookback_override_instant_start: Instant | None=None, lookback_override_instant_end: Instant | None=None) -> tuple[MarketRegime, dict[str, Any]]`. İkinci tuple elemanı = **AUX payload (corr/caus/meta)**. MarketRegime contract'a correlation/caus YOK, bunları ayrı dict döndür → envelope bu ikisini metadata olarak ekler. | 400–650 | stdlib-only. Import: `from app.contracts.regime import MarketRegime, MarketRegimeState, TimeRangeSpec, REGIME_KEYS`. YENİ contract importu YOK (app/contracts/regime.py tamamen AYNI KALIR). |
| 3 | `tests/regime/test_sreg01_engine_basics.py` | H1+H2: 6 enum coverage + bull / bear / sideways temel happy path + insufficient lookback + null_count high → transition | 220 | 20+ test |
| 4 | `tests/regime/test_sreg01_high_low_vol.py` | H3: high_volatility / low_volatility skoru tek başına trigger; vol axis threshold | 180 | 18+ test |
| 5 | `tests/regime/test_sreg01_transition_uncertain.py` | H4: transition_uncertain 4 trigger (tie/bull-bear yakın / çelişkili sinyal / yetersiz lookback / düşük confidence + kalite stale/invalid/quarantined/degraded) | 260 | 28+ test |
| 6 | `tests/regime/test_sreg01_scores_confidence.py` | H5: scores dict 6 key 0–1, sum normalizasyon ADN, confidence ∈[0,1], 6 skorun her biri 0–1 aralığı clamp, tie handling 5 varyant | 240 | 24+ test |
| 7 | `tests/regime/test_sreg01_quality_cap2.py` | H6: CAP-2 — QualityFlags okunur, NE mutate eder NE validator çağırır; stale/invalid/quarantined/degraded/duplicate/missing/out_of_order 7 kalite + expected davranış | 260 | 26+ test |
| 8 | `tests/regime/test_sreg01_determinism_cap1.py` | H7: CAP-1 AST run_mode/source_type 0 finding; 10x determinizm (aux dahil ayrı dict de aynı); leakage AST; NaN/None coercion to 0.0/None; feature_version hatalı → raise veya transition (ADN-REG-02 varyant 1 default) | 300 | 30+ test |
| 9 | `tests/regime/test_sreg01_safety_regression.py` | H8: credential 0, network 0, 562 regression PASS (subset import smoke 22 import), pyproject deps=[], CONTRACT_VERSION 1.0.0, `app/contracts/regime.py` unchanged sha, forbidden lib scan (22 lib) 0 finding | 280 | 28+ test |

**Toplam Yeni Test Tahmini (9 dosya):** 20+18+28+24+26+30+28 + varyant parametrize = **≥ 240 yeni test.**

### 3.2 DEĞİŞTİRİLECEK (Potansiyel 1 dosya — AMACI YALNIZCA `.gitignore` ise opsiyonel)
| # | Yol | Değişiklik (YOKSA ATLA) | Not |
|---|---|---|---|
| 10 | `.gitignore` | Opsiyonel: `_run_pytest.py` ve `_pytest_local/` untracked artık ignore edilsin mi? → KULLANICI ONAYI SONRASI YAPILACAK. BU HİKÂYEDE DEFAULT: `.gitignore` DEĞİŞTİRME — bu işlem dev-story aşamasında "opsiyonel son adım" olarak not düşülür, default ATLA. | **ATLA** varsayılan. |

### 3.3 KESİNLİKLE DEĞİŞTİRİLMEYECEK DOSYALAR — 442/562 regression KORU
- ❌ `app/contracts/*.py` — HEPSİ dokunulmuyor. `MarketRegime`, `FeatureVector`, `CONTRACT_VERSION="1.0.0"` + ilk 71 `__all__` sırası %100 KORUNUR.
- ❌ `pyproject.toml` — `dependencies=[]` DEĞİŞMEZ.
- ❌ S-RDH-01/02, S-PLN-01, S-CON-02A/B/C, S-FEA-01 kaynak/test — dokunulmaz (regression onayı).
- ❌ `app/features/` — önceki hikâye, dokunulmaz (sadece import edilir).

### 3.4 Out of Scope (Kesin — OOS)
- ❌ Trend / Momentum Strategy implementasyonu (S-STR-01/02)
- ❌ OpportunityScore, AI scoring (S-AIS-01)
- ❌ Risk Engine, Kill Switch, Limits (E-RSK)
- ❌ Backtest / Paper Trading / Fill Model / Portfolio Simulation
- ❌ Exchange / API Key / Credential / WS / DB / Redis
- ❌ AI/ML/Model training/inference
- ❌ Dashboard / API (E-API)
- ❌ Pandas / NumPy / TA-Lib / ccxt / pydantic / msgspec / cattrs — yeni runtime import YASAK
- ❌ `MarketRegime` contract 8. alan EKLEME — yeni contract OLUŞTURMA. correlation/caus ayrı `aux` dict döner (ADN-REG-01).

---

## 4. Algoritma Detayları (ZORUNLU SPEC — HİLE YOK, AÇIK KARARLAR AYRICA LİSTELENDİ)

### 4.1 Genel RegimeEngine Sözleşmesi (Public API)

**Class signature (stdlib-only):**
```python
from dataclasses import dataclass, field
from typing import Any
from app.contracts.feature import FeatureVector
from app.contracts.regime import MarketRegime, MarketRegimeState, TimeRangeSpec
from app.contracts.types import Instant

# ---------- Kalite İpucu (CAP-2 READ-ONLY WRAPPER — NO MUTATE) ----------
@dataclass(frozen=True)           # frozen = READ-ONLY enforce — doğrudan QualityFlags payload taşır ama mutate YOK
class QualityHint:
    """CAP-2 READ-ONLY wrapper around event quality flags.
    Bu sınıf NE QualityFlags'i MUTATE EDER, NE VALIDATOR TEKRAR ÇAĞIRIR.
    Her boolean bayrak: True = problemli durum (adından belli).
    Default hepsi False (yani kalite TEMİZ).
    """
    stale: bool = False
    invalid: bool = False
    quarantined: bool = False
    degraded: bool = False
    duplicate: bool = False
    out_of_order: bool = False
    missing: bool = False
    abnormal_spread: bool = False
    # Not: validator çağırmıyoruz, bu sadece caller tarafından doldurulan read-only hint.

# ---------- Detect Options (esas ADN eşiklerinin override edilebildiği nokta — production override KALICI DEĞİLDİR, TESTTE KULLANILIR) ----------
@dataclass(frozen=True)
class DetectOptions:
    # Production'da ADN-REG-03..08 aşağıdaki DEFAULTS ile çalışır; test fixture tarafından override edilir.
    trend_momentum_axis_weight: tuple[float, float, float] = (0.50, 0.30, 0.20)  # EMA+RSI(5), Mom(3), Vol(2)
    tie_threshold: float = 0.050       # Top1 - Top2 < 0.050 → near-tie → transition
    conflict_threshold: float = 0.300  # |trend_axis| vs vol_axis uyumsuzluk skoru > 0.300 → çelişki → transition
    null_count_pct_transition: float = 0.500  # null_count / 9_nullable_features ≥50% → transition
    min_confidence_before_transition: float = 0.350  # confidence < 0.350 ve üstü 3 şarttan biri → transition
    high_vol_bps_floor: float = 150.0  # volatility_20_bps ≥150 → high_vol axis +=
    low_vol_bps_ceiling: float = 25.0  # volatility_20_bps ≤25 → low_vol axis +=
    sideways_band_ema_pct: float = 0.005  # |close - ema_14| / ema_14 ≤ 0.5% → EMA flat
    sideways_rsi_band: tuple[float, float] = (43.0, 57.0)  # RSI 43–57 → neutral
    momentum_band_abs_pct: float = 0.003  # |mom_10_pct| ≤ 0.3% → momentum flat
    bull_score_weight: tuple[float, float, float] = (0.40, 0.35, 0.25)  # Trend↑, Mom↑, Vol-low
    bear_score_weight: tuple[float, float, float] = (0.40, 0.35, 0.25)  # Trend↓, Mom↓, Vol-low
    confidence_smooth_alpha: float = 0.85  # 1 - entropi tabanlı sapma + alpha (yumuşatma)
    # Kalite penalty (0.0–1.0, confidence çarpanı olarak uygulanır — 1.0 = NO PENALTY)
    quality_penalty_invalid_quarantined: float = 0.20
    quality_penalty_stale_degraded: float = 0.75
    quality_penalty_dup_missing_ooo: float = 0.90
    quality_penalty_abnormal_spread: float = 0.85

DEFAULT_OPTIONS: DetectOptions = DetectOptions()

# ---------- Ana Engine ----------
@dataclass
class RegimeEngine:
    detector_version: str = "reg_01_v1"   # SREG01_DETECTOR_VERSION sabiti
    options: DetectOptions = field(default_factory=lambda: DEFAULT_OPTIONS)

    def detect(
        self,
        symbol: str,                        # canonical symbol (örn BTC_USDT) — not: MarketRegime contract'ta symbol YOK; sadece log/aux koru
        feature_vector: FeatureVector,      # ZORUNLU — GİRDİ
        quality_hint: QualityHint | None = None,  # CAP-2 READ-ONLY — None → default hepsi False (clean)
        *,
        # lookback_ts için override (eğer caller, FeatureVector.input_refs'ten daha doğru Instant start/end biliyorsa). YOKSA: FeatureVector.input_refs[0]/[-1] → Instant'a çevrilir (ADN-REG-04).
        lookback_start_override: Instant | None = None,
        lookback_end_override: Instant | None = None,
        # AUX metadata (correlation/causation — MarketRegime contract'ında YOK, döndürülen 2. tuple elemanında aux olarak verilir, envelope ekler)
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> tuple[MarketRegime, dict[str, Any]]:
        """
        Deterministic → Aynı FeatureVector + options → AYNI (MarketRegime, aux) 10 kez.
        RETURN:
          - [0]: MarketRegime (S-CON-02A AD-8 contract — 7 alan TAM, KESİNLİKLE 8. alan EKLEME).
          - [1]: aux dict (read-only): {
              "correlation_id": input or derived,
              "causation_id": input or derived,
              "symbol": symbol,
              "feature_version_used": fv.feature_version,
              "quality_hint_applied_penalty": float,
              "raw_axes": {"trend_axis": float, "mom_axis": float, "vol_axis": float},  # -1…1 arası 3 ölçüt
              "raw_scores_before_clamp": {"bull":…6 key…},
              "tie_activated": bool,
              "conflict_activated": bool,
              "insufficient_lookback_activated": bool,
              "low_confidence_activated": bool,
              "quality_triggered_transition": bool,
            }
        RAISES:
          - ContractSchemaError (eğer feature_version beklenen değil ve ADN-REG-02 varyant 1 = raise; test 2 varyantta transition → raise ya da transition varyant 2)
          - TypeError (eğer fv FeatureVector değilse)
        İÇ ADIMLAR (ZORUNLU SIRASINI koru):
          1.  _validate_inputs(fv)   →   raise ContractSchemaError if feature_version != expected + fv not instance
          2.  Eğer ADN-REG-02 default = raise değilse → transition.
          3.  _extract_12_features(fv) → dict 12 key float or None + null_count (FeatureVector.null_count kullan, ZİRVDEN HESAPLAMA)
          4.  _compute_three_axes(feat_12, opt) → trend_axis[-1,1], mom_axis[-1,1], vol_axis[-1,1]
          5.  _compute_six_raw_scores(ax_trend, ax_mom, ax_vol, opt) → 6-key dict[str, float ∈ ℝ] (henüz 0/1 clamp yok)
          6.  _soft_clamp_scores_to_0_1(raw_scores) → HER KEY clamp(0.0, 1.0) (toplam 1.0 olmak ZORUNDA DEĞİLDİR — CONTRACTS §3.6)
          7.  _check_transition_triggers(scores_clamped, feat_12, fv.null_count, opt, quality_hint) → (transition_reasons: list[str], effective_transition: bool)
          8.  _compute_confidence(scores_clamped, axes, opt, quality_hint) → float[0,1] (kalite penalty SONRASI confidence uygulanır — aşağıya doğru çarpan)
          9.  _select_regime_state(scores_clamped, effective_transition, opt) → MarketRegimeState
          10. _derive_lookback_ts(fv, start_override, end_override) → TimeRangeSpec
          11. _build_MarketRegime(frame_tf, state, confidence, scores_6key, det_ver, fv_ver, tr_spec) → MarketRegime instance
          12. _build_aux(...) → aux dict
          13. RETURN (market_regime_instance, aux)
        """
```

### 4.2 Adım 1: Feature doğrulaması (AD-22 feature_version zorunlu)
```python
EXPECTED_INPUT_FEATURE_VERSION = "fea_01_v1"
```
- **ADN-REG-02 VARYANT 1 (DEFAULT):** `fv.feature_version != "fea_01_v1"` → `raise ContractSchemaError(f"Unsupported feature_version={fv.feature_version!r}, expected='fea_01_v1'")`.
- **VARYANT 2 (Test fixture override options.unexpected_version_mode = "transition"):** transition_uncertain + confidence 0.05 + scores 0.05 all + transition.

### 4.3 Adım 2: 3 Eksen Ölçümü (Trend / Momentum / Volatility axes ∈ `[-1.0, +1.0]`)
Her bir 3 eksen kendi ağırlıkları + alt ölçütleri ile hesaplanır. Bu 3 eksen, 6 skorun ham bileşenleri olur.

#### 4.3.1 Eksen 1: Trend Ölçütü (Ağırlık: 0.50 → %50 trend ekseni)
Trend = 3 bileşen ortalaması:
  a) **EMA-Price Distance Score**:
     - `if ema_14 is None or ema_14 == 0 or close_raw is None` → 0.0 (nötr)
     - else: `ed = (close_raw - ema_14) / ema_14` → clamp `ed ∈ [-0.05, +0.05]` (±%5 maks) → normalize → `-1…+1`.
     - Örn: `ed = +0.02` → trend_ema = `clamp(ed/0.05, -1, +1)` = 0.40
  b) **RSI Neutral Center Offset (RSI):**
     - `if rsi_14 is None` → 0.0 (nötr)
     - else: `rs = (rsi_14 - 50.0) / 50.0` → clamp `[-1, +1]` → RSI 100 = +1, RSI 0 = -1, RSI 50=0.
  c) **VWAP-Price Distance Score:**
     - `if vwap_20 is None or vwap_20 == 0 or close_raw is None` → 0.0
     - else: `vd = (close_raw - vwap_20) / vwap_20` → ±%5 clamp → normalize → trend_vwap = `[-1,+1]`.

**Trend_Ekseni = clamp( `(0.45 × trend_ema + 0.35 × trend_rsi + 0.20 × trend_vwap)`, -1, +1 )**

#### 4.3.2 Eksen 2: Momentum Ölçütü (Ağırlık 0.30)
  a) **Abs Momentum normalizasyonu:** `mom_10_abs / close_raw` (close_raw None ise 0). clamp `[-0.05, +0.05]` → 20x büyüterek `[-1,+1]` → `mom_abs_component`.
  b) **Pct Momentum:** `mom_10_pct` (zaten %), clamp `[-5.0, +5.0]` → 5'e böl → `[-1,+1]` → `mom_pct_component`.

**Mom_Ekseni = clamp( `0.55 × mom_abs_component + 0.45 × mom_pct_component`, -1, +1 )**

#### 4.3.3 Eksen 3: Volatility Ölçütü (Ağırlık 0.20)
ÖNEMLİ: Vol ekseni **tek yönlü magnitude** (düşük vol = -1, yüksek vol = +1, orta = 0).
  - `if volatility_20_bps is None` → 0.0 (bilinmiyor → nötr)
  - `v = volatility_20_bps`
  - 3 bant:
    - (a) v ≤ LOW_VOL_CEIL(25) → `vol_ax = -1 + 2 × (v / 25.0)` (0 ise -1, 25 ise 0)
    - (b) v ≥ HIGH_VOL_FLOOR(150) → `vol_ax = min(1.0, (v - 150.0) / 150.0)` (150=0, 300+ = 1.0)
    - (c) 25 < v < 150 → doğrusal 0.0 yakın
  - Sonra vol_ratio ve vol_std scaling faktörü:
    - `vol_ratio_ax` = `vol_ratio_20` (1.0 civarı nötr, ≥2 = +0.1 ek puan, ≤0.5 = -0.1 puan) clamp [-0.1, +0.1]
    - `vol_std_ax` = `vol_std_20_scaled` (0 ise 0, ≥50 ise +0.1 ek, clamp [-0.1,+0.1])

**Vol_Ekseni = clamp( vol_ax + vol_ratio_ax + vol_std_ax, -1, +1 )**

> **ÖZET 3 EKSEN:** `trend_axis ∈ [-1,1]`, `mom_axis ∈ [-1,1]`, `vol_axis ∈ [-1,1]`. Bu 3'ü 6 ham skora dönüştürürüz.

### 4.4 Adım 3: 6 Ham Skor Hesabı
6 skor, 6 rejimle birebir ilişkili. Her biri önce ham sayı (ℝ), sonra clamp `[0.0, 1.0]`. **6 skorun toplamı 1 olmak ZORUNDA DEĞİLDİR (CONTRACTS §3.6).**

| Regime | Ham Skor Formülü (Ağırlıklı toplanır) | Açıklama |
|---|---|---|
| **bull_score** | `raw = 0.55 * (+trend_axis) + 0.30 * (+mom_axis) + 0.15 * max(0, -vol_axis)` → trend + momentum YUKARI, vol DÜŞÜK → bull güçlü | Clamp [0,1] |
| **bear_score** | `raw = 0.55 * (-trend_axis) + 0.30 * (-mom_axis) + 0.15 * max(0, -vol_axis)` → trend+mom AŞAĞI, vol DÜŞÜK | Clamp [0,1] |
| **sideways_score** | 3 bileşen ÇARPIM (hepsi nötrken yüksek):<br> `comp_trend_neutral = 1 - abs(trend_axis)` (trend 0 ise 1)<br>`comp_mom_neutral = 1 - abs(mom_axis)` (mom 0 ise 1)<br>`comp_vol_mid = 1 - abs(vol_axis)` (vol 0 → 1, -1/+1 → 0)<br>`raw_sideways = comp_trend_neutral × comp_mom_neutral × comp_vol_mid`<br> **EK bonus:** Eğer (EMA flat) AND (RSI 43-57) AND (abs(mom) ≤0.3%) → +0.30 bonus (sonra clamp [0,1]) | Clamp [0,1] |
| **high_volatility_score** | `raw = max(0.0, vol_axis) * 0.85 + (vol_spike_flag ? 0.15 : 0.0)` — vol spike: `vol_ratio_20 ≥ 2.0 AND volatility_20_bps ≥ 100`. Clamp [0,1] | Clamp [0,1] |
| **low_volatility_score** | `raw = max(0.0, -vol_axis) * 0.85 + (vol_calm_flag ? 0.15 : 0.0)` — vol calm: `volatility_20_bps ≤ 25 AND vol_ratio_20 ≤ 0.9` | Clamp [0,1] |
| **transition_uncertain_score** | Bu skor, daha Adım 4'te (transition triggerları) **puanlanır**; varsayılan başlangıç = 0.001 (minimum default — her zaman 0 değil). Clamp [0,1] | Clamp [0,1] |

### 4.5 Adım 4: Transition Uncertain Tetikleyicileri (4+1 Kalite = 5 Tetik)
Transition_Uncertain seçimi için AŞAĞIDAKİ 5 şarttan **HERHANGİ BİRİ (OR)** tetiklenirse `effective_transition = True`. Üstelik her tetikleyici skorları bozmadan **confidence düşürür** ve geçer.

| Tetikleyici # | İsim | Aktif Olma Şartı (ADN eşikler `DetectOptions` aracılığıyla testte override edilebilir — production değil default) | Doğrulayan AC |
|---|---|---|---|
| T1 | **Tie / Near-Tie** | Sorted 6 skor: `Top1 - Top2 < tie_threshold(0.05)` — yani iki rejim arasında 5 puan farktan az | C45, C46 |
| T2 | **Çelişkili Sinyal (Conflict)** | `(abs(trend_axis) + abs(mom_axis)) / 2 ≥ 0.400 AND abs(vol_axis) ≥ conflict_threshold(0.300)` ve **vol_axis, trend/mom karşı**: örn trend↑bull beklerken vol↑highvol bekler → çelişki var. Kesin formül: `conflict_score = abs( abs(trend_axis) - abs(vol_axis) ) / max(0.001, abs(trend_axis)+abs(mom_axis))` ise conflict_score ≥ 0.600 → T2 aktif. | C47, C48 |
| T3 | **Yetersiz Lookback (High Null Count)** | `FeatureVector.null_count / 9_nullable ≥ options.null_count_pct_transition (0.50)` — Yani 9 nullable feature'dan ≥ 5'i None → yetersiz lookback (aynı S-FEA-01 insufficient lookback davranışı). 9 nullable: ema_14, rsi_14, atr_14, vwap_20, mom_10_abs, mom_10_pct, volatility_20_bps, vol_ratio_20, vol_std_20_scaled. | C49, C50 |
| T4 | **Düşük Confidence** | Clamp SONRASI 6 skor maks skorundan önce bir proxy confidence (kalite öncesi): `proxy_conf = clamp(Top1 - mean(rest_5), 0, 1)` < `min_confidence_before_transition(0.350)` → T4 | C51 |
| T5 | **Kalite Bozuk → Transition (CAP-2)** | `quality_hint.invalid = True OR quality_hint.quarantined = True` → T5. Ekstra: diğer kalite modları (stale/degraded/duplicate/ooo/missing/abnormal_spread) → confidence düşürür, T5'i TRİGGERLAMAZ (T5 sadece invalid/quarantined için geçerli). | C52, C53, C54 |

### 4.6 Adım 5: Confidence Hesabı + Kalite Penalty Çarpanı
1. **Step 5a: Temel Confidence (kaliteden önce):**
   - `confidence_raw = 1.0 - (stddev_of_clamped_scores * k)` — 6 skorun standart sapması yüksek (skorlar yayılmış, çelişkili) → confidence düşük.
   - Alternatif kesin formül (ZORUNLU, deterministik):
     ```
     import statistics
     s6 = list(clamped_scores.values())  # sorted (alphabetical to deterministic)
     top1 = max(s6)
     mean_rest = (sum(s6) - top1) / (len(s6) - 1)   # len=6 olduğu için 5e böl
     conf_base = clamp(top1 - mean_rest, 0.0, 1.0)
     # sonra confidence_smooth_alpha yumuşat:
     conf_smoothed = clamp(confidence_smooth_alpha * conf_base + (1-confidence_smooth_alpha) * (top1), 0.0, 1.0)
     ```
2. **Step 5b: Kalite Çarpanı (CAP-2 okuma, NO MUTATE):**
   ```
   qh = quality_hint or QualityHint()
   qmul = 1.0
   if qh.invalid or qh.quarantined:
       qmul *= quality_penalty_invalid_quarantined(0.20)   # T5 de tetiklenir!
   if qh.stale or qh.degraded:
       qmul *= quality_penalty_stale_degraded(0.75)
   if qh.duplicate or qh.out_of_order or qh.missing:
       qmul *= quality_penalty_dup_missing_ooo(0.90)
   if qh.abnormal_spread:
       qmul *= quality_penalty_abnormal_spread(0.85)
   # Tüm kalite çarpanları BİRLEŞİK (çarpımsal). Sonuç clamp [0,1]
   ```
3. **Step 5c: Transition etkisi → confidence minimuma düşüş:**
   Eğer T1–T5 herhangi biri AKTİF → `conf_transition_factor = 0.75` (confidence 25% daha düşer).
4. **Adım 5d Final:** `confidence_final = clamp(conf_smoothed * qmul * (conf_transition_factor if effective_transition else 1.0), 0.0, 1.0)` → HER ZAMAN `[0,1]` aralığı (MarketRegime contract zorunlu).

### 4.7 Adım 6: Rejim Seçimi
- Eğer `effective_transition = True` → **KESİN** `MarketRegimeState.TRANSITION_UNCERTAIN`.
- Aksi: 6 skorun **maksimum** anahtar → enum state.
  - Tiebreaker: Eğer 2+ skor aynı max → alfabetik ilk (determinism için). Örn `bear=0.70, bull=0.70` → bear (alfabetik önde). → Bu da **tie threshold** ile T1 tetiklendiği için neredeyse hiç yaşanmaz ama yaşanırsa deterministik alfabetik öncelik → PASS.

### 4.8 Adım 7: TimeRangeSpec (lookback_ts) Türetme (ADN-REG-04)
- Eğer `lookback_start_override` ve `lookback_end_override` verilmiş → bunları kullan.
- Aksi: `FeatureVector.input_refs` ULIDish/Instant string içeriyorsa:
  - `start = min(Instant(s) for s in input_refs)` (string ISO karşılaştırması yeter)
  - `end   = max(Instant(s) for s in input_refs)`
- Eğer `input_refs` boş veya ISO değilse → **ADN-REG-04 VARYANT 1 (DEFAULT):** `ContractSchemaError("Cannot derive lookback_ts; input_refs empty/invalid — please provide lookback_start/end_override")`. VARYANT 2: lookback_ts = `(as_of_now = end of fv ??? YOK, determinizm için RAISE, VARYANT 1 DEFAULT)`.
- ZORUNLU: `start ≤ end` (TimeRangeSpec.__post_init__ zaten doğrular).

### 4.9 Adım 8: MarketRegime Constructor (KESİNLİKLE MEVCUT CONTRACT)
```
return MarketRegime(
    timeframe = feature_vector.timeframe,      # "1h" vs — FeatureVector'dan kopya
    regime = state,                           # enum
    confidence = confidence_final,            # [0,1]
    scores = clamped_scores_sorted_dict_6key,  # 6 key, her float [0,1], REGIME_KEYS frozenset aynısı
    detector_version = self.detector_version,  # "reg_01_v1"
    feature_version = feature_vector.feature_version,  # "fea_01_v1"
    lookback_ts = time_range_spec_instance,    # TimeRangeSpec
)
```
- **ÇOK ÖNEMLİ:** MarketRegime'in 8. alanı olarak correlation/causation/symbol EKLEME. Bunlar **AUX** sözlüğünde (ikinci tuple elemanı) döner. Bunları downstream consumer (EventBus envelope publisher) ekler → AD-3 envelope zaten `correlation_id`/`causation_id` taşıyor (Zorunlu NFR-019/SPEC §). Bu hikâyede REJİM ENGINE, BU metadata'yı ayrı aux olarak kaydeder → envelope üretimi ayrı komponent.

### 4.10 Kalite Davranışı (CAP-2 KANIT)
**İKİ YÖNTEMLE KANIT:**
1. **Read-only enforce:** `@dataclass(frozen=True) QualityHint` → SETATTR denerseniz Python raise FrozenInstanceError.
2. **AST tarayıcı testi:** `app/regime/engine.py` içinde QualityFlags / quality_hint ataması (`Assign`, `AugAssign`) YOK — 0 finding.
3. **No validator call:** `from app.contracts.quality import ...` importu yok → validator yeniden çağrılmıyor. Sadece caller QualityHint doldurur.

---

## 5. Acceptance Criteria (72/72 — HEPİ Test Edilebilir, AC #C1..C72)

### H1: 6 Enum Coverage + Bull/Bear/Sideways Happy (C1–C18 — 18 AC)
| # | AC (C1+) | Davranış | Grup |
|---|---|---|---|
| C1 | Bull Sinyal → regime=bull + confidence≥0.40 | Trend↑↑Mom↑ + Low Vol | H1-Happy |
| C2 | Bear Sinyal → regime=bear + confidence≥0.40 | Trend↓↓Mom↓ + Low Vol | H1 |
| C3 | Sideways sinyal → regime=sideways + RSI 43-57, EMA flat, mom flat | 3 nötr bileşen + bonus +0.30 | H1 |
| C4 | HighVol → regime=high_volatility + confidence≥0.45 | vol_axis≥0.8 + spike | H1 |
| C5 | LowVol → regime=low_volatility + confidence≥0.45 | vol_axis≤-0.8 + calm | H1 |
| C6 | Near-Tie → regime=transition_uncertain + tie_activated=True aux | bull=0.40, bear=0.37 fark<0.05 → T1 | H1 |
| C7 | Transition Confidence → her zaman ≤ 0.80 | confidence_smoothed * 0.75 | H1 |
| C8 | 6-key scores ZORUNLU: HERHANGİ bir MarketRegime.scores.keys() == REGIME_KEYS → True | sözleşme | H1 |
| C9 | scores values HEPSI float ∈ [0,1] → contract post_init validasyon HATA YAPMAZ | clamped_scores doğruluğu | H1 |
| C10 | scores sum 1.0 olmak ZORUNDA DEĞİL → test 0.78 TOPLAM geçmeli | CONTRACTS §3.6 | H1 |
| C11 | detector_version == "reg_01_v1" varsayılan | expected | H1 |
| C12 | feature_version == FeatureVector.feature_version → "fea_01_v1" | koruma | H1 |
| C13 | timeframe == FeatureVector.timeframe | 1h korunur | H1 |
| C14 | lookback_ts.start ≤ lookback_ts.end, TimeRangeSpec ISO valid | Doğrudan contract | H1 |
| C15 | schema_sha256 ve to_sorted_dict → 2 kez aynı → True | determinizm min | H1 |
| C16 | bull_score ağırlık (trend↑ 0.55 doğru) el ile fixture hesap doğrula | Hesap doğruluğu | H1 |
| C17 | bear_score ağırlık (trend↓ 0.55) — el hesap doğrula | Hesap doğruluğu | H1 |
| C18 | transition_uncertain skor başlangıç 0.001 minimum (0 değil) — doğrula | Determinizm koruma | H1 |

### H2: High/Low Vol Özel (C19–C36 — 18 AC)
| C19 | HighVol: volatility_20_bps=200 (≥150) + vol_ratio≥2 → high_vol_score ≥ 0.80 | Fixture |
| C20 | HighVol: v=125, ratio=1.0 → skor 0.40–0.60 | Orta band |
| C21 | LowVol: v=10 + ratio=0.7 → low_vol_score ≥ 0.75 | Düşük |
| C22 | LowVol: v=30 + ratio=1.2 → low_vol_score ≤ 0.10 | Eşiğin üstünde |
| C23 | Spike Flag (v≥100 + ratio≥2) → high_vol ek 0.15 puan | Tetik doğruluğu |
| C24 | Calm Flag (v≤25 + ratio≤0.9) → low_vol ek 0.15 puan | Tetik doğruluğu |
| C25 | Vol ekseni 0 (nötr) → high_vol + low_vol skorları < 0.30 | Özel |
| C26 | Vol ekseni +1, trend 0 → high_vol seçim | Doğru |
| C27 | Vol ekseni -1, trend 0 → low_vol seçim | Doğru |
| C28 | atr_14 None (insufficient ATR lookback) → vol_axis hesaba KATILMAZ (0.0 nötr) | Null koruma |
| C29 | volatility_20_bps None → vol_axis 0 + insufficient_lookback_score +0 → ama T3? 9 nullable'dan 1 kayıp 1/9=0.11 <0.5 → T3 yok | null_count 1 |
| C30 | high_vol ve low_vol aynı anda HIGH → near-tie T1 → transition | Çelişki |
| C31 | volatility_20_bps=0.0 → low_vol_score ≥ 0.85 | Edge |
| C32 | volatility_20_bps=500.0 → high_vol_score ≥ 0.90 | Edge |
| C33 | vol_std_20_scaled büyük → vol_ax küçük artış (±0.1 limit) | sınır |
| C34 | vol_ratio_20 çok küçük (0.2) → vol_ax düşür | sınır |
| C35 | HighVol seçim → scores['high_volatility'] en büyük (transition YOKSA) | seçim |
| C36 | LowVol seçim → scores['low_volatility'] en büyük (transition YOKSA) | seçim |

### H3: Transition Uncertain 5 Tetikleyici (C37–C54 = 18 AC)
| # | Tetik | Doğrulama |
|---|---|---|
| C37 | T1 Tie: bull=0.42, bear=0.40 (diff 0.02 < 0.05) → regime=transition + tie_activated=True | Doğrudan |
| C38 | T1 Değil: bull=0.45, bear=0.39 (diff 0.06 > 0.05) → T1 YOK, bull seçilir | Doğrudan |
| C39 | T2 Conflict: Trend↑=0.80 kuvvetli, vol_axis↑=0.60 yüksek vol → conflict_score ≥ 0.6 → transition | Çelişki |
| C40 | T2 No Conflict: trend 0.20, vol 0.20 → conflict küçük → T2 yok | |
| C41 | T3 Null Count: 9 nullable'dan 6 None → 6/9=0.67 ≥ 0.50 → T3 + transition | Yetersiz |
| C42 | T3 No: 9'dan 4 None → 4/9=0.44 < 0.50 → T3 YOK | |
| C43 | T4 Düşük Confidence: 6 skor (0.22, 0.22, 0.20, 0.15, 0.11, 0.10) → top1-mean(rest)=0.04 < 0.35 → T4 transition | |
| C44 | T4 No: top1=0.70, rest ortalama 0.06 → fark 0.64 → T4 YOK | |
| C45 | T5 Kalite Invalid: quality_hint.invalid=True → effective_transition=True (qmul=0.20) + confidence ≤ 0.20 | H6-CAP-2 |
| C46 | T5 Kalite Quarantined: qh.quarantined=True → transition (aynı T5) | |
| C47 | T1 tie, threshold 0.01 → override ile tie threshold 0.001 → test geçer (options override ÇALIŞIYOR) | Options kalıcı değil production |
| C48 | T2 conflict, options.conflict_threshold=0.05 → küçük bir uyumsuzlukta T2 | Options |
| C49 | T3 null_count_pct = 0.10 override → 1 None ≥0.1 → T3 | Options |
| C50 | T3 için 9 nullable FEATURE anahtarlarının sayısı doğru mu? (9 evet: ema_14, rsi_14, atr_14, vwap_20, mom_10_abs, mom_10_pct, volatility_20_bps, vol_ratio_20, vol_std_20_scaled → 9) | Sabit |
| C51 | transition etkisiyle confidence_final 0.75 çarpanı uygulanmış → kontrol | Doğrudan |
| C52 | Kalite stale → qmul 0.75 → confidence 0.25 düşer, T5 YOK → transition YOK (sadece invalid/quarantined T5) | CAP-2 |
| C53 | Kalite degraded → 0.75 qmul | |
| C54 | Kalite duplicate/missing/out_of_order → qmul 0.90 → 10% confidence düşüşü T5 YOK → | |

### H4: Confidence + Scores Aralığı + Tiebreaker (C55–C63 — 9 AC)
| C55 | confidence_final HER ZAMAN 0.0 ≤ c ≤ 1.0 (özellikle extreme kalite 0.20*0.75*0.90*0.85 → ~0.114 clamp 0–1) | |
| C56 | confidence_final hiçbir zaman NEGATİF veya >1 → contract post_init validasyon doğrular | |
| C57 | EMA-14 None, VWAP-20 None → 2 feature None → 2/9=0.22 → T3 yok (Confidence düşer ama transition zorunlu değil) | |
| C58 | Tiebreaker aynı max 2 → alfabetik önce: bear=bull=0.50 → bear (alfabetik önce: B < H) → eğer tie threshold 0 olsun override → tie T1 yok. Aksi T1 var | Determinizm |
| C59 | 6 skorun hepsi 0.0 → transition T4 düşük confidence (max=0.0 < 0.35) + Sıfır → regime=transition, confidence≤0.20 | Edge |
| C60 | Skorlar (transition 0.5, high_vol 0.48) → fark 0.02 < 0.05 T1 → transition_uncertain (T1), transition zaten var, seçim doğru | |
| C61 | Proxy_conf (top1 - mean_rest) el hesapla eşleşiyor mu? Kontrol | Doğruluk |
| C62 | confidence_smooth_alpha 0.85 doğrulandı (fixture: alpha=0.50 override → farklı sonuç, çalışıyor) | Options |
| C63 | Kalite abnormal_spread → qmul 0.85 → confidence 15% düşüşü | CAP-2 |

### H5: Input Validation + Lookback_ts + Aux (C64–C69 — 6 AC)
| C64 | feature_version == "fea_02_v99" → ADN-REG-02 default RAISE ContractSchemaError | ADN-REG-02 |
| C65 | C64 varyant 2 → options.unexpected_version_mode="transition" (ADN-REG-02) → transition + confidence düşük | |
| C66 | FeatureVector.input_refs boş → lookback_ts override YOK → ADN-REG-04 default RAISE (determinizm koru) | ADN-REG-04 |
| C67 | C66 varyant 2 → lookback_start/end override verilince çalışır → TİMERANGESPEC doğru | |
| C68 | Aux dict: correlation_id ve causation_id doğru döndürülen 2. tuple elemanında (MarketRegime contract'ta YOK — AUX) | ADN-REG-01 |
| C69 | Aux dict: `raw_axes` trend, mom, vol eksenlerinin 3 değerinin her biri ∈ [-1, +1] clamp doğru | Hesap |

### H6: CAP-1 / CAP-2 / Safety / Regression (C70–C72 — 3 AC)
| C70 | CAP-1 AST scan → `run_mode`/`source_type` if/attribute 0 finding. 5 modül (`app/contracts`, `app/features`, `app/regime`, ...). `app/regime` İÇİNDE 0 finding. | |
| C71 | CAP-2 AST scan → QualityFlags/quality_hint Assign/AugAssign 0 finding (NO MUTATE). Ayrıca validator importu YOK. Frozen dataclass QualityHint → testte setattr dene → FrozenInstanceError. | |
| C72 | FULL regression smoke: 22 import subset (her contract ve S-CON-02A/B/C FEA01) 0 import error; pyproject dependencies=[]; CONTRACT_VERSION 1.0.0; forbidden 22 lib AST 0. | |

---

## 6. Definition of Done (14/14 — HER BİRİ BİREYSEL DOĞRULANACAK)

| # | DoD | Kaynak / İlişkili AC |
|---|---|---|
| DoD-01 | 6 rejim (bull/bear/sideways/high_volatility/low_volatility/transition_uncertain) HERHANGİ bir fixture → EN AZ 1 KEZ `regime` olarak seçilmiş ve test edilmiş. 6/6 coverage. | C1-C6 + 18 AC |
| DoD-02 | Trend/Momentum/Volatility 3 eksen formülleri (ağırlıklar, clamp, null koruma, 9 nullable sayısı) 10+ EL fixture ile hesap doğrulanmış. | C16,C17,C49,C69 |
| DoD-03 | 6 skor clamp [0,1]; scores.keys() = REGIME_KEYS; her değer float; toplam=1 zorunlu DEĞİL testi. | C8,C9,C10 |
| DoD-04 | 5 transition tetikleyicisi (T1/T2/T3/T4/T5) ayrı ayrı + birleşik (3 tetik aynı anda) kapsamlı test edilmiş. | H3 18 AC C37-C54 |
| DoD-05 | Confidence hesabı (smooth alpha + kalite penalty * transition penalty ×) 0–1 aralığı clamp + kalite 7 modu tek tek test edilmiş. | C52-C54,C55,C56,C63 |
| DoD-06 | CAP-1 replay/live parity 0 branch AST tarayıcı + `if run_mode` / `source_type` 0 finding. | C70 |
| DoD-07 | CAP-2 read-only kalite: QualityHint frozen, Assign/AugAssign 0, validator import yok; kalite bayrakları okunur → confidence etkiler ama mutate edilmez/validator çağrılmaz. | C45,C46,C52-C54,C62,C71 |
| DoD-08 | AD-20 10x determinizm: 10 kez `schema_sha256(regime)` 1 unique; aux dict JSON sorted 10 kez aynı digest. | H7 determinizm testleri |
| DoD-09 | FeatureVector AD-22: Yanlış feature_version → ADN-REG-02 default raise (doğrulandı); override transition → doğru. | C64,C65 |
| DoD-10 | Lookback_ts TimeRangeSpec: start ≤ end ISO doğruluğu; override çalışıyor; empty input_refs → ADN-REG-04 raise. | C66,C67 |
| DoD-11 | Correlation/Causation → AUX dict 2. tuple elemanı; MarketRegime contract 7 ALAN SABİT (8. alan YOK), contract public API BOZULMAMIŞ, CONTRACT_VERSION 1.0.0. | C68 + Regression C72 |
| DoD-12 | PYPROJECT `dependencies=[]` korunur; 0 yeni runtime dependency; forbidden 22 kütüphane (pandas/numpy/ta/ccxt/…) 0 import; credential 0; network 0; 562 regression tamamen korunur (test subset 22 import + C72 smoke). | C72 + safety |
| DoD-13 | 562 mevcut test BOZULMAMALI (full suite 562 PASS devam etmeli, **hiçbir S-RDH/S-PLN/S-CON/S-FEA testi FAIL OLMAMALI**). AC sayısı 72'ye ek ≥240 yeni → **toplam ≥ 802 test PASS.** | Safety regression |
| DoD-14 | 72 AC (H1+H2+H3+H4+H5+H6) 100% PASS; H7/H8 (determinism/safety) ayrıca doğrulandı. | 72 + ≥18 safety+determinism ekstra → 90+ AC ilişkili |

---

## 7. Test Planı (9 dosya, ≥ 240 Yeni Test + 562 Regression)

### 7.1 Test Klasör Yapısı
```
app/regime/              ← 2 yeni engine + init
tests/regime/            ← 9 yeni test dosyası (H1–H8 coverage)
```
Her test dosyasında parametrize + varyant:

| Dosya | Test Sayısı Tahmini | AC Kapsar | Ana Fixture Örnekleri |
|---|---|---|---|
| test_sreg01_engine_basics.py | ≥ 20 (parametrize + 3) | C1–C18, C58 | bull 0.6, bear 0.6, sideways 3-nötr, tie 0.42/0.40 → transition |
| test_sreg01_high_low_vol.py | ≥ 18 (parametrize 8) | C19–C36 | v=5/10/25/50/125/150/200/500 bps × ratio 0.2/0.7/1.0/2.0/3.0 |
| test_sreg01_transition_uncertain.py | ≥ 28 (5 tetikleyici × 5 varyant + 3 combine) | C37–C54, C51 | T1 tie diff 0.01–0.10; T2 conflict_score 0.4–0.8; T3 null 0/3/5/7/9; T4 top1 0.20-0.70; T5 invalid+quarantined |
| test_sreg01_scores_confidence.py | ≥ 24 (confidence 4 kalite × 2) | C10,C55,C56,C57,C59,C60,C61,C62 | conf 0.0, 0.5, 1.0 clamp; 6 skor 0.0 edge; transition 0.75 çarpan; alpha override 0.5 |
| test_sreg01_quality_cap2.py | ≥ 26 (7 kalite bayrağı × 3 varyant + T5 sadece invalid/q) | C45,C46,C52,C53,C54,C63,C71 | T5 (invalid, quar) → transition; stale/degraded → qmul 0.75 (no T5); dup/miss/ooo → 0.90; abnormal 0.85; + Combined 7 all true → confidence 0.086 clamp 0–1 |
| test_sreg01_aux_metadata.py | ≥ 12 (corr/caus/lookback) | C64,C65,C66,C67,C68,C69 | feature_version yanlış → raise; lookback_override ver; empty input_refs → raise; corr/caus = 26-char ULID aux içinde doğru döner |
| test_sreg01_determinism_cap1.py | ≥ 30 (10× determinizm 5 fixture, CAP-1 AST scan 5, leakage 3, NaN coerce 4, feature version 3, options override 5) | C15,C47,C48,C49,C70,C62 | 5 fixture × 10 kez determinizm; AST NodeVisitor 0 finding run_mode/source_type; options override ile threshold testleri |
| test_sreg01_formula_verification.py | ≥ 48 (3 eksen × 10 fixture hand verify + 6 skor × 3 hand verify + confidence × 3 hand verify) | C16,C17,C61,C69 | Trend/Mom/Vol 30 fixture hand; 6 skor 18 fixture; confidence 9 fixture; EL HESAPLAMA ile engine.detect sonucu arasında < 1e-9 fark (float karşılaştırma tolerance) |
| test_sreg01_safety_regression.py | ≥ 34 (forbidden lib 22, credential 2, network 3, regression smoke 22, pyproject deps, contract_version, sha regime unchanged) | C72 | 22 forbidden AST 0; 2 credential substr 0; 3 network token 0; 22 import 0 error; `app/contracts/regime.py` sha değişmedi → 0 contract mutation |

**TOPLAM ≥ 20+18+28+24+26+12+30+48+34 = 240 Yeni Test.**

### 7.2 Özel Güvenlik/Regression Testleri
1. **AST Forbidden Imports (22 lib):** `ast.NodeVisitor` Import/ImportFrom node isimleri: pandas, numpy, ta, talib, ccxt, binance, pydantic, attrs, msgspec, cattrs, sklearn, xgboost, torch, tensorflow, requests, aiohttp, websockets, httpx, sqlalchemy, psycopg, boto3, redis → 0 match.
2. **Credential Substrings (chr concat ile oluşturulan stringler BULUNDURULMAZ, doğrudan substring YOK):** 2 hassas kelime 0.
3. **Network Tokens:** requests, urllib.request, aiohttp, httpx, websockets, socket, urllib3 → 0 match.
4. **DB Tokens:** sqlalchemy, psycopg, sqlite3, asyncpg, pymongo, redis → 0 match.
5. **Contract unchanged SHA:** `hashlib.sha256(open('app/contracts/regime.py','rb').read()).hexdigest()` başlangıç (baseline) hash ile AYNI. Değişiklik YOK.

---

## 8. Algoritma Varsayımları (Spec'te belirtilmeyen, production kararı OLMAYAN — Test Defaultları, ADN ile Açık)

| Varsayım # | İçerik | Kiracı (DetectOptions) | Override Edilebilir mi? | Production Kararı mı? |
|---|---|---|---|---|
| A1 | 3 eksen ağırlık (0.50 trend, 0.30 mom, 0.20 vol) | `options.trend_momentum_axis_weight` | ✅ Evet, testte | ❌ HAYIR — ADN-REG-05 |
| A2 | Tie threshold = 0.050 | `options.tie_threshold` | ✅ | ❌ ADN-REG-03 |
| A3 | Conflict threshold = 0.300 | `options.conflict_threshold` | ✅ | ❌ ADN-REG-03 |
| A4 | Null count yüzde = 0.500 | `options.null_count_pct_transition` | ✅ | ❌ ADN-REG-03 |
| A5 | Min confidence transition = 0.350 | `options.min_confidence_before_transition` | ✅ | ❌ ADN-REG-03 |
| A6 | HighVol zemin 150 bps, LowVol tavan 25 bps | `high_vol_bps_floor`, `low_vol_bps_ceiling` | ✅ | ❌ ADN-REG-06 |
| A7 | Sideways bonus 0.30 puan | `options.sideways_rsi_band`, `sideways_band_ema_pct`, `momentum_band_abs_pct` ile birlikte | ✅ | ❌ ADN-REG-07 |
| A8 | 9 nullable anahtar sabit listesi (ema_14, rsi_14, atr_14, vwap_20, mom_10_abs, mom_10_pct, volatility_20_bps, vol_ratio_20, vol_std_20_scaled) | Sabit | ❌ Hayır — AD-22 12-key registry kesin | ✅ Kısmi (kesin, fea_01_v1 için) |
| A9 | Kalite penalty 4 çarpan (0.20 invalid/q, 0.75 stale/degraded, 0.90 dup/miss/ooo, 0.85 abnormal) | `quality_penalty_*` 4 seçenek | ✅ | ❌ ADN-REG-08 |
| A10 | Transition confidence çarpanı 0.75 (sabit, options aracılığıyla değil — KESİN, hikâye spec) | Yok | ❌ | ✅ Evet — v1 kesin (ileride options taşınabilir, bu hikâyede SABİT) |

---

## 9. Açık Kararlar (ADN-REG-01..ADN-REG-08 — Üretim Kararları Değil, Sadece Defaultlar Hikâye Tarafından)

| ADN Kodu | Konu | Bu Hikâyedeki Default Davranış | Üretim Kararı Girişi |
|---|---|---|---|
| **ADN-REG-01** | Correlation_id / Causation_id / Symbol (3 alan) MarketRegime contract içinde Mevcut DEĞİL; contract bump yasak | Engine `(MarketRegime, aux_dict)` 2-tuple döndür; aux: `{"correlation_id", "causation_id", "symbol", ...}`. Publisher envelope bu 3 alanı AD-3 canonical envelope metadata olarak ekler. | Gelecek S-REG-02 ya da E-CON contract bump aşamasında istenirse MarketRegime 2.0 (1.1) eklenebilir. BU HİKÂYEDE YOK. |
| **ADN-REG-02** | Yanlış / desteklenmeyen feature_version davranışı | Default raise `ContractSchemaError`. Varyant 2 (opsiyonel): `options.unexpected_version_mode="transition"` → transition + confidence düşük. | Gelecek fea_02_v2 çıkarsa karar — bu hikâyede raise default. |
| **ADN-REG-03** | Tie / Conflict / Insufficient Lookback / Low Confidence 4 eşiğin production sayısallığı | Default: 0.050, 0.300, 0.500, 0.350. | Backtest + paper trading evaulation sonrası (S-REG-02 veya E-REG-2) optimize edilir. |
| **ADN-REG-04** | lookback_ts başlangıç/bitiş Instant üretimi yöntemi | Default: FeatureVector.input_refs min/max (ISO string); empty ise RAISE. Override verilebilir. | Gelecek: input_refs[-1] son mum open_time kesin Instant ise; bu hikâyede RAISE default güvenlidir. |
| **ADN-REG-05** | Trend/Momentum/Vol 3 ekseninin 3 bileşen ağırlıkları | 0.50 / 0.30 / 0.20; trend içi 0.45 ema / 0.35 rsi / 0.20 vwap; mom 0.55 abs / 0.45 pct. | Aynı ADN-REG-03 — evaluation sonrası optimize. |
| **ADN-REG-06** | HighVol (150 bps) / LowVol (25 bps) bantları | 150 / 25 bps (1h timeframe varsayılan; 1m için farklı olabilir). | Timeframe bazlı ayar — evaluation sonra. |
| **ADN-REG-07** | Sideways bonus 0.30 + RSI band (43-57) + mom flat 0.3% + ema flat 0.5% | 3 nötr bileşen + bonus | Sideways tanımının incelemesi market koşullarına göre güncellenebilir. |
| **ADN-REG-08** | Kalite 4 penalty çarpanları | 0.20 / 0.75 / 0.90 / 0.85. | Kalite politikasının S-RDH-02 sonuçlarına göre incelemesi — AD-5 hard gate ile ilişkilidir. |

---

## 10. Mimari Uyumluluk / AD Referansları (Her AD için Hikâye Davranışı)
| AD Kodu | Konu | Bu Hikâyedeki Uygulama |
|---|---|---|
| AD-1 | Modular Monolith | `app/regime/` → ayrı bounded context; `app/contracts`, `app/features` sadece import, NO strategy/risk |
| AD-3 | Envelope Correlation/Causation | Aux dict olarak döndürülür; envelope metadata eklenir, engine correlation üretmez ama saklar |
| AD-4 | Live/Replay Parity (CAP-1) | 0 run_mode/source_type branch; AST scan 0 |
| AD-5 | Data Quality Hard Gate | Kalite bayrakları READ-ONLY, invalid/quarantined → transition, diğerleri → confidence azalt (NO mutate/validator) |
| AD-8 | Regime Independent Service | 6-state + confidence + scores; strategy/risk/AI'den bağımsız |
| AD-9 | Strategy Plugin Pure | Engine SADECE FeatureVector + kalite okur, strategy import YOK (OOS) |
| AD-17 | Observability Correlation | Aux correlation/causation döndürülür, trace saklanır |
| AD-20 | Testability / Determinism | 10x determinizm + 3 eksen hand verify 30 fixture + C8 doğrulamaları |
| AD-22 | Feature Version Contract | Yalnızca "fea_01_v1" kabul (ADN-REG-02); 9 nullable sayısı sabit |
| AD-23 | Registry/Status Mutation YOK | Sadece model registry bu hikâyede YOK — kaleme ALINMAZ (OOS) |

---

## 11. Dependencies (0 Yeni Runtime Dep — Stdlib-Only)
- `pyproject.toml` L5 `dependencies=[]` **DEĞİŞMEDEN KALACAK.**
- Kullanılacak STANDART kütüphaneler (HEPSI stdlib): `dataclasses`, `typing` (Any, Union, Optional, Literal, FrozenSet), `math` (clamp için 3.14+ `math.clamp` veya kendi clamp), `statistics` (mean, fmean, stdev), `hashlib` (sha256 digest aux determinizm için), `json` (sorted dumps aux), `ast` (test fixtures), `re` (test regex, engine içinde 0), `copy` (deepcopy options frozen, 0).
- YASAK: `pandas`, `numpy`, `ta`, `talib`, `ccxt`, `binance`, `pydantic`, `msgspec`, `cattrs`, `attrs`, `sklearn`, `xgboost`, `torch`, `tensorflow`, `requests`, `aiohttp`, `websockets`, `httpx`, `sqlalchemy`, `psycopg`, `boto3`, `redis`, `pymongo` (22 tanesi AST scan 0 finding — 562 regression korunur).

---

## 12. Out of Scope (Kapsam DIŞI — 16 Kalem)
| # | Kapsam Dışı | Neden |
|---|---|---|
| 1 | Strategy plugin implement (trend/momentum) | E-STR — S-STR-01 |
| 2 | OpportunityScore / Component Policy | E-AIS |
| 3 | RiskEngine / KillSwitch / Limits | E-RSK |
| 4 | Backtest Engine / Walk Forward | E-BKT |
| 5 | Paper Trading / Fill Model / Portfolio | E-PTR / E-PTF |
| 6 | Live Exchange Connectivity / API Keys | OOS - V1 Hard Safety |
| 7 | PostgreSQL / TimescaleDB / ObjectStore | E-PLN / E-FND-03 sonrası |
| 8 | Dashboard / MVP API Surface | E-API |
| 9 | AI/ML training / inference / classification | E-MDL / E-AIS |
| 10 | Regime Engine 2.0 / Alternate detector (S-REG-02) | E-REG 2. hikâye |
| 11 | correlation_id, causation_id'nin MarketRegime contract'a EKLENMESİ (ADN-REG-01 open) | Contract bump YOK bu hikâyede |
| 12 | ADN-REG-01..08 üretim eşiklerinin KALICI (non-fixture) kararları | Gelecek E-REG-2 / E-STR evaluation sonrası |
| 13 | EventBus / envelope publish (bu hikâyede sadece detection, publish OOS) | Publisher downstream ayrı komponent |
| 14 | Per-symbol regime calibration (BTC / ETH / altcoinler için farklı threshold) | OOS — 1 detector 1 threshold (ADN-REG-03) |
| 15 | Multi-timeframe regime (1h + 4h + 1d combined) | OOS — S-REG-02 |
| 16 | Feature selection / feature importance | E-AIS / Model |

---

## 13. Implementation Readiness (Hikaye Hazır mı? → ✅ HAZIR)
### 13.1 Exit Criteria (10/10)
| Exit Criterium | Durum |
|---|---|
| 1. Hikâye id/key/title/baseline/previous/next mevcut | ✅ |
| 2. 72 AC list, test edilebilir, her biri C1..C72 | ✅ 72 AC |
| 3. 14 DoD list, her biri kanıtlanabilir | ✅ 14 DoD |
| 4. 9 test dosyası planı ≥ 240 yeni test + 562 regression korunacak | ✅ ≥240 yeni |
| 5. Algoritma 3 eksen + 6 skor + 5 transition tetikleyici + confidence + kalite 7 modu + tiebreaker + lookback_ts ADN detaylı açıklandı | ✅ §4 |
| 6. 8 ADN (ADN-REG-01..08) açıkça listelendi — production kararları HİÇBİRİ kalıcı yazılmadı, sadece fixture default olarak DetectOptions override edilebilir | ✅ §9 |
| 7. Hard Safety sınırları + 0 yeni dep + contract version 1.0.0 + 6-state YENİ DURUM YOK (sabit 6) + contract unchanged | ✅ |
| 8. Out of Scope 16 kalem list → strateji/risk/AI/execution OOS | ✅ |
| 9. Mimari AD-1/3/4/5/8/9/17/20/22 hepsine tek tek referans + uygulama detayı | ✅ §10 |
| 10. Dosya yapısı (9 test dosyası, 2 kaynak dosya) list, her dosya satır tahmini + kapsam | ✅ §3 |

### 13.2 Regression Koruması (KANITLANMALI)
```
BEFORE IMPLEMENTATION (baseline):     562 / 562 PASS    (RDH 68+64 + PLN 42 + CON-02A/B/C 104+71+93 + FEA-01 120)
AFTER IMPLEMENTATION (HEDEF):         562 / 562 PASS    (BOZULMAMA — regression 0 FAIL) + 240 YENİ TEST = ≥ 802 PASS TOPLAM
```

### 13.3 Implementation Notları (Dev agent için son uyarılar):
1. `app/contracts/regime.py` DOSYASINI AÇMA, DEĞİŞTİRME, 8. ALAN EKLEME. (ZORUNLU)
2. `CONTRACT_VERSION = "1.0.0"` KORUNUR — BUMP YOK.
3. FeatureVector AD-22 12-key registry okunurken `try/except` YOK, doğrudan 12 key istenen sürüm kontrol edilir (ADN-REG-02 raise default).
4. QualityHint: `@dataclass(frozen=True)` — frozen, immutable; assign raise.
5. DetectOptions frozen, options override Sadece testte; production DEFAULT_OPTIONS.
6. Determinizm: Sıralama her zaman alfabetik (sorted keys); set yerine sorted list; tiebreaker alfabetik öncelik.
7. Tüm float karşılaştırmalar: `abs(a - b) < 1e-9 tolerance` (floating point hassasiyeti).
8. `.gitignore` (workaround) _run_pytest.py / _pytest_local/ ignore edilmek istenirse KULLANICI ONAYI gerekir — BU HİKÂYEDE YOK.

---

## 14. Completion Record (Bu Hikâye Spec Oluşturulduktan Sonra Doldurulur — DEV aşaması)
> Bu bölüm, `bmad-dev-story` tarafından S-REG-01 IMPLEMENT EDİLDİKTEN SONRA doldurulur (spec oluşturma aşamasında boş).
```
[ ] 14.1 Test Sonuçları: ____ PASS / ____ Toplam (562 regression + 240+ yeni)
[ ] 14.2 AC: 72/72 PASS
[ ] 14.3 DoD: 14/14 PASS
[ ] 14.4 Oluşturulan/Değiştirilen dosyalar (liste)
[ ] 14.5 Safety (forbidden 22 lib 0, credential 0, network 0)
[ ] 14.6 Lessons Learned (3+ kalem)
[ ] 14.7 Exit Criteria 10/10 KANIT
```

---

**Not:** Bu story spec, `ready-for-dev` durumundadır. Implementasyon `bmad-dev-story` workflow'u ile yapılacaktır; BU YAZIDA `KOD YAZILMADI`.

---
story_id: S-FEA-01
story_key: "S-FEA-01"
title: "Deterministic Feature Engine Foundation"
epic: "E-FEA — Feature Engineering & Technical Indicators"
status: "ready-for-dev"
created: "2026-08-23"
updated: "2026-08-23"
author: "bm-create-story v1"
tags: [features, indicators, deterministic, stdlib-only, AD-22, CAP-1]
baseline_commit: "2fbf986 feat: add opportunity and model lifecycle contracts"
previous_story: "S-CON-02C"
next_story: "S-REG-01"
contract_version_preserved: "1.0.0"
---

# S-FEA-01 — Deterministic Feature Engine Foundation

## 1. Amaç ve Genel Bakış

**User Story (BDD):**  
> Bir FeatureEngine tüketicisi (strategy, regime veya AI modülü) olarak,  
> Verdiğim kapanmış canonical candle serisinden tekil deterministik FeatureVector elde etmek istiyorum,  
> Öyle ki AYNI candle input’u (10 tekrar) → AYNI feature output (aynı sorted temsil, aynı SHA-256),  
> Gelecekteki candle verisini (t+1…N) KULLANMAYAN,  
> run_mode / source_type branch’i OLMAYAN (CAP-1),  
> MeVeut AD-22 FeatureVector contract’ını DOLDURAN ve geriye doğru uyumlu bir feature katmanı olsun.

**Hedef:** S-CON-02A'da (AD-22) tanımlı mevcut `FeatureVector` + `LookbackWindowSpec` + `FeatureSchemaSpec` + `FEATURE_SCHEMA_REGISTRY` sözleşmelerini KULLANARAK (YENİ CONTRACT OLUŞTURMAYARAK) ilk gerçek feature engineering katmanını oluştur.

### Ön Koşullar (Mevcut System Under Test)
✅ S-RDH-01 (68) / S-RDH-02 (64) / S-PLN-01 (42) / S-CON-02A (104) / S-CON-02B (71) / S-CON-02C (93) = 442/442 PASS  
✅ `app/contracts/feature.py` mevcut ve AD-22 sözleşmelerini içeriyor (FeatureVector, LookbackWindowSpec, FeatureSchemaSpec, FEATURE_SCHEMA_REGISTRY, validate_feature_vector_features, register_feature_schema)  
✅ pyproject.toml `dependencies = []` — stdlib-only  
✅ CONTRACT_VERSION = "1.0.0" (this story de YOKSAYACAK — bump yapma)  
✅ Hard Safety: short yok, leverage yok, futures yok, gerçek exchange yok, API key yok (this story de bu sınırlar korunacak)

### Değişmez Mimari Kurallar (HİÇBİR KOŞULDA İHLAL EDİLEMEZ)
| Kural | Kaynak | Davranış |
|---|---|---|
| AD-22 FeatureVector flat dict | ARCHITECTURE-SPINE §AD-22 + CONTRACTS §3.7 | `features{}` NESTED YOK, dizi YOK; key `^[a-z][a-z0-9_]*$`; value `Decimal\|float\|int\|str\|None`; bool YASAK |
| CAP-1 Replay/Live Parity | SPEC §CAP-1 | Feature klasöründe `if run_mode == "live"`, `if source_type == "replay"` branch YOK. AST taraması 0 finding |
| AD-20 Determinism | ARCHITECTURE-SPINE §AD-20 | Aynı input → 10 kez aynı FeatureVector; `to_sorted_dict()` eşit; `schema_sha256()` eşit |
| AD-5 Data Quality Gate (partial) | ARCHITECTURE-SPINE §AD-5 | `strict_closed_only=True` modunda `candle.closed=False` (kısmi mum) feature hesaplamaya GİRMEZ → bu inputlar YA reject edilir YA feature değerleri `None` atanır, input_refs kanıtlanır |
| Hard Safety (v1) | PRD Hard Boundaries | short/lev>1/futures/network/credentials gerçek çağrı YOK — AST + static scan 0 finding |
| Look-ahead Bias (ZORUNLU) | User talebi + FR-043 | `Feature(t)` YALNIZCA `candles[≤t]` indexlerini kullanabilir. `candles[t+1]` veya sonrası → YASAK. AST tarayıcısı veya hesaplama sınırı HARD enforce. |

---

## 2. Mimari Uyum & Bağlam Devamlılığı (S-CON-02C Sonrası)

### Mevcut 7-Halka Corr/Caus Zincirine Feature Katmanı (INTEGRATION YOK — bu hikâyede SADECE contract seviyesi)

```
[CanonicalCandle → S-PLN-01 EventBus]
    ↘ input_refs[] + lookback_window + FeatureEngine (S-FEA-01)
        ↘ FeatureVector (AD-22)                    ← BU HİKÂYE: SOL 2 KOŞUL
            ↘ MarketRegime (S-REG-01)
                ↘ StrategyContext (AD-25)
                    ↘ StrategySignal (S-CON-02A)
                        ↘ OpportunityScore (S-CON-02C)
                            ↘ RiskDecision (S-CON-02B)
                                ↘ ... (4 halka daha S-CON-02B)
```

> Not: Bu hikâyede MarketRegime / StrategySignal ÜRETİLMEYECEK (OOS). Bu hikâyede SADECE:
> `List[CanonicalCandle] → FeatureEngine.calculate() → FeatureVector` TEK YÖNLÜ.

### Geliştirici Notları (S-CON-02C Lessons Learned Aktarımı)
1. **ULIDISH regex underscore:** Tüm 6 contract dosyasında `_ULIDISH_RE = r"^[A-Za-z0-9_\-]{8,}$"` (input_refs `[]` bu formatta olacak; feature.py L203-213 `_validate_ulidish_list` buna uygun — zaten var).
2. **Nested constructor scope:** Testte `pytest.raises(ContractSchemaError)` BLOĞUNDA nested dataclass yapıcılarını çağır (dışarıda çağırma).
3. **Determinism test:** `schema_sha256(instance)` ve `to_sorted_dict()` karşılaştır; `schema_sha256(dict)` YOK.
4. **Credential safety:** Hassas substrları `chr()` runtime concat yap; dosyada doğrudan string BULUNDURMA.
5. **pyproject deps=[]:** Yeni runtime dep EKLEME.

---

## 3. Dosya Yapısı (Kesin)

### 3.1 Yeni Dosyalar (Oluşturulacak)
| # | Mutlak Yol | Kapsam | Not |
|---|---|---|---|
| 1 | `app/features/__init__.py` | Public API export: `FeatureEngine`, `CandleView`, `SFEA01_FEATURE_VERSION`, `SFEA01_SCHEMA_SPEC` (sonuna ekle — sırasını koru) | Modül init |
| 2 | `app/features/engine.py` | Ana class: `FeatureEngine` + nested `CandleView` (veya contract candle reuse) + 7 indicator math + leakage guard + determinism + register SFEA01_SCHEMA_SPEC | 350-550 satır stdlib-only |
| 3 | `tests/features/test_sfea01_engine_happy.py` | H1+H2 AC (8+6 = 14 test): happy path, insufficient lookback, OHLCV normalize, provenance, lookback meta | ~200 satır |
| 4 | `tests/features/test_sfea01_ema_rsi.py` | H3 (8+8 = 16 test): EMA period/seed/insufficient; RSI Wilder/div-by-zero/insufficient | ~280 satır |
| 5 | `tests/features/test_sfea01_atr_vwap.py` | H4 (7+9 = 16 test): ATR true-range/Wilder; VWAP rolling/zero-volume; min bounds | ~240 satır |
| 6 | `tests/features/test_sfea01_mom_vol_volm.py` | H5 (7+6+7 = 20 test): momentum abs/pct; volatilite stdev; volume raw+ratio+std | ~260 satır |
| 7 | `tests/features/test_sfea01_determinism_cap.py` | H6+H7 (10+10+5+5 = 30 test): 10x determinism 10 indicator; CAP-1 AST scan; leakage guard HARD test; NaN/None handling | ~320 satır |
| 8 | `tests/features/test_sfea01_safety_regression.py` | H8 (12 test): credential; network; S-RDH-01/02; S-PLN-01; S-CON-02A/B/C 442 pass; QualityFlags(CAP-2); pyproject deps=[]; CONTRACT_VERSION 1.0.0 | ~280 satır |

**Toplam Yeni Test Tahmini:** 8 dosya → ~14+16+16+20+30+12 = **108 yeni test**.

### 3.2 DEĞİŞTİRİLECEK Dosyalar (2 adet — mevcut 442 regression BOZULMAYACAK)
| # | Mutlak Yol | Değişiklik | Not |
|---|---|---|---|
| 9 | `app/contracts/__init__.py` | **SONUNA** 3 yeni isim EKLE (ilk 71 isim SIRASI BOZULMAYACAK): `SFEA01_FEATURE_VERSION`, `SFEA01_SCHEMA_SPEC`, `FeatureEngine?` (Engine contract dışı ise `__init__.py` contract exportlarında YOK, sadece `app/features/__init__.py` dışarı export eder) | CONTRACT_VERSION = "1.0.0" KORU. __all__ len = 71 (contract) DEĞİŞMEZ (FeatureEngine contract DEĞİL — ayrı feature modülü) |
| 10 | `.tmp/srdh01_baseline_sha256.json` | **YALNIZCA** public sözleşme hashleri DEĞİŞTİYSE güncelle (eğer `app/contracts/__init__.py` içeriği değişmediyse → baseline 14 dosya hash SABİT KALIR) | .gitignore; commit ETME |

### 3.3 YAPILMAYACAK / KAPSAM DIŞI (OOS)
- ❌ Yeni canonical contract (FeatureVector zaten var — BU HİKÂYE YENİ CONTRACT OLUŞTURMAZ)
- ❌ Market Regime algorithm (S-REG-01)
- ❌ Trend/Momentum strategy engine (S-STR-01/02)
- ❌ OpportunityScore algorithm (S-AIS-01)
- ❌ AI/ML (S-AIS-02)
- ❌ Risk Engine / Kill Switch (E-RSK)
- ❌ Backtest / Paper Trading (E-BKT / E-PTR)
- ❌ Exchange / API / DB / Dashboard (E-API)
- ❌ Model training (E-MDL sonrası)

---

## 4. Özellik Detayları & Per-Feature Matematik Kuralları (TAM SPEC)

### 4.1 Genel Feature Engine Sözleşmesi

**Class:`FeatureEngine` (stdlib-only, typed dataclass veya normal class)**
```python
class FeatureEngine:
    feature_version: str          # "fea_01_v1" (SFEA01_FEATURE_VERSION sabiti)
    default_timeframe: str        # "1h" (test fixture default; ADN production KARAR DEĞİL)
    default_lookback: int         # 200 (fixture default; ADN değil)
    strict_closed_only: bool      # True: closed=False mumları REJECT; False: dahil et ama kanıtla

    # --- Public API (deterministic, side-effect FREE) ---
    def calculate(
        self,
        symbol: str,
        candles: list[CanonicalCandle],   # ← ZATEN mevcut (S-CON-02A ingest normalizer sonrası)
        timeframe: str | None = None,
        lookback: int | None = None,
    ) -> FeatureVector:
        """Takes sorted candles (oldest[0] .. newest[-1]=current_t).

        RAISES ContractSchemaError if:
          (a) len(candles) == 0
          (b) candles not strictly sorted by open_ts ascending
          (c) duplicate open_ts in candles
          (d) strict_closed_only=True AND any candle.closed is False
          (e) any candle has high < low OR open <= 0 OR close <= 0 OR volume < 0
        """

    # --- Per-indicator private helpers (called inside calculate) ---
    @staticmethod
    def _compute_ema(close: list[float], period: int) -> list[float | None]: ...
    @staticmethod
    def _compute_rsi(close: list[float], period: int) -> list[float | None]: ...
    @staticmethod
    def _compute_atr(high: list[float], low: list[float], close: list[float], period: int) -> list[float | None]: ...
    @staticmethod
    def _compute_vwap(high: list[float], low: list[float], close: list[float], volume: list[float], window: int) -> list[float | None]: ...
    @staticmethod
    def _compute_momentum(close: list[float], period: int) -> tuple[list[float | None], list[float | None]]:  # (abs, pct)
    @staticmethod
    def _compute_volatility(close: list[float], window: int) -> list[float | None]:  # std of returns, bps
    @staticmethod
    def _compute_volume_features(volume: list[float], window: int) -> tuple[list[float | None], list[float | None]]:  # (ratio, std_scaled)
```

### 4.2 SFEA01 FeatureVector Schema (register_feature_schema ile ZORUNLU KAYDEDİLECEK)

**`SFEA01_FEATURE_VERSION = "fea_01_v1"`**

**Zorunlu 12 Key (required_keys):**
| Key | Tip | Unit | Nullable? | Min | Max | Açıklama | Kaynak |
|---|---|---|---|---|---|---|---|
| `ema_14` | `float` | fiyat | YES (insufficient) | - | - | EMA(14) kapanış | H3 |
| `rsi_14` | `float` | 0-100 | YES (insufficient) | 0.0 | 100.0 | RSI(14) Wilder | H3 |
| `atr_14` | `float` | fiyat aralığı | YES | 0.0 (soft floor) | - | ATR(14) Wilder | H4 |
| `vwap_20` | `float` | fiyat | YES (insufficient + zero-vol) | - | - | VWAP rolling(20) | H4 |
| `mom_10_abs` | `float` | fiyat farkı | YES | - | - | Mom(10): close[t]-close[t-10] | H5 |
| `mom_10_pct` | `float` | % | YES | - | - | Mom(10) % change ×100 | H5 |
| `volatility_20_bps` | `float` | bps | YES | 0.0 (soft) | - | Returns std(window=20) ×10000 | H5 |
| `vol_ratio_20` | `float` | oran | YES | 0.0 (soft) | - | Vol[t] / mean(vol window 20) | H5 |
| `vol_std_20_scaled` | `float` | ölçeklenmiş std | YES | 0.0 (soft) | - | Std(vol window 20) / 1_000_000 | H5 |
| `close_raw` | `float` | fiyat | NO (mevcutsa always) | 1e-9 | - | Anlık close | H2/Happy |
| `high_raw` | `float` | fiyat | NO | 1e-9 | - | Anlık high | H2 |
| `low_raw` | `float` | fiyat | NO | 1e-9 | - | Anlık low | H2 |

> **Nullable Keys:** Eğer `t < lookback_required - 1` veya zero-vol/zero-loss → ilgili key = `None`. FEATURE_SCHEMA_REGISTRY nullable_keys listesine kaydedilecek.

### 4.3 Gösterge Matematik Detayları

### 4.3.1 EMA (H3 — Exponential Moving Average)
- **Formül (ZORUNLU):**
  ```
  alpha = 2.0 / (period + 1.0)
  sma_seed = statistics.mean( close[0 : period] )    // t in [0..period-1] → seed
  ema[period-1] = sma_seed
  for t in range(period, len(close)):
      ema[t] = alpha * close[t] + (1.0 - alpha) * ema[t-1]
  ```
- **Insufficient Lookback:** `len(close) < period` → ema_14 = None.
- **Period doğruluğu:** Test fixture period=14 (ADN production değil).

### 4.3.2 RSI (H3 — Wilder Smoothing Relative Strength Index)
- **Formül (ZORUNLU):**
  ```
  deltas[t] = close[t] - close[t-1]    // t >= 1
  gains[t]  = max(deltas[t], 0.0)
  losses[t] = max(-deltas[t], 0.0)
  avg_gain[period] = statistics.mean( gains[1 : period+1] )   // seed
  avg_loss[period] = statistics.mean( losses[1 : period+1] )  // seed
  for t in range(period+1, len(close)):
      avg_gain[t] = (avg_gain[t-1] * (period-1) + gains[t]) / period
      avg_loss[t] = (avg_loss[t-1] * (period-1) + losses[t]) / period
  if avg_loss[t] == 0.0:
      rsi[t] = 100.0          // ← zero denominator davranışı (NaN YOK)
  else:
      rs = avg_gain[t] / avg_loss[t]
      rsi[t] = 100.0 - (100.0 / (1.0 + rs))
  ```
- **Div-by-Zero:** `avg_loss == 0` → RSI = 100.0.
- **Insufficient:** `len(close) <= period` (t tohumlamak için period+1 kapanış gerekir) → None.
- **Range HARD enforve:** RSI her zaman [0.0, 100.0] (key_types + min/max FeatureSchemaSpec).

### 4.3.3 ATR (H4 — Average True Range Wilder)
- **True Range (ZORUNLU):**
  ```
  TR[t] = max(
      high[t] - low[t],
      abs(high[t] - close[t-1]),
      abs(low[t] - close[t-1]),
  )  // t >= 1 (t=0'da TR TANIMSIZ)
  ```
- **Wilder smoothing:** seed = mean(TR[1..period]), sonra `(ATR[t-1]*(period-1)+TR[t])/period`.
- **Insufficient:** `len(close) <= period` → None (TR seed requires period indices 1..period).
- **Min bound:** ATR >= 0.0 (FeatureSchemaSpec min_value_per_key["atr_14"] = 0.0).

### 4.3.4 VWAP (H4 — Rolling Window Volume Weighted Average Price)
- **Yaklaşım (ZORUNLU):** Rolling window (BU HİKÂYEDE cumulative session-start YOK — zaman dilimi bilinmiyor).
  ```
  typical_price[i] = (high[i] + low[i] + close[i]) / 3.0
  denom[t] = sum( volume[t - W + 1 : t + 1] )     // W = window (20 fixture)
  numer[t] = sum( typical_price[i] * volume[i]  for i in range(t-W+1, t+1) )
  if denom[t] == 0.0:
      vwap[t] = None           // ← zero-volume davranışı (NaN YOK)
  else:
      vwap[t] = numer[t] / denom[t]
  ```
- **Zero Volume:** denom = 0 → VWAP = None.
- **Insufficient:** `t < W - 1` → None.

### 4.3.5 Momentum (H5 — Absolute + Percent Change)
- **Abs:** `mom_abs[t] = close[t] - close[t - period]`
- **Pct:** `mom_pct[t] = (close[t] / close[t - period] - 1.0) * 100.0`
- **Insufficient:** `t < period` → None.
- **Period:** 10 (test fixture default; production ADN değil).

### 4.3.6 Volatility (H5 — Rolling Standard Deviation of Returns)
- **Returns:** `ret[t] = (close[t] / close[t-1]) - 1.0`, t>=1
- **Std:** `statistics.stdev(ret[t-W+1 : t+1])` (sample std; ddof=1). W=20.
- **Scale to bps:** `volatility_bps = stdev * 10000.0`
- **Annualization:** **OPEN DECISION** (ADN-013). Bu hikâyede YOK — sadece bps per window.
- **Insufficient:** `t < W` → None (çünkü ret[1..W] = W tane return gerekir; stdev requires en az 2 değer).

### 4.3.7 Volume Features (H5 — Ratio + Scaled Std)
- **Ratio:** `vol_ratio[t] = volume[t] / statistics.mean(vol_window)`; if mean==0 → 0.0
- **Std Scaled:** `vol_std_scaled[t] = statistics.stdev(vol_window) / 1_000_000.0`; if len(vol_window)<2 → 0.0
- **Window:** 20 (fixture default).
- **Insufficient:** `t < W-1` → None.

### 4.4 Input Provenance & LookbackWindowSpec (H2/H6 — ZORUNLU)
- `lookback_window = LookbackWindowSpec(count=actual_used_lookback, timeframe=timeframe)`  
  (actual_used_lookback = max(ema.p, rsi.p, atr.p, vwap.W, mom.p, vol.W, volm.W) = **200** default veya max(14,14,14,20,10,20,20) = **20** eğer lookback=None ise hangisi — AÇIK: engine kendi iç max indicator period W = max(14,14,14,20,10,20,20) = 20'dir; ancak kullanıcı `lookback=200` verirse bu kullanılır ve LookbackWindowSpec.count = lookback OLUR (büyük olan).
- `input_refs = [candle_id for candle_id in sorted(candles[i].candle_id for i in (.. actually used lookback index range))]`  
  (KANIT: Yalnızca kullanılan mumların ULID'leri input_refs'e yazılır — gelecekteki mumlar KESİNLİKLE YOK.)
- `FeatureVector.input_refs.sort()` KULLANILMAZ (ZORUNLU: chronological order korunur ama SHA-256 için `to_sorted_dict()` yine de sıralar).

### 4.5 Look-ahead Bias Guard (H7 — EN ZOR KURAL)

**İki Katmanlı Enforce:**
1. **Runtime Index Boundary:** `_compute_*` static helper'ları yalnızca `close[0..t]`, `high[0..t]`, `low[0..t]`, `volume[0..t]` kullanır. İçeride `for t in range(len(close))` ve alt limitler `t-period >= 0` kontrolleriyle Yalnızca geriye doğru endeks.
2. **Test Layer (ZORUNLU):** H7 AST tarayıcısı: `app/features/engine.py` içinde `[t+1]`, `[t+2]`, `future`, `next_candle` gibi string/AST Subscript patternleri aranır. 0 finding gerek.

---

## 5. Acceptance Criteria (42/42 — H1-H8)

### H1: Feature Engine Architecture & Public API (9 AC) — C01–C09
| Kod | Verilmemiş (Given) | Ne Olur (When) | Sonuç (Then) |
|---|---|---|---|
| C01 | 50 kapalı mum (sıralı), symbol, timeframe=1h | FeatureEngine().calculate() çağrılır | FeatureVector DÖNER, ContractSchemaError YOK |
| C02 | 0 mum | calculate() çağrılır | ContractSchemaError RAISE ("candles empty") |
| C03 | 20 mum ama open_ts göre ters sıralı (desc) | calculate() | ContractSchemaError RAISE ("candles not sorted ascending by open_ts") |
| C04 | 20 mum ama 2 aynı open_ts (duplicate) | calculate() | ContractSchemaError RAISE ("duplicate open_ts") |
| C05 | strict_closed_only=True + 1 mum closed=False (kısmi) arada | calculate() | ContractSchemaError RAISE ("closed=False not allowed in strict mode") |
| C06 | Mumda high=50 low=55 (high<low) | calculate() | ContractSchemaError RAISE ("invalid OHLC: high<low") |
| C07 | FeatureEngine sınıfı import edilir | Static attribute feature_version kontrol | feature_version == "fea_01_v1" (SFEA01 sabiti) |
| C08 | FeatureEngine import + `register_feature_schema(...)` çağrılır (import-time) | `FEATURE_SCHEMA_REGISTRY["fea_01_v1"]` kontrol | Registry'de var, FeatureSchemaSpec required_keys 12 key içeriyor |
| C09 | calculate() sonrası FeatureVector.validate_against_registry() çağrılır | Validation reasons list | Boş ([]) → AD-22 şema uyumlu |

### H2: OHLCV Normalization/Validation + Provenance/Lookback (7 AC) — C10–C16
| Kod | Given | When | Then |
|---|---|---|---|
| C10 | 200 mum (fixture) | calculate(candles, lookback=200) | fv.lookback_window.count == 200, timeframe == "1h" |
| C11 | aynı fixture, lookback=None varsayılan | calculate() | lookback_window.count == max(W) = 20 veya 200 (açık seçim: max indicator period = 20) |
| C12 | 200 mumluk input | fv.input_refs kontrol | len(input_refs) == min(200, len(candles)) veya == actual_lookback; her input ULIDISH formatta (underscore dahil) |
| C13 | mum.candle_id `["CAND_000" .. "CAND_200"]` | fv.input_refs[0] / [-1] | `input_refs[0] == "CAND_000"` (en eski) ve `input_refs[-1] == "CAND_199"` (mevcut t) — gelecekteki CAND_200+ YOK |
| C14 | FeatureVector.null_count (None ise otomatik doldurulur) | `len(candles)=14` (insufficient for 20 VWAP vb) | fv.null_count == actual number of None features |
| C15 | FeatureVector fv1 = calculate(candles); fv2=calculate(candles) | `fv1.to_sorted_dict() == fv2.to_sorted_dict()` | True |
| C16 | `fv.validate_against_registry()` + min bound (low_raw high_raw) | `close_raw < 1e-9` veya `high_raw < close_raw` | Registry validation reason list NON-EMPTY |

### H3: EMA + RSI Indicators (10 AC) — C17–C26
| Kod | Given | When | Then |
|---|---|---|---|
| C17 | period=14, close = [10]*14 + [10,10] (16 eleman, sabit) | _compute_ema(close, 14) son 2 değer | ema[t=13]=10.0 (sma_seed), ema[t=14]=10.0, ema[t=15]=10.0 → sabit correct |
| C18 | _compute_ema(close[0:10], 14) len(close)<period | return | ema[9] = None (insufficient) |
| C19 | EMA serisi: close = linear 1,2,3,4,...,500 (500 nokta). alpha=2/15. | t = 15 (seed sonrası 1. adım) | hand-verify: ema[13] = mean(1..14)=7.5; ema[14]=(2/15)*15+(13/15)*7.5=8.5; FV ema_14 == pytest.approx(8.5) |
| C20 | RSI period=14, close = sürekli artan (deltas hep +) 30 nokta | son RSI | avg_loss[t]=0 → RSI=100.0 (zero denominator behavior test) |
| C21 | RSI period=14, close = sürekli AZALAN (deltas hep -) 30 nokta | son RSI | avg_gain=0 → rs=0 → RSI = 0.0 (sınır test) |
| C22 | RSI len(close)=10 (period=14'den küçük) | _compute_rsi()[9] | None (insufficient) |
| C23 | RSI 30 dalgalı (alternans +/-) fixture | RSI son değer | RSI ∈ [0,100]; schema validation min=0/max=100 reason=[] |
| C24 | FV sonucu: rsi_14 == 150.0 (aşırı) yapay bir FeatureVector üret | validate_against_registry() | reasons NON-EMPTY: "rsi_14 value=150 > max=100" |
| C25 | FV sonucu: rsi_14 == -5.0 | validate_against_registry() | reasons NON-EMPTY: "rsi_14 value=-5 < min=0" |
| C26 | EMA+RSI fixture 10 tekrar hesap | 10 kez schema_sha256(fv) digest | Hep AYNI (H6 determinism subset) |

### H4: ATR + VWAP Indicators (8 AC) — C27–C34
| Kod | Given | When | Then |
|---|---|---|---|
| C27 | ATR: high[t]=50 low[t]=40 close[t-1]=45 → true_range[t] = max(10, abs(50-45)=5, abs(40-45)=5) = 10 | _compute_atr tek true_range hesaplaması | TR[t]=10 (doğrulama) |
| C28 | ATR period=14; high/low/close = 20 nokta. t<14 (10 eleman) | atr[9] | None (insufficient) |
| C29 | ATR 30 nokta uniform high=50 low=40 (TR hep 10) | tohumlamadan sonra ATR | ATR → 10.0收敛, approx(10.0, rel=1e-3) |
| C30 | ATR min bound: atr_14 = -1.0 olan yapay FV üret | validate_against_registry() | reasons NON-EMPTY: atr_14 < 0 |
| C31 | VWAP window=20; volume = [0]*100 + [100]*1 → denom = 0 for ilk 20 window | vwap[19] = None | True (zero-vol behavior) |
| C32 | VWAP window=20; typical=50, volume=100 hep → denom=20×100=2000; numer=20×(50×100)=100000; VWAP=50 | t=50 VWAP | VWAP == pytest.approx(50.0) |
| C33 | VWAP window=20; 10 mum (insufficient) | vwap[9] | None |
| C34 | VWAP + ATR fixture 10x calculate | 10 kez schema_sha256(fv) | Hep aynı |

### H5: Momentum + Volatility + Volume Features (9 AC) — C35–C43
| Kod | Given | When | Then |
|---|---|---|---|
| C35 | Mom abs period=10; close[t]=110, close[t-10]=100 | mom_10_abs[t] | = 10.0 approx |
| C36 | Mom pct period=10; aynı ↑ değerler | mom_10_pct[t] | = (110/100 -1)*100 = 10.0 approx |
| C37 | Mom t=5 (period=10'dan küçük) | mom_10_abs[5] = None | True (insufficient) |
| C38 | Volatility window=20; close = 1,2,1,2,1,2,... (alternating); returns=±1/x | 30 nokta sonu stdev hesap. volatility_bps | ≥ 0.0 (min bound) ve sabit serie deterministik |
| C39 | Volatility t=10 (window=20'den küçük) | volatility_20_bps[t] = None | True |
| C40 | Volume ratio window=20; volume = 1000 hep (mean=1000, anlık=1000) | vol_ratio_20[t] | = 1.0 approx |
| C41 | Volume ratio mean=0 (tüm volume=0 window 20) | ratio | = 0.0 (zero mean guard) |
| C42 | Volume std t < W-1 (insufficient) | vol_std_20_scaled[t] | None |
| C43 | Mom+Vol+Volm 10x hesap fixture | schema_sha256 ×10 | Hep aynı (subset H6) |

### H6: CAP-1 Parity + Determinism + Schema Registry (6 AC) — C44–C49
| Kod | Given | When | Then |
|---|---|---|---|
| C44 | `app/features/` klasör kaynak kodu AST taraması (tree walk) | NodeVisitor: run_mode, source_type kelimeleri + If node test stringleri | 0 occurrence → CAP-1 parity compliant |
| C45 | Büyük fixture (200 mum 1h) 10 kez ayrı Python subprocess/çağrı | 10 kez calculate → 10 kez fv.to_sorted_dict() JSON string | Tümü == (string eşitliği) |
| C46 | Aynı fixture C45 | 10 kez fv.schema_sha256() | 64 hex char HEP AYNI |
| C47 | 12 required_key: "ema_14","rsi_14","atr_14","vwap_20","mom_10_abs","mom_10_pct","volatility_20_bps","vol_ratio_20","vol_std_20_scaled","close_raw","high_raw","low_raw" — eksik anahtar olan yapay FeatureVector üret | validate_against_registry() | reasons: "missing required keys: [...]" NON-EMPTY |
| C48 | 13. ekstra key "foo_bar" olan yapay FV (allowed_keys sadece 12 + 2 opsiyonel olsun) | validate_against_registry() | reasons NON-EMPTY: "extra forbidden keys: ['foo_bar']" |
| C49 | feature_version="fea_01_v1" → required_keys 12 | register_feature_schema() çağrısı sonrası registry lookup | spec.required_keys len = 12; spec.key_types hepsi Decimal/float/int/str; none bool |

### H7: Look-ahead Bias + NaN/Invalid Handling (5 AC) — C50–C54? (eksik 1 → C54 son)
| Kod | Given | When | Then |
|---|---|---|---|
| C50 | `app/features/engine.py` static AST tarayıcı (NodeVisitor): Subscript içinde `[t+1]`, `[t+2]`, `[i+1]` if i dış döngü ise; ayrıca "future", "next_candle" | Tüm kaynak | 0 finding (leakage YOK) |
| C51 | FeatureVector içinde NaN (float('nan')) bulunan değer → bu None yerine konursa? | validate_against_registry() veya _validate_features_flat | `ContractSchemaError` RAISE (NaN primitive forbidden veya nan check) — AÇIK: FeatureValue NaN ise yazılımda `None` ATAR; NaN YAPMAYIZ. Eğer biri NaN koyarsa isinstance(float) True ama isnan → ZORUNLU test: NaN detect ve RAISE. |
| C52 | close[t] = 0 (geçersiz fiyat) veya close[t] = -5 (negatif) mum | calculate() | ContractSchemaError (price <= 0 validation) veya OHLCV validation içinde high_low |
| C53 | volume = -10 (negatif volume) | calculate() | ContractSchemaError: "volume < 0" |
| C54 | 12 indicator key 10 fixture için 10x hesap → her biri hand-verified formül match | Test parametrize 12×10 (120 assert) | HEP FORMÜL doğruluğu (parametrize test) |

> Düzeltme: H7 C54 sonrası = H8 tamamlanacak.

### H8: Safety / Regression / CAP-2 Quality Envelope + Regression Commitment (7 AC) — C55–C61
| Kod | Given | When | Then |
|---|---|---|---|
| C55 | `app/features/` klasöründe AST tarayıcı + static: forbidden imports (pandas/numpy/ta-lib/ccxt/pydantic/sklearn/xgboost...) | tree walk Import/ImportFrom node isimleri | 0 finding — stdlib-only |
| C56 | Security C44 benzer: credential scanner (S-RDH-02 tarayıcıları) features klasörüne uygula | hassas kelime string AST Constant | 0 finding; varsa `chr()` concat zorunlu |
| C57 | CAP-2: features modülünde QualityFlags nesnesi doğrudan assignment (mutate) AST tarayıcısı | Assign target Attribute quality_flags | 0 mutate; sadece read-only pass |
| C58 | `python _run_pytest.py tests/ -q --no-header` TÜM TÜM | pytest exit code | Exit 0; TOPLAM ≥ 442 + 108 = ≥ 550 PASS |
| C59 | Regression sayıları (eski): S-RDH-01 68, S-RDH-02 64, S-PLN-01 42, S-CON-02A 104, S-CON-02B 71, S-CON-02C 93 | pytest subset `tests/contracts` + `tests/failure` + `tests/pipeline` | TOPLAM 442/442 PASS (BOZULMADI) |
| C60 | pyproject.toml L4 dependencies + CONTRACT_VERSION import sonucu | Inline check | dependencies == []; CONTRACT_VERSION == "1.0.0" |
| C61 | Eski SRDH-01 baseline (.tmp/srdh01_baseline_sha256.json 14 pipeline source) | F2/AC04 test (hash karşılaştırması) | Değişen contract yoksa → 14/14 hash match. Değişen VARSA → sadece değişen dosya hashi güncellenmeli ve o test PASS |

> **TOPLAM AC:** H1(9)+H2(7)+H3(10)+H4(8)+H5(9)+H6(6)+H7(5)+H8(7) = **61 AC** (Hedef ≥35 → %174 ASILDI).

---

## 6. Definition of Done (13/13 — ZORUNLU)

| DoD # | Açıklama | Doğrulama |
|---|---|---|
| DoD-01 | 61 AC 100% PASS (0 FAIL) | Tüm testler C01-C61 H1-H8 PASS |
| DoD-02 | Mevcut 442 regression BOZULMADI | S-RDH-01/02, S-PLN-01, S-CON-02A/02B/02C = 442/442 PASS |
| DoD-03 | Toplam test ≥ 550 PASS (442 + ≥108 yeni test) | pytest çalıştırma çıktısı ≥ 550 |
| DoD-04 | Yeni runtime dependency 0 (stdlib-only) | `pyproject.toml dependencies = []`; imports AST tarayıcı 0 pandas/numpy/ta/... |
| DoD-05 | CONTRACT_VERSION = "1.0.0" NO BUMP; `__init__.py` ilk 71 isim SIRASI KORUNUR | Import + getattr 71 isim + len(__all__) = 71 |
| DoD-06 | 2 yeni klasör: `app/features/` + `tests/features/`; FeatureEngine public export edilir | LS klasör kontrol |
| DoD-07 | CAP-1 `run_mode/source_type` if/else branch 0 finding | AST tarayıcı C44 0 match |
| DoD-08 | AD-20 Determinism 10x: 7 indicator fixture 10 kez → schema_sha256 AYNI | C45/C46 + per-indicator 10x (H3/H4/H5 C26/C34/C43) |
| DoD-09 | Look-ahead bias 2 katman 0 finding: (a) AST leakage tarayıcısı (b) min bound/range dışı formül | C50 0 match + C54 hand formula |
| DoD-10 | Zero-denominator (RSI avg_loss=0, VWAP denom=0, vol mean=0) DAVRANIŞLARI AÇIK ve TEST EDİLDİ (NaN YOK — sabit değer veya None) | C20 (RSI 100), C31 (VWAP None), C41 (ratio 0.0) PASS |
| DoD-11 | CAP-2 QualityFlags mutate 0; SFEA01 feature_version registry'de doğrulandı; 12 required_key min/max doğruluğu | C57 0 match + C08/C49 PASS |
| DoD-12 | Hard Safety (S-RDH-02) — short/lev>1/futures/network/credentials 0 occurrence; credential chr concat if needed | C56 0 finding + S-RDH-02 64/64 PASS |
| DoD-13 | `FeatureVector.feature_version` = `SFEA01_FEATURE_VERSION` = "fea_01_v1" (TUTARLI); lookback_window + input_refs ZORUNLU doldurulur; `null_count` ya otomatik ya declared = actual | C07 + C09 + C10/C12/C14 PASS |

---

## 7. Test Planı (6 yeni dosya + ≥108 yeni method)

| # | Test Dosyası | Test Sayısı | AC Kapsamı |
|---|---|---|---|
| T1 | `test_sfea01_engine_happy.py` | 16 (C01-C09 9 + C10-C16 7) | H1 Happy/Sorted/Dup/Strict/OHLCV + H2 Provenance/Lookback |
| T2 | `test_sfea01_ema_rsi.py` | 20 (C17-C26 10 + 10 parametrize edge) | H3 EMA (insufficient/alpha/linear), RSI (zero-den/neg-bound/range) |
| T3 | `test_sfea01_atr_vwap.py` | 18 (C27-C34 8 + 10 parametrize zero-vol/insufficient/TR varyantları) | H4 ATR true-range/Wilder/min-bound; VWAP rolling/zero-vol/insufficient |
| T4 | `test_sfea01_mom_vol_volm.py` | 22 (C35-C43 9 + 13 parametrize abs/pct/window/std/ratio) | H5 mom abs/pct; vol bps/std; vol ratio/std |
| T5 | `test_sfea01_determinism_cap.py` | 24 (C44-C49 6 + C50-C54 5 leakage + 10x 3 fixture + 3 invalid) | H6/H7: CAP-1 AST, 10x determinism 3 fixture, leakage AST, NaN/-price/-vol, 12-key registry |
| T6 | `test_sfea01_safety_regression.py` | 18 (C55-C61 7 + 4 credential/network + 7 pyproject/CV/__all__/hash) | H8 safety, forbidden imports, 442 regression call, dependencies, version, baseline hash |
| **TOPLAM** | **6 dosya** | **≥ 118 yeni test** | H1-H8 61 AC kapsar + 57 parametrize/edge case |

### 7.1 Regression Taahhüdü (ZORUNLU)
- `tests/failure/test_no_credentials.py`: S-RDH-02 64/64 PASS olmalı.
- `tests/pipeline/test_hash_pipeline_srdh01.py`: S-RDH-01 68/68 PASS olmalı (baseline hash gerekiyorsa güncellenecek — ama sadece contract değişirse).
- `tests/contracts/`: S-CON-02A 104, S-CON-02B 71, S-CON-02C 93 TOPLAM 268/268 PASS.
- `tests/pipeline/normalizer`: S-PLN-01 42 PASS.
- `pytest tests/` → TOPLAM ≥ 550 PASS.

---

## 8. Open Decisions (BU HİKÂYEDE KESİNLİKLE ÜRETİLMEYECEK — AÇIK KALACAK)

| ADN # | Açık Konu | Neden Açık | Hangi Hikâyede Çözülür |
|---|---|---|---|
| ADN-013 | Volatility annualization çarpanı (sqrt(252*24)? per timeframe?) | v1 MVP için window-bps yeterli | S-FEA-02 (ekstra indikatörler) |
| ADN-014 | Kesin timeframe seti (1m/5m/15m/1h/4h/1d?) — bu hikâyede fixture 1h ONLY | production zaman dilimi kararı operasyonel | E-STR-01 (plugin interface) veya ayrı S-FEA-03 |
| ADN-015 | Kesin period değerleri (EMA 14/20/50/200 hepsi mi? Bu hikâye sadece 14/10/20 tek tek) | Strategy plugin ihtiyacına göre genişletilir | S-FEA-02 |
| ADN-016 | VWAP: rolling window mi cumulative session start mı? | session start belirlemek için exchange schedule bilgisi gerekir | S-FEA-02 veya S-RDH-03 (veri toplama sonrası) |
| ADN-017 | `strict_closed_only` default value (True/False)? Bu hikâyede True = fixture only | production: replay closed=True; live closed=False olabilir — CAP-1 branch YOK ancak parametre dışarı verilir | S-STR-01 plugin interface |
| ADN-018 | FeatureVector ek field (correlation_id / causation_id şu anda contract'ta YOK — AD-22'ye eklemek contract_version bump ister mi?) | bump 1.0.0 korumalı → bu hikâyede FEATURE_VERSION="fea_01_v1" ile kanıtlar input_refs ve lookback_window üzerinden | S-CON-03 (opsiyonel) veya ayrı story |

---

## 9. Safety & Sınırlar (TEKRAR)

1. ✅ **Futures yok** — feature kodunda sözleşmede related concept YOK.
2. ✅ **Leverage yok** — feature'lar leverage kavramı içermez.
3. ✅ **Short yok** — feature fiyat yönü içerir ama short/long kavramı YOK (strategy'de).
4. ✅ **Gerçek exchange / emir yok** — feature SADECE fiyat/volume matematik; network call YOK.
5. ✅ **API key yok** — credential taramaları 0 finding.
6. ✅ **Gerçek para yok** — tüm feature'lar sayısal değer, para aktarımı YOK.
7. ✅ **DB yok** — feature engine PURE function; DB çağrısı YOK.
8. ✅ **ML / AI yok** — bu hikâyede SADECE belirleyici (deterministic) matematik.
9. ✅ **Strategy/risk/backtest/paper yok** — bunların hepsi OOS.

---

## 10. Çıktı (Deliverables) Checklist (Hikâyenin Geliştirici Sonunda Üreteceği)

- [ ] `app/features/__init__.py` var, `FeatureEngine`, `SFEA01_FEATURE_VERSION` export eder.
- [ ] `app/features/engine.py` var, `FeatureEngine` + 7 `_compute_*` static + `SFEA01_SCHEMA_SPEC` registry kaydı.
- [ ] `tests/features/` 6 dosya; 118+ yeni test methodu.
- [ ] `app/contracts/__init__.py` ilk 71 isim SIRASI BOZULMADI; CONTRACT_VERSION="1.0.0" KORUNDU.
- [ ] `pyproject.toml dependencies = []` DEĞİŞMEDİ.
- [ ] `.tmp/srdh01_baseline_sha256.json` (eğer contract hash değişirse) güncellendi.
- [ ] `pytest tests/` ≥ 550 PASS; 442 regression 442/442 PASS.
- [ ] 61/61 AC PASS; 13/13 DoD PASS.
- [ ] GIT COMMIT YOK (kullanıcı S-CON-02C sonrası açıkça YASAKLADI — devam ediyor).
- [ ] Sonraki hikâyeye (S-REG-01) GEÇİŞ YOK — sadece bu story.

---

## 11. Implementation Readiness Assessment (Okuma Hazırlığı)

| Öğe | Hazır | Not |
|---|---|---|
| 61 AC (≥35 hedefi) | ✅ %174 asıldı | Ayrıntılı parametrize plan |
| 13 DoD (≥12 hedefi) | ✅ | Tek tek doğrulanabilir |
| ≥108 yeni test planı | ✅ 118 planlandı | 6 dosya |
| Per-feature math ZORUNLU formül | ✅ 7 gösterge formül | Seed/Wilder/zero-denom/zero-vol AÇIK |
| AD-22 mevcut FeatureVector reuse | ✅ | Yeni contract YOK (doğru) |
| Look-ahead guard 2 katman | ✅ | AST + index sınırı |
| CAP-1 parity zorunlu | ✅ | AST tarayıcı planı |
| Open Decisions 6 başlık | ✅ | Production sahte kesinlikten KAÇINILDI |
| Regression commitment 442 | ✅ | H8 C59/C60/C61 explicit |
| pyproject deps=[] koruma | ✅ | C55 forbidden import scan |
| Dosya yapısı 8 yeni + 2 değişiklik | ✅ | Kesin yollar |

**Genel Readiness:** ✅ **Ready-for-dev** (bu hikâye artık geliştiricinin implement etmesi için yeterli bağlam, bağlayıcı kural, test planı ve matematik tanımı içeriyor).

---

## 12. Kullanıcı Yasakları & Sonrası (TEKRAR — HİÇBİRİ İHLAL EDİLEMEZ)

1. ❌ **Git commit oluşturma.** — FeatureEngine implementasyonundan SONRA da YOK. (Kullanıcı 3 kural: NO COMMIT / NEXT STORY / NO TRADING)
2. ❌ **Sonraki hikâyeye geçme.** — Bu hikâyeden sonra S-REG-01 OKUNMAYACAK, SADECE S-FEA-01 implement edilecek veya bu spec hazırlık sonrası KULLANICI onayı beklenecek.
3. ❌ **Gerçek trading/execution/network.** — Bu hikâyede OOS.

---

## 13. Completion Record (Spec Creation)

### 13.1 Spec Summary
- **Yaratılan:** `_bmad-output/implementation-artifacts/S-FEA-01-deterministic-feature-engine-foundation.md` (bu dosya)
- **Status:** ready-for-dev
- **Önceki hikâye:** S-CON-02C (442/442 PASS)
- **Sonraki (bekleyen ama GEÇİŞ YOK):** S-REG-01

### 13.2 Metrics
- **AC sayısı:** 61 (hedef ≥35)
- **DoD sayısı:** 13 (hedef ≥12)
- **Planlanan yeni test:** ≥118 (hedef ≥30)
- **Planlanan regression:** 442/442 KORUNACAK
- **Toplam hedef test:** ≥ 560 PASS
- **Yeni runtime dep:** 0 (dependencies=[] KORUNUR)
- **Yeni contract:** 0 (FeatureVector zaten mevcut — doğru)
- **Open Decisions:** 6 (ADN-013…018)

### 13.3 Lessons Learned (S-CON-02C → bu spec)
1. Fixture alan isimleri mevcut contract (S-CON-02A/B/C) fixture KANONİK isimleriyle %100 aynı olmalı — spec'te yazılan "qty_base" yerine contract alan "base_qty" ise doğrudan contract fixture'ı 1:1 kopyala.
2. Determinism test: 10 kez sha256 + dict eşitliği — iki yöntem de uygulanmalı.
3. Nested typed constructor `pytest.raises` BLOĞUNDA çağrılır.
4. Credential substrs testte `chr()` runtime concat — global tarayıcı false-positive 0.
5. ULIDISH regex underscore içermeli — input_refs `[]` bu format.

### 13.4 Exit Criteria (Spec creation for bmad-create-story)
- [x] Referans dokümanlar okundu (PRD/ARCHITECTURE/SPEC/CONTRACTS/EPICS + 6 hikâye)
- [x] FeatureVector mevcut contract analyzed
- [x] Per-feature math 7 gösterge + 2 leakage guard net
- [x] H1-H8 61 AC yazıldı
- [x] 13 DoD yazıldı
- [x] Test planı 6 dosya ≥118 test
- [x] Open Decisions 6 başlık — SAHTE kesinlikten KAÇINILDI
- [x] Regression commitment 442 explicit
- [x] Dosya yapısı kesin
- [x] Implementation readiness = Ready-for-dev

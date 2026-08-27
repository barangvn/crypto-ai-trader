---
story_id: "S-OPP-01"
story_key: "S-OPP-01"
title: "Deterministic Opportunity Scoring Engine (Net-of-Cost, AD-9/AD-20/CAP-1/CAP-2/CAP-3 Pure)"
epic: "E-AIS — Opportunity & AI Scoring (Epic 8)"
status: "ready-for-dev"
created: 2026-08-26
updated: 2026-08-26
author: "bmad-create-story v1"
tags: [opportunity, scoring, net_of_cost, deterministic, explainable, AD-9, AD-20, CAP-1, CAP-2, CAP-3, long_only, v1, stdlib_only]
baseline_commit: "a471a6e feat: implement trend and momentum strategy engine"
previous_story: "S-STR-01"
next_story: "S-RSK-01 (Risk Engine — Out of Scope bu hikâyede)"
contract_version_preserved: "1.0.0"
contracts_used:
  - "OpportunityScore (app/contracts/opportunity.py) — S-CON-02C v1, YENİ CONTRACT YOK"
  - "StrategySignal (app/contracts/strategy.py) — S-STR-01 str_01_v1 output"
  - "FeatureVector (app/contracts/feature.py) — S-FEA-01 fea_01_v1 12-key"
  - "MarketRegime (app/contracts/regime.py) — S-REG-01 AD-8 6-state + confidence + 6 scores"
  - "QualityFlags (app/contracts/quality.py) — S-CON-02A/B/C shared frozen, 7 bayrak"
  - "InMemoryTypedEventBus (app/platform/event_bus.py) — S-PLN-01 typed bus, publish test"
test_baseline_count: 1265
test_baseline_passed: 1265
test_baseline_regression_breakdown:
  S-RDH-01: 68
  S-RDH-02: 64
  S-PLN-01: 42
  S-CON-02A: 104
  S-CON-02B: 71
  S-CON-02C: 93
  S-FEA-01: 120
  S-REG-01: 302
  S-STR-01: 401
scorer_version_story_default: "opp_01_v1"
opportunity_policy_version_default: "opp_policy_v1.0.0"
runtime_dependencies_new_allowed: 0
v1_hard_boundary_long_only: true
new_contract_allowed: false
---

# S-OPP-01 — Deterministic Opportunity Scoring Engine (Net-of-Cost, AD-9/AD-20/CAP-1/CAP-2/CAP-3)

## 1. Amaç ve Genel Bakış

**User Story (BDD):**
> Bir Opportunity Scoring tüketicisi (Risk Engine, Portfolio Simulator, AD-9 downstream bağımsız modüller) olarak,
> Sadece 3.5 adet typed girdi verildiğinde:
>   1. **StrategySignal** (S-STR-01 çıktısı; Trend veya Momentum, long/flat/hold, signal_strength [0,1], confidence [0,1])
>   2. **FeatureVector** (S-FEA-01 12-key fea_01_v1, RSI/EMA/VWAP/MOM/VOL/SPREAD)
>   3. **MarketRegime** (S-REG-01 6-state AD-8, bull/bear/sideways/hv/lv/tu + regime_score + confidence)
>   3.5. **MarketCostAssumptions** (frozen helper, fee/slippage/spread/latency defaults — fixture override edilebilir, production kalıcı karar DEĞİL)
> **Deterministik, açıklanabilir, net-of-cost duyarlı `OpportunityScore`** (S-CON-02C v1, mevcut contract — YENİ CONTRACT YOK) üretmek istiyorum,
> Öyle ki:
> - 12 skor bileşeni (raw → confidence → gross edge → fee → slippage → spread → latency → net edge → cost multiplier → regime adj → strategy adj → final score) TEK TEK formül ile tanımlı ve HER BİRİ AYRI TEST EDİLEBİLİR,
> - AYNI girdi 10 TEKRAR → AYNI OpportunityScore (aynı sorted dict, aynı SHA-256) (AD-20),
> - `OpportunityScore.correlation_id` = `StrategySignal.correlation_id` (SABİT, tüm zincirde),
> - `OpportunityScore.causation_id` = `StrategySignal.signal_id` (parent event id),
> - Confidence = StrategySignal confidence + Regime confidence + Quality etkisi birleşimi (açıklanabilir),
> - 7 kalite bayrağı (stale/degraded/dup/missing/out_of_order/invalid/quarantined) → OKUNUR, MUTATE EDİLMEZ, 0 VALIDATOR CALL (CAP-2),
> - QualityFlags `invalid` veya `quarantined` → **güvenli davranış**: `actionable=false` + skor düşük (0.15 ceiling) + reject_reason eklenir,
> - 6 rejim (AD-8) → deterministic regime adjustment ağırlık matrisi (formül açık),
> - 2 strateji (Trend / Momentum) → strategy id & version OpportunityScore'de KORUNUR (strategy_ref alanında),
> - Explainability: 6 zorunlu açıklama alanı (score_components, component_weights, dominant_factors, cost_breakdown, regime_evidence, strategy_evidence) → DETERMINISTIC SORTED ORDER,
> - `app/opportunity/` klasör kaynak kodunda `if run_mode` / `if source_type` BRANCH YOK (CAP-1),
> - NO network / NO DB / NO FS / NO exchange / NO credential / NO short / NO leverage / NO futures / NO real order / NO RiskDecision / NO PaperOrder (SAFETY + OOS),
> - `pyproject.toml dependencies = []` DEĞİŞMEZ, stdlib-only, 0 yeni runtime dep.

### Hedef
Mevcut **OpportunityScore** contract (`app/contracts/opportunity.py`, S-CON-02C v1) **DEĞİŞTİRİLMEDEN** (hiçbir public alan/import/enum/contract_version **DEĞİŞMEZ**), 1 saf (pure) Opportunity Scorer modülü + 1 frozen defaults helper (MarketCostAssumptions + ScoringWeights) oluştur.

**Bu hikâyede SADECE:** `StrategySignal × FeatureVector × MarketRegime × CostAssumptions → OpportunityScore` yönünde (tek yönlü deterministik fonksiyon).
**Hiçbir şekilde:** RiskDecision / PaperOrder / PaperFill / Fill Model / Backtest / Position / Portfolio üretimi YOK (OOS).
**Hiçbir şekilde:** Production eşiklerinin "optimal" olduğu IDDİA EDİLMEZ. Fixture defaults (test) ile production defaults (frozen) AYRI TUTULUR.

### Ön Koşullar (BAŞLANGIÇTA DOĞRULANACAK — HİKÂYE ÖNCESİ)
✅ **1265 / 1265 FULL regression PASS** (S-RDH-01 68, S-RDH-02 64, S-PLN-01 42, S-CON-02A 104, S-CON-02B 71, S-CON-02C 93, S-FEA-01 120, S-REG-01 302, S-STR-01 401) — BU HİKÂYE SONRASI EN AZ `1265 + ≥300 = 1565+` test hedeflenir. **1265 regression BOZULMAYACAK.**
✅ `app/contracts/opportunity.py` mevcut (S-CON-02C v1, analiz edildi):
  - 13 ZORUNLU alan: score_id, score_total [0,1], confidence [0,1], actionable bool, reject_reasons list[str], score_components dict[str,float], expected_edge_bps float, expected_cost_bps float, symbol_ref, regime_ref, strategy_ref, policy_version, correlation_id, causation_id, created_ts
  - 5 OPSİYONEL alan: model_version_ref, quality_flags (CAP-2 immutable), expected_hold_bars ≥0, explainability_note
  - `to_sorted_dict()` + `schema_sha256()` hazır (determinizm doğrulama aracı)
✅ `app/contracts/strategy.py` → `StrategySignal` mevcut (signal_id, strategy_id, strategy_version, direction ∈ {long/flat/hold}, signal_strength [0,1], confidence [0,1], correlation_id, causation_id)
✅ `app/contracts/regime.py` → `MarketRegime` + 6-state `MarketRegimeState` mevcut (AD-8)
✅ `app/contracts/feature.py` → `FeatureVector` + 12-key `FEATURE_SCHEMA_REGISTRY['fea_01_v1']` mevcut
✅ `app/contracts/quality.py` → `QualityFlags` frozen, 7 bayrak (stale, degraded, duplicate, missing, out_of_order, invalid, quarantined) + abnormal_spread
✅ `pyproject.toml dependencies = []` — stdlib-only
✅ `CONTRACT_VERSION = "1.0.0"` (BU HİKÂYEDE BUMP YOK — geriye dönüş garantisi)
✅ Hard Safety (v1 boundary): short / leverage>1 / futures / network / credentials / ML/pandas/numpy/ta-lib/ccxt/requests/sqlalchemy YOK (S-RDH-02 credential scan + C-FND-03 forbidden tests devam ettirilecek)
✅ S-PLN-01 EventBus mevcut (`InMemoryTypedEventBus`) — OpportunityScore event publish integration test planlanır

### Değişmez Mimari Kurallar (HİÇBİR KOŞULDA İHLAL EDİLEMEZ)
| Kural | Kaynak | Davranış |
|---|---|---|
| AD-9 Scorer Purity | ARCHITECTURE-SPINE §AD-9 | OpportunityScorer SADECE 4 typed girdi alır (StrategySignal, FeatureVector, MarketRegime, CostAssumptions) → OpportunityScore döndürür; NO network/NO DB/NO FS/NO exchange/NO credential. Pure fonksiyon. |
| AD-20 Determinism + Reproducibility | ARCHITECTURE-SPINE §AD-20 | AYNI 4 girdi → 10 kez → AYNI OpportunityScore. `to_sorted_dict()` eşit; `schema_sha256()` eşit (set len = 1). |
| AD-17 End-to-End Corr/Caus Zinciri | ARCHITECTURE-SPINE §AD-17 | 7-link zincir: StrategySignal → OpportunityScore → RiskDecision → PaperOrder → PaperFill → Position → PortfolioSnapshot. `correlation_id` SABİT (Signal ile aynı); `causation_id = parent.signal_id`. |
| AD-8 Regime Independent Service Boundary | ARCHITECTURE-SPINE §AD-8 | OpportunityScorer, MarketRegime'i READ-ONLY OKUR; rejim engine çağırmaz. 6 rejim (bull/bear/sideways/hv/lv/tu) → 7. rejim YOK. |
| AD-22 FeatureVector Version Contract | ARCHITECTURE-SPINE §AD-22 | Scorer YALNIZCA `feature_version = "fea_01_v1"` → 12-key okur. Başka version → skor düşür + reject_reason ekle (validasyon değil, scoring penalty). |
| AD-10 AI/Scoring Has No Execution Authority | ARCHITECTURE-SPINE §AD-10 | `OpportunityScore.actionable = true` OLSA BİLE; RiskDecision/PaperOrder/PaperFill ÜRETMEZ. **Hiçbir trading permission vermez.** Sadece scoring sonucudur. |
| CAP-1 Replay/Live Parity | SPEC CAP-1 | `app/opportunity/` kaynak kodunda `if run_mode` / `if source_type` dallanması 0 — AST tarayıcı 0 finding. Aynı girdi (replay/live) → Aynı skor. |
| CAP-2 Quality Flags Read-Only + Validator 0 Call | SPEC CAP-2 | QualityFlags OKUNUR (upstream'den gelir); **MUTATE EDİLMEZ** (frozen). Kalite VALIDATOR TEKRAR ÇAĞIRILMAZ (çağrı sayısı = 0). Sadece scoring penalty uygulanır. |
| CAP-3 Plugin Isolation + Forbidden Libs 0 Match | SPEC CAP-3 | `app/opportunity/` için 22 forbidden lib import scan → 0 match. No network, no DB, no FS, no exchange. |
| v1 Hard Safety | PRD Hard Boundaries + CONTRACTS | short / leverage>1 / futures / real order / exchange / API key / network / DB / credential / ML training — HEPSİ YOK. `OpportunityScore.actionable` bir öneridir, execution authority YOK (AD-10). |
| Yeni Contract YOK (Kullanıcı KURAL) | User HARD kural | `OpportunityScore` public API/field/enum DEĞERLERİ %100 KORUNUR. BU HİKÂYEDE YENİ BİR CONTRACT DATACLASS/ENUM OLUŞTURULMAZ. Helper class olabilir (CostAssumptions, ScoringWeights — frozen=True, AMA `app/contracts/` KLASÖRÜNE YAZILMAZ; `app/opportunity/` içinde tutulur). |
| NO Risk / NO Order (Kullanıcı OOS) | User HARD kural | Scorer SADECE `OpportunityScore` üretir. RiskDecision / PaperOrder / PaperFill / Position / Fill Model / Backtest — HEPSİ OOS (bu hikâyede yok). |
| Fixture Defaults ≠ Production Defaults | Kullanıcı KURAL | Production eşikleri KALICI OLARAK KARARLANMAZ. Production defaults `frozen=True` dataclass ile saklanır; fixture/test defaults DEEP COPY ile override edilir (ADN açık kalır). |

---

## 2. Mimari Uyum & Bağlam Devamlılığı (S-STR-01 Sonrası — 10. Halka)

### 7-Halka Korelasyon Zincirine Ekleme (AD-17, BU HİKÂYEDE 2. halka aktif)
```
[CanonicalCandle → S-PLN-01 Typed EventBus]
    ↘ FeatureVector (S-FEA-01 fea_01_v1, 12-key)
        ↘ MarketRegime (S-REG-01 AD-8 6-state)
            ↘ StrategyContext (S-CON-02A AD-25)
                ↘ StrategySignal (S-STR-01: Trend / Momentum)
                    ↘ OpportunityScore (S-OPP-01: BU HİKÂYE — TEK YÖNLÜ scoring)  ← BU HİKÂYE
                        ↘ RiskDecision (S-RSK-01: OOS)
                            ↘ PaperOrder → PaperFill → Position → PortfolioSnapshot (OOS)
```

> **ÖNEMLİ NOT (AD-10 + OOS):** Bu hikâyede **RiskDecision / PaperOrder / PaperFill / Fill Model / Backtest / Position / Portfolio** üretimi KESİNLİKLE YOK. SADECE: `scorer.evaluate(signal, fv, regime, cost_assumptions) → OpportunityScore`.

### Kalıtsal Geliştirici Notları (S-STR-01 Lessons Learned → S-OPP-01)
1. **ULIDISH regex koruma:** `_ULIDISH_RE = r"^[A-Za-z0-9_\-]{8,}$"` — correlation/causation için S-CON-02C zaten tür garantisi; scorer bunları SADECE kopyalar.
2. **Credential false-positive önlemi:** Hassas substrları DOĞRUDAN STRING YAZMA; `chr(ord('B')) + chr(ord('I')) + ...` runtime concat. (örn: `BINANCE_API_KEY`, `SECRET`, `LEVERAGE_2X`, `PRIVATE_KEY` gibi — credential scanner test C-FND-03.)
3. **CAP-1 AST tarama kalıbı:** `ast.NodeVisitor` If/test + Attribute (`expr.attr == "run_mode"` / `"source_type"` / `Name.id == "run_mode"` / `"source_type"`) → 0 finding.
4. **10x Determinizm test kalıbı:** 10 kez evaluate → `set(opp.schema_sha256() for _ in range(10)) == 1` → PASS.
5. **Zero-denominator / NaN koruması:** Her formülde div-by-zero, NaN, Inf → fallback 0.0 ya da clamp [0,1].
6. **22 Forbidden Lib kesin listesi:** `["requests", "httpx", "websockets", "asyncpg", "psycopg2", "sqlalchemy", "pydantic", "pandas", "numpy", "talib", "ta", "ccxt", "kafka", "redis", "aiohttp", "boto3", "django", "flask", "fastapi", "torch", "tensorflow", "catboost"]` — `app/opportunity/` + `tests/opportunity/` için import scan 0 match.
7. **Frozen Defaults + Fixture Override kalıbı (S-STR-01'den benimsendi):** Üretim decision ile test fixture default KARIŞTIRILMAZ! Defaults `app/opportunity/defaults.py` içinde `frozen=True` dataclass ile tutulur; test fixture **override edebilir** (kalıcı production kararı DEĞİLDİR). Aşağıda ADN-OPP-01..12 olarak her eşik testte override edilebilir.

---

## 3. Dosya Yapısı (Kesin — 0 Modified, 2 Yeni Klasör, ≥300 Yeni Test)

### 3.1 Yeni Dosyalar (Oluşturulacak — Tahmini 2 kaynak + 26 test dosyası)

| # | Mutlak Yol | Kapsam | Satır Tahmini | Not |
|---|---|---|---|---|
| **A. KAYNAK (2 DOSYA)** | | | | |
| A1 | `app/opportunity/__init__.py` | Public API: `DeterministicOpportunityScorer`, `DEFAULT_OPPORTUNITY_PARAMS`, `DEFAULT_COST_ASSUMPTIONS`, `DEFAULT_SCORING_WEIGHTS`, `SCORER_VERSION_STORY_DEFAULT`, `POLICY_VERSION_STORY_DEFAULT`, `compute_raw_opportunity_score`, `compute_confidence`, `compute_gross_edge_bps`, `compute_fee_bps`, `compute_slippage_bps`, `compute_spread_bps`, `compute_latency_bps`, `compute_net_edge_bps`, `compute_cost_multiplier`, `compute_regime_adjustment`, `compute_strategy_adjustment`, `compute_final_score`, `build_explainability_bundle` | 40–80 | Modül init; `__all__` 18+ isim. **Contracts klasörüne DOKUNULMAZ; mevcut contracts import edilir ama DEĞİŞTİRİLMEZ.** |
| A2 | `app/opportunity/base.py` | 13 bileşen hesaplayan saf fonksiyonlar + DeterministicOpportunityScorer evaluate() + 3 frozen helper: (i) MarketCostAssumptions, (ii) ScoringWeights, (iii) QualityPenaltyConfig. Her alt bileşen ayrı fonksiyon (tek tek test edilebilir). | 500–900 | stdlib-only, sadece `dataclasses` + `typing` + mevcut contracts import. **Yeni contract YOK.** |
| **B. TEST (26 DOSYA, ≥300 TEST)** | | | | |
| T1 | `tests/opportunity/test_sopp01_01_raw_opportunity_score.py` | 12. raw_opportunity_score formülü: ağırlıklar 0.55/0.30/0.15, clamp [0,1], 0-strength flat, 1-strength bull. | 220 | ≥22 test |
| T2 | `tests/opportunity/test_sopp01_02_confidence_model.py` | 2. confidence = 0.55 strat_conf + 0.30 regime_conf + 0.15 quality_mult. Her bir alt bileşen varyantları + clamp. | 240 | ≥24 test |
| T3 | `tests/opportunity/test_sopp01_03_gross_edge_bps.py` | 3. gross_edge_bps = signal_strength · regime_compat · gross_edge_scale · expected_vol_factor. Flat direction → 0.0. | 220 | ≥22 test |
| T4 | `tests/opportunity/test_sopp01_04_fee_cost_bps.py` | 4. fee_cost_bps = (base_taker_fee_bps + network_fee_bps) · trade_size_multiplier (fixture default 1.0x). Negatif YOK (min 0.0). | 200 | ≥20 test |
| T5 | `tests/opportunity/test_sopp01_05_slippage_cost_bps.py` | 5. slippage_cost_bps = slippage_base_bps · volatility_factor · orderbook_depth_factor (vol yüksek → slippage yüksek). | 220 | ≥22 test |
| T6 | `tests/opportunity/test_sopp01_06_spread_cost_bps.py` | 6. spread_cost_bps = (featured_spread_bps if valid else min_spread_bps) · 0.5 (yarısı maliyet). Abnormal_spread kalite → 1.3x. | 200 | ≥20 test |
| T7 | `tests/opportunity/test_sopp01_07_latency_impact_bps.py` | 7. latency_impact_bps = (latency_ms / target_latency_ms) · vol_based_sensitivity. Latency yüksek → maliyet artar. | 200 | ≥20 test |
| T8 | `tests/opportunity/test_sopp01_08_net_edge_bps.py` | 8. net_edge_bps = gross - fee - slippage - spread - latency. Negatif olabilir. Tüm ara toplam varyantları. | 220 | ≥22 test |
| T9 | `tests/opportunity/test_sopp01_09_cost_multiplier.py` | 9. cost_multiplier = f(net_edge_positive? 1.0 : penalty). Net edge pozitif ise 1.0; negatif ise 0.15. | 180 | ≥18 test |
| T10 | `tests/opportunity/test_sopp01_10_regime_adjustment.py` | 10. 6 rejim × 2 strateji: bull=1.0, lv=0.9, hv=0.4, sideways=0.2, tu=0.1, bear=0.0. Formül + clamp [0,1]. | 260 | ≥26 test |
| T11 | `tests/opportunity/test_sopp01_11_strategy_adjustment.py` | 11. 2 strateji: trend=1.0, momentum=0.95. Unknown strategy id → 0.3 (penalize). Strategy id+version korunur. | 200 | ≥20 test |
| T12 | `tests/opportunity/test_sopp01_12_final_opportunity_score.py` | 12. final_score = clamp(raw * regime_adj * strategy_adj * cost_mult * quality_impact_mult, 0, 1). Tüm kombineasyonlar. | 240 | ≥24 test |
| T13 | `tests/opportunity/test_sopp01_13_quality_flags_cap2.py` | 7 kalite bayrağı: stale 0.60, degraded 0.60, duplicate 0.85, missing 0.85, out_of_order 0.85, invalid 0.15 + force actionable=false, quarantined 0.15 + force actionable=false. CAP-2: MUTATE YOK, VALIDATOR 0 CALL. | 320 | ≥32 test |
| T14 | `tests/opportunity/test_sopp01_14_explainability.py` | 6 explainability alanı: score_components, component_weights, dominant_factors, cost_breakdown, regime_evidence, strategy_evidence → DETERMINISTIC SORTED ORDER. Key'ler alfabetik. | 280 | ≥28 test |
| T15 | `tests/opportunity/test_sopp01_15_determinism_10x.py` | 10x determinizm: her 2 strateji × her 6 rejim × 2 quality varyant = 24 case × 10 kez → set len = 1. SHA-256 + sorted dict. | 320 | ≥32 test |
| T16 | `tests/opportunity/test_sopp01_16_cap1_ast_branch.py` | CAP-1: AST scan `app/opportunity/` → `if run_mode` / `if source_type` dallanması 0 finding. Grep 0 match. | 200 | ≥20 test |
| T17 | `tests/opportunity/test_sopp01_17_cap2_quality_immutable.py` | CAP-2: QualityFlags MUTATE YOK (id koruması). Validator çağrı sayısı 0 (mock ile verify). | 200 | ≥20 test |
| T18 | `tests/opportunity/test_sopp01_18_correlation_causation.py` | Correlation_id = Signal.correlation_id (aynı). Causation_id = Signal.signal_id (parent). 10x run'da corr/caus SABİT. ULID length doğrulaması. | 220 | ≥22 test |
| T19 | `tests/opportunity/test_sopp01_19_eventbus_integration.py` | S-PLN-01 EventBus: OpportunityScore publish → wildcard + typed subscriber → 4 olay (score_created / score_accepted / score_rejected / explainability_ready). Correlation_id AYNI. | 260 | ≥26 test |
| T20 | `tests/opportunity/test_sopp01_20_network_safety.py` | Network güvenliği: `app/opportunity/` kaynaklarında socket, urllib, http.client, requests, httpx, websocket — import 0. AST grep. | 180 | ≥18 test |
| T21 | `tests/opportunity/test_sopp01_21_credential_safety.py` | Credential güvenliği: 40+ hassas substring regex scan (API_KEY, SECRET, BINANCE, BYBIT, PRIVATE_KEY vs) → 0 match. `_chr_join()` test helper DOĞRU kullanım. | 180 | ≥18 test |
| T22 | `tests/opportunity/test_sopp01_22_output_contract.py` | OpportunityScore 13 zorunlu alan + 5 opsiyonel doğrulaması. score_total/clamp, confidence/clamp, policy_version regex, corr/caus ULID length. | 260 | ≥26 test |
| T23 | `tests/opportunity/test_sopp01_23_no_execution_authority.py` | AD-10: Scorer output → 0 RiskDecision/PaperOrder/PaperFill/Position. `app/opportunity/` → bu class isimlerine import/reference 0. | 160 | ≥16 test |
| T24 | `tests/opportunity/test_sopp01_24_safety_boundary.py` | v1 safety: short direction gelirse → skor 0 + actionable=False + reject_reason. Leverage/futures field YOK. Sadece long/flat/hold scoring. | 180 | ≥18 test |
| T25 | `tests/opportunity/test_sopp01_25_integration_full_chain.py` | Tam zincir: StrategySignal (S-STR-01) → FV (S-FEA-01) → Regime (S-REG-01) → Scorer (S-OPP-01) → OpportunityScore. 3 senaryo (strong_bull_long, bear_flat, lv_momentum_long). | 280 | ≥28 test |
| T26 | `tests/opportunity/test_sopp01_26_full_regression_smoke.py` | Regression smoke: 1265 mevcut testin tümünü (import subset ile) + S-OPP-01 yeni testlerin import smoke'u. pyproject.toml deps=[], 22 forbidden lib 0 match, CONTRACT_VERSION 1.0.0. | 240 | ≥24 test |

**Toplam Yeni Test Tahmini (26 dosya):** 22+24+22+20+22+20+20+22+18+26+20+24+32+28+32+20+20+22+26+18+18+26+16+18+28+24 = **616 test** (min bound: ≥300, hedef aşıldı).
**Regression Hedef:** 1265 + ≥300 = **1565+ PASS (0 regression kaybı).**

### 3.2 DEĞİŞTİRİLECEK DOSYALAR — 0 ADET (KESİN)
Bu hikâyede **hiçbir mevcut kaynak dosyası DEĞİŞTİRİLMEZ.** Sadece YENİ dosya oluşturulur:
- ❌ `app/contracts/*.py` — HEPSİ dokunulmuyor. `OpportunityScore`, `StrategySignal`, `MarketRegime`, `FeatureVector`, `QualityFlags`, `CONTRACT_VERSION="1.0.0"` + 100+ `__all__` sırası %100 KORUNUR.
- ❌ `app/strategies/*.py` — S-STR-01 kaynak dokunulmuyor.
- ❌ `app/regime/*.py` — S-REG-01 kaynak dokunulmuyor.
- ❌ `app/features/*.py` — S-FEA-01 kaynak dokunulmuyor.
- ❌ `app/platform/*.py` — S-PLN-01 kaynak dokunulmuyor.
- ❌ `pyproject.toml` — `dependencies=[]` DEĞİŞMEZ.
- ❌ S-RDH-01/02, S-PLN-01, S-CON-02A/B/C, S-FEA-01, S-REG-01, S-STR-01 test dosyaları — dokunulmaz (regression onayı).

### 3.3 Out of Scope (Kesin — OOS, HİÇBİR ŞEKİLDE YOK)
| OOS Madde | Açıklama |
|---|---|
| ❌ Risk Engine / Kill Switch / Limits / Position Sizing | E-RSK Epic — ayrı hikâye (S-RSK-01 sonrakidir, bu hikâyede YOK) |
| ❌ RiskDecision generation algoritması | RiskDecision contract mevcut ama ÜRETİM YOK |
| ❌ PaperOrder / PaperFill / Fill Model | E-PTR Epic — OOS |
| ❌ Backtest Engine / Portfolio Simulator / Fill Engine | E-BKT/E-SIM — OOS |
| ❌ AI/ML/Model training/inference / sklearn / XGBoost / pandas / numpy | E-AIS model training — OOS |
| ❌ Feature Engineering / Feature Leakage | S-FEA-01 zaten yapıldı — OOS |
| ❌ Regime Detection Engine | S-REG-01 zaten yapıldı — OOS |
| ❌ Strategy implementation | S-STR-01 zaten yapıldı — OOS |
| ❌ Exchange / API Key / Credential / WS / HTTP | E-PLN — OOS |
| ❌ Dashboard / Web API / UI | E-API — OOS |
| ❌ Database / Redis / Kafka / Object Storage | E-STORAGE — OOS |
| ❌ Live execution / Gerçek emir gönderme | v2+ — OOS |
| ❌ Short / Leverage>1 / Futures / Options | v1 hard boundary — OOS |
| ❌ Production eşiklerinin optimalliği iddiası | Açık kararlar ADN-OPP-01..12 — fixtures ile ayrıldı |

---

## 4. 12 Skor Bileşeni — KESİN MATEMATİKSEL FORMÜLLER

> **KURAL:** Her bir alt bileşen **ayrı bir saf fonksiyon** olarak uygulanır ve **ayrı ayrı test edilir.** Formüldeki tüm sabitler (ağırlıklar, ölçekler, penalty'ler) `ScoringWeights` ve `MarketCostAssumptions` frozen dataclass içinde tutulur; fixture/test DEFAULTSLARI override edilebilir (production defaults kalıcı DEĞİLDİR, ADN açık kalır).

### 4.0 Girdi Tipleri (Kısaltmalar — Formüllerde Kullanılacak)
```
S = StrategySignal (S-STR-01)
  S.ss    = signal_strength ∈ [0, 1]
  S.c     = confidence ∈ [0, 1]
  S.dir   = direction ∈ {long, flat, hold}
  S.sid   = strategy_id   (örn: "trend_following_v1", "momentum_v1")
  S.sver  = strategy_version (örn: "str_01_v1")
  S.scid  = signal_id → causation_id için kullanılır (parent id)
  S.corr  = correlation_id → OpportunityScore.correlation_id (SABİT)

F = FeatureVector (S-FEA-01 fea_01_v1, 12-key)
  F.rsi       = F.rsi_14            ∈ [0, 100]
  F.ema14     = F.ema_14_close
  F.ema28     = F.ema_28_close
  F.price     = F.close_ref
  F.mom10abs  = F.mom_10_abs
  F.mom10pct  = F.mom_10_pct
  F.vol24     = F.volatility_24h    ∈ [0, 1] normalize
  F.spreadbps = F.spread_bps        (bazı FV'larda NaN olabilir, min fallback)
  F.vwapgap   = F.vwap_gap_pct      ∈ [-x, +x]

R = MarketRegime (S-REG-01 AD-8 6-state)
  R.state       ∈ {bull, bear, sideways, high_volatility, low_volatility, transition_uncertain}
  R.c           = regime_confidence ∈ [0, 1]
  R.score_bull  / R.score_bear / R.score_sideways / R.score_hv / R.score_lv / R.score_tu  (6 skor)
  R.compat_strat = [derived: bu rejim hangi strateji ile çalışır] (yoksa skor matrisinden bul)

Q = QualityFlags (upstream'den gelir, frozen=True — MUTATE YOK, VALIDATOR 0 CALL)
  Q.stale / Q.degraded / Q.duplicate / Q.missing / Q.out_of_order / Q.invalid / Q.quarantined / Q.abnormal_spread

C = MarketCostAssumptions (frozen helper, fixture override edilebilir)
  C.fee_taker_bps        = 10.0   (ADN-OPP-01: fixture default 10 bps = %0.1)
  C.fee_network_bps      =  0.5   (ADN-OPP-01: fixture default 0.5 bps)
  C.slippage_base_bps    =  3.0   (ADN-OPP-02: fixture default 3 bps)
  C.slippage_vol_expo    =  1.5   (ADN-OPP-02: vol yükselince slippage eğrisi)
  C.min_spread_bps       =  1.0   (ADN-OPP-03: fixture spread fallback)
  C.latency_ms           =  3.0   (ADN-OPP-04: fixture default 3ms)
  C.latency_target_ms    =  1.0   (ADN-OPP-04: target latency)
  C.latency_sensitivity  =  2.0   (ADN-OPP-04: latency vol etkisi çarpanı)
  C.gross_edge_scale_bps = 50.0   (ADN-OPP-10: fixture default 50 bps birim başı)
  C.trade_size_mult      =  1.0   (ADN-OPP-01: size etkisi)

W = ScoringWeights (frozen helper, fixture override edilebilir)
  W.w_raw_strategy   = 0.55   (ADN-OPP-05)
  W.w_raw_regime     = 0.30   (ADN-OPP-05)
  W.w_raw_feature    = 0.15   (ADN-OPP-05)
  W.w_conf_strategy  = 0.55   (ADN-OPP-06)
  W.w_conf_regime    = 0.30   (ADN-OPP-06)
  W.w_conf_quality   = 0.15   (ADN-OPP-06)
  W.net_positive_mult = 1.00  (ADN-OPP-09)
  W.net_negative_mult = 0.15  (ADN-OPP-09)
  W.actionable_score_threshold = 0.55  (ADN-OPP-06: long için actionable eşiği — fixture)
  W.actionable_net_edge_bps    = 5.0   (ADN-OPP-06: net edge pozitif eşik — fixture)
```

---

### 4.1 Bileşen 1/12: `raw_opportunity_score` ∈ [0, 1]

**Formül (KESİN, clamp [0,1]):**
```
direction_compat = 1.0   if S.dir == "long"
direction_compat = 0.0   if S.dir in {"flat", "hold"}   # flat/hold sinyali → raw skor 0 tabanı

strategy_component   = S.ss                           # [0,1]
regime_component     = R.c * _regime_compat_score(R)   # [0,1] · [0,1] → [0,1]
feature_component    = _feature_vol_score(F)           # [0,1] türetilmiş: (0.5 + vol_align_with_trend/2)

raw_pre_clamp = (
    W.w_raw_strategy   * strategy_component +
    W.w_raw_regime     * regime_component +
    W.w_raw_feature    * feature_component
) * direction_compat

raw_opportunity_score = clamp(raw_pre_clamp, 0.0, 1.0)
```

**Yardımcı 1: `_regime_compat_score(R)` ∈ [0,1]**
```
REGIME_COMPAT = {
    "bull":                 1.00,   # güçlü long ortamı
    "low_volatility":       0.90,   # stabil, long uygun
    "high_volatility":      0.40,   # riskli
    "sideways":             0.20,   # yönsüz
    "transition_uncertain": 0.10,   # geçiş, çok riskli
    "bear":                 0.00,   # düşüşte long yok
}
_regime_compat_score = REGIME_COMPAT[R.state]  # 7. rejim YOK (AD-8)
```

**Yardımcı 2: `_feature_vol_score(F)` ∈ [0,1]**
```
# Trend ile vol uyumu: EMA trend + mom pozitif + vol ılımlı ise yüksek skor
price_above_ema = 1.0 if (F.price or 0.0) >= (F.ema14 or F.price or 0.0) else 0.0
ema_bull       = 1.0 if (F.ema14 or 0.0) >= (F.ema28 or F.ema14 or 0.0) else 0.0
mom_positive   = 1.0 if (F.mom10pct or 0.0) >= 0.0 else 0.0
vol_moderate   = 1.0 - abs((F.vol24 or 0.5) - 0.5)  # vol 0.5 civarında 1.0, uçlarda 0.5

_feature_vol_score = clamp(
    0.30 * price_above_ema +
    0.25 * ema_bull +
    0.25 * mom_positive +
    0.20 * vol_moderate,
    0.0, 1.0
)
```

**Ayrı testler (T1):** strategy 0/0.5/1, 6 rejim × 2 fv, long vs flat/hold direction_compat, clamp taşması.

---

### 4.2 Bileşen 2/12: `confidence` ∈ [0, 1]

**Formül (KESİN, clamp [0,1]):**
```
quality_mult = _quality_confidence_multiplier(Q)   # [0.0, 1.0] — aşağıda Quality bölümünde tanımlı

confidence_pre_clamp = (
    W.w_conf_strategy  * S.c +
    W.w_conf_regime    * R.c +
    W.w_conf_quality   * quality_mult
)

confidence = clamp(confidence_pre_clamp, 0.0, 1.0)
```

> **CAP-2:** `_quality_confidence_multiplier(Q)` — QualityFlags OKUR, MUTATE ETMEZ, VALIDATOR TEKRAR ÇAĞIRMAZ.

**Ayrı testler (T2):** 3 bileşen varyantları, 0.0/0.5/1.0 her biri, quality 7 bayrak varyantları, clamp taşması.

---

### 4.3 Bileşen 3/12: `expected_gross_edge_bps` ∈ ℝ (negatif olabilir ama formül pozitif yönlü)

**Formül (KESİN):**
```
if S.dir in {"flat", "hold"}:
    expected_gross_edge_bps = 0.0
else:
    regime_strength = R.c * _regime_compat_score(R)          # [0,1]
    vol_factor      = 0.5 + 0.5 * (F.vol24 or 0.5)           # [0.5, 1.0] — yüksek vol daha fazla edge potansiyeli
    trend_alignment = 0.4 * price_above_ema + 0.3 * ema_bull + 0.3 * mom_positive  # [0,1]

    expected_gross_edge_bps = (
        C.gross_edge_scale_bps *     # 50 bps fixture default
        S.ss *                        # [0,1] — sinyal gücü
        regime_strength *             # [0,1] — rejim uyumu
        vol_factor *                  # [0.5,1.0] — vol tabanlı edge ölçeği
        trend_alignment               # [0,1] — trend doğrulama
    )

# Not: gross edge her zaman ≥ 0 (sadece long/flat, short yok).
expected_gross_edge_bps = max(expected_gross_edge_bps, 0.0)
```

**Ayrı testler (T3):** strong bull (yüksek), bear flat (0), low vol (düşük), high vol (orta), ss=0 → 0, clamp 0 altı.

---

### 4.4 Bileşen 4/12: `fee_cost_bps` ∈ [0, +∞) (negatif YOK)

**Formül (KESİN):**
```
fee_cost_bps = max(C.fee_taker_bps + C.fee_network_bps, 0.0) * C.trade_size_mult
```

**Ayrı testler (T4):** fixture default, fee 0, size mult 2x, NaN koruması → 0.

---

### 4.5 Bileşen 5/12: `slippage_cost_bps` ∈ [0, +∞)

**Formül (KESİN):**
```
vol_factor     = (max(F.vol24 or 0.1, 0.01)) ** C.slippage_vol_expo   # vol yükseldikçe artan
# Örn: vol=0.2 → 0.2^1.5 ≈ 0.089 ; vol=0.8 → 0.8^1.5 ≈ 0.715
# min 0.01 koruması (div-by-zero / negatif olmasın)

depth_factor   = 1.0   # fixture default (orderbook derinliği şu an feature'da yok; 1.0 alınır,
                        # ADN-OPP-02: ileride feature_vector'a orderbook_depth gelirse kullanılır)

abnormal_penalty = 1.30 if Q and Q.abnormal_spread else 1.00

slippage_cost_bps = max(
    C.slippage_base_bps * vol_factor * depth_factor * abnormal_penalty,
    0.0
)
```

**Ayrı testler (T5):** düşük/orta/yüksek vol, abnormal_spread True/False, min vol koruması.

---

### 4.6 Bileşen 6/12: `spread_cost_bps` ∈ [0, +∞)

**Formül (KESİN):**
```
# spread maliyeti: girerken + çıkarken toplamda spread'in yaklaşık yarısı
raw_spread = F.spreadbps if F.spreadbps is not None and not isinstance(F.spreadbps, float) or (isinstance(F.spreadbps, float) and not (F.spreadbps != F.spreadbps)) else C.min_spread_bps
# Yukarıdaki: F.spreadbps varsa (ve NaN değilse) onu al; yoksa min_spread_bps

valid_spread = max(raw_spread, C.min_spread_bps)   # alt sınır
abnormal_mult = 1.30 if Q and Q.abnormal_spread else 1.00

spread_cost_bps = max(valid_spread * 0.5 * abnormal_mult, 0.0)
# 0.5 = spread'in yarısı (giriş maliyeti; çıkış OOS — bu scoring için sadece giriş yarısı)
```

**Ayrı testler (T6):** spread 0/1/10/100 bps, NaN fallback, abnormal_spread True.

---

### 4.7 Bileşen 7/12: `latency_impact_bps` ∈ [0, +∞)

**Formül (KESİN):**
```
latency_ratio  = max(C.latency_ms / max(C.latency_target_ms, 0.001), 1.0)
# latency hedefin üstündeysek oran > 1

vol_sens_factor = (max(F.vol24 or 0.0, 0.0))   # yüksek vol'da latency daha pahalı

latency_impact_bps = max(
    latency_ratio * C.latency_sensitivity * vol_sens_factor * (C.gross_edge_scale_bps / 50.0),
    # normalize: 50 bps scale başına 2.0 bps · ratio · vol
    0.0
)
```

**Ayrı testler (T7):** latency 0.1ms (target), 3ms (default), 50ms (kötü). Vol 0/yüksek varyantları.

---

### 4.8 Bileşen 8/12: `expected_net_edge_bps` ∈ ℝ (negatif OLABİLİR — önemli!)

**Formül (KESİN, Net-of-Cost ANA denklem):**
```
total_cost_bps = fee_cost_bps + slippage_cost_bps + spread_cost_bps + latency_impact_bps

expected_net_edge_bps = expected_gross_edge_bps - total_cost_bps

# Önemli: bu değer NEGATİF OLABİLİR. Öyle olursa cost_multiplier onu da aşağı çeker.
```

> **Bu hikâyenin en önemli denklemidir (FR-019).** Gross edge'ten TÜM 4 maliyet (fee/slippage/spread/latency) tek tek çıkarılır ve her bir bileşen ayrı test edilir.

**Ayrı testler (T8):** pozitif net edge (tüm maliyetler düşük), negatif net edge (yüksek maliyetler), net sıfır, her bir maliyetin tek tek kaldırıldığı varyantlar.

---

### 4.9 Bileşen 9/12: `cost_multiplier` ∈ (0, 1]

**Formül (KESİN):**
```
if expected_net_edge_bps > 0.0:
    cost_multiplier = W.net_positive_mult   # 1.00
else:
    cost_multiplier = W.net_negative_mult   # 0.15 — negatif net edge için çok düşük
```

**Ayrı testler (T9):** pozitif (1.0), negatif (0.15), tam sıfır (0.15).

---

### 4.10 Bileşen 10/12: `regime_adjustment` ∈ [0, 1]

**Formül (KESİN, 6 rejim × 2 strateji matrisi):**
```
REGIME_ADJUSTMENT_MATRIX = {
    # (regime_state)           trend  momentum
    "bull":                   (1.00, 1.00),
    "low_volatility":         (0.90, 0.95),
    "high_volatility":        (0.40, 0.35),
    "sideways":               (0.20, 0.25),
    "transition_uncertain":   (0.10, 0.10),
    "bear":                   (0.00, 0.00),
}
# 7. rejim YOK (AD-8)

strategy_idx = 0 if "trend" in S.sid.lower() else 1 if "momentum" in S.sid.lower() else 1  # unknown → momentum matrisi
base_regime_adj = REGIME_ADJUSTMENT_MATRIX[R.state][strategy_idx]

# Rejim confidence ile ağırla: confidence yüksekse → matris değeri; düşükse → 0.5'e converge
confidence_blend = R.c * base_regime_adj + (1.0 - R.c) * 0.50

regime_adjustment = clamp(confidence_blend, 0.0, 1.0)
```

**Ayrı testler (T10):** 6 rejim × 2 strateji = 12 varyant; R.c=0/0.5/1.0 için 36 varyant.

---

### 4.11 Bileşen 11/12: `strategy_adjustment` ∈ [0, 1]

**Formül (KESİN):**
```
STRATEGY_ADJUSTMENT = {
    "trend_following": 1.00,
    "momentum":        0.95,
    # unknown strategy → düşük ayar
}
# strateji adı match:
strategy_key = None
if "trend" in S.sid.lower():
    strategy_key = "trend_following"
elif "momentum" in S.sid.lower():
    strategy_key = "momentum"

if strategy_key:
    raw_strat_adj = STRATEGY_ADJUSTMENT[strategy_key]
else:
    raw_strat_adj = 0.30   # unknown strategy penalize

# StrategySignal confidence ile blend (stratejinin kendinden gelen güven)
strategy_adjustment = clamp(raw_strat_adj * (0.5 + 0.5 * S.c), 0.0, 1.0)
```

**ÖNEMLİ KURAL:** `OpportunityScore.strategy_ref` alanında `S.sid + ":" + S.sver` KORUNUR (orijinal strateji kimliği kaybolmaz — S-CON-02C contract gereği). Strateji ID/version OpportunityScore içinden her zaman geri okunabilir.

**Ayrı testler (T11):** Trend/Momentum/Unknown 3 case × S.c 0/0.5/1 → 9 varyant. strategy_ref alanının doğruluğu.

---

### 4.12 Bileşen 12/12: `final_opportunity_score` ∈ [0, 1] + `actionable` + `expected_cost_bps` + `reject_reasons`

**Formül (KESİN, clamp [0,1]):**
```
quality_impact_mult = _quality_score_multiplier(Q)   # Quality bölümünde aşağıda tanımlı [0,1]

score_unclamped = (
    raw_opportunity_score *
    regime_adjustment *
    strategy_adjustment *
    cost_multiplier *
    quality_impact_mult
)

final_opportunity_score = clamp(score_unclamped, 0.0, 1.0)
```

**`expected_cost_bps` (contract zorunlu alan):**
```
expected_cost_bps = total_cost_bps   # fee + slippage + spread + latency (toplam)
```

**`actionable` bool (contract zorunlu alan — 3 KOŞUL HEPSİ):**
```
actionable = (
    final_opportunity_score >= W.actionable_score_threshold
    AND
    expected_net_edge_bps >= W.actionable_net_edge_bps
    AND
    Q is None or (not Q.invalid and not Q.quarantined)
)
# Not: actionable=true OLSA BİLE — AD-10: execution authority YOK. Sadece skor önerisidir.
```

**`reject_reasons: list[str]` (contract zorunlu, None YOK, boş olabilir):**
```
reject_reasons = []
if final_opportunity_score < W.actionable_score_threshold:
    reject_reasons.append("score_below_threshold")
if expected_net_edge_bps < W.actionable_net_edge_bps:
    reject_reasons.append("net_edge_not_positive")
if S.dir in {"flat", "hold"}:
    reject_reasons.append("signal_direction_flat")
if R.state == "bear":
    reject_reasons.append("regime_bear_no_long")
if Q and Q.invalid:
    reject_reasons.append("quality_invalid_data")
if Q and Q.quarantined:
    reject_reasons.append("quality_quarantined")
if expected_net_edge_bps <= 0.0:
    reject_reasons.append("cost_exceeds_gross_edge")
# Listeyi DETERMINISTIC SORT et (alfabetik):
reject_reasons = sorted(reject_reasons)
```

**Ayrı testler (T12):** 5 bileşen her biri 0/0.5/1 varyantları, final clamp taşması, actionable 3 koşul varyantları, reject_reasons sort order.

---

## 5. Confidence Model (Bileşen 2 Detay) + Quality 7 Bayrak Etkisi (CAP-2)

### 5.1 Confidence Bileşenleri (tekrar + kalite detayı)
```
confidence = 0.55*S.c + 0.30*R.c + 0.15*quality_mult
```

### 5.2 `_quality_confidence_multiplier(Q)` ∈ [0, 1] — confidence için kalite etkisi (CAP-2: READ-ONLY)
```
def _quality_confidence_multiplier(Q) -> float:
    if Q is None:
        return 1.0   # kalite bilgisi yoksa temiz varsay
    mult = 1.0
    # Şiddet SIRASIYLA uygulanır (en şiddetli son karar, ama hepsi çarpılır):
    if Q.stale:           mult *= 0.85
    if Q.degraded:        mult *= 0.85
    if Q.duplicate:       mult *= 0.90
    if Q.missing:         mult *= 0.90
    if Q.out_of_order:    mult *= 0.90
    if Q.abnormal_spread: mult *= 0.92
    # EN ŞİDDETLİ: invalid / quarantined → en düşük çarpan
    if Q.invalid:         mult = min(mult, 0.15)   # 0.15 ceiling
    if Q.quarantined:     mult = min(mult, 0.15)   # 0.15 ceiling
    return clamp(mult, 0.0, 1.0)
```

### 5.3 `_quality_score_multiplier(Q)` ∈ [0, 1] — final skor için kalite etkisi (CAP-2)
```
def _quality_score_multiplier(Q) -> float:
    if Q is None:
        return 1.0
    mult = 1.0
    if Q.stale:           mult *= 0.60     # §S-CON-02C ile uyumlu
    if Q.degraded:        mult *= 0.60
    if Q.duplicate:       mult *= 0.85
    if Q.missing:         mult *= 0.85
    if Q.out_of_order:    mult *= 0.85
    if Q.abnormal_spread: mult *= 0.80
    # invalid / quarantined → hem skor düşer HEM DE actionable=False (§4.12'de)
    if Q.invalid:         mult = min(mult, 0.15)
    if Q.quarantined:     mult = min(mult, 0.15)
    return clamp(mult, 0.0, 1.0)
```

### 5.4 Quality 7 Bayrak Özet Tablo (Hepsi AÇIK)
| Kalite Bayrağı | Confidence Çarpanı | Final Skor Çarpanı | `actionable` Etkisi | `reject_reasons` |
|---|---|---|---|---|
| stale | 0.85× | 0.60× | normal koşullara bağlı | yok (eşik altına düşerse gelir) |
| degraded | 0.85× | 0.60× | normal koşullara bağlı | yok |
| duplicate | 0.90× | 0.85× | normal koşullara bağlı | yok |
| missing | 0.90× | 0.85× | normal koşullara bağlı | yok |
| out_of_order | 0.90× | 0.85× | normal koşullara bağlı | yok |
| abnormal_spread | 0.92× | 0.80× + slippage 1.3x + spread 1.3x | normal koşullara bağlı | yok (maliyet artışı net edge'i düşürür) |
| invalid | 0.15 (CEILING) | 0.15 (CEILING) | **ZORUNLU FALSE** | `"quality_invalid_data"` |
| quarantined | 0.15 (CEILING) | 0.15 (CEILING) | **ZORUNLU FALSE** | `"quality_quarantined"` |

> **GÜVENLİ DAVRANIŞ (invalid/quarantined):** Skor 0.15'ten yüksek OLAMAZ. Actionable ZORUNLU false. QualityFlags MUTATE EDİLMEZ (CAP-2). Validator TEKRAR ÇAĞIRILMAZ (çağrı sayısı 0).

---

## 6. Explainability Model (6 Alan, Deterministic Sorted Order)

`OpportunityScore.score_components` + `OpportunityScore.explainability_note` içinde 6 zorunlu açıklama alanı **deterministik sıralama ile** sunulur.

### 6.1 Zorunlu 6 Açıklama Alanı (Key'ler ALFABETİK — deterministic)
```python
explainability_bundle = {
    # 1. Skor bileşenlerinin ham değerleri (hesaplanan 12 bileşenden anlamlı olanlar)
    "score_components": {
        # ALFABETİK KEY ORDER
        "confidence":             confidence,                 # [0,1]
        "cost_multiplier":        cost_multiplier,            # (0,1]
        "expected_net_edge_bps":  expected_net_edge_bps,      # float (negatif olabilir)
        "final_score":            final_opportunity_score,    # [0,1]
        "raw_score":              raw_opportunity_score,      # [0,1]
        "regime_adjustment":      regime_adjustment,          # [0,1]
        "strategy_adjustment":    strategy_adjustment,        # [0,1]
    },

    # 2. Her skor bileşeninin ağırlığı (toplam 1.00)
    "component_weights": {
        # ALFABETİK KEY ORDER
        "cost_multiplier_w":      0.20,
        "quality_impact_w":       0.15,
        "raw_score_w":            0.25,
        "regime_adjustment_w":    0.20,
        "strategy_adjustment_w":  0.20,
    },  # Not: bu ağırlıklar "önem ağırlığı" açıklaması için, formülde kullanılan çarpımdan bağımsızdır (fixture).

    # 3. Dominant faktörler: |etki| yüksek → önce gelir (DETERMINISTIC: etkiler hesaplanır, aynı etki → alfabetik)
    "dominant_factors": _compute_dominant_factors(raw_score, regime_adj, strategy_adj, cost_mult, quality_mult),
    # Örn çıktı: ["raw_score:0.80", "regime_adjustment:1.00", "strategy_adjustment:0.95"] — sorted by abs(contribution) desc, then alpha

    # 4. Maliyet dökümü (bps olarak) — ALFABETİK key
    "cost_breakdown_bps": {
        "expected_cost_total": expected_cost_bps,
        "fee_cost":            fee_cost_bps,
        "gross_edge_expected": expected_gross_edge_bps,
        "latency_impact":      latency_impact_bps,
        "net_edge_expected":   expected_net_edge_bps,
        "slippage_cost":       slippage_cost_bps,
        "spread_cost":         spread_cost_bps,
    },

    # 5. Rejim kanıtı (6 rejim skorundan oluşur, ALFABETİK)
    "regime_evidence": {
        "detected_state":          R.state,
        "detected_state_conf":      R.c,
        "score_bear":              R.score_bear,
        "score_bull":              R.score_bull,
        "score_high_volatility":   R.score_hv,
        "score_low_volatility":    R.score_lv,
        "score_sideways":          R.score_sideways,
        "score_transition_uncertain": R.score_tu,
        "adjustment_applied":      regime_adjustment,
    },

    # 6. Strateji kanıtı (uygulanan strateji kimliği + kanıt)
    "strategy_evidence": {
        "direction":              S.dir,
        "signal_confidence":      S.c,
        "signal_id":              S.scid,
        "signal_strength":        S.ss,
        "strategy_id":            S.sid,
        "strategy_ref_output":    strategy_ref,   # OpportunityScore.strategy_ref ile AYNI
        "strategy_version":       S.sver,
        "adjustment_applied":     strategy_adjustment,
    },
}
```

### 6.2 `OpportunityScore.score_components` contract alanına yazılacak içerik
S-CON-02C gereği `score_components: dict[str, float]` (flat dict). Yukarıdaki açıklama bundle'ından **flat edilebilir** (2 seviyeye kadar) `key.subkey` formatı kullanılır:
```
score_components (contract alanı) = {
    "confidence":                 confidence,
    "cost_multiplier":            cost_multiplier,
    "costs.fee_bps":              fee_cost_bps,
    "costs.latency_bps":          latency_impact_bps,
    "costs.slippage_bps":         slippage_cost_bps,
    "costs.spread_bps":           spread_cost_bps,
    "costs.total_bps":            expected_cost_bps,
    "edge.gross_bps":             expected_gross_edge_bps,
    "edge.net_bps":               expected_net_edge_bps,
    "final_score":                final_opportunity_score,
    "quality_multiplier":         quality_impact_mult,
    "raw_score":                  raw_opportunity_score,
    "regime.adjustment":          regime_adjustment,
    "strategy.adjustment":        strategy_adjustment,
}  # TÜM key'ler ALFABETİK SORTED (determinizm)
```

**`explainability_note` (opsiyonel contract alanı):** Yukarıdaki 6 alanın özet metni (deterministic sırada, pipe (`|`) ayraçlı):
```
"raw:0.72|conf:0.81|gross:36.0bps|net:+12.4bps|rej:score_below_threshold|reg:bull|str:trend_v1|adj:0.95"
```

---

## 7. Correlation / Causation Zinciri (AD-17 — KESİN)

```
StrategySignal (parent, S-STR-01)
  ├── signal_id         = "sig_<ulidish>"        ← parent id (= causation input)
  ├── correlation_id    = "cor_<ulidish>"        ← SABİT (tüm zincir)
  └── causation_id      = "<market_regime_id>"   ← S-STR-01 içinde korunur
            │
            ▼
OpportunityScore (S-OPP-01, BU HİKÂYE)
  ├── score_id          = "opp_<ulidish>"        ← kendi id (yeni)
  ├── correlation_id    = S.correlation_id       ← AYNEN KOPYALA (SABİT)
  └── causation_id      = S.signal_id            ← parent signal id (= causation zinciri)
            │
            ▼
RiskDecision (S-RSK-01 — OOS)
  ├── decision_id       = "dec_<ulidish>"
  ├── correlation_id    = OPPORTUNITY.correlation_id   (AYNI — sabit)
  └── causation_id      = OPPORTUNITY.score_id         (parent score id)
```

**Test Doğrulamaları (T18):**
1. `opp.correlation_id == signal.correlation_id` (aynı, 10x run'da değişmez)
2. `opp.causation_id == signal.signal_id` (parent id)
3. `opp.score_id != signal.signal_id` (yeni ULID üretildi, aynı değil)
4. 10 kez evaluate → corr/caus değerleri HER ZAMAN aynı (deterministik).

---

## 8. EventBus Integration Planı (S-PLN-01)

Eğer `InMemoryTypedEventBus` kullanılıyorsa (S-PLN-01), OpportunityScorer evaluate sonrası opsiyonel olarak 4 event yayınlanabilir. **Bu hikâyede scorer kendisi publish YAPMAZ (AD-9 pure), ama integration test S-PLN-01 bus kullanarak bunu DOĞRULAR (T19):**

| Event Tipi | Ne Zaman | Payload |
|---|---|---|
| `OpportunityScoreCreated` | Her evaluate sonrası | `score_id`, `correlation_id`, `symbol_ref`, `score_total` |
| `OpportunityScoreAccepted` | `actionable = true` ise | Yukarıdaki + `expected_net_edge_bps` |
| `OpportunityScoreRejected` | `actionable = false` ise | Yukarıdaki + `reject_reasons` |
| `OpportunityExplainabilityReady` | Her evaluate sonrası | `score_id` + 6 explainability alanının hash'i |

**Not (AD-9 Purity):** `app/opportunity/base.py` içinde kendisi EventBus publish YAPMAZ. Publish caller (örn S-PLN-01 orchestrator) tarafından yapılır. Scorer SADECE OpportunityScore üretir.

---

## 9. Determinizm (AD-20 — 10x Aynı Çıktı)

Aynı 4 girdi (S, F, R, C, W) verildiğinde:
1. 10 kez `scorer.evaluate(...)` çalıştır
2. `schema_sha256()` değerlerini `set()` içine al
3. `len(set) == 1` OLMAK ZORUNDA (10x aynı hash)
4. Ayrıca `to_sorted_dict()` çıktıları karşılaştırılabilir (deep equal)
5. `score_components` dict key'leri ALFABETİK → sırası 10x için de aynı (deterministic ordering).

**Test (T15):** 2 strateji × 6 rejim × 2 quality (temiz / stale) = 24 case × 10 kez = **240 evaluate**, hepsi için set len=1.

---

## 10. CAP-1 / CAP-2 / CAP-3 + Safety Planı

### CAP-1 (0 `run_mode` / `source_type` branch)
- **Uygulama:** `app/opportunity/` kaynak kodlarında AST taraması (T16)
  - `ast.NodeVisitor` ile `If` node'larının test Attribute alanında `"run_mode"` veya `"source_type"` geçiyor mu?
  - Ayrıca grep: `run_mode|source_type` regex — `app/opportunity/` altında 0 match.
- **Fixture ile bypass YOK:** Değişken adı değiştirerek bypass etme girişimi AST tarayıcı ile engellenmez ama bu hikâyede kodu yazarak bunu yapmamak kuraldır.

### CAP-2 (QualityFlags immutable + Validator 0 call)
- **Immutable test (T17):** QualityFlags örneği → scorer'a ver → test sonrası `id(Q)` korundu mu (deepcopy YOK)? Ayrıca tüm field'lar ilk değerleri ile aynı mı? (assert her field).
- **Validator 0 call test (T17):** `app.contracts.quality.validate_quality_flags` fonksiyonu varsa (ya da benzeri), `unittest.mock.patch` ile izle → çağrı sayısı = 0.

### CAP-3 (Forbidden Libs 0 match + No Network/DB/FS/Exchange/Credential)
- Forbidden 22 lib import scan (T26): `grep -E "import (requests|httpx|websockets|asyncpg|psycopg2|sqlalchemy|pydantic|pandas|numpy|talib|ta|ccxt|kafka|redis|aiohttp|boto3|django|flask|fastapi|torch|tensorflow|catboost)"` → 0 match.
- Network safety (T20): `socket`, `urllib`, `http.client`, `requests` → import 0 match.
- Credential safety (T21): 40+ hassas substring regex (API_KEY, SECRET, BINANCE, BYBIT, PASSWORD, TOKEN, ACCESS_KEY, PRIVATE_KEY, WALLET_MNEMONIC, LEVERAGE, WEBHOOK_URL, PROD_URL, TESTNET_URL...) → 0 match.

### SAFETY (v1 Hard Boundary)
- Short engeli (T24): Eğer StrategySignal `direction="short"` (normalde S-STR-01'de YOK ama gelecekte eklenebilir diye) → `final_score = 0.0`, `actionable = false`, `reject_reasons += "short_direction_forbidden"`.
- Leverage / futures / real order / exchange / API key / network / DB → HEPSİ YOK (T20, T21, T23, T24).
- AD-10 Execution authority yok (T23): `app/opportunity/` içinde RiskDecision/PaperOrder/PaperFill/Position/Portfolio isimlerine import/reference 0.

---

## 11. Acceptance Criteria (AC — 72+ Madde, Grup Lu)

### G1. Invariant & Contract Koruma (12 AC)
- [ ] AC-G1-01: Yeni contract OLUŞTURULMADI; `app/contracts/` klasöründe yeni dosya YOK
- [ ] AC-G1-02: Mevcut 1265/1265 regression test BOZULMADI (sıfır yan etki)
- [ ] AC-G1-03: `pyproject.toml dependencies = []` DEĞİŞMEDİ; 0 yeni runtime dep
- [ ] AC-G1-04: 22 forbidden lib import scan → 0 match (CAP-3)
- [ ] AC-G1-05: `CONTRACT_VERSION = "1.0.0"` contract bump YOK
- [ ] AC-G1-06: `OpportunityScore` 13 zorunlu alan TAMAMEN dolduruldu (opsiyonel 5 izin verildi)
- [ ] AC-G1-07: `OpportunityScore.score_total` her zaman ∈ [0, 1] (clamp test)
- [ ] AC-G1-08: `OpportunityScore.confidence` her zaman ∈ [0, 1]
- [ ] AC-G1-09: `OpportunityScore.policy_version` regex uyumlu (S-CON-02C spec doğrultusu)
- [ ] AC-G1-10: `correlation_id` ULID benzeri ≥8 char; `causation_id` ≥8 char
- [ ] AC-G1-11: `regime_ref` non-empty; `strategy_ref` non-empty; `symbol_ref` canonical Symbol
- [ ] AC-G1-12: `reject_reasons` hiçbir zaman None DEĞİL (boş liste olabilir) ve ALFABETİK sıralı

### G2. 12 Skor Bileşeni Formül (24 AC)
- [ ] AC-G2-01–12: Bileşen 1 (raw score) → 12 formül varyant test (T1 doğrular)
- [ ] AC-G2-13–24: Bileşen 3 (gross) / 4 (fee) / 5 (slippage) / 6 (spread) / 7 (latency) / 8 (net edge) / 9 (cost mult) / 10 (regime adj) / 11 (strategy adj) / 12 (final) → HER BİRİ İÇİN 2+ formül varyant (T3..T12 doğrular: toplam 24 AC)

### G3. Net-of-Cost Model (8 AC)
- [ ] AC-G3-01: `net = gross - fee - slippage - spread - latency` formülü 6 varyantta doğru
- [ ] AC-G3-02: Net edge NEGATİF olabilir; T4-T8 testlerinde en az 1 negatif case var
- [ ] AC-G3-03: Fee, slippage, spread, latency HER BİRİ ≥ 0.0 (negatif maliyet YOK)
- [ ] AC-G3-04: `expected_cost_bps` alanı = fee+slippage+spread+latency toplamı
- [ ] AC-G3-05: Fixture defaults üretim defaults'tan AYRILIDIR (frozen dataclass + fixture override pattern)
- [ ] AC-G3-06: Production eşiklerinin "optimal" olduğu IDDİA EDİLMİYOR (spec içinde açık ifade var)
- [ ] AC-G3-07: `abnormal_spread` True ise slippage 1.3x + spread 1.3x (T5/T6 doğrular)
- [ ] AC-G3-08: 0 cost (tüm maliyetler 0) → net = gross (eşitlik test)

### G4. Confidence Model (6 AC)
- [ ] AC-G4-01: confidence = 0.55*S.c + 0.30*R.c + 0.15*quality_mult (3 varyant)
- [ ] AC-G4-02: Quality 7 bayrak → confidence çarpanları doğru (T2/T13 doğrular)
- [ ] AC-G4-03: S.c=1, R.c=1, quality=1 → confidence ∈ [0.85, 1.0] (blend yüksek)
- [ ] AC-G4-04: S.c=0, R.c=0, quality=0 → confidence = 0.0 (sıfır)
- [ ] AC-G4-05: Invalid → confidence ceiling 0.15
- [ ] AC-G4-06: Quarantined → confidence ceiling 0.15

### G5. Regime + Strategy Adjustment (10 AC)
- [ ] AC-G5-01–06: 6 rejim → doğru regime_adjustment (T10 doğrular, bull=1.0 / bear=0.0 / lv=yüksek / hv=düşük)
- [ ] AC-G5-07–09: 2 strateji + 1 unknown → strategy_adjustment doğru (T11 doğrular: trend 1.0, mom 0.95, unknown 0.3)
- [ ] AC-G5-10: Strategy id+version `OpportunityScore.strategy_ref` içinde KORUNUR (örn `"trend_following_v1:str_01_v1"`)

### G6. Quality Flags 7 Bayrak + Invalid/Quarantine Güvenli Davranış (10 AC)
- [ ] AC-G6-01: stale → skor ×0.60, conf ×0.85
- [ ] AC-G6-02: degraded → skor ×0.60, conf ×0.85
- [ ] AC-G6-03: duplicate → skor ×0.85, conf ×0.90
- [ ] AC-G6-04: missing → skor ×0.85, conf ×0.90
- [ ] AC-G6-05: out_of_order → skor ×0.85, conf ×0.90
- [ ] AC-G6-06: abnormal_spread → skor ×0.80 + maliyetler ×1.3
- [ ] AC-G6-07: invalid → skor ceiling 0.15, conf ceiling 0.15, actionable ZORUNLU False
- [ ] AC-G6-08: quarantined → skor ceiling 0.15, conf ceiling 0.15, actionable ZORUNLU False
- [ ] AC-G6-09 (CAP-2): QualityFlags MUTATE EDİLMEDİ (id korundu + field ilk değerler korundu)
- [ ] AC-G6-10 (CAP-2): Kalite validator çağrı sayısı = 0

### G7. Explainability (6 AC)
- [ ] AC-G7-01: 6 explainability alanı (score_components, weights, dominant_factors, cost_breakdown, regime_evidence, strategy_evidence) MEVCUT
- [ ] AC-G7-02: Tüm dict key'leri ALFABETİK sıralı (deterministic)
- [ ] AC-G7-03: `dominant_factors` en yüksek etki → önce gelir (aynı etki → alfabetik)
- [ ] AC-G7-04: `score_components` (contract alanı) flat dict, 12+ key, alfabetik
- [ ] AC-G7-05: `cost_breakdown_bps` içinde gross/net/total + 4 maliyet tek tek görünüyor
- [ ] AC-G7-06: `explainability_note` pipe ayraçlı, deterministic sıralı

### G8. Corr/Caus / Determinism / CAP-1 / Safety / Bus Integration (12+ AC)
- [ ] AC-G8-01 (AD-17): `opp.correlation_id == signal.correlation_id` (aynı)
- [ ] AC-G8-02 (AD-17): `opp.causation_id == signal.signal_id` (parent id)
- [ ] AC-G8-03 (AD-17): 10x evaluate → corr/caus SABİT (asla değişmez)
- [ ] AC-G8-04 (AD-20): 10x evaluate → `set(schema_sha256) == 1` (aynı çıktı)
- [ ] AC-G8-05 (AD-20): 24 case (T15) → hepsi deterministik
- [ ] AC-G8-06 (CAP-1): `app/opportunity/` AST + grep → `run_mode` / `source_type` dallanması 0
- [ ] AC-G8-07 (AD-9 Purity): No network / no DB / no FS / no exchange (T20 doğrular)
- [ ] AC-G8-08 (Safety): Short engeli; short gelirse skor=0 + actionable=false
- [ ] AC-G8-09 (AD-10): RiskDecision / PaperOrder / PaperFill ÜRETİLMEDİ (T23 doğrular)
- [ ] AC-G8-10 (Bus): S-PLN-01 EventBus üzerinden 4 event publish (T19 doğrular)
- [ ] AC-G8-11: Credential taraması 0 match (T21)
- [ ] AC-G8-12: Full regression 1265 + yeni ≥300 test → 1565+ PASS

---

## 12. Definition of Done (DoD — 16 Madde, KESİN)

- [x] DoD-00: Bu spec dosyası `_bmad-output/implementation-artifacts/` altında KAYDEDİLDİ (S-OPP-01)
- [ ] DoD-01: Toplam test sayısı ≥ 1565 PASS (1265 regression + ≥300 yeni)
- [ ] DoD-02: 12 skor bileşeninin HER BİRİ İÇİN AYRI AYRI saf fonksiyon + ayrı test dosyası MEVCUT (T1..T12)
- [ ] DoD-03: 1265 regression testinin TAMAMI BOZULMADI (sıfır yan etki — import smoke test ile)
- [ ] DoD-04: `pyproject.toml dependencies = []` KORUNDU (0 yeni runtime dep, stdlib-only)
- [ ] DoD-05: 22 forbidden lib → import 0 match (CAP-3)
- [ ] DoD-06: 10x Determinizm: 24 case × 10 kez → set(sha256) len = 1 (AD-20)
- [ ] DoD-07: CAP-1: `app/opportunity/` kaynaklarında `if run_mode/source_type` dallanması 0 finding (AST + grep)
- [ ] DoD-08: CAP-2: QualityFlags immutable (id korundu) + Validator çağrı sayısı = 0
- [ ] DoD-09: Correlation SABİT + Causation = parent signal id (AD-17, 3 doğrulama testi)
- [ ] DoD-10: invalid/quarantine → actionable=False + skor ceiling 0.15 + reject_reason var (güvenli davranış)
- [ ] DoD-11: OpportunityScore sadece scoring sonucudur; RiskDecision/PaperOrder/Execution YOK (AD-10 — 26. T23 testi)
- [ ] DoD-12: Explainability 6 alanı mevcut + deterministic sorted order (T14 testi)
- [ ] DoD-13: 2 strateji (Trend / Momentum) → strategy id+version strategy_ref içinde KORUNDU (T11 testi)
- [ ] DoD-14: Short / Leverage / Futures / Network / Credential / Real Order → HEPSİ YOK (T20, T21, T24 testleri)
- [ ] DoD-15: Fixture defaults ile production frozen defaults AYRILDI (ADN-OPP-01..12 açık kaldı, her biri fixture override edilebilir)

---

## 13. Test Planı (Toplam ≥300, Hedef 616 Test — 26 Dosya)

| Test Grubu | Test # | Dosya | Hedef Test Sayısı | Kapsanan AC/DoD |
|---|---|---|---|---|
| 1. Raw Score | T1 | `test_sopp01_01_raw_opportunity_score.py` | ≥22 | AC-G2-01..06, G1 |
| 2. Confidence | T2 | `test_sopp01_02_confidence_model.py` | ≥24 | AC-G4-01..06, G1 |
| 3. Gross Edge | T3 | `test_sopp01_03_gross_edge_bps.py` | ≥22 | AC-G2-13, G3-01 |
| 4. Fee | T4 | `test_sopp01_04_fee_cost_bps.py` | ≥20 | AC-G2-14, G3-03 |
| 5. Slippage | T5 | `test_sopp01_05_slippage_cost_bps.py` | ≥22 | AC-G2-15, G3-07 |
| 6. Spread | T6 | `test_sopp01_06_spread_cost_bps.py` | ≥20 | AC-G2-16, G3-07 |
| 7. Latency | T7 | `test_sopp01_07_latency_impact_bps.py` | ≥20 | AC-G2-17 |
| 8. Net Edge | T8 | `test_sopp01_08_net_edge_bps.py` | ≥22 | AC-G2-18, G3-01..04/08 |
| 9. Cost Multiplier | T9 | `test_sopp01_09_cost_multiplier.py` | ≥18 | AC-G2-19, G3-05..06 |
| 10. Regime Adj | T10 | `test_sopp01_10_regime_adjustment.py` | ≥26 | AC-G2-20, G5-01..06, DoD-13 |
| 11. Strategy Adj | T11 | `test_sopp01_11_strategy_adjustment.py` | ≥20 | AC-G2-21, G5-07..10, DoD-13 |
| 12. Final Score | T12 | `test_sopp01_12_final_opportunity_score.py` | ≥24 | AC-G2-22..24, G1-07/12 |
| 13. Quality CAP-2 | T13 | `test_sopp01_13_quality_flags_cap2.py` | ≥32 | G6-01..10, DoD-08/10 |
| 14. Explainability | T14 | `test_sopp01_14_explainability.py` | ≥28 | G7-01..06, DoD-12 |
| 15. 10x Determinism | T15 | `test_sopp01_15_determinism_10x.py` | ≥32 | AD-20, DoD-06 |
| 16. CAP-1 AST | T16 | `test_sopp01_16_cap1_ast_branch.py` | ≥20 | CAP-1, DoD-07 |
| 17. CAP-2 Immut. | T17 | `test_sopp01_17_cap2_quality_immutable.py` | ≥20 | CAP-2, DoD-08 |
| 18. Corr/Caus | T18 | `test_sopp01_18_correlation_causation.py` | ≥22 | AD-17, DoD-09 |
| 19. EventBus Int. | T19 | `test_sopp01_19_eventbus_integration.py` | ≥26 | S-PLN-01, G8-10 |
| 20. Network Safety | T20 | `test_sopp01_20_network_safety.py` | ≥18 | AD-9, DoD-07/14 |
| 21. Credential Safety | T21 | `test_sopp01_21_credential_safety.py` | ≥18 | C-FND-03, DoD-14 |
| 22. Contract Output | T22 | `test_sopp01_22_output_contract.py` | ≥26 | G1-06..11 |
| 23. No Exec Auth. | T23 | `test_sopp01_23_no_execution_authority.py` | ≥16 | AD-10, DoD-11 |
| 24. Safety Boundary | T24 | `test_sopp01_24_safety_boundary.py` | ≥18 | v1 Boundary, DoD-14 |
| 25. Full Chain Int. | T25 | `test_sopp01_25_integration_full_chain.py` | ≥28 | E2E S-STR-01→S-OPP-01 |
| 26. Full Regression | T26 | `test_sopp01_26_full_regression_smoke.py` | ≥24 | DoD-01/03/04/05 |
| | | **TOPLAM** | **616 test (≥300 hedef)** | 72+ AC / 16 DoD HEPSİ |

---

## 14. Open Decisions (ADN-OPP-01..12 — Üretim Kararları AÇIK KALDI)

> **KURAL:** Aşağıdaki 12 karar bu hikâyede KALICI OLARAK VERİLMEDİ. Fixture/test defaults var ama production defaults (`frozen=True` dataclass) sadece "sensible başlangıç" değerleridir. Kalıcı karar ayrı ADN toplantısında alınır.

| No | Açık Karar | Fixture Default (bu hikâyede) | Kalıcı Karar Ne Zaman |
|---|---|---|---|
| ADN-OPP-01 | Fee maliyeti: taker fee + network fee bps | 10 bps + 0.5 bps = 10.5 bps | Live trading öncesi (Exchange + Broker anlaşması sonrası) |
| ADN-OPP-02 | Slippage eğrisi (base + vol exponent) + depth factor | base=3 bps, exp=1.5, depth=1.0 | Orderbook derinliği feature_vector'a eklendikten sonra |
| ADN-OPP-03 | Spread maliyeti min fallback + abnormal_penalty | min=1 bps, abnormal=1.3x | Canlı spread gözlemi sonrası |
| ADN-OPP-04 | Latency (ms) + hedef + sensitivity | latency=3ms, target=1ms, sens=2.0 | Gerçek network latency ölçümleri sonrası |
| ADN-OPP-05 | Raw score ağırlıkları (strat / regime / feature) | 0.55 / 0.30 / 0.15 | Backtest (E-BKT) sonuçlarına göre kalibrasyon |
| ADN-OPP-06 | Confidence ağırlıkları + actionable eşik (score + net edge) | conf=0.55/0.30/0.15 ; thr=0.55 score + 5.0 bps net edge | Backtest + simulation (E-SIM) sonrası |
| ADN-OPP-07 | 7 kalite bayrağı penalty (stale/degraded 0.60 vs) | §5.3 tablosu (stale=0.60, invalid=0.15 ceiling) | Saha kalite gözlemi sonrası |
| ADN-OPP-08 | 6 rejim × 2 strateji adj. matrisi | §4.10 (bull=1.0, bear=0.0, trend=1.0, mom=0.95) | Backtest regime split sonuçları sonrası |
| ADN-OPP-09 | Cost multiplier (net pozitif=1.0 / negatif=0.15) | 1.00 / 0.15 | Backtest cost/edge analizleri sonrası |
| ADN-OPP-10 | `gross_edge_scale_bps` (birim başı beklenen edge) | 50 bps | Backtest expected edge dağılımı sonrası |
| ADN-OPP-11 | `expected_hold_bars` default (opsiyonel alan) | None / fixture=12 | Bar süresi analizi sonrası |
| ADN-OPP-12 | Kalıcı production decision tarihi | Bu hikâyede AÇIK (yok) | E-BKT + E-SIM + E-RSK tamamlandıktan sonra |

---

## 15. Dependencies & Regression Korunması

### Dependencies (SIFIR — Değişmez)
- `pyproject.toml dependencies = []` → %100 KORUNUR.
- Yeni runtime bağımlılık: 0.
- Sadece stdlib: `dataclasses`, `typing`, `hashlib`, `ast`, `re`, `json` — Python 3.14+ ile mevcut.

### Regression (1265 → 1565+ — Sıfır Kayıp Hedefi)
- Korunacak hikâyeler (test dosyaları DEĞİŞTİRİLMEYECEDİR):
  - S-RDH-01 (68) / S-RDH-02 (64) / S-PLN-01 (42)
  - S-CON-02A (104) / S-CON-02B (71) / S-CON-02C (93)
  - S-FEA-01 (120) / S-REG-01 (302) / S-STR-01 (401)
  - TOPLAM: **1265 PASS** (bu hikâyeden ÖNCE, a471a6e)
- Hedef: **1265 + ≥300 = 1565+ PASS** (bu hikâyeden SONRA)
- Yalnızca YENİ klasör eklenecektir: `app/opportunity/` (kaynak) + `tests/opportunity/` (test). Mevcut klasörlerde 0 satır değişiklik.

---

## 16. Implementation Readiness (Uygulama Hazırlığı)

| Madde | Durum | Açıklama |
|---|---|---|
| Spec Tamam mı? | ✅ EVET | 16 bölüm, 72+ AC, 16 DoD, 26 test dosyası planı, 12 ADN — HEPSİ TAMAM |
| Contract Hazır mı? | ✅ EVET | Mevcut `app/contracts/opportunity.py` S-CON-02C v1 — Yeni contract GEREK YOK |
| Ön Hikâyeler Hazır mı? | ✅ EVET | S-FEA-01 (FV), S-REG-01 (Regime), S-STR-01 (Signal) — HEPSİ 100% TAMAMLANDI + AUDIT |
| Dependency Durumu | ✅ TEMİZ | 0 yeni dep, pyproject deps=[] korunur, 22 forbidden lib 0 match |
| CAP-1/2/3 Uyumluluk | ✅ PLANLANDI | Her biri için özel test dosyaları (T16, T17, T20/21/26) mevcut |
| Determinizm Planı | ✅ TAM | 10x 24 case T15 dosyası + to_sorted_dict + SHA-256 |
| Safety / OOS | ✅ KESİN | 8-item safety + 13-item OOS listesi; AD-10 exec authority yok |
| Corr/Caus Zinciri | ✅ KESİN | correlation sabit, causation = parent signal_id |
| Quality Behavior | ✅ AÇIK | 7 bayrak tablo + invalid/quarantine güvenli davranış |
| Cost Model | ✅ AÇIK | 4 maliyet + gross/net formül TAM |
| Explainability | ✅ AÇIK | 6 alan + deterministic sorted order TAM |
| Test Hedefi | ✅ AŞILDI | 616 hedef ≥ 300 minimum |
| Regression Hedefi | ✅ KORUNUYOR | 1265 + 616 = 1881 maks (1565+ minimum garanti) |
| Fixture/Prod Ayrımı | ✅ KESİN | Frozen defaults + fixture override kalıbı; ADN-OPP-01..12 AÇIK |
| Sonraki Hikâye Hazır mı? | ⏳ BEKLİYOR | S-RSK-01 Risk Engine — bu hikâye bittikten SONRA (şimdilik YOK) |

**Sonuç:** S-OPP-01 — **IMPLEMENTASYONA HAZIR (Ready-for-Dev).** Onay sonrası `bmad-dev-story` ile kodlama aşamasına geçilebilir.

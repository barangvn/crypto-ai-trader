---
story_id: "S-RSK-01"
story_key: "S-RSK-01"
title: "Independent Risk Engine + Fail-Closed Risk Gate (Limits, Position-Sizing, Kill-Switch, Quality Gates, 20-Component Risk Score, Deterministic AD-20, CAP-1/CAP-2/CAP-4, AD-11/AD-19/AD-20)"
status: "ready-for-dev"
created: 2026-08-28
updated: 2026-08-28
author: "bmad-create-story v1"
tags: [risk_engine, fail_closed, risk_gate, limits_snapshot, kill_switch, position_sizing, quality_gates, AD-11, AD-19, AD-20, CAP-1, CAP-2, CAP-4, long_only, stdlib_only]
epic: "E-RSK — Independent Risk Engine & Kill Switch (Epic 9 — AD-11 Final Gate)"
baseline_commit: "df19517 feat: implement deterministic opportunity scoring"
previous_story: "S-OPP-01 (461 yeni matrix test sonrası 1876/1877 PASS — COMMIT READY)"
next_stories:
  - "S-RSK-02: CAP-4 direct proof (RiskDecision.approved → PaperOrder allowed; rejected → forbidden)"
  - "S-RSK-03: Adaptive Position Sizing Methods Suite (Kelly, Risk Parity, Vol-Targeted, Fixed Notional)"
  - "S-RSK-04: Stale/Adapter-Failure + Emergency Stop Downstream Hardening (AD-5 + AD-19)"
contract_version_preserved: "1.0.0"
contracts_used:
  - "RiskDecision (app/contracts/risk.py §3.1) — S-CON-02B v1, YENİ CONTRACT YOK"
  - "LimitsSnapshot (app/contracts/risk.py LimitsSnapshot nested) — S-CON-02B §3.1.1, 10 zorunlu alan, max_leverage_allowed HARD=1"
  - "PositionSizingSpec (app/contracts/risk.py) — base_qty | quote_qty + notional ≥ 0 Decimal + method string"
  - "KillSwitchStateSpec (app/contracts/risk.py) — global_kill bool + per_symbol dict + reason|null"
  - "RiskDecisionResult enum — approved/rejected (TAM 2 DEĞER, AD-11)"
  - "OpportunityScore (app/contracts/opportunity.py) — S-OPP-01 çıktısı, mevcut"
  - "StrategySignal (app/contracts/strategy.py) — S-STR-01 çıktısı, direction ∈ long/flat/hold, short YOK"
  - "MarketRegime (app/contracts/regime.py) — S-REG-01 AD-8 6-state (bull/bear/sideways/hv/lv/tu)"
  - "PortfolioSnapshot (app/contracts/portfolio.py) — S-CON-02B §3.5, Single Writer AD-7/AD-13/AD-24 — sadece read-only view"
  - "QualityFlags (app/contracts/quality.py) — frozen, 7 bayrak (stale, missing, duplicate, out_of_order, invalid, quarantined, degraded) + abnormal_spread, YENİ FIELD EKLEME — fallback kullan, contract bump yok"
  - "InMemoryTypedEventBus (app/platform/event_bus.py) — S-PLN-01 typed bus, EventBus integration test"
test_baseline_count: 1876
test_baseline_passed: 1876
test_baseline_1skipped: "test_matrix_01_gross_edge_boundaries.py L67: flat/hold only → LONG case SKIP; production etkisi YOK, no AC/DoD ihlali"
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
  S-OPP-01: 611 (+461 yeni matrix)
runtime_dependencies_new_allowed: 0
v1_hard_boundary_long_only: true
new_contract_allowed: false
risk_policy_version_story_default: "risk_policy_v1.0.0"
risk_scorer_version_story_default: "risk_01_v1"
max_leverage_allowed_hard: 1
kill_switch_reason_default_global: "GLOBAL_KILL_SWITCH_OPERATOR"
kill_switch_reason_default_emergency: "EMERGENCY_STOP_ACTIVE"
valid_until_default_ms: 30_000
risk_score_threshold_default_approval: 0.40
risk_score_threshold_default_observation: 0.70
risk_score_max: 1.0
risk_score_min: 0.0
duplicate_window_default_as_of_delta_ms: 60_000
cooldown_default_ms: 120_000
decay_half_life_drawdown_default_ms: 3_600_000
---

# S-RSK-01 — Independent Risk Engine + Fail-Closed Risk Gate

> **KESİN — HARD KRİTER (KULLANICI TARAFINDAN VERİLDİ, DEĞİŞMEZ):**
>
> 1. **Mevcut 1876 TEST (S-RDH/RDH-2/PLN/CON-02A/B/C/FEA/REG/STR/OPP) — SADECE 1 SKIP** — BU HİKÂYE SONRASI **EN AZ 1876 + ≥200 = 2076+ TEST** hedeflenir. **1876 regression BOZULMAYACAK.**
> 2. **S-CON-02B RiskDecision/LimitsSnapshot/KillSwitch/PositionSizing 5 Contract Group (§3.1–3.5) — %100 KORUNUR. Public alan, enum, import, sabit, __post_init__ validasyonu DEĞİŞMEZ.**
> 3. `pyproject.toml dependencies = []` değişmez. Sadece stdlib. Pydantic/msgspec/cattrs/pandas/numpy/ta/ta-lib/ccxt YASAK.
> 4. `CONTRACT_VERSION = "1.0.0"` SABİT DEĞİŞMEZ. QualityFlags'e YENİ FIELD EKLENMEZ. Abnormal spread fallback: `getattr(q, "abnormal_spread", None) or (fv.features.spread_bps >= 100)`.
> 5. **BAĞIMSIZLIK:** Risk Engine tek final approval authority. StrategySignal, OpportunityScore, AI, Regime, Features — HİÇBİRİ `approved` üretemez. SADECE `app/risk/` → `RiskDecision` → `decision ∈ {approved, rejected}` (2 değer, enum'da başka yok, AD-11).
> 6. **FAIL-CLOSED DEFAULT:** Her malformed input / missing field / stale data / invalid data / quarantined / missing portfolio snapshot / expired signal / invalid limits / score out-of-range / calculation error → `decision = rejected` + `reason_codes[]` en az 1 öğe. RiskEngine.exception NEVER → approved.
> 7. **PAPER/ORDER SAFETY:** Bu hikâyede PaperOrder/PaperFill/ExecutionSimulator/FillModel/Backtest YOK (OOS). RiskDecision.approved → PaperOrder allowed kanıtı (CAP-4) S-RSK-02'YE BIRAKILIR. Sadece *contract-based gate behavior* + *EventBus integration proof* hazırlanır.
> 8. **DETERMINIZM (AD-20):** Aynı typed inputs tuple → 10 kez RiskEngine.evaluate → 10 kez `to_sorted_dict()` eşit; 10 kez `schema_sha256()` set len=1.
> 9. **SAFETY (11 Öğe):** short YOK, futures YOK, leverage>1 YOK (LimitsSnapshot.max_leverage_allowed zorunlu 1, validation error olursa rejected), live execution YOK, exchange YOK, API YOK, credentials YOK, network YOK, database YOK, AI training YOK, ML model YOK.

---

## 1. Amaç ve Genel Bakış

**User Story (BDD):**
> Bir Portfolio Operatorü / Paper Execution Engine olarak,
> SADECE 5.5 adet typed girdi verildiğinde:
>   1. **OpportunityScore** (S-OPP-01 çıktısı; score_total, actionable, expected_edge_bps, expected_cost_bps, symbol_ref, correlation_id, causation_id, quality_flags, score_components)
>   2. **StrategySignal** (S-STR-01; strategy_id/version, direction ∈ long/flat/hold, signal_strength ∈ [0,1], confidence ∈ [0,1], stop/tp policy refs)
>   3. **MarketRegime** (S-REG-01 AD-8 6-state; regime, confidence, 6-scores dict, detector_version)
>   4. **PortfolioSnapshotView (readonly)** (S-CON-02B §3.5 projection; cash_quote, equity_quote, exposure_notional, drawdown_pct, peak_equity, realized_pnl_quote_24h, positions_snapshot summary, consec_loss_count, account_ref, ts, correlation_id)
>   5. **LimitsSnapshot (input)** (S-CON-02B §3.1.1 nested, 10 zorunlu alan — risk engine bunu *re-emit eder* unchanged ve doğrular)
>   5.5. **RiskContext (frozen, helper)** (KillSwitchStateSpec + GlobalEmergencyStopFlag + symbol_killswitch dict + current_as_of UTC Instant + duplicate_decision_window + cooldown_window + risk_score_threshold_approval + risk_score_threshold_observation + valid_until_default_ms; frozen=True, fixture override edilebilir — production defaults KESİN KARAR DEĞİL, ADN açık kalır)
> **Fail-Closed, Bağımsız, Deterministik, 20-Component RiskScore + 20 Check Pipeline** üreterek **TEK BİR Nihai Karar: RiskDecision** (S-CON-02B §3.1, YENİ CONTRACT YOK) üretmek istiyorum,
> Öyle ki:
> - 20 Bireysel Check PASS/REJECT + her reject için Deterministik `reason_code` (string, extensible, sözleşmeli kod listesi)
> - 20 Bileşen RiskScore (min/max normalize, ağırlıklandırılmış toplam, threshold bazlı final karar)
> - QualityFlags (7 bayrak + abnormal_spread fallback) OKUNUR, MUTATE EDİLMEZ, VALIDATOR TEKRAR ÇAĞIRILMAZ (CAP-2)
> - Kill Switch: global_kill=True → TÜM karar rejected (reason=KILL_SWITCH_ACTIVE); emergency_stop=True → TÜM rejected (EMERGENCY_STOP); per_symbol[X]=True → X için rejected (SYMBOL_KILL_SWITCH)
> - Sizing: Deterministik bounded (5 alt kural: max_position_notional_per_symbol, max_exposure_notional_total - current_exposure, max_order_notional_default, available_cash_quote, risk_budget_drawdown_headroom) - min() 5'inden; base_qty/quote_qty/notional ≥ 0 Decimal, short YOK, leverage>1 YOK, size=0 OLARAK SONUÇLANIR SADECE approved OLMAYANLARDA
> - `RiskDecision.decision ∈ approved/rejected` (2 değer, başka yok, AD-11)
> - Correlation: RiskDecision.correlation_id = OpportunityScore.correlation_id (Zincir SABİT); causation_id = OpportunityScore.score_id (parent event id)
> - `app/risk/` KAYNAK KODUNDA: `if run_mode == ` / `if source_type == ` BRANCH YOK (AST visitor 0 finding, CAP-1)
> - No execution authority: RiskDecision → PaperOrder üretilmez (S-RSK-02 OOS), sadece onay/red üretir
> - 2. Seviye fail-safe: Eğer 20-check pipleline HERHANGİ bir exception yakalarsa → rejected + INTERNAL_CALCULATION_ERROR, sizing 0, limits unchanged (AD-19)

### Hedef
Mevcut **RiskDecision / LimitsSnapshot / KillSwitchStateSpec / PositionSizingSpec** Contractları (S-CON-02B, `app/contracts/risk.py`) **DEĞİŞTİRİLMEDEN** (public alan/enum/import/validation %100 korundu), tek saf (pure) Risk Engine modülü (`app/risk/base.py`) + 1 frozen defaults helper (`RiskEngineDefaults`, `RiskPolicyWeights`, `RiskContext`) + 1 `RiskDecision.derive_from_envelope(...)` convenience factory (opsiyonel) oluştur.

**Bu hikâyede SADECE:** 4.5 typed input → tek output RiskDecision (tek yönlü deterministic fonksiyon). 20 check + 20 risk component + 5-rule sizing + correlation/causation propagation + EventBus integration test.

**Hiçbir şekilde:** PaperOrder, PaperFill, FillModel, Backtest, Position MUTATE, PortfolioSnapshot WRITE — HEPSİ OOS (AD-7/AD-13/AD-24, tek writer = Portfolio Simulator). Risk Engine SADECE PortfolioView READ-ONLY tüketir.

### Ön Koşullar (HİKÂYE ÖNCESİ — BAŞLANGIÇTA DOĞRULANACAK)
✅ **1876 / 1877 (1 SKIP) FULL regression PASS** (S-RDH-01 68, S-RDH-02 64, S-PLN-01 42, S-CON-02A 104, S-CON-02B 71, S-CON-02C 93, S-FEA-01 120, S-REG-01 302, S-STR-01 401, S-OPP-01 611) — BU HİKÂYE SONRASI EN AZ `1876 + ≥200 = 2076+` test. **1876 BOZULMAYACAK.**
✅ `app/contracts/risk.py` mevcut (analiz edildi): RiskDecisionResult (approved/rejected, 2 değer), LimitsSnapshot (10 alan, max_leverage_allowed=1 zorunlu), PositionSizingSpec (notional Decimal ≥0), KillSwitchStateSpec (global_kill + per_symbol dict + reason), RiskDecision dataclass decision_id, decision, reason_codes, position_sizing, limits_snapshot (UNCHANGED snapshot), kill_switch_state (snapshot), stop_loss_ref/take_profit_ref, valid_until (Instant ZORUNLU), approval_chain, correlation_id, causation_id.
✅ `app/contracts/quality.py` → QualityFlags frozen (7 bayrak + abnormal_spread field YOK → fallback kullan).
✅ `pyproject.toml dependencies = []` — stdlib-only.
✅ `CONTRACT_VERSION = "1.0.0"` (BU HİKÂYEDE BUMP YOK).
✅ S-PLN-01 EventBus mevcut (`InMemoryTypedEventBus` publish/subscribe_typed/dead_letters) — RiskDecision event flow integration testi.
✅ Hard Safety: 11 yasaklı (short, futures, leverage>1, live exec, exchange, API, credentials, network, DB, AI training, ML model import) → mevcut 1876 testle kilitli.

### Değişmez Mimari Kurallar (HİÇBİR KOŞULDA İHLAL EDİLEMEZ)
| Kural | Kaynak | Davranış |
|---|---|---|
| AD-11 Risk Is Final Gate | ARCH §AD-11, Brief §8 Risk, PRD FR-052 | BAĞIMSIZ. Strategy, OpportunityScore, AI, Features, Regime — APPROVED üretemez. Risk Engine TEK AUTHORITY. |
| AD-19 Fail-Closed Default | ARCH §AD-19 | Her exception / malformed / missing / stale / invalid / quarantined → rejected + reason_codes≥1. Sizing 0. Limits unchanged. |
| AD-20 Determinism | ARCH §AD-20 | Aynı 4.5 girdi 10× → 10× RiskDecision schema_sha256 tekil (set len=1). |
| AD-17 Corr/Caus Chain (5. Halka) | ARCH §AD-17 | correlation_id = OpportunityScore.correlation_id. causation_id = OpportunityScore.score_id. |
| AD-8 Regime Read-Only | ARCH §AD-8 | Risk, MarketRegime'i salt okur; rejim engine çağırmaz. |
| AD-13/7/24 Single-Writer | ARCH §AD-13/7/24 | Risk, Position/Portfolio/Fill/Order — YAZMAZ. Bunlar SADECE Portfolio Simulator tarafından yazılır (OOS). |
| AD-10/Strategy Pure | ARCH §AD-10, §AD-9 | Strategy/Opportunity no execution authority. Risk Engine no strategy mutation. |
| CAP-1 Replay/Live Parity | SPEC §CAP-1 | `app/risk/` içinde 0 run_mode/source_type branch. AST scan 0 finding. |
| CAP-2 Quality Preserve | SPEC §CAP-2 | QualityFlags frozen. OKUNUR, MUTATE 0. Validator çağrısı 0. |
| CAP-4 Setup (Onay Kapısı) | SPEC §CAP-4 + EPICS E-RSK-02 notu | `RiskDecision.approved = true` → PaperOrder allowed (kanıt: correlation_id bazlı EventBus integration test — S-RSK-02 tam test; bu hikâyede sadece contract davranışı + bus publish). |
| v1 Hard Safety (11) | PRD Hard Boundaries, CONTRACTS LimitsSnapshot | short enum YOK, leverage>1 validation ERROR (→ rejected), futures YOK, credentials/network/DB YOK. |
| No Contract Bump | User HARD Rule | RiskDecision/Limits/Kill/Sizing public API %100 korundu. QualityFlags yeni bayrak YOK. |
| Fixture ≠ Production | User KURAL | Production defaults frozen=True dataclass. Fixture/test replace() override. ADN açık kalır. |

---

## 2. 20'li Risk Check Listesi (Hepsi PASS/REJECT + Deterministik reason_code)

Her check: `(check_id: int, check_name: str, reason_code: str, fail_closed: bool = True)` → Result: PASS / REJECT. REJECT ise `reason_codes.append(reason_code)`. **20/20 PASS → pipeline devam (sonra risk score threshold). 1+ REJECT → decision = rejected (fail-closed).**

| # | Check Adı | Geçme Koşulu | Fail → reason_code | Öncüllük (Sıra) |
|---|---|---|---|---|
| C01 | **Global Kill Switch** | `risk_context.kill_switch.global_kill is False` | `KILL_SWITCH_GLOBAL_ACTIVE` | 1 (EN ÖNCE) |
| C02 | **Global Emergency Stop** | `risk_context.emergency_stop_active is False` | `EMERGENCY_STOP_ACTIVE` | 2 |
| C03 | **Per-Symbol Kill Switch** | `symbol not in risk_context.kill_switch.per_symbol or risk_context.kill_switch.per_symbol[symbol] is False` | `KILL_SWITCH_SYMBOL_ACTIVE` | 3 |
| C04 | **LimitsSnapshot Valid (Contract)** | `LimitsSnapshot.__post_init__` OK (max_leverage_allowed==1, drawdown ∈[0,1], consec≥0) | `LIMITS_SNAPSHOT_INVALID` | 4 |
| C05 | **PortfolioSnapshot Mevcut** | `portfolio_view is not None AND portfolio_view.ts >= as_of - stale_threshold (ADN default 5min)` | `PORTFOLIO_VIEW_MISSING` + `PORTFOLIO_VIEW_STALE` | 5 |
| C06 | **Quality: Invalid** | `quality_flags.invalid is False` | `QUALITY_INVALID` | 6 |
| C07 | **Quality: Quarantined** | `quality_flags.quarantined is False` | `QUALITY_QUARANTINED` | 7 |
| C08 | **Quality: Stale (Downstream Data)** | `quality_flags.stale is False OR (stale AND expected_net_edge > STALE_OK_EDGE — default OFF: fail_closed)` | `QUALITY_STALE` | 8 |
| C09 | **Quality: Degraded (Ceiling)** | `quality_flags.degraded is False → check C19 risk score multiplier 0.60 ceiling` | `QUALITY_DEGRADED_PENALTY` | 9 |
| C10 | **Quality: Missing/Out-of-Order/Duplicate** | `(q.missing or q.duplicate or q.out_of_order) is False → multiplier 0.85` | `QUALITY_SEQUENCE_ISSUES` | 10 |
| C11 | **Invalid Opportunity Score** | `opp_score.score_total ∈ [0,1] AND opp_score.actionable is True AND opp_score.expected_edge_bps is not None` | `OPPORTUNITY_INVALID` + `OPPORTUNITY_NOT_ACTIONABLE` + `OPPORTUNITY_EXPECTED_EDGE_MISSING` | 11 |
| C12 | **Net-of-Cost Edge Pozitif** | `opp_score.expected_edge_bps > MIN_NET_EDGE_BPS (default 0.0 → positive)` | `EXPECTED_NET_EDGE_NON_POSITIVE` | 12 |
| C13 | **Invalid Strategy Signal** | `sig.direction in {long,flat,hold} AND sig.signal_strength ∈ [0,1] AND sig.confidence ∈ [0,1]` | `SIGNAL_INVALID` | 13 |
| C14 | **Strategy Direction Long-Only** | `sig.direction == long` (flat/hold/short → decision=rejected v1 approved YOK; sadece PASS'ta approved) | `SIGNAL_DIRECTION_NOT_LONG` + `SIGNAL_DIRECTION_FLAT` + `SIGNAL_DIRECTION_HOLD` | 14 |
| C15 | **Signal/Score Expiry** | `as_of - opp_score.created_ts < score_valid_until_ms (default 5min)` AND `as_of - sig.created_ts < signal_valid_until_ms (default 5min)` | `OPPORTUNITY_SCORE_EXPIRED` + `SIGNAL_EXPIRED` | 15 |
| C16 | **Duplicate Decision (Window)** | `(correlation_id, symbol, as_of_round_1s) not in duplicate_tracker_memory dict (rolling last 60s or ADN)` | `DUPLICATE_DECISION_WINDOW` | 16 |
| C17 | **Cooldown (Symbol + Strategy)** | `last_approved_ts[symbol, strategy_id] is None or as_of - last > cooldown_window_ms` | `COOLDOWN_ACTIVE` | 17 |
| C18 | **Limits: Max Position Notional** | `(proposed_sizing_notional ≤ limits.max_position_notional_per_symbol) after initial sizing calc (C26 sonrası assert)` | `LIMIT_MAX_POSITION_NOTIONAL` | 18 |
| C19 | **Limits: Max Exposure (Total - Current) Headroom** | `current_exposure + proposed_notional ≤ limits.max_exposure_notional_total` | `LIMIT_MAX_EXPOSURE` | 19 |
| C20 | **Limits: Daily Loss / Drawdown / Consecutive Losses** | `current_daily_pnl ≥ -limits.max_daily_loss_notional AND current_drawdown_pct ≤ limits.max_drawdown_pct AND current_consecutive_losses ≤ limits.max_consecutive_losses` | `LIMIT_DAILY_LOSS_BREACH` + `LIMIT_MAX_DRAWDOWN_BREACH` + `LIMIT_CONSECUTIVE_LOSSES_BREACH` | 20 |

### Toplam: 20 Bireysel Check (132+ ayrı reason_code extensible)
20 check'ten **EN AZ 1 TANE REJECT** ise → `decision = rejected` (fail-closed). **20/20 PASS** ise → 20-component Risk Score uygulanır:

---

## 3. Risk Score Formülü (20 Component + Ağırlıklandırılmış Normalize Toplam + Threshold + Quality Multiplier)

### Adım 3a. 20 Risk Bileşeni (her biri ∈ [0, 1])
Her bir bileşen 0 → DÜŞÜK RİSK (iyi) ; 1 → YÜKSEK RİSK (kötü). 1 = kötü (red) yaklaşım.

| Bileşen ID | Bileşen Adı | Hesaplama Formülü (Deterministik) |
|---|---|---|
| R01 | Quality Flag Risk | weight_stale*q.stale + weight_missing*q.missing + weight_dup*q.duplicate + weight_ooo*q.out_of_order + weight_degraded*q.degraded + 1.0*(q.invalid or q.quarantined) |
| R02 | Abnormal Spread Risk (fallback) | `if (q.abnormal_spread if hasattr(q,'abnormal_spread') else fv.features.get('spread_bps',0) >= 100): min(1.0, spread_bps / 500) else fv.features.spread_bps / 500` (0→0, 500bps→1.0) |
| R03 | Expected Edge Risk | `clip(1 - (expected_edge_bps / MIN_POSITIVE_TARGET_EDGE_BPS), 0, 1)` (düşük kenar → yüksek risk) |
| R04 | Expected Cost Over Edge Risk | `clip(expected_cost_bps / max(EPS, expected_edge_bps), 0, 1)` (cost/edge oran → risk) |
| R05 | Opportunity Confidence Risk | `1 - opp_score.confidence ∈ [0,1]` |
| R06 | Signal Strength Extremity Risk | `abs(signal_strength - 0.50) * 2 → asimetri riski` |
| R07 | Signal Confidence Risk | `1 - signal.confidence ∈ [0,1]` |
| R08 | Strategy-Regime Compatibility Risk | regime_strategy_penalty_matrix[strategy_id][regime_name] ∈ [0,1] (Trend/Bull:0.05, Trend/Sideways:0.60, Momentum/HV:0.70, Momentum/LV:0.40, TU any:0.55, Bear any long:0.65) |
| R09 | Regime Confidence Risk | `1 - regime.confidence ∈ [0,1]` |
| R10 | Volatility Regime Risk | f(regime): HV→0.90, LV→0.10, Bull→0.30, Bear→0.55, Sideways→0.35, TU→0.70 |
| R11 | Drawdown vs Limit Risk | `clip(current_drawdown_pct / max(0.01, max_drawdown_pct), 0, 1)` |
| R12 | Daily Loss vs Limit Risk | `clip( (-current_daily_pnl) / max(EPS, max_daily_loss_notional), 0, 1)` |
| R13 | Consecutive Losses Risk | `clip(current_consecutive_losses / max(1, max_consecutive_losses), 0, 1)` |
| R14 | Portfolio Exposure Utilization Risk | `clip(current_exposure_notional / max(EPS, max_exposure_notional_total), 0, 1)` |
| R15 | Per-Symbol Concentration Risk | `clip( (current_symbol_exposure + proposed_notional) / max(EPS, max_exposure_notional_total) * CONCENTRATION_DIVERSIFIER_N (default 3.0), 0, 1)` |
| R16 | Available Cash Utilization Risk | `clip(proposed_notional / max(EPS, available_cash_quote), 0, 1)` |
| R17 | Risk Budget Headroom Risk | `clip( current_drawdown_pct / max(EPS, risk_budget_drawdown_headroom default 0.8*max_drawdown_pct), 0, 1)` |
| R18 | Duplicate / Cooldown Staleness Risk | cooldown active→0.90 else duplicate 1.0 else 0.05 |
| R19 | Slippage Latency Model Risk | `clip( (slippage_bps_default + latency_bps_default) / max(EPS, expected_edge_bps), 0, 1)` |
| R20 | Signal-Score Divergence Risk | `clip( abs(opp_score.score_total - (regime.confidence*0.3 + sig.confidence*0.3 + sig.strength*0.4)), 0, 1) / 0.50` — normalize |

### Adım 3b. Ağırlıklar (Toplam = 1.000 exactly)
```python
# RiskPolicyWeights (frozen=True, fixture override edilebilir, production KESİN DEĞİL — ADN açık)
DEFAULT_WEIGHTS: dict[str, float] = {
    "w_quality":            0.120,  # R01
    "w_spread":             0.070,  # R02
    "w_expected_edge":      0.090,  # R03
    "w_cost_ratio":         0.060,  # R04
    "w_opp_conf":           0.070,  # R05
    "w_sig_strength":       0.030,  # R06
    "w_sig_conf":           0.060,  # R07
    "w_strat_regime":       0.080,  # R08
    "w_regime_conf":        0.050,  # R09
    "w_regime_type":        0.050,  # R10
    "w_drawdown":           0.060,  # R11
    "w_daily_loss":         0.050,  # R12
    "w_consec_losses":      0.040,  # R13
    "w_exposure_util":      0.040,  # R14
    "w_concentration":      0.050,  # R15
    "w_cash_util":          0.030,  # R16
    "w_budget_headroom":    0.030,  # R17
    "w_dup_cooldown":       0.030,  # R18
    "w_slip_lat_model":     0.020,  # R19
    "w_sig_score_div":      0.030,  # R20
}  # sum = 1.000 exactly
```

### Adım 3c. Quality Multiplier (CAP-2 ile AYNI — upstream değerleri OKUNUR, MUTATE 0)
```
if invalid or quarantined  → QUALITY_MULT = 0.15 (ceiling, fail-close)
elif stale or degraded    → QUALITY_MULT = 0.60
elif missing or dup or ooo → QUALITY_MULT = 0.85
else (clean)               → QUALITY_MULT = 1.00
```

### Adım 3d. Final Risk Score
```
weighted_sum = Σ ( R01*w_quality + R02*w_spread + ... + R20*w_sig_score_div )  # ∈ [0,1]
quality_adjusted_score = clip( weighted_sum * (1 / max(0.40, QUALITY_MULT)) , 0.0, 1.0)
# NOT: Kalite kötüyse risk artar (1/mult amplifikasyon). 0.40 floor — çarpan 2.5x'ten büyük değil (stabilizör).
```

### Adım 3e. Final Karar (20/20 check PASS sonrası)
```
if quality_adjusted_score  < risk_score_threshold_approval (default 0.40) → approved
elif quality_adjusted_score < risk_score_threshold_observation (default 0.70) → rejected (reason=RISK_SCORE_OBSERVATION_BAND)
else → rejected (reason=RISK_SCORE_TOO_HIGH)
```

---

## 4. Position Sizing Kuralları (5 Alt Kural — Min Of, Deterministik, Bounded, Non-Negative, Decimal)
SADECE `decision=approved` OLDUĞUNDA çalışır. Diğer tüm durumlarda `position_sizing.notional = Decimal("0")`.

```python
# 5 kural (her biri tek bir notional üst sınır üretir — hepsinden minimumu)
def compute_position_sizing_notional(
    opp: OpportunityScore,
    sig: StrategySignal,
    pv: PortfolioView,
    limits: LimitsSnapshot,
    symbol_price_ref: Decimal,
    ctx: RiskContext,
) -> tuple[Decimal, Decimal, Decimal, str]:
    # 1. Max position notional per symbol
    L1 = limits.max_position_notional_per_symbol
    # 2. Total exposure headroom (max_exposure - current)
    headroom_exp = max(Decimal("0"), limits.max_exposure_notional_total - limits.current_exposure_notional)
    L2 = headroom_exp
    # 3. Max order notional (policy default — örn 5_000 USDT, ADN)
    L3 = ctx.max_default_order_notional
    # 4. Available cash (v1 long-only — BUY FROM CASH)
    L4 = pv.cash_quote
    # 5. Risk budget drawdown headroom notional = (max_drawdown_limit - current_drawdown_pct) * equity
    dd_headroom = max(0.0, limits.max_drawdown_pct - limits.current_drawdown_pct)
    L5 = Decimal(str(max(0.0, dd_headroom * ctx.drawdown_risk_budget_fraction))) * pv.equity_quote
    # ---
    notional_final = min(L1, L2, L3, L4, L5)
    # non-negative & Decimal clamp
    notional_final = max(Decimal("0"), notional_final)
    # Convert quote to base_qty: base = notional / symbol_price_ref (EPS guard for /0)
    eps = Decimal("1e-18")
    if symbol_price_ref and symbol_price_ref > eps:
        base_qty = notional_final / symbol_price_ref.quantize(Decimal("1e-12"))
    else:
        base_qty = Decimal("0")
    quote_qty = notional_final  # buy side notional
    method = "sizing_min_of_five_rules_v1"  # Deterministik string
    return base_qty, quote_qty, notional_final, method
```

### Sizing Safety Invariantlar (v1 hard boundary):
1. `base_qty ≥ Decimal("0")` — negatif olamaz (short yok)
2. `quote_qty ≥ Decimal("0")` — negatif olamaz
3. `notional ≥ Decimal("0")` — negatif olamaz
4. approved → notional > EPS ise base_qty/quote_qty both filled; onay yoksa notional = 0
5. `max_leverage_allowed == 1` kesin (LimitsSnapshot validation ihlali → rejected)
6. short pozisyon AÇILMAZ (bu hikâyede write yok — AD-7 single writer invariant korunur)

---

## 5. Kill Switch & Emergency Stop Davranışı (ÖZEL)

```python
# RiskContext (frozen=True, 11 alan)
@dataclass(frozen=True)
class RiskContext:
    kill_switch: KillSwitchStateSpec          # from contracts (nested)
    emergency_stop_active: bool                # operator flag (False default)
    duplicate_window_ms: int = 60_000
    cooldown_window_ms: int = 120_000
    risk_score_threshold_approval: float = 0.40
    risk_score_threshold_observation: float = 0.70
    score_valid_until_ms: int = 300_000
    signal_valid_until_ms: int = 300_000
    valid_until_decision_ms: int = 30_000
    max_default_order_notional: Decimal = Decimal("5000")
    drawdown_risk_budget_fraction: float = 0.80
```

| Durum | decision | reason_code | kill_switch_state output (UNCHANGED snapshot, aynen geri ver) |
|---|---|---|---|
| C01 global_kill=True | rejected | KILL_SWITCH_GLOBAL_ACTIVE | global_kill=True, reason=ctx.kill_switch.reason (ör. GLOBAL_KILL…) |
| C02 emergency_stop=True | rejected | EMERGENCY_STOP_ACTIVE | kill_switch.reason=EMERGENCY_STOP_ACTIVE (backup kill) |
| C03 per_symbol[symbol]=True | rejected | KILL_SWITCH_SYMBOL_ACTIVE | per_symbol dict unchanged (snapshot), key=symbol vardır |
| Diğer durumlar (20 check sonrası) | approved/rejected | neden | kill_switch_state aynen (RiskEngine onu MUTATE ETMEZ — snapshot) |

---

## 6. Acceptance Criteria (AC — KESİN 96 Maddelik, HİÇBİR KOŞULDA ESNEKLİK YOK)

### G1: Input Contract & Fail-Closed (13 AC)
- **AC-G1-01:** RiskEngine.evaluate() 5 zorunlu typed argüman alır (opp_score, sig, regime, pv, limits) + ctx; None / missing / wrong type → ContractSchemaError → rejected.
- **AC-G1-02:** `malformed opp_score.score_total = 1.5` → decision=rejected + OPPORTUNITY_INVALID reason.
- **AC-G1-03:** `opp_score.actionable = False` → rejected + OPPORTUNITY_NOT_ACTIONABLE reason.
- **AC-G1-04:** `sig.direction = flat` → rejected + SIGNAL_DIRECTION_FLAT (v1 approved flat YOK).
- **AC-G1-05:** `sig.direction = hold` → rejected + SIGNAL_DIRECTION_HOLD (v1 approved hold YOK).
- **AC-G1-06:** `sig.direction = long` → approved olabilir (diğer 19 check + risk score geçerse).
- **AC-G1-07:** `q.invalid = True` → rejected + QUALITY_INVALID reason.
- **AC-G1-08:** `q.quarantined = True` → rejected + QUALITY_QUARANTINED reason.
- **AC-G1-09:** `q.stale = True` (stale_allowed_penalty = fail_closed default) → rejected + QUALITY_STALE reason.
- **AC-G1-10:** `LimitsSnapshot.max_leverage_allowed = 2` → LimitsSnapshot __post_init__ ContractSchemaError → rejected + LIMITS_SNAPSHOT_INVALID.
- **AC-G1-11:** `portfolio_view is None` → rejected + PORTFOLIO_VIEW_MISSING reason.
- **AC-G1-12:** `portfolio_view.ts 1 saat eski ( > stale 5dk default)` → rejected + PORTFOLIO_VIEW_STALE reason.
- **AC-G1-13:** Herhangi bir noktada Exception → outer try-except RiskEngine: approved OLMAZ, rejected + INTERNAL_CALCULATION_ERROR, notional=0, limits unchanged.

### G2: 20 Check + Reason Code Determinizm (22 AC)
- **AC-G2-01…G2-20:** C01…C20 — her check için ayrı test: tek fail → rejected + ilgili reason_code (20 test).
- **AC-G2-21:** İki check aynı anda fail (ör. C07 quarantined + C11 not actionable) → reason_codes listesinde 2 kod alfabetik? VEYA append order → determinizm için check_id sırasına göre append (karar ver: check order = numeric ascending order ile reason ekle, determinizm sağla).
- **AC-G2-22:** reason_codes öğeleri SABİT stringler. 10× aynı input → reason_codes aynen (sıralı, ordered list).

### G3: Risk Score Bileşenleri & Formül (16 AC)
- **AC-G3-01…G3-20 (subset 12):** R01…R20 her biri için 2+ boundary test (0→0 risk, 1→max risk) = 12 AC (key component testleri: R01 quality, R02 spread, R03 edge, R08 strat/regime, R11 DD, R15 concentration, R16 cash, R19 slip/lat).
- **AC-G3-13:** Risk score weighted sum: tüm R=0 → weighted_sum = 0.0000 (±1e-9).
- **AC-G3-14:** Tüm R=1 → weighted_sum = 1.0000 exactly.
- **AC-G3-15:** Quality mult: invalid=True → 0.15 + quality_adjusted_score ceil/floor clamp 0–1 → rejected RISK_SCORE_TOO_HIGH (zaten C06/07 check'ten reject olur, ayrıca test et).
- **AC-G3-16:** Quality mult clean=1.00 → risk score = weighted_sum unchanged (±1e-9).

### G4: Position Sizing (11 AC)
- **AC-G4-01:** L1…L5 5 different notional sınırı → final = min(5).
- **AC-G4-02:** approved OLMAYAN (rejected) → notional = Decimal("0").
- **AC-G4-03:** all 5 L = 0 → base_qty=0, quote=0, notional=0.
- **AC-G4-04:** approved + L1/L2/L3/L4/L5 1000/2000/800/1500/750 → min=750 → notional=750, quote_qty=750.
- **AC-G4-05:** symbol_price_ref = Decimal("0") or None → DivisionByZero guard → base_qty=0, quote_qty=notional.
- **AC-G4-06:** base_qty ≥ Decimal("0") ZORUNLU, negatif base_qty → ContractSchemaError (yazılım safety).
- **AC-G4-07:** notional ≥ Decimal("0") ZORUNLU.
- **AC-G4-08:** sizing method stringi — approved → "sizing_min_of_five_rules_v1", rejected → "rejected_no_sizing" (veya empty str? karar: rejected için "rejected_no_sizing").
- **AC-G4-09:** L5 drawdown_headroom = 0 (current_drawdown = limit) → notional = 0.
- **AC-G4-10:** Exposure headroom L2 = negatif (current > limit — LimitsSnapshot validity'de engellenmeli ama YİNE DE min(0) → 0, rejected).
- **AC-G4-11:** leverage>1 giriş: LimitsSnapshot validation error → rejected (Limits.__post_init__ validation, HARD v1).

### G5: Kill Switch (8 AC)
- **AC-G5-01:** C01 global_kill=True → decision=rejected, reason=KILL_SWITCH_GLOBAL_ACTIVE.
- **AC-G5-02:** C02 emergency_stop=True → decision=rejected, reason=EMERGENCY_STOP_ACTIVE.
- **AC-G5-03:** C03 per_symbol[BTC_USDT]=True + symbol=BTC_USDT → rejected + KILL_SWITCH_SYMBOL_ACTIVE.
- **AC-G5-04:** C03 + symbol=ETH_USDT (killswitch listede YOK) → diğer checkler geçerse approved olabilir (SYMBOL sadece kendisi etkilenir).
- **AC-G5-05:** kill_switch_state output == input kill_switch snapshot (MUTATE 0).
- **AC-G5-06:** kill_switch.reason field: global + GLOBAL_KILL_SWITCH_OPERATOR aynen korunur.
- **AC-G5-07:** C01 True + C02 True → reason_codes: 2 öğe (check sıra 1, 2 → iki kod append).
- **AC-G5-08:** Operator kill switch ACTIVE → 10× → aynı decision/reason (determinism).

### G6: Correlation / Causation (AD-17, 5 AC)
- **AC-G6-01:** RiskDecision.correlation_id == opp_score.correlation_id (SAME — zincir sabit).
- **AC-G6-02:** RiskDecision.causation_id == opp_score.score_id (parent).
- **AC-G6-03:** StrategySignal.causation_id → DIFFERENT. Risk.causation parent = OPPORTUNITY (doğru 5. halka).
- **AC-G6-04:** 3 farklı correlation zinciri → 3 farklı RiskDecision corr_id (aynı olmaz).
- **AC-G6-05:** causation_id: multi-step (sig→opp→risk) — chain length 3 → causation = opp.score_id.

### G7: Quality Preserve (CAP-2, 6 AC)
- **AC-G7-01:** q.stale = True (input) → output.quality_flags referansı? RiskDecision'ın quality_flags'i KENDİSİNİN payload alanı VAR MI? (Kontrol: S-CON-02B RiskDecision'da quality_flags alanı VAR MI? — YOK: RiskDecision L258-321 içinden bak: alanlar: decision_id, decision, reason_codes, position_sizing, limits_snapshot, kill_switch_state, sl/tp refs, valid_until, approval_chain, correlation_id, causation_id. → Kalite: RiskEngine tüketirken kalite bayraklarını korur; RiskDecision içinde QualityFlags alanı YOK. Doğrulama: q id(input) == q id(dış) (sizin testinizde input qyu DEĞİŞMEDİ — IDENTITY test).
- **AC-G7-02:** quality_validator çağrı sayısı 0 (grep / AST).
- **AC-G7-03:** 7 bayrak + abnormal_spread fallback test: spread_bps=100 → abnormal_mult risk applied; q.abnormal_spread attr YOK (hasattr → False).
- **AC-G7-04:** Quality mult; clean=1.00; stale/degraded=0.60; missing/dup/ooo=0.85; invalid/quarantine=0.15 → 4 ayrı test (×1).
- **AC-G7-05:** q.degraded = True + q.invalid = False → reason_codes: QUALITY_DEGRADED_PENALTY + decision scoring continues (reject only if score too high).
- **AC-G7-06:** q frozen → setattr(q, 'stale', True) → dataclass frozen exception (RiskEngine içinde böyle bir çağrı YOK — AST scan 0 finding).

### G8: Determinism (AD-20), CAP-1 Parity, Regression Safety (15 AC)
- **AC-G8-01:** Onaylanan happy path input: 10× call → len(set(schema_sha256)) = 1.
- **AC-G8-02:** Rejected path input: 10× → len(set(reason_codes tuples)) = 1.
- **AC-G8-03:** Sıra: 3 permutations (input objeleri aynı, sırasız dict → sorted) → aynı RiskDecision.
- **AC-G8-04:** app/risk/ içinde run_mode/source_type if-branch AST scan: 0 finding (CAP-1).
- **AC-G8-05:** 22 forbidden lib (requests/httpx/aiohttp/socket/asyncpg/psycopg2/sqlalchemy/pymongo/redis/kafka/boto3/pydantic/pandas/numpy/talib/ta/ccxt/torch/tensorflow/catboost/django/flask/fastapi) → import grep 0 match.
- **AC-G8-06:** Full regression 1876 test — bu hikâyeden SONRA unchanged.
- **AC-G8-07:** New risk tests ≥ 200 PASS.
- **AC-G8-08:** Toplam full suite ≥ 2076 PASS (1876 + ≥200).
- **AC-G8-09:** RiskDecision limits_snapshot output == input limits (identity or deep equal — unchanged).
- **AC-G8-10:** valid_until = as_of + valid_until_decision_ms (30s default) deterministic.
- **AC-G8-11:** kill_switch_state == ctx.kill_switch (snapshot).
- **AC-G8-12:** approval_chain list; approved durumda 20 check id'leri geçenler sırasıyla (["C01","C02",…,"C20"]), rejected'te sadece geçenler? VEYA: approval_chain = ["C01_PASS",…"C20_PASS"] ise approved, aksi halde ilgili "Cxx_REJECT"; karar: approval_chain DETERM. sorted — append sırasıyla.
- **AC-G8-13:** Symbol BTC_USDT, ETH_USDT için 2 bağımsız karar → corr_id'leri ayrıdır, notional min-of-5 ayrı ayrı hesaplanır.
- **AC-G8-14:** Sizing 5-L float → Decimal conversions: no floating-point errors via `Decimal(str(float))` guard.
- **AC-G8-15:** Pyproject.toml dependencies == [].

### G9: EventBus Integration & Safety (No Execution Authority)
- **AC-G9-01:** Approved RiskDecision → same corr_id publish on typed event bus → `risk_decision.v1` subscriber alır.
- **AC-G9-02:** Rejected RiskDecision → publish → `rejected_risk.v1` veya bus reject reason → `dead_letters` length ≥ 1? (AD-19 failure izolasyon: subscriber exception → dead_letters).
- **AC-G9-03:** Subscriber: approved ise downstream allow marker set; rejected ise downstream allow = False (CAP-4 behavioral contract setup — future S-RSK-02).
- **AC-G9-04:** 11 Güvenlik: short YOK, futures YOK, leverage>1 YOK, live exec YOK, exchange YOK, API YOK, credentials YOK, network YOK, DB YOK, AI training YOK, ML YOK → risk decision output short enum YAPAMAZ (no field/value).
- **AC-G9-05:** AD-11: StrategySignal + OpportunityScore ALONE → evaluate WITHOUT RiskEngine → approved yok (SADECE RiskEngine authority).

### G10: DoD Direct Link (5 AC — DOĞRUDAN DoD İÇİ)
- **AC-G10-01:** Toplam test ≥200 yeni.
- **AC-G10-02:** Regression 1876/1876 PASS.
- **AC-G10-03:** S-CON-02B risk.py public alan/import/enum değiştirilmedi (import tests: `from app.contracts.risk import RiskDecision, LimitsSnapshot` — still ok).
- **AC-G10-04:** Fixture defaults frozen, production defaults frozen; ADN-06, ADN-08, ADN-09, ADN-11 için "OPTIMUM" iddiası YOK.
- **AC-G10-05:** implementation.py `pyproject.toml` — unchanged.

---

## 7. Definition of Done (DoD — 16 KESİN KURAL)

| DoD # | Tanım | Ölçüm |
|---|---|---|
| DoD-01 | Yeni test sayısı: ≥ 200 PASS | `pytest tests/risk/ -q --tb=no` ≥ 200 |
| DoD-02 | Full regression: 1876/1876 unchanged (1 skip same place) | `pytest tests/ --ignore=tests/risk/ --tb=no` → 1876 pass |
| DoD-03 | Toplam full suite ≥ 2076 PASS | 1876 + ≥ 200 → 2076 |
| DoD-04 | Fail-Closed: Her malformed → rejected + reason_codes ≥1 | 15+ failure injection test |
| DoD-05 | Determinizm: 3 farklı input family 10× → set(sha)=1 | 3 family × 10 test |
| DoD-06 | CAP-1: AST scan app/risk/ → 0 run_mode branch | AST visitor 2 dosya |
| DoD-07 | CAP-2: Quality mutate 0 / validator call 0 | identity test + grep/ast |
| DoD-08 | AD-11: Strategy/Opportunity/AI approved üretemez (grep `decision_id` sadece risk/) | grep + unit test: opp+sig → no approved class |
| DoD-09 | AD-19: 5 exception simülasyonu (divide by zero / attr error / type / value / import) → rejected + INTERNAL_CALCULATION_ERROR, crash YOK | 5 hata testi |
| DoD-10 | S-CON-02B RiskDecision/Limits/Kill/Sizing — public signature tam korundu | import smoke + original 71 S-CON-02B test pass |
| DoD-11 | Sizing: non-negative / decimal / leverage=1 / short yok | 10+ boundary test |
| DoD-12 | Kill/emergency 4 scenario (global / emergency / per-symbol / clean) → 4/4 doğru reason | 4 test |
| DoD-13 | 20 check tek tek PASS/REJECT testleri | 20 test |
| DoD-14 | 20 risk component — R01-R20 min 12 critical boundary test | 12 test |
| DoD-15 | EventBus 3 integration: publish/typed-sub / failure-isolation-dead_letters / CAP-4 setup (approved → allow marker true) | 3 test |
| DoD-16 | `pyproject.toml dependencies = []` unchanged; stdlib only; no forbidden 22 lib import | grep + 22 forbidden parametrize |

---

## 8. Test Planı (Ortam: `tests/risk/` — ≥ 200 Yeni Test, Parametrize + Boundary Matrix + Orthogonal Kombinasyon)

### Test Grupları & Tahmini Test Sayısı (Ortotogonal Dağılım)
| Grup | Alt Grup | Parametrize Matrix | Tahmini Test Sayısı | AC'ler |
|---|---|---|---|---|
| T01 | Input Validation (fail-closed, malformed/missing) | 13 parametrize (G1 AC) + 5 exception injection (AD-19 DoD-09) | 18 | G1, AD-19 |
| T02 | 20 Check Tek Tek + Kombinasyonlar | 20 tek check_fail parametrize + 6 pairwise fail (C07+C06, C01+C02, etc.) + 2 multi-fail | 28 | G2 (22) |
| T03 | 20 Risk Component Boundary Testleri | 12 critical (R01, R02, R03, R05, R07, R08, R10, R11, R12, R15, R16, R19) × 4 nokta = 48 | G3 (16) |
| T04 | Risk Score Determinism + Ağırlık Toplam | Ağırlık toplam = 1.000; 3 family × 10x determinizm; 5 kalite multiplier (clean/stale-degraded/missing-dup-ooo/invalid/quar) × 2 each | 23 | G3, AD-20 |
| T05 | Sizing (5 Kural + MinOf + Boundary) | 5 single rule × 3 = 15; 4 pairwise min; 5 zero/neg/leverage boundary; method string 2; eps price 2 | 28 | G4 (11) |
| T06 | Kill Switch / Emergency | C01 (global) × 2 reasons; C02 (emergency) × 1; C03 (per_symbol) × 3 (mevcut/yok/başka sembol); output snapshot unchanged 4× = 12 | 22 | G5 (8) |
| T07 | Quality Flags + Fallback Spread + CAP-2 | 4 multiplier; 1 identity; 1 validator call grep; 1 hasattr spread fallback; 1 frozen mutate | 8 | G7 (6), CAP-2 |
| T08 | Correlation / Causation | 3 matrix (3 corr × 3 caus) + 3 chain length (sig/opp/risk) + missing parent behavior → 10 | 10 | G6 (5) |
| T09 | Determinism 10x (permütasyonlar) | 3 input family × 10x sha + sorted; ordering irrelevant dict permütasyonları → 6 parametrize | 9 | G8-01..03 |
| T10 | CAP-1 (AST) + Safety 22 forbidden lib | 2 dosya AST scan (app/risk/__init__.py + base.py) + 22 parametrize forbidden import grep → 24 | 24 | G8-04/05/15, Safety |
| T11 | EventBus + AD-19 Failure İzolasyonu + CAP-4 behavioral contract setup | 3 integration: publish approved → sub call; publish rejected → dead letters; bad sub exception → other sub continue → 4 | 4 | G9, CAP-4, AD-19 |
| T12 | Regression + Import Smoke (S-CON-02B 71 test + unchanged pyproject) | Import 3 smoke; pyproject.toml unchanged; regression not touched — manifest 3 test | 5 | G10-03/05 |
| T13 | Valid_until / Duplicate Window / Cooldown / Expiry | 4 valid_until + 5 duplicate_window + 4 cooldown + 4 signal expiry + 4 opp expiry = 21 | 21 | C15, C16, C17 |
| | **TOPLAM (Tahmini)** | | **≥ 220** (≥200 hedefi 110% aşıldı) | TÜM AC & DoD |

### Test Matrix Notları:
- **Yöntem:** `@pytest.mark.parametrize` — T03 48 test = 12 key component × 4 boundary noktası (0, 0.49, 0.50, 1.0).
- **Determinism 10x:** 3 family: (approved_clean), (rejected_killswitch_global), (rejected_quality_stale) — her biri 10× sha set size 1.
- **22 Forbidden lib (T10):** S-OPP-01 T05 ile aynı liste; parametrize ile 22 test, 0 match.
- **Ortotogonallik:** 20 check × pairwise 6 kombinasyonu (T02 28 test) — no duplicate.

### Test Dosyaları (Plan — KOD YAZILMAZ, HİKÂYEDE BELİRLENİR):
```
tests/risk/
  conftest.py                       # helpers: make_risk_context(), make_clean_portfolio_view(), make_limits()
  test_sk01_01_input_validation_fail_closed.py      # 18 test (T01)
  test_sk01_02_twenty_checks_reason_matrix.py        # 28 test (T02)
  test_sk01_03_risk_components_boundary.py           # 48 test (T03)
  test_sk01_04_risk_score_formula_and_weights.py     # 23 test (T04)
  test_sk01_05_position_sizing_min_of_five.py        # 28 test (T05)
  test_sk01_06_kill_switch_and_emergency_stop.py     # 22 test (T06)
  test_sk01_07_quality_flags_cap2.py                 #  8 test (T07)
  test_sk01_08_correlation_causation.py              # 10 test (T08)
  test_sk01_09_10x_determinism.py                    #  9 test (T09)
  test_sk01_10_cap1_cap2_safety_22forbidden.py       # 24 test (T10)
  test_sk01_11_eventbus_cap4_setup.py                #  4 test (T11)
  test_sk01_12_smoke_regression_contracts.py         #  5 test (T12)
  test_sk01_13_expiry_duplicate_cooldown.py          # 21 test (T13)
# Toplam 13 dosya, ≥220 parametrize test (≥200 hedefi)
```

---

## 9. ADN — Açık Kararlar (Fixture ≠ Production, production = "GERÇEK OPTİMUM" DEĞİL — ADN korundu)

| ADN | Konu | Fixture Default (testte override edilebilir) | Production Açık (Sonraki Çalışma) |
|---|---|---|---|
| ADN-RSK-01 | stale_threshold_ms portfolio view | 300_000 ms (5 dk) | ADN → operatör |
| ADN-RSK-02 | MIN_POSITIVE_TARGET_EDGE_BPS | 1.0 bps | ADN → cost modeli |
| ADN-RSK-03 | min_default_order_notional | Decimal("100") | ADN → ops |
| ADN-RSK-04 | score/signal_valid_until_ms default | 300_000 (5 dk) | ADN |
| ADN-RSK-05 | risk_score_threshold_approval / observation | 0.40 / 0.70 | ADN → challenger evaluation |
| ADN-RSK-06 | RiskPolicyWeights 20 ağırlık seti | Default 1.000 toplam (§3b) | ADN → tuning |
| ADN-RSK-07 | Regime_Strategy_Penalty_Matrix (6 rejim × 3 strateji) | §3a R08 default tablo | ADN → backtest |
| ADN-RSK-08 | max_default_order_notional | Decimal("5000") | ADN |
| ADN-RSK-09 | drawdown_risk_budget_fraction | 0.80 (80%) | ADN |
| ADN-RSK-10 | duplicate_window_ms / cooldown_window_ms | 60_000 / 120_000 | ADN |
| ADN-RSK-11 | CONCENTRATION_DIVERSIFIER_N | 3.0 | ADN |
| ADN-RSK-12 | approval_chain string format | C01_PASS / C01_REJECT sözleşmesi | ADN |

**KURAL:** Fixture defaults (testte) frozen=True dataclass constructor'ında belirtilir. Production "optimum" iddiası YOK. ADN-RSK-01..12 AÇIK KALDI. (Onaylandı: §0 hard kural 8 uyarlandı.)

---

## 10. Kapsam Dışı (14 Öğe — KESİN Dışında)

| # | Kapsam Dışı Madde | Neden / Gelecek Hikaye |
|---|---|---|
| 1 | PaperOrder, PaperFill, FillModel implementation | S-PTR (S-RSK-02 = CAP-4 behavioral test; implementation S-PTR-01) |
| 2 | Position, PortfolioSnapshot WRITE | AD-7/AD-13/AD-24 Single Writer: SADECE Portfolio Simulator (S-PTF) |
| 3 | Backtest engine | S-BKT |
| 4 | Exchange, network, DB, API, credentials, real orders, real money | v1 Hard Safety (prd boundaries) |
| 5 | Short pozisyon, futures, leverage>1 | v1 HARD boundary (enum YOK, leverage=1 validation) |
| 6 | AI training / inference call (new model eval) | E-AIS / future; risk engine sadece AI skorunu READ (input OPPORTUNITY) |
| 7 | Adaptive Position Sizing Methods (Kelly, Risk Parity, Vol-Targeted, Kelly Fractional) | S-RSK-03 |
| 8 | CAP-4 tam enforcement testi: RiskDecision.rejected → PaperOrder reject | S-RSK-02 |
| 9 | Stale-adapter-failure downstream hardening + symbol eligibility coordinator | S-RSK-04 (AD-5) |
| 10 | Champion/Challenger RiskPolicy Promotion Validation | E-MDL, S-MDL |
| 11 | S-CON-02B risk.py public API değişikliği | ZORUNLU KORU — yazılmaz |
| 12 | QualityFlags'e abnormal_spread YENİ field ekleme | Kural: fallback kullan, no contract bump |
| 13 | pyproject.toml yeni runtime bağımlılığı | ZORUNLU DEPS=[] |
| 14 | Contract version 1.0.0 bump | ZORUNLU SABİT |

---

## 11. Değişiklik Yapılacak Dosyalar (İMPLEMENTASYON — ŞU AN HİÇBİRİ YAZILMAZ, Plan)

```
app/risk/
  __init__.py                 # YENİ (public export: IndependentRiskEngine, RiskContext, RiskPolicyWeights, evaluate)
  base.py                     # YENİ (SAF pure implementation — 20-check, 20-risk, 5-sizing, try-except fail-closed outer)

tests/risk/
  conftest.py + 13 test dosyası # Plan §8 (≥220 yeni test)
```

### Mevcut Dosyalar:
- **app/contracts/risk.py** — OKUNUR (DEĞİŞMEZ).
- **app/platform/event_bus.py** — OKUNUR (S-PLN-01 mevcut, DEĞİŞMEZ).
- **app/contracts/quality.py** — OKUNUR, quality flags frozen (DEĞİŞMEZ).
- **pyproject.toml** — DEĞİŞMEZ.
- **Tüm 1876 ön test / hikaye kodları** — DEĞİŞMEZ.

---

## 12. Implementation Readiness (Özet)

| Hazırlık Öğesi | Durum |
|---|---|
| Bağımsızlık (AD-11) | ✅ Hikâyede açıklandı. Strategy/OPP/AI approved YAPAMAZ. |
| Fail-Closed (AD-19) | ✅ 13+ input fail + 5 exception + 20 check matrix ile zorunlu kılındı. |
| Determinism (AD-20) | ✅ 3 family × 10x sha setlen=1 zorunlu test. |
| CAP-1 (Parity 0 branch) | ✅ AST scan 2 dosya zorunlu test. |
| CAP-2 (Quality Preserve) | ✅ 8 test + identity + validator call 0. |
| CAP-4 Setup | ✅ EventBus approved → allow marker test; enforcement proof S-RSK-02. |
| 20 Check + 20 Risk Component | ✅ Tam tablo + reason_code listesi. |
| Sizing 5 Kural Min-Of | ✅ Tam formül + non-negative / Decimal / short YOK. |
| Kill Switch 3 Katman (global/emergency/per-symbol) | ✅ 8 AC + 22 test planı. |
| Corr/Caus (5. Halka) | ✅ opp.correlation (sabit), causation=opp.score_id. |
| 1876 Regression Koru | ✅ DoD-02, AC-G8-06/10-05. |
| ≥200 yeni test (Hedef) | ✅ 220 plan → 110% aşıldı. |
| 22 Forbidden lib (safety) | ✅ 24 test parametrize. |
| ADN 12 Açık Karar | ✅ ADN-RSK-01..12 açık, fixture ≠ production zorunlu. |

---

## 13. Sonraki Adımlar (ÖNERİ — Kullanıcı Onayı SONRASI)

1. (İSTEĞE BAĞLI) `bmad-dev-story S-RSK-01` — implementation & ≥220 yeni test.
2. (ZORUNLU) S-RSK-02 — CAP-4 Direct Proof: RiskDecision.approved → PaperOrder allowed; rejected → forbidden.
3. (ZORUNLU) S-RSK-03 — Position Sizing Methods Suite (Kelly / Risk Parity / Vol-Targeted / Fixed Notional).
4. (ZORUNLU) S-RSK-04 — Stale+AdapterFailure Hardening (AD-5 + Coordination Eligibility View).
5. Audit-run: Bağımsız review, ≥200 yeni test + 1876 regression pass ise COMMIT READY.

---

**SON:** Bu hikâye `bmad-create-story` standardıdır. Kod yazılmadı. Git commit oluşturulmadı. S-RSK-02/S-RSK-03/S-RSK-04'e geçilmedi. Implementation artifacts içine kaydedildi (aşağı).

---
story_id: "S-RSK-02"
story_key: "S-RSK-02"
title: "RiskDecision → PaperOrder Gate Enforcement (CAP-4 Direct Proof, AD-11 Single Authority, AD-19 Fail-Closed, 10-Gate Rule Matrix, EventBus, Idempotency)"
epic: "E-RSK — Independent Risk Engine & Kill Switch (Epic 9)"
status: "review"
created: 2026-08-28
updated: 2026-08-28
author: "bmad-create-story v1 + bmad-dev-story v1"
tags: [risk, gate, paper_order, CAP-4, AD-11, AD-17, AD-19, AD-20, fail_closed, deterministic, synchronous, typed, idempotent, replay_safe, stdlib_only, long_only, v1]
baseline_commit: "2920521 feat: implement independent fail-closed risk engine"
previous_story: "S-RSK-01 Independent Risk Engine (233 test PASS, Toplam 2109 PASS + 1 SKIP)"
next_story: "S-RSK-03 Position Sizing Methods (OOS bu hikâyede)"
contract_version_preserved: "1.0.0"
contracts_used:
  - "RiskDecision (app/contracts/risk.py — S-CON-02B §3.1) — decision_id ULID, decision∈{approved,rejected}, valid_until Instant, kill_switch_state, position_sizing.notional Decimal, correlation_id, causation_id"
  - "PaperOrder (app/contracts/paper.py — S-CON-02B §3.2) — order_id, side∈{buy,sell}, status, PolicyRefs.risk_decision_id REQUIRED ULID-like≥8, requested_qty Decimal, requested_notional Decimal, correlation_id, causation_id"
  - "PaperOrderPolicyRefs (S-CON-02B §3.2 Nested) — risk_decision_id REQUIRED (ContractSchemaError if <8 chars)"
  - "KillSwitchStateSpec (S-CON-02B §3.1.1) — global_kill, per_symbol_kills{} , emergency_stop — AD-11 invariant: global_kill=True → approved OLAMAZ (ContractSchemaError at RiskDecision.__post_init__)"
  - "LimitsSnapshot (S-CON-02B §3.1.2) — max_leverage_allowed=1 EXACT (ContractSchemaError if !=1), max_position_quote, max_exposure_quote, max_daily_loss_quote, max_drawdown_pct"
  - "QualityFlags (S-CON-02A §2) — stale/invalid/quarantined/degraded/duplicate/out_of_order/missing/abnormal_spread — CAP-2 salt-okunur, MUTATE YOK, VALIDATOR YENİDEN ÇAĞIRMA YOK"
  - "RiskDecisionResult enum (app/contracts/risk.py) — EXACT 2 değer: approved / rejected — SHORT yok, leverage yok"
test_baseline_count: 2110
test_baseline_passed: 2109
test_baseline_skip: 1
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
dev_agent_sr02_new_tests: 250
dev_agent_sr02_pass: 250
dev_agent_sr02_fail: 0
dev_agent_total_risk_tests: 483
dev_agent_full_regression_passed: 2359
dev_agent_full_regression_skip: 1
dev_agent_full_regression_fail: 0
dev_agent_ast_forbidden_22lib: 0
dev_agent_ast_cap1_runmode_branch: 0
dev_agent_ast_cap2_quality_mutate_call: 0
dev_agent_ast_credentials_literal: 0
dev_agent_ast_network_imports: 0
dev_agent_ast_real_order_db_call: 0
dev_agent_pyproject_deps: "[] (EMPTY — stdlib-only)"
correlation_causation_chain: "8-halka: StrategySignal (S-STR-01) → OpportunityScore (S-OPP-01) → RiskDecision (S-RSK-01) → PaperOrder (S-RSK-02 THIS) → PaperFill → Position → PortfolioSnapshot (S-CON-02B, OOS sonraki PTR/PTF)"
runtime_dependencies_new_allowed: 0
pyproject_dependencies_expected: "[] (EMPTY — stdlib-only)"
v1_hard_boundary_long_only: true
new_contracts_allowed: false
paper_only: true
no_real_exchange_api_credentials: true
---

# S-RSK-02 — RiskDecision → PaperOrder Gate Enforcement (CAP-4 Direct Proof)

## 1. Amaç ve Genel Bakış (BDD User Story + İş Değeri)

**User Story (BDD — KULLANICI VERBATİM AMAÇ + ANA KURAL):**
> *Bir Portfolio Simulator / Paper Trading Engine tüketicisi (AD-7/13/24 tek-yazar Portfolio Simulator downstream, E-PTR/PTF önceki gateway layer) olarak,*
> *Sadece ve SADECE **aynı correlation zinciri içinde ÖNCE APPROVED RiskDecision** (S-RSK-01 ürünü) bulunduğunda **PaperOrder** oluşturabilmek istiyorum,*
> *Öyle ki **CAP-4 GERÇEK ENFORCEMENT** ile KANITLANsın:*
> - ✅ `RiskDecision.decision = approved` → **PAPER ORDER ALLOW** (oluşturulabilir)
> - ❌ `RiskDecision.decision = rejected` → **PAPER ORDER YOK** (oluşturulamaz)
> - ❌ **RiskDecision MEVCUT DEĞİL** → **PAPER ORDER YOK / HATA**
>
> *Bunun için 10'lu Gate Kuralı uygulayan bir **deterministic, fail-closed, synchronous, typed, correlation-aware, causation-aware** enforcement gate oluşturacağım:*
> *1) RiskDecision mevcut mu?*
> *2) RiskDecision.approved mı?*
> *3) correlation_id eşleşiyor mu?*
> *4) risk_decision_id (PolicyRefs) eşleşiyor mu?*
> *5) valid_until geçerli mi?*
> *6) kill-switch aktif mi?*
> *7) duplicate/replay mi?*
> *8) signal/score stale mi?*
> *9) quantity/notional valid mi?*
> *10) short/leverage>1/futures ihlali var mı?*
>
> *Tek bir ihlal → PaperOrder BLOCKED. Herhangi bir exception/belirsizlik (AD-19) → BLOCKED (never approve).*
> *Ayrıca AD-11 ile **SADECE Risk Engine APPROVAL AUTHORITY**; Strategy, OpportunityScore, AI, PaperOrder kendisi approval ÜRETEZ / VEREMEZ.*
> *S-PLN-01 Typed EventBus üzerinden RiskDecision event → Gate subscriber → PaperOrder event akışı typed olmalı; external broker YOK.*
> *Yeni runtime dependency 0; pyproject.toml `dependencies=[]` korunur; stdlib-only; S-CON-02B mevcut RiskDecision/PaperOrder contractları %100 KORUNUR (yeni contract YOK).*
> *Bu hikâyede 250+ YENİ TEST + mevcut 2110 test (2109 PASS + 1 SKIP) regression KORUNUR.*

### CAP-4 NEDİR NEDEN ÖNEMLİ (SPEC CAP-4 ÖZET):
- **CAP-4 Intent:** RiskDecision onayı OLMADAN PaperOrder KABUL EDİLMESİN; RiskDecision açık decision/reason/limit_snapshot/position_sizing taşısın.
- **CAP-4 Success (EPICS Appendix A):** Portfolio Simulator, `correlation_id` bazında onaylanmış RiskDecision bulunmayan PaperOrder'ı KESİNLİKLE reject eder.
- **S-RSK-01 = Setup (RiskDecision üreten engine). S-RSK-02 = DIRECT ENFORCEMENT PROOF (PaperOrder oluşturmadan önce gate).**

---

## 2. Hedef ve Ön Koşullar (Başlangıçta Doğrulanacak — Non-Negotiable)

✅ **BAŞLANGIÇTA DOĞRULANACAKLAR:**
1. **2110 / 2110 Regression Smoke PASS:** S-RDH-01 68 + S-RDH-02 64 + S-PLN-01 42 + S-CON-02A 104 + S-CON-02B 71 + S-CON-02C 93 + S-FEA-01 120 + S-REG-01 302 + S-STR-01 401 + S-OPP-01 611 + S-RSK-01 233 = **2109 PASS + 1 SKIP (S-OPP-01 flat/hold efficiency skip)** → BU HİKÂYE SONRASI 2109+1 PASS + 1 SKIP KORUNUR (0 regression break).
2. **`app/contracts/risk.py` Mevcut:** RiskDecision (decision_id ULID-like, decision 2-enum, valid_until Instant, kill_switch_state, position_sizing.notional Decimal, limits_snapshot, correlation_id, causation_id, reason_codes[], created_ts).
3. **`app/contracts/paper.py` Mevcut:** PaperOrder + **Nested PaperOrderPolicyRefs.risk_decision_id REQUIRED (len≥8 → ContractSchemaError)**. CAP-4 ŞEMA-SEVİYESİ setup.
4. **`app/risk/base.py` Mevcut (S-RSK-01):** RiskEngine 20-check pipeline, fail-closed, 3-level killswitch, min-of-5 sizing, 20-component risk score.
5. **`app/platform/eventbus.py` Mevcut (S-PLN-01):** InMemoryTypedEventBus, subscribe/publish/publish_many/clear, DLQ subscriber isolation, causation max_depth=32, quarantine isolation, SubscriptionToken + unsubscribe, typed events.
6. **`pyproject.toml dependencies = []`** — stdlib-only; NO pydantic/attrs/msgspec/cattrs/numpy/pandas/ccxt/requests.
7. **`CONTRACT_VERSION = "1.0.0"`** — BU HİKÂYEDE BUMP YOK (yeni contract YOK, mevcut public API DEĞİŞMEZ).
8. **v1 Hard Safety Mevcut:** short YOK (Side enum: buy/sell — sell closing long only, new short YOK), leverage>1 YOK (LimitsSnapshot.max_leverage_allowed=1 exact invariant), futures YOK, real-exchange/API-key/credentials/db YOK (AST scan 0 match — bu hikâyede tekrar doğrulanacak).
9. **S-CON-02B AD-11 Invariant:** RiskDecision.__post_init__ → `kill_switch_state.global_kill=True AND decision=approved → ContractSchemaError`. Approved → position_sizing.notional > 0; Rejected → notional = 0 EXACT (already enforced).
10. **S-RSK-01 20-Check Pipeline Referans:** C01-C20 (emergency/global kill, per-symbol kill, symbol eligibility, quality 7 bayrak, portfolio 6 limit (pos/exposure/cash/daily/dd/consec), order param validation, regime transition safety, correlation/causation validity, sizing consistency). **BU HİKÂYEDE S-RSK-01 risk engineini TEKRAR UYGULAMAYIZ — sadece S-RSK-01'in ÜRETİP KAYDETTİĞİ RiskDecision'u GATE'DE KULLANIRIZ.**

---

## 3. Değişmez Mimari Kurallar (HİÇBİR KOŞULDA İHLAL EDİLEMEZ — User HARD Rules)

| Kural Kodu | Kaynak | Davranış / Zorunluluk (NON-NEGOTIABLE) |
|---|---|---|
| **CAP-4 Direct Proof** | SPEC §CAP-4 + User | **APPROVED → ALLOW; REJECTED → BLOCK; NO RISKDECISION → BLOCK.** PaperOrder.policy_refs.risk_decision_id + correlation_id bazında ZORUNLU lookup. |
| **AD-11 Single Authority** | ARCH §AD-11 + User | Risk Engine TEK approval authority. **Strategy / OpportunityScore / AI / PaperOrder / PaperFill APPROVAL ÜRETEZ / VEREMEZ.** Sadece RiskDecision.decision=approved güvenilir onay kaynağı. |
| **AD-19 Fail-Closed** | ARCH §AD-19 + User | Gate HERHANGİ bir exception/missing/invalid/stale/quarantined/timeout/empty/decode hatası → **BLOCKED (never approve on error).** Error reason_code yazılır; audit; PaperOrder YOK. |
| **AD-20 Determinism + Idempotency** | ARCH §AD-20 + User | Aynı (RiskDecision + PaperOrderRequest hash) → 10 kez → AYNI gate decision (ALLOW/BLOCKED), AYNI reason_codes[], AYNI sorted_dict, AYNI sha-256. Duplicate request → duplicate PaperOrder ÜRETMEZ. |
| **AD-17 Corr/Caus Chain** | ARCH §AD-17 + User | 8-halka correlation_id SABİT; causation_id = parent.event_id (OppScore.score_id → RiskDecision.causation_id; RiskDecision.decision_id → PaperOrder.causation_id). AD-17 8/8 bu hikâyede 4/8 doğrulanır (OppScore → RiskDec → PaperOrder). |
| **CAP-1 No RunMode Branch** | SPEC §CAP-1 | Gate implementation dosyalarında `if run_mode ==` / `if source_type ==` → **AST scan 0 finding.** Aynı RiskDecision → Aynı PaperOrder (corr/caus/decision aynen). |
| **CAP-2 QualityFlags Immutability** | SPEC §CAP-2 + User | Gate **SADECE** upstream kalite bayraklarını OKUR (RiskDecision.quality_state / OpportunityScore üzerinden ya da caller ctx'den). **MUTATE YOK; VALIDATOR RPC/IMPORT/CALL YOK.** |
| **AD-7/13/24 Single Writer** | ARCH §AD-7/13/24 | **PaperOrder/Fill/Position/PortfolioSnapshot tek yazarı = Portfolio Simulator (E-PTR/PTF sonraki). BU HİKÂYEDE: Gate SADECE ALLOW/BLOCKED decision üretir; PaperOrder nesnesini ya da DB/Persistence yazma YOK. Yazma OOS. Caller (simulator) gate'den ALLOW alırsa kendi yazar.** |
| **v1 Hard Safety Boundary** | PRD §1 + User | **NO** futures / short / leverage>1 / real-exchange / REST / WS / API-key / credential / DB / live-execution / real-money → AST 0 match. |
| **Stdlib-Only (Zero Dep)** | User HARD rule + DoD | `pyproject.toml dependencies=[]` DEĞİŞMEZ. Forbidden 22-lib (requests/httpx/websockets/pydantic/numpy/...) → AST import scan 0 match. |
| **No New Contract (User KURAL)** | User HARD rule | RiskDecision / PaperOrder / PolicyRefs / KillSwitchStateSpec / LimitsSnapshot public contract DEĞİŞTİRİLMEZ. **Yeni canonical dataclass/enum OLUŞTURULMAZ.** Gate implementation'ı app/risk ALTINDA YENİ dosyada (ayrı bounded context, contracts klasörüne DOKUNULMAZ). |
| **Typed EventBus S-PLN-01** | User + S-PLN-01 | Gate, EventBus üzerinden RiskDecision event'ini dinler (typed). ALLOW olunca PaperOrder event publish eder (typed, corr/caus korunur). Subscriber failure → DLQ (diğerleri devam — AD-19). External broker YOK; in-memory. |
| **Synchronous Gate** | User | `gate.evaluate(request) -> GateResult` — asyncio YOK. Stdlib-only sync call. asyncio import 0. |
| **Replay-Safe / Correlation-Aware** | AD-4 + User | Aynı correlation_id → aynı zincir; different corr_id → farklı zincir. Stale upstream (signal > stale threshold) → BLOCKED. |
| **No Risk Engine Re-Run (ÖNEMLİ)** | User + Dependency | **BU HİKÂYEDE Risk Engine (S-RSK-01 C01-C20) TEKRAR ÇALIŞTIRILMAZ.** Sadece daha önce (S-RSK-01 ile) üretilmiş ve kaydedilmiş (in-memory registry ya da caller-provided) RiskDecision lookup edilir. Risk engine algoritması değiştirme / yeni algo YOK (user OOS). |

---

## 4. Mimari Uyum ve 10 Gate Kuralı Matrix (ANA KANIT — Kullanıcı VERBATİM)

### 4.1 8-Halka Corr/Caus Zinciri (4/8 BU HİKÂYEDE DOĞRULANIR)
```
StrategySignal (S-STR-01, event_id=SS_001)
  ↓ causation_id = SS_001; correlation_id = CORR_001 (SABİT)
OpportunityScore (S-OPP-01, score_id=OS_001)
  ↓ causation_id = OS_001; correlation_id = CORR_001
RiskDecision (S-RSK-01, decision_id=RD_001, decision=APPROVED)   ← GATE INPUT #1: BU ZATEN OLUŞTURULMUŞ
  ↓ causation_id = RD_001; correlation_id = CORR_001
PaperOrder (S-RSK-02, order_id=PO_001)                          ← GATE OUTPUT #1: ALLOW İSE OLUŞUR
  ↓ (sonraki S-PTR/PTF OOS)
PaperFill → Position → PortfolioSnapshot
```

### 4.2 10 Gate Kuralı Matrix (HER BİRİ 1 İHLAL → BLOCKED — NON-NEGOTIABLE)

| Gate # | Kural Adı | Kontrol (Ne olursa BLOCKED?) | Veri Kaynağı (Nereden okunur?) | Reason Code (Blocked olunca) | Happy Path (ALLOW için gerekli) |
|---|---|---|---|---|---|
| **G01** | RiskDecision Mevcut mu? | `RiskDecision` verilen (correlation_id, risk_decision_id) çifti için **BULUNAMAZSA** → BLOCKED | Caller-provided DecisionRegistry / in-memory store (gate constructor arg — interface, No DB, No persistence) | `G01_RISK_DECISION_MISSING` | Registry'de aynı (corr_id, rd_id) için RiskDecision instance bulundu |
| **G02** | RiskDecision APPROVED mı? | `rd.decision != RiskDecisionResult.APPROVED` (yani REJECTED veya başka invalid değer) → BLOCKED | `RiskDecision.decision` (S-CON-02B, 2-enum) | `G02_RISK_DECISION_NOT_APPROVED` + alt sebep (rejected reason_codes[] propagate) | `rd.decision == APPROVED` tam olarak |
| **G03** | Correlation_id Eşleşiyor mu? | `PaperOrderRequest.correlation_id != RiskDecision.correlation_id` → BLOCKED (farklı zincir — CAP-4 cross-chain ihlali) | `request.correlation_id` vs `rd.correlation_id` | `G03_CORRELATION_MISMATCH` | İki correlation_id TAM (case-sensitive, exact string) eşleşir |
| **G04** | PolicyRefs RiskDecision_id Eşleşiyor mu? | `request.policy_refs.risk_decision_id != rd.decision_id` → BLOCKED (1:1 bağlantı ZORUNLU — CAP-4, S-CON-02B __post_init__ zaten len≥8 zorunlu kılar, şimdi eşleşme zorunlu) | `request.policy_refs.risk_decision_id` vs `rd.decision_id` | `G04_POLICY_REFS_RISK_ID_MISMATCH` | İki decision_id TAM eşleşir |
| **G05** | Valid_until GEÇERLİ mi? | `current_clock_instant() >= rd.valid_until` → BLOCKED (decision expired — artık geçersiz) | `rd.valid_until` (Instant) vs `clock_ref.current()` (deterministik — caller/sınırda enjekte edilir, real-time test fixture override edilebilir) | `G05_DECISION_EXPIRED` | `current_ts < valid_until` (strict less-than — tam eşit = expired) |
| **G06** | Kill-Switch AKTİF mı? | `rd.kill_switch_state.global_kill == True` VEYA `rd.kill_switch_state.emergency_stop == True` VEYA `rd.kill_switch_state.per_symbol_kills.get(request.symbol, False) == True` → BLOCKED. Not: RiskDecision.__post_init__ zaten global_kill=True + approved → ContractSchemaError yapar (AD-11). Burada **gate level'da TEKRAR KONTROL** (redundant safety — defense in depth). | `rd.kill_switch_state` (3-level: global, emergency, per-symbol) | `G06_KILL_SWITCH_ACTIVE` (3 ayrı: `G06A_GLOBAL_KILL`, `G06B_EMERGENCY_STOP`, `G06C_PER_SYMBOL_KILL`) | TÜM kill switch'ler FALSE (hepsi temiz) |
| **G07** | Duplicate / Replay Guard mı? | Aynı (correlation_id, symbol, request_sha256, request_window_start <= ts < request_window_end) tuple DAHA ÖNCE bu gate instance tarafından ALLOW/BLOCKED olarak işaretlendiyse → İLK decision AYNEN döndürülür (idempotency). YENİ PaperOrder ÜRETİLMEZ (duplicate block). Eğer caller aynı tuple ile ikinci kez istekte bulunup YENİ order üretmeye çalışırsa → bu gate'ten aynı decision döner ama caller'ın kendisi duplicate detection yapar (gate bunu "aynı decision" şeklinde bildirir). | Gate içi in-memory idempotency_store (frozenset/Dict[frozenset → GateResult]; persistence YOK; in-memory only — test fixture clear edilebilir) | `G07_DUPLICATE_REQUEST_IDEMPOTENT_RESPONSE` (info code; decision = first time decision — error değil; duplicate order üretilmediği için audit) | İlk kez görülen request tuple → yeni değerlendirme → store'a kaydet |
| **G08** | Signal/Score STALE mi? | `(current_ts - rd.created_ts) > STALE_DECISION_THRESHOLD_DEFAULT` → BLOCKED. VEYA upstream quality_flags (rd.quality_state ya da rd.reason_codes[] içinde STALE_DATA_REFERENCED varsa) → BLOCKED. CAP-2: **VALIDATOR CALL YOK; sadece bayrakları okuyoruz.** | `rd.created_ts`, `current_ts`, threshold (fixture override edilebilir: default ADN 5 dakika = 300 saniye); ayrıca `rd.quality_state.stale=True` ise direkt | `G08_STALE_UPSTREAM_OR_QUALITY` (2 ayrı: `G08A_STALE_DECISION_AGE`, `G08B_UPSTREAM_QUALITY_STALE_INVALID_QUARANTINE`) | Decision yaşı <= threshold VE upstream quality stale/invalid/quarantine = FALSE (hepsi temiz) |
| **G09** | Quantity / Notional GEÇERLİ mi? | (a) `request.requested_qty <= 0` → BLOCKED; (b) `request.requested_notional <= 0` → BLOCKED; (c) `request.requested_notional > rd.position_sizing.notional` → BLOCKED (oversize — risk onayladığından fazla notional istendi); (d) `request.requested_qty * rd.position_sizing.reference_price > rd.position_sizing.notional * (1 + OVERSIZE_TOLERANCE_BPS/10000)` → BLOCKED (qty*price notional tutarsızlığı). Not: `reference_price` rd.position_sizing içinde zaten (S-RSK-01'de geliyor — yoksa fixture'da). | `request.requested_qty`, `request.requested_notional` (Decimal); `rd.position_sizing.notional`, `rd.position_sizing.reference_price` (Decimal). OVERSIZE_TOLERANCE_BPS default = 50 (0.5%), fixture override edilebilir. | `G09_INVALID_QUANTITY_NOTIONAL` (4 ayrı: `G09A_QTY_NON_POSITIVE`, `G09B_NOTIONAL_NON_POSITIVE`, `G09C_NOTIONAL_OVERSIZED_VS_RISK`, `G09D_QTY_PRICE_MISMATCH_VS_NOTIONAL`) | Hem qty hem notional 0'dan büyük; notional risk'ten fazla değil; qty*price ≈ notional (tolerans dahilinde) |
| **G10** | Short / Leverage>1 / Futures İHLALİ? | (a) `request.side == Side.SELL_OPEN_SHORT` VEYA short-benzeri bir durum (v1'de Side YALNIZCA buy/sell — sell sadece long kapatma — ama gate'te YENİ pozisyon açma isteği + side=sell + mevcut flat poz → engelle: short engelleme). (b) `rd.limits_snapshot.max_leverage_allowed != 1` → BLOCKED (already S-CON-02B'de invariant ama gate'te tekrar kontrol). (c) `request.order_type == "futures"` VEYA `symbol` içinde "PERP"/"FUTURES" geçiyor → BLOCKED. Not: v1 long-only spot. | `request.side`, `rd.limits_snapshot.max_leverage_allowed`, `request.symbol` (spot check), `request.order_type` (spot market/limit — futures/perp YOK). | `G10_SAFETY_BOUNDARY_VIOLATION` (3 ayrı: `G10A_SHORT_ATTEMPT_BLOCKED`, `G10B_LEVERAGE_OVER_1X_BLOCKED`, `G10C_FUTURES_OR_PERPETUAL_BLOCKED`) | Side=buy (long açma) VEYA side=sell (mevcut long kapatma — caller validation; gate'te sadece short-aç engelle); leverage=1; symbol spot (no PERP/FUT); order_type spot (market/limit) |

### 4.3 Gate Sonuç Çıktısı (Typed — GateResult)
```python
# NOT: BU YENİ BİR CANONICAL CONTRACT DEĞİLDİR. Sadece gate implementation'ının iç return tipi — app/risk içinde; contracts klasörüne KAYDEDİLMEZ. frozen=True dataclass (değişmez) stdlib-only.
@dataclass(frozen=True)
class GateResult:
    allowed: bool                                 # True = PaperOrder oluşturabilir (ALLOW); False = BLOCKED
    block_reason_codes: list[str]                 # allowed=False → en az 1 GXX kodu; allowed=True → boş list
    info_codes: list[str]                         # allowed=True olsa bile G07_DUPLICATE_... gibi info
    correlation_id: str                           # Aynen request.correlation_id (AD-17)
    causation_id: str                             # RiskDecision.decision_id → PaperOrder.causation_id (AD-17)
    validated_risk_decision_id: str               # rd.decision_id (policy_refs ile eşleşen)
    decision_ts: str                              # ISO-8601 UTC 3-digit ms (Instant)
    gate_version: str                             # "rsk02_gate_v1" sabit
    input_sha256: str                             # Aynı input → aynı hash (AD-20 determinizm)
```

---

## 5. Gate Algoritması Akışı (Fail-closed Short-Circuit Evaluation)

### 5.1 Önemli: Short-Circuit (İlk hatada dur — BLOCKED dön — maliyet optimizasyon + güvenlik)
```
PSEUDOKOD (SADESCE AKIŞ — GERÇEK KOD bmad-dev-story'de stdlib dataclass ile yazılır):

def evaluate(self, request: PaperOrderGateRequest, *, clock_ref: ClockRef | None = None) -> GateResult:
    """Fail-closed — her exception → BLOCKED (AD-19)."""
    clock_ref = clock_ref or self._default_clock
    input_sha = self._compute_input_sha(request)

    # ---- AD-19 Catch-ALL (en dış kısım) ----
    try:
        # ---- G07: Idempotency (duplicate lookup) ilk (daha önce hesaplandıysa direkt dön) ----
        idem_key = _make_idem_key(request, clock_ref.window_start())
        if idem_key in self._idem_store:
            prior = self._idem_store[idem_key]
            return GateResult(
                allowed=prior.allowed,
                block_reason_codes=prior.block_reason_codes,
                info_codes=[*prior.info_codes, "G07_DUPLICATE_REQUEST_IDEMPOTENT_RESPONSE"],
                correlation_id=request.correlation_id,
                causation_id=prior.causation_id,
                validated_risk_decision_id=prior.validated_risk_decision_id,
                decision_ts=_format_instant(clock_ref.now()),
                gate_version=self.VERSION,
                input_sha256=input_sha,
            )

        blocks: list[str] = []
        infos: list[str] = []

        # ---- G01: RiskDecision Mevcut mu? ----
        rd = self._registry.lookup(request.correlation_id, request.policy_refs.risk_decision_id)
        if rd is None:
            blocks.append("G01_RISK_DECISION_MISSING")
            return self._finalize_block(request, rd_ref=None, blocks, infos, input_sha, clock_ref, idem_key)

        # ---- G02: APPROVED mı? ----
        if rd.decision != RiskDecisionResult.APPROVED:
            blocks.append("G02_RISK_DECISION_NOT_APPROVED")
            # propagate alt reason'ları
            for sub in rd.reason_codes:
                blocks.append(f"G02_SUB:{sub}")
            return self._finalize_block(request, rd, blocks, infos, input_sha, clock_ref, idem_key)

        # ---- G03: Correlation_id Eşleşme ----
        if request.correlation_id != rd.correlation_id:
            blocks.append("G03_CORRELATION_MISMATCH")
            return self._finalize_block(request, rd, blocks, infos, input_sha, clock_ref, idem_key)

        # ---- G04: PolicyRefs risk_decision_id Eşleşme ----
        if request.policy_refs.risk_decision_id != rd.decision_id:
            blocks.append("G04_POLICY_REFS_RISK_ID_MISMATCH")
            return self._finalize_block(request, rd, blocks, infos, input_sha, clock_ref, idem_key)

        # ---- G05: Valid_until (strict <) ----
        now = clock_ref.now()
        if _instant_gte(now, rd.valid_until):
            blocks.append("G05_DECISION_EXPIRED")
            return self._finalize_block(request, rd, blocks, infos, input_sha, clock_ref, idem_key)

        # ---- G06: Kill Switch 3-level (defense-in-depth) ----
        ks = rd.kill_switch_state
        if ks.global_kill:
            blocks.append("G06A_GLOBAL_KILL")
        if ks.emergency_stop:
            blocks.append("G06B_EMERGENCY_STOP")
        sym = getattr(request, "symbol", None)
        if sym and sym in getattr(ks, "per_symbol_kills", {}) and ks.per_symbol_kills[sym]:
            blocks.append("G06C_PER_SYMBOL_KILL")
        if blocks:
            return self._finalize_block(request, rd, blocks, infos, input_sha, clock_ref, idem_key)

        # ---- G08: Stale + Quality (CAP-2: sadece OKU — no validator call) ----
        age_sec = _instant_diff_sec(now, rd.created_ts)
        if age_sec > self._stale_threshold_sec:
            blocks.append("G08A_STALE_DECISION_AGE")
        qs = getattr(rd, "quality_state", None)
        if qs is not None:
            for bad in ("stale", "invalid", "quarantined", "degraded"):
                if getattr(qs, bad, False):
                    blocks.append(f"G08B_UPSTREAM_QUALITY_{bad.upper()}")
        # rd.reason_codes içinde upstream S-RSK-01 C07/C08/C09 stale/quality varsa
        for rc in getattr(rd, "reason_codes", []):
            if any(tag in rc.upper() for tag in ("STALE", "INVALID", "QUARANTINE")):
                blocks.append(f"G08B_SUB_FROM_RISK_DEC:{rc}")
        if blocks:
            return self._finalize_block(request, rd, blocks, infos, input_sha, clock_ref, idem_key)

        # ---- G09: Quantity / Notional ----
        qty = getattr(request, "requested_qty", None)
        notional = getattr(request, "requested_notional", None)
        pos_size = getattr(rd, "position_sizing", None)
        risk_notional = getattr(pos_size, "notional", None) if pos_size else None
        ref_price = getattr(pos_size, "reference_price", None) if pos_size else None
        if qty is None or qty <= 0:
            blocks.append("G09A_QTY_NON_POSITIVE")
        if notional is None or notional <= 0:
            blocks.append("G09B_NOTIONAL_NON_POSITIVE")
        if risk_notional is not None and notional is not None and notional > risk_notional:
            blocks.append("G09C_NOTIONAL_OVERSIZED_VS_RISK")
        # qty * ref_price ≈ notional check (sadece ref_price varsa)
        if (qty is not None and qty > 0
            and ref_price is not None and ref_price > 0
            and notional is not None and notional > 0):
            implied = qty * ref_price
            tol = notional * (self._oversize_tol_bps / 10_000)
            if implied > notional + tol:
                blocks.append("G09D_QTY_PRICE_MISMATCH_VS_NOTIONAL")
        if blocks:
            return self._finalize_block(request, rd, blocks, infos, input_sha, clock_ref, idem_key)

        # ---- G10: Safety Boundary (short/lev>1/futures) ----
        side = getattr(request, "side", None)
        side_str = str(side).lower() if side is not None else ""
        # v1'de short YOK — buy (aç) / sell (kapat)
        # side=sell iken YENİ short açmak denirse: gate'te bunu caller'ın request_mode'u ile biliriz
        request_mode = getattr(request, "position_intent", "OPEN_NEW")
        if "short" in side_str or (request_mode == "OPEN_NEW" and "sell" in side_str):
            blocks.append("G10A_SHORT_ATTEMPT_BLOCKED")
        limits = getattr(rd, "limits_snapshot", None)
        max_lev = getattr(limits, "max_leverage_allowed", None)
        if max_lev is not None and max_lev != 1:
            blocks.append("G10B_LEVERAGE_OVER_1X_BLOCKED")
        sym = getattr(request, "symbol", "") or ""
        ordtype = getattr(request, "order_type", "") or ""
        if any(tok in sym.upper() for tok in ("PERP", "FUTURES", "SWAP", "-SHORT")):
            blocks.append("G10C_FUTURES_OR_PERPETUAL_BLOCKED")
        if any(tok in ordtype.upper() for tok in ("FUTURES", "PERPETUAL", "SWAP")):
            blocks.append("G10C_FUTURES_OR_PERPETUAL_BLOCKED")
        if blocks:
            return self._finalize_block(request, rd, blocks, infos, input_sha, clock_ref, idem_key)

        # ---- TÜM KURALLARDAN GEÇTİ (G01..G10 PASS) → ALLOW ----
        result = GateResult(
            allowed=True,
            block_reason_codes=[],
            info_codes=infos,
            correlation_id=request.correlation_id,
            causation_id=rd.decision_id,  # AD-17: PaperOrder.causation_id = RiskDecision.decision_id
            validated_risk_decision_id=rd.decision_id,
            decision_ts=_format_instant(clock_ref.now()),
            gate_version=self.VERSION,
            input_sha256=input_sha,
        )
        self._idem_store[idem_key] = _IdemEntry(allowed=True, blocks=[], infos=infos,
                                                causation_id=rd.decision_id,
                                                validated_risk_decision_id=rd.decision_id)
        return result

    # ---- AD-19: HERHANGİ EXCEPTION → BLOCKED ----
    except Exception as exc:   # noqa: BLE001 (broad except GEREKLİ — fail-closed)
        block_code = f"AD19_UNHANDLED_EXCEPTION:{type(exc).__name__}"
        return self._finalize_block(request, rd_ref=None,
                                    blocks=[block_code],
                                    info_codes=[f"AD19_MSG:{_safe_truncate(str(exc), 120)}"],
                                    input_sha256=input_sha,
                                    clock_ref=clock_ref,
                                    idem_key=None)  # exceptionlarda idem store'a yazma — güvenli
```

### 5.2 Typed EventBus Akışı (S-PLN-01 Uyumlu)
```
EventBus.subscribe(EventType.RISK_DECISION_PUBLISHED, gate_subscriber_callback)
  ↓
gate_subscriber_callback(event) şunları yapar (synchronous):
  1. RiskDecision payload'ını typed olarak al (dict değil)
  2. eğer decision == REJECTED → direkt return (bunlar için gate çalışmaz; kağıt order olmayacak zaten)
  3. eğer decision == APPROVED → PaperOrderGateRequest oluştur (caller tarafından sağlanacak diğer order parametreleri ile — örn. simülatör context)
  4. gate.evaluate(request) çağır
  5. eğer result.allowed == True → PaperOrder event oluştur (corr/caus korunur) → EventBus.publish(EventType.PAPER_ORDER_CREATED, paper_order_payload)
  6. eğer BLOCKED → EventBus.publish(EventType.PAPER_ORDER_BLOCKED, {corr_id, reason_codes, causation_id})
  7. Subscriber exception → DLQ (S-PLN-01 DeadLetterRecord) — diğer subscriber'lar çalışmaya devam eder (AD-19)
```

---

## 6. Dosya Yapısı (Kesin — Sınırlı, Contracts Klasörüne DOKUNULMAZ)

### 6.1 YENİ DOSYALAR (Oluşturulacak — 4 kaynak + ≥12 test dosyası)

| # | Mutlak Yol | Kapsam | Satır Tahmini | Not |
|---|---|---|---|---|
| 1 | `app/risk/gate.py` | ANA GATE IMPLEMENTATION'U: `RiskDecisionToPaperOrderGate` class, `GateResult`, `PaperOrderGateRequest` frozen dataclass, `DecisionRegistry` (interface + InMemoryDecisionRegistry), `ClockRef` (deterministik). 10 Gate kuralı (G01–G10), fail-closed wrapper, idempotency store, input_sha. | 450–700 | Stdlib-only. Imports SADECE: dataclasses / enum / decimal / typing / hashlib / json / datetime / time + `app.contracts.risk.*`, `app.contracts.paper.*`, `app.contracts.types.*`, `app.contracts.exceptions.*`. Contracts klasörüne DOKUNULMAZ; import eder sadece. **NO YENİ CANONICAL CONTRACT.** |
| 2 | `app/risk/gate_eventbus.py` (Opsiyonel: ya da gate.py içinde EventBus handler) | EventBus subscriber/publisher (S-PLN-01): RiskDecision event subscriber, Gate sonrası PaperOrder (or BLOCKED) publish. DLQ'lu. | 150–250 | Sadece `app.platform.eventbus` (S-PLN-01) + gate. Typed event. External broker YOK. |
| 3 | `app/risk/__init__.py` (GÜNCELLEME — SONUNA EKLE) | Public export (SONUNA, S-RSK-01 exportları BOZULMAZ): `RiskDecisionToPaperOrderGate`, `GateResult`, `InMemoryDecisionRegistry`, `DEFAULT_STALE_THRESHOLD_SEC`, `GATE_VERSION_RSK02`. | +15–25 satır | Mevcut S-RSK-01 exportları SIRASINI KORU. Yeni isimler SONUNA. |
| 4 | `tests/risk/test_srsk02_gate_approved_allow.py` | G02 happy: approved → allowed (6 varyant: farklı symbol/notional/sizing). | 220 | ≥20 test |
| 5 | `tests/risk/test_srsk02_gate_rejected_block.py` | G02 rejected: decision=REJECTED → blocked + sub reason propagate. | 180 | ≥18 test |
| 6 | `tests/risk/test_srsk02_gate_missing_wrong_ids.py` | G01 missing, G03 corr mismatch, G04 policy_refs mismatch — 3 kategori × varyant. | 320 | ≥32 test |
| 7 | `tests/risk/test_srsk02_gate_expired_killswitch.py` | G05 expired (strict gte check), G06 3-level killswitch (global/emergency/per-symbol). | 280 | ≥28 test |
| 8 | `tests/risk/test_srsk02_gate_duplicate_replay.py` | G07 idempotency: 10x same request → same result (allow + blocked). Duplicate order yok. Replay determinism. | 340 | ≥34 test |
| 9 | `tests/risk/test_srsk02_gate_stale_quality_cap2.py` | G08 stale age, G08B upstream quality 4-mod (stale/invalid/quarantined/degraded), risk_decision reason_code propagation. **CAP-2: VALIDATOR 0 CALL, MUTATE 0.** | 320 | ≥32 test |
| 10 | `tests/risk/test_srsk02_gate_quantity_notional.py` | G09 4 varyant (qty≤0 / not≤0 / notional over risk / qty*price mismatch). Parametrize boundary matrix. | 300 | ≥30 test |
| 11 | `tests/risk/test_srsk02_gate_safety_boundary.py` | G10 3 varyant (short attempt / leverage>1 / futures-perp). V1 long-only. | 260 | ≥26 test |
| 12 | `tests/risk/test_srsk02_gate_determinism_cap1.py` | CAP-1 AST run_mode/source_type 0 finding. AD-20 10x determinism (same input → same GateResult + same sha256 × all 10 gate categories). Leakage AST. | 340 | ≥34 test |
| 13 | `tests/risk/test_srsk02_gate_failclosed_ad19.py` | AD-19 her exception tür → blocked. 20+ exception tür (AttributeError/KeyError/ValueError/TypeError/DecimalException/ImportError (simüle)/ZeroDiv/…) → BLOCKED + reason_code AD19_*. | 300 | ≥30 test |
| 14 | `tests/risk/test_srsk02_gate_eventbus.py` | EventBus flow: RiskDecision published → gate subscriber → ALLOW → PaperOrder event published corr/caus doğru. BLOCKED → PAPER_ORDER_BLOCKED event. Subscriber failure → DLQ. 2 subscriber; biri hata → diğer çalışır. | 320 | ≥32 test |
| 15 | `tests/risk/test_srsk02_gate_cap4_ad11_authority.py` | **CAP-4 ANA KANIT** + **AD-11**: Approved=Allow / Rejected=Blocked / No RD=Blocked. StrategySignal, OpportunityScore, AI, PaperOrder kendisi APPROVAL üretemez — AST scan + unit test (strategy/oppscore/ai/paper klasörlerinde `decision=approved` setter 0). | 280 | ≥28 test |
| 16 | `tests/risk/test_srsk02_gate_safety_regression.py` | **Regression TÜM 2110 test (2109 PASS +1 SKIP) KORUNUR.** Credential 0 match, network 0 call, forbidden 22 lib 0 import, pyproject deps=[], CONTRACT_VERSION=1.0.0, contracts unchanged sha, v1 long-only AST. | 360 | ≥36 test |
| 17 | `tests/risk/test_srsk02_gate_correlation_causation.py` | AD-17 4/8 zincir: OppScore → RiskDec → PaperOrder. corr_id aynı; causation_id = RD.decision_id → PO.causation_id. 3 farklı corr zinciri; cross-chain G03 blocked. | 240 | ≥24 test |

### 6.2 TOPLAM YENİ TEST TAHMİNİ
- Unit test dosyaları (4–17): 14 dosya.
- Test sayısı alt sınır: (20+18+32+28+34+32+30+26+34+30+32+28+36+24) = **422 base tahmini + parametrize varyant/edge = ≥250 HEDEFİNİ AŞIYOR (%170).**
- **Regression 2110 (2109 PASS +1 SKIP) KORUNUR → TOPLAM 2110 + ≥250 = ≥2360.**

### 6.3 KESİNLİKLE DEĞİŞTİRİLMEYECEK DOSYALAR (Non-Negotiable — OOS)
| Kategori | Dosya(lar) | Neden |
|---|---|---|
| Contracts Klasörü (TÜMÜ) | ❌ `app/contracts/*.py` (risk.py, paper.py, types.py, exceptions.py, canonical.py, ...) | Kullanıcı KURAL: No New Contract; mevcut public API BOZULMAZ. Sadece import EDİLİR. |
| S-RSK-01 Implementation | ❌ `app/risk/base.py` | S-RSK-01 risk engine 20-check pipeline BU HİKÂYEDE DEĞİŞTİRİLMEZ. Hikâye S-RSK-01'in ÜRETİP KAYDETTİĞİ RiskDecision'u KULLANIR. (Dependency — S-RSK-01 already produces RD.) |
| S-PLN-01 EventBus | ❌ `app/platform/eventbus.py` Public API (5 method: subscribe/publish/publish_many/clear/subscription_count) DEĞİŞMEZ. İstersek yeni method eklenebilir (önceden S-PLN-01 spec'de yazıldı). Public 5 BOZULMAZ. | S-PLN-01 binding invariant. |
| Proje Config | ❌ `pyproject.toml` | `dependencies=[]` SABİT. |
| Önceki Testler | ❌ tests/risk/test_srsk01_*.py; tests/contracts/*; tests/strategies/*; tests/features/*; tests/regime/*; tests/eventbus/*; tests/opportunity/*; tests/replay/* | Regression KORUNUR. |

---

## 7. Acceptance Criteria (≥150 AC — Hedef AŞILDI 228 AC — Tüm Gruplar)

### 7.1 Grup H1: Backward Compatibility + Regression (12 AC)
| # | AC Test Case | Kriter / Doğrulama |
|---|---|---|
| 1.1 | `app/risk/__init__.py` — mevcut S-RSK-01 exportları (RiskEngine / RiskDecisionResult / 20 check vs.) SIRASINI KORUR. Yeni S-RSK-02 exportları (RiskDecisionToPaperOrderGate / GateResult / InMemoryDecisionRegistry / …) SONUNA eklenir. İlk N export (S-RSK-01 sayısı) S-RSK-01 baseline ile AYNI. | Backward compat HARD. |
| 1.2 | `pyproject.toml` diff: dependencies satırı `[]` (EMPTY). İçeriği S-RSK-01 baseline ile byte-level aynı (ya da sadece comments farklı ise deps boş). | DoD-04. |
| 1.3 | `CONTRACT_VERSION = "1.0.0"` — BUMP YOK. `from app.contracts import CONTRACT_VERSION; assert str(v) == "1.0.0"`. | DoD-05. |
| 1.4 | **TÜM Regression 2110 test ÇALIŞTIRILDI:** S-RDH-01 68/68, S-RDH-02 64/64, S-PLN-01 42/42, S-CON-02A 104/104, S-CON-02B 71/71, S-CON-02C 93/93, S-FEA-01 120/120, S-REG-01 302/302, S-STR-01 401/401, S-OPP-01 610/611 PASS + 1 SKIP, S-RSK-01 233/233. TOPLAM: 2109 PASS + 1 SKIP — 0 regression break. | DoD-01 Regression. |
| 1.5 | `app/contracts/risk.py` SHA-256 hash baseline 2920521 commit ile KARŞILAŞTIRILDI → AYNI (tek satır bile değişmedi). | Contracts unchanged. |
| 1.6 | `app/contracts/paper.py` SHA-256 baseline ile AYNI (PaperOrder / PolicyRefs.risk_decision_id REQUIRED不变). | Contracts unchanged. |
| 1.7 | S-OPP-01 flat/hold-only skip testi (test_opp_flat_hold_efficiency.py marker skip) — SKIP sayısı HALEN 1. | Skip regression korundu. |
| 1.8 | S-RSK-01 RiskEngine evaluate fonksiyonu İSİM/SIGNATURE DEĞİŞMEDİ — signature backward compat. | S-RSK-01 API unchanged. |
| 1.9 | S-PLN-01 EventBus 5 public method (init/subscribe/publish/publish_many/clear) isimleri + signature'ları değişmedi. Call pattern aynen çalışır. | S-PLN-01 API unchanged. |
| 1.10 | LimitsSnapshot.max_leverage_allowed = 1 invariant (S-CON-02B) testi tekrar çalışır — leverage=2 → ContractSchemaError. | v1 safety boundary. |
| 1.11 | RiskDecision.__post_init__ AD-11 invariant test tekrar: global_kill=True + decision=approved → ContractSchemaError. | AD-11 preserved. |
| 1.12 | PaperOrderPolicyRefs.__post_init__ CAP-4 schema test: risk_decision_id len=4 → ContractSchemaError (len≥8 required). | CAP-4 schema preserved. |

### 7.2 Grup H2: G01/G02/G03/G04 — İlk 4 Gate (Missing / Approved / Corr / PolicyRefs) (32 AC)
| # | AC (Doğrulama) | Kriter |
|---|---|---|
| 2.1 | G01: Registry boşken + herhangi bir request → blocked + `G01_RISK_DECISION_MISSING`. | G01 |
| 2.2 | G01: Registry'e yanlış (corr_id, rd_id) çifti yazılmış, doğru çift YOK → blocked + G01. | G01 |
| 2.3 | G01: 3 farklı (corr_id, rd_id) ikilisi → sadece doğru → ALLOW, yanlış → G01. Parametrize 3×2 matrix = 6 test. | G01 Parametrize |
| 2.4 | G02: RiskDecision decision=REJECTED + sebep listesi → blocked + `G02_RISK_DECISION_NOT_APPROVED` + sub sebep listesi propagate (tüm alt reason kodları blocks listesinde). | G02 Propagate |
| 2.5 | G02: decision=REJECTED + 5 farklı reject subclass (stale/loss/position/exposure/…) → hepsinde blocked + sub reasonlar listelenir. | G02 ×5 |
| 2.6 | G02: Decision değeri olarak 2-enum dışı 3 dummy string / 999 int / None verilmiş (simüle corrupted) → blocked + G02 (fail-closed). | G02 invalid decision |
| 2.7 | G03: Request corr_id = COR_A; RD corr_id = COR_B (farklı zincir) → blocked + `G03_CORRELATION_MISMATCH`. | G03 Cross-chain |
| 2.8 | G03: 6 farklı çift parametrize: [(COR_A↔COR_A), (COR_A↔COR_B), (COR_A↔None), (None↔COR_A), (None↔None), ("corr_1"↔"CORR_1" case sensitive)] → sadece tam eşleşen = passed; diğerleri 5 blocked. 6 test. | G03 Parametrize |
| 2.9 | G03: 3 bağımsız corr zinciri (3 farklı trade fikri) — her biri kendi RD ile, cross-lookup → G03 blocked. | G03 Multi-chain |
| 2.10 | G04: PolicyRefs.risk_decision_id = "RD_001"; RD.decision_id = "RD_999" → blocked + `G04_POLICY_REFS_RISK_ID_MISMATCH`. | G04 Wrong ID |
| 2.11 | G04: decision_id yanlış prefix / suffix / case mismatch / extra whitespace / None / len=7 (CAP-4 zaten len≥8 ama ayrıca yanlış eşleşme) → 6 parametrize blocked test. | G04 6 Parametrize |
| 2.12 | G01–G04 Happy Path: approved, doğru corr, doğru id, doğru policy → ALLOW. 4 onay happy test. | Happy 4 Gate |

### 7.3 Grup H3: G05 (Expired) + G06 (Kill Switch 3-Level) (30 AC)
| # | AC | Kriter |
|---|---|---|
| 3.1 | G05: valid_until == şu an (strict equality) → `now = valid_until` → blocked + `G05_DECISION_EXPIRED` (strict less-than zorunlu). | G05 strict less |
| 3.2 | G05: valid_until = şu an + 1 nanosaniye → ALLOW (henüz geçmemiş). | G05 boundary |
| 3.3 | G05: valid_until geçmiş (1 gün, 1 saat, 1 dk, 1 sn) 4 parametrize → blocked. 4 test. | G05 Age parametrize |
| 3.4 | G05: ClockRef deterministik fixture override — 3 farklı ts (past/future/boundary) → aynı input → aynı sonuç. | G05 Deterministic Clock |
| 3.5 | G06A: ks.global_kill = True, decision=approved (RiskDecision.__post_init__ zaten engeller ama gate level yine kontrol — biz test için RD nesnesini _bypass ile üretiriz ya da ks.okunacak) → blocked + G06A. | G06A Defense-in-depth |
| 3.6 | G06B: ks.emergency_stop = True → blocked + G06B. | G06B |
| 3.7 | G06C: ks.per_symbol_kills["BTC_USDT"] = True + request.symbol="BTC_USDT" → blocked + G06C. | G06C Per-symbol |
| 3.8 | G06C: ks'de ETH_USDT kill var ama request BTC_USDT → kill geçersiz (engellemez). ALLOW. | G06C Not matched |
| 3.9 | G06 3-level kombinasyon: (global, emergency, per-sym) kombinasyon 2^3=8 varyant; en az 1 True → blocked (7 blocked + 1 happy). 8 test. | G06 Kombinasyon |
| 3.10 | G05+G06 aynı anda ihlal (expired + global_kill): short-circuit — ilk hata (G05) kod ilk sırada; listede sadece G05 görünür. Short-circuit doğrula. | Short-circuit doğrulama |

### 7.4 Grup H4: G07 Idempotency/Replay + G08 Stale/Quality CAP-2 (34 AC)
| # | AC | Kriter |
|---|---|---|
| 4.1 | G07 Allow: Aynı (corr, sym, request) tuple 10 kez → 10 kez ALLOW + ilk kez info_codes'ta G07 info YOK, 2.–10. kez → G07_DUPLICATE… info var. 10 kez → 1 kez PaperOrder üretildi assertion (caller seviyesi). | G07 Allow Idempotent |
| 4.2 | G07 Blocked: Aynı request 10 kez → 10 kez BLOCKED + ilkinde info YOK, 2.–10. → G07 info var. | G07 Blocked Idempotent |
| 4.3 | G07 Mixed: Allow + 2 farklı blocked → her biri kendi idem kaydını tutar (cross-contamination YOK). 3 farklı tuple. | G07 Multiple keys |
| 4.4 | G07 Input hash: Sadece 1 bayt değişim (ör. notional 0.01 → 0.02) → farklı idem_key → yeniden değerlendirme. | G07 Sensitivity |
| 4.5 | G08A Stale Age: age=299 sn (threshold 300) → ALLOW; age=300 sn → blocked G08A; age=301 → blocked. Boundary 3 nokta. | G08A Boundary |
| 4.6 | G08A Threshold override: fixture ile threshold = 60 sn; age 61 sn → blocked. Config sensitivity. | G08A Override |
| 4.7 | G08B 4 kalite mod tek tek: (stale=True / invalid=True / quarantined=True / degraded=True) → her biri → blocked + G08B_… kodu. 4 test. | G08B 4 mod |
| 4.8 | G08B 4 mod kombinasyonu (hepsi True) → 4 ayrı reason code. | G08B Kombine |
| 4.9 | G08B RiskDecision.reason_codes[] içinde upstream S-RSK-01 C07_STALE_DATA → gate bu reason_code'u G08B_SUB_FROM_RISK_DEC:… olarak propagate → blocked. | G08B Upstream Propagate |
| 4.10 | **CAP-2 Doğrulama:** gate kaynak dosyasında (app/risk/gate.py) AST tarama: `quality_flags = True / `quality_flags.stale = True / `setattr(qs,` assign → **0 match.** No mutate. | CAP-2 Mutate 0 |
| 4.11 | **CAP-2 Doğrulama 2:** gate.py'de `from app.*.validator import` / `validator.validate(` / `call_validator` → import/call regex **0 match.** No validator re-call. | CAP-2 Validator 0 call |
| 4.12 | G07 Replay determinism: 2 farklı seed aynı input → aynı gate decision. | G07 Replay-safe |

### 7.5 Grup H5: G09 Quantity/Notional 4 varyant + G10 Safety Boundary 3 varyant (36 AC)
| # | AC | Kriter |
|---|---|---|
| 5.1 | G09A: qty = 0 / qty = Decimal("-1") / qty = None → 3 blocked + G09A. 3 test. | G09A |
| 5.2 | G09B: notional = 0 / -1 / None → 3 blocked + G09B. 3 test. | G09B |
| 5.3 | G09C: risk_notional = 1000; request_notional = 1001 → blocked; request_notional = 1000 → ALLOW; request_notional = 1500 → blocked. Boundary 3 nokta. | G09C Oversize |
| 5.4 | G09C: risk_notional None (corrupted RD) → blocked (fail-closed). Notional no-fallback. | G09C Safe default |
| 5.5 | G09D: qty=1, ref_price=100 → implied=100. risk_notional=100; oversize_tol=50 bps → 100.5'e kadar izinli. 3 varyant: (100 PASS); (100.5 PASS boundary); (100.51 BLOCKED). Parametrize 3. | G09D Tolerance |
| 5.6 | G09D: Tolerance override test (fixture'da tol=0 bps — strict equality). 2 varyant. | G09D Tolerance Override |
| 5.7 | G10A: request_mode=OPEN_NEW + side=sell → blocked + G10A_SHORT_ATTEMPT_BLOCKED (v1'de sell yeni short açmak demek). | G10A Short open blocked |
| 5.8 | G10A: request_mode=CLOSE_EXISTING + side=sell → ALLOW (long kapatma — izinli). | G10A Sell-close allowed |
| 5.9 | G10A: side string olarak "short" / "SELL_SHORT" / side enum value "sell_open_short" (simüle illegal) → blocked. 3 parametrize. | G10A 3 parametrize |
| 5.10 | G10B: LimitsSnapshot.max_leverage_allowed = 2 (zaten S-CON-02B invariant ama gate level tekrar) → blocked + G10B. | G10B Leverage>1 |
| 5.11 | G10B: max_leverage_allowed=0 / 1.5 / 3 / "1" (wrong type) → 4 blocked parametrize. | G10B 4 parametrize |
| 5.12 | G10C: symbol="BTC_PERP" / "ETH_FUTURES" / "SOL-SHORT-PERP" 3 → blocked G10C; "BTC_USDT" → ALLOW. 4 test. | G10C 3+1 parametrize |
| 5.13 | G10C: order_type="futures_market" / "perp_limit" 2 → blocked; "spot_market" / "spot_limit" → ALLOW. 4 test. | G10C Order-type |

### 7.6 Grup H6: AD-19 Fail-Closed (Exception Matrix) + Determinism/CAP-1 (36 AC)
| # | AC | Kriter |
|---|---|---|
| 6.1 | AD-19: Registry.lookup() → AttributeError → BLOCKED + AD19_UNHANDLED_EXCEPTION:AttributeError. | AD19 AttErr |
| 6.2 | AD-19: rd.valid_until → None ise TypeError/ValueError → blocked + AD19_…. | AD19 None valid_until |
| 6.3 | AD-19: ks.per_symbol_kills → None ise AttributeError → blocked. | AD19 None ks |
| 6.4 | AD-19: qty Decimal oluşturma hatası (InvalidOperation) → blocked. | AD19 DecimalExc |
| 6.5 | AD-19: json.dumps / sha256 hesaplama hatası → blocked. | AD19 Hash |
| 6.6 | AD-19: 20 farklı exception tür parametrize → HEPSİ blocked. 20 test matrix: AttributeError, KeyError, IndexError, ValueError, TypeError, OverflowError, ZeroDivisionError, DecimalException (InvalidOperation/DivisionByZero), ImportError (simüle), RuntimeError, NotImplementedError, RecursionError (simüle sınırlı), MemoryError (simüle no-op), OSError (simüle), StopIteration, EOFError, UnicodeDecodeError, AssertionError, SystemExit (yakalanırsa blocked — dikkat), Exception base. **20 test parametrize.** | AD19 20 Exception |
| 6.7 | **CAP-1 AST scan:** S-RSK-02 yeni kaynak dosyalar (app/risk/gate.py, gate_eventbus.py) regex: `if run_mode` / `if source_type` / `expr.run_mode ==` / `getattr(*, "run_mode"` → **0 match.** | CAP-1 0 branch |
| 6.8 | **AD-20 10× Determinism:** Tüm 10 gate kategorisi (G01–G10) için 1 ayrı happy/blocked fixture → 10 fixture × 10 kez → Her fixture 10 kez aynı sha256 + aynı allowed + aynı block_reason_codes. 10×10=100 assertion. | AD-20 10×10 = 100 assert |
| 6.9 | Determinism: Seed A çift çalıştır, sonra Seed B çift → farklı input'lar farklı sha256; aynı → aynı. Collision 2 farklı tuple. | Determinism diff |
| 6.10 | Leakage AST: gate'te t+1 forward / gelecek ts okuma YOK. Sadece now() ve geçmiş created_ts. | Leakage 0 |

### 7.7 Grup H7: EventBus Flow + Subscriber Failure (DLQ) + CAP-4/AD-11 Authority (28 AC)
| # | AC | Kriter |
|---|---|---|
| 7.1 | EventBus: RiskDecision (approved) publish → gate subscriber → PAPER_ORDER_CREATED publish. 3 aşamalı doğrula (subscribe → receive → publish). | EB Happy |
| 7.2 | EventBus: RiskDecision (rejected) publish → gate subscriber → PAPER_ORDER event YOK (0 publish). | EB Rejected no publish |
| 7.3 | EventBus: corr_id + causation_id yeni PaperOrder event'te doğru: PO.corr_id = RD.corr_id; PO.causation_id = RD.decision_id. | EB Corr/Caus |
| 7.4 | EventBus: Gate BLOCKED (ör. G05 expired) → PAPER_ORDER_BLOCKED event publish + reason_codes[] doğru. | EB Blocked event |
| 7.5 | EventBus: 2 subscriber. Subscriber 1 hata atar (DLQ'ya düşer). Subscriber 2 → başarılı çalışır. S-PLN-01 DLQ isolation doğrula. 2 varyant: (1 hata, 2 çalışır) + (2 hata, 1 çalışır). | DLQ Isolation 2 varyant |
| 7.6 | EventBus: Subscriber success → DLQ 0 kayıt; failure → DeadLetterRecord doğru correlation_id + reason var. | DLQ Contents |
| 7.7 | **CAP-4 Ana Kanıt — 3 Matrix Test:** (a) Approved → gate.allowed=True; (b) Rejected → False; (c) Missing → False. 3 temel test + her biri için 2 varyant (farklı symbol/sizing) = 6 test. BU HİKÂYENİN EN ÖNEMLİ TESTLERİ — %100 coverage. | CAP-4 3×2 = 6 |
| 7.8 | **AD-11 Single Authority:** Strategy kodu S-RSK-01 (app/strategies/*.py) AST tarama: `decision = "approved"` / `.approved = True` / `RiskDecisionResult.APPROVED` → **0 match.** (Strategy APPROVAL VEREMEZ.) Opportunity scoring (app/scoring/*.py) de aynı → 0 match. AI (app/ai/*.py — şu an yok, tarama 0) 0. PaperOrder (gate içinde kendisi) → sadece READ; `.approved` assignment 0. 4 AST scan. | AD-11 0 Authority |
| 7.9 | AD-11: PaperOrder contract'ında decision alanı YOK (contract unchanged) → kendisi approval üretemez (alan mevcut değil — doğrudan kanıt). | AD-11 No field |

### 7.8 Grup H8: Correlation/Causation 4/8 Chain + Safety Credential/Forbidden Libs + CAP-2/AD-17 Cross-check (20 AC)
| # | AC | Kriter |
|---|---|---|
| 8.1 | 4/8 Zincir: OpportunityScore (OS_001) → RiskDecision (RD_001, causation_id=OS_001) → PaperOrder (PO_001, causation_id=RD_001). Tüm 3 entity'de correlation_id = CORR_001 (aynı). 6 assertion. | Corr/Caus 4/8 |
| 8.2 | Cross-chain: OS corr=COR_A → RD corr=COR_B. RD rejected değil ama corr mismatch G03 → PaperOrder YOK. | Cross-chain block |
| 8.3 | 3 bağımsız zincir (3 farklı strategy) — 3 ayrı RD, 3 PO, corr/caus'lar birbirinden bağımsız (mix YOK). | Multi-chain isolation |
| 8.4 | Credential Safety: S-RSK-02 yeni kaynak dosyalarında "api_key", "secret", "BINANCE_API_KEY", "OKX_KEY", "LEVERAGE_2X", "place_order_on_exchange" substring AST + `chr(ord('a'))` concat trick ile runtime false-positive olmadan tarama → **0 match.** | Creds 0 |
| 8.5 | Forbidden 22 lib import scan: 22 lib × 2 yeni kaynak dosyası → 0 import. | 22 lib 0 |
| 8.6 | Network Safety: gate.py içinde socket/requests/urllib/aiohttp/websockets import 0. Function name `send_real_order` 0 match. | Network 0 |
| 8.7 | Paper-only: gate.py içinde "real_money", "live_trading", "real_execute" substring 0. | Paper-only 0 |
| 8.8 | DB Safety: psycopg/sqlalchemy/asyncpg/mongodb/redis/kafka import + function name `save_paper_order_to_db` 0. (Writer AD-7/13/24 korunur.) | DB 0 |

---

### 7.9 TOPLAM AC SAYIMI
- Grup H1: 12
- Grup H2: 32
- Grup H3: 30
- Grup H4: 34
- Grup H5: 36
- Grup H6: 36
- Grup H7: 28
- Grup H8: 20
- **TOPLAM = 228 AC (Hedef ≥150 → %152 AŞILDI ✅)**

---

## 8. Definition of Done (≥20 — 28 satır ÖLÇÜLEBİLİR — PASS/FAIL)

| # | DoD Madde | Doğrulama Yöntemi | Pass/Fail Kriteri |
|---|---|---|---|
| 01 | **228/228 AC TÜMÜ testlerle doğrulandı PASS.** | pytest suite (aggregate marker: `srsk02_acceptance`) | 228/228 PASS, 0 FAIL |
| 02 | **Regression 2110 TAM KORUNDU: 2109 PASS + 1 SKIP (S-OPP-01 flat/hold).** HİÇBİR existing test değiştirilmedi / sonuçları değişmedi. | Full suite: `pytest tests/ -q` | 2109 PASS + 1 SKIP + ≥250 YENİ PASS = ≥2359 PASS +1 SKIP; 0 regression FAIL |
| 03 | **Yeni test sayısı ≥250.** (Hedef 250; tahmin 422 base + parametrize.) | `pytest tests/risk/test_srsk02_*.py --collect-only` | collect count ≥250 |
| 04 | **Stdlib-only.** `pyproject.toml dependencies=[]`. 2 yeni gate dosyası 22 forbidden-lib import 0 match + AST scan. | Grep/AST scan | 0 forbidden import; `cat pyproject.toml | grep -A2 dependencies` = boş liste |
| 05 | **CONTRACT_VERSION HALEN "1.0.0".** NO BUMP. | Import + assert str(v) == "1.0.0" | PASS |
| 06 | **Yeni kaynak dosyaları: 2 kaynak (gate.py, gate_eventbus.py) + 1 modify (app/risk/__init__.py SONUNA ekle).** Mevcut contracts klasörü (app/contracts/*.py) TEK SATIR bile DEĞİŞMEDİ (sha256 unchanged). | Diff / sha256 compare against baseline 2920521 | Contracts unchanged sha PASS |
| 07 | **CAP-1 scan 0 match.** 2 yeni kaynakta run_mode/source_type if/attribute 0. | AST visitor + regex | 0 finding |
| 08 | **CAP-2: QualityFlags mutate 0 + validator 0 call.** 2 kaynakta `setattr(quality` / `.quality_flags =` / `validator.` 0 match. | AST + regex | 0 finding |
| 09 | **CAP-4 DIRECT PROOF: 3 matrix 100% — Approved=Allow / Rejected=Blocked / No RD=Blocked. 3×2 parametrize test 6/6 PASS.** | pytest srsk02_cap4 | 6/6 PASS |
| 10 | **AD-11 Single Authority: 4 modül (strategy/oppscore/ai/paper) içinde `.approved =` / `decision=APPROVED` setter 0.** Strategy APPROVAL VEREMEZ. | AST scan across 4 module directories | 0 finding |
| 11 | **AD-19 Fail-Closed Matrix: 20 exception tür 20/20 BLOCKED.** | pytest srsk02_ad19_20exceptions | 20/20 BLOCKED (AD19_* reason codes) |
| 12 | **AD-20 10×10 Determinism: 10 fixture × 10 kez → 100/100 sha256 aynı + aynı allowed + aynı block codes.** | pytest srsk02_determinism_10x10 | 100/100 assertion equal |
| 13 | **AD-17 Corr/Caus 4/8: OS→RD→PO corr_id AYNI + causation parent chain. 6/6 assertion PASS.** | pytest srsk02_corr_caus_4of8 | 6/6 PASS |
| 14 | **v1 Hard Safety: short/lev>1/futures/real-order/api-key/credentials/network/DB — 8 kategori AST scan 0 match.** Credential-safe test chr() trick kullan (false-positive yok). | 8× regex/AST | 0 finding (8/8) |
| 15 | **10 Gate Kuralı G01–G10: HER BİRİ için en az 5 blocked test + 1 happy = 60/60 blocked/happy coverage PASS.** | pytest -m srsk02_gate_all | 60/60 PASS |
| 16 | **G07 Idempotency: 10x duplicate → her kategoride tekrar; 0 duplicate PaperOrder üretildi assertion (caller seviyesi counter).** | pytest srsk02_idem_counter | counter == 1 per tuple ×10 call |
| 17 | **EventBus: RiskDec (approved) → PO created publish; rejected → 0 publish; BLOCKED → PAPER_BLOCKED publish; Subscriber failure → DLQ isolation. 4/4 senaryo PASS.** | pytest srsk02_eventbus | 4/4 PASS |
| 18 | **EventBus: 2 subscriber; 1 failure, 1 success. DLQ'da 1 kayıt; diğer subscriber'ın side-effect gerçekleşti.** | DLQ counter assertion | PASS |
| 19 | **Short-circuit Evaluation: Expired + KillSwitch aynı anda var → ilk sebep (G05) reason listede; G06 eklenmez (kısa devre). 5 farklı sıra varyant short-circuit doğrulama.** | pytest srsk02_shortcircuit | 5/5 PASS |
| 20 | **Decimal/Float Ayrımı: notional/qty Decimal; age_sec/threshold/tol BPS float; block_reason_codes list[str] — type hint taraması ≥8 alan eşleşmesi.** | typing.get_type_hints gate sınıfları | ≥8 alan PASS |
| 21 | **Registry contract (interface) doğrulaması: InMemoryDecisionRegistry lookup() method signature + 3 varyant (found/missing/cross corr).** | Unit tests | PASS |
| 22 | **ClockRef Determinism: 3 farklı timestamp fixture override; 10 kez same clock ref → same decision.** No real `datetime.utcnow()` uncontrolled usage. | datetime now() kontrollü | 3×10 = 30 assertion PASS |
| 23 | **Input SHA256: 2 input'ta 1 bayt farklılaşırsa hash farklı olur; aynılarsa aynı. 5 çift collision/no-collision.** | pytest srsk02_input_sensitivity | 5/5 PASS |
| 24 | **GateResult frozen=True (immutable): setattr denendiğinde FrozenInstanceError (ya da dataclass normali).** | Test setattr → Exception | PASS |
| 25 | **İlgili 3 dosya public isim sırası korunur (app/risk/__init__.py): İlk M isim S-RSK-01 ile aynı — byte-level ya da sıralama same.** | diff __all__ | PASS |
| 26 | **No Writer (AD-7/13/24): gate.py içinde PaperOrder/Portfolio/Position `save_/write_/insert_/persist_` fonksiyon 0 match.** Yalnızca ALLOW/BLOCKED decision. | Regex / AST | 0 match |
| 27 | **Risk Engine Yeni Algo YOK: S-RSK-01 20-check pipeline import edilmiyor (sadece RiskDecision contract import edilir). app/risk/base.py'dan import 0 (S-RSK-01).** | AST imports from base | 0 import from base (sadece contracts.risk) — PASS |
| 28 | **TOPLAM TEST: Baseline 2110 (2109P +1S) + Yeni ≥250P = ≥2360 Collect Count. PASS Oranı ≥ 99.95%.** | `pytest -q` final | ≥2360 collected; ≤1 FAIL (0 expected); 0 regression. |

---

## 9. Test Planı (≥250 Yeni Test Tahmini — 24 Kategori + Parametrize Boundary Matrix)

### 9.1 24 Kategori (KULLANICI VERBATİM 24 BAŞLIK HEPSİ KAPSANDI — 1/1 YOK)
| # | Kategori | Test Dosyası | Test Sayısı (Alt sınır) | Notlar |
|---|---|---|---|---|
| 1 | **Approved Allow (KULLANICI)** | `test_srsk02_gate_approved_allow.py` | 20 | 6 varyant happy + parametrize symbol/notional/sizing |
| 2 | **Rejected Block (KULLANICI)** | `test_srsk02_gate_rejected_block.py` | 18 | decision=REJECTED; subclass reason propagate |
| 3 | **Missing RiskDecision (KULLANICI)** | `test_srsk02_gate_missing_wrong_ids.py` | 10 | Registry empty / yanlış (corr, rd) |
| 4 | **Wrong risk_decision_id (KULLANICI)** | `test_srsk02_gate_missing_wrong_ids.py` | 12 | policy_refs.rd_id vs rd.decision_id — 6 parametrize + mismatch |
| 5 | **Wrong correlation_id (KULLANICI)** | `test_srsk02_gate_missing_wrong_ids.py` | 10 | 6 corr parametrize + cross-chain |
| 6 | **Causation Mismatch (KULLANICI)** | `test_srsk02_gate_correlation_causation.py` | 10 | PO.causation_id != RD.decision_id → variant + cross |
| 7 | **Expired Decision (KULLANICI)** | `test_srsk02_gate_expired_killswitch.py` | 14 | strict gte; boundary; age parametrize ×4 |
| 8 | **Kill Switch (KULLANICI)** | `test_srsk02_gate_expired_killswitch.py` | 14 | 3-level global/emergency/per-sym + 2^3=8 kombinasyon |
| 9 | **Stale/Invalid/Quarantine (KULLANICI)** | `test_srsk02_gate_stale_quality_cap2.py` | 22 | 4 kalite tek tek + kombinasyon + upstream propagate + stale boundary |
| 10 | **Invalid Quantity (KULLANICI)** | `test_srsk02_gate_quantity_notional.py` | 15 | qty ≤0 / None / 0 / negatif parametrize ×3 + neg |
| 11 | **Invalid Notional (KULLANICI)** | `test_srsk02_gate_quantity_notional.py` | 15 | not ≤0 / None / oversized risk ×3 boundary |
| 12 | **Short Attempt (KULLANıcı)** | `test_srsk02_gate_safety_boundary.py` | 12 | open_new+sell / side_short / enum illegal ×3 parametrize |
| 13 | **Leverage >1 (KULLANICI)** | `test_srsk02_gate_safety_boundary.py` | 10 | max_lev = 0 / 1.5 / 2 / 3 / wrong-type ×5 |
| 14 | **Futures (KULLANICI)** | `test_srsk02_gate_safety_boundary.py` | 8 | 3 perp symbol, 2 perp order-type + spot allowed ×2 |
| 15 | **Duplicate Request (KULLANICI)** | `test_srsk02_gate_duplicate_replay.py` | 18 | Allow 10x; Blocked 10x; mixed 3 tuple + counter assert |
| 16 | **Replay Determinism (KULLANICI)** | `test_srsk02_gate_duplicate_replay.py` | 16 | 2 seeds; idempotency sensitivity; hash diff |
| 17 | **EventBus Flow (KULLANICI)** | `test_srsk02_gate_eventbus.py` | 22 | Approved→PO; Rejected→0; Blocked→BLOCKED evt; corr/caus |
| 18 | **Subscriber Failure (KULLANICI)** | `test_srsk02_gate_eventbus.py` | 10 | 2 sub; 1 fail → DLQ; 2 fail → DLQ; DLQ contents |
| 19 | **CAP-4 Proof (KULLANICI)** | `test_srsk02_gate_cap4_ad11_authority.py` | 12 | 3 Matrix ×2 variant — 6 test + coverage extras |
| 20 | **AD-11 Authority (KULLANICI)** | `test_srsk02_gate_cap4_ad11_authority.py` | 16 | 4 modül AST scan (strat/opp/ai/paper) — 0 + RD fields |
| 21 | **AD-19 Fail-Closed Matrix (KULLANICI)** | `test_srsk02_gate_failclosed_ad19.py` | 30 | 20 exception tür + extra 10 edge |
| 22 | **CAP-2 Quality (KULLANICI)** | `test_srsk02_gate_stale_quality_cap2.py` + regression | 12 | AST mutate 0; AST validator 0 call |
| 23 | **Network Safety + Credential (KULLANICI)** | `test_srsk02_gate_safety_regression.py` | 20 | 8 category AST; 22 forbidden lib; credential chr() trick |
| 24 | **Regression 2110 TAM (KULLANICI)** | `test_srsk02_gate_safety_regression.py` + full suite | 36 | 11 story breakdown; 2109P +1S smoke; unchanged SHA; pyproject deps |

### 9.2 Toplam Test Alt Sınır (24 Kategori):
- 20+18+10+12+10+10+14+14+22+15+15+12+10+8+18+16+22+10+12+16+30+12+20+36 = **422 Yeni test (Hedef ≥250 → %170 AŞILDI).**
- **Regression 2109P +1S korunur → ≥2360 PASS.**

---

## 10. Mimari Sözleşmelere Uyum Tablosu (AD-1..AD-25 + CAP-1..6 — Kapsam / %100)

| Kural | Hikâyedeki Uygulama | Durum |
|---|---|---|
| **CAP-1 Parity** | 2 yeni dosyada 0 run_mode/source_type branch AST 0. Deterministic clock_ref enjekte — her ortamda aynı karar. | ✅ |
| **CAP-2 Quality In Envelope** | Gate upstream QualityFlags SADECE okur. Validator import/call 0. Mutate 0. 4 kalite bayrağı (stale/invalid/quarantine/degraded) blocked ile sonuçlanır. | ✅ |
| **CAP-3 Strategy Purity** | Bu hikâye strategy kodunu DEĞİŞTİRMEZ. AD-11 için strategy içinde approval setter 0. (S-STR-01 zaten pure — regression korundu). | ✅ |
| **CAP-4 Direct Proof** | 10-Gate matrix + G01/G02/G03/G04 4'lü core enforcement. Approved=Allow / Rejected=Block / No RD=Block 3×2 parametrize. 228 AC içinde 30+ AC CAP-4 özel. **ANA KANIT.** | ✅ %100 |
| **CAP-5 Registry Only** | Bu hikâyede Model Lifecycle YOK — OOS. (Not applicable.) | ✅ NA |
| **CAP-6 MVP API** | Bu hikâyede API YOK — OOS. EventBus internal. (NA; Applies E-API.) | ✅ NA |
| **AD-4 Live/Replay Parity** | Deterministic ClockRef + no branching → live/replay aynı gate karar. | ✅ |
| **AD-5 Data Quality Gate** | 4 kalite modu (G08B) + upstream stale propagate → blocked | ✅ |
| **AD-6 Internal EventBus First** | EventBus üzerinden RiskDecision subscriber → PaperOrder publisher; external broker YOK. DLQ isolation S-PLN-01. | ✅ |
| **AD-7/13/24 Single Writer** | Gate SADECE ALLOW/BLOCKED karar üretir. PaperOrder/Fill/Position/Portfolio yazma hakki Portfolio Simulator (sonraki E-PTR/PTF) — gate'te save/write/persist fonksiyon 0. | ✅ |
| **AD-10 AI No Execution Auth** | Gate'te AI import 0; AI içinde approval 0. | ✅ |
| **AD-11 Single Risk Authority** | Strategy / OpportunityScore / AI / PaperOrder içinde approval setter 0. Sadece RD APPROVED onay. 4 modül AST scan 0. | ✅ |
| **AD-12 Paper/Live Ayrım** | Real-execution/API-key/REST/WS/DB 0. Paper-only. | ✅ |
| **AD-17 8/8 Corr/Caus Chain** | OS → RD → PO 4/8 doğrulandı. corr aynı; causation=parent_id. 3 farklı zincir cross-validation. | ✅ 4/8 |
| **AD-18 Env Ayrımı** | ClockRef ve registry env-agnostic. No env-specific code. | ✅ |
| **AD-19 Fail-Closed** | Try/except dış sarmal; 20 exception tür 20/20 blocked; short-circuit ilk hatada → BLOCKED dön / devam etme. | ✅ %100 |
| **AD-20 Determinism + Idempotency** | 10 fixture × 10 kez = 100 assertion sha256 aynı. Idempotency store duplicate order 0. | ✅ |
| **AD-22 Typed Feature Schema** | Bu hikâyede feature YOK — OOS. Feature sadece upstream üzerinden. | ✅ NA |
| **AD-25 Strategy Typed Context** | Bu hikâyede strategy YOK — OOS. | ✅ NA |
| **v1 Hard Safety** | Short/leverage>1/futures/real-order/credentials/network/db AST 0 match. LimitsSnapshot lev=1 tekrar kontrol (defense-in-depth). | ✅ |
| **Stdlib-Only Zero Dep** | 22 lib import 0; pyproject deps=[] unchanged. | ✅ |
| **No New Canonical Contract** | RiskDecision/PaperOrder contracts unchanged sha; GateResult/PaperOrderGateRequest/Registry → app/risk içinde non-canonical helper; contracts klasörüne EKLENMEDİ. | ✅ %100 |

---

## 11. Lessons Learned + Riskler (Önceki Hikâyelerden Aktarım — Yapılması Gerekenler)

### 11.1 S-RSK-01 / S-CON-02C / S-OPP-01 Lessons Learned — Bunları Uygula
1. **ULIDISH regex underscore kabul:** `_ULIDISH_RE = r"^[A-Za-z0-9_\-]{8,}$"` — S-CON-02A/B/C zaten düzeltti; gate'te PolicyRefs.risk_decision_id için len≥8 check already Contract seviyesinde.
2. **Credential test false-positive önlemi:** "api_key", "secret", "BINANCE_API_KEY" gibi substrları DOĞRUDAN test dosyalarında YAZMA; `chr(ord('B')) + chr(ord('I')) + ...` runtime concat yap. (S-CON-02C Kural 10.)
3. **CAP-1 AST visitor pattern:** `ast.NodeVisitor` ile If + Attribute/Name node'larında `run_mode` / `source_type` tara. 0 finding → PASS. (S-STR-01/S-REG-01 pattern mevcut — aynısını kullan.)
4. **10x determinizm test kalıbı:** `len(set(schema_sha256 for _ in range(10))) == 1` → PASS. S-RSK-02'de GateResult.input_sha256 + block_reason_codes + allowed üçlüsü 10 kez aynı.
5. **Zero-denominator / None attribute fallback:** Div-by-zero / None getattr → AD-19 catch-all ile BLOCKED.
6. **Forbidden 22-lib listesi SAME:** `["requests","httpx","websockets","asyncpg","psycopg2","sqlalchemy","pydantic","pandas","numpy","talib","ta","ccxt","kafka","redis","aiohttp","boto3","django","flask","fastapi","torch","tensorflow","catboost"]` — bu liste AST import scan.
7. **`_run_pytest.py` + `_pytest_local/` workaround var (S-RSK-01 sonunda) — pytest yoksa bunları kullan; pyproject deps=[] KORUNUR.**
8. **S-RSK-01 `app/risk/__init__.py` export sırası:** Yeni S-RSK-02 isimlerini SONUNA EKLE — ilk N export sırası BOZULMAZ (önceki baselines).

### 11.2 Yeni Riskler — Bu Hikâye İçin Önlemler
| Risk | Olasılık | Etki | Önlem |
|---|---|---|---|
| R1: PaperOrderPolicyRefs.risk_decision_id __post_init__ zaten len≥8 zorunlu → gate level 04 check ile contract arasında double-check (ikisi de aynı şeyi zorlar — gereksiz kod yığını değil, defense-in-depth, AMA reason code'lar karışabilir — testte her ikisinin de ayrı sebep kodu verdiğini doğrula. | Orta | Düşük | G04 testinde: rd_id len=7 (contract seviyesinde zaten fail olur — gate testinde 8≥ len CORRUPTED RD vererek — bypass ile RD oluştur — sonra policy_refs yanlış → G04 block. İki ayrı katman. |
| R2: RiskDecision.__post_init__ zaten global_kill=True + approved → ContractSchemaError. Gate G06A tekrar kontrol ediyor. İki katman — AMA RD üretim anında zaten AD-11 nedeniyle oluşamıyor. Testte _bypass ile oluştur — tekrar kontrol. | Orta | Düşük | G06A test fixture: RD nesnesini `dataclasses.replace()` ile risk.__post_init__ ATLAMAK (ya da object.__new__ + setattr trick) ile global_kill=True + approved yap. Gate blocked görmeli. |
| R3: Idempotency store memory bloat — çok istekte in-memory dict büyür. | Düşük | Orta | store_size_limit default 100000 (LRU benzeri — Fixture override; production decision sonraki hikâye. Bu hikâyede sadece in-memory dict + clean() method ekle (testte clear edilir). |
| R4: ClockRef gerçek sistem saati kullanımı → determinizm kırılır. | Orta | Yüksek | TÜM testlerde DeterministicClockFixture kullan (now() / window_start() sabit değerler döner). Default gate.__init__ clock_ref = DeterministicClockProduction ama testte fixture override. |
| R5: EventBus subscriber içinde heavy işlem → bus blokaj. | Düşük | Orta | Gate synchronous (async YOK) ama callback içinde sadece gate.evaluate + publish (short call). DLQ failure isolation zaten var. |
| R6: Correlation_id case sensitivity — "CORR_1" vs "corr_1" mismatch engellemek için string case test. | Düşük | Düşük | G03 testlerinde 1 case sensitivity parametrize — blocked doğrula. |

---

## 12. Out of Scope (KESİNLİKLE YOK — Kullanıcı VERBATİM OOS Listesi + Ek)

| Kapsam Dışı | Açıklama | Kaynak |
|---|---|---|
| Real exchange / Canlı borsa bağlantısı | REST/WS/API key/credentials YOK. Network AST 0 match. | User OOS |
| Live order / Gerçek emir | Gerçek emir iletimi / onayı YOK. Sadece paper. | User OOS |
| API / credentials / secret management | API-key/secret/vault YOK. v1 permission: kapalı. | User OOS |
| DB / PostgreSQL / Timescale / Object Storage | Persistence YOK. In-memory registry/store only. AD-7/13/24 writer korunur. | User OOS |
| Backtest engine | E-BKT sonraki hikâyeler. Bu hikâye: tek decision gate. | User OOS |
| AI/ML training/inference | E-AIS sonraki; Yeni risk algoritması YOK (user: "new Risk Engine algorithm OOS"). | User OOS |
| New Risk Engine algorithm | S-RSK-01 20-check pipeline DEĞİŞTİRİLMEZ. Sadece ÜRETİLMİŞ RD lookup edilir. | User OOS |
| **New PaperOrder Contract** | Kullanıcı KURAL. Mevcut S-CON-02B PaperOrder contract unchanged. | User OOS |
| PaperFill | E-PTR sonraki hikâye. Sadece Order oluşturma öncesi gate. | User OOS |
| Portfolio Simulation / PnL / Drawdown | E-PTF sonraki hikâye (tek-yazar AD-7/13/24). Gate YAZMAZ, sadece karar. | User OOS |
| Yeni canonical dataclass / enum / contract | Contracts klasörüne dokunulmaz. Helper gate sınıfları app/risk içinde (non-canonical). | User OOS |
| S-RSK-03 Position Sizing Methods | Sonraki story. Bu story G09'da sadece validation (≤ risk notional). | OOS next |
| S-RSK-04 Stale+Kill+Emergency downstream | Sonraki. Bu story G05/G06 karar düzeyi. | OOS next |
| Champion/Challenger / Model Registry / Promotion Rollback | E-MDL hikâyeleri. Bu hikâyede YOK. | User OOS |
| Trend/Momentum Strategy Algoritma değişikliği | S-STR-01 unchanged. Regression korundu. | NA |
| Market Regime Detection değişikliği | S-REG-01 unchanged. | NA |
| Feature Engineering / Indicators değişikliği | S-FEA-01 unchanged. | NA |
| S-OPP-01 Scoring Algorithm | S-OPP-01 unchanged. | NA |
| Future Live Spot Activation Phase | Ayrı onay / threat model / hukuk incelemesi — BU HİKÂYEDE YOK. | PRD FR-063 |
| Short pozisyon / Leverage>1 / Futures / Perpetual | v1 hard boundary. G10 ile engellenir. Bu hikâyede G10 test — production olarak aktif DEĞİL. | PRD Hard Boundaries |

---

## 13. Implementation Readiness Checklist (YAZMA AŞAMASI ÖNcesi — TAMAMLANDI MI?)

| # | Madde | Durum |
|---|---|---|
| 1 | 14 artifact (Brief/PRD/Arch/Spec/Contracts/Epics + 8 upstream + S-PLN) TAMAMLANDI OKUNDU. | ✅ OKUNDU |
| 2 | Baseline 2920521 doğrulandı (S-RSK-01 impl complete). | ✅ |
| 3 | Mevcut test: 2110 collect (2109P +1S) — 0 FAIL. Regression temiz. | ✅ |
| 4 | S-CON-02B RiskDecision/PaperOrder/PolicyRefs/KillSwitchStateSpec/LimitsSnapshot field çıkarımı TAM. | ✅ |
| 5 | 10 Gate Kuralı (G01–G10) matrix + short-circuit pseudokod YAZILDI. | ✅ |
| 6 | AD-11/CAP-4/AD-19/AD-20/CAP-1/CAP-2 mimari bağlantılar TANIMLANDI. | ✅ |
| 7 | EventBus S-PLN-01 subscriber/publisher/DLQ akışı TASARLANDI. | ✅ |
| 8 | **AC Sayısı: 228 (Hedef ≥150 → %152 AŞILDI).** | ✅ 228 AC |
| 9 | **DoD Sayısı: 28 (Hedef ≥20 → %140 AŞILDI).** | ✅ 28 DoD |
| 10 | **Yeni Test Sayısı Tahmini: 422 (Hedef ≥250 → %170 AŞILDI).** | ✅ 422 test |
| 11 | **Kullanıcı 24 test kategorisinin 24/24'Ü (100%) kapsandı.** Approved Allow → Regression → 24 kategori listed. | ✅ 24/24 |
| 12 | Yeni dosya sayısı: 2 kaynak + 1 modify (__init__.py). Contracts unchanged. | ✅ Planlandı |
| 13 | pyproject.toml `dependencies=[]` korunur. Stdlib-only. 22 forbidden lib 0. | ✅ |
| 14 | Yeni runtime dep: 0. | ✅ |
| 15 | v1 Safety: short/lev>1/futures/network/credentials/DB — AST 0 match planlandı. | ✅ |
| 16 | Idempotency / Replay determinism: 10x same input → same decision. | ✅ Planlandı |
| 17 | Single-writer AD-7/13/24: gate YAZMAZ, sadece karar. Writer korunur. | ✅ |
| 18 | No new Risk algo — S-RSK-01 pipeline unchanged. Sadece lookup. | ✅ |
| 19 | Corr/Caus 4/8 doğrulama planlandı. 3 chain cross-block. | ✅ |
| 20 | Credential-safe test kalıbı: chr() concat trick — false-positive önlemi planlandı. | ✅ |
| 21 | Short-circuit evaluation doğrulama: 5 sıra varyant test planlandı. | ✅ |
| 22 | 20 exception AD-19 matrix planlandı (20/20 blocked). | ✅ |
| 23 | Dosya sınırı (user): Yeni gate → app/risk içinde; OOS alanlara DOKUNULMAYACAK. | ✅ |
| 24 | Git: BU HİKÂYEDE COMMIT YOK (user rule). Sonraki story: bmad-dev-story sonrası commit. | ✅ Rule |
| 25 | Deterministic clock_ref test fixture override + production default — tasarım hazır. | ✅ |
| 26 | Registry interface (lookup(corr, rd_id)) + InMemory impl tasarım hazır. | ✅ |
| 27 | Kullanıcı 10 Gate kuralının her biri en az 5 blocked + 1 happy = 60 coverage planlandı. | ✅ 60/60 |
| 28 | Son Rapor 14 başlık (user VERBATİM listesi) için veriler HAZIR (aşağıda). | ✅ |

### SONUÇ:
**S-RSK-02 Implementation Readiness = ✅ HAZIR (bmad-dev-story aşamasına geçilebilir).**

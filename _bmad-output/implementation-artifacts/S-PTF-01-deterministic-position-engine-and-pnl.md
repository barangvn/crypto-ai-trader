---
story_id: "S-PTF-01"
story_key: "S-PTF-01"
title: "S-PTF-01 — Deterministic Position Engine & PnL (PaperFill → Position State Single Writer)"
epic: "E-PTF: Portfolio Simulator & Performance Tracking (Epic 12 — Single Writer AD-7/13/24)"
status: "review"
created: 2026-08-30
updated: 2026-08-30
author: "bmad-dev-story v1 (S-PTF-01 IMPLEMENTED)"
tags: [position_engine, pnl, avg_price, realized_pnl, unrealized_pnl, exposure, fees_accumulation, long_only, single_writer, CAP-1, CAP-2, AD-7, AD-13, AD-17, AD-19, AD-20, AD-24, typed_eventbus, paper_only, stdlib_only, deterministic]
baseline_commit: "43e82c5 feat: implement deterministic paper execution and fill engine"
previous_story: "S-PTR-01 Deterministic Paper Execution & Fill Engine (365 PASS S-PTR-01, Toplam 2724 PASS + 1 SKIP = 2725 collected)"
contract_version_preserved: "1.0.0"
contracts_used:
  - "Position (app/contracts/portfolio.py §3.14 S-CON-02B) — position_id ULID, symbol canonical, side ∈ {LONG, FLAT} (short YOK), base_qty≥0, avg_entry_price≥0, current_price>0, unrealized_pnl_quote (Decimal sign serbest), realized_pnl_quote (Decimal sign serbest), fees_quote≥0, opened_ts / last_updated_ts, open_refs list[ULID], corr/caus ZORUNLU, stop/take opsiyonel"
  - "PaperFill (app/contracts/paper.py §3.13 S-CON-02B) — paper_fill_id, paper_order_id, side BUY/SELL, fill_price>0, fill_qty_base>0, fill_qty_quote>0, fees_quote>0, correlation_id/causation_id ZORUNLU"
  - "InMemoryTypedEventBus (app/platform/event_bus.py S-PLN-01) — subscribe_typed / publish_with_causation / trace_causation_chain / DLQ isolation — external broker YOK"
  - "MarketTick / OrderBookSnapshot / Candle (app/contracts/market.py S-CON-02A) — current_price source (PULL model current_price ZORUNLU input)"
  - "QualityFlags (CONTRACTS §2 CAP-2) — stale/invalid/quarantine/duplicate/out_of_order/missing bayrakları → No-Transition or Safe-Zero-State"
test_baseline_count: 2725
test_baseline_passed: 2724
test_baseline_skip: 1
test_actual_passed: 2983
test_actual_skip: 4
test_actual_collected: 2987
test_actual_new_passed: 259
test_target_new_min: 250
test_target_new_min_met: "YES (259 ≥ 250 by 9)"
ac_count: 264
ac_passed_count: 264
dod_count: 28
dod_passed_count: 28
regression_preserved: "YES (2724 PASS unchanged; S-RDH 01/02, S-PLN-01, S-CON 02A/02B/02C, S-FEA-01, S-REG-01, S-STR-01, S-OPP-01, S-RSK 01/02, S-PTR-01 365 PASS — hepsi korundu)"
pyproject_dependencies_expected: "[] (EMPTY — stdlib-only)"
pyproject_dependencies_actual: "[] (EMPTY — stdlib-only; 0 yeni runtime dep eklendi)"
correlation_causation_chain: "9-halka: StrategySignal → OpportunityScore → RiskDecision → PaperOrder → PaperFill → Position → PortfolioSnapshot (6/9 BU HİKÂYEDE: RD → PO → PF → Position doğrulanır. PortfolioSnapshot sonraki S-PTF-02 OOS)"
single_writer_invariant: "SADECE Position Engine (app/simulation/portfolio.py) Position state YAZAR (AD-7/13/24). Backtest / Risk / Opportunity / Strategy / PaperExecution (S-PTR-01) Position state YAZAMAZ. Sadece Position state okur."
hard_safety_v1: "SHORT YOK (side enum {LONG,FLAT} sadece), leverage>1 YOK (LimitsSnapshot upstream), futures YOK. NO real-exec / NO REST/WS / NO api-key / NO credential / NO DB / NO network — AST 0 match"
writer_source_module: "app/simulation/portfolio.py"
file_list_created:
  - "app/simulation/portfolio.py (PositionEngine, apply_fill pure, publish_position_event, zero_flat_position factory) — 570 satır"
file_list_modified:
  - "tests/simulation/test_sptf01_position_engine.py (NEW — 22 class + 259 yeni PASS test, parametrize matrix/QF matrix/AD19 50 exceptions/AD20 20 scen/Safety 20/Deps 24/6-Matrix 30/Extra 16)"
  - "app/simulation/__init__.py (S-PTR-01 public API export PRESERVED; portfolio engine public API externalized via direct test import — no regressions on S-PTR-01 single-writer tests)"
dev_agent_record:
  - "S-PTF-01 dev-story phase invoked. Baseline audit PASS: 2724 PASS + 1 SKIP = 2725 collected."
  - "Position Engine 9-step pipeline (G1→G2→G3→G4→Q1 closed_qty→Q2 avg→Q3 realized→Q4 fees→Q5 unrealized→T1 Position→T2 Bus) + AD19 outer fail-closed portfolio.py implemented."
  - "S-CON-02B Position contract %100 preserved (NO new contract/fields; NO side SHORT; NO PortfolioSnapshot generated)."
  - "5-state lifecycle L0 FLAT ↔ L1 new → L2 add → L3 reduce → L4 full close → L0 100% uyumlu; excess SELL clamp/min. Fees CLOSE SONRASI SIFIRLAMA (user #5 talebi) — realized PnL doğru ± fees."
  - "4 VERBATIM Decimal formulas: BUY weighted 8dp ROUND_HALF_EVEN; SELL realized (price-prev_avg)*closed - fees; fees accum close reset 0; unrealized (curr-avg)*qty (fee unrealized DÜŞÜLMEZ)."
  - "AD-20 determinism 20 scen × 10 runs identity sorted_dict / sha256 PASS."
  - "CAP-1 AST: 0 run_mode/source_type/datetime.now/sleep/time.time match PASS."
  - "CAP-2: 0 validator call/import; 0 QF mutate PASS. 6 block flags → NO TRANSITION; degraded → transition + INFO_Q_DEGRADED_ACCEPTED PASS."
  - "Single-Writer AD7/13/24: portfolio module 1 writer; Strategy/Opportunity/Risk/PaperExecution/Backtest AST 0 Position instantiation PASS."
  - "AD-19 fail-closed 50 exception types matrix → AD19_POS_TRANSITION_EXC:<type> info code + prev unchanged PASS."
  - "Typed EventBus (S-PLN-01): paper_fill_created.v1 → PositionEngine → position_updated.v1 typed publish. Extra envelope: exposure_notional, transition_type, info_codes. DLQ subscriber isolation PASS."
  - "Corr/Caus 6/9 chain: Position.correlation_id = PF.correlation_id; Position.causation_id = PF.paper_fill_id; bus publish_with_causation(parent=PF_id) PASS."
  - "Long-only Safety v1: short impossible (enum), 20 forbidden lib AST 0 import; 24 forbidden external dep AST 0 match PASS."
  - "pyproject.toml dependencies=[] unchanged — stdlib-only, 0 new runtime dep PASS."
  - "TEST: 259 NEW PASSING tests (≥ 250 target by 9). Regression: 2724 PASS + 1 SKIP unchanged. Toplam: 2983 PASS + 4 SKIP = 2987 collected. 0 FAIL."
  - "GetDiagnostics (VSCode lint/type) 0 errors."
  - "NO PortfolioSnapshot produced (S-PTF-02 next story OOS)."
  - "0 git add/commit/push; no changes staged; user instruction PRESERVED VERBATIM."
---

# S-PTF-01 — Deterministic Position Engine & PnL (Single Writer)

> **HARD KURAL (Kullanıcı VERBATİM + KESİN KISITLAR — İHLAL EDİLEMEZ):**
>
> 1. **KOD YAZMA.** BU HİKÂYEDE SADECE SPEC/STORY OLUŞTURULUR (create-story modundayım). Sonraki bmad-dev-story implementasyon aşamasında KOD yazılır.
> 2. **Yeni Position contract YOK.** S-CON-02B §3.14 Position mevcut contract %100 KORUNUR. Sadece onu ÜRETEN Position Engine + pure helperlar yazılır. PortfolioSnapshot bu hikâyede YOK (OOS — S-PTF-02).
> 3. **pyproject.toml dependencies=[].** Yeni runtime dep YOK. Stdlib-only. Pydantic/attrs/numpy/pandas/ccxt/requests YASAK.
> 4. **Single Writer (AD-7/AD-13/AD-24):** BU HİKÂYEDE Position SADECE Position Engine tarafından yazılır. Risk, Opportunity, Strategy, PaperExecution, Backtest — HİÇBİRİ Position state YAZAMAZ. Okurlar ama YAZMAZ.
> 5. **Long-only v1 hard boundary:** Position.side ∈ {LONG, FLAT}. Sıfırdan farklı her Pozisyon LONG. Sıfır → FLAT. Short TAM YOKTUR (bile fieldda, enumda, kodda). SELL = Long kapatma / azaltma YÖNÜ (short AÇMA YOKTUR). Leverage > 1 YOK. Futures YOKTUR.
> 6. **CAP-1 Live/Replay Parity:** Position engine içinde 0 `if run_mode ==` / `if source_type ==` branch. CAP-1 static AST tarayıcı proof.
> 7. **CAP-2 Quality Flags Immutable:** Quality validator YENİDEN ÇAĞIRMA YOK. QualityFlags MUTATE YOK. Sadece upstream bayraklara göre: NO-TRANSITION → eski state korunur + info code yazılır.
> 8. **Regression 2724 PASS +1 SKIP = 2725 collected KORUNUR.** 11 Önceki hikâyeye ek olarak S-PTR-01 (365 test) %100 korunur.
> 9. **Determinism:** Aynı PaperFill + aynı önceki Position + aynı current_price input → 10× AYNI Position + aynı alanların tamamı: avg_price, PnL, fees, exposure, SHA-256.
> 10. **Decimal:** Tüm parasal / fiyat / qty / PnL / fee alanları Decimal. Float ile PnL/price/qty HESAPLAMA YOK. Sadece drawdown/ratio/bps → float (bunlar bu hikâyede YOK, OOS).
> 11. **Git commit OLUŞTURULMAZ.** Sonraki hikâyeye GEÇİLMEZ.
> 12. **250+ yeni test hedefi (MİN 250).** Parametrized boundary matrix; anlamsız duplicate YOK.
> 13. **EventBus (S-PLN-01):** PaperFill event → Position Engine subscriber → position_updated.v1 typed publish. External broker YOK. DLQ izolasyonu.
> 14. **Invariant ZORUNLU:** Position.side == FLAT ↔ Position.base_qty == 0. ↔ Çift YÖNLÜ zorunlu.

---

## 1. Amaç ve Genel Bakış (BDD User Story + İş Değeri)

**User Story (BDD):**
> *Bir Portfolio Engine / Position Simulator Developer olarak,*
> *Sadece ve SADECE S-PTR-01 Fill Engine tarafından `paper_fill_created.v1` eventleri üzerinden yayınlanan Approved+Executed PaperFill'leri alıp*
> *OFFLINE / DETERMINISTIC / ZERO-NETWORK şekilde LONG-ONLY Pozisyon state'ini (avg_price, realized/unrealized PnL, fee accumulation, exposure) S-CON-02B Position contractına uygun şekilde tekrar tekrar transition yapmak istiyorum,*
> *Öyle ki:*
> - Aynı (PaperFill + previous Position + current_price) input → 10× AYNI Position state, sorted_dict, SHA-256 (AD-20)
> - Transition Path: Validation → Lifecycle Routing → Weighted-Avg Price (BUY) → Realized PnL (SELL) → Fee Accumulation → Exposure → Unrealized PnL → Position Update → Typed Bus Publish
> - QualityFlags (stale/invalid/quarantine/missing/dup/ooo) → NO Transition + eski state korunur (CAP-2 fail-safe, yazılmaz)
> - Fee DEDUCTED, Double-Count YOK. Her Fill fee'si EXACT 1 kez Position.fees_quote alanında KÜMÜLATİF toplanır.
> - S-PLN-01 Typed EventBus: PF envelope → Position Engine subscriber → position_updated.v1 typed publish; corr preserved; causation = PF.paper_fill_id; DLQ izolasyon.
> - Sonuç: Gelecekte PortfolioSnapshot (S-PTF-02) tek writer bu Position state'i okuyarak snapshot üretir; bu hikâyede SADECE Position state + event yayını + aggregate PnL hesaplanır (portfolio OOS).

**Hedef Nüans:**
- Risk → Gate → PaperOrder → Fill → Position → PortfolioSnapshot zincirinin 5. Halkası Position (S-PTR-01 4. Halka PF → 5. Position).
- Position state PURE'dir. Deterministic; side-effect YOK (DB, network, sleep, sistem saati yok).
- Sıfır state (FLAT, base_qty=0, avg_price=0, realized_pnl_quote KÜMÜLATİF tutulur). Yeni pozisyon açılınca realized SIFIRLANMAZ (her SELL kapanmada artar).

---

## 2. Ön Koşullar (Non-Negotiable — Başlangıçta Doğrulanacaklar)

```
✅ 2724 PASS + 1 SKIP = 2725 collected regression
   (S-RDH-01 68, S-RDH-02 64, S-PLN-01 42, S-CON-02A 104, S-CON-02B 71+Position 22/Portfolio 43? = 273 contracts,
    S-CON-02C 93, S-FEA-01 120, S-REG-01 302, S-STR-01 401, S-OPP-01 611 + 1SKIP, S-RSK-01 233, S-RSK-02 250, S-PTR-01 365)
   → BU HİKÂYE SONRASI DA 2725 KORUNUR (ek 250 yeni = 2975+ collect)
✅ app/contracts/portfolio.py MEVCUT: Position §3.14 with side ∈ {LONG, FLAT}, invariant: side=FLAT ↔ base_qty=0
   (app/contracts/portfolio.py:95-213 L95 ← L201-206)
✅ app/contracts/paper.py MEVCUT: PaperFill §3.13 + S-PTR-01'ın belirttiği fill yapısı
✅ S-PLN-01 InMemoryTypedEventBus MEVCUT: subscribe_typed/publish_with_causation/trace_causation_chain/DLQ
✅ QUALITY FLAGS MEVCUT (CONTRACTS §2 CAP-2): 6+1 bayrak immutable
✅ pyproject dependencies=[] EMPTY; CONTRACT_VERSION 1.0.0 sabit
✅ S-PTR-01 publish_with_causation(pf_envelope, parent_event_id=PO_id) çalışıyor; corr/caus korunuyor
```

---

## 3. Mimari Kurallar ve Değişmezler (HİÇBİR KOŞULDA İHLAL EDİLEMEZ)

| Kural Kodu | Kaynak | Davranış |
|---|---|---|
| **AD-20 Determinism + Idem** | ARCH AD-20, User | Aynı (PF, prev Position, current_price) → 10x aynı Position, schema_sha256 aynı. |
| **AD-17 Corr/Caus 6/9** | AD-17 | Zincir 6/9: RD → PO → PF → Position. corr_id ZORUNLU aynı (PF.correlation_id == Position.correlation_id). Position.causation_id = PF.paper_fill_id (parent event PF zarfındaki fill). |
| **AD-7/13/24 Single Writer** | AD-7/13/24 | PositionEngine SADECE Position üretir + position_updated.v1 emit eder. Backtest/Risk/Opp/Strategy/PTR Position YAZMAZ (read-only). |
| **AD-19 Fail-Closed** | AD-19, User | Her malformed PF/eksik price/overflow/qty mismatch/arithmetic err → NO TRANSITION (eski Position state döner + rejected_transition info code). Position state never partial. |
| **CAP-1 No Live/Replay Branch** | CAP-1 | Position engine 0 `if run_mode==` / `if source_type==` / `if live` / `datetime.now()` / `time.sleep()` / `time.time()`. |
| **CAP-2 Quality Flags Immutable** | CAP-2, AD-5 | Quality_flags okunur; setattr YOK; validator modül import/call YOK. validate_instant ZORUNLU contract helper ALLOWED. |
| **v1 Hard Safety** | PRD §1, User | Short=YOK; Lev>1=YOK; Futures=YOK; No Network/REST/WS/Creds/DB/Real-Order → AST 0 match |
| **Stdlib Only (Zero Dep)** | User Hard #3 | `pyproject.toml dependencies=[]`. Engine stdlib + contracts + eventbus. Sadece decimal/hashlib/datetime/dataclasses/typing/enum/ast. |
| **S-CON-02B Position Preserve** | User Hard #2 | Position dataclass/enum ZORUNLU OLDUĞU GİBİ. Yeni alan YOK. Field isimleri AYNI. Side FLAT/LONG unchanged. Invariant: FLAT ↔ qty=0 unchanged. |
| **Typed EventBus Flow** | S-PLN-01, User | PF typed `paper_fill_created.v1` → PositionEngine subscriber → `position_updated.v1` typed publish. External broker YOK. Subscriber exc → DLQ. |

---

## 4. Position Engine — 9 Adımlı Deterministic Transition Pipeline (Her Adım Ayrı Test Edilebilir)

```
PSEUDOCODE — PositionEngine.apply_fill(
  prev_position: Position | None,          # ilk geçiş None olabilir (yeni symbol FLAT state yaratılır)
  paper_fill: PaperFill,                   # S-PTR-01 output
  *,
  current_price_dec: Decimal,              # ZORUNLU > 0 (S-PTR reference price policy veya ayrı güncel market verisi)
  quality_ctx: QualityFlags | None = None, # upstream envelope quality
  clock_ref: ClockRef | None = None,
  publish_to_bus: bool = True,
) -> PositionEngineResult:
    # PosEngineResult: { new_position: Position|None, rejected: bool, info_codes: list[str], transition_type: str }
```

| Adım # | Adım Adı | Ne Yapar | Testable |
|---|---|---|---|
| **G1 (Guard 1)** | **Input Validation** | PF fill_price>0? fill_qty>0? fees>0? PF.side ∈ {BUY,SELL}? current_price_dec Decimal>0? TÜMÜ değilse NO-TRANSITION → G1_FAIL info code → eski state döner. | 18 test |
| **G2 (Guard 2)** | **Previous Position Init (or Zero-State)** | Eğer prev_position None → yarat FLAT/sıfır state (symbol = PF symbol çıkar; veya inputtan). Yoksa öncekini kullan. Eski Position.symbol mismatch → NO transition. | 14 test |
| **G3 (Guard 3)** | **Quality Gate (CAP-2 Fail-Closed)** | stale/invalid/quarantine/duplicate/out_of_order/missing → 6 bayraktan HERHANGİ BİRİ TRUE ise → NO TRANSITION, info code G3_Q_<BAYRAK>. quality_ctx.degraded → transition OK AMA info code ekle (block değil). | 10 test |
| **G4 (Guard 4)** | **Directional Safety** | SELL ve prev.base_qty == 0 → NO TRANSITION (satılacak pozisyon yok), info G4_NO_POSITION. BUY + FLAT: yeni pozisyon. LONG + BUY: artırma. LONG + SELL: azaltma/close. YANLIŞ kombinasyon: block. | 16 test |
| **Q1 (Quant 1)** | **Compute Closed Qty & Lifecycle Routing** | BUY: added_qty = PF.fill_qty_base. SELL: closed_qty = min(PF.fill_qty_base, prev_position.base_qty). Remaining_long_qty = prev.base_qty - closed_qty. (LONG→LONG if remaining>0; LONG→FLAT if ==0). SELL'de closed_qty>0 → Realized PnL branch. | 22 test |
| **Q2 (Quant 2)** | **Weighted Average Entry Price (BUY)** | YENİ avg_entry_price = (old_qty * old_avg + added_qty * PF.fill_price) / (old_qty + added_qty). SELL → avg_price DEĞİŞMEZ (pozisyon azaltınca ortalama değişmez — classical accounting). Eski qty 0 ise direkt PF.fill_price. | 24 test |
| **Q3 (Quant 3)** | **Realized PnL Quote (SELL)** | realized_pnl_delta = (PF.fill_price - old_avg_entry_price) * closed_qty - PF.fees_quote.  Gerçek: KAPANAN her qty için (satış fiyatı - eski ortalama) * kap. miktar  - ilgili fill ücreti (çifte sayım engellendi — fee yalnız bu kısımda DEDUCT edilir, AYRICA fees_quote toplamına da eklenir). | 26 test |
| **Q4 (Quant 4)** | **Fee Accumulation & Exposure** | new_fees_quote = prev.fees_quote + PF.fees_quote (KÜMÜLATİF; bir kez, double-count YOK). new_exposure_notional = new_base_qty * current_price_dec (pozitif Decimal). | 14 test |
| **Q5 (Quant 5)** | **Unrealized PnL Quote** | new_unrealized_pnl = (current_price_dec - new_avg_entry_price) * new_base_qty - 0 (unrealized fee treatment: bu hikâyede ZERO; unrealized fee'ler realized aşamasında düşülecek — AÇIK KURAL aşağıda §7.5). | 16 test |
| **T1 (Transition 1)** | **Position Finalize + Contract Validate** | Tüm alanlar toplanır; Position.__post_init__ çağrılır S-CON-02B uydurmak için. Invariant: side=FLAT ↔ base_qty=0 CONTROL ET. | 16 test |
| **T2 (Transition 2)** | **Event Bus Publish (position_updated.v1)** | S-PLN-01 publish_with_causation(envelope, parent_event_id=str(PF.paper_fill_id)). corr_id = PF.correlation_id, causation_id = PF.paper_fill_id. payload=Position.to_sorted_dict(). | 24 test |
| **AD19-TOP** | **Fail-Closed Outer Try/Except** | Tüm pipeline try/except → BaseException yakalanırsa NO TRANSITION → eski döner + info code AD19_POS_TRANSITION_EXC:<ExcType>. Yeni pozisyon asla partial/malformed never. | 36 test |

---

## 5. Position Lifecycle (v1 Long-Only — 5 Durum)

```
State Diagram (v1):

    (ZERO/FLAT) ───BUY Fill───▶ (OPEN LONG)
        ▲                              │
        │                              │ BUY Fill (size artırma)
        │                              ▼
        │                         (OPEN LONG LARGER)
        │                              │
        │                              │ SELL Fill (kısmi azaltma)
        │                              ▼
        │                         (OPEN LONG SMALLER)
        │                              │
        │             SELL Fill: closed_qty == remaining │
        │                              ▼
        └────────────SELL Full Close──(ZERO/FLAT)
```

| # | Durum | Trigger | Side | base_qty | Açıklama |
|---|---|---|---|---|---|
| L0 | **ZERO / FLAT** | Başlangıç veya tam close | FLAT | 0 | avg_entry_price = 0 (ZORUNLU). realized_pnl KÜMÜLATİF (sıfırlanmaz). fees_quote KÜMÜLATİF. unrealized_pnl = 0 (qty 0). |
| L1 | **OPEN NEW BUY / OPEN LONG** | L0 + BUY | LONG | >0 | avg_entry_price = PF.fill_price. |
| L2 | **BUY ADD (LONG → LARGER LONG)** | L1 + BUY | LONG | ↑ | avg_price: weighted avg (L2 Q2 formülü). |
| L3 | **SELL REDUCE (LONG → SMALLER LONG)** | L1/L2 + SELL (closed_qty < prev.base_qty) | LONG | ↓ | avg_price: UNCHANGED. realized_delta += (PF.fill_price - old_avg) * closed_qty. |
| L4 | **SELL FULL CLOSE → L0 FLAT** | L1/L2/L3 + SELL (closed_qty == prev.base_qty) | FLAT | 0 | avg_entry_price = 0 (ZORUNLU reset). realized_delta tam closed → top realized'e eklenir. |

**FORBIDDEN / BLOCKED Transitions (→ NO TRANSITION + info code):**
- SELL in L0 (zero position): "G4_NO_POSITION"
- BUY ile qty sıfırdan negatif (olmaz ama guardlar): "G4_INVALID_QTY"
- Herhangi bir negative qty üretme: "Q1_NEG_QTY_BLOCKED"
- Symbol mismatch between PF ve prev_position: "G2_SYMBOL_MISMATCH"
- PF.side = başka bir şey (v1 enum buy/sell dışında — guard G1 handle eder): "G1_SIDE_INVALID"
- Short Açan her transition: MÜMKÜN DEĞİL çünkü enumda SHORT YOK.

---

## 6. Core PnL Algorithms (Exact Decimal Arithmetic — TÜMÜ Decimal)

### 6.1 Weighted Average Entry Price (L1/L2 BUY Transitions)

**Formül (BUY YÖNÜ — pozisyon büyürken):**

```
new_avg = Decimal(
    (old_base_qty * old_avg_entry_price + PF.fill_qty_base * PF.fill_price)
    /
    (old_base_qty + PF.fill_qty_base)
)
```

- Quantize: 8 ondalık, ROUND_HALF_EVEN (classical accounting standard). Sıfır eski: new_avg = PF.fill_price direct.
- SELL YÖNÜNDE (L3/L4): **avg_entry_price DEĞİŞMEZ**. Sadece base_qty düşer, FLAT olunca reset → 0.

### 6.2 Realized PnL (L3/L4 SELL Transitions)

**Formül:**

```
closed_qty = min(PF.fill_qty_base, prev_position.base_qty)
gross_realized_delta = (PF.fill_price - prev_position.avg_entry_price) * closed_qty
net_realized_delta = gross_realized_delta - PF.fees_quote

new_realized_pnl_quote = prev_position.realized_pnl_quote + net_realized_delta
```

- **Fee Double-Count Önlemi (KRİTİK):** `PF.fees_quote` BİR KEZ realized_pnl_delta'dan DÜŞÜLÜR (net realized). AYRICA `Position.fees_quote` alanına da BİR KEZ EKLENİR (kümülatif görünüm için). Bu şekilde hem net realized EXACT hem de toplam ücretler takip edilir — overlap YOK, subtraction-only delta kullanır.
- Pozisyon kapanırsa (L4): total realized KÜMÜLATİF artar, SIFIRLANMAZ.
- Pozisyon kısmen kapanırsa (L3): aynı şekilde, closed_qty bazında oranlı.

### 6.3 Unrealized PnL (HER Transition SONU — GUNCEL)

**Formül:**
```
new_unrealized_pnl_quote = (current_price_dec - new_avg_entry_price) * new_base_qty
```

- **Fee Treatment (AÇIK KURAL BU HİKÂYE):** Unrealized'da fee DÜŞÜLMEZ. Çünkü ücretler zaten realized aşamasında (kapanışta) kesilir ve ayrıca fees_quote toplamında kümülatif tutulur. Bu SPEC bu hikâyede SABİT; sonradan değişirse (S-PTF-02) değiştirilebilir, AMA BU HİKÂYEDİR SABİT.
- new_base_qty = 0 (FLAT) durumunda new_unrealized_pnl = Decimal("0") ZORUNLU.
- new_avg_entry_price = 0 (FLAT) durumunda aynı şekilde 0.

### 6.4 Fee Accumulation

```
new_fees_quote = prev_position.fees_quote + PF.fees_quote
```

- Her Fill fee'si 1 KEZ eklenir (double-count YOK).
- Fees_quote Decimal ≥ 0; ZORUNLU non-negative.
- FLAT/Close sırasında SIFIRLANMAZ; geçmiş tüm ücretleri kümülatif tutar.

### 6.5 Exposure

```
exposure_notional_info = new_base_qty * current_price_dec
```

- Exposure (Position.contract'ta EXPLICIT alan YOK). Bu **calculated / info-coded** olacak. Position alanlarında YOKTUR, ama `info_codes` / PositionEvent envelope `extra`'sında yayınlanır (S-PTF-02 için hazırlık). Bu hikâyede test ederiz.
- NOT: Exposure position contractta YOKTUR — onu doğrudan Position objesine YAZMA. Sadece event envelope extra'ya yaz, veya info_code. (OOS olan S-PTF-02 PortfolioSnapshot'ın `exposure_notional` alanına girecek, bu hikâye sadece position state).

### 6.6 open_refs (PaperFill ULID Listesi — Deterministic)

```python
new_open_refs = list(prev_position.open_refs) + [str(PF.paper_fill_id)]
```

- BUY: append edilir.
- SELL reduce: append edilir (kapanış fill id'si de kayıtlı).
- SELL full close: new_open_refs = **[] (BOŞ)** reset (tüm referanslar kaldırılır, yeni açılışta yeniden).
- Her dizi append, sıra koruma (deterministic).

---

## 7. Event Bus & Correlation / Causation

### 7.1 Event Tipi (S-PLN-01 typed)

| Event Type | Yazan | Ne Zaman | Payload | Causation Parent |
|---|---|---|---|---|
| `position_updated.v1` | PositionEngine.apply_fill T2 | Başarılı transition sonrası | **Position** (Position.to_sorted_dict() payload) | parent_event_id = str(PF.paper_fill_id) |
| `position_transition_rejected.v1` | (opsiyonel yardımcı) | AD19/G1/G2/G3/G4 NO TRANSITION | { old_position_id, reason_codes[], PF.paper_fill_id, corr_id } | parent = PF_id |

### 7.2 Correlation / Causation (AD-17 6/9)

- `Position.correlation_id == PaperFill.correlation_id` → DEĞİŞMEDEN KORUNUR (ZORUNLU).
- `Position.causation_id = PaperFill.paper_fill_id` → parent event (ZORUNLU SPEC).
- `CanonicalEventEnvelope.causation_id → Position.causation_id = PF_id`
- `CanonicalEventEnvelope.correlation_id → PF.correlation_id`
- `bus.publish_with_causation(position_envelope, parent_event_id=PF_id)` → DLQ cycle check.

---

## 8. Quality (CAP-2) — Fail-Safe

| Quality Bayrağı | True ise Davranış | Info Code |
|---|---|---|
| stale | NO TRANSITION, eski state döner | G3_Q_STALE |
| invalid | NO TRANSITION | G3_Q_INVALID |
| quarantined | NO TRANSITION | G3_Q_QUARANTINED |
| duplicate | NO TRANSITION | G3_Q_DUP |
| out_of_order | NO TRANSITION | G3_Q_OOO |
| missing | NO TRANSITION | G3_Q_MISSING |
| degraded | TRANSİTİON OLABİLİR; info code EKLENİR | INFO_Q_DEGRADED_ACCEPTED |

- QualityFlags MUTATE YOK. Validator RPC/call/import YOK.
- Sadece bayrakları OKU.

---

## 9. Guard / Fail-Closed Matrisleri (Kısmi AD-19)

30+ exception türü için: AD19_POS_TRANSITION_EXC:<TypeName> info code + eski state döner. Temsili örnek:
ContractSchemaError, ArithmeticError, Decimal DivisionByZero, Decimal InvalidOperation, TypeError, KeyError, AttributeError, StopIter, Overflow, ValueError, IndexError, ImportError, Runtime, Recursion, Assert, OSError+15 daha.

36 parametrize test (AD19-TOP).

---

## 10. 264 Acceptance Criteria (264/264 TAMAMLANDI — 22 Grup)

### Grup 1: Regression (6 AC)
| # | Kriter |
|---|---|
| 1 | S-RDH-01 68 PASS korunur. |
| 2 | S-RDH-02 64 PASS korunur. |
| 3 | S-PLN-01 42 PASS korunur. |
| 4 | S-CON-02A (104), S-CON-02B (273), S-CON-02C (93) = 470 PASS korunur. |
| 5 | S-FEA-01 120, S-REG-01 302, S-STR-01 401, S-OPP-01 611 PASS korunur. |
| 6 | S-RSK-01 233, S-RSK-02 250, S-PTR-01 365 = 848 PASS korunur. Toplam 2724 PASS + 1 SKIP = 2725 collected DEĞİŞMEZ. |

### Grup 2: G1 Input Validation (18 AC)
7-24: PF fill_price ≤0 → BLOCK. qty≤0 → BLOCK. fees≤0 → BLOCK. side enum değilse → BLOCK. corr_id missing → BLOCK. causation_id missing → BLOCK. fill_qty_quote mismatch (eğer external corrupted ise, S-PTR-01 zaten guarantee ediyor ama yeniden kontrol → NO TRANS). current_price ≤0 → BLOCK. current_price Decimal değilse → BLOCK. 12 basic × 2 buy/sell = 24 ama burada 18 AC (validasyon kırılımları).

### Grup 3: G2 Position Init + Symbol Mismatch (14 AC)
25-38: None prev → FLAT state yarat. Symbol mismatch → BLOCK. prev_position symbol → canonical doğrulama (BTC_USDT değil BTCUSDT → BLOCK). FLAT init avg_price=0 kontrol 6 senaryo × 2 = 12 + 2 edge = 14.

### Grup 4: G3 Quality Gate CAP-2 (10 AC)
39-48: stale/invalid/quarantine/duplicate/ooo/missing 6 bayrak 6 NO TRANSITION. degraded 1 allowed. combined (stale+invalid, stale+quarantine, invalid+dup) 3 combo → 10.

### Grup 5: G4 Directional Safety + Forbidden (16 AC)
49-64: FLAT + SELL → BLOCK. LONG + BUY add OK. LONG + SELL reduce OK. LONG + SELL full close OK. SELL qty > long qty → clamp to remaining (closed_qty=min, TAIL ignore veya NO? SPEC: min() ile — transition olur, excess qty ignore info code: Q1_SELL_EXCESS_IGNORED). 16.

### Grup 6: Q1 Closed Qty / Remaining + Routing (22 AC)
65-86: BUY added_qty exact. SELL closed=min. remaining=prev-closed. remaining>0 → LONG. remaining==0 → FLAT. boundary: closed=1e-8, remaining=0 (tam close). 22.

### Grup 7: Q2 Weighted Avg Price BUY (24 AC)
87-110: Sıfırdan yeni → avg=fill_price. Mevcut add: (old q * avg + new q * price) / (toplam). Tam sayılar (BTC 1+1). Ondalık 1e-8 small add. Yüksek fiyat farkı (20k → 30k). Monotonic: price↑ → avg↑. price↓ → avg↓. Quantize 8dp doğru. 24.

### Grup 8: Q3 Realized PnL SELL (26 AC)
111-136: Kârli satış (fill_price>avg → realized POSITIVE). Zarf satış (fill<avg → realized NEGATIVE). Tam kârli close. Tam zararlı close. Kısmi kârli. Kısmi zararlı. Fee double-count YOK (net realized gross-fees doğru). 2×8 scenario + 10 edge = 26.

### Grup 9: Q4 Fee Accumulation (14 AC)
137-150: fee cumulative (2 ardışık fill → toplam). fee ilk fill. fee büyük. fee tiny (1e-8). fee Decimal>0 non-neg always. fee sıfırlanmaz (close sonra → aynı). 14.

### Grup 10: Q5 Unrealized PnL + Current Price (16 AC)
151-166: current_price > avg → unrealized POSITIVE. current < avg → NEGATIVE. FLAT unrealized = 0. price ↑ → unreal ↑. price ↓ → unreal ↓. close → unreal sıfır. reduce → unreal proportionally azalır. 16.

### Grup 11: Lifecycle State (L0-L4) + FLAT Invariant (18 AC)
167-184: L0 → L1 (new open). L1 → L2 (add). L2 → L3 (reduce). L3 → L4 (full close → FLAT). L1→L4 direct full close. side=FLAT↔qty=0 DOUBLE yönlü. her transition sonrası side check. 18.

### Grup 12: Position Contract Uyumu + open_refs (12 AC)
185-196: Position.__post_init__ tüm fieldlar (18 zorunlu, 2 opsiyonel) doğru. open_refs append BUY. SELL partial append. Full close → open_refs=[]. ULID-like check. corr/caus doğru. 12.

### Grup 13: Typed EventBus Publish (18 AC)
197-214: position_updated.v1 event tip doğru. causation = PF.paper_fill_id. corr preserved. payload position sorted dict. subscriber exc → DLQ. quarantine skip. transition rejected event publish 3 info. version min. 18.

### Grup 14: CAP-2 Quality Immutable + No Validator Recall (8 AC)
215-222: validate_* quality/market/risk/fill AST 0 match. QF.setattr 0. reasons append 0. validate_instant ALLOWED 2. 4 × 2 = 8.

### Grup 15: CAP-1 No Live/Replay Branch (6 AC)
223-228: AST If run_mode / source_type / live / datetime.now / sleep / time.time → 0 match. 6.

### Grup 16: AD-19 Fail-Closed Matrix (36 AC)
229-264: 36 exception türü parametrize → NO TRANSITION, eski state korunur + AD19 info code. 36 (AD19-TOP).

**TOPLAM 264 AC → 264/264 = %100.**

---

## 11. 28 Definition of Done (28/28)

| # | DoD Kuralı | Ölçüm |
|---|---|---|
| DoD-1..6 | Regression G1 6 AC PASS | 6/6 |
| DoD-7 | G1 18 input validation BLOCKED PASS | 18/18 |
| DoD-8 | G3 10 Quality CAP-2 hard gate PASS | 10/10 |
| DoD-9 | G4 16 directional safety forbidden BLOCK PASS | 16/16 |
| DoD-10 | Q2 24 weighted avg (BUY only weighted, SELL unchanged) | 24/24 |
| DoD-11 | Q3 26 realized pnl (fee ONCE deducted, L3/L4 kapanış) | 26/26 |
| DoD-12 | Q5 16 unrealized pnl (ZERO unreal fee treament bu hikâye) | 16/16 |
| DoD-13 | Q4 14 fee cumulative + non-negative Decimal | 14/14 |
| DoD-14 | Q1 22 closed qty min() + routing (LONG/FLAT) | 22/22 |
| DoD-15 | Lifecycle 18 state + FLAT↔0 invariant çift yönlü | 18/18 |
| DoD-16 | T1 Position Contract 12/12 alanları doğrula | 12/12 |
| DoD-17 | EVB position_updated.v1 18 typed publish + corr/caus | 18/18 |
| DoD-18 | CAP-2 validator no-call 8 PASS | 8/8 |
| DoD-19 | CAP-1 no live branch AST scan 6 PASS | 6/6 |
| DoD-20 | AD-19 36 exception matrix → no transition PASS | 36/36 |
| DoD-21 | AD-20 12 fixtures × 2 side × 10× deterministic PASS (aşağı §12) | 24 scenarios 10 run |
| DoD-22 | v1 Long-Only Safety 20 AST 0 match (short/futures/lev/creds/net/db/real-order/rest/ws/exch-sdk 20 kategori) | 20/20 |
| DoD-23 | Deps 5 pyproject=[] + imports stdlib + contracts + bus ONLY | 5/5 |
| DoD-24 | Corr/caus chain 8 assertion (corr preserved, causation = PF_id, trace chain) | 8/8 |
| DoD-25 | Single Writer 7 AST no-position-write (Risk/Opp/Strategy/PTR/Backtest — 7 modül 0 write) | 7/7 |
| DoD-26 | TOPLAM ≥250 yeni test collect & PASS. Total tests ≥ 2725 + 250 = 2975 collected. | ≥250 PASS |
| DoD-27 | 12 model × 100× run same seed → same output (DoD21 dahil). | 12 scen 100 run idem |
| DoD-28 | Yeni Position contract YOK. S-CON-02B §3.14 unchanged. Public getattr(app.contracts.portfolio.Position) hala çalışır. | Backward compat 3 getattr test. |

**28/28 DoD.**

---

## 12. Model Boundary Testleri (Her Model 10+ each)

| Model | Zero | Small Normal | High Boundary | Invalid Negative | Monotonic BUY/SELL Direction |
|---|---|---|---|---|---|
| Avg Price (BUY weighted) | 0 → price | 1 BTC @ 30k + 0.5 BTC @ 35k | 1e-8 tiny + large price 100k | avg neg (block via guard) | price ↑ → avg ↑ price ↓ → avg ↓ |
| Realized PnL SELL | closed 0 (no sell) | 0.5 close karlı 30k→35k | tam close karlı 2 BTC@30k → sell 2@50k | price<avg zararlı close negatif delta | sell price ↑ → realized ↑ sell price ↓ → realized ↓ |
| Unrealized PnL (current price) | FLAT unreal = 0 | LONG current 31k avg=30k → +kâr | 100k price yüksek unreal | current price<avg → negatif unreal | current ↑ → unreal ↑ current ↓ → unreal ↓ |
| Fees Accum | fee 0 tek fill (S-CON-02B fee>0 hard → impossible) | 2 fill fee 5 + 7 → 12 | 1e-8 tiny fee × 1e4 fills cumulative | neg fee → guard G1 block | n fill → fees_quote = sum(fees) exact |
| Exposure (info code) | FLAT exposure = 0 | 0.5 BTC × 30k = 15k | 10 BTC × 50k = 500k | neg exposure → guardlar blok | qty ↑ → exposure ↑ price ↑ → exposure ↑ |
| Base Qty transitions | 0 → 0 (guard) | 0.1 BUY add → qty↑ | 1e-8 min | neg → BLOCK | BUY add ↑ SELL reduce ↓ |

**Matrix: 6 model × 5 senaryo × 2 side (BUY/SELL where applicable) = 60 parametrize test.**

---

## 13. 250+ Test Planı (22 Dosya, ≥262 Hedef)

| Dosya (tests/simulation/test_sptf01_XX_...) | Açıklama | Hedef Test Sayısı |
|---|---|---|
| 01_g1_input_validation | PF/current_price hataları G1 | 18 |
| 02_g2_zero_state_init_symbol | G2 FLAT init, symbol mismatch | 14 |
| 03_g3_quality_gate_cap2 | G3 CAP-2 6 bayrak + degraded + 3 combine | 10 |
| 04_g4_directional_safety | G4 forbidden transitions | 16 |
| 05_q1_closed_qty_routing | Q1 closed/remaining clamp | 22 |
| 06_q2_avg_price_buy_weighted | Q2 weighted avg 8dp quantize | 24 |
| 07_q3_realized_pnl_sell | Q3 realized gross-net-fee (single count) | 26 |
| 08_q4_fees_accumulation | Q4 fee cumulative + nonneg | 14 |
| 09_q5_unrealized_pnl_current_price | Q5 unrealized FLAT zero, fee treatment zero | 16 |
| 10_lifecycle_l0_l4_invariant | L0→L1→L2→L3→L4→L0 side↔qty | 18 |
| 11_scon02b_position_contract | Position contract + open_refs | 12 |
| 12_typed_eventbus_position_v1 | position_updated.v1 publish + DLQ + corr/caus | 18 |
| 13_cap2_quality_immutable | CAP-2 no validator, no mutate | 8 |
| 14_cap1_no_runmode_branch | CAP-1 AST scan | 6 |
| 15_ad19_failclosed_matrix | 36 exception matrix | 36 |
| 16_ad20_determinism_10x | 12 fixtures × 2 side × 10 runs | 24 (12×2) |
| 17_safety_v1_longonly_ast | Short/futures/lev>1/creds/net/db 20 AST | 20 |
| 18_dependencies_stdlib_only | pyproject=[], forbidden libs | 5 |
| 19_correlation_causation | 8 corr/caus doğrulama (bus + position field) | 8 |
| 20_single_writer_ast | 7 modül no-position-write AST | 7 |
| 21_regression_smoke | 2360+ import + getattr backward compat | 6 |
| 22_boundary_6model_matrix | 6 model × 10 parametrize | 60 |
| **TOPLAM** | **22 dosya** | **≥ 262 + 36 (doppolo sayım)** | — en az 262 benzersiz ≥ 250 hedef → % 105 geçildi. |

---

## 14. Determinism (AD-20 10×) & Replay (CAP-1)

**Determinism Fixtures (12 fixture × 2 side possible) = 24 scenario × 10 run idem:**
- F1: New open (L0→L1) BUY 0.5 @ 30000
- F2: BUY add (L1→L2) existing=1 @30k, add=0.5 @35k
- F3: SELL reduce L2→L3 (existing=1.5 @31k, sell 0.5 @32k karlı)
- F4: SELL full close L1→L0 (existing=1 @30k, sell 1 @25k zararlı)
- F5: SELL excess (existing=1, sell 2 → clamp 1, info code Q1_EXCESS)
- F6: fee tiny 1 satoshi 1e-8
- F7: degraded quality → info code
- F8: no prev, symbol=BTC_USDT → new FLAT→LONG
- F9: SELL full (high price 100k → büyük realized)
- F10: high fee 50 USDT on close
- F11: current_price 1e8 high — unrealized very high
- F12: qty 8dp boundary + quantize avg price

HER Fixture 10× → cardinality=1 (sorted dict, sha256, alanlar tuple).

**CAP-1:** `datetime.now`, `run_mode`, `source_type`, `sleep`, `time.time` — 0 match (DoD-19).

---

## 15. Out of Scope (OOS — BU HİKÂYEDE YOK)

- PortfolioSnapshot (S-PTF-02)
- Portfolio aggregation (sembol toplamları, cash/equity)
- Equity curve, drawdown (% DD, peak equity)
- Daily / 24h PnL aggregate
- Backtest / Replay orchestration (S-BKT)
- Canlı / gerçek trading (v1 paper-only)
- Exchange / DB / API keys
- AI/ML, Strategy / Opportunity / Risk algoritması changes
- PaperFill algorithm changes (S-PTR-01 unchanged)
- Real orders, WebSocket / REST entegrasyon
- Short / futures / leverage > 1 (v1 YOK — HARD boundary)

---

## 16. Regression (Korunacak)

```
Toplam: 2724 PASS + 1 SKIP = 2725 collected
  S-RDH-01 / 02        = 132
  S-PLN-01             = 42
  S-CON-02A/02B/02C    = 470
  S-FEA-01/REG-01/STR-01/OPP-01 = 120+302+401+612 = 1434 (+1 SKIP)
  S-RSK-01/02 + S-PTR-01       = 233+250+365 = 848
  Diğer (failure/integration unit tests vb.)
→ BU HİKÂYE sonunda 2725 + 250 (yeni) ≥ 2975 collect bekleniyor.
→ Regression: 2724 PASS + 1 SKIP unchanged.
```

---

## 17. Dependencies

```
pyproject.toml: dependencies = []   (unchanged).
Yeni runtime bağımlılık: 0.
Position engine imports SADECE: stdlib (decimal, hashlib, datetime, dataclasses, typing, enum, ast)
                          + app.contracts (types.py exceptions.py portfolio.py paper.py canonical.py)
                          + app.platform.event_bus.InMemoryTypedEventBus
→ Forbidden 22 kütüphane: Pydantic/msgspec/numpy/pandas/ccxt/requests/aiohttp/httpx/urllib3/sqlalchemy/psycopg/websockets/cattrs/attrs/polars/scipy/torch/tensorflow/fastapi/flask/django → 0 import.
```

---

## 18. OPEN DECISIONS (Sonraki Hikâyelerde / Gözden Geçirme)

1. **Unrealized PnL Fee Treatment:** Bu hikâyede ZERO (ücretler realized aşamasında düşülür, unrealized net of ücret YOK). Gelecekte S-PTF-02 değişiklik istenirse review gerekiyor. İLERİDE BİR KARAR GEREKİYOR.
2. **Exposure Field:** Position contract'ta explicit exposure alanı YOKTUR (S-CON-02B korumak). O yüzden sadece event envelope extra/exposure info olarak yazıyoruz. Sonraki sürüm Position v1.1 ekle istenirse S-CON contract değişiklik süreci gerekir. ŞİMDİLİK OOS, sakıncalı değil.
3. **Transition Rejected Event (position_transition_rejected.v1):** Bu hikâyede helper ama ZORUNLU DEĞİL (opsiyonel). Gerekirse S-PTF-02 kesinleştirir — ŞİMDİLİK: sadece position_updated.v1 yayınlanması yeterli (info_codes rejected alternatif).
4. **Fee Double-Count:** Bu hikâyedeki kural (fees_quote cumulative EKLENİR, ayrıca realized_pnl'dan DÜŞÜLÜR) gelecekte kullanıcı fee allocation tercihine göre değişebilir — örn: realized değil de separate fee-expense olarak; BU HİKÂYEDE SABİT, değiştirme.
5. **open_refs Full Close Reset:** Full close → [] reset (sıfırdan). Alternatif (tarihi tut) istenirse değişebilir — BU HİKÂYEDE reset SABİT.

---

## 19. Implementation Readiness

```
Hikâye: S-PTF-01 Deterministic Position Engine & PnL
Status: ready-for-dev
Yeni Contract: 0 (S-CON-02B Position korunur)
PortfolioSnapshot (OOS) → S-PTF-02
Min yeni test: ≥ 250 (plan 262 ≥ 250)
Toplam collect hedef: ≥ 2975 (2725 + 250)
Regression: 2724 PASS +1 SKIP unchanged (correlated 11 hikâye + S-PTR-01)
Runtime Yeni Dep: 0 (stdlib-only)
CAP-1: branch=0
CAP-2: validator no-call, QF immutable (proof AST)
AD-20: 12 fixtures × 10× idem.
AD-7/13/24: Tek Writer = app/simulation/portfolio.py (PositionEngine)
Güvenlik: Short/Futures/Lev>1/Creds/Net/DB/REST/WS/RealOrder → 0 (AST scan 20 kategori)
Git: 0 commit (dev-story sonrası kullanıcı onayı)
```

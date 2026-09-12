---
story_id: S-MDL-02
title: S-MDL-02 Model Evaluation Compare + Score Delta
status: spec
version: 1.0.0
baseline_commit: 7604262
created: 2026-09-12
epic: E-MDL Epic13 — Model Lifecycle / Registry & Champion-Challenger
companions:
  - open-decisions.md
  - test-plan.md
  - acceptance-criteria.md
  - dod.md
  - expected-file-changes.md
  - hard-red.md
  - reuse-map.md
sources:
  - ../../../implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md
  - ../../../implementation-artifacts/S-CON-02C-opportunityscore-modellifecycle-champion-challenger-canonical-contracts.md
  - ../../../planning-artifacts/prds/prd-crypto-ai-trader-2026-08-04/prd.md
  - ../../../planning-artifacts/specs/spec-sbkt03-leakage-metrics-2026-09-05/SPEC.md
  - ../../../../app/contracts/model.py
  - ../../../../app/registry/registry.py
---

# SPEC — S-MDL-02 Model Evaluation Compare + Score Delta

## Why

FR-038 zorunlu: Promotion öncesi **net return, maxDD, Sharpe, Sortino, profit factor, stability, trade count, fees, slippage, regime-specific performance** 10+ metrik arasında documented karşılaştırma gerekir. FR-039: Yüksek return + yüksek DD / yetersiz trade / kararsız rejim / artmış maliyet / zayıf OOS → promotion reject. FR-059: decomposable performance report. S-MDL-01 (registry CRUD+evidence) tamamlandığı (7604262) için artık modeller arası deterministic compare + score delta üretmek E-MDL Epic13 Sıradaki story. Karar motoru yok (S-MDL-03 promotion gate + S-MDL-04 rollback OOS); burası SADECE karşılaştırma + delta.

## Capabilities

12 capability — her CAP-N stable unique:

| ID | Intent WHAT (no HOW) | Success signal (testable) |
|---|---|---|
| CAP-1 | Champion ve Challenger modeli registry üzerinden doğrula + model+evidence+artifact yükle | registry.get_model_version champion=CHAMPION status, challenger=CHALLENGER status OK; 3 evidence kind (historical/walk-forward/paper) yüklendi; artifact_uri dosya mevcut → 4 load noktasında 0 hata |
| CAP-2 | Comparability invariants zorunlu tut (aynı pencere / aynı dataset / same cost / same universe / same compatibility / same thresholds) | 6 invariant'tan herhangi 1 mismatch → raise `CompareValidationError(INCOMPARABLE_* reason_code, mismatch_details dict)` — 6 mismatch 6/6 REJECT |
| CAP-3 | SBKT artifact → typed `ModelEvaluation` contract (11 required keys) üret. Sadece READ; yeni hesaplama YOK | Constructor 11 key contract check → `ModelEvaluation.schema_sha256()` 10x identik; 0 PnL/DD/cost yeniden hesap (diff against SBKT artifact sha → 0 diff proof) |
| CAP-4 | 11 metrik × N fold × R regime groups için per-metric delta üret; directionality (HigherBetter / LowerBetter / NeutralMatch) tanımlı | Her metric için `{champion_value, challenger_value, delta}` tuple; directionality contract match; bool neutral için equality; sayı metrics delta `challenger - champion` if HigherBetter else `champion - challenger` → positive delta = challenger pro |
| CAP-5 | Canonical score delta list (sorted keys) + deterministic serialization + `schema_sha256()` digest | Delta list sorted ASC metric_key ASC fold ASC regime ASC; `to_sorted_dict()` output karşılaştır 10 kez → AYNI; schema_sha256 set len=1 |
| CAP-6 | Evidence integrity doğrula: EvidenceRef.integrity_sha256 varsa local artifact bytes sha256 eşleşmeli | Integrity set & mismatch → `INTEGRITY_SHA_MISMATCH` reject; integrity set & match → PASS; integrity notset → SKIP ok |
| CAP-7 | Fold-level (per-fold) + Aggregate delta üret (matching fold count zorunlu) | Fold count EŞİT DEĞİL → `INCOMPARABLE_FOLD_COUNT` reject; aggregate compound `Π(1+r_i) - 1` Decimal kesin; avg sharpe/sortino/PF; min/max fold return — 7 aggregate field 7/7 match SBKT CAP-M05 digest |
| CAP-8 | Regime-performance delta: SBKT03 CAP-M06 strateji×rejim decomposition tüket; per-rejim return_pct + trade_count delta; group count mismatch reject | Decomposition sort (strategy_id ASC, regime ASC) identical; farklı count → `INCOMPARABLE_REGIME_GROUPS`; her group 2 delta produce |
| CAP-9 | Non-binding winner hint: `CCWinnerEnum` (champion_keeps / challenger_promoted / inconclusive_rerun); critical metric threshold eşitliğine göre | Critical 6 metric (return, maxDD, sharpe, sortino, PF, fees) challenger lehine pro → challenger_promoted; champion lehine → champion_keeps; mixed → inconclusive_rerun. HİÇBİR promotion gate decision (S-MDL-03 boundary). |
| CAP-10 | Fail-closed 25 reason_code enum deterministik; ANY invalid payload/state → raise; NONE silent success or None return | 25 fail-category × 1 fail-case 25/25 RAISE; exception `.reason_code` str enum 25 değer biri; `.details` dict non-empty |
| CAP-11 | Determinism 10× cross-instance: aynı inputs → 10x build 10x compare AYNI output; 2 farklı CompareEngine objeleri → delta sha eş | 10 run × ModelEvaluation sha set len=1; 10 run × delta_list sha set len=1; 10 run × winner hint enum set len=1; 2 engine sha set len=1 |
| CAP-12 | `ChampionChallengerEvaluation` contract-ready typed payload üret (S-CON-02C §3.5 field şemasıyla uyumlu 11 karşılaştırma delta); approval_refs boş (S-MDL-03 doldurur); gate_result=null; rollback_strategy_ref = registry predecessor ref (varsa) | Constructor payload karşılaştır ChampionChallengerEvaluation(**payload) → 0 schema error; `comparison_metrics` 11 zorunlu key tam; `winner` enum populated; `comparable` bool + `incomparable_reasons[]` list |

## Constraints (Design Benders — no vacuum)

C1. **Hard-red immutability**: hard-red.md listesi %100 korunur; değişiklik → audit reject (0 diff zorunlu). Contracts `app/contracts/*.py` 1.0.0 version preserved. `app/registry/*` DEĞİŞTİRİLMEZ (S-MDL-01 modül). Sadece `app/evaluation/` (yeni) + `tests/evaluation/` (yeni) değişebilir.
C2. **Zero new dependencies**: `pyproject.toml dependencies=[]` korunur. numpy/pandas/scipy YASAK. Stdlib: `dataclasses/enum/decimal/hashlib/json/re/pathlib/statistics/functools` ALLOWED.
C3. **No algorithm rewrite**: S-BKT-03 metrics, S-BKT-02 cost injection, S-PTF-01/02 PnL/DD, S-PTR-01 fill, S-MDL-01 registry — HEPSI SOURCE-READONLY wrapper ile tüketilir. Yeni PnL/DD/cost/fill/position/PORTFOLIO hesap YAZILMAZ.
C4. **No new contract class**: `app/contracts/*.py` DEĞİŞMEZ. Yeni Compare classes `app/evaluation/*` içinde local; sadece export edilen dataclass `ChampionChallengerEvaluationPayload` (contract field isimlerini KULLANIR ama contract file içine KONMAZ, çünkü contract version preserved).
C5. **Fail-closed first**: ANY incomparable / integrity / corrupt → RAISE. `None` return veya `empty list` ile silent bypass YOK.
C6. **Decimal / Float strict rule**: Monetary (return_pct, total_fees_quote, compound_aggregate) → Decimal ROUND_HALF_EVEN quantize 1e-8; Rate (sharpe/sortino/dd_ratio/pf/slippage_bps) → float round 8 dp; Counter (trade_count/coverage_count/days) → int exact. bool → bool.
C7. **Deterministic sort**: EVERY delta list / group list / evidence list explicit key ASC sort. dict insertion order GÜVENİLMEZ.
C8. **CAP-1 Parity**: evaluation module `datetime.now/time.time/Instant.now()/run_mode/source_type if-branch` AST 0 match. Deterministic ts: upstream evaluation_ts'den al.
C9. **Single owner extend (AD-7/13/24)**: Yeni CompareEngine class SADECE registry GET, SBKT artifact READ, model/evidence/transition okur. WRITE PATH (registry create/update/transition) DOKUNULMAZ (S-MDL-01 tek writer korumalı).
C10. **Placeholder backward**: Missing metric → SKIP değil; MISSING_METRIC reject. Fold count / regime group karşılaştırılabilir değilse reject. SBKT03 "None" values empty fold olamaz — enforce typed.
C11. **Boundary S-MDL-03/04/05**: `promotion_gate_result.passed` KESİNLİKLE set ETME (S-MDL-03). `rollback` algoritma YOK (S-MDL-04). `forbidden transition state mutation` YOK (S-MDL-05).

## Non-Goals (explicit — no downstream vacuum)

NG1. ❌ Promotion gate pass/fail decision / approval min-sample enforcement / auto-promotion (S-MDL-03)
NG2. ❌ Rollback algorithm / predecessor switch / champion-degrade trigger (S-MDL-04)
NG3. ❌ CAP-5 state mutation / direct ModelVersion status write (S-MDL-05)
NG4. ❌ Yeni PnL / maxDD / Sharpe / Sortino / fee / slippage / trade / cost MODEL hesaplama (S-BKT-03/02 + S-PTR/S-PTF tarafından önceden hesaplandı — burası sadece karşılaştırma)
NG5. ❌ New FeeModel / SpreadModel / SlippageModel / PartialFillModel / LatencyModel (S-PTR-01 + S-BKT-02)
NG6. ❌ ML training / fit / partial_fit / optimizer call / grid search / learn — AD-10 AI no execution
NG7. ❌ Real exchange / network / credentials / DB / Redis / Kafka / objectstore SDK — v1 hard boundary
NG8. ❌ Short / futures / leverage > 1 / real orders / live trades — v1 hard safety boundary
NG9. ❌ Contract version bump — mevcut dataclass field isimleri preserved; S-CON-02C contract_version 1.0.0 sabit
NG10. ❌ Registry storage write / create/update/transition — S-MDL-01 tek owner; NO write. SADECE read
NG11. ❌ Frontend dashboard rendering / FastAPI endpoint expose (S-API Epic14)
NG12. ❌ S-MDL-01/03/04/05 test dosyalarında veya SBKT 01/02/03 testlerinde assertion değişikliği (NO touch; backward compat preserved)

## Success Signal (Concrete, test/audit against)

S1. **Test matrix:** `python -m pytest tests/evaluation/ -q --no-header` → **≥ 240 PASS / 0 FAIL / 0 SKIP**
S2. **Regression preserved:** SBKT01 222/222; SBKT02 unchanged collected count; SBKT03 332/332; Registry 162/162; FULL tests/ `FAIL=0 / SKIP ≤ 5`
S3. **Direction correctness**: return/sharpe/sortino/PF/trade_count HigherBetter challenger lehine pozitif delta → PASS; maxDD/fees/slippage/window LowerBetter challenger lehine pozitif delta → PASS
S4. **Integrity SHA doğruluğu**: 1x correct match / 1x mismatch → PASS / REJECT (INTEGRITY_SHA_MISMATCH)
S5. **Incomparable 6 tür mismatch**: different dataset_kind / <99pct window overlap / diff thresholds / diff cost / diff universe / diff compatibility → 6/6 INCOMPATIBLE_* reject
S6. **10x determinism**: 10x same input → sha set len=1 for (ModelEvaluation, DeltaList, WinnerHint) × 3 = 3 set len=1
S7. **25 fail-category RAISE**: 25× fail_matrix 25/25 raise
S8. **AST safety**: 24 forbidden patterns (network/credential/DB/short/lev>1/fit/write_registry/datetime_now/run_mode_if) **24/24 0 HIT**
S9. **Contract payload acceptance**: ChampionChallengerEvaluation(**payload_from_engine) → 0 ContractSchemaError; 11 comparison_metrics keys exact set
S10. **Audit DoD**: dod.md 24-28 maddenin source evidence doğrulanması 28/28

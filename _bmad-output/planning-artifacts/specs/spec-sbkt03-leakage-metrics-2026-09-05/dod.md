# dod.md — S-BKT-03 Definition of Done (28 zorunlu kalem, audit checklist)
Her DoD → "Nasıl doğrulanır" + kaynaktan kanıt zorunlu.

| # | DoD Kalemi | Audit doğrulama | Kaynak | Durum (IMP phase) |
|---|------------|-----------------|--------|-------------------|
| 1 | **Full suite ≥4725 PASS / ≤5 SKIP / 0 FAIL** | `python -m pytest tests/ -q --no-header` çıktısı | SPEC Success signal | ☐ |
| 2 | S-BKT-01 222/222 PASS korunur | SBKT01 pytest çıktısı (gerçek) | Hard-red backward | ☐ |
| 3 | S-BKT-02 ≥619 collected unchanged PASS | SBKT02 pytest çıktısı (gerçek) | Hard-red backward | ☐ |
| 4 | Non-backtest 3631 PASS / 5 SKIP unchanged | tests/ non-backtest çıktısı | Baseline regression | ☐ |
| 5 | S-BKT-03 yeni test ≥ 320 PASS | SBKT03 file list collected × PASS sayısı | SPEC Success | ☐ |
| 6 | CAP-L01 6 stage injection → ALL raise | pytest parametrize 6 stage × 2 sym = 12 PASS | AC-L01-01..06 | ☐ |
| 7 | CAP-L02 intra/inter + edge WS cases PASS | AC-L02-01..05 5/5 | FR-042 | ☐ |
| 8 | CAP-L03 AST 48 leakage 0 HIT + 20 safety = 68/68 0 HIT | AST script çıktısı | SPEC Constraints 8 | ☐ |
| 9 | CAP-L04 fail-closed: failure_reason + NO mutation | 12 injection L04-01/02/03 PASS | AD-19 fail-closed | ☐ |
| 10 | CAP-M01 placeholder → populated; backward fixture None ok | 3/3 AC-M01-01..03 PASS | runner L157-159 | ☐ |
| 11 | CAP-M02 11 FR metrics (Sortino/PF/avg WL/expectancy/stability/total/net/DD/count/fees/slip) ALL compute PASS | 11/11 AC M02 PASS | FR-059 FR-038 | ☐ |
| 12 | CAP-M03 5 override cost metrics (taker/maker spread slip latency partial) + sha → 6 PASS | 6/6 AC-M03 | S-BKT-02 cost inj | ☐ |
| 13 | CAP-M04 per-fold 3/3 PASS (len/sort/equality) | AC-M04-01..03 | EPICS multi-fold | ☐ |
| 14 | CAP-M05 aggregate 6/6 PASS (avg/compound/minmax/sha) | AC-M05-01..06 | MFR L63-66 extend | ☐ |
| 15 | CAP-M06 strategy×regime decomposition 4/4 PASS | AC-M06-01..04 | FR-028/FR-059 | ☐ |
| 16 | CAP-DET01 cross-determinism 10×2 SHA set=1, sorted dict diff == 0 | 20 runs | AD-20 | ☐ |
| 17 | CAP-1 no branch (datetime.now/run_mode/...) 0 match AST | 2 patterns × scan | CAP-1 parity | ☐ |
| 18 | CAP-2 QualityFlags mutate 0; validator import 0 call | AST grep `validate_quality/setattr(QualityFlags` | CAP-2 | ☐ |
| 19 | CAP-4 RiskGate before PaperOrder preserved | pipeline L583 gate → L609 PO unchanged AST 1/1 match order | CAP-4 S-RSK-02 | ☐ |
| 20 | Single Writer: 0 direct `Position(` / `Portfolio(` in backtest/metrics/leakage modules | AST grep module 5 files | AD-7/13/24 | ☐ |
| 21 | Hard-red files 0 diff bytes b6f5411 → bbade89 HEAD from b6f5411 delta preserved (only approved added files exist) | `git diff HEAD hard-red-args` 0 output | hard-red.md | ☐ |
| 22 | pyproject.toml dependencies=[] unchanged | `git diff bbade89 pyproject.toml` 0 | constraints | ☐ |
| 23 | Yeni duplicate Model class 0 (Fee/Spread/Slip/Latency/PartialFill/Cost) | grep class Model + 7 forbidden 0 | non-goals 3 | ☐ |
| 24 | S-PTF-01/02/03 source file bytes 0 diff rewrite 0 | `git diff bbade89 -- app/simulation/` 0 output (no touch) | reuse-map.md | ☐ |
| 25 | No git add/commit/push → cached 0 staged | `git diff --cached --name-only` EMPTY | user VERBATIM | ☐ |
| 26 | Artifact roundtrip: save_backtest_artifact → load_backtest_artifact → sha match (5 case default+overrides+leak) | 5/5 roundtrip | runner L240-259 | ☐ |
| 27 | Test quality: S-BKT-03 ≥320 new test → 0 assertionless; 0 duplicate cell; ≥80% parametrize coverage | Inspection sample 30 tests | SPEC constraints | ☐ |
| 28 | OPEN DECISIONS 9→4 veya daha az kalır; resolved decisions evidence memlog append | .memlog append count | risks-open.md | ☐ |

---
*28/28 PASS required → COMMIT READY audit.*

# S-MDL-02 Expected File Changes

YENİ ÜRETİLECEK (production):
```
app/evaluation/
├── __init__.py                  # Public surface: CompareEngine, MetricDelta, CompareValidationError, ChampionChallengerEvaluationPayload, DIRECTIONALITY enum, load_helpers
├── engine.py                    # CompareEngine dataclass (main) — 12 capabilities implementation (CAP1-12)
├── delta.py                     # MetricDelta dataclass + per-metric direction table (HigherBetter/LowerBetter/Neutral) + canonical serialization
├── exceptions.py                # CompareValidationError(str reason_code, dict details) + 25 ERR_* constants (CAP-10)
├── comparability.py             # 6 invariant guard (window, dataset, thresholds, cost, universe, compatibility)
└── contract_payload.py          # ChampionChallengerEvaluationPayload helper (typed) converting deltas to comparison_metrics 11-key flat dict
```

YENİ ÜRETİLECEK (tests):
```
tests/evaluation/
├── conftest.py                  # fixtures: sample_champion_mv / sample_challenger_mv / sample_sbkt_artifact_json / sample_evidence_refs / fresh_evaluation_engine (new engine per test)
├── test_smdl02_01_cap1_load_status.py       # 22 tests A-01..A-22 CAP-1
├── test_smdl02_02_cap2_comparability.py      # 25 tests B invariants CAP-2
├── test_smdl02_03_cap3_artifact_me.py         # 39 tests CAP-3 build MEval
├── test_smdl02_04_cap4_direction.py           # 55 tests D direction deltas
├── test_smdl02_05_cap5_canonical_sha.py      # 6 tests E canonical
├── test_smdl02_06_cap6_integrity.py          # 4 tests F SHA
├── test_smdl02_07_cap7_fold_aggregate.py     # 18 tests G folds
├── test_smdl02_08_cap8_regime_groups.py      # 14 tests H regime deltas
├── test_smdl02_09_cap9_winner_hint.py        # 7 tests I hints
├── test_smdl02_10_failclosed_25.py           # 25 tests J reason codes
├── test_smdl02_11_determinism_10x.py         # 13 tests K
├── test_smdl02_12_contract_cce_payload.py    # 8 tests L
├── test_smdl02_13_safety_ast_backward.py     # 13 tests M
└── test_smdl02_14_smoke_quick.py              # 1 smoke
```

SPEC companion dosyaları (oluşturuldu bu tur, spec gelistirme asamasında):
```
_bmad-output/planning-artifacts/specs/spec-smdl02-eval-compare-2026-09-12/
├── SPEC.md
├── .memlog.md
├── open-decisions.md
├── test-plan.md
├── acceptance-criteria.md
├── dod.md
├── hard-red.md
├── expected-file-changes.md
└── reuse-map.md
```

**DEĞİŞTİRİLMEYEN — EKSİK**:
```
app/contracts/*          ← HARD-RED (contract_version 1.0.0, DO NOT EDIT)
app/registry/*           ← S-MDL-01 tek writer DO NOT EDIT (CAP-10 single writer)
app/backtest/*           ← HARD-RED SBKT 01/02/03 dosyaları DO NOT TOUCH
app/platform/event_bus.py / app/features/* / app/regime/* / app/strategies/* / app/opportunity/* / app/risk/* / app/simulation/* / app/replay/* — HARD-RED DO NOT MODIFY
pyproject.toml — dependencies=[] preserved
tests/backtest/test_sbkt01_* / test_sbkt02_* / test_sbkt03_* — HARD-RED no assertion changes
tests/registry/* — unchanged (read-only not modified)
```

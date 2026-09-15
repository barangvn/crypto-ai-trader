# S-MDL-04 Hard-Red 0 diff (20 scopes immutable — 14 inherit + 6 new rollback-specific)

AUDIT COMMAND (20 scopes inherit first 14, add 6 rollback module extra):
```
# 14 scopes S-MDL-03 aynen devam
git diff --name-only HEAD -- app/contracts app/registry tests/registry app/backtest tests/backtest app/risk app/simulation app/replay app/platform app/features app/regime app/strategies app/opportunity pyproject.toml
# + 6 additional rollback specific AST literal zero check (scoped app/rollback only)
pytest -q tests/rollback/rollback_11_registry_readonly_boundary.py tests/rollback/rollback_12_smdl03_border_strict.py tests/rollback/rollback_15_safety_ast_forbidden.py tests/rollback/rollback_16_f5_champion_challenger_bypass.py
```
Expected first 14 diffs = EMPTY; second 6 AST = 0 HIT.

---
## 20 Immutable Scopes (0 byte diff / 0 literal occurrence)

**PART 1 — 14 inherit (S-MDL-03 hard-red identical):**
1. app/contracts/* (S-CON-02C v1.0.0; field/import/public export order preserved)
2. app/registry/* (registry CRUD single-writer S-MDL-01 — READ only)
3. app/backtest/*
4. tests/backtest/*
5. tests/registry/*
6. app/risk/*
7. app/simulation/*
8. app/replay/*
9. app/platform/* (event_bus publish NG5 — no use inside rollback)
10. app/features/*
11. app/regime/*
12. app/strategies/*
13. app/opportunity/*
14. pyproject.toml (dependencies=[])

**PART 2 — 6 ROLLBACK NEW HRC15-20 (app/rollback/ module AST 0 literal/call):**
15. HRC15: registry.request_transition() CALL count = 0 (under app/rollback/*.py) — NG1 / CAP-5 mutation deferred S-MDL-05
16. HRC16: `if run_mode ==` / `if source_type ==` / `datetime.now()` AST pattern count = 0 under app/rollback — CAP-1 parity
17. HRC17: function name string contains `auto_rollback` / `trigger_rollback` / `execute_rollback` (def or call) = 0 — NG2 no automatic rollback execution
18. HRC18: literal `to_status="challenger"` OR `ModelLifecycleStatus.CHALLENGER` assigned to current champion FSM target output = 0 — F5 S-CON-02C L202-203 FORBIDDEN bypass
19. HRC19: 0 disk write primitive — `open(..., "w"|"wb"|"a")` / Path.write_text / rename-overwrite / mkdir-and-write-atomic count = 0 — NG write path; single writer registry only
20. HRC20: Weighted composite Σ w_i × norm(metric) compute inside app/rollback/*.py AST identifier `weighted_total` / `Σw` pattern count = 0 — S-MDL-03 boundary only promotion uses weighted score; rollback eligibility only READ (not recompute)

---
## Allowed ONLY (NEW files or THIS spec folder)

```
# SPEC ARTIFACTS — BÜTÜN BU KLASÖR (new files 10 companion + SPEC.md)
_bmad-output/planning-artifacts/specs/spec-smdl04-rollback-2026-09-15/  (THIS folder)

# FUTURE IMPLEMENTATION STORY ALLOWLIST (henüz YAZILMADI — S-MDL-04 implementation story sonrası)
app/rollback/          FUTURE 6 NEW files: __init__.py exceptions.py thresholds.py evidence.py builder.py engine.py
tests/rollback/        FUTURE 18 NEW families + conftest.py (19 test files)
```

**MEVCUT KOD / TEST DOSYALARINA 0 DEĞİŞİKLİK.**

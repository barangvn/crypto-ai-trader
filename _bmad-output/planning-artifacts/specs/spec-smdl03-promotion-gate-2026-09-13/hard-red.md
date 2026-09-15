# S-MDL-03 Hard-Red 0 diff (14 scopes immutable)

AUDIT COMMAND:
```
git diff --name-only 9325236 -- app/contracts app/registry app/backtest tests/backtest tests/registry app/risk app/simulation app/replay app/platform app/features app/regime app/strategies app/opportunity pyproject.toml
→ Expected EMPTY.
```

## 14 Immutable

1. app/contracts/* (S-CON-02C 1.0.0)
2. app/registry/* (registry CRUD single-writer S-MDL-01 — READ only)
3. app/backtest/*
4. tests/backtest/*
5. tests/registry/*
6. app/risk/*
7. app/simulation/*
8. app/replay/*
9. app/platform/* (event_bus publish is NG10 — no use)
10. app/features/*
11. app/regime/*
12. app/strategies/*
13. app/opportunity/*
14. pyproject.toml (dependencies=[])

## Allowed ONLY (NEW files or THIS spec folder)

```
app/gate/          6 NEW files: __init__.py exceptions.py weights.py thresholds.py builder.py engine.py
tests/gate/        15 NEW families + conftest
_bmad-output/planning-artifacts/specs/spec-smdl03-promotion-gate-2026-09-13/  (THIS SPEC folder - companion 9 + SPEC.md)
```

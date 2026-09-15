# S-MDL-03 Expected File Changes (allowlist only; HARD-RED 0 diff)

## Production — NEW app/gate/ 6 files

1. app/gate/__init__.py — public exports
2. app/gate/exceptions.py — GateValidationError, GateInvariantError + 18 ERR_GATE_* constants
3. app/gate/weights.py — load/validate/renormalize weights
4. app/gate/thresholds.py — load/validate hard/soft/norm bounds checks
5. app/gate/builder.py — build_promotion_gate_result, inject_gate_into_cce, invariant enforce, staleness/approval/comparable/integrity checks
6. app/gate/engine.py — PromotionGate class (no registry write, no bus publish, deterministic)

## Tests — NEW tests/gate/ (15 families + conftest)

7. tests/gate/conftest.py (fixtures)
8–22. T01..T15 per family

## Spec artifacts (THIS FOLDER)

23. SPEC.md
24. open-decisions.md
25. weights.md
26. thresholds.md
27. test-plan.md
28. hard-red.md
29. acceptance-criteria.md
30. dod.md
31. expected-file-changes.md
32. reuse-map.md

## Forbidden Zero-touch hard-red
app/contracts/*, app/registry/*, app/backtest/*, tests/backtest|registry, app/risk|simulation|replay|platform|features|regime|strategies|opportunity, pyproject.toml.

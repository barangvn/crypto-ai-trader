---
scope: E-API Epic 14 Expected File Changes (FUTURE-PHASE) — 1 explicit existing exception: pyproject.toml ONLY
created: 2026-09-19
updated: 2026-09-20 (C1 CASE B APPROVED: pyproject.toml single existing-file exception)
---

# Expected File Changes

## 1. Companion Spec MD (Bu klasör — 10 dosya; yeni folder) ✅ (şu an yazıldı 10/10)
1. `SPEC.md`
2. `acceptance-criteria.md`
3. `dod.md`
4. `test-plan.md`
5. `hard-red.md`
6. `open-decisions.md`
7. `source-traceability.md`
8. `reuse-map.md`
9. `sp05-self-validation.md`
10. `expected-file-changes.md` (self)

## 2. Production Code (18 dosya — YENİ KLASÖR app/platform/api/ + app/platform/observability/ + configs — S-MDL existing dosya MODIFY 0)
- `app/platform/api/__init__.py` (yeni)
- `app/platform/api/main.py` (FastAPI app, middleware, /api/v1 prefix — yeni)
- `app/platform/api/routes_system.py` (system group + POST emergency — yeni)
- `app/platform/api/routes_market.py` (market 5 route — yeni)
- `app/platform/api/routes_opportunities.py` (2 route — yeni)
- `app/platform/api/routes_regime.py` (2 route — yeni)
- `app/platform/api/routes_strategies.py` (3 route — yeni)
- `app/platform/api/routes_portfolio.py` (4 route — yeni)
- `app/platform/api/routes_performance.py` (3 route — yeni)
- `app/platform/api/routes_models.py` (5 route — yeni)
- `app/platform/api/routes_risk.py` (3 GET + POST kill-switch — yeni)
- `app/platform/api/routes_logs.py` (2 route — yeni)
- `app/platform/api/schemas.py` (Pydantic request/response; N1 body fields idempotency_key + double_confirm_token ULID REQUIRED — yeni)
- `app/platform/api/auth.py` (Ayrı izin scope EMERGENCY/RISK validation placeholder — yeni)
- `app/platform/api/audit.py` (Audit event writer N1 2 field zorunlu — yeni)
- `app/platform/observability/__init__.py` (package init — yeni)
- `app/platform/observability/metrics.py` (Prometheus endpoint + 11 metric family — yeni)
- `configs/prometheus_rules_base.yml` (İlk alert seti 4 groups 12 rules — yeni)

Existing `app/platform/event_bus.py`, `app/platform/__init__.py` + TÜM S-MDL production domain dosyaları
(app/registry, app/risk, app/contracts, app/evaluation, app/gate, app/strategies, app/ingest, app/processing,
app/backtest, app/simulation) → MODIFY 0 dokunulmadan.

## 3. Test (5 dosya — YENİ KLASÖR tests/api/ — existing MODIFY 0)
1. `tests/api/conftest.py`
2. `tests/api/test_sapi01_10read_contracts.py`
3. `tests/api/test_sapi02_2write_permission_audit.py` (N1 T2.1..T2.4 idempotency + double-confirm)
4. `tests/api/test_sapi03_cap6_forbidden_scan.py` (T3 ANA PROOF)
5. `tests/api/test_sapi04_prometheus_metrics.py` (T4.1..4.5)

## 4. EXPLICIT SINGLE EXCEPTION (CASE B APPROVED — C1) — Existing File Modification ALLOWED (TEK İSTİSNA)

| # | Existing file | Exact allowed purpose | Minimum allowed modification | Source reference | S-MDL behavior impact? | Unrelated dep changes? |
|---|---|---|---|---|---|---|
| **C1** | `pyproject.toml` | E-API future-phase 3rd-party dependency declaration (FastAPI 0.141.1 + uvicorn ≥0.34 + prometheus-client ≥0.22) inside `[project.optional-dependencies]` subgroup `eapi` (PEP 621 idiomatic Python future-phase optional deps). | +5 lines ONLY (no other toml section touched, no unrelated dep added, no install_requires change): `eapi = [\n    "fastapi==0.141.1",\n    "uvicorn>=0.34",\n    "prometheus-client>=0.22",\n]` | (1) **Msg4 user implementation directive VERBATIM:** *"EXISTING MODIFY: ONLY pyproject.toml add optional deps (0 S-MDL prod modify)."* (2) **SPEC §8 L53 NORMATİF stack:** FastAPI==0.141.1 / Prometheus≥0.22 / Uvicorn≥0.34 (ARCH L551 / L554). (3) **SPEC §14 Hard-Red L101 FUTURE EXCEPTION:** *"HTTP listener fastapi + 3 third-party dep"*. | **0.** `[project.optional-dependencies]` subgroup is NOT installed by default (`pip install .` 0 etkisi). Only explicit future-phase `pip install ".[eapi]"` ile yüklenir. S-MDL stdlib-only çalışma zamanı korunur. | **0. No unrelated dep**; tam 3 package, exact SPEC sürümleri. |

### Forbidden (this single exception DIŞINDA existing-file modification HÂLÂ FORBIDDEN):
- `tests/failure/test_no_credentials.py` → modification FORBIDDEN (reverted — diff = 0).
- `tests/failure/test_bus_no_credentials.py` → modification FORBIDDEN (reverted — diff = 0).
- Any other existing app/* / tests/* / configs/* / root file (unless pyproject.toml C1 tektir) → FORBIDDEN.
- Any broadening of C1 (install_requires change, new package, new group name, > 5 lines) → FORBIDDEN.

**Toplam:** 10 companion + 18 production (new folder) + 5 test (new folder) + 1 existing pyproject C1 single exception = 34 artifacts.
**Existing modül değiştirme (C1 TEK İSTİSNA HARİCİNDE):** 0.  # Explicitly canonical after C1 CASE B APPROVAL

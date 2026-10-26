# Architecture Traceability — S-FND-04

Maps S-FND-04 every scope item to AD-1..AD-25 ARCHITECTURE-SPINE.md binding invariants & NFR.

| Arch ID | Title | FND-04 Scope Item How Satisfies | Verification |
|---|---|---|---|
| AD-1 | Single Repo Modular Monolith (bounded context) | Config layer placed: `app/platform/config/` → matches bounded context `platform` klasör (AD-1 line 48). S-FND-02 app/platform/observability next door neighbor klasör. Correct. | LS folder structure: app/platform/{observability, config, api, ...} |
| AD-4 | Live / Replay Parity (NFR-010) | ConfigFactory exposes `run_mode_default` (Enum replay/paper). Domain code NOT branch by config; consumers only use `run_mode_default` passed typed; AD-4 zorunlu: "branching only clock_ref + source_type, not run_mode". Config layer does NOT branch logic. Correct: run_mode is VALUE, not code path if. | S-FND-04 code scan: `if run_mode ==` 0 match in layer (grep); passed downstream uses. |
| AD-5 | Data Quality First Hard Gate (NFR-011) | Config layer DOES NOT modify / generate data-quality flags (AD-5 owner: ingest/processing DQM module). Quality is not here. HOWEVER config VALIDATION mirrors: validation fail → startup ABORT (AD-5 hard gate spirit → fail fast). | Fail-closed FC-1..FC-8. Safety lock violation raise. Startup stop not continue degraded. Consistent. |
| AD-6 | Internal Event Bus First | NOT THIS STORY. E-PLN scope (typed bus + outbox). FND-04 config module has 0 event publish/subscribe code. Correct separation. | AST grep bus/event/subscribe/publish: 0 matches config layer. Deferred E-PLN. |
| AD-7 | Single-Writer Mutation Ownership / Read Model Ownership | ConfigLayer mutation owner = ONLY `app/platform/config/` (FND-04). No OTHER module allowed to overwrite AppConfig: frozen constants, frozen top-level optional fields, dataclass frozen where applicable. Config version immutable. Governance registry (AD-7 row 4 model registry gov owner) → 0 touch config layer. Correct. | AST grep imports FROM app.platform.config setattr → 0 (except public readonly read). Setattr VersionConstants FrozenInstanceError. |
| AD-8 | Regime as Independent Service Boundary | NOT CONFIG SCOPE. No regime here. Deferred E-REG. Correct separation. | Regime pattern 0 matches. |
| AD-13 | Portfolio State Single-Writer | NOT CONFIG SCOPE. Deferred E-PTF. Correct. | 0 import simulation/portfolio. |
| AD-14 | Governed Learning Lifecycle | NOT CONFIG SCOPE. E-MDL 4 hikaye owner. FND-04 0 registry status/transition/lifecycle import. HR-4 Hard-red enforces 0. Correct. | HR-4 0 import governance/registry. |
| AD-15 | Polyglot Storage Minimal (Postgres + Timescale) | Config layer SCOPE: NO DB ACCESS. Reads ONLY local INI file. PG/Timescale/Object Storage deferred E-PLN + future. Correct per AD-15 MVP minimal db. | 0 import psycopg/timescaledb/sqlalchemy; pg connection strings IN config DEĞİL, INI içinde env alanları = db_namespace name only. |
| AD-16 | API Query + Control Plane Only | E-API scope. FND-04 config layer: 0 HTTP route, 0 API framework import (fastapi/flask). Correct. | AST 0 fastapi/flask/starlette import. |
| AD-18 | 4 Environment Strictly Separated (NFR-016). Dev/Test/Stg/Paper-Prod. | ConfigFactory Literal validation: env_name in ["dev","test","stg","paper-prod"] → only 4 allowed (AC-12). Unknown env error. db_namespace, artifact_path, run_mode per-env typed. Correct AD-18. | AC-12 test; 4 env literal enum. |
| AD-19 | 10 Failure Modes Default Safe | S-FND-04 config: ALL 8 FC fail-closed (not defaults). File not found → exception; section missing → exception; safety lock violated → exception; YAML gate → exception; type coerce → exception; interpolation → exception; extension error → exception; frozen mutate → exception. 8/8 fail stop exception alert pattern (startup abort, degraded allowed NEVER). AD-19 matches: 10 defined failure modes FND-04 covers 8 config ones. | Fail-closed FC-1..FC-8 8/8 test PASS; all exceptions no defaults. |
| AD-20 | Deterministic Testability by Fixture / Replay Inputs (contract/replay/failure_injection/regression tests architectural mandate) | Config layer 100% deterministic (§7 D1..D6, 6D ×10 len(set)=1 determ test). Test fixtures: Typed pytest markers S-FND-03 → FND-04 test paketi markerlardan faydalanır (AC-01..24 via existing markers). Correct AD-20. | Determinism test green; pytest markers used. |
| AD-22 | FeatureVector Flat Dict (No Nested) (S-REG Feature) | Config layer extension_sections: allows dict[str, Any] however SPEC: typed contracts only core. Platform Contract section: decimal_precision (int). Flat typed fields. Nested deferred feature engine. Correct AD-22 principle: "flat types prefer for performance". | FeatureVector 0 reference config layer; field pattern in typed models: scalar types only. Flat ok. |
| AD-23 | Registry / Lifecycle State Mutate ONLY Registry.request_transition | Correct. ConfigLayer 0 registry mutation. HR-4 0 matches. Read model only, registry commands YOK. | HR-4 pass. |
| AD-24 | Storage / Outbox / Inbox Single Writer (durability) | Config: 0 DB write. Correct (E-PLN owner). Inbox/outbox YOK here. | Grep outbox/inbox/sql 0. |
| AD-25 | Strategy Purity: StrategyContext ONLY Tüketir | Config layer exports Strategy plugin NOTHING about. Strategy context: E-STR story owner. Correct layer separation. | 0 strategy import context. |

---

## AD / NFR / FR Summary Binding Counts

- Toplam AD-1..25 = 25
- **Bağlanan (Directly Implemented or Aligns):** AD-1 / AD-4 / AD-5 / AD-7 / AD-15 / AD-18 / AD-19 / AD-20 / AD-22 / AD-23 / AD-24 / AD-25 → 12 doğrudan
- **Deferred Explicit (Not This Story Scope):** AD-6 (E-PLN), AD-8 (E-REG), AD-13 (E-PTF), AD-14 (E-MDL), AD-16 (E-API) → 5 explicit deferred
- **Unrelated (No Touch):** AD-2/3/9/10/11/12/17/21 = 8 (boundary correctness no touch = implicitly OK no coupling)

Total = 25 ✅

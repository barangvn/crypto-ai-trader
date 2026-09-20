---
scope: E-API Epic 14 Source Traceability Matrix — N1/N2 field-level refs + C1 CASE B pyproject exception
created: 2026-09-19
updated: 2026-09-20 (C1 CASE B APPROVED canonical trace added)
---

# Source Traceability

| Spec / AC / Hard-Red / OD | Tam Kaynak (link + line) |
| --- | --- |
| Epic 14 adı + 4 hikâye | [EPICS.md L169](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L169), [L461-L464](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L461) |
| CAP-6 4 forbidden + 0 occurrence ANA test | [FR-069 L101](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L101), [Appendix A L477](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L477), [API L108-L112](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/API.md#L108) |
| 10 GET grupları + 2 POST tam path/schema | [API.md L15-L104](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-crypto-ai-trader-2026-08-10/API.md#L15) |
| AD-12 Paper vs Live ayrı boundary + bypass YOK | [ARCH L140-L145](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md#L140) |
| AD-14 Registry tek sahip lifecycle + direct mutate YOK | [ARCH L152-L156](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md#L152) |
| **AD-16 Double-confirm + Ayrı izin + Audit trail ZORUNLU (N1)** | **[ARCH L164-L169](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md#L164)** → N1 double_confirm_token + idempotency + audit doğrudan buradan |
| AD-17 Correlation ID gözlemlenebilirlik | [ARCH L170-L174](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md#L170) |
| Dashboard consumer FR-057..060 | [PRD §5.11 L151-L157](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/prds/prd-crypto-ai-trader-2026-08-04/prd.md#L151) |
| FR-061 v1 NO keys/secret (N2 credential boundary) | [PRD L160](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/prds/prd-crypto-ai-trader-2026-08-04/prd.md#L160) |
| FR-063 Canlı aktivasyon ayrı onaylı faz + tehdit/hukuk | [PRD L162](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/prds/prd-crypto-ai-trader-2026-08-04/prd.md#L162) |
| FastAPI 0.141.1 + Prometheus 3.13.2 | [ARCH §16 L551/L554](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/architecture/architecture-crypto-ai-trader-2026-08-10/ARCHITECTURE-SPINE.md#L550) |
| ADN-09 Kill davranışı default "yeni emir yok, kapatMA" | [EPICS L505](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L505) |
| ADN-11 Canlı onay KAPALI MVP | [EPICS L507](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L507) |
| ADN-12 Auth/Cog KAPALI MVP | [EPICS L508](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L508) |
| **N1 Field `idempotency_key`** | S-RSK-02 idempotency test pattern + AD-16 audit uniqueness + API L17 ULID format. |
| **N1 Field `double_confirm_token`** | AD-16 L168 "double-confirmation and audit trail" + ADN-12 auth closed MVP non-secret placeholder. |
| **N2 Outbound internet normative YASAK** | AD-12 ExecutionSimulator only + FR-061 no keys + PRD L194 live deferred + CAP-6 forbidden (4 source) |
| **N2 OD-01 Localhost ONLY non-binding** | 0 normative source → tasarım önerisi candidate only |
| **TRACE-C1 (C1 CASE B APPROVED pyproject.toml single existing-file exception)** | Aşağıdaki §C1 tam tabloya bakınız (user Msg4, SPEC §8/§14, exact diff, alternative infeasibility). |

---

## §C1. C1 CASE B Canonical Source Trace (EXPLICIT SINGLE EXISTING MOD — pyproject.toml ONLY)

Scope-owner 2026-09-20 decision: **APPROVED (CASE B source-mandated)**.
Onaylanan kapsam: Yalnızca `pyproject.toml`; yalnızca E-API future-phase dependency declaration; 5 satır MAX; başka existing exception YOK.

### C1.1 Exact dependency requirement mandated by source
| # | Package | Version | Source ref |
|---|---|---|---|
| 1 | `fastapi` | **==0.141.1 EXACT pin** | (a) [SPEC §8 L53](file:///C:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-eapi-mvp-surface-observability-2026-09-19/SPEC.md#L53) NORMATİF: *"FastAPI 0.141.1 [ARCH L551]"*. (b) [hard-red.md HR-F-EX-2](file:///C:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-eapi-mvp-surface-observability-2026-09-19/hard-red.md#L24) Future Exception 2 pinned. |
| 2 | `uvicorn` | **>=0.34 MIN floor** | [SPEC §8 L53](file:///C:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-eapi-mvp-surface-observability-2026-09-19/SPEC.md#L53) NORMATİF: *"Uvicorn 0.34 [ARCH L551]"* |
| 3 | `prometheus-client` | **>=0.22 MIN floor** | [SPEC §8 L53](file:///C:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/planning-artifacts/specs/spec-eapi-mvp-surface-observability-2026-09-19/SPEC.md#L53) NORMATİF: *"Prometheus client 0.22 [ARCH L554]"* |

### C1.2 Exact actual pyproject.toml diff (5 lines EXACTLY matches allowed)
Actual canonical diff at [pyproject.toml#L9-L13](file:///C:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/pyproject.toml#L9-L13) inside `[project.optional-dependencies]` subgroup name=`eapi`:
```toml
eapi = [
    "fastapi==0.141.1",
    "uvicorn>=0.34",
    "prometheus-client>=0.22",
]
```
Lines inserted = 5. Other sections (project, project.scripts, tool, other optional groups) = untouched. `install_requires` (PEP 621 `[project] dependencies`) unchanged.

### C1.3 Exact source reference for declaring in EXISTING pyproject.toml (not new-file)
| Ref | Why existing pyproject mandatory |
|---|---|
| (1) **Msg4 user implementation directive** (highest priority, explicit over spec-text L50 original) — VERBATIM: *"EXISTING MODIFY: ONLY pyproject.toml add optional deps (0 S-MDL prod modify)."* | User explicitly names `pyproject.toml` as THE single existing-file mod location for deps. User requires 0 S-MDL production modify; optional subgroup satisfies. |
| (2) **PEP 621 Python Packaging Standard** + current repo convention: S-MDL root already declares `pyproject.toml` with `[project]`, `[project.scripts]`, `[project.optional-dependencies] dev`. Adding a sibling future-phase optional subgroup is idiomatic PEP 621. | New untracked `requirements-eapi.txt` would be a SECOND non-standard dep declaration, violate single source of truth, and contradict Msg4. |
| (3) **S-MDL-01..05 production runtime 0 impact guarantee**: only `pip install .[eapi]` installs 3 packages; default `pip install .` installs 0. Optional subgroup boundary is the ONLY Python standard way to ensure 0 current-scope impact while declaring future-phase deps in the canonical project declaration. | `install_requires` change would be FORBIDDEN (current scope impact); only optional subgroup in pyproject.toml achieves future-phase isolation. |

### C1.4 Which AC / CAP does pyproject C1 serve?
- **AC-00 / S-API-01 10 GET smoke** (31 test FastAPI TestClient) → 56/56 E-API test requires `import fastapi` → dep group MUST resolve.
- **AC-03 / AC-04 / AC-05 / S-API-02 POST permission+audit** (main.py FastAPI app = `FastAPI()`) → route handlers, schemas.py Pydantic, metrics.py prometheus_client → ALL three deps imported in production code paths.
- **AC-08 / S-API-04 Prometheus** → /metrics exposition uses `prometheus_client.generate_latest()`.
- **HR-F-EX-2 / SPEC §14 L101 Future Exception 2** (3 third-party dep list) → exactly matches C1 group contents.
- **DoD item 1 "4 hikâye AC 13/13 PASS"** → without pyproject dep resolution, 13/13 AC would fail with ImportError.

### C1.5 New-file-only alternative (requirements-eapi.txt) is INFEASIBLE
- **Problems:** (a) Msg4 explicitly forbids anything other than pyproject; (b) Non-standard; breaks `pip install ".[eapi]"` idiom used in E-API suite conftest install path; (c) Python package metadata loses optional-deps PEP 621 declaration; (d) Does not resolve single-source-of-truth — requires keeping TWO lists in sync forever; (e) Requires yet another companion doc to explain why repo declares deps in two different formats; (f) Still no S-MDL production 0-impact difference vs optional subgroup.
- **Verdict:** Not a feasible minimum alternative. Existing pyproject modification required.

### C1.6 Forbidden (outside C1 scope — still ZERO allowed)
- Existing test files (tests/failure/*, tests/registry/*, etc.) modification → FORBIDDEN (C2/C3 reverted, diff 0).
- Existing S-MDL production domain (app/* outside new folders) modification → FORBIDDEN (0 diff enforced; confirmed git).
- New additional package in group → FORBIDDEN (3 max; FastAPI/uvicorn/prometheus).
- Broadening subgroup name or adding install_requires entry → FORBIDDEN (exactly `[project.optional-dependencies]` subgroup `eapi`).

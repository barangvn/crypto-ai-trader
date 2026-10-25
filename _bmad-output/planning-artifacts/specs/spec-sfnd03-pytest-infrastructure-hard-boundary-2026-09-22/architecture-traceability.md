# Architecture Traceability — S-FND-03

## CAP Matrix (15 Bağlama — AD × NFR)
| CAP # | Architectural Binding (AD) / NFR | S-FND-03 nasıl bağlar? | Üretim (N-01..N10) / Test Referans |
|---|---|---|---|
| CAP-1 | AD-1: Modular Boundaries (ExchangeAdapter core leak prevent) | F1' prime scan: sadece app/ingest/adapters network import allow — AD-1 modular bound enforce via static scan | N04 helpers (F1' scan rule), N06 F1' test |
| CAP-2 | AD-7: Single Writer Ownership (tek yazarlık) | DoD-6 Ownership separation invariant: SFND03 testlerinden S-FND-01 tests/failure/* import 0, tek yazarlık korunur; ayrıca registry write path 0 import (AD-7 subset) | N10 audit test (A-3 import graph), HR-4 |
| CAP-3 | AD-10: AI No Execution Authority | F4' prime REAL order name scan: AI veya decision katmanında gerçek emir isimleri BLOCKER; long-only + paper prefix zorla | N09 F4' test, F4' helper |
| CAP-4 | AD-11: Risk Engine Final Approval | F3' prime leverage/short taraması: Risk Engine tarafından blocklanacak kuralların statik ihlalleri (short direction leverage>1) pre-commit aşamasında görünür kılar | N08 F3' test, helper |
| CAP-5 | AD-12: Paper vs Future Live Ayrımı — v1 canlı emir yolu YOK | F4' prime scan "paper_"/"simulate_" önek zorunluluğu, "send_real_order" vb. BLOCKER — AD-12 doğrudan uygulama | N09 F4' helper def/name rule |
| CAP-6 | AD-17: E2E Observability Correlation | AC-21: Optional correlation_id label PatternScanFinding — S-FND-02 correlation provider inject (no-op if yok) | N04 helpers finding builder, AC-21 test |
| CAP-7 | AD-18: Environment Separation | 3 marker: `contract` (all env), `replay` (replay data), `failure_injection` (dev/test). AD-18 env ayrımı markerlar ile PR çalıştırma ayrımı yapılmasına imkan | N01 pytest.ini markers 3, N05 marker catalog test |
| CAP-8 | AD-19: Failure Defaults to Safe Stop | 8 Fail-closed kural FC 1..8 — marker parse fail veya scan broken → session FAIL, sessiz continue YOK (güvenli dur) | N10 fail-closed 8 test, §8 |
| CAP-9 | AD-20: Testability Constraint | Marker mechanism, PR-gate scanner fixture (N03 conftest) — AD-20 test edilebilirlik için contract/replay/failure injection mark + explicit collection hooks sunar | N03 conftest pytest_collection_modifyitems, N05 marker smoke |
| CAP-10 | NFR-002 Reliability (fail closed detectable) | FC-3 SyntaxError dosya → devam, sonrasında pass_fail=False; FC-7 timeout BLOCKER → failure detectable, logged | N10 fail closed test 3/7 |
| CAP-11 | NFR-004 Observability Available | Correlation label AC-21 + JSON report A-1. S-FND-02 log hooks ile uyumlu. | N04 helpers report builder, AC-21 |
| CAP-12 | NFR-006 Integrity Immutable Provenance | Scan id hash deterministic, 10x aynı (D-4). Findings tuple key dedup (FC-8) duplicate result yoktur — integrity. | N10 determinism D-4, FC-8 test |
| CAP-13 | NFR-007 Reproducibility Determinism | §7 D1-D6 Determinism 6 grup × 10x len(set)==1; sorted paths, explicit AST sıra, sort_keys JSON. | N10 determinism test 6 senaryo |
| CAP-14 | NFR-008 Security v1 No Credentials | HR-3 mask output, HR-5 stdlib only, HR-2 no live network own code, HR-4 no registry mutation. | §12 hard-red 8/8 |
| CAP-15 | (Ekstra NFR) — Marker Stability Contract | Downstream 10+ hikâye markerları kullanır → marker isimleri (contract/replay/failure_injection) SABİT, rename ancak OD-01 ile. | N01 pytest.ini, N05 marker catalog enum stable |

---

## Hikâyeler arası bağlantı (Upstream / Downstream)
```
UPSTREAM (completed, immutable):
    E-API MVP @ 80933f8
        └──► S-FND-01 Env @ e1bdff7 ──► pytest root conftest offline blocker  (MODIFY 0 — HR-1)
            └──► S-FND-02 Observability @ d02f58b ──► correlation + masking (OPTIONAL reuse AC-21)
                    └──► *S-FND-03 (PREP)*
                            │
                            ▼
DOWNSTREAM (tüketiciler, marker + pr-gate ihtiyacı):
    S-CON-01 / S-CON-02 ──► @pytest.mark.contract
    S-FEA-01 / S-REG-01 ──► replay + failure_injection marker
    S-RSK-01/02 / S-PTR-01 ► failure_injection + contract
    S-BKT-01/02/03         ► @pytest.mark.replay (REPLAY bağımlılığı)
    S-RDH-01/02            ► failure_injection
```

---
scope: E-API Epic 14 Reuse Map (Dependencies / Upstream / Downstream)
created: 2026-09-19
updated: 2026-09-19
---

# Reuse Map

## Yukarı Akış (E-API kullanan bağımlı old. upstream — bunlar bitmeden E-API starts)
1. **S-CON-04** (Forbidden routes + lifecycle schema initial gate setup) [EPICS L298-L308](file:///c:/Users/Baran/OneDrive/Desktop/crypto-ai-trader/_bmad-output/implementation-artifacts/epics-crypto-ai-trader-mvp-2026-08-10/EPICS.md#L298)
2. **E-RSK-04 / S-RSK-02 kill/emergency gateway interface** — E-API YALNIZCA bunu CALL eder; direct mutate 0.
3. **S-PLN-01 EventBus (Typed + correlation ULID)** — AD-17 correlation + audit event yazımı
4. **S-MDL-01..05 Read-Only registry exposure** — models/* GET endpointleri için read model single-writer

## Aşağı Akış (E-API'yi tüketen downstream)
1. Dashboard SPA (operatör UI; FR-057..060 surface)
2. Prometheus scraper + Alertmanager (S-API-04 metrics)
3. Operatör audit viewer (POST 2 audit event)

## Boundary Sınırları (Zero-leak)
- Domain modülleri (features, strategies, regime, opportunity, risk-engine, portfolio, paper, backtest, model-lifecycle) → E-API YALNIZCA READ. 2 POST YALNIZCA Risk Engine gateway call. Hiçbir domain contract dosyası E-API tarafından değiştirilmez.
- 15 companion OOS pattern onay: ❌ E-API OOS existing hikâyelerde yazılmış.

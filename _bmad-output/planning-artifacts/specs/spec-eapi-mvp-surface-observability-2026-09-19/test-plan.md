---
scope: E-API Epic 14 Test Plan (FUTURE-PHASE) — N1 + N2 dahil
created: 2026-09-19
updated: 2026-09-19
---

# Test Plan — E-API

## Genel Setup
Fixture: FastAPI TestClient; 5 yeni dosya `tests/api/*`; existing conftest.py S-MDL event bus + risk engine mock gateway (gerçek production call YOK, test doubles ile çalışır).

## T1 — S-API-01 10 GET Groups (routes_system..routes_logs) × Schema Contract
- T1.1: 10 grup başına 1 smoke 200 ok=true + correlation_id ULID
- T1.2: Envelope format (4 field L17)
- T1.3: Invalid path /api/v2 → 404 (path prefix enforcement)

## T2 — N1 (POST Body / Semantics — Idempotency + Double Confirm) [MAJOR N1 resolved here]
### T2.1 `/system/emergency-stop` idempotency_key validation
- T2.1a: Eksik `idempotency_key` → 400 INVALID_IDEMPOTENCY_KEY; gateway counter = 0; audit failed_attempt
- T2.1b: Non-ULID format `idempotency_key = "not-a-ulid-123"` → 400 same error
### T2.2 `/system/emergency-stop` double_confirm_token validation (AD-16)
- T2.2a: Eksik `double_confirm_token` → 403 INSUFFICIENT_CONFIRMATION
- T2.2b: Non-ULID format confirm → 403
- T2.2c: Valid confirm ama auth scope mismatch (RISK scope bir token ile EMERGENCY route) → 403
### T2.3 2 POST Idempotency Replay (AC-05)
- T2.3a: Same idempotency_key 2x call → response byte karşılaştırma AYNI; gateway counter=1; main audit row count=1; duplicate info row=1
### T2.4 `/risk/kill-switch` body scope + idempotency + confirm integration same pattern
- T2.4a: Body `{scope: global, enabled: true, ... idempotency, confirm}` → success + audit fields complete
- T2.4b: Kill POST → registry ModelVersion UPDATE counter = 0 (AD-14 single owner boundary)

## T3 — CAP-6 Forbidden Surface (S-API-03) [ANA PROOF — EPICS L477]
- T3.1 Runtime registry scan: 4 pattern count = 0
- T3.2 Static AST scan (Python AST + route string): 4 pattern = 0
- T3.3 OpenAPI generated JSON scan: 4 pattern path = 0
- T3.4 Path variant scan (case / underscore / prefix v2 / traversal): 4 pattern variant coverage = 0 occurrence LOW explicit yazılmıyor ama testte ek assertion YAPILMAZ (LOW gap kalır).
- T3.5 Ek `/admin/retire-champion` 5. yasak = 0.

## T4 — S-API-04 Observability / Prometheus
- T4.1 `/metrics` 200 Prometheus format parse
- T4.2 Credential label scan regex "secret|key|password|token" (exclude `idempotency_key`/`double_confirm_token` olan = audit row field ama metric label HAYIR) → 0 match
- T4.3 10+ metric family (counter/gauge) smoke
- T4.4 First alert rules YAML load success → 10+ rule

## T5 — N2 (Localhost ONLY artık normative YOK)
- T5.1: TEST CODE içinde HARD ASSERT "bind address MUST be 127.0.0.1" YOKTUR. (N2 düzeltmesi — böyle bir satır varsa FAIL)
- T5.2: HARD-RED içinde NORMATİF: **Outbound internet non-loopback call block** assertion VAR ve çalışır (mock socket public IP → FAIL).
- T5.3: Deployment listener = OD-01 non-binding; test sadece "default development loopback" bind üzerinden çalışır ama AC zorunlu DEĞİL.

## T6 — Current Scope Preservation (Regression)
- T6.1 S-MDL-01..05 17 domain modüllerinin (S-MDL contracts dosyaları) sha256sum: E-API impl sonrası değişmemiş.
- T6.2 Existing tests full suite (S-MDL..cap5) regression PASS (0 fail).

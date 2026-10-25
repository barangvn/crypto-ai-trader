---
artifact: acceptance-criteria
story: S-FND-02
status: spec-only
---
# S-FND-02 Acceptance Criteria (24 AC)

Measurable, reproducible. All 24 AC: Pass/Fail binary. 0 partial.

| ID | Title | Metric | Pass when | Source binding |
|---|---|---|---|---|
| AC-01 | Log line has 11 mandatory fields | 100 random rows checked | 11/11 present every row, 0 missing | SPEC 6.1 |
| AC-02 | Schema version constant | All log records | schema_version == "sfnd02/v1" | SPEC 6.1 |
| AC-03 | JSON serialization deterministic | 10× serialize identical input | 10/10 byte identical | SPEC 6.4 / D2 |
| AC-04 | log_id deterministic | 10× identical input | 10× same log_id value | SPEC 6.1 / D1 |
| AC-05 | Env value from S-FND-01 EnvConfig | 4 env test runs | env in {dev,test,stg,paper-prod} | SPEC 6.1 / S-FND-01 baseline |
| AC-06 | run_mode valid | All logs | run_mode in {replay, mock, readonly-live, live, NO_MODE} | AD-4 / SPEC 6.1 |
| AC-07 | msg truncation for oversize | Inject 5000-char msg | len(msg field) ≤ 4096 AND _msg_truncated label present AND line not dropped | FC-03 |
| AC-08 | Labels cap 20 keys | Inject 25 labels | 20 preserved; dropped_counter +1; line written; no exception | FC-06 |
| AC-09 | New root correlation causation=ROOT | new_root() | causation_id == "ROOT" | SPEC 6.3 |
| AC-10 | from_envelope copies AD-3 fields | build envelope with correlation_id X and event_id Y | ctx.correlation_id=X AND ctx.causation_id=Y | AD-3 / SPEC 6.3 |
| AC-11 | child() preserves correlation_id | ctx.child(CAUSE2) | new correlation_id same; causation_id=CAUSE2 | SPEC 6.3 |
| AC-12 | as_labels() 2-key dict | all contexts | keys == {"correlation_id","causation_id"}; values str | SPEC 6.3 |
| AC-13 | Serialize failure call-site safe | Inject unserializable set() value | No exception raised at caller; dropped counter increments | FC-04 / M3 |
| AC-14 | NaN/Inf histogram observe no exception | 4 invalid values in, 4 valid out | 0 call-site exceptions; dropped=4 | FC-07 |
| AC-15 | Invalid level promotes to ERROR | Level="UNKNOWN!!" | written level=ERROR and label _invalid_level=1 | FC-02 |
| AC-16 | Init failure → NullSink fallback | Import broken module via mock | factory falls back; 0 exception; logger_init_fallback flag true | FC-01 |
| AC-17 | Oversize msg never dropped | Force 4096+15 chars | output line exists; truncation applied | FC-03 |
| AC-18 | AUDIT tagged row never fully dropped | Oversize + invalid level + serialize fault | AUDIT row persists in sink; truncated/labels only | S5 / SPEC 9 |
| AC-19 | Masking on sensitive key/value/patterns | 8 positive inputs | 8 outputs start with "REDACTED:" + 12 hex chars | M5 / SPEC 8 FC-10 |
| AC-20 | 0 NEW S-FND-01 F2 false positives after install | Run test_f2_no_credentials suite | 60 PASS / 1 SKIP / 0 FAIL / no new matches | B1 preserved / S-FND-01 |
| AC-21 | Metrics interface has Counter/Hist/Gauge + correlation provider | Interface ABC subclassing test | all 3 methods and set_correlation_provider exist; 0 missing | SPEC 6.2 |
| AC-22 | Histogram default buckets 12 ordered correctly | Bucket tuple inspected | tuple == (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, inf) | SPEC 6.2 / D3 |
| AC-23 | 3 built-in log sinks + 3 built-in metric sinks importable | import + instantiate each one | 6 types created with no error | SPEC 3 / 3. IN |
| AC-24 | InMemoryCaptureSink captures chain correctly | 5 chained calls | 5 rows, 11 fields all present, correlation_id identical in 5 | SPEC 10 / M2 |

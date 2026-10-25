---
artifact: test-plan
story: S-FND-02
status: spec-only
---
# S-FND-02 Test Plan

4 layers: Unit contract → regression (S-FND-01 F2) → Integration/determinism → Hardred boundary / stdlib-only

## TP-1 Unit / Contract tests
File: `tests/foundation/test_sfnd02_contracts.py` (~24 test, 1:1 AC-01..24)

| ID | Test | Asserts |
|---|---|---|
| T-01 | `test_log_schema_11_mandatory` | AC-01 |
| T-02 | `test_log_schema_version_constant` | AC-02 |
| T-03 | `test_serialization_deterministic_10x` | AC-03 |
| T-04 | `test_log_id_stable_on_same_fields` | AC-04 |
| T-05 | `test_log_env_matches_sfnd01_EnvConfig` | AC-05 |
| T-06 | `test_log_run_mode_enum_values_valid` | AC-06 |
| T-07 | `test_msg_oversize_truncation_preserves_row` | AC-07 |
| T-08 | `test_labels_21_keys_caps_dropped_5_preserved` | AC-08 |
| T-09 | `test_correlation_root_has_root_causation` | AC-09 |
| T-10 | `test_from_envelope_ad3_fields` | AC-10 |
| T-11 | `test_child_preserves_correlation_updates_causation` | AC-11 |
| T-12 | `test_as_labels_two_keys_str_values` | AC-12 |
| T-13 | `test_serialize_unserializable_value_no_caller_exception` | AC-13 |
| T-14 | `test_histogram_nan_inf_no_caller_exception` | AC-14 |
| T-15 | `test_invalid_level_upgrades_error_label` | AC-15 |
| T-16 | `test_factory_init_failure_fallback_nullsink` | AC-16 |
| T-17 | `test_oversize_msg_5000_not_dropped` | AC-17 |
| T-18 | `test_audit_tag_never_full_dropped_under_3_faults` | AC-18 |
| T-19 | `test_masking_positive_8_cases_sha_prefix` | AC-19 |
| T-20 | `test_f2_sfnd01_compatibility_no_new_hits` | AC-20 |
| T-21 | `test_metrics_interface_compliance_3_types_provider` | AC-21 |
| T-22 | `test_histogram_default_buckets_12_ordered` | AC-22 |
| T-23 | `test_builtin_sinks_3_log_3_metric_import` | AC-23 |
| T-24 | `test_inmemorycapture_chain_5_linked` | AC-24 |

## TP-2 S-FND-01 F2 Compatibility / regression
Run:
```
pytest tests/failure/test_f2_no_credentials.py tests/failure/test_no_credentials.py tests/failure/test_bus_no_credentials.py tests/failure/test_registry_no_credentials.py -q
```
Expected: B1 = RESOLVED preserved; 0 NEW S-FND-02-induced credential hits.

## TP-3 Integration / determinism
File: `tests/foundation/test_sfnd02_determinism.py`
- `test_log_id_hash_10x_unique_len_1`
- `test_json_serialize_10x_byte_equal`
- `test_bucket_tuple_idempotent_10x`
- `test_correlation_provider_deterministic_seed_10x`
- `test_level_numeric_map_stable_10x`
- `test_counter_identity_same_labels_10x`

File: `tests/foundation/test_sfnd02_failsafe.py`
- FC-01..FC-10 failover scenarios 10 test

File: `tests/foundation/test_sfnd02_masking.py`
- 8 positive sensitive-value / 2 negative normal-value / 1 JWT-prefix / 1 prefix-key sk (REDACTED rules)

## TP-4 Hardred / stdlib-only boundary
- Marker: reuse S-FND-01 F4 (stdlib-only). All TP1 unit tests tagged F4.
- `pytest tests/foundation -m stdlib-only` or direct collection hook.
- `import ast` scan in test: for all `app/platform/observability/*.py` verify NO non-stdlib non-local imports (stdlib + pytest + typing/dataclasses/hashlib/json/abc — allowed).

## TP-x Counts (expected)
- ~ 24 TP1 + 6 determinism + 10 fail-safe + 11 masking = 51 new unit tests in tests/foundation.
- Regression: 60 PASS / 1 SKIP S-FND-01 tests preserved.

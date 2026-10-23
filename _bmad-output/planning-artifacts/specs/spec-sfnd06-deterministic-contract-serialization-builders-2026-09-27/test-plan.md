# Test Plan — S-FND-06 (TP-01..14)

Test dizin `tests/foundation_sfnd06/` (yeni, izole). Her TP = 1 veya daha fazla test dosyası.

| TP # | Test Amacı | Test Dosyası (expected) | Test Kategorileri | AC Kapladığı |
|---|---|---|---|---|
| TP-01 | Import + public API 18 isim listesi (17 fonksiyon + 1 exception) + `__all__` doğruluğu | `test_sfnd06_imports_public_api.py` | Unit, smoke | AC-01 |
| TP-02 | Canonical JSON determinism 10x + fingerprint + sort_keys shuffled | `test_sfnd06_canonical_json_stable.py` | Unit, Determinism | AC-03/04/05 |
| TP-03 | Decimal→str, datetime reject, circular ref fail-closed | `test_sfnd06_json_types_failclosed.py` | Unit, Negatif | AC-06/07, FC-09/10 |
| TP-04 | Symbol canonical strict accept & invalid raise (HTML/SQL/path geçmişi) | `test_sfnd06_symbol_canonical_gate.py` | Unit, Security (HR-13) | AC-08/09/10, HR-13, FC-13 |
| TP-05 | Instant validate Z-suffix + offset raise + fractional 1-6 + fixture | `test_sfnd06_instant_validate_fixture.py` | Unit, Contract | AC-11/12/13, FC-14 |
| TP-06 | Envelope builder defaults + partial override + empty event_type fail | `test_sfnd06_build_valid_envelope.py` | Unit, Integration (uses S-FND-05) | AC-14/15, FC-11 |
| TP-07 | Quality builders: degraded auto, manual override HR-12 **default safety raise (non-binding future optional classification)**, reason append idempotent, code validation | `test_sfnd06_quality_builders.py` | Unit, Invariant, HR | AC-16/17, FC-12/16, HR-12 |
| TP-08 | ULID validate + compare sort + UUID7 format support | `test_sfnd06_ulid_sortable.py` | Unit, Determinism | AC-18 |
| TP-09 | Version literals alignment 1.0.0 / schema_ref contracts_md exact | `test_sfnd06_version_alignment.py` | Unit, Contract | AC-02/19 |
| TP-10 | 7 Determinism ölçümü 10x loop → set len 1 audit | `test_sfnd06_determinism_audit_10x.py` | Audit, Determinism | D-01..07 |
| TP-11 | HRC 13: 8 proje genel + 5 hikâye özel forbidden-pattern scan new prod 6 files | `test_sfnd06_hrc_sanity.py` | Hard-Red, Safety | HR-01..13 |
| TP-12 | Parity Branch Tarayıcı: `if run_mode` / `if source_type` / manual time.now() AST scan new production 6 → 0 match | `test_sfnd06_parity_static_ast.py` | CAP-1, Static, Safety | SEC-06, HR-11 |
| TP-13 | Regex Tek Kaynak Doğrulama: SYMBOL/INSTANT/ULID regex sabitleri → S-FND-05 public API'de varsa import edilir, yoksa bu hikâyedeki kopya ile string karşılaştırması (%100 aynı) | `test_sfnd06_regex_single_source.py` | DRY, Contract | AUD-03 |
| TP-14 (REG) | **Upstream regression:** S-FND-05 test suite changesiz (`tests/foundation_sfnd05/`) + S-FND-04 + foundation tests (S-FND-02/03) + contracts tests + E-API tests → exit 0 new FAIL | Run via `pytest tests/foundation_sfnd05 tests/foundation_sfnd04 tests/foundation tests/contracts tests/api -q` | Regression | AC-20 |

### Çalıştırma Komutları (Implementation Phase, test aşaması)

```powershell
# 1. Smoke + unit (fast first)
pytest tests/foundation_sfnd06/test_sfnd06_imports_public_api.py tests/foundation_sfnd06/test_sfnd06_version_alignment.py -q

# 2. Determinism + security HRC block
pytest tests/foundation_sfnd06 -k "determinism or hrc or parity_static" -v

# 3. Full 14 suites
pytest tests/foundation_sfnd06/ -v

# 4. Regression (completed stories):
pytest tests/foundation_sfnd05/ tests/foundation_sfnd04/ tests/foundation/ tests/contracts/ tests/api/ tests/failure/ -q
```

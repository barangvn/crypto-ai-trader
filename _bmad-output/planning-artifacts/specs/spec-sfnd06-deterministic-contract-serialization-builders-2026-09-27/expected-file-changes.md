# Expected File Changes — S-FND-06

## GENEL KURAL: Existing tracked file modification = 0 (DEFAULT). EX İSTİSNA LİSTESİ = BOŞ.
Hiçbir completed-story dosyası (S-FND-01..05, E-API, S-MDL-01..05, pyproject.toml, pytest.ini, 4 env INI, tests/conftest.py, tests/foundation*, tests/api*, tests/contracts*, tests/failure*) DEĞİŞTİRİLMEZ.

**EXCEPTION LIST (EX):** BOŞ. Existing modify = 0.

---

## NEW Production Files (under `app/contracts/` + `app/platform/` ??? → Default: `app/contracts/` domain — contracts owned. Toplam 6 Yeni.)

| # | Absolute Yeni Dosya Yolu | İçerik / Sorumluluk | Tür | Gerekçe (SPEC ref) |
|---|---|---|---|---|
| P01 | `app/contracts/sfnd06_serialize.py` | **ANA PUBLIC API:** 17 fonksiyon + 1 exception class (`CanonicalSerializationError`) = 18 export. §6.1 Signature sözleşmesi burada yaşar. `__all__` 18 isim export. Diğer tüm yardımcıları iç modülden import eder. | PROD | SPEC §1-2-3; public import path UP-01 |
| P02 | `app/contracts/_sfnd06_constants.py` | Shared regex constants (SYMBOL_RGX, INSTANT_RGX, ULID_CROCKFORD_RGX, UUID7_RGX, EVENT_TYPE_RGX) — S-FND-05 public API'den import edilebilirse import; edilemezse kopya (aynı string). Tek kaynak; diğer modüller buradan import eder. | PROD (Internal, underscore prefix: private) | SPEC §6.2 Shared reuse, AUD-03 regex tek kaynak |
| P03 | `app/contracts/_sfnd06_json.py` | `canonical_json`, `canonical_loads`, `canonical_json_equal` implementasyonu. stdlib `json`, `decimal`, `dataclasses` kullanır. 3p yok. sort_keys + compact separator + Decimal→str custom default(o). Circular ref detection. | PROD (Internal) | CAP-SER-01/08, FC-09/10, HR-09 |
| P04 | `app/contracts/_sfnd06_fingerprint.py` | `envelope_fingerprint`, `payload_fingerprint` — stdlib `hashlib.sha256`. 12 hex lowercase prefix. | PROD (Internal) | CAP-SER-02, HR-10 |
| P05 | `app/contracts/_sfnd06_builders.py` | `build_valid_envelope`, `build_quality`, `append_quality_reason`, `set_quality_flag` builders. S-FND-05 frozen dataclassları new instance ile döner (frozen immutable workaround). Degrade manual override raise (default safety / non-binding future optional classification). | PROD (Internal) | CAP-SER-05/06, FC-11/12/16, HR-12 |
| P06 | `app/contracts/_sfnd06_helpers.py` | Symbol canonicalizer (`canonical_symbol`, `is_canonical_symbol`), Instant helpers (`validate_instant`, `now_instant_utc_fixture` — fixture only), ULID helpers (`validate_ulid_sortable`, `ulid_compare`, ulid_newer/older). | PROD (Internal) | CAP-SER-03/04/07, FC-13/14, HR-11/13 |

**Default Production new count: 6. (1 public API modül + 5 internal yardımcı modül)**

---

## NEW Test Files (under `tests/foundation_sfnd06/`)

| T # | Dosya | İçerik (test-plan.md TP ref) | Tür |
|---|---|---|---|
| T01 | `tests/foundation_sfnd06/__init__.py` | Allowlist marker (empty 0 line). Allowlist count. | TEST |
| T02 | `tests/foundation_sfnd06/conftest.py` | Fixtures: `sample_valid_env_fixture()`, `sample_shuffled_dict()`, `sample_instant_strings()`, `clean_no_now_mock` (monkeypatch datetime.now block for HR-11). | TEST |
| T03 | `tests/foundation_sfnd06/_helpers.py` | Shared helpers: `sha_sorted_json()`, `scan_new_prod_3rd_party_imports()` (stdlib 18 modules allowlist). | TEST (helper) |
| T04 | `tests/foundation_sfnd06/test_sfnd06_imports_public_api.py` | TP-01 → imports + `__all__` count =18 (17 fonksiyon + 1 exception). | TEST |
| T05 | `tests/foundation_sfnd06/test_sfnd06_canonical_json_stable.py` | TP-02 → determinism 10x + shuffled key sort. | TEST |
| T06 | `tests/foundation_sfnd06/test_sfnd06_json_types_failclosed.py` | TP-03 → Decimal/circular/datetime. | TEST |
| T07 | `tests/foundation_sfnd06/test_sfnd06_symbol_canonical_gate.py` | TP-04 → strict gate + no sanitize HR-13. | TEST |
| T08 | `tests/foundation_sfnd06/test_sfnd06_instant_validate_fixture.py` | TP-05 → UTC Z / offset fail. | TEST |
| T09 | `tests/foundation_sfnd06/test_sfnd06_build_valid_envelope.py` | TP-06 → builder defaults + empty event_type fail. | TEST |
| T10 | `tests/foundation_sfnd06/test_sfnd06_quality_builders.py` | TP-07 → degraded invariant, manual override HR-12. | TEST |
| T11 | `tests/foundation_sfnd06/test_sfnd06_ulid_sortable.py` | TP-08 → ULID sortable compare. | TEST |
| T12 | `tests/foundation_sfnd06/test_sfnd06_version_alignment.py` | TP-09 → 1.0.0 literals exact | TEST |
| T13 | `tests/foundation_sfnd06/test_sfnd06_determinism_audit_10x.py` | TP-10 → D-01..07 audit 10x | TEST |
| T14 | `tests/foundation_sfnd06/test_sfnd06_hrc_sanity.py` | TP-11 → HRC 13 scan | TEST |
| T15 | `tests/foundation_sfnd06/test_sfnd06_parity_static_ast.py` | TP-12 → AST static scan no branch | TEST |
| T16 | `tests/foundation_sfnd06/test_sfnd06_regex_single_source.py` | TP-13 → regex tek kaynak doğrula | TEST |

**Test default count: 16 new (1 __init__, 1 conftest, 1 _helpers, 13 test_ modules).**

---

## Toplam Önerilen Allowlist

- Production new: **6**
- Test new: **16**
- **Toplam new: 22 dosya**
- Existing modified: **0 satır / 0 dosya**
- SPEC dışı artifact exclude: pickle, msgpack, proto, orjson, yaml, debug temp .memlog outside spec folder, network fixtures.

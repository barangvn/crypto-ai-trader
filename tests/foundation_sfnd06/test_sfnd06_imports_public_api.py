"""TP-01 / AC-01 — public API import surface & `__all__` correctness."""

from __future__ import annotations

import app.contracts.sfnd06_serialize as api


# AC-01: the 9 names that MUST be importable from the public path.
AC01_IMPORT_NAMES = (
    "canonical_json",
    "envelope_fingerprint",
    "canonical_symbol",
    "validate_instant",
    "build_valid_envelope",
    "build_quality",
    "append_quality_reason",
    "ulid_compare",
    "CanonicalSerializationError",
)

# Exact public API surface defined by SPEC §6.1 signature BODY
# (17 functions + 1 exception class = 18 names). See D-06-A documentation note:
# the SPEC §6.1 heading / P01 / DoD#8 / TP-01 say "13", but the §6.1 body
# explicitly defines 17 functions + 1 exception. Per "no invent behavior" the
# full §6.1 body is implemented; no name is dropped or invented.
EXPECTED_PUBLIC_API = frozenset(
    {
        "CanonicalSerializationError",
        "canonical_json",
        "canonical_loads",
        "canonical_json_equal",
        "envelope_fingerprint",
        "payload_fingerprint",
        "canonical_symbol",
        "is_canonical_symbol",
        "validate_instant",
        "now_instant_utc_fixture",
        "build_valid_envelope",
        "build_quality",
        "append_quality_reason",
        "set_quality_flag",
        "validate_ulid_sortable",
        "ulid_compare",
        "ulid_newer",
        "ulid_older",
    }
)


def test_ac01_public_import_names_available():
    for name in AC01_IMPORT_NAMES:
        assert hasattr(api, name), f"missing public name: {name}"


def test_ac01_exception_is_valueerror_subclass():
    assert issubclass(api.CanonicalSerializationError, ValueError)


def test_all_matches_spec_6_1_body_exactly():
    assert frozenset(api.__all__) == EXPECTED_PUBLIC_API
    # 18 == 17 functions + 1 exception class (SPEC §6.1 body).
    assert len(api.__all__) == 18
    assert len(set(api.__all__)) == len(api.__all__), "__all__ has duplicates"


def test_every_export_is_importable_attribute():
    for name in api.__all__:
        assert getattr(api, name) is not None


def test_public_module_has_no_logic_of_its_own():
    # The public module is a pure re-export aggregator: its own source must not
    # define new functions/classes (only imports + __all__).
    import ast
    from pathlib import Path

    src = Path(api.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    defined = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    assert defined == []

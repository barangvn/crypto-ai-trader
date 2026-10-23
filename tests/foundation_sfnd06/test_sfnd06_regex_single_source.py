"""TP-13 / AUD-03 — regex single source: no third source of truth.

OD-06-08 two-sequence strategy: S-FND-05's public API does not export the raw
regex constants, so this story keeps its OWN single-source copy in
`app/contracts/_sfnd06_constants.py` with IDENTICAL string values to the
canonical S-FND-05 source (`app/contracts/_validation.py`). This test proves the
values are byte-identical (zero drift) and that no other new module redefines them.
"""

from __future__ import annotations

import app.contracts._sfnd06_constants as C
import app.contracts._validation as V
import pytest
from tests.foundation_sfnd06._helpers import new_prod_paths

IDENTICAL_VALUE_PAIRS = [
    (C.INSTANT_RGX_STR, V.INSTANT_RGX_STR, "INSTANT_RGX_STR"),
    (C.SYMBOL_RGX_STR, V.SYMBOL_RGX_STR, "SYMBOL_RGX_STR"),
    (C.EVENT_TYPE_RGX_STR, V.EVENT_TYPE_RGX_STR, "EVENT_TYPE_RGX_STR"),
    (C.ULID_CROCKFORD_RGX_STR, V.ULID_CROCKFORD_RGX_STR, "ULID_CROCKFORD_RGX_STR"),
    (C.UUID7_RGX_STR, V.UUID7_RGX_STR, "UUID7_RGX_STR"),
    (C.CONTRACT_VERSION_STR, V.CONTRACT_VERSION_STR, "CONTRACT_VERSION_STR"),
    (C.SCHEMA_REF_CONTRACTS_MD, V.SCHEMA_REF_CONTRACTS_MD, "SCHEMA_REF_CONTRACTS_MD"),
    (C.QUALITY_CODE_MAX, V.QUALITY_CODE_MAX, "QUALITY_CODE_MAX"),
    (C.QUALITY_MESSAGE_MAX, V.QUALITY_MESSAGE_MAX, "QUALITY_MESSAGE_MAX"),
]


@pytest.mark.parametrize("ours,canonical,name", IDENTICAL_VALUE_PAIRS)
def test_aud03_constants_identical_to_sfnd05_source(ours, canonical, name):
    assert ours == canonical, f"{name} drift between S-FND-06 copy and S-FND-05 source"


def test_aud03_compiled_patterns_equivalent():
    assert C.INSTANT_RGX.pattern == V.INSTANT_RGX.pattern
    assert C.SYMBOL_RGX.pattern == V.SYMBOL_RGX.pattern
    assert C.EVENT_TYPE_RGX.pattern == V.EVENT_TYPE_RGX.pattern
    assert C.ULID_CROCKFORD_RGX.pattern == V.ULID_CROCKFORD_RGX.pattern
    assert C.UUID7_RGX.pattern == V.UUID7_RGX.pattern


def test_aud03_no_other_new_module_redefines_regex_literals():
    literals = [
        C.INSTANT_RGX_STR,
        C.SYMBOL_RGX_STR,
        C.EVENT_TYPE_RGX_STR,
        C.ULID_CROCKFORD_RGX_STR,
        C.UUID7_RGX_STR,
    ]
    for path in new_prod_paths():
        if path.name == "_sfnd06_constants.py":
            continue
        source = path.read_text(encoding="utf-8")
        for literal in literals:
            assert literal not in source, (
                f"{path.name} re-defines a regex literal; must import single source"
            )


def test_od0608_public_api_does_not_export_raw_regex():
    # Documents the reason for the story-local single-source copy (two-sequence
    # strategy). If upstream ever exports it, the import strategy should switch.
    import app.contracts.sfnd05_api as api

    assert not hasattr(api, "SYMBOL_RGX_STR")
    assert not hasattr(api, "INSTANT_RGX_STR")

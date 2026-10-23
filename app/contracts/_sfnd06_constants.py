"""S-FND-06 single-source constants (regex + integrity limits).

OD-06-08 two-sequence strategy (DEFAULT):
  1) Prefer importing the regex constants from the S-FND-05 public API path
     (`app.contracts.sfnd05_api`).
  2) The S-FND-05 public API does NOT export the raw regex constants, therefore
     this story keeps its OWN single-source copy in this module with IDENTICAL
     string values.

K0 / HR-08: the S-FND-05 files (in particular `_validation.py`) are NEVER
modified. This module exists precisely so S-FND-06 has a single source of truth
without touching any completed-story file.
"""

from __future__ import annotations

import re


INSTANT_RGX_STR = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$"
INSTANT_RGX = re.compile(INSTANT_RGX_STR)

SYMBOL_RGX_STR = r"^[A-Z0-9]{2,20}_[A-Z0-9]{2,12}$"
SYMBOL_RGX = re.compile(SYMBOL_RGX_STR)

EVENT_TYPE_RGX_STR = r"^[a-z_]+\.v[0-9]+$"
EVENT_TYPE_RGX = re.compile(EVENT_TYPE_RGX_STR)

ULID_CROCKFORD_RGX_STR = r"^[0-9A-HJKMNP-TV-Z]{26}$"
ULID_CROCKFORD_RGX = re.compile(ULID_CROCKFORD_RGX_STR)

UUID7_RGX_STR = (
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
UUID7_RGX = re.compile(UUID7_RGX_STR)

CONTRACT_VERSION_STR = "1.0.0"
SCHEMA_REF_CONTRACTS_MD = "CONTRACTS.md@1.0.0"

QUALITY_CODE_MAX = 64
QUALITY_MESSAGE_MAX = 512

__all__ = [
    "INSTANT_RGX_STR",
    "INSTANT_RGX",
    "SYMBOL_RGX_STR",
    "SYMBOL_RGX",
    "EVENT_TYPE_RGX_STR",
    "EVENT_TYPE_RGX",
    "ULID_CROCKFORD_RGX_STR",
    "ULID_CROCKFORD_RGX",
    "UUID7_RGX_STR",
    "UUID7_RGX",
    "CONTRACT_VERSION_STR",
    "SCHEMA_REF_CONTRACTS_MD",
    "QUALITY_CODE_MAX",
    "QUALITY_MESSAGE_MAX",
]

"""TP-08 / AC-18 — ULID sortable validate + compare + UUIDv7 support (GAP-06-06)."""

from __future__ import annotations

import functools

import pytest

from app.contracts.sfnd06_serialize import (
    ulid_compare,
    ulid_newer,
    ulid_older,
    validate_ulid_sortable,
)

OLDER = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
NEWER = "01ARZ3NDEKTSV4RRFFQ69G5FB2"
UUID7_A = "01926bfb-4f4b-78a9-8f3b-0a2c3d4e5f6a"
UUID7_B = "01926bfb-4f4b-78a9-8f3b-0a2c3d4e5f6b"


def test_ac18_ulid_compare_signs():
    assert ulid_compare(OLDER, NEWER) == -1
    assert ulid_compare(NEWER, OLDER) == 1
    assert ulid_compare(OLDER, OLDER) == 0


def test_ac18_sort_matches_lexicographic_order():
    ordered = sorted([NEWER, OLDER], key=functools.cmp_to_key(ulid_compare))
    assert ordered == [OLDER, NEWER]


def test_ulid_newer_older_helpers():
    assert ulid_newer(NEWER, OLDER) is True
    assert ulid_newer(OLDER, NEWER) is False
    assert ulid_older(OLDER, NEWER) is True
    assert ulid_older(NEWER, OLDER) is False


@pytest.mark.parametrize("value", [OLDER, NEWER, UUID7_A])
def test_validate_ulid_sortable_accepts_ulid_and_uuid7(value):
    assert validate_ulid_sortable(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-a-ulid",
        "01ARZ3NDEKTSV4RRFFQ69G5FA",  # 25 chars
        "01ARZ3NDEKTSV4RRFFQ69G5FAVX",  # 27 chars
        "01arz3ndektsv4rrffq69g5fav",  # lowercase not accepted
        "01ARZ3NDEKTSV4RRFFQ69G5FAI",  # I not in Crockford
    ],
)
def test_validate_ulid_sortable_rejects_invalid(value):
    with pytest.raises(ValueError):
        validate_ulid_sortable(value)


def test_ulid_compare_validates_arguments():
    with pytest.raises(ValueError):
        ulid_compare(OLDER, "bad")


def test_gap0606_uuid7_is_sortable():
    assert ulid_compare(UUID7_A, UUID7_B) == -1
    assert ulid_compare(UUID7_B, UUID7_A) == 1


def test_gap0606_cross_format_compare_raises_typeerror():
    with pytest.raises(TypeError):
        ulid_compare(OLDER, UUID7_A)

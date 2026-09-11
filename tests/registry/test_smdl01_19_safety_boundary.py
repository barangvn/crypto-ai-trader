from __future__ import annotations

import pathlib
import re

import pytest


REGISTRY_ROOT = pathlib.Path("app/registry")

SAFETY_TOKENS = [
    "api_key",
    "secret_key",
    "access_token",
    "place_order",
    "send_order",
    "submit_order",
    "futures",
    "ccxt",
    "leverage",
    "short",
    "live",
    "trading",
    "real_order",
    "execute_order",
]

LEVERAGE_LITERAL_RE = re.compile(r"leverage_allowed\s*[>=]+\s*[2-9]")


def _registry_files() -> list[pathlib.Path]:
    return sorted(p for p in REGISTRY_ROOT.rglob("*.py") if p.is_file())


def _strip_strings_and_comments(line: str) -> str:
    clean = re.sub(r"#.*$", "", line)
    clean = re.sub(r"('''.*?'''|\"\"\".*?\"\"\"|'.*?'|\".*?\")", "", clean, flags=re.S)
    return clean


def test_smdl01_19_all_11_safety_tokens_zero_count_regex_scan():
    per_token_counts: dict[str, list[tuple[str, int, str]]] = {t: [] for t in SAFETY_TOKENS}
    lev_literal_hits: list[tuple[str, int, str]] = []

    for f in _registry_files():
        lines = f.read_text(encoding="utf-8").splitlines()
        for lineno, raw_line in enumerate(lines, 1):
            clean = _strip_strings_and_comments(raw_line)
            clean_lower = clean.lower()
            for tok in SAFETY_TOKENS:
                pattern = re.compile(r"\b" + re.escape(tok.lower()) + r"\b")
                if pattern.search(clean_lower):
                    per_token_counts[tok].append((str(f), lineno, raw_line.strip()))
            if LEVERAGE_LITERAL_RE.search(clean):
                lev_literal_hits.append((str(f), lineno, raw_line.strip()))

    summary = {k: len(v) for k, v in per_token_counts.items()}
    summary["leverage_allowed_gt_1_literal"] = len(lev_literal_hits)

    all_zero = all(v == 0 for v in summary.values())
    assert all_zero, f"Safety boundary violation counts: {summary!r}"


def test_smdl01_19_each_token_individually_zero():
    files = _registry_files()
    all_source = "\n".join(
        _strip_strings_and_comments(line)
        for f in files
        for line in f.read_text(encoding="utf-8").splitlines()
    )
    all_source_lower = all_source.lower()

    for tok in SAFETY_TOKENS:
        pattern = re.compile(r"\b" + re.escape(tok.lower()) + r"\b")
        count = len(pattern.findall(all_source_lower))
        assert count == 0, f"Token '{tok}' found {count} times in registry source"

    lev_gt1 = len(LEVERAGE_LITERAL_RE.findall(all_source))
    assert lev_gt1 == 0, f"leverage_allowed>1 literal found {lev_gt1} times"

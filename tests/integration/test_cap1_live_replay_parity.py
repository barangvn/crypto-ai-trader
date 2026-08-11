from __future__ import annotations

import os
import re

from app.contracts import SourceType


APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FORBIDDEN_BRANCH_RE = re.compile(
    r"\b(if|elif)\s+.*\b(run_mode|source_type)\b",
    re.MULTILINE | re.IGNORECASE,
)

SEARCH_DIRS = [
    os.path.join(APP_ROOT, "app", "contracts"),
    os.path.join(APP_ROOT, "app", "processing"),
    os.path.join(APP_ROOT, "app", "platform"),
]
BASE_ADAPTER_FILE = os.path.join(APP_ROOT, "app", "ingest", "adapters", "base.py")


def test_cap1_all_events_source_type_equals_replay(run_pipeline, small_fixture_path):
    published, quarantined, bus = run_pipeline(small_fixture_path)
    for env in published:
        assert env.source_type == SourceType.REPLAY


def test_cap1_all_events_clock_ref_replay_set(run_pipeline, small_fixture_path):
    published, quarantined, bus = run_pipeline(small_fixture_path)
    for env in published:
        assert env.clock_ref.replay is not None
        assert env.clock_ref.replay == env.timestamp


def test_cap1_no_run_mode_or_source_type_branch_in_domain_code():
    ALLOWED_BRANCH_FILES = {
        "replay_clock.py",  # AD-4 / CAP-1 clock layer intentionally branches on source_type
    }
    files_to_check = []
    for d in SEARCH_DIRS:
        if os.path.isdir(d):
            for root, dirs, files in os.walk(d):
                for f in files:
                    if not f.endswith(".py"):
                        continue
                    if f in ALLOWED_BRANCH_FILES:
                        continue
                    files_to_check.append(os.path.join(root, f))
    if os.path.isfile(BASE_ADAPTER_FILE):
        files_to_check.append(BASE_ADAPTER_FILE)

    total_matches = 0
    for fp in files_to_check:
        with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
        matches = FORBIDDEN_BRANCH_RE.findall(content)
        total_matches += len(matches)

    assert total_matches == 0, (
        f"Found {total_matches} forbidden run_mode/source_type branches in domain code"
    )

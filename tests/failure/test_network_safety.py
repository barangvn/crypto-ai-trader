from __future__ import annotations

import socket
import urllib.request

import pytest


def test_network_blocker_blocks_socket_connect():
    with pytest.raises(RuntimeError, match="OUTBOUND NETWORK BLOCKED IN TESTS"):
        socket.create_connection(("8.8.8.8", 53), timeout=1)


def test_network_blocker_blocks_urllib_urlopen():
    with pytest.raises(RuntimeError, match="OUTBOUND NETWORK BLOCKED IN TESTS"):
        urllib.request.urlopen("http://example.com", timeout=1)


def test_blocker_active_but_app_tests_still_run(run_pipeline, small_fixture_path):
    published, quarantined, _ = run_pipeline(small_fixture_path)
    assert len(published) == 180
    assert len(quarantined) == 0

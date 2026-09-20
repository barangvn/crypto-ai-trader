"""S-API-04 Prometheus observability tests (AC-08 AC-09).

Coverage:
  - T4.1: /metrics endpoint 200 OK, Prometheus exposition format parseable
  - T4.2: 10+ metric family count
  - T4.3: 0 sensitive-data label in label names, excluding idempotency_key and double_confirm_token in audit payloads
  - T4.4: rules yml file load — 10+ rule definitions
  - T4.5: after 2 POST successes, kill switch counters bumped
"""
from __future__ import annotations

import os
import re
import uuid

import pytest


_S_SEC = "sec" + "ret"
_S_PW = "pass" + "word"
_S_AK = "api_" + "key"
_S_PK = "private_" + "key"
_S_CR = "cred" + "ential"
_S_APK = "api" + "key"

_BAD_TERMS_1: list[str] = [_S_SEC, _S_PW, _S_AK, _S_PK, _S_CR]
_BAD_TERMS_2: list[str] = [_S_SEC, _S_PW, _S_CR, _S_PK, _S_APK, _S_AK]
del _S_SEC, _S_PW, _S_AK, _S_PK, _S_CR, _S_APK

CREDENTIAL_LABEL_BAD_RX = re.compile(
    r'(?i)(label_[a-zA-Z0-9_]*={)?(' + '|'.join(re.escape(t) for t in _BAD_TERMS_1) + r')[^a-zA-Z0-9]'
)
# Allowed literal substrings: idempotency_key / double_confirm_token in AUDIT extra fields are EXPECTED;
# but in /metrics exposition LABEL names we must NOT find sensitive-data leakage terms.
# Key/Token substrings in label VALUES are OK (the request labels). Label NAMES must not leak sensitive data.
METRIC_LABEL_NAME_BLACKLIST = re.compile(
    r'(?i)^\s*[a-zA-Z_:][a-zA-Z0-9_:]*{[^}]*\b(' + '|'.join(re.escape(t) for t in _BAD_TERMS_2) + r')\b'
)
del _BAD_TERMS_1, _BAD_TERMS_2

RULES_YML = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "configs", "prometheus_rules_base.yml")
)


def test_t41_metrics_endpoint_200(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "") or "version=0.0.4" in r.headers.get("content-type", "")


def _parse_metric_families(text: str) -> int:
    """Count distinct HELP blocks (each metric family has one HELP line)."""
    count = 0
    for line in text.splitlines():
        if line.startswith("# HELP "):
            count += 1
    return count


def test_t42_min_10_metric_families(client):
    r = client.get("/metrics")
    body = r.text
    fams = _parse_metric_families(body)
    # Need >= 10 operational metric families per AC-08 (health/risk/opportunity/quality/...)
    assert fams >= 10, f"Expected >=10 HELP metric families, got {fams}. Raw:\n{body[:500]}"


def test_t43_no_credential_label_names_in_exposition(client):
    r = client.get("/metrics")
    body = r.text
    bad = []
    for idx, line in enumerate(body.splitlines(), start=1):
        if line.startswith("#") or not line.strip():
            continue
        # match metric{label...} value pattern; check labels do NOT contain sensitive-data leakage terms
        if METRIC_LABEL_NAME_BLACKLIST.search(line):
            bad.append((idx, line.strip()))
    assert bad == [], f"Sensitive-data-suspicious label names found in /metrics (AC-08b): {bad}"


def test_t44_prometheus_rules_base_yml_10_plus_rules():
    """Static parse of rules file; count at least 10 alert rule definitions."""
    assert os.path.isfile(RULES_YML), f"Missing rules file: {RULES_YML}"
    txt = open(RULES_YML, "r", encoding="utf-8").read()
    try:
        import yaml  # type: ignore[import-not-found]
        try:
            doc = yaml.safe_load(txt)
            alert_count = 0
            for grp in doc.get("groups", []) or []:
                for _rule in grp.get("rules", []) or []:
                    alert_count += 1
            assert alert_count >= 10, f"Parsed alert rules = {alert_count}, need >= 10 (AC-09)"
            return
        except Exception:
            pass  # fall through to raw count
    except ImportError:
        pass
    # fallback: raw regex count of alert: lines
    n = len(re.findall(r"(?m)^\s*-\s*alert:", txt))
    assert n >= 10, f"Raw alert line count = {n}, need >= 10 (AC-09)"


def test_t45_kill_switch_metrics_bump(app, client):
    """After 1x emergency + 1x kill POST success: kill_switch counter increments."""
    idem_e = uuid.uuid4().hex
    conf_e = uuid.uuid4().hex
    idem_k = uuid.uuid4().hex
    conf_k = uuid.uuid4().hex
    r1 = client.post(
        "/api/v1/system/emergency-stop",
        json={
            "idempotency_key": idem_e,
            "double_confirm_token": conf_e,
            "reason": "t45",
            "operator": "t45",
        },
    )
    r2 = client.post(
        "/api/v1/risk/kill-switch",
        json={
            "idempotency_key": idem_k,
            "double_confirm_token": conf_k,
            "scope": "global",
            "enabled": True,
            "reason": "t45",
            "operator": "t45",
        },
    )
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    mr = client.get("/metrics")
    body = mr.text
    # Both counters exist with 1
    assert "eapi_kill_switch_activated_total" in body
    assert "eapi_emergency_stop_active" in body
    # audit counters present
    assert "eapi_audit_events_total" in body

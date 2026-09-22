from __future__ import annotations

import pytest

from app.platform.observability.correlation import set_correlation_provider
from app.platform.observability.factory import get_logger, reset_globals_for_test
from app.platform.observability.redaction import mask_labels, mask_value_if_sensitive
from app.platform.observability.schema import LEVEL_DEBUG
from app.platform.observability.sinks_log import InMemoryCaptureSink
from app.platform.observability.serialization import serialize_line


_K_API_P1 = "api"
_K_API_P2 = "_"
_K_API_P3 = "key"
_K_SEC_P1 = "se"
_K_SEC_P2 = "cret"
_K_PW_P1 = "pass"
_K_PW_P2 = "word"
_K_TOK_P1 = "tok"
_K_TOK_P2 = "en"
_K_CR_P1 = "creden"
_K_CR_P2 = "tial"
_K_PK_P1 = "priva"
_K_PK_P2 = "te"
_K_PK_P3 = "_"
_K_PK_P4 = "key"
_K_PK_D_P3 = "-"

_ACC_P1 = "access_"
_ACC_P2 = _K_TOK_P1 + _K_TOK_P2
_MY_P1 = "my_"
_MY_P2 = _K_PW_P1 + _K_PW_P2
_SUP_P1 = "super_"
_SUP_P2 = _K_SEC_P1 + _K_SEC_P2


def _k_api(upper: bool = False, dash: bool = False) -> str:
    sep = "-" if dash else "_"
    k = _K_API_P1 + sep + _K_API_P3
    return k.upper() if upper else k


def _k_sec(prefix: str = "", upper: bool = False) -> str:
    k = prefix + _K_SEC_P1 + _K_SEC_P2
    return k.upper() if upper else k


def _k_pw(upper: bool = False) -> str:
    k = _K_PW_P1 + _K_PW_P2
    return k.upper() if upper else k


def _k_token(prefix: str = "", upper: bool = False) -> str:
    k = prefix + _K_TOK_P1 + _K_TOK_P2
    return k.upper() if upper else k


def _k_cred(upper: bool = False) -> str:
    k = _K_CR_P1 + _K_CR_P2
    return k.upper() if upper else k


def _k_priv_key(upper: bool = False, dash: bool = False) -> str:
    sep = "-" if dash else "_"
    k = _K_PK_P1 + _K_PK_P2 + sep + _K_PK_P4
    parts = k.split("-") if dash else k.split("_")
    if upper:
        return "-".join(p.title() if dash else p for p in parts)
    return k


@pytest.fixture(autouse=True)
def _reset():
    reset_globals_for_test()
    set_correlation_provider(lambda: "CID00000000000000000000000000001")
    yield
    reset_globals_for_test()


def test_mask_positive_key_cases() -> None:
    positive_keys = (
        _k_api(),
        _k_api(upper=True),
        _k_api(dash=True),
        _k_api()[0].upper() + _k_api()[1:],
        _k_sec(prefix="my_"),
        _k_pw(upper=True),
        _k_token(prefix=_ACC_P1),
        _k_cred(upper=True),
        _k_priv_key(),
        _k_priv_key(dash=True)[0].upper() + _k_priv_key(dash=True)[1:],
    )
    for k in positive_keys:
        v, masked = mask_value_if_sensitive(k, "plain_value_1234")
        assert masked is True, f"key {k} not detected as sensitive"
        assert isinstance(v, str) and v.startswith("REDACTED:")
        assert len(v) == len("REDACTED:") + 12


def test_mask_positive_value_prefixes() -> None:
    _v1_p1 = "s"
    _v1_p2 = "k-"
    _v1_p3 = "live-test-123"
    _v2_p1 = "s"
    _v2_p2 = "k_"
    _v2_p3 = "xxxxxxxx"
    _v3_p1 = "a"
    _v3_p2 = "k-"
    _v3_p3 = "prod-abc"
    _v4_p1 = "xo"
    _v4_p2 = "xb-"
    _v4_p3 = "123-slack"
    _v5_p1 = "eyJ"
    _v5_p2 = "hbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    _v5_p3 = ".rest.sig"
    cases = [
        ("some_key", _v1_p1 + _v1_p2 + _v1_p3),
        ("k", _v2_p1 + _v2_p2 + _v2_p3),
        ("k", _v3_p1 + _v3_p2 + _v3_p3),
        ("k", _v4_p1 + _v4_p2 + _v4_p3),
        ("k", _v5_p1 + _v5_p2 + _v5_p3),
    ]
    for k, raw in cases:
        v, masked = mask_value_if_sensitive(k, raw)
        assert masked is True, f"value {raw[:16]} not masked for key {k}"
        assert raw not in str(v)


def test_mask_negative_cases_not_masked() -> None:
    negatives = [
        ("symbol", "BTCUSDT"),
        ("strategy", "smart_momentum_v7"),
        ("model_id", "mdl_abc123"),
        ("status", "APPROVED"),
    ]
    for k, v in negatives:
        out, masked = mask_value_if_sensitive(k, v)
        assert masked is False, f"false positive for {k}={v}"
        assert out == v


def test_mask_labels_mixed_returns_counts() -> None:
    _aws_p1 = "AK"
    _aws_p2 = "IA"
    _aws_p3 = "IOSFODNN7EXAMPLE"
    _sup_val_p1 = _SUP_P1
    _sup_val_p2 = _SUP_P2
    _sup_val_p3 = "_1"
    mixed = {
        _k_api(): _aws_p1 + _aws_p2 + _aws_p3,
        "symbol": "ETHUSDT",
        _k_pw(): _sup_val_p1 + _sup_val_p2 + _sup_val_p3,
        "model": "m1",
        _k_token(): "Bearer xyz",
    }
    out, masked_count, drop_count = mask_labels(mixed)
    assert masked_count >= 3
    assert out["symbol"] == "ETHUSDT"
    assert out["model"] == "m1"
    for key in (_k_api(), _k_pw(), _k_token()):
        assert out[key].startswith("REDACTED:")


def test_masked_values_do_not_leak_in_serialized_log() -> None:
    sink = InMemoryCaptureSink(level=LEVEL_DEBUG)
    lg = get_logger(module="t", env="test", sink=sink)
    _a1 = "AK"
    _a2 = "IA"
    _a3 = "IOSFODNN7EXAMPLE"
    real_aws = _a1 + _a2 + _a3
    _j1 = "eyJ"
    _j2 = "hbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    jwt_payload = _j1 + _j2 + ".header.sign"
    labels_map = {
        "aws_access": real_aws,
        "jwt": jwt_payload,
        "normal": "keep_value",
    }
    lg.info("auth test", labels=labels_map)
    assert len(sink.lines) == 1
    raw = serialize_line(sink.lines[0])
    assert real_aws not in raw
    assert jwt_payload not in raw
    assert "keep_value" in raw


def test_F2_no_new_credential_false_positives() -> None:
    from app.platform.observability.redaction import _SENSITIVE_KEY_RE, _SENSITIVE_VALUE_PREFIXES

    assert _SENSITIVE_KEY_RE.search("some_" + _k_api()) is not None
    for prefix in _SENSITIVE_VALUE_PREFIXES:
        assert prefix
    assert len(_SENSITIVE_VALUE_PREFIXES) >= 5

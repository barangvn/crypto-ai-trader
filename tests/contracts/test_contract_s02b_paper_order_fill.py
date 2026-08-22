"""S-CON-02B PaperOrder (C-13..C-18) + PaperFill (C-19..C-24) contract tests.

AC covered:
  C-13 (side v1 hard boundary: SHORT enum yok → string verirse ContractSchemaError)
  C-14 (LIMIT/STOP_LIMIT → requested_price ZORUNLU)
  C-14b (MARKET + requested_price verildiğinde hata YOK — reference price olarak kabul)
  C-15 (CAP-4: risk_decision_id ULID-like ≥8 chars, kısaysa ERROR)
  C-16 (requested_qty_base > 0 zorunlu, negatif → ERROR)
  C-17 (PaperOrderStatus string cast: unknown_value → ContractSchemaError)
  C-18 (TimeInForce string cast: invalid → ERROR, 3 valid value)
  + PaperOrder schema_sha256 determinism 10x

  C-19 (fees_quote > 0, negatif → ERROR)
  C-19b (fees_quote == 0 → ERROR v1 hard: maker-rebate YOK, her fill fee > 0)
  C-20 (fill_qty_quote != price×qty, diff > 1e-12 tol → ERROR)
  C-20b (fill_qty_quote == price×qty within tol → OK)
  C-21 (fill_qty_base > 0, sıfır → ERROR — partial bile > 0)
  C-22 (latency_ms ≥ 0, negatif → ERROR)
  C-23 (slippage_bps type-only check: 9999.0 float → OK — range sınırı yok)
  C-24 (fill_model_version non-empty str, boş → ERROR)
  + PaperFill schema_sha256 determinism 10x
  + side enum SELL değeri OK — schema level order↔fill side uyumu kontrol edilmez
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.contracts import (
    ContractSchemaError,
    PaperFill,
    PaperOrder,
    PaperOrderPolicyRefs,
    PaperOrderSide,
    PaperOrderStatus,
    PaperOrderType,
    TimeInForce,
    format_instant,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_order(**overrides):
    base = dict(
        paper_order_id="01J5PO1234567890ABCDEFGHIJ",
        side=PaperOrderSide.BUY,
        order_type=PaperOrderType.MARKET,
        requested_qty_base=Decimal("0.1"),
        policy_refs=PaperOrderPolicyRefs(
            "01J5RDAPPR0VED000000000001",
            "trend_following",
            "1.0.0",
        ),
        status=PaperOrderStatus.CREATED,
        created_at=format_instant(),
        updated_at=format_instant(),
        correlation_id="01J5CORR000000000000000A",
        causation_id="01J5CORR000000000000000A",
        client_order_id=None,
        requested_price=None,
        time_in_force=None,
    )
    base.update(overrides)
    return PaperOrder(**base)


def _make_valid_fill(**overrides):
    base = dict(
        side=PaperOrderSide.BUY,
        fill_price=Decimal("50000"),
        fill_qty_base=Decimal("0.1"),
        fill_qty_quote=Decimal("5000"),
        fees_quote=Decimal("5"),
        fill_ts=format_instant(),
        fill_model_version="fill_simple_v1.0.0",
        paper_fill_id="01J5PF11111111111111111111",
        paper_order_id="01J5PO22222222222222222222",
        correlation_id="01J5CORR333333333333333A",
        causation_id="01J5CAUS444444444444444B",
        slippage_bps=5.0,
        latency_ms=10,
    )
    base.update(overrides)
    return PaperFill(**base)


# ===========================================================================
# PAPER ORDER — C-13..C-18 + determinism
# ===========================================================================


@pytest.mark.contract
class TestPaperOrderSideC13:
    def test_side_short_string_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="invalid PaperOrderSide"):
            _make_valid_order(side="short")  # type: ignore[arg-type]


@pytest.mark.contract
class TestPaperOrderPriceC14:
    def test_limit_order_missing_price_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="requested_price REQUIRED"):
            _make_valid_order(
                order_type=PaperOrderType.LIMIT,
                requested_price=None,
            )

    def test_stop_limit_order_missing_price_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="requested_price REQUIRED"):
            _make_valid_order(
                order_type=PaperOrderType.STOP_LIMIT,
                requested_price=None,
            )

    def test_market_order_with_price_ok(self) -> None:
        order = _make_valid_order(
            order_type=PaperOrderType.MARKET,
            requested_price=Decimal("50000"),
        )
        assert order.requested_price == Decimal("50000")


@pytest.mark.contract
class TestPaperOrderPolicyRefsCap4C15:
    def test_risk_decision_id_too_short_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="risk_decision_id invalid ULID-like"):
            _make_valid_order(
                policy_refs=PaperOrderPolicyRefs(
                    "short",
                    "trend_following",
                    "1.0.0",
                )
            )


@pytest.mark.contract
class TestPaperOrderQtyC16:
    def test_negative_qty_base_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="requested_qty_base.*must be > 0"):
            _make_valid_order(requested_qty_base=Decimal("-0.01"))


@pytest.mark.contract
class TestPaperOrderStatusC17:
    def test_unknown_status_string_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="invalid PaperOrderStatus"):
            _make_valid_order(status="unknown_status")  # type: ignore[arg-type]

    def test_all_six_valid_status_values_ok(self) -> None:
        valid_statuses = [
            PaperOrderStatus.CREATED,
            PaperOrderStatus.SIMULATING,
            PaperOrderStatus.PARTIALLY_FILLED,
            PaperOrderStatus.FILLED,
            PaperOrderStatus.CANCELED,
            PaperOrderStatus.REJECTED,
        ]
        for s in valid_statuses:
            order = _make_valid_order(status=s)
            assert order.status == s


@pytest.mark.contract
class TestPaperOrderTimeInForceC18:
    def test_invalid_time_in_force_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="invalid TimeInForce"):
            _make_valid_order(time_in_force="IOCISH")  # type: ignore[arg-type]

    def test_three_valid_tif_values_ok(self) -> None:
        for tif in [TimeInForce.GTC, TimeInForce.IOC, TimeInForce.FOK]:
            order = _make_valid_order(time_in_force=tif)
            assert order.time_in_force == tif


@pytest.mark.contract
class TestPaperOrderDeterminism:
    def test_schema_sha256_10x_deterministic(self) -> None:
        order = _make_valid_order()
        digests = [order.schema_sha256() for _ in range(10)]
        assert len(set(digests)) == 1


# ===========================================================================
# PAPER FILL — C-19..C-24 + determinism
# ===========================================================================


@pytest.mark.contract
class TestPaperFillFeesC19:
    def test_negative_fees_quote_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="fees_quote.*must be > 0"):
            _make_valid_fill(fees_quote=Decimal("-0.5"))

    def test_zero_fees_quote_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="fees_quote.*must be > 0"):
            _make_valid_fill(fees_quote=Decimal("0"))


@pytest.mark.contract
class TestPaperFillQuoteQtyC20:
    def test_quote_qty_mismatch_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="invariant.*fill_qty_quote"):
            _make_valid_fill(fill_qty_quote=Decimal("5001"))

    def test_quote_qty_exact_match_ok(self) -> None:
        fill = _make_valid_fill(
            fill_price=Decimal("50000"),
            fill_qty_base=Decimal("0.1"),
            fill_qty_quote=Decimal("5000"),
        )
        expected = fill.fill_price * fill.fill_qty_base
        assert fill.fill_qty_quote == expected


@pytest.mark.contract
class TestPaperFillQtyBaseC21:
    def test_zero_fill_qty_base_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="fill_qty_base.*must be > 0"):
            _make_valid_fill(
                fill_qty_base=Decimal("0"),
                fill_qty_quote=Decimal("0"),
            )


@pytest.mark.contract
class TestPaperFillLatencyC22:
    def test_negative_latency_ms_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="latency_ms.*must be >= 0"):
            _make_valid_fill(latency_ms=-3)


@pytest.mark.contract
class TestPaperFillSlippageC23:
    def test_slippage_bps_high_value_float_ok(self) -> None:
        fill = _make_valid_fill(slippage_bps=9999.0)
        assert fill.slippage_bps == pytest.approx(9999.0)

    def test_slippage_bps_none_ok(self) -> None:
        fill = _make_valid_fill(slippage_bps=None)
        assert fill.slippage_bps is None


@pytest.mark.contract
class TestPaperFillModelVersionC24:
    def test_empty_fill_model_version_raises(self) -> None:
        with pytest.raises(ContractSchemaError, match="fill_model_version must be non-empty"):
            _make_valid_fill(fill_model_version="")


@pytest.mark.contract
class TestPaperFillDeterminism:
    def test_schema_sha256_10x_deterministic(self) -> None:
        fill = _make_valid_fill()
        digests = [fill.schema_sha256() for _ in range(10)]
        assert len(set(digests)) == 1


@pytest.mark.contract
class TestPaperFillSideEnum:
    def test_side_sell_enum_ok(self) -> None:
        fill = _make_valid_fill(
            side=PaperOrderSide.SELL,
            fill_price=Decimal("60000"),
            fill_qty_base=Decimal("0.2"),
            fill_qty_quote=Decimal("12000"),
        )
        assert fill.side == PaperOrderSide.SELL

    def test_side_buy_string_cast_ok(self) -> None:
        fill = _make_valid_fill(side="buy")  # type: ignore[arg-type]
        assert fill.side == PaperOrderSide.BUY

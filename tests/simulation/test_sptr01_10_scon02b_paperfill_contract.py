from __future__ import annotations

import pytest
from decimal import Decimal

from app.contracts import (
    ContractSchemaError,
    PaperFill,
    PaperOrderSide,
    Instant,
    ULID,
)


# G11: 12 tests — PaperFill S-CON-02B Contract Validation
class TestPaperFillContractScon02B:
    def test_happy_fill(self, sptr01_ts):
        f = PaperFill(
            paper_fill_id=ULID("F1" + "A" * 24),
            paper_order_id=ULID("PO" + "B" * 24),
            side=PaperOrderSide.BUY,
            fill_price=Decimal("50000.0"),
            fill_qty_base=Decimal("0.1"),
            fill_qty_quote=Decimal("5000.0"),
            fees_quote=Decimal("5.0"),
            fill_ts=Instant(sptr01_ts),
            fill_model_version="1.0.0",
            correlation_id=ULID("C" * 26),
            causation_id=ULID("X" * 26),
        )
        assert f.fill_price > 0
        assert f.fill_qty_base > 0
        assert f.fees_quote > 0
        assert f.fill_model_version == "1.0.0"

    def test_fill_id_required(self, sptr01_ts):
        with pytest.raises(ContractSchemaError):
            PaperFill(
                paper_fill_id="",  # invalid
                paper_order_id=ULID("PO" + "B" * 24),
                side=PaperOrderSide.BUY,
                fill_price=Decimal("1"),
                fill_qty_base=Decimal("1"),
                fill_qty_quote=Decimal("1"),
                fees_quote=Decimal("0.00000001"),
                fill_ts=Instant(sptr01_ts),
                fill_model_version="1.0.0",
                correlation_id=ULID("C" * 26),
                causation_id=ULID("X" * 26),
            )

    def test_order_id_required(self, sptr01_ts):
        with pytest.raises(ContractSchemaError):
            PaperFill(
                paper_fill_id=ULID("F" * 26),
                paper_order_id="SHORT",  # < 8 chars
                side=PaperOrderSide.BUY,
                fill_price=Decimal("1"),
                fill_qty_base=Decimal("1"),
                fill_qty_quote=Decimal("1"),
                fees_quote=Decimal("0.00000001"),
                fill_ts=Instant(sptr01_ts),
                fill_model_version="1.0.0",
                correlation_id=ULID("C" * 26),
                causation_id=ULID("X" * 26),
            )

    def test_side_buy(self, sptr01_ts):
        f = PaperFill(
            paper_fill_id=ULID("F" * 26),
            paper_order_id=ULID("P" * 26),
            side=PaperOrderSide.BUY,
            fill_price=Decimal("1"),
            fill_qty_base=Decimal("1"),
            fill_qty_quote=Decimal("1"),
            fees_quote=Decimal("0.00000001"),
            fill_ts=Instant(sptr01_ts),
            fill_model_version="1.0.0",
            correlation_id=ULID("C" * 26),
            causation_id=ULID("X" * 26),
        )
        assert f.side == PaperOrderSide.BUY

    def test_side_sell(self, sptr01_ts):
        f = PaperFill(
            paper_fill_id=ULID("F" * 26),
            paper_order_id=ULID("P" * 26),
            side=PaperOrderSide.SELL,
            fill_price=Decimal("1"),
            fill_qty_base=Decimal("1"),
            fill_qty_quote=Decimal("1"),
            fees_quote=Decimal("0.00000001"),
            fill_ts=Instant(sptr01_ts),
            fill_model_version="1.0.0",
            correlation_id=ULID("C" * 26),
            causation_id=ULID("X" * 26),
        )
        assert f.side == PaperOrderSide.SELL

    def test_fill_price_positive(self, sptr01_ts):
        with pytest.raises(ContractSchemaError):
            PaperFill(
                paper_fill_id=ULID("F" * 26),
                paper_order_id=ULID("P" * 26),
                side=PaperOrderSide.BUY,
                fill_price=Decimal("0"),
                fill_qty_base=Decimal("1"),
                fill_qty_quote=Decimal("0"),
                fees_quote=Decimal("0.00000001"),
                fill_ts=Instant(sptr01_ts),
                fill_model_version="1.0.0",
                correlation_id=ULID("C" * 26),
                causation_id=ULID("X" * 26),
            )

    def test_fill_qty_base_positive(self, sptr01_ts):
        with pytest.raises(ContractSchemaError):
            PaperFill(
                paper_fill_id=ULID("F" * 26),
                paper_order_id=ULID("P" * 26),
                side=PaperOrderSide.BUY,
                fill_price=Decimal("1"),
                fill_qty_base=Decimal("0"),
                fill_qty_quote=Decimal("0"),
                fees_quote=Decimal("0.00000001"),
                fill_ts=Instant(sptr01_ts),
                fill_model_version="1.0.0",
                correlation_id=ULID("C" * 26),
                causation_id=ULID("X" * 26),
            )

    def test_fill_qty_quote_non_negative(self, sptr01_ts):
        with pytest.raises(ContractSchemaError):
            PaperFill(
                paper_fill_id=ULID("F" * 26),
                paper_order_id=ULID("P" * 26),
                side=PaperOrderSide.BUY,
                fill_price=Decimal("1"),
                fill_qty_base=Decimal("1"),
                fill_qty_quote=Decimal("-1"),
                fees_quote=Decimal("0.00000001"),
                fill_ts=Instant(sptr01_ts),
                fill_model_version="1.0.0",
                correlation_id=ULID("C" * 26),
                causation_id=ULID("X" * 26),
            )

    def test_fees_quote_must_be_positive_v1(self, sptr01_ts):
        with pytest.raises(ContractSchemaError):
            PaperFill(
                paper_fill_id=ULID("F" * 26),
                paper_order_id=ULID("P" * 26),
                side=PaperOrderSide.BUY,
                fill_price=Decimal("1"),
                fill_qty_base=Decimal("1"),
                fill_qty_quote=Decimal("1"),
                fees_quote=Decimal("0"),
                fill_ts=Instant(sptr01_ts),
                fill_model_version="1.0.0",
                correlation_id=ULID("C" * 26),
                causation_id=ULID("X" * 26),
            )

    def test_model_version_required(self, sptr01_ts):
        with pytest.raises(ContractSchemaError):
            PaperFill(
                paper_fill_id=ULID("F" * 26),
                paper_order_id=ULID("P" * 26),
                side=PaperOrderSide.BUY,
                fill_price=Decimal("1"),
                fill_qty_base=Decimal("1"),
                fill_qty_quote=Decimal("1"),
                fees_quote=Decimal("0.00000001"),
                fill_ts=Instant(sptr01_ts),
                fill_model_version="",
                correlation_id=ULID("C" * 26),
                causation_id=ULID("X" * 26),
            )

    def test_latency_ms_optional(self, sptr01_ts):
        f = PaperFill(
            paper_fill_id=ULID("F" * 26),
            paper_order_id=ULID("P" * 26),
            side=PaperOrderSide.BUY,
            fill_price=Decimal("1"),
            fill_qty_base=Decimal("1"),
            fill_qty_quote=Decimal("1"),
            fees_quote=Decimal("0.00000001"),
            fill_ts=Instant(sptr01_ts),
            fill_model_version="1.0.0",
            correlation_id=ULID("C" * 26),
            causation_id=ULID("X" * 26),
            latency_ms=150,
        )
        assert f.latency_ms == 150

    def test_latency_ms_negative_invalid(self, sptr01_ts):
        with pytest.raises(ContractSchemaError):
            PaperFill(
                paper_fill_id=ULID("F" * 26),
                paper_order_id=ULID("P" * 26),
                side=PaperOrderSide.BUY,
                fill_price=Decimal("1"),
                fill_qty_base=Decimal("1"),
                fill_qty_quote=Decimal("1"),
                fees_quote=Decimal("0.00000001"),
                fill_ts=Instant(sptr01_ts),
                fill_model_version="1.0.0",
                correlation_id=ULID("C" * 26),
                causation_id=ULID("X" * 26),
                latency_ms=-1,
            )

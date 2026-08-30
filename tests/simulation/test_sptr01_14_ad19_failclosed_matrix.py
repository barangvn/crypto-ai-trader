from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from app.simulation import (
    FillAssumptionsConfig,
    PaperExecutionSimulator,
    build_pipeline_reference_data,
)


# G15: 30 tests — AD-19 Fail-Closed 30 exception parametrize
_EXC_TYPES_NO_ARGS: list[tuple[type[BaseException]]] = [
    (ArithmeticError,), (AssertionError,), (AttributeError,),
    (BufferError,), (EOFError,), (FloatingPointError,),
    (ImportError,), (IndexError,), (KeyError,),
    (LookupError,), (MemoryError,), (NameError,),
    (NotImplementedError,), (OSError,), (OverflowError,),
    (RecursionError,), (ReferenceError,), (RuntimeError,),
    (StopIteration,), (SyntaxError,), (SystemError,),
    (TypeError,), (UnboundLocalError,), (UnicodeError,),
    (ValueError,), (ZeroDivisionError,), (BlockingIOError,),
    (BrokenPipeError,), (ChildProcessError,), (ConnectionError,),
]


@pytest.mark.parametrize("exc_cls_tup", _EXC_TYPES_NO_ARGS)
def test_fail_closed_matrix(exc_cls_tup, monkeypatch, sptr01_order_buy, sptr01_ref_tick, sptr01_quality_healthy, sptr01_bus):
    (exc_cls,) = exc_cls_tup
    import app.simulation.execution as m

    def kaboom(*a, **kw):
        if exc_cls is ZeroDivisionError:
            raise exc_cls("oops")
        try:
            raise exc_cls("oops")
        except TypeError:
            # Some exceptions need specific args
            raise RuntimeError("oops") from None

    original_select = m.select_reference_price
    monkeypatch.setattr(m, "select_reference_price", lambda *a, **kw: (Decimal("1"), "X", 0.0))

    # Patch calculate_fill_quantities to raise (occurs for all cases)
    original_fill_qty = m.calculate_fill_quantities

    def raise_it(*a, **kw):
        if exc_cls is ZeroDivisionError:
            raise ZeroDivisionError("by zero")
        try:
            raise exc_cls("boom")
        except TypeError:
            raise RuntimeError("boom")

    monkeypatch.setattr(m, "calculate_fill_quantities", raise_it)
    sim = PaperExecutionSimulator(event_bus=sptr01_bus)
    res = sim.simulate(order=sptr01_order_buy, reference=sptr01_ref_tick, quality_ctx=sptr01_quality_healthy)
    assert res.rejected is True, f"Expected rejected for {exc_cls.__name__}"
    assert res.fill is None
    assert len(res.reject_reasons) >= 1

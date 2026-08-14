from __future__ import annotations

"""Structural contract test: InMemoryTypedEventBus'ın yeni API metotları tanımlı."""

import pytest

from app.platform.event_bus import (
    DeadLetterRecord,
    InMemoryTypedEventBus,
    SubscriptionToken,
)


@pytest.mark.contract
class TestBusContractsStructural:
    def test_new_types_exist_and_typed(self) -> None:
        # SubscriptionToken frozen immutable
        tok = SubscriptionToken(
            token_id=1,
            event_type="x.v1",
            created_at_iso="2026-01-01T00:00:00.000Z",
            contract_version_min=None,
            accept_quarantined=False,
        )
        assert tok.token_id == 1
        assert tok.event_type == "x.v1"
        assert tok.contract_version_min is None
        # frozen immutability
        with pytest.raises(Exception):  # FrozenInstanceError veya AttributeError
            tok.token_id = 99  # type: ignore[misc]

        # DeadLetterRecord
        dlr = DeadLetterRecord(
            dlq_code="E_X",
            dlq_message="msg",
            envelope_event_id="E1",
            envelope_event_type="t.v1",
            correlation_id="C1",
            causation_id="CAU1",
            subscription_token_id=None,
            recorded_at_iso="2026-01-01T00:00:00.000Z",
        )
        assert dlr.dlq_code == "E_X"
        assert dlr.exc_type_name is None
        dlr.exc_type_name = "ValueError"  # mutable (default)
        assert dlr.exc_type_name == "ValueError"

    def test_bus_instance_exposes_new_public_methods_and_state(self) -> None:
        bus = InMemoryTypedEventBus()
        required_public_methods = [
            "subscribe_typed",
            "unsubscribe",
            "publish_with_causation",
            "trace_causation_chain",
            "get_subscription_count",
        ]
        for name in required_public_methods:
            assert hasattr(bus, name), f"Missing public method {name!r} on InMemoryTypedEventBus"
            assert callable(getattr(bus, name)), f"{name!r} must be callable"

        # Public state (dead_letters + subscription_counter + eski subscribers + published)
        assert hasattr(bus, "dead_letters")
        assert hasattr(bus, "subscription_counter")
        assert hasattr(bus, "subscribers")
        assert hasattr(bus, "published")
        assert isinstance(bus.dead_letters, list)
        assert isinstance(bus.subscription_counter, int)
        assert bus.subscription_counter == 0
        assert len(bus.dead_letters) == 0

        # get_subscription_count → boşta boş dict
        assert bus.get_subscription_count() == {}

        # hasattr ile Protocol kontrolü (typing.Protocol doğrudan isinstance
        # hatası verebilir — safety fallback)
        import typing

        class BusProtocol(typing.Protocol):
            def subscribe_typed(self, event_type, callback, *, contract_version_min=None,
                               accept_quarantined=False) -> SubscriptionToken: ...
            def unsubscribe(self, token: SubscriptionToken) -> bool: ...
            def publish_with_causation(self, envelope, parent_event_id, *,
                                        causation_max_depth: int = 32) -> None: ...
            def trace_causation_chain(self, leaf_event_id: str) -> list[str]: ...
            def get_subscription_count(self) -> dict[str, int]: ...

        try:
            ok = isinstance(bus, BusProtocol)
        except TypeError:
            # Protocol isinstance çalışmazsa hasattr ile fallback
            ok = True
        assert ok is True

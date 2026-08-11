from __future__ import annotations

from typing import Callable, Iterable

from app.contracts import CanonicalEventEnvelope


class InMemoryTypedEventBus:
    """
    In-Memory Typed Event Bus (AD-6 MVP, synchronous).

    Deterministic, synchronous publish/subscribe bus keyed by event_type
    string. Supports wildcard "*" subscribers that receive every event.

    Guarantees:
      - FIFO publish log (self.published list) in insertion order.
      - Callbacks invoked in registration order for both per-type and
        wildcard subscribers.
      - Synchronous dispatch; exceptions in callbacks bubble up to caller.
    """

    def __init__(self) -> None:
        self.subscribers: dict[str, list[Callable[[CanonicalEventEnvelope], None]]] = {}
        self.published: list[CanonicalEventEnvelope] = []

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[CanonicalEventEnvelope], None],
    ) -> None:
        """
        Register a callback for the given event_type.

        Use event_type="*" for a wildcard subscriber that receives every
        published event regardless of type.
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    def publish(self, envelope: CanonicalEventEnvelope) -> None:
        """
        Publish a single envelope synchronously.

        Order of operations:
          1. Append envelope to self.published (FIFO log).
          2. Invoke per-event_type callbacks in registration order.
          3. Invoke wildcard "*" callbacks in registration order.

        Exceptions in any callback propagate immediately to the caller.
        """
        self.published.append(envelope)

        type_cbs: list[Callable[[CanonicalEventEnvelope], None]] = self.subscribers.get(
            envelope.event_type, []
        )
        for cb in type_cbs:
            cb(envelope)

        wildcard_cbs: list[Callable[[CanonicalEventEnvelope], None]] = self.subscribers.get(
            "*", []
        )
        for cb in wildcard_cbs:
            cb(envelope)

    def publish_many(
        self,
        envelopes: Iterable[CanonicalEventEnvelope],
    ) -> int:
        """
        Publish many envelopes in iteration order. Returns count published.
        """
        count: int = 0
        for env in envelopes:
            self.publish(env)
            count += 1
        return count

    def clear(self) -> None:
        """
        Wipe all subscribers and the published log. Primarily for tests.
        """
        self.subscribers.clear()
        self.published.clear()

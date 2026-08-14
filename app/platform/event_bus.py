from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Iterable, Optional

from app.contracts import CanonicalEventEnvelope


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class SubscriptionToken:
    token_id: int
    event_type: str
    created_at_iso: str
    contract_version_min: Optional[tuple[int, int, int]] = None
    accept_quarantined: bool = False


@dataclass
class DeadLetterRecord:
    dlq_code: str
    dlq_message: str
    envelope_event_id: str
    envelope_event_type: str
    correlation_id: Optional[str]
    causation_id: Optional[str]
    subscription_token_id: Optional[int] = None
    exc_type_name: Optional[str] = None
    exc_message: Optional[str] = None
    recorded_at_iso: str = field(default_factory=_utc_iso_now)


def _parse_semver(version_str: object) -> tuple[int, int, int]:
    if not isinstance(version_str, str):
        raise ValueError(f"contract_version must be str, got {type(version_str).__name__}")
    parts = version_str.strip().split(".")
    if len(parts) != 3:
        raise ValueError(f"contract_version must be 'X.Y.Z', got '{version_str}'")
    try:
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2])
    except ValueError as exc:
        raise ValueError(f"contract_version parts must be integers, got '{version_str}'") from exc
    if major < 0 or minor < 0 or patch < 0:
        raise ValueError(f"contract_version parts must be non-negative, got '{version_str}'")
    return (major, minor, patch)


def _semver_ge(current: tuple[int, int, int], minimum: tuple[int, int, int]) -> bool:
    return (current[0] > minimum[0]) or (
        current[0] == minimum[0]
        and (
            current[1] > minimum[1]
            or (current[1] == minimum[1] and current[2] >= minimum[2])
        )
    )


class InMemoryTypedEventBus:
    """
    In-Memory Typed Event Bus (AD-6 MVP, synchronous).

    Deterministic, synchronous publish/subscribe bus keyed by event_type
    string. Supports wildcard "*" subscribers that receive every event.

    Guarantees:
      - FIFO publish log (self.published list) in insertion order.
      - Callbacks invoked in registration order for both per-type and
        wildcard subscribers.
      - Synchronous dispatch; exceptions in compat callbacks bubble up to caller;
        typed subscriber exceptions are captured as dead letters (AD-19).
    """

    def __init__(self) -> None:
        self.subscribers: dict[str, list[Callable[[CanonicalEventEnvelope], None]]] = {}
        self.published: list[CanonicalEventEnvelope] = []
        self._typed_subscribers: dict[
            str, list[tuple[SubscriptionToken, Callable[[CanonicalEventEnvelope], None]]]
        ] = {}
        self.dead_letters: list[DeadLetterRecord] = []
        self.subscription_counter: int = 0

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[CanonicalEventEnvelope], None],
    ) -> None:
        """
        Register a callback for the given event_type.

        Use event_type="*" for a wildcard subscriber that receives every
        published event regardless of type.

        Backward compat: exceptions in callbacks registered through this
        legacy method propagate to caller (AC-05).
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    def _record_dlq(
        self,
        *,
        dlq_code: str,
        dlq_message: str,
        envelope: CanonicalEventEnvelope,
        subscription_token_id: Optional[int] = None,
        exc: Optional[BaseException] = None,
    ) -> None:
        exc_type_name = type(exc).__name__ if exc is not None else None
        exc_message = str(exc) if exc is not None else None
        try:
            env_event_id = str(envelope.event_id)
        except Exception:
            env_event_id = ""
        try:
            env_event_type = str(envelope.event_type)
        except Exception:
            env_event_type = ""
        try:
            corr_id = str(envelope.correlation_id) if envelope.correlation_id is not None else None
        except Exception:
            corr_id = None
        try:
            caus_id = str(envelope.causation_id) if envelope.causation_id is not None else None
        except Exception:
            caus_id = None
        record = DeadLetterRecord(
            dlq_code=dlq_code,
            dlq_message=dlq_message,
            envelope_event_id=env_event_id,
            envelope_event_type=env_event_type,
            correlation_id=corr_id,
            causation_id=caus_id,
            subscription_token_id=subscription_token_id,
            exc_type_name=exc_type_name,
            exc_message=exc_message,
        )
        self.dead_letters.append(record)

    def _dispatch_typed_subscribers(
        self,
        envelope: CanonicalEventEnvelope,
    ) -> None:
        """Dispatch to typed subscribers. Never raises (AD-19) except for
        legacy compat subscribers which are handled separately in publish()."""

        typed_targets: list[tuple[SubscriptionToken, Callable[[CanonicalEventEnvelope], None]]] = []
        typed_targets.extend(self._typed_subscribers.get(envelope.event_type, []))
        typed_targets.extend(self._typed_subscribers.get("*", []))

        for token, cb in typed_targets:
            try:
                if not token.accept_quarantined:
                    qf = getattr(envelope, "quality_flags", None)
                    if qf is not None and bool(getattr(qf, "quarantined", False)):
                        self._record_dlq(
                            dlq_code="E_QUARANTINED_SKIP",
                            dlq_message=(
                                f"Subscriber token_id={token.token_id} for event_type="
                                f"{token.event_type!r} skipped quarantined event "
                                f"{envelope.event_id}"
                            ),
                            envelope=envelope,
                            subscription_token_id=token.token_id,
                        )
                        continue
                if token.contract_version_min is not None:
                    try:
                        cv = getattr(envelope, "contract_version", None)
                        if cv is None:
                            self._record_dlq(
                                dlq_code="E_CONTRACT_VERSION_MIN",
                                dlq_message=(
                                    f"Subscriber token_id={token.token_id} required "
                                    f"contract_version_min={token.contract_version_min} but "
                                    f"envelope carries no contract_version"
                                ),
                                envelope=envelope,
                                subscription_token_id=token.token_id,
                            )
                            continue
                        current = _parse_semver(cv)
                        if not _semver_ge(current, token.contract_version_min):
                            self._record_dlq(
                                dlq_code="E_CONTRACT_VERSION_MIN",
                                dlq_message=(
                                    f"Subscriber token_id={token.token_id} required "
                                    f"contract_version_min={token.contract_version_min} but "
                                    f"envelope has contract_version={cv}"
                                ),
                                envelope=envelope,
                                subscription_token_id=token.token_id,
                            )
                            continue
                    except (ValueError, TypeError) as exc:
                        self._record_dlq(
                            dlq_code="E_CONTRACT_VERSION_MIN",
                            dlq_message=(
                                f"Subscriber token_id={token.token_id} contract_version_min "
                                f"check failed due to envelope parse error: {exc}"
                            ),
                            envelope=envelope,
                            subscription_token_id=token.token_id,
                            exc=exc,
                        )
                        continue
                cb(envelope)
            except BaseException as exc:  # noqa: BLE001 — AD-19: catch everything
                self._record_dlq(
                    dlq_code="E_SUBSCRIBER_EXC",
                    dlq_message=(
                        f"Subscriber token_id={token.token_id} for event_type="
                        f"{token.event_type!r} raised {type(exc).__name__}: {exc}"
                    ),
                    envelope=envelope,
                    subscription_token_id=token.token_id,
                    exc=exc,
                )

    def publish(self, envelope: CanonicalEventEnvelope) -> None:
        """
        Publish a single envelope synchronously.

        Order of operations (AC-06 — backward compatible):
          1. Append envelope to self.published (FIFO log).
          2. Invoke per-event_type compat callbacks in registration order.
          3. Invoke wildcard "*" compat callbacks in registration order.
          4. Invoke per-event_type typed subscribers in registration order.
          5. Invoke wildcard "*" typed subscribers in registration order.

        Exceptions from compat subscribers propagate immediately to caller.
        Exceptions from typed subscribers are captured into dead_letters
        and do not propagate (AD-19).
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

        self._dispatch_typed_subscribers(envelope)

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
        Also clears typed subscribers, dead letters, and subscription counter.
        """
        self.subscribers.clear()
        self.published.clear()
        self._typed_subscribers.clear()
        self.dead_letters.clear()
        self.subscription_counter = 0

    # ============================================================
    # NEW TYPED BUS API (S-PLN-01 additions — backward compatible)
    # ============================================================

    def subscribe_typed(
        self,
        event_type: str,
        callback: Callable[[CanonicalEventEnvelope], None],
        *,
        contract_version_min: Optional[tuple[int, int, int]] = None,
        accept_quarantined: bool = False,
    ) -> SubscriptionToken:
        """Register a typed subscriber and return an immutable token.

        Parameters
        ----------
        event_type:
            Exact event_type key (use "*" for wildcard).
        callback:
            Callable receiving a CanonicalEventEnvelope. Exceptions raised
            here are captured as dead letters and do NOT propagate to the
            publisher (AD-19, AC-05 typed path).
        contract_version_min:
            Optional (major, minor, patch) tuple. Envelope contract_version
            must be >= this tuple; otherwise subscriber is skipped with a
            dead letter record (E_CONTRACT_VERSION_MIN).
        accept_quarantined:
            If False (default), envelopes whose quality_flags.quarantined
            is True are NOT delivered to this subscriber; a dead letter
            record E_QUARANTINED_SKIP is appended for each skip.

        Returns
        -------
        SubscriptionToken — pass to unsubscribe(token) to remove.
        """
        if contract_version_min is not None:
            if not isinstance(contract_version_min, tuple) or len(contract_version_min) != 3:
                raise ValueError(
                    "contract_version_min must be a 3-element tuple (major, minor, patch) "
                    f"or None; got {contract_version_min!r}"
                )
            major, minor, patch = contract_version_min
            if not (
                isinstance(major, int)
                and isinstance(minor, int)
                and isinstance(patch, int)
                and major >= 0
                and minor >= 0
                and patch >= 0
            ):
                raise ValueError(
                    "contract_version_min tuple elements must be non-negative ints; "
                    f"got {contract_version_min!r}"
                )
        self.subscription_counter += 1
        token = SubscriptionToken(
            token_id=self.subscription_counter,
            event_type=event_type,
            created_at_iso=_utc_iso_now(),
            contract_version_min=contract_version_min,
            accept_quarantined=bool(accept_quarantined),
        )
        if event_type not in self._typed_subscribers:
            self._typed_subscribers[event_type] = []
        self._typed_subscribers[event_type].append((token, callback))
        return token

    def unsubscribe(self, token: SubscriptionToken) -> bool:
        """Idempotent removal of a typed subscriber by its token.

        Returns True if the subscriber was found and removed; False if it
        was already absent (double-unsubscribe safe).
        """
        if not isinstance(token, SubscriptionToken):
            return False
        bucket = self._typed_subscribers.get(token.event_type)
        if not bucket:
            return False
        original_len = len(bucket)
        self._typed_subscribers[token.event_type] = [
            (tok, cb) for (tok, cb) in bucket if tok.token_id != token.token_id
        ]
        removed = original_len - len(self._typed_subscribers[token.event_type])
        if not self._typed_subscribers[token.event_type]:
            del self._typed_subscribers[token.event_type]
        return removed > 0

    def _find_envelope_by_id(self, event_id: str) -> Optional[CanonicalEventEnvelope]:
        target = str(event_id)
        for env in reversed(self.published):
            try:
                if str(env.event_id) == target:
                    return env
            except Exception:
                continue
        return None

    def _build_ancestors(self, parent_event_id: str) -> list[str]:
        """Return ancestors of parent_event_id, ordered leaf-first (parent
        first, then grandparent, ..., root last). Duplicates are detected
        along the way but the returned list contains unique, ordered
        ancestor ids including the given parent id itself.

        The traversal follows causation_id links using the published log.
        If a cycle is discovered during traversal, we stop and return only
        the nodes visited so far. Callers can detect cycle by checking
        whether the new event_id is in ancestors.
        """
        ancestors: list[str] = []
        seen: set[str] = set()
        current_id: Optional[str] = str(parent_event_id) if parent_event_id is not None else None
        depth_safe = 0
        while current_id is not None and depth_safe < 10_000:
            if current_id in seen:
                break
            seen.add(current_id)
            ancestors.append(current_id)
            env = self._find_envelope_by_id(current_id)
            if env is None:
                break
            try:
                next_caus = env.causation_id
            except Exception:
                next_caus = None
            if next_caus is None:
                break
            next_str = str(next_caus)
            if next_str == current_id:
                break
            current_id = next_str
            depth_safe += 1
        return ancestors

    def publish_with_causation(
        self,
        envelope: CanonicalEventEnvelope,
        parent_event_id: str,
        *,
        causation_max_depth: int = 32,
    ) -> None:
        """Publish envelope as a child of parent_event_id.

        Steps:
        1. Build ancestors chain from parent via causation_id back to root.
        2. If envelope.event_id is already in ancestors → cycle: record
           E_CYCLE_DETECTED, do NOT publish, no exception.
        3. If len(ancestors) >= causation_max_depth → depth exceeded: record
           E_CAUSATION_DEPTH, do NOT publish, no exception.
        4. Copy correlation_id from parent if envelope's correlation_id is
           empty; otherwise preserve envelope's correlation_id.
        5. Set envelope.causation_id = parent_event_id (mutable-copy
           semantics if the envelope class exposes a setter or supports
           attribute assignment; otherwise rely on caller having prepared
           a writable envelope instance).
        6. Call normal publish() dispatch.
        """
        parent_str = str(parent_event_id) if parent_event_id is not None else ""

        # Step 1 — ancestors chain (tolerates missing parent — AD-24)
        ancestors = self._build_ancestors(parent_str)
        parent_env = self._find_envelope_by_id(parent_str) if parent_str else None

        # Step 2 — cycle detection
        try:
            new_id = str(envelope.event_id)
        except Exception:
            new_id = ""
        if new_id and new_id in ancestors:
            self._record_dlq(
                dlq_code="E_CYCLE_DETECTED",
                dlq_message=(
                    f"publish_with_causation aborted: event_id {new_id!r} already "
                    f"present in causation ancestors chain of parent {parent_str!r}"
                ),
                envelope=envelope,
                subscription_token_id=None,
                exc=None,
            )
            return

        # Step 3 — depth check
        if len(ancestors) >= int(causation_max_depth):
            self._record_dlq(
                dlq_code="E_CAUSATION_DEPTH",
                dlq_message=(
                    f"publish_with_causation aborted: ancestors depth {len(ancestors)} "
                    f">= max_depth {causation_max_depth} for parent {parent_str!r}"
                ),
                envelope=envelope,
                subscription_token_id=None,
                exc=None,
            )
            return

        # Step 4 — correlation propagation
        try:
            current_corr = getattr(envelope, "correlation_id", None)
            corr_needs_set = (current_corr is None) or (str(current_corr).strip() == "")
        except Exception:
            corr_needs_set = True
        if corr_needs_set and parent_env is not None:
            try:
                parent_corr = getattr(parent_env, "correlation_id", None)
                if parent_corr is not None:
                    envelope.correlation_id = parent_corr  # type: ignore[attr-defined]
            except Exception:
                pass

        # Step 4b — if correlation still empty, set to own event_id
        try:
            current_corr = getattr(envelope, "correlation_id", None)
            if (current_corr is None) or (str(current_corr).strip() == ""):
                if new_id:
                    envelope.correlation_id = envelope.event_id  # type: ignore[attr-defined]
        except Exception:
            pass

        # Step 5 — causation_id := parent_event_id
        try:
            envelope.causation_id = parent_event_id  # type: ignore[attr-defined]
        except Exception:
            pass

        # Step 6 — normal dispatch
        self.publish(envelope)

    def trace_causation_chain(self, leaf_event_id: str) -> list[str]:
        """Return the causation chain from leaf_event_id back to root.

        The returned list is ordered leaf-first: [leaf_id, parent_id,
        grandparent_id, ..., root_id]. If no envelope with leaf_event_id
        can be found in the published log, return [].
        """
        chain: list[str] = []
        seen: set[str] = set()
        current_id: Optional[str] = str(leaf_event_id) if leaf_event_id is not None else None
        while current_id is not None:
            if current_id in seen:
                break
            env = self._find_envelope_by_id(current_id)
            if env is None:
                break
            seen.add(current_id)
            chain.append(current_id)
            try:
                caus = env.causation_id
            except Exception:
                caus = None
            if caus is None:
                break
            caus_str = str(caus)
            if caus_str == current_id:
                break
            current_id = caus_str
        return chain

    def get_subscription_count(self) -> dict[str, int]:
        """Return a snapshot of typed subscription counts per event_type.

        Wildcard subscribers appear under key "*". Compat (legacy)
        subscribers are not reported; use len(self.subscribers.get(...))
        if you need compat counts separately.
        """
        out: dict[str, int] = {}
        for etype, bucket in self._typed_subscribers.items():
            out[etype] = len(bucket)
        return out

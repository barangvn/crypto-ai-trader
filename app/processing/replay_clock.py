from __future__ import annotations

from app.contracts import CanonicalEventEnvelope, SourceType


def set_clock_ref_for_replay(
    envelope: CanonicalEventEnvelope,
) -> CanonicalEventEnvelope:
    """
    Replay Clock Helper (AD-4, CAP-1).

    Ensures replay-sourced envelopes carry their event timestamp on
    clock_ref.replay so downstream components can distinguish replay
    (logical) time from wall-clock (ingest) time.

    Side effects:
      - If source_type is unset or empty, sets it to SourceType.REPLAY.
      - Sets envelope.clock_ref.replay = envelope.timestamp.

    Returns the (mutated) envelope for chaining.
    """
    if not envelope.source_type or envelope.source_type == "":
        envelope.source_type = SourceType.REPLAY
    if envelope.source_type == SourceType.REPLAY:
        envelope.clock_ref.replay = envelope.timestamp
    return envelope

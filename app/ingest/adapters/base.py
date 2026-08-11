from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator, Protocol, TypeAlias


RawFrame: TypeAlias = dict[str, Any]


class PublicExchangeAdapter(Protocol):
    """
    Public Exchange Adapter Port (AD-2, Hexagonal Architecture).

    This is the PUBLIC port only — no authentication or credential fields.
    Concrete implementations (e.g., ReplayBundleAdapter, BinanceWSAdapter)
    satisfy this Protocol by yielding raw provider-specific frames as
    dictionaries. No canonical types or normalization at this layer; that
    responsibility belongs to the Normalizer downstream.

    Returns Iterator[RawFrame] — flexible dicts with provider-specific keys.
    """

    def stream_market_events(
        self, fixture_ref: str | Path | None = None
    ) -> Iterator[RawFrame]:
        """
        Yield raw market event frames from the adapter's source.

        Args:
            fixture_ref: Optional reference to a fixture file or stream source
                (interpretation is adapter-specific).

        Yields:
            RawFrame dicts — raw provider-specific fields, NO canonical types.
        """
        ...

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterator

from app.ingest.adapters.base import PublicExchangeAdapter, RawFrame


class ReplayBundleAdapter(PublicExchangeAdapter):
    """
    Concrete Replay Bundle adapter that streams RawFrames from a CSV fixture.

    Implements PublicExchangeAdapter Protocol. Deterministic row-order
    iteration using csv.DictReader. Each row is yielded as a dict with
    an extra `_row_index` key (0-based) for stable ordering guarantees.

    No normalization is performed here — that is the Normalizer's job.
    """

    def __init__(
        self,
        fixture_path: str | Path,
        default_source: str = "replay.csv_default",
        csv_encoding: str = "utf-8",
    ) -> None:
        self.fixture_path: Path = Path(fixture_path)
        self.default_source: str = default_source
        self.csv_encoding: str = csv_encoding

    def stream_market_events(
        self, fixture_ref: str | Path | None = None
    ) -> Iterator[RawFrame]:
        """
        Open the CSV fixture and yield rows as RawFrame dicts in order.

        Each yielded dict has column names from the CSV header as keys,
        plus `_row_index` (0-based integer position) for stable ordering.
        """
        path: Path = self.fixture_path
        if fixture_ref is not None:
            path = Path(fixture_ref)

        with open(path, mode="r", encoding=self.csv_encoding, newline="") as f:
            reader: csv.DictReader[str] = csv.DictReader(f)
            idx: int = 0
            for row in reader:
                row_copy: dict[str, Any] = dict(row)
                row_copy["_row_index"] = idx
                yield row_copy
                idx += 1

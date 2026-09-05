"""S-BKT-02: Walk-Forward Multi-Fold orchestration (foundation).

Yeni ML training/fit CALGORITMASI YOK. Sadece window split + fold izolasyon
orchestration. Overlap-free + chronological + deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal
from typing import Any, Iterable, Sequence

from .run_metadata import BacktestWindowSplit, WindowSplit, SplitDataset


def _instant_from_event(event: Any) -> str:
    for attr in ("event_ts", "decision_ts", "snapshot_ts", "close_time", "market_ts"):
        v = getattr(event, attr, None)
        if isinstance(v, str) and v:
            return v
        if isinstance(event, dict):
            v = event.get(attr)
            if isinstance(v, str) and v:
                return v
    raise ValueError("BK_WF_INSTANT: event'ten zaman damgasi cikarilamadi")


def _valid_ratios(train: Decimal, validation: Decimal, test: Decimal) -> None:
    total = train + validation + test
    if total == 0:
        raise ValueError("BK_WF_RATIO: train+val+test toplami 0")
    if any(x <= 0 for x in (train, validation, test)):
        raise ValueError(f"BK_WF_RATIO: her ratio >0 olmali: train={train} val={validation} test={test}")


def _instant_cmp_key(a: str) -> tuple[int, int] | tuple[int, float] | tuple[int, str]:
    try:
        return (0, int(a))
    except (ValueError, TypeError):
        pass
    try:
        return (1, float(a))
    except (ValueError, TypeError):
        pass
    return (2, a)


@dataclass(frozen=True)
class WalkForwardConfig:
    n_folds: int = 5
    train_ratio: Decimal = Decimal("0.6")
    validation_ratio: Decimal = Decimal("0.2")
    test_ratio: Decimal = Decimal("0.2")
    inter_fold_gap_ms: int = 60_001
    intra_window_gap_ms: int = 60_001
    min_events_per_window: int = 3
    fold_id_prefix: str = "F"

    def to_sorted_dict(self) -> dict[str, Any]:
        return dict(
            sorted(
                {
                    "n_folds": self.n_folds,
                    "train_ratio": format(self.train_ratio, "f"),
                    "validation_ratio": format(self.validation_ratio, "f"),
                    "test_ratio": format(self.test_ratio, "f"),
                    "inter_fold_gap_ms": self.inter_fold_gap_ms,
                    "intra_window_gap_ms": self.intra_window_gap_ms,
                    "min_events_per_window": self.min_events_per_window,
                    "fold_id_prefix": self.fold_id_prefix,
                }.items()
            )
        )


def _validate_walk_forward_config(cfg: WalkForwardConfig) -> None:
    if cfg.n_folds < 1:
        raise ValueError(f"BK_WF_CONFIG: n_folds >=1 olmali: {cfg.n_folds}")
    if cfg.inter_fold_gap_ms < 0:
        raise ValueError(f"BK_WF_CONFIG: inter_fold_gap_ms >=0: {cfg.inter_fold_gap_ms}")
    if cfg.intra_window_gap_ms < 0:
        raise ValueError(f"BK_WF_CONFIG: intra_window_gap_ms >=0: {cfg.intra_window_gap_ms}")
    if cfg.min_events_per_window < 1:
        raise ValueError(f"BK_WF_CONFIG: min_events_per_window >=1: {cfg.min_events_per_window}")
    _valid_ratios(cfg.train_ratio, cfg.validation_ratio, cfg.test_ratio)


def _split_times(
    sorted_events: Sequence[Any],
    start_idx: int,
    end_idx: int,
    cfg: WalkForwardConfig,
) -> tuple[tuple[str, str], tuple[str, str], tuple[str, str], int, int, int]:
    seg_len = end_idx - start_idx
    if seg_len < cfg.min_events_per_window * 3:
        raise ValueError(
            f"BK_WF_SMALL: fold segmenti yeterince buyuk degil ({seg_len} events, min {cfg.min_events_per_window*3})"
        )
    total = cfg.train_ratio + cfg.validation_ratio + cfg.test_ratio
    tr = cfg.train_ratio / total
    vr = cfg.validation_ratio / total
    train_end = start_idx + max(1, int(seg_len * float(tr)))
    val_end = train_end + max(1, int(seg_len * float(vr)))
    val_end = min(val_end, end_idx - cfg.min_events_per_window)
    test_start = val_end
    if (end_idx - test_start) < cfg.min_events_per_window:
        raise ValueError("BK_WF_SMALL: test penceresi yeterince buyuk degil")
    intra = cfg.intra_window_gap_ms
    train_ts_start = _instant_from_event(sorted_events[start_idx])
    train_ts_end = _instant_from_event(sorted_events[train_end - 1])
    val_ts_start = _add_gap(train_ts_end, intra)
    val_ts_end = _instant_from_event(sorted_events[val_end - 1])
    test_ts_start = _add_gap(val_ts_end, intra)
    test_ts_end = _instant_from_event(sorted_events[end_idx - 1])
    if _cmp_instant(val_ts_start, train_ts_end) <= 0:
        raise ValueError("BK_WF_OVERLAP: train/val overlap")
    if _cmp_instant(test_ts_start, val_ts_end) <= 0:
        raise ValueError("BK_WF_OVERLAP: val/test overlap")
    return (
        (train_ts_start, train_ts_end),
        (val_ts_start, val_ts_end),
        (test_ts_start, test_ts_end),
        train_end,
        val_end,
        test_start,
    )


def _cmp_instant(a: str, b: str) -> int:
    try:
        ai = int(a)
        bi = int(b)
        if ai < bi:
            return -1
        if ai > bi:
            return 1
        return 0
    except (ValueError, TypeError):
        pass
    try:
        af = float(a)
        bf = float(b)
        if af < bf:
            return -1
        if af > bf:
            return 1
        return 0
    except (ValueError, TypeError):
        pass
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def _add_gap(instant: str, gap_ms: int) -> str:
    try:
        v = int(instant)
    except (TypeError, ValueError):
        try:
            dt = __import__("datetime").datetime.fromisoformat(instant)
            dt = dt + __import__("datetime").timedelta(milliseconds=gap_ms)
            return dt.isoformat()
        except Exception:
            return instant
    return str(v + gap_ms)


@dataclass(frozen=True)
class WalkForwardFoldDefinition:
    fold_id: str
    fold_index: int
    train: WindowSplit
    validation: WindowSplit
    test: WindowSplit
    segment_start_idx: int
    segment_end_idx: int

    def to_sorted_dict(self) -> dict[str, Any]:
        return dict(
            sorted(
                {
                    "fold_id": self.fold_id,
                    "fold_index": self.fold_index,
                    "train": self.train.to_sorted_dict(),
                    "validation": self.validation.to_sorted_dict(),
                    "test": self.test.to_sorted_dict(),
                    "segment_start_idx": self.segment_start_idx,
                    "segment_end_idx": self.segment_end_idx,
                }.items()
            )
        )

    def to_backtest_window_split(self) -> BacktestWindowSplit:
        return BacktestWindowSplit(
            train=self.train,
            validation=self.validation,
            test=self.test,
            overlap_free=True,
        )


def validate_no_inter_fold_overlap(folds: Sequence[WalkForwardFoldDefinition]) -> None:
    for i in range(1, len(folds)):
        prev_end = folds[i - 1].test.end_instant
        curr_start = folds[i].train.start_instant
        if _cmp_instant(curr_start, prev_end) <= 0:
            raise ValueError(
                f"BK_WF_INTER_OVERLAP: fold[{i-1}] test.end >= fold[{i}] train.start ({prev_end} vs {curr_start})"
            )


def generate_fold_splits(
    events: Iterable[Any],
    config: WalkForwardConfig | None = None,
) -> list[WalkForwardFoldDefinition]:
    cfg = config if config is not None else WalkForwardConfig()
    _validate_walk_forward_config(cfg)
    ev_list = sorted(events, key=lambda e: _instant_cmp_key(_instant_from_event(e)))
    if not ev_list:
        raise ValueError("BK_WF_EMPTY: events bos")
    total = len(ev_list)
    n = cfg.n_folds
    base = total // n
    rem = total % n
    folds: list[WalkForwardFoldDefinition] = []
    cursor = 0
    for i in range(n):
        seg_len = base + (1 if i < rem else 0)
        if seg_len < cfg.min_events_per_window * 3:
            raise ValueError(
                f"BK_WF_SMALL_FOLD: fold[{i}] segment {seg_len} events, min {cfg.min_events_per_window*3}"
            )
        start_idx = cursor
        end_idx = cursor + seg_len
        (tr_s, tr_e), (va_s, va_e), (te_s, te_e), train_end, val_end, test_start = _split_times(
            ev_list, start_idx, end_idx, cfg
        )
        if i > 0 and cfg.inter_fold_gap_ms > 0:
            prev_end = folds[i - 1].test.end_instant
            tr_s = max(tr_s, _add_gap(prev_end, cfg.inter_fold_gap_ms), key=_instant_cmp_key)
            if _cmp_instant(tr_s, tr_e) > 0:
                raise ValueError(f"BK_WF_GAP_TOO_BIG: fold[{i}] inter-fold gap train penceresini asiyor")
        fold_id = f"{cfg.fold_id_prefix}{i:03d}"
        train_event_count = train_end - start_idx
        val_event_count = val_end - train_end
        test_event_count = end_idx - test_start
        train_split = WindowSplit(
            dataset=SplitDataset.TRAIN,
            start_instant=tr_s,
            end_instant=tr_e,
            event_count=train_event_count,
        )
        val_split = WindowSplit(
            dataset=SplitDataset.VALIDATION,
            start_instant=va_s,
            end_instant=va_e,
            event_count=val_event_count,
        )
        test_split = WindowSplit(
            dataset=SplitDataset.TEST,
            start_instant=te_s,
            end_instant=te_e,
            event_count=test_event_count,
        )
        folds.append(
            WalkForwardFoldDefinition(
                fold_id=fold_id,
                fold_index=i,
                train=train_split,
                validation=val_split,
                test=test_split,
                segment_start_idx=start_idx,
                segment_end_idx=end_idx,
            )
        )
        cursor = end_idx
    validate_no_inter_fold_overlap(folds)
    return folds


def cut_events_for_fold(
    sorted_events: Sequence[Any],
    fold: WalkForwardFoldDefinition,
) -> tuple[list[Any], list[Any], list[Any]]:
    def _within(e: Any, w: WindowSplit) -> bool:
        ts = _instant_from_event(e)
        return w.start_instant <= ts <= w.end_instant

    train = [e for e in sorted_events if _within(e, fold.train)]
    val = [e for e in sorted_events if _within(e, fold.validation)]
    test = [e for e in sorted_events if _within(e, fold.test)]
    return train, val, test

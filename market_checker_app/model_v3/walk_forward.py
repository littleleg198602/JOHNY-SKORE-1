from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    embargo_periods: int


def make_walk_forward_windows(
    dates: pd.Series | list[pd.Timestamp],
    *,
    train_periods: int,
    validation_periods: int,
    test_periods: int,
    step_periods: int = 1,
    embargo_periods: int = 0,
    expanding: bool = True,
) -> list[WalkForwardWindow]:
    """Create chronological train/validation/test windows.

    ``dates`` should represent equally spaced prediction dates.  The embargo
    creates a gap after train and validation periods, which is required when
    labels use overlapping future-return windows.
    """

    if min(train_periods, validation_periods, test_periods, step_periods) <= 0:
        raise ValueError("Window and step sizes must be positive")
    if embargo_periods < 0:
        raise ValueError("embargo_periods must not be negative")

    unique_dates = pd.Series(pd.to_datetime(dates, utc=True, errors="raise")).drop_duplicates().sort_values().tolist()
    if len(unique_dates) < train_periods + validation_periods + test_periods + 2 * embargo_periods:
        return []

    windows: list[WalkForwardWindow] = []
    train_boundary = train_periods
    while True:
        train_start_index = 0 if expanding else train_boundary - train_periods
        train_end_index = train_boundary - 1
        validation_start_index = train_end_index + 1 + embargo_periods
        validation_end_index = validation_start_index + validation_periods - 1
        test_start_index = validation_end_index + 1 + embargo_periods
        test_end_index = test_start_index + test_periods - 1
        if test_end_index >= len(unique_dates):
            break
        windows.append(
            WalkForwardWindow(
                train_start=unique_dates[train_start_index],
                train_end=unique_dates[train_end_index],
                validation_start=unique_dates[validation_start_index],
                validation_end=unique_dates[validation_end_index],
                test_start=unique_dates[test_start_index],
                test_end=unique_dates[test_end_index],
                embargo_periods=embargo_periods,
            )
        )
        train_boundary += step_periods
    return windows


def select_window(
    frame: pd.DataFrame,
    window: WalkForwardWindow,
    split: Literal["train", "validation", "test"],
    *,
    date_col: str = "date",
) -> pd.DataFrame:
    """Select one named split from a panel using inclusive timestamps."""

    if date_col not in frame.columns:
        raise ValueError(f"Missing date column: {date_col}")
    dates = pd.to_datetime(frame[date_col], utc=True, errors="raise")
    ranges = {
        "train": (window.train_start, window.train_end),
        "validation": (window.validation_start, window.validation_end),
        "test": (window.test_start, window.test_end),
    }
    if split not in ranges:
        raise ValueError(f"Unknown split: {split}")
    start, end = ranges[split]
    return frame.loc[dates.between(start, end)].copy()

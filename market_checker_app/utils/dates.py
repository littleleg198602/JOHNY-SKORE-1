from __future__ import annotations

import datetime as dt


def now_local_naive() -> dt.datetime:
    return dt.datetime.now().replace(tzinfo=None)


def previous_week_monday_friday(today: dt.date) -> tuple[dt.date, dt.date]:
    this_monday = today - dt.timedelta(days=today.weekday())
    prev_monday = this_monday - dt.timedelta(days=7)
    prev_friday = prev_monday + dt.timedelta(days=4)
    return prev_monday, prev_friday

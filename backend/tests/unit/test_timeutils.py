from datetime import UTC, date, datetime, time, timedelta, timezone

import pandas as pd
import pytest

from app.domain.timeutils import (
    CutoffTimeError,
    cutoff_instant,
    cutoff_instants,
    delivery_day,
    local_hours,
    target_grid,
)

GATE = time(9, 50)


def test_january_window_has_744_hours() -> None:
    grid = target_grid(datetime(2026, 1, 2, tzinfo=UTC), datetime(2026, 2, 2, tzinfo=UTC))
    assert len(grid) == 744
    assert grid[0] == pd.Timestamp("2026-01-02T00:00Z")
    assert grid[-1] == pd.Timestamp("2026-02-01T23:00Z")  # end is exclusive
    assert str(grid.tz) == "UTC"


@pytest.mark.parametrize(
    ("start", "end", "msg"),
    [
        (datetime(2026, 1, 2), datetime(2026, 1, 3, tzinfo=UTC), "timezone-aware"),  # noqa: DTZ001 (naive on purpose)
        (datetime(2026, 1, 2, 0, 30, tzinfo=UTC), datetime(2026, 1, 3, tzinfo=UTC), "whole hour"),
        (datetime(2026, 1, 3, tzinfo=UTC), datetime(2026, 1, 3, tzinfo=UTC), "before end"),
    ],
)
def test_grid_rejects_bad_bounds(start: datetime, end: datetime, msg: str) -> None:
    with pytest.raises(ValueError, match=msg):
        target_grid(start, end)


def test_delivery_day_follows_uk_time() -> None:
    assert delivery_day(datetime(2026, 1, 10, 23, 30, tzinfo=UTC)) == date(2026, 1, 10)
    # 23:30Z on 30 Jun is 00:30 BST on 1 Jul.
    assert delivery_day(datetime(2026, 6, 30, 23, 30, tzinfo=UTC)) == date(2026, 7, 1)
    with pytest.raises(ValueError, match="timezone-aware"):
        delivery_day(datetime(2026, 1, 10))  # noqa: DTZ001 (naive on purpose)


def test_t5_dst_safe_cutoff() -> None:
    """DOMAIN.md §7 T5."""
    assert cutoff_instant(date(2026, 3, 30), GATE) == datetime(2026, 3, 29, 8, 50, tzinfo=UTC)
    assert cutoff_instant(date(2026, 3, 29), GATE) == datetime(2026, 3, 28, 9, 50, tzinfo=UTC)
    assert cutoff_instant(date(2026, 1, 10), GATE) == datetime(2026, 1, 9, 9, 50, tzinfo=UTC)


@pytest.mark.parametrize(
    "day", [date(2026, 3, 30), date(2026, 10, 26)]
)  # gate 01:30 local on 29 Mar (gap) and 25 Oct (overlap)
def test_cutoff_refuses_nonexistent_or_ambiguous_local_times(day: date) -> None:
    with pytest.raises(CutoffTimeError, match=f"delivery day {day}.*outside 01:00–01:59") as err:
        cutoff_instant(day, time(1, 30))
    assert err.value.delivery_day == day


def test_vectorised_cutoffs_match_scalar() -> None:
    targets = pd.Series(pd.to_datetime(["2026-03-29T22:00Z", "2026-03-29T23:00Z"], utc=True))
    # 22:00Z on 29 Mar is 23:00 BST (delivery 29 Mar); 23:00Z is 00:00 BST on 30 Mar.
    assert cutoff_instants(targets, GATE).tolist() == [
        pd.Timestamp("2026-03-28T09:50Z"),
        pd.Timestamp("2026-03-29T08:50Z"),
    ]


def test_local_hours() -> None:
    times = pd.Series(pd.to_datetime(["2026-01-10T12:00Z", "2026-06-01T12:00Z"], utc=True))
    assert local_hours(times).tolist() == [12, 13]


def test_whole_hour_is_checked_in_utc_not_the_input_offset() -> None:
    """05:00+05:30 is 23:30Z: not a whole UTC hour, so it must be rejected."""
    ist = timezone(timedelta(hours=5, minutes=30))
    with pytest.raises(ValueError, match="whole hour"):
        target_grid(datetime(2026, 1, 10, 5, tzinfo=ist), datetime(2026, 1, 10, 8, tzinfo=ist))
    # 05:30+05:30 is 00:00Z: fine.
    grid = target_grid(
        datetime(2026, 1, 10, 5, 30, tzinfo=ist), datetime(2026, 1, 10, 7, 30, tzinfo=ist)
    )
    assert list(grid) == [pd.Timestamp("2026-01-10T00:00Z"), pd.Timestamp("2026-01-10T01:00Z")]

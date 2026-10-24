"""Time maths for decisions. The backend's only use of Europe/London (AGENTS.md §5.4)."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

LONDON = ZoneInfo("Europe/London")


def target_grid(start: datetime, end: datetime) -> pd.DatetimeIndex:
    """Every whole UTC hour in [start, end), built from the bounds alone.

    The grid never comes from the data, so an hour with no forecast or no actual still gets a row
    (and a status) instead of silently disappearing.
    """
    for name, t in (("start", start), ("end", end)):
        if t.tzinfo is None:
            raise ValueError(f"{name} must be timezone-aware")
        utc = t.astimezone(UTC)  # +05:30 offsets exist: 05:00+05:30 is not a whole hour
        if (utc.minute, utc.second, utc.microsecond) != (0, 0, 0):
            raise ValueError(f"{name} must be a whole hour")
    if start >= end:
        raise ValueError("start must be before end")
    return pd.date_range(
        start.astimezone(UTC), end.astimezone(UTC), freq="h", inclusive="left", name="target_time"
    )


def delivery_day(t: datetime) -> date:
    """The UK calendar day an instant falls in. Also the settlement date of a half-hour."""
    if t.tzinfo is None:
        raise ValueError("t must be timezone-aware")
    return t.astimezone(LONDON).date()


def cutoff_instant(day: date, gate_closure_local: time) -> datetime:
    """Gate closure for delivery day `day`: `day − 1` at the local gate time, as a UTC instant.

    Computed in Europe/London so the UTC instant shifts by an hour across BST (DOMAIN.md §7 T5).
    A local time that doesn't exist (spring gap) or happens twice (autumn overlap) has no single
    answer, so it raises rather than guessing.
    """
    local = datetime.combine(day - timedelta(days=1), gate_closure_local, tzinfo=LONDON)
    if local.utcoffset() != local.replace(fold=1).utcoffset():
        raise ValueError(
            f"{gate_closure_local} on {local.date()} is ambiguous or doesn't exist in UK time"
        )
    return local.astimezone(UTC)


def cutoff_instants(targets: pd.Series, gate_closure_local: time) -> pd.Series:
    """`cutoff_instant(delivery_day(t))` for each target, computed once per distinct UK day."""
    days = targets.dt.tz_convert(LONDON).dt.date
    by_day = {d: cutoff_instant(d, gate_closure_local) for d in days.unique()}
    cutoffs: pd.Series = pd.to_datetime(days.map(by_day), utc=True)
    return cutoffs


def local_hours(times: pd.Series) -> pd.Series:
    """UK-local hour of day (0–23) of each instant."""
    hours: pd.Series = times.dt.tz_convert(LONDON).dt.hour
    return hours

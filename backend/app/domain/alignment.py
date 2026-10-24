"""Half-hourly actuals → one value per hourly target (ADR-005)."""

from typing import Literal

import pandas as pd

Aggregation = Literal["point", "hourly_mean"]


def hourly_actuals(
    actuals: pd.DataFrame, targets: pd.DatetimeIndex, aggregation: Aggregation
) -> pd.Series:
    """Actual MW per target hour, NaN where it can't be determined.

    `point`: the half-hour starting on the hour. `hourly_mean`: the mean of hh:00 and hh:30, and
    only if both exist. Averaging a single half-hour would quietly change what the number means.
    0 MW is a value: NaN only comes from a missing row.
    """
    by_start = actuals.set_index("start_time")["generation"]
    on_hour = by_start.reindex(targets)
    if aggregation == "point":
        return on_hour.rename("actual_mw")
    half_past = by_start.reindex(targets + pd.Timedelta(minutes=30)).set_axis(targets)
    return ((on_hour + half_past) / 2).rename("actual_mw")  # NaN + x is NaN: both required

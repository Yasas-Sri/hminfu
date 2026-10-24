"""The decision forecast: the latest forecast usable before each delivery day's gate closure."""

from datetime import time, timedelta

import numpy as np
import pandas as pd

from app.domain.metrics import signed_error
from app.domain.models import Coverage, PointStatus
from app.domain.timeutils import cutoff_instants

DECISION_COLUMNS = ["forecast_mw", "forecast_publish_time", "horizon_hours"]


def valid_forecasts(forecasts: pd.DataFrame, targets: pd.DatetimeIndex) -> pd.DataFrame:
    """Rows that forecast a grid target from before it (`start_time > publish_time`).

    Runs repeat past hours with frozen values; those echoes are not forecasts (AGENTS.md §5.2).
    No cutoff here: by-horizon analysis uses these directly.
    """
    fc = forecasts[forecasts["start_time"].isin(targets)]
    return fc[fc["start_time"] > fc["publish_time"]]


def eligible_forecasts(
    forecasts: pd.DataFrame,
    targets: pd.DatetimeIndex,
    gate_closure_local: time,
    publish_lag: timedelta,
) -> pd.DataFrame:
    """Valid forecasts usable by the cutoff: `publish_time + lag <= cutoff_instant` (DOMAIN.md §4).

    Nothing about accuracy is consulted, so a later, better forecast can never leak in.
    """
    if publish_lag < timedelta(0):
        raise ValueError("publish lag must be >= 0: a negative lag would admit post-cutoff runs")
    # Cutoffs come from the grid, so an invalid gate time fails even on days with no rows.
    by_target = cutoff_instants(targets.to_series(), gate_closure_local)
    fc = valid_forecasts(forecasts, targets)
    cutoff = fc["start_time"].map(by_target)
    return fc[fc["publish_time"] + publish_lag <= cutoff]


def decision_forecasts(
    forecasts: pd.DataFrame,
    targets: pd.DatetimeIndex,
    gate_closure_local: time,
    publish_lag: timedelta,
) -> pd.DataFrame:
    """One row per target: the eligible forecast with the latest publish_time (ADR-004).

    Indexed by the grid, so targets without an eligible forecast are kept as NaN rows.
    """
    eligible = eligible_forecasts(forecasts, targets, gate_closure_local, publish_lag)
    latest = (
        eligible.sort_values("publish_time", kind="stable")
        .drop_duplicates("start_time", keep="last")
        .set_index("start_time")
        .reindex(targets)
    )
    return pd.DataFrame(
        {
            "forecast_mw": latest["generation"],
            "forecast_publish_time": latest["publish_time"],
            "horizon_hours": (targets - latest["publish_time"]) / pd.Timedelta(hours=1),
        },
        index=targets,
    )


def decision_frame(decisions: pd.DataFrame, actual_mw: pd.Series) -> pd.DataFrame:
    """Join decision forecasts with aligned actuals (same grid index) and give each hour a status.

    `error_mw` is only non-null for `ok` hours: signed_error propagates NaN from either side.
    """
    if not decisions.index.equals(actual_mw.index):
        raise ValueError("decisions and actuals must be indexed by the same target grid")
    has_f = decisions["forecast_mw"].notna()
    has_a = actual_mw.notna()
    status = np.select(
        [has_f & has_a, has_f, has_a],
        [
            PointStatus.OK.value,
            PointStatus.MISSING_ACTUAL.value,
            PointStatus.MISSING_FORECAST.value,
        ],
        default=PointStatus.MISSING_BOTH.value,
    )
    out = decisions.assign(
        status=status,
        actual_mw=actual_mw,
        error_mw=signed_error(decisions["forecast_mw"], actual_mw),
    )
    out = out.rename_axis("target_time").reset_index()
    return out[["target_time", "status", "actual_mw", *DECISION_COLUMNS, "error_mw"]]


def coverage(frame: pd.DataFrame) -> Coverage:
    """Count hours per status. Every hour has exactly one status, so the counts sum to the grid."""
    counts = frame["status"].value_counts()
    return Coverage(
        target_hours=len(frame),
        **{s.value: int(counts.get(s.value, 0)) for s in PointStatus},
    )

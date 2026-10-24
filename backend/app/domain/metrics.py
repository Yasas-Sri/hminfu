"""Forecast error and its statistics (docs/ANALYSIS.md). All values in MW unless stated."""

from dataclasses import dataclass
from datetime import datetime
from typing import cast

import numpy as np
import pandas as pd

from app.domain.models import PointStatus
from app.domain.timeutils import local_hours


def signed_error(forecast: pd.Series, actual: pd.Series) -> pd.Series:
    """error = forecast − actual. The ONLY place the error is computed (ADR-006).

    > 0: over-forecast, less wind than predicted (potential shortfall).
    < 0: under-forecast, more wind than predicted (potential excess procurement).
    NaN on either side gives NaN, so a missing value can never look like a zero error.
    """
    return (forecast - actual).rename("error_mw")


@dataclass(frozen=True)
class Extreme:
    error_mw: float
    target_time: datetime


@dataclass(frozen=True)
class Quantiles:
    p10: float
    p50: float
    p90: float


@dataclass(frozen=True)
class HeadlineMetrics:
    """Every field except `n` is None when n == 0 (never 0: no data is not a perfect forecast)."""

    n: int
    mae_mw: float | None
    rmse_mw: float | None
    bias_mw: float | None
    nmae: float | None
    error_quantiles_mw: Quantiles | None
    p90_over_forecast_mw: float | None
    over_forecast_share: float | None  # share of hours with e > 0 (raw ratio)
    largest_over_forecast: Extreme | None
    largest_under_forecast: Extreme | None


def headline_metrics(frame: pd.DataFrame) -> HeadlineMetrics:
    """Headline statistics over the `ok` hours of a selection.decision_frame."""
    ok = frame[frame["status"] == PointStatus.OK].sort_values("target_time")
    e = ok["error_mw"].to_numpy(dtype=float)
    if len(e) == 0:
        return HeadlineMetrics(0, None, None, None, None, None, None, None, None, None)
    mean_actual = float(ok["actual_mw"].mean())
    p10, p50, p90 = (float(q) for q in np.quantile(e, [0.1, 0.5, 0.9], method="linear"))
    mae = float(np.mean(np.abs(e)))
    return HeadlineMetrics(
        n=len(e),
        mae_mw=mae,
        rmse_mw=float(np.sqrt(np.mean(e**2))),
        bias_mw=float(np.mean(e)),
        nmae=mae / mean_actual if mean_actual > 0 else None,
        error_quantiles_mw=Quantiles(p10, p50, p90),
        p90_over_forecast_mw=max(0.0, p90),
        over_forecast_share=float(np.mean(e > 0)),
        largest_over_forecast=_extreme(ok, positive=True),
        largest_under_forecast=_extreme(ok, positive=False),
    )


def by_hour(frame: pd.DataFrame) -> pd.DataFrame:
    """n, MAE and bias per UK-local hour 0–23 of `ok` hours. 24 rows, None if n = 0."""
    ok = frame[frame["status"] == PointStatus.OK]
    stats = _mae_bias(ok["error_mw"], local_hours(ok["target_time"]))
    out = stats.reindex(range(24)).rename_axis("hour_local").reset_index()
    out["n"] = out["n"].fillna(0).astype(int)
    return out.astype(object).where(out.notna(), None)


def by_forecast_level(frame: pd.DataFrame, bucket_mw: int) -> pd.DataFrame:
    """MAE and bias of `ok` hours grouped by the decision forecast's own level (MW).

    Buckets are half-open [k·b, (k+1)·b); empty buckets are omitted. Diagnostic only: shows
    whether the error depends on how much wind was forecast (DECISIONS.md, Data observations).
    """
    if bucket_mw < 1:
        raise ValueError("bucket_mw must be >= 1")
    ok = frame[frame["status"] == PointStatus.OK]
    level = (ok["forecast_mw"] // bucket_mw * bucket_mw).astype(int)
    stats = _mae_bias(ok["error_mw"], level).rename_axis("level_from_mw").reset_index()
    stats.insert(1, "level_to_mw", stats["level_from_mw"] + bucket_mw)
    return stats


def by_horizon(
    valid: pd.DataFrame, actual_mw: pd.Series, bucket_hours: int
) -> tuple[pd.DataFrame, int]:
    """MAE and bias by forecast age over all valid forecast rows, ignoring the cutoff (ANALYSIS.md).

    `valid`: selection.valid_forecasts rows (grid targets, no past echoes). `actual_mw`: aligned
    actuals on the grid. Buckets are half-open [k·b, (k+1)·b); empty buckets are omitted.
    Returns (rows, rows_used).
    """
    if bucket_hours < 1:
        raise ValueError("bucket_hours must be >= 1")
    actual = valid["start_time"].map(actual_mw)
    rows = valid.assign(actual=actual).dropna(subset=["actual"])
    error = signed_error(rows["generation"], rows["actual"])
    horizon = (rows["start_time"] - rows["publish_time"]).dt.total_seconds() / 3600
    if (horizon <= 0).any():
        raise ValueError("every horizon must be > 0: pass valid_forecasts (no past echoes)")
    bucket = (horizon // bucket_hours * bucket_hours).astype(int)  # half-open [k·b, (k+1)·b)
    stats = _mae_bias(error, bucket).rename_axis("horizon_from_h").reset_index()
    stats.insert(1, "horizon_to_h", stats["horizon_from_h"] + bucket_hours)
    return stats, len(rows)


def _mae_bias(error: pd.Series, key: pd.Series) -> pd.DataFrame:
    keys = key.to_numpy()
    g = error.groupby(keys)
    return pd.DataFrame(
        {"n": g.size(), "mae_mw": error.abs().groupby(keys).mean(), "bias_mw": g.mean()}
    )


def _extreme(ok: pd.DataFrame, positive: bool) -> Extreme | None:
    """Largest error of one sign; ties take the earliest target (rows are sorted by time)."""
    e = ok["error_mw"]
    side = ok[e > 0] if positive else ok[e < 0]
    if side.empty:
        return None
    errors = side["error_mw"].to_numpy(dtype=float)
    pos = int(errors.argmax() if positive else errors.argmin())  # argmax/argmin: first on ties
    when = cast(pd.Timestamp, side["target_time"].iat[pos]).to_pydatetime()
    return Extreme(float(errors[pos]), when)

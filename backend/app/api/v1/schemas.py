"""Public `/api/v1` contract. Source of truth for docs/API.md and the generated TS types.

Times are UTC datetimes (serialised with `Z`). `None` means "not available"; the reason is in
`status` (points) or `n` / `coverage` / `rows_used` (metrics).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Aggregation = Literal["point", "hourly_mean"]
Status = Literal["ok", "missing_actual", "missing_forecast", "missing_both"]


class _Model(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class TimeRange(_Model):
    from_: datetime = Field(alias="from")
    to: datetime


class SnapshotSummary(_Model):
    fetched_at: datetime
    forecast_rows: int
    actual_rows: int
    conflicts: int


class HealthResponse(_Model):
    status: Literal["ok"]
    snapshot: SnapshotSummary


class Defaults(_Model):
    cutoff_local: str
    publish_lag_minutes: int
    aggregation: Aggregation


class PublicationsPerDay(_Model):
    min: int
    median: float
    max: int


class MetaResponse(_Model):
    supported_target_range: TimeRange
    default_window: TimeRange
    defaults: Defaults
    data_as_of: datetime
    publications_per_day: PublicationsPerDay
    sign_convention: Literal["error = forecast − actual (MW)"]


class Coverage(_Model):
    """Mutually exclusive status counts; they always sum to `target_hours`."""

    target_hours: int
    ok: int
    missing_actual: int
    missing_forecast: int
    missing_both: int


class Meta(_Model):
    """Echo of the parameters behind an analytical response (ADR-011)."""

    from_: datetime = Field(alias="from")
    to: datetime
    cutoff_local: str
    cutoff_timezone: Literal["Europe/London"]
    publish_lag_minutes: int
    aggregation: Aggregation
    cutoff_applied: bool
    data_as_of: datetime
    coverage: Coverage | None


class SeriesPoint(_Model):
    target_time: datetime
    status: Status
    actual_mw: float | None
    forecast_mw: float | None
    forecast_publish_time: datetime | None
    horizon_hours: float | None
    error_mw: float | None = Field(description="forecast − actual (MW); only when status is ok")


class ActualHalfHour(_Model):
    start_time: datetime
    actual_mw: float


class SeriesResponse(_Model):
    meta: Meta
    points: list[SeriesPoint]
    actuals_halfhourly: list[ActualHalfHour]


class Quantiles(_Model):
    p10: float
    p50: float
    p90: float


class Extreme(_Model):
    error_mw: float
    target_time: datetime


class MetricsResponse(_Model):
    meta: Meta
    n: int
    mae_mw: float | None
    rmse_mw: float | None
    bias_mw: float | None
    nmae: float | None
    error_quantiles_mw: Quantiles | None
    p90_over_forecast_mw: float | None
    over_forecast_share: float | None
    largest_over_forecast: Extreme | None
    largest_under_forecast: Extreme | None


class ByHourRow(_Model):
    hour_local: int
    n: int
    mae_mw: float | None
    bias_mw: float | None


class ByHourResponse(_Model):
    meta: Meta
    rows: list[ByHourRow]


class ByHorizonRow(_Model):
    horizon_from_h: int
    horizon_to_h: int
    n: int
    mae_mw: float
    bias_mw: float


class ByHorizonResponse(_Model):
    meta: Meta
    bucket_hours: int
    rows_used: int
    rows: list[ByHorizonRow]


class InternalError(_Model):
    detail: Literal["Internal error"]
    request_id: str

"""Domain vocabulary shared by selection, metrics and (from M3) the API layer."""

from dataclasses import dataclass
from enum import StrEnum


class PointStatus(StrEnum):
    OK = "ok"
    MISSING_ACTUAL = "missing_actual"
    MISSING_FORECAST = "missing_forecast"
    MISSING_BOTH = "missing_both"


@dataclass(frozen=True)
class Coverage:
    """Status counts. Mutually exclusive, so they always sum to `target_hours`."""

    target_hours: int
    ok: int
    missing_actual: int
    missing_forecast: int
    missing_both: int


# ponytail: one decision point = one row of selection.decision_frame (columns: target_time, status,
# actual_mw, forecast_mw, forecast_publish_time, horizon_hours, error_mw). No per-row dataclass;
# add one if M3's schema mapping wants it.

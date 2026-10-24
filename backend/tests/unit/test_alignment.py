import math
from datetime import UTC, datetime

from app.domain.alignment import hourly_actuals
from app.domain.timeutils import target_grid
from tests.builders import actuals

GRID = target_grid(datetime(2026, 1, 10, 16, tzinfo=UTC), datetime(2026, 1, 10, 19, tzinfo=UTC))
ACT = actuals(
    ("2026-01-10T16:00Z", 8222),
    ("2026-01-10T16:30Z", 8121),
    ("2026-01-10T17:00Z", 0),  # zero is a value
    ("2026-01-10T17:30Z", 0),
    ("2026-01-10T18:00Z", 500),  # 18:30 missing
)


def test_point_uses_the_half_hour_starting_on_the_hour() -> None:
    assert hourly_actuals(ACT, GRID, "point").tolist() == [8222.0, 0.0, 500.0]


def test_hourly_mean_needs_both_half_hours() -> None:
    values = hourly_actuals(ACT, GRID, "hourly_mean").tolist()
    assert values[:2] == [8171.5, 0.0]
    assert math.isnan(values[2])


def test_missing_rows_are_nan_not_zero() -> None:
    values = hourly_actuals(ACT.iloc[0:0], GRID, "point")
    assert values.isna().all()
    assert list(values.index) == list(GRID)

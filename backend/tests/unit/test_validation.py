from datetime import UTC, datetime
from typing import Any

import pandas as pd
import pytest

from app.data import validation as v


def fc(publish: str, start: str, gen: Any = 100) -> dict[str, Any]:
    return {"dataset": "WINDFOR", "publishTime": publish, "startTime": start, "generation": gen}


def act(
    start: str, gen: Any, publish: str = "2026-01-10T23:59:00Z", fuel: str = "WIND"
) -> dict[str, Any]:
    return {"publishTime": publish, "startTime": start, "fuelType": fuel, "generation": gen}


def test_parse_forecasts_gives_utc_aware_frame() -> None:
    df = v.parse_forecasts([fc("2026-01-09T09:30:00Z", "2026-01-10T16:00:00+00:00", 6526)])
    assert list(df.columns) == v.COLUMNS
    assert str(df["start_time"].dt.tz) == "UTC"
    assert df.loc[0, "generation"] == 6526.0


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        ({"publishTime": "2026-01-09T09:30:00Z", "generation": 1}, "missing"),
        (fc("2026-01-09T09:30:00Z", "2026-01-10T16:00:00Z", None), "missing"),
        (fc("2026-01-09T09:30:00Z", "2026-01-10T16:00:00Z", "6526"), "non-numeric"),
        (fc("2026-01-09T09:30:00Z", "2026-01-10T16:00:00Z", True), "non-numeric"),
        (fc("2026-01-09T09:30:00Z", "2026-01-10T16:00:00Z", float("nan")), "non-numeric"),
        (fc("2026-01-09T09:30:00", "2026-01-10T16:00:00Z"), "timezone-aware"),
        (fc("not a time", "2026-01-10T16:00:00Z"), "timezone-aware"),
    ],
)
def test_bad_rows_fail_loudly(row: dict[str, Any], reason: str) -> None:
    with pytest.raises(v.SnapshotValidationError, match=reason):
        v.parse_forecasts([row])


def test_zero_generation_is_a_value() -> None:
    df = v.parse_forecasts([fc("2026-01-09T09:30:00Z", "2026-01-10T16:00:00Z", 0)])
    assert len(df) == 1
    assert df.loc[0, "generation"] == 0.0


def test_actuals_keep_wind_only() -> None:
    df, dropped = v.parse_actuals(
        [act("2026-01-10T16:00:00Z", 8222), act("2026-01-10T16:00:00Z", 5, fuel="CCGT")]
    )
    assert dropped == 1
    assert df["generation"].tolist() == [8222.0]


def test_past_echoes_are_dropped_and_counted() -> None:
    df = v.parse_forecasts(
        [
            fc("2026-01-09T09:30:00Z", "2026-01-09T09:00:00Z"),  # past
            fc("2026-01-09T09:30:00Z", "2026-01-09T09:30:00Z"),  # == publish: still not a forecast
            fc("2026-01-09T09:30:00Z", "2026-01-09T10:00:00Z"),
        ]
    )
    kept, dropped = v.drop_past_echoes(df)
    assert dropped == 2
    assert kept["start_time"].tolist() == [pd.Timestamp("2026-01-09T10:00:00Z")]


def test_identical_forecast_duplicates_are_dropped_silently() -> None:
    row = fc("2026-01-09T09:30:00Z", "2026-01-10T16:00:00Z", 6526)
    df, conflicts, dupes = v.dedupe_forecasts(v.parse_forecasts([row, row]))
    assert (len(df), conflicts, dupes) == (1, [], 1)


def test_conflicting_forecasts_are_reported_and_removed() -> None:
    rows = [
        fc("2026-01-09T09:30:00Z", "2026-01-10T16:00:00Z", 6526),
        fc("2026-01-09T09:30:00Z", "2026-01-10T16:00:00Z", 7000),
        fc("2026-01-09T09:30:00Z", "2026-01-10T17:00:00Z", 6600),
    ]
    df, conflicts, _ = v.dedupe_forecasts(v.parse_forecasts(rows))
    assert conflicts == [
        v.ForecastConflict("2026-01-09T09:30:00Z", "2026-01-10T16:00:00Z", [6526.0, 7000.0])
    ]
    assert df["start_time"].tolist() == [pd.Timestamp("2026-01-10T17:00:00Z")]


def test_actual_revisions_keep_latest_publish_time() -> None:
    rows = [
        act("2026-01-10T16:00:00Z", 8000, publish="2026-01-10T16:30:00Z"),
        act("2026-01-10T16:00:00Z", 8222, publish="2026-01-11T09:00:00Z"),
        act("2026-01-10T16:30:00Z", 8121, publish="2026-01-10T17:00:00Z"),
        act("2026-01-10T16:30:00Z", 8121, publish="2026-01-10T17:00:00Z"),  # identical repeat
    ]
    df, revised = v.dedupe_actuals(v.parse_actuals(rows)[0])
    assert revised == 1
    assert df["generation"].tolist() == [8222.0, 8121.0]


def test_actual_tie_with_different_values_fails() -> None:
    rows = [act("2026-01-10T16:00:00Z", 1), act("2026-01-10T16:00:00Z", 2)]
    with pytest.raises(v.SnapshotValidationError, match="equal publishTime"):
        v.dedupe_actuals(v.parse_actuals(rows)[0])


def test_missing_times_uses_an_independent_grid() -> None:
    present = pd.Series(pd.to_datetime(["2026-01-10T00:00:00Z", "2026-01-10T01:00:00Z"]))
    start, end = datetime(2026, 1, 10, tzinfo=UTC), datetime(2026, 1, 10, 1, 30, tzinfo=UTC)
    assert v.missing_times(present, start, end, "30min") == ["2026-01-10T00:30:00Z"]


def test_publication_stats_and_max_horizon() -> None:
    df = v.parse_forecasts(
        [
            fc("2026-01-09T02:30:00Z", "2026-01-11T21:00:00Z"),
            fc("2026-01-09T02:30:00Z", "2026-01-10T00:00:00Z"),
            fc("2026-01-09T09:30:00Z", "2026-01-10T00:00:00Z"),
            fc("2026-01-10T02:30:00Z", "2026-01-11T00:00:00Z"),
        ]
    )
    assert v.publications_per_day(df) == {"2026-01-09": 2, "2026-01-10": 1}
    assert v.publish_time_of_day_histogram(df) == {"02:30": 2, "09:30": 1}
    assert v.max_horizon_hours(df) == 66.5
    assert v.max_horizon_hours(df.iloc[0:0]) is None


@pytest.mark.parametrize(
    ("start", "freq"), [("2026-01-10T16:30:00Z", "1h"), ("2026-01-10T16:15:00Z", "30min")]
)
def test_off_grid_start_times_fail_loudly(start: str, freq: str) -> None:
    df = v.parse_forecasts([fc("2026-01-09T09:30:00Z", start)])
    with pytest.raises(v.SnapshotValidationError, match="off the"):
        v.check_cadence(df, "TEST", freq)


def test_on_grid_start_times_pass() -> None:
    df = v.parse_forecasts([fc("2026-01-09T09:30:00Z", "2026-01-10T16:30:00Z")])
    v.check_cadence(df, "FUELHH", "30min")

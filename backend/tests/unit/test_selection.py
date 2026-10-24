"""DOMAIN.md §7: T1 (real data, both lags), T2, T3, T4, T6, plus lag behaviour on real data."""

from datetime import time, timedelta
from pathlib import Path

import pandas as pd
import pytest

from app.data.repository import read_rows
from app.domain.alignment import hourly_actuals
from app.domain.metrics import headline_metrics
from app.domain.models import Coverage
from app.domain.selection import (
    coverage,
    decision_forecasts,
    decision_frame,
    eligible_forecasts,
    valid_forecasts,
)
from app.domain.timeutils import target_grid
from tests.builders import actuals, forecasts, ts

GATE = time(9, 50)
LAG0, LAG60 = timedelta(0), timedelta(minutes=60)
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "snapshot"


def grid(start: str, hours: int) -> pd.DatetimeIndex:
    t = ts(start).to_pydatetime()
    return target_grid(t, t + timedelta(hours=hours))


def frame(
    fc: pd.DataFrame, act: pd.DataFrame, targets: pd.DatetimeIndex, lag: timedelta = LAG0
) -> pd.DataFrame:
    decisions = decision_forecasts(fc, targets, GATE, lag)
    return decision_frame(decisions, hourly_actuals(act, targets, "point"))


@pytest.fixture(scope="module")
def real() -> tuple[pd.DataFrame, pd.DataFrame]:
    return read_rows(FIXTURE / "forecasts.json.gz"), read_rows(FIXTURE / "actuals.json.gz")


@pytest.mark.parametrize(
    ("lag", "publish", "horizon"),
    [(LAG0, "2026-01-09T09:30Z", 30.5), (LAG60, "2026-01-09T07:30Z", 32.5)],
)
def test_t1_golden_example(
    real: tuple[pd.DataFrame, pd.DataFrame], lag: timedelta, publish: str, horizon: float
) -> None:
    """Same 6,526 MW at both lags but from different runs: assert the source, not only the MW."""
    row = frame(*real, grid("2026-01-10T16:00Z", 1), lag).iloc[0]
    assert row["status"] == "ok"
    assert row["forecast_publish_time"] == ts(publish)
    assert row["forecast_mw"] == 6526
    assert row["horizon_hours"] == horizon
    assert row["actual_mw"] == 8222
    assert row["error_mw"] == -1696  # under-forecast


def test_lag_changes_decisions_on_real_data(real: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    targets = grid("2026-01-09T00:00Z", 48)
    at0, at60 = frame(*real, targets, LAG0), frame(*real, targets, LAG60)
    assert (at0["status"] == "ok").all() and (at60["status"] == "ok").all()
    # Every day the 09:30 run is usable at lag 0 but not at lag 60 (available 10:30 > 09:50).
    assert (at0["forecast_publish_time"].dt.strftime("%H:%M") == "09:30").all()
    assert (at60["forecast_publish_time"].dt.strftime("%H:%M") == "07:30").all()
    # ...and it changes the forecast value for at least one hour (delivery day 9 Jan).
    assert (at0["forecast_mw"] != at60["forecast_mw"]).any()


def test_t2_no_leakage_even_when_later_forecast_is_better() -> None:
    fc = forecasts(
        ("2026-01-09T07:30Z", "2026-01-10T12:00Z", 6400),
        ("2026-01-09T09:30Z", "2026-01-10T12:00Z", 6500),
        ("2026-01-09T10:30Z", "2026-01-10T12:00Z", 8000),  # perfect, but after the cutoff
    )
    row = frame(fc, actuals(("2026-01-10T12:00Z", 8000)), grid("2026-01-10T12:00Z", 1)).iloc[0]
    assert (row["forecast_mw"], row["forecast_publish_time"]) == (6500, ts("2026-01-09T09:30Z"))


def test_cutoff_is_inclusive_of_the_lagged_availability_time() -> None:
    fc = forecasts(
        ("2026-01-09T09:20Z", "2026-01-10T12:00Z", 1),  # + 30 min = 09:50 = cutoff: eligible
        ("2026-01-09T09:21Z", "2026-01-10T12:00Z", 2),  # + 30 min = 09:51: too late
    )
    decisions = decision_forecasts(fc, grid("2026-01-10T12:00Z", 1), GATE, timedelta(minutes=30))
    assert decisions["forecast_mw"].tolist() == [1]


def test_dst_cutoff_applies_to_selection() -> None:
    """Delivery 30 Mar (BST): cutoff is 08:50Z, so a 09:00Z run is already too late."""
    fc = forecasts(
        ("2026-03-29T08:30Z", "2026-03-30T12:00Z", 1),
        ("2026-03-29T09:00Z", "2026-03-30T12:00Z", 2),
    )
    decisions = decision_forecasts(fc, grid("2026-03-30T12:00Z", 1), GATE, LAG0)
    assert decisions["forecast_mw"].tolist() == [1]


def test_t3_no_silent_loss_of_missing_hours() -> None:
    fc = forecasts(
        ("2026-01-09T09:30Z", "2026-01-10T00:00Z", 100),  # h1: ok
        ("2026-01-09T11:30Z", "2026-01-10T01:00Z", 999),  # h2: only a post-cutoff forecast
        ("2026-01-09T09:30Z", "2026-01-10T02:00Z", 300),  # h3: forecast, no actual
    )
    act = actuals(("2026-01-10T00:00Z", 150), ("2026-01-10T01:00Z", 200))  # h4: nothing
    out = frame(fc, act, grid("2026-01-10T00:00Z", 4))

    assert out["status"].tolist() == ["ok", "missing_forecast", "missing_actual", "missing_both"]
    assert out["target_time"].tolist() == list(grid("2026-01-10T00:00Z", 4))
    assert coverage(out) == Coverage(
        target_hours=4, ok=1, missing_actual=1, missing_forecast=1, missing_both=1
    )
    # Field presence by status (API.md): only ok has an error.
    assert out["error_mw"].notna().tolist() == [True, False, False, False]
    assert out.loc[1, ["actual_mw"]].notna().all()
    assert out.loc[1, ["forecast_mw", "forecast_publish_time", "horizon_hours"]].isna().all()
    assert pd.isna(out.loc[2, "actual_mw"])
    assert out.loc[2, ["forecast_mw", "forecast_publish_time", "horizon_hours"]].notna().all()
    # Metrics use only h1.
    m = headline_metrics(out)
    assert (m.n, m.mae_mw, m.bias_mw) == (1, 50.0, -50.0)


def test_t4_zero_is_preserved() -> None:
    fc = forecasts(("2026-01-09T09:30Z", "2026-01-10T00:00Z", 0))
    out = frame(fc, actuals(("2026-01-10T00:00Z", 0)), grid("2026-01-10T00:00Z", 1))
    assert out.loc[0, "status"] == "ok"
    assert out.loc[0, "error_mw"] == 0
    m = headline_metrics(out)
    assert (m.n, m.mae_mw) == (1, 0.0)


def test_valid_forecasts_drop_echoes_and_off_grid_targets() -> None:
    """By-horizon has no cutoff, so this filter is the only thing keeping echoes out of it."""
    fc = forecasts(
        ("2026-01-10T00:00Z", "2026-01-10T00:00Z", 1),  # echo (start == publish)
        ("2026-01-10T01:00Z", "2026-01-10T00:00Z", 2),  # echo (start < publish)
        ("2026-01-09T09:30Z", "2026-01-10T00:00Z", 3),  # valid
        ("2026-01-09T09:30Z", "2026-01-11T00:00Z", 4),  # target outside the grid
    )
    assert valid_forecasts(fc, grid("2026-01-10T00:00Z", 1))["generation"].tolist() == [3]


def test_t6_past_echoes_are_never_selected() -> None:
    """Echoes are published on/after their target, i.e. after any D−1 cutoff, so they also fail
    eligibility; valid_forecasts drops them first anyway."""
    fc = forecasts(
        ("2026-01-10T00:00Z", "2026-01-10T00:00Z", 1),  # start == publish
        ("2026-01-10T01:00Z", "2026-01-10T00:00Z", 2),  # start < publish
    )
    out = frame(fc, actuals(("2026-01-10T00:00Z", 5)), grid("2026-01-10T00:00Z", 1))
    assert out.loc[0, "status"] == "missing_forecast"


def test_empty_inputs_still_give_one_row_per_hour() -> None:
    out = frame(forecasts(), actuals(), grid("2026-01-10T00:00Z", 3))
    assert out["status"].tolist() == ["missing_both"] * 3
    assert coverage(out).target_hours == 3


def test_negative_lag_is_rejected() -> None:
    """A negative lag would make post-cutoff runs eligible (leakage), so the domain refuses it."""
    with pytest.raises(ValueError, match="lag"):
        eligible_forecasts(forecasts(), grid("2026-01-10T00:00Z", 1), GATE, timedelta(hours=-3))


def test_decision_frame_requires_the_same_grid() -> None:
    decisions = decision_forecasts(forecasts(), grid("2026-01-10T00:00Z", 2), GATE, LAG0)
    other = hourly_actuals(actuals(), grid("2026-01-11T00:00Z", 2), "point")
    with pytest.raises(ValueError, match="same target grid"):
        decision_frame(decisions, other)

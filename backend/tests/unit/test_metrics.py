"""Hand-computed values from docs/ANALYSIS.md."""

import math

import pandas as pd
import pytest

from app.domain.metrics import (
    Extreme,
    Quantiles,
    by_horizon,
    by_hour,
    headline_metrics,
    signed_error,
)
from tests.builders import forecasts, ts


def ok_frame(errors: list[float], actual: float = 8000.0) -> pd.DataFrame:
    times = pd.date_range("2026-01-10T00:00Z", periods=len(errors), freq="h")
    return pd.DataFrame(
        {
            "target_time": times,
            "status": "ok",
            "actual_mw": actual,
            "forecast_mw": [actual + e for e in errors],
            "error_mw": errors,
        }
    )


def test_signed_error_is_forecast_minus_actual() -> None:
    e = signed_error(pd.Series([6526.0, 9000.0]), pd.Series([8222.0, 8000.0]))
    assert e.tolist() == [-1696.0, 1000.0]  # under-forecast, over-forecast


def test_signed_error_propagates_missing() -> None:
    assert math.isnan(signed_error(pd.Series([1.0]), pd.Series([float("nan")]))[0])


def test_headline_hand_computed() -> None:
    m = headline_metrics(ok_frame([168, -813, -1481, -1696]))
    assert m.n == 4
    assert m.mae_mw == 1039.5
    assert m.bias_mw == -955.5
    assert m.rmse_mw == pytest.approx(1199.89, abs=0.01)
    assert m.nmae == pytest.approx(1039.5 / 8000)
    # numpy linear quantiles of sorted [-1696, -1481, -813, 168]
    assert m.error_quantiles_mw == Quantiles(
        p10=pytest.approx(-1631.5), p50=pytest.approx(-1147.0), p90=pytest.approx(-126.3)
    )
    assert m.p90_over_forecast_mw == 0.0  # p90 < 0 is clamped
    assert m.largest_over_forecast == Extreme(168.0, ts("2026-01-10T00:00Z").to_pydatetime())
    assert m.largest_under_forecast == Extreme(-1696.0, ts("2026-01-10T03:00Z").to_pydatetime())


def test_p90_over_forecast_positive() -> None:
    m = headline_metrics(ok_frame([float(x) for x in range(1, 11)]))
    assert m.p90_over_forecast_mw == pytest.approx(9.1)


def test_extremes_absent_for_missing_sign() -> None:
    assert headline_metrics(ok_frame([-5, -1])).largest_over_forecast is None
    m = headline_metrics(ok_frame([0]))
    assert (m.mae_mw, m.largest_over_forecast, m.largest_under_forecast) == (0.0, None, None)


def test_extreme_ties_take_earliest_target() -> None:
    m = headline_metrics(ok_frame([5, 5, -7, -7]))
    assert m.largest_over_forecast == Extreme(5.0, ts("2026-01-10T00:00Z").to_pydatetime())
    assert m.largest_under_forecast == Extreme(-7.0, ts("2026-01-10T02:00Z").to_pydatetime())


def test_no_ok_hours_gives_nulls_not_zeros() -> None:
    frame = ok_frame([1.0]).assign(status="missing_actual", error_mw=float("nan"))
    m = headline_metrics(frame)
    assert m.n == 0
    assert all(v is None for k, v in vars(m).items() if k != "n")


def test_only_ok_hours_count() -> None:
    frame = pd.concat(
        [ok_frame([10.0]), ok_frame([float("nan")]).assign(status="missing_actual")],
        ignore_index=True,
    )
    assert headline_metrics(frame).n == 1


def test_nmae_null_when_mean_actual_not_positive() -> None:
    assert headline_metrics(ok_frame([0.0], actual=0.0)).nmae is None


def test_by_hour_has_24_rows_with_null_metrics_for_empty_hours() -> None:
    rows = by_hour(ok_frame([10, -20]))  # UTC 00:00 and 01:00 = UK 00, 01 in January
    assert len(rows) == 24
    assert rows.loc[0].to_dict() == {"hour_local": 0, "n": 1, "mae_mw": 10.0, "bias_mw": 10.0}
    assert rows.loc[1, "bias_mw"] == -20.0
    assert rows.loc[5].to_dict() == {"hour_local": 5, "n": 0, "mae_mw": None, "bias_mw": None}


def test_by_hour_uses_uk_local_hour() -> None:
    frame = ok_frame([3.0]).assign(target_time=[ts("2026-06-01T12:00Z")])
    rows = by_hour(frame)
    assert rows.loc[13, "n"] == 1 and rows.loc[12, "n"] == 0


def test_by_horizon_half_open_buckets_ignore_cutoff_and_skip_empty() -> None:
    fc = forecasts(
        ("2026-01-10T11:30Z", "2026-01-10T12:00Z", 110),  # 0.5 h  → [0, 6)
        ("2026-01-10T06:00Z", "2026-01-10T12:00Z", 90),  # 6 h exactly → [6, 12)
        ("2026-01-09T12:00Z", "2026-01-10T12:00Z", 100),  # 24 h → [24, 30)
        ("2026-01-09T12:00Z", "2026-01-10T13:00Z", 100),  # no actual for 13:00: excluded
    )
    actual = pd.Series(
        [100.0, float("nan")],
        index=pd.DatetimeIndex([ts("2026-01-10T12:00Z"), ts("2026-01-10T13:00Z")]),
    )
    rows, used = by_horizon(fc, actual, bucket_hours=6)
    assert used == 3
    assert rows.to_dict("records") == [
        {"horizon_from_h": 0, "horizon_to_h": 6, "n": 1, "mae_mw": 10.0, "bias_mw": 10.0},
        {"horizon_from_h": 6, "horizon_to_h": 12, "n": 1, "mae_mw": 10.0, "bias_mw": -10.0},
        {"horizon_from_h": 24, "horizon_to_h": 30, "n": 1, "mae_mw": 0.0, "bias_mw": 0.0},
    ]


def test_by_horizon_rejects_echoes_and_bad_bucket() -> None:
    echo = forecasts(("2026-01-10T13:00Z", "2026-01-10T12:00Z", 1))
    actual = pd.Series([1.0], index=pd.DatetimeIndex([ts("2026-01-10T12:00Z")]))
    with pytest.raises(ValueError, match="horizon"):
        by_horizon(echo, actual, bucket_hours=6)
    with pytest.raises(ValueError, match="bucket_hours"):
        by_horizon(forecasts(), actual, bucket_hours=0)

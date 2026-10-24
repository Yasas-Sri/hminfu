"""The fixture is cut from the real snapshot; pin the DOMAIN.md §7 T1 raw values it must contain."""

from pathlib import Path

import pandas as pd

from app.data.repository import read_rows

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "snapshot"
TARGET = pd.Timestamp("2026-01-10T16:00:00Z")


def test_t1_raw_values_are_in_the_fixture() -> None:
    fc = read_rows(FIXTURE / "forecasts.json.gz")
    act = read_rows(FIXTURE / "actuals.json.gz")

    assert act.loc[act["start_time"] == TARGET, "generation"].tolist() == [8222.0]
    runs = fc[(fc["start_time"] == TARGET) & (fc["publish_time"].dt.day == 9)]
    assert dict(
        zip(runs["publish_time"].dt.strftime("%H:%M"), runs["generation"], strict=True)
    ) == {
        "02:30": 6579.0,
        "04:30": 6604.0,
        "07:30": 6526.0,
        "09:30": 6526.0,
        "11:30": 7469.0,
        "15:30": 6844.0,
        "18:30": 6698.0,
        "22:30": 6976.0,
    }


def test_more_real_pairs_from_the_0930_run() -> None:
    fc = read_rows(FIXTURE / "forecasts.json.gz")
    act = read_rows(FIXTURE / "actuals.json.gz").set_index("start_time")["generation"]
    run = fc[fc["publish_time"] == pd.Timestamp("2026-01-09T09:30:00Z")].set_index("start_time")
    for hour, forecast, actual in [(12, 7945, 7777), (13, 7325, 8138), (15, 6627, 8108)]:
        t = pd.Timestamp(f"2026-01-10T{hour:02d}:00:00Z")
        assert (run.loc[t, "generation"], act[t]) == (forecast, actual)

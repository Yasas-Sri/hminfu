import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.config import Settings
from app.data import validation as v
from app.data.repository import read_rows
from scripts import ingest

BASE = "https://elexon.test/api"
START = datetime(2026, 1, 10, tzinfo=UTC)


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def settings(tmp_path: Path, **kw: Any) -> Settings:
    defaults: dict[str, Any] = {
        "window_start": START,
        "window_end": START + timedelta(hours=2),
        "elexon_base_url": BASE,
        "http_backoff_base_s": 0,
        "forecast_lookback_hours": 96,
        "horizon_margin_hours": 6,
        "snapshot_dir": tmp_path / "snapshot",
    }
    return Settings(**(defaults | kw))


def fake_elexon(windfor: list[dict[str, Any]], fuelhh: list[dict[str, Any]]) -> None:
    def windfor_chunk(request: httpx.Request) -> httpx.Response:
        lo, hi = request.url.params["publishDateTimeFrom"], request.url.params["publishDateTimeTo"]
        return httpx.Response(200, json=[r for r in windfor if lo <= r["publishTime"] <= hi])

    def fuelhh_day(request: httpx.Request) -> httpx.Response:
        day = request.url.params["settlementDateFrom"]
        return httpx.Response(200, json=[r for r in fuelhh if r["startTime"].startswith(day)])

    respx.get(f"{BASE}/datasets/WINDFOR/stream").mock(side_effect=windfor_chunk)
    respx.get(f"{BASE}/datasets/FUELHH/stream").mock(side_effect=fuelhh_day)


def windfor(publish: datetime, start: datetime, gen: float) -> dict[str, Any]:
    return {"publishTime": iso(publish), "startTime": iso(start), "generation": gen}


def fuelhh(start: datetime, gen: float) -> dict[str, Any]:
    return {
        "publishTime": iso(start + timedelta(minutes=30)),
        "startTime": iso(start),
        "fuelType": "WIND",
        "generation": gen,
    }


RUN = datetime(2026, 1, 9, 9, 30, tzinfo=UTC)
FORECASTS = [
    windfor(RUN, RUN - timedelta(minutes=90), 1),  # past echo (08:00, on the hour grid)
    windfor(RUN, START, 6526),
    windfor(RUN, START + timedelta(hours=1), 0),  # zero is a value
    windfor(RUN, START + timedelta(hours=3), 5),  # target outside the window
]
ACTUALS = [fuelhh(START + timedelta(minutes=30 * i), 8000 + i) for i in (0, 1, 3)]  # 01:00 missing


@respx.mock
def test_ingest_writes_snapshot_and_manifest(tmp_path: Path, monkeypatch: Any) -> None:
    fake_elexon(FORECASTS, ACTUALS)
    s = settings(tmp_path)
    monkeypatch.setattr(ingest, "Settings", lambda: s)

    assert ingest.main([]) == 0

    m = json.loads((s.snapshot_dir / "manifest.json").read_text())
    assert m["row_counts"] == {"forecasts": 2, "actuals": 3}
    assert m["dropped"]["forecast_past_echoes"] == 1
    assert m["dropped"]["forecast_target_outside_window"] == 1
    assert m["gaps"]["missing_actual_half_hours"] == ["2026-01-10T01:00:00Z"]
    assert m["gaps"]["target_hours_without_forecast"] == []
    assert m["publish_time_of_day_histogram"] == {"09:30": 1}
    assert m["max_horizon_hours"] == 17.5
    assert m["conflicts"] == []

    fc = read_rows(s.snapshot_dir / "forecasts.json.gz")
    assert fc["generation"].tolist() == [6526.0, 0.0]
    assert str(fc["publish_time"].dt.tz) == "UTC"
    assert len(read_rows(s.snapshot_dir / "actuals.json.gz")) == 3


@respx.mock
def test_conflicts_refuse_to_write_unless_allowed(tmp_path: Path, monkeypatch: Any) -> None:
    fake_elexon([*FORECASTS, windfor(RUN, START, 9999)], ACTUALS)
    s = settings(tmp_path)
    monkeypatch.setattr(ingest, "Settings", lambda: s)

    assert ingest.main([]) == 1
    assert not s.snapshot_dir.exists()

    assert ingest.main(["--allow-conflicts"]) == 0
    m = json.loads((s.snapshot_dir / "manifest.json").read_text())
    assert m["conflicts"] == [
        {"publish_time": iso(RUN), "start_time": iso(START), "values": [6526.0, 9999.0]}
    ]
    assert m["gaps"]["target_hours_without_forecast"] == [iso(START)]


@respx.mock
def test_lookback_must_exceed_max_horizon_plus_margin(
    tmp_path: Path, monkeypatch: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_elexon(FORECASTS, ACTUALS)
    # Max horizon is 17.5 h; 20 h look-back with a 6 h margin is not enough.
    s = settings(tmp_path, forecast_lookback_hours=20)
    monkeypatch.setattr(ingest, "Settings", lambda: s)

    assert ingest.main([]) == 1
    assert "does not exceed max horizon 17.5 h + margin 6 h" in capsys.readouterr().err
    assert not s.snapshot_dir.exists()


def test_settlement_days_cover_window_in_uk_time(tmp_path: Path) -> None:
    s = settings(tmp_path, window_start=START, window_end=START + timedelta(days=2))
    assert [str(d) for d in ingest.actual_settlement_days(s)] == ["2026-01-10", "2026-01-11"]
    # In BST, 23:00Z on 30 Jun is 1 Jul local: the settlement day must follow UK time.
    bst = datetime(2026, 6, 30, 23, tzinfo=UTC)
    s = settings(tmp_path, window_start=bst, window_end=bst + timedelta(hours=1))
    assert [str(d) for d in ingest.actual_settlement_days(s)] == ["2026-07-01", "2026-07-01"]


def test_rewrite_replaces_old_snapshot_atomically(tmp_path: Path) -> None:
    s = settings(tmp_path)
    snap = ingest.build_snapshot(FORECASTS, ACTUALS, s, START, "test")
    ingest.write_snapshot(snap, s.snapshot_dir)
    ingest.write_snapshot(snap, s.snapshot_dir)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["snapshot"]
    assert sorted(p.name for p in s.snapshot_dir.iterdir()) == [
        "actuals.json.gz",
        "forecasts.json.gz",
        "manifest.json",
    ]


def test_leftover_old_dir_from_a_crash_does_not_block_writing(tmp_path: Path) -> None:
    s = settings(tmp_path)
    leftover = tmp_path / ".snapshot-old"
    leftover.mkdir()
    (leftover / "junk").write_text("x")
    snap = ingest.build_snapshot(FORECASTS, ACTUALS, s, START, "test")
    ingest.write_snapshot(snap, s.snapshot_dir)
    ingest.write_snapshot(snap, s.snapshot_dir)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["snapshot"]


def test_off_grid_forecast_target_refuses_snapshot(tmp_path: Path) -> None:
    bad = [*FORECASTS, windfor(RUN, START + timedelta(minutes=30), 1)]
    with pytest.raises(v.SnapshotValidationError, match="off the 1h grid"):
        ingest.build_snapshot(bad, ACTUALS, settings(tmp_path), START, "test")


def test_fixture_manifest_describes_only_the_cut(tmp_path: Path) -> None:
    s = settings(tmp_path)
    ingest.write_snapshot(
        ingest.build_snapshot(FORECASTS, ACTUALS, s, START, "abc"), s.snapshot_dir
    )
    out = tmp_path / "fixture"
    ingest.cut_fixture(s.snapshot_dir, out, START, START + timedelta(hours=1))
    m = json.loads((out / "manifest.json").read_text())
    assert m["ranges"] == {"target": {"from": iso(START), "to": iso(START + timedelta(hours=1))}}
    assert m["row_counts"] == {"forecasts": 1, "actuals": 2}
    assert "dropped" not in m
    assert m["fixture"]["source"]["dropped"]["forecast_past_echoes"] == 1

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import synthetic_client
from tests.builders import forecasts

API = "/api/v1"
T1 = {"from": "2026-01-10T16:00:00Z", "to": "2026-01-10T17:00:00Z"}


def test_health_proves_the_snapshot_is_loaded(client: TestClient) -> None:
    body = client.get(f"{API}/health").json()
    assert body == {
        "status": "ok",
        "snapshot": {
            "fetched_at": "2026-10-24T11:42:08Z",
            "forecast_rows": 928,
            "actual_rows": 96,
            "conflicts": 0,
        },
    }


def test_openapi_and_docs_live_under_api_prefix(client: TestClient) -> None:
    assert client.get(f"{API}/openapi.json").status_code == 200
    assert client.get(f"{API}/docs").status_code == 200


def test_meta_reads_the_range_from_the_manifest(client: TestClient) -> None:
    body = client.get(f"{API}/meta").json()
    window = {"from": "2026-01-09T00:00:00Z", "to": "2026-01-11T00:00:00Z"}
    assert body["supported_target_range"] == window == body["default_window"]
    assert body["defaults"] == {
        "cutoff_local": "09:50",
        "publish_lag_minutes": 0,
        "aggregation": "point",
    }
    assert body["publications_per_day"] == {"min": 8, "median": 8.0, "max": 8}
    assert body["sign_convention"] == "error = forecast − actual (MW)"
    assert "meta" not in body


@pytest.mark.parametrize(("lag", "publish", "horizon"), [(0, "09:30", 30.5), (60, "07:30", 32.5)])
def test_series_t1_golden_example(
    client: TestClient, lag: int, publish: str, horizon: float
) -> None:
    body = client.get(f"{API}/series", params=T1 | {"lag_minutes": lag}).json()
    assert body["points"] == [
        {
            "target_time": "2026-01-10T16:00:00Z",
            "status": "ok",
            "actual_mw": 8222.0,
            "forecast_mw": 6526.0,
            "forecast_publish_time": f"2026-01-09T{publish}:00Z",
            "horizon_hours": horizon,
            "error_mw": -1696.0,
        }
    ]
    assert body["actuals_halfhourly"] == [
        {"start_time": "2026-01-10T16:00:00Z", "actual_mw": 8222.0},
        {"start_time": "2026-01-10T16:30:00Z", "actual_mw": 8121.0},
    ]
    assert body["meta"]["publish_lag_minutes"] == lag


def test_series_defaults_cover_the_window_with_meta(client: TestClient) -> None:
    r = client.get(f"{API}/series")
    body = r.json()
    assert r.headers["cache-control"] == "public, max-age=3600"
    assert len(r.headers["x-request-id"]) == 32
    assert len(body["points"]) == 48 and len(body["actuals_halfhourly"]) == 96
    assert body["meta"] == {
        "from": "2026-01-09T00:00:00Z",
        "to": "2026-01-11T00:00:00Z",
        "cutoff_local": "09:50",
        "cutoff_timezone": "Europe/London",
        "publish_lag_minutes": 0,
        "aggregation": "point",
        "cutoff_applied": True,
        "data_as_of": "2026-10-24T11:42:08Z",
        "coverage": {
            "target_hours": 48,
            "ok": 48,
            "missing_actual": 0,
            "missing_forecast": 0,
            "missing_both": 0,
        },
    }


def test_offsets_are_normalised_to_utc(client: TestClient) -> None:
    body = client.get(
        f"{API}/series",
        params={"from": "2026-01-10T17:00:00+01:00", "to": "2026-01-10T18:00:00+01:00"},
    ).json()
    assert body["meta"]["from"] == "2026-01-10T16:00:00Z"
    assert body["points"][0]["target_time"] == "2026-01-10T16:00:00Z"


def test_metrics_shape(client: TestClient) -> None:
    body = client.get(f"{API}/metrics").json()
    assert body["n"] == 48
    assert set(body) == {
        "meta",
        "n",
        "mae_mw",
        "rmse_mw",
        "bias_mw",
        "nmae",
        "error_quantiles_mw",
        "p90_over_forecast_mw",
        "over_forecast_share",
        "largest_over_forecast",
        "largest_under_forecast",
    }
    assert 0 <= body["over_forecast_share"] <= 1
    assert body["largest_under_forecast"]["target_time"].endswith("Z")
    assert body["rmse_mw"] >= body["mae_mw"] > 0


def test_by_hour_has_24_rows(client: TestClient) -> None:
    rows = client.get(f"{API}/metrics/by-hour").json()["rows"]
    assert [r["hour_local"] for r in rows] == list(range(24))
    assert sum(r["n"] for r in rows) == 48


def test_by_horizon_ignores_cutoff_and_says_so(client: TestClient) -> None:
    body = client.get(f"{API}/metrics/by-horizon", params={"bucket_hours": 12}).json()
    assert body["meta"]["cutoff_applied"] is False
    assert body["meta"]["coverage"] is None
    assert body["bucket_hours"] == 12
    assert body["rows_used"] == sum(r["n"] for r in body["rows"]) > 0
    other = client.get(
        f"{API}/metrics/by-horizon",
        params={"bucket_hours": 12, "cutoff": "06:00", "lag_minutes": 120},
    ).json()
    assert other["rows"] == body["rows"]


@pytest.mark.parametrize(
    ("params", "field", "msg"),
    [
        ({"from": "2026-01-09T00:00:00"}, "from", "must include a timezone offset"),
        ({"from": "2026-01-09T00:30:00Z"}, "from", "must be a whole hour"),
        ({"from": "2026-01-09T05:00:00+05:30"}, "from", "must be a whole hour"),
        ({"from": "not-a-date"}, "from", "must be ISO-8601"),
        ({"from": "2026-01-09T00:00:00 01:00"}, "from", "encode + as %2B"),
        (
            {"from": "2026-01-10T00:00:00Z", "to": "2026-01-10T00:00:00Z"},
            "to",
            "must be after from",
        ),
        ({"from": "2026-01-08T00:00:00Z"}, "from", "within the snapshot range"),
        ({"from": "2025-01-01T00:00:00Z"}, "from", "within the snapshot range"),  # not "62 days"
        ({"from": "2026-03-01T00:00:00Z"}, "from", "within the snapshot range"),  # not "after from"
        ({"to": "2026-01-12T00:00:00Z"}, "to", "within the snapshot range"),
        ({"cutoff": "9:50"}, "cutoff", "HH:MM"),
        ({"cutoff": "24:00"}, "cutoff", "HH:MM"),
        ({"lag_minutes": -1}, "lag_minutes", "greater than or equal to 0"),
        ({"lag_minutes": 181}, "lag_minutes", "less than or equal to 180"),
        ({"aggregation": "mean"}, "aggregation", "point"),
    ],
)
def test_422_paths(client: TestClient, params: dict[str, object], field: str, msg: str) -> None:
    r = client.get(f"{API}/series", params=params)
    assert r.status_code == 422
    (error,) = r.json()["detail"]
    assert error["loc"] == ["query", field]
    assert msg in error["msg"]


@pytest.mark.parametrize("bucket", [0, 25])
def test_bad_bucket_hours(client: TestClient, bucket: int) -> None:
    r = client.get(f"{API}/metrics/by-horizon", params={"bucket_hours": bucket})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["query", "bucket_hours"]


def test_clock_change_cutoff_is_a_422_naming_the_delivery_day(tmp_path: Path) -> None:
    c = synthetic_client(tmp_path, "2026-03-29T23:00:00Z", "2026-03-30T23:00:00Z", forecasts())
    r = c.get(f"{API}/series", params={"cutoff": "01:30"})
    assert r.status_code == 422
    (error,) = r.json()["detail"]
    assert error["loc"] == ["query", "cutoff"]
    assert "delivery day 2026-03-30" in error["msg"] and "outside 01:00–01:59" in error["msg"]
    assert error["input"] == "01:30"
    # by-horizon ignores the cutoff for its numbers but still rejects an impossible one
    assert c.get(f"{API}/metrics/by-horizon", params={"cutoff": "01:30"}).status_code == 422


def test_no_ok_hours_gives_null_metrics_and_full_coverage(tmp_path: Path) -> None:
    fc = forecasts(("2026-01-09T09:30Z", "2026-01-10T00:00Z", 0))  # forecast but no actuals
    c = synthetic_client(tmp_path, "2026-01-10T00:00:00Z", "2026-01-10T02:00:00Z", fc)
    body = c.get(f"{API}/metrics").json()
    assert body["n"] == 0
    assert all(body[k] is None for k in body if k not in ("meta", "n"))
    assert body["meta"]["coverage"] == {
        "target_hours": 2,
        "ok": 0,
        "missing_actual": 1,
        "missing_forecast": 0,
        "missing_both": 1,
    }
    points = c.get(f"{API}/series").json()["points"]
    assert points[0] | {"target_time": None} == {
        "target_time": None,
        "status": "missing_actual",
        "actual_mw": None,
        "forecast_mw": 0.0,
        "forecast_publish_time": "2026-01-09T09:30:00Z",
        "horizon_hours": 14.5,
        "error_mw": None,
    }  # 0 MW forecast kept as a value
    assert points[1]["status"] == "missing_both"


def test_unhandled_error_is_a_500_with_request_id_and_no_trace(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_: object) -> None:
        raise RuntimeError("secret internals")

    monkeypatch.setattr(client.app.state.service, "decisions", boom)  # type: ignore[attr-defined]
    r = client.get(f"{API}/series")
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal error", "request_id": r.headers["x-request-id"]}
    assert "secret" not in r.text


def test_structured_logs_record_memo_hits(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    params = {"from": "2026-01-09T03:00:00Z", "to": "2026-01-09T05:00:00Z"}
    with caplog.at_level("INFO", logger="app"):
        client.get(f"{API}/metrics", params=params)
        client.get(f"{API}/metrics", params=params)
    lines = [json.loads(r.getMessage()) for r in caplog.records if r.name == "app"][-2:]
    assert [line["memo"] for line in lines] == ["miss", "hit"]
    assert lines[0]["route"] == "/api/v1/metrics" and lines[0]["status"] == 200
    assert lines[0]["params"]["from"] == "2026-01-09T03:00:00Z"
    assert {"request_id", "latency_ms"} <= set(lines[0])


def test_range_over_62_days_is_rejected(tmp_path: Path) -> None:
    c = synthetic_client(tmp_path, "2026-01-01T00:00:00Z", "2026-04-01T00:00:00Z", forecasts())
    r = c.get(f"{API}/series", params={"to": "2026-03-05T00:00:00Z"})  # from defaults to 1 Jan
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["query", "to"]
    assert "at most 62 days" in r.json()["detail"][0]["msg"]
    assert c.get(f"{API}/series", params={"to": "2026-03-04T00:00:00Z"}).status_code == 200

from datetime import UTC, date, datetime

import httpx
import pytest
import respx

from app.data.elexon_client import ElexonClient, ElexonError

BASE = "https://elexon.test/bmrs/api/v1"
WINDFOR = f"{BASE}/datasets/WINDFOR/stream"
FUELHH = f"{BASE}/datasets/FUELHH/stream"


def client(max_attempts: int = 3) -> ElexonClient:
    return ElexonClient(
        BASE, timeout_s=5, max_attempts=max_attempts, concurrency=2, backoff_base_s=0
    )


@respx.mock
async def test_windfor_is_fetched_in_one_day_chunks() -> None:
    route = respx.get(WINDFOR).mock(return_value=httpx.Response(200, json=[{"x": 1}]))
    async with client() as c:
        rows = await c.fetch_windfor(
            datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 3, 12, tzinfo=UTC)
        )
    params = [dict(call.request.url.params) for call in route.calls]
    assert sorted(p["publishDateTimeFrom"] for p in params) == [
        "2026-01-01T00:00:00Z",
        "2026-01-02T00:00:00Z",
        "2026-01-03T00:00:00Z",
    ]
    assert {p["publishDateTimeFrom"]: p["publishDateTimeTo"] for p in params}[
        "2026-01-03T00:00:00Z"
    ] == "2026-01-03T12:00:00Z"
    assert len(rows) == 3


@respx.mock
async def test_fuelhh_requests_each_settlement_day_with_wind_filter() -> None:
    route = respx.get(FUELHH).mock(return_value=httpx.Response(200, json=[]))
    async with client() as c:
        await c.fetch_fuelhh_wind(date(2026, 1, 30), date(2026, 2, 1))
    params = sorted((dict(call.request.url.params) for call in route.calls), key=str)
    assert [p["settlementDateFrom"] for p in params] == ["2026-01-30", "2026-01-31", "2026-02-01"]
    assert all(p["settlementDateTo"] == p["settlementDateFrom"] for p in params)
    assert all(p["fuelType"] == "WIND" for p in params)


@respx.mock
async def test_retries_on_429_5xx_and_transport_errors_then_succeeds() -> None:
    respx.get(FUELHH).mock(
        side_effect=[
            httpx.Response(429),
            httpx.ConnectTimeout("slow"),
            httpx.Response(503),
            httpx.Response(200, json=[{"ok": True}]),
        ]
    )
    async with client(max_attempts=4) as c:
        assert await c.fetch_fuelhh_wind(date(2026, 1, 2), date(2026, 1, 2)) == [{"ok": True}]


@respx.mock
async def test_gives_up_after_max_attempts() -> None:
    route = respx.get(FUELHH).mock(return_value=httpx.Response(500))
    async with client(max_attempts=3) as c:
        with pytest.raises(ElexonError, match="gave up after 3 tries"):
            await c.fetch_fuelhh_wind(date(2026, 1, 2), date(2026, 1, 2))
    assert route.call_count == 3


@respx.mock
async def test_client_errors_are_not_retried() -> None:
    route = respx.get(FUELHH).mock(return_value=httpx.Response(400))
    async with client() as c:
        with pytest.raises(ElexonError, match="HTTP 400"):
            await c.fetch_fuelhh_wind(date(2026, 1, 2), date(2026, 1, 2))
    assert route.call_count == 1


@respx.mock
async def test_non_list_body_is_an_error() -> None:
    respx.get(FUELHH).mock(return_value=httpx.Response(200, json={"data": []}))
    async with client() as c:
        with pytest.raises(ElexonError, match="expected a JSON list"):
            await c.fetch_fuelhh_wind(date(2026, 1, 2), date(2026, 1, 2))

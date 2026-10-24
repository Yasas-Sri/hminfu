"""Async client for the two Elexon BMRS stream endpoints we ingest (FUELHH, WINDFOR)."""

import asyncio
import itertools
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

Row = dict[str, Any]

_RETRY_STATUS = {429, 500, 502, 503, 504}


class ElexonError(RuntimeError):
    """Elexon kept failing, or answered with something we can't use. Ingest must stop."""


class ElexonClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float,
        max_attempts: int,
        concurrency: int,
        backoff_base_s: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(base_url=base_url, timeout=timeout_s, transport=transport)
        self._max_attempts = max_attempts
        self._backoff_base_s = backoff_base_s
        self._sem = asyncio.Semaphore(concurrency)

    async def __aenter__(self) -> "ElexonClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._http.aclose()

    async def fetch_windfor(self, publish_from: datetime, publish_to: datetime) -> list[Row]:
        """WINDFOR rows with publishTime in [publish_from, publish_to], fetched in 1-day chunks.

        Chunk edges may return the same row twice; validation drops identical duplicates.
        """
        edges = _day_edges(publish_from, publish_to)
        chunks = [
            {"publishDateTimeFrom": _iso(a), "publishDateTimeTo": _iso(b)}
            for a, b in itertools.pairwise(edges)
        ]
        return await self._gather("/datasets/WINDFOR/stream", chunks)

    async def fetch_fuelhh_wind(self, first_day: date, last_day: date) -> list[Row]:
        """FUELHH WIND rows for settlement dates first_day..last_day inclusive, 1 request/day."""
        days = [first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)]
        chunks = [
            {
                "settlementDateFrom": d.isoformat(),
                "settlementDateTo": d.isoformat(),
                "fuelType": "WIND",
            }
            for d in days
        ]
        return await self._gather("/datasets/FUELHH/stream", chunks)

    async def _gather(self, path: str, chunks: list[dict[str, str]]) -> list[Row]:
        parts = await asyncio.gather(*(self._get(path, params) for params in chunks))
        return [row for part in parts for row in part]

    async def _get(self, path: str, params: dict[str, str]) -> list[Row]:
        async with self._sem:
            for attempt in range(1, self._max_attempts + 1):
                try:
                    response = await self._http.get(path, params=params)
                except httpx.TransportError as exc:
                    problem = f"{type(exc).__name__}: {exc}"
                else:
                    if response.status_code == 200:
                        body = response.json()
                        if not isinstance(body, list):
                            raise ElexonError(f"{path} {params}: expected a JSON list")
                        return body
                    if response.status_code not in _RETRY_STATUS:
                        raise ElexonError(f"{path} {params}: HTTP {response.status_code}")
                    problem = f"HTTP {response.status_code}"
                if attempt < self._max_attempts:
                    await asyncio.sleep(self._backoff_base_s * 2 ** (attempt - 1))
            raise ElexonError(
                f"{path} {params}: gave up after {self._max_attempts} tries ({problem})"
            )


def _day_edges(start: datetime, end: datetime) -> list[datetime]:
    edges = [start]
    while edges[-1] + timedelta(days=1) < end:
        edges.append(edges[-1] + timedelta(days=1))
    return [*edges, end]


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

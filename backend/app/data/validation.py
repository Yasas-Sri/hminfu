"""Turn raw Elexon rows into clean frames, and describe what was wrong or unusual about them.

Schema problems fail loudly (SnapshotValidationError): we never write a snapshot from rows we
can't trust.
Everything else (duplicates, revisions, conflicts, gaps) is returned as numbers for the manifest.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

COLUMNS = ["publish_time", "start_time", "generation"]
_MAX_REPORTED = 5


class SnapshotValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ForecastConflict:
    publish_time: str
    start_time: str
    values: list[float]


def parse_forecasts(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """WINDFOR rows → `publish_time`, `start_time` (UTC), `generation` (MW)."""
    return _parse(rows, "WINDFOR", {"publishTime", "startTime", "generation"})


def parse_actuals(rows: list[dict[str, Any]]) -> tuple[pd.DataFrame, int]:
    """FUELHH rows → same columns, WIND only. Returns (frame, non-WIND rows dropped).

    The API is already asked for fuelType=WIND; filtering again defends against a changed filter.
    """
    wind = [r for r in rows if r.get("fuelType") == "WIND"]
    return _parse(wind, "FUELHH", {"publishTime", "startTime", "generation"}), len(rows) - len(wind)


def drop_past_echoes(fc: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Drop rows with start_time <= publish_time (AGENTS.md §5.2).

    Runs repeat already-past hours with frozen values; those are echoes, not forecasts.
    """
    keep = fc["start_time"] > fc["publish_time"]
    return fc[keep].reset_index(drop=True), int((~keep).sum())


def dedupe_forecasts(fc: pd.DataFrame) -> tuple[pd.DataFrame, list[ForecastConflict], int]:
    """One row per (publish_time, start_time). Returns (frame, conflicts, identical dupes dropped).

    Identical repeats (e.g. from overlapping fetch chunks) are dropped silently. Different values
    for the same key are conflicts: they are reported and the key is removed entirely, because
    neither value can be trusted and picking one would be a guess.
    Ingest refuses to write unless --allow-conflicts.
    """
    unique = fc.drop_duplicates(COLUMNS)
    duplicates = len(fc) - len(unique)
    key = ["publish_time", "start_time"]
    clashing = unique.duplicated(key, keep=False)
    conflicts = [
        ForecastConflict(_iso(p), _iso(s), sorted(g["generation"].tolist()))
        for (p, s), g in unique[clashing].groupby(key)
    ]
    return unique[~clashing].sort_values(key).reset_index(drop=True), conflicts, duplicates


def dedupe_actuals(act: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """One row per start_time, keeping the latest publish_time. Returns (frame, revised count).

    A start_time published more than once with different values is a revision: the latest wins.
    Two different values with the same publish_time can't be ordered, so that fails loudly.
    """
    unique = act.drop_duplicates(COLUMNS)
    ties = unique.duplicated(["start_time", "publish_time"], keep=False)
    if ties.any():
        times = sorted({_iso(t) for t in unique.loc[ties, "start_time"]})
        raise SnapshotValidationError(
            f"FUELHH: conflicting values with equal publishTime at {times}"
        )
    revised = int((unique.groupby("start_time")["generation"].nunique() > 1).sum())
    latest = unique.sort_values("publish_time").drop_duplicates("start_time", keep="last")
    return latest.sort_values("start_time").reset_index(drop=True), revised


def missing_times(present: pd.Series, start: datetime, end: datetime, freq: str) -> list[str]:
    """Slots of the grid [start, end) at `freq` with no row. Grid first, so gaps stay visible."""
    grid = pd.date_range(start, end, freq=freq, inclusive="left")
    return [_iso(t) for t in grid.difference(pd.DatetimeIndex(present))]


def check_cadence(df: pd.DataFrame, dataset: str, freq: str) -> None:
    """Fail if any start_time is off the expected grid (WINDFOR hourly, FUELHH half-hourly).

    The gap report compares against a grid, so an off-grid row would otherwise slip in unnoticed.
    """
    off = df.loc[df["start_time"] != df["start_time"].dt.floor(freq), "start_time"]
    if not off.empty:
        shown = sorted({_iso(t) for t in off})[:_MAX_REPORTED]
        raise SnapshotValidationError(
            f"{dataset}: {len(off)} startTime values off the {freq} grid {shown}"
        )


def publications_per_day(fc: pd.DataFrame) -> dict[str, int]:
    """Distinct publish_times per UTC day."""
    runs = pd.Series(fc["publish_time"].unique())
    return {str(day): int(n) for day, n in runs.groupby(runs.dt.date).size().items()}


def publish_time_of_day_histogram(fc: pd.DataFrame) -> dict[str, int]:
    """Distinct publish_times counted by UTC time of day ("HH:MM")."""
    runs = pd.Series(fc["publish_time"].unique())
    return {
        str(k): int(v) for k, v in runs.dt.strftime("%H:%M").value_counts().sort_index().items()
    }


def max_horizon_hours(fc: pd.DataFrame) -> float | None:
    """Largest start_time − publish_time in hours (None if no rows)."""
    if fc.empty:
        return None
    return float((fc["start_time"] - fc["publish_time"]).max() / pd.Timedelta(hours=1))


def _parse(rows: list[dict[str, Any]], dataset: str, required: set[str]) -> pd.DataFrame:
    problems: list[str] = []
    for i, row in enumerate(rows):
        reason = _row_problem(row, required)
        if reason is not None:
            problems.append(f"row {i}: {reason}")
    if problems:
        shown = "; ".join(problems[:_MAX_REPORTED])
        raise SnapshotValidationError(f"{dataset}: {len(problems)} invalid rows ({shown})")
    df = pd.DataFrame(
        {
            "publish_time": pd.to_datetime(
                [r["publishTime"] for r in rows], utc=True, format="ISO8601"
            ),
            "start_time": pd.to_datetime(
                [r["startTime"] for r in rows], utc=True, format="ISO8601"
            ),
            "generation": pd.Series([r["generation"] for r in rows], dtype="float64"),
        }
    )
    return df


def _row_problem(row: dict[str, Any], required: set[str]) -> str | None:
    missing = sorted(k for k in required if row.get(k) is None)
    if missing:
        return f"missing {missing}"
    value = row["generation"]
    # bool is an int subclass; 0 is a valid value (AGENTS.md §5.9), NaN/inf are not.
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return f"non-numeric generation {value!r}"
    for key in ("publishTime", "startTime"):
        if not _is_aware_timestamp(row[key]):
            return f"{key} {row[key]!r} is not a timezone-aware ISO-8601 timestamp"
    return None


def _is_aware_timestamp(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def _iso(t: Any) -> str:
    return pd.Timestamp(t).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")

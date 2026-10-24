"""Elexon → backend/data/snapshot/{forecasts.json.gz, actuals.json.gz, manifest.json}.

The only code that touches the network (AGENTS.md §5.7). Writes nothing unless every check passes.

Usage (from backend/):
    uv run python -m scripts.ingest [--allow-conflicts]
    uv run python -m scripts.ingest --cut-fixture 2026-01-09T00:00:00Z 2026-01-11T00:00:00Z
"""

import argparse
import asyncio
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

from app.config import Settings
from app.data import validation as v
from app.data.elexon_client import ElexonClient, Row
from app.data.repository import read_rows, write_rows

LONDON = ZoneInfo("Europe/London")
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "snapshot"


@dataclass(frozen=True)
class Snapshot:
    forecasts: pd.DataFrame
    actuals: pd.DataFrame
    manifest: dict[str, Any]


def forecast_publish_range(s: Settings) -> tuple[datetime, datetime]:
    return s.window_start - timedelta(hours=s.forecast_lookback_hours), s.window_end


def actual_settlement_days(s: Settings) -> tuple[date, date]:
    """Settlement dates are UK-local days; cover every half-hour in [window_start, window_end)."""
    last_slot = s.window_end - timedelta(minutes=30)
    return s.window_start.astimezone(LONDON).date(), last_slot.astimezone(LONDON).date()


async def fetch(
    s: Settings, transport: httpx.AsyncBaseTransport | None = None
) -> tuple[list[Row], list[Row]]:
    async with ElexonClient(
        s.elexon_base_url,
        timeout_s=s.http_timeout_s,
        max_attempts=s.http_max_attempts,
        concurrency=s.http_concurrency,
        backoff_base_s=s.http_backoff_base_s,
        transport=transport,
    ) as client:
        return await asyncio.gather(
            client.fetch_windfor(*forecast_publish_range(s)),
            client.fetch_fuelhh_wind(*actual_settlement_days(s)),
        )


def build_snapshot(
    fc_rows: list[Row], act_rows: list[Row], s: Settings, fetched_at: datetime, code_version: str
) -> Snapshot:
    ws, we = s.window_start, s.window_end
    raw_fc = v.parse_forecasts(fc_rows)
    v.check_cadence(raw_fc, "WINDFOR", "1h")
    fc, echoes = v.drop_past_echoes(raw_fc)
    fc, conflicts, fc_dupes = v.dedupe_forecasts(fc)
    in_window = fc["start_time"].between(ws, we, inclusive="left")
    fc_window = fc[in_window].reset_index(drop=True)

    act, non_wind = v.parse_actuals(act_rows)
    v.check_cadence(act, "FUELHH", "30min")
    act_raw_rows = len(act)
    act, revisions = v.dedupe_actuals(act)
    act_window = act[act["start_time"].between(ws, we, inclusive="left")].reset_index(drop=True)

    per_day = v.publications_per_day(raw_fc)
    typical = statistics.median(per_day.values()) if per_day else 0
    pub_from, pub_to = forecast_publish_range(s)
    first_day, last_day = actual_settlement_days(s)
    manifest = {
        "fetched_at": _iso(fetched_at),
        "source_base_url": s.elexon_base_url,
        "code_version": code_version,
        "ranges": {
            "target": {"from": _iso(ws), "to": _iso(we)},
            "forecast_publish": {"from": _iso(pub_from), "to": _iso(pub_to)},
            "actual_settlement_dates": {"from": str(first_day), "to": str(last_day)},
        },
        "row_counts": {"forecasts": len(fc_window), "actuals": len(act_window)},
        "dropped": {
            "forecast_past_echoes": echoes,
            "forecast_identical_duplicates": fc_dupes,
            "forecast_target_outside_window": int((~in_window).sum()),
            "actual_non_wind": non_wind,
            "actual_superseded_or_duplicate": act_raw_rows - len(act),
            "actual_outside_window": len(act) - len(act_window),
        },
        "publications_per_day": per_day,
        "publish_time_of_day_histogram": v.publish_time_of_day_histogram(raw_fc),
        "max_horizon_hours": v.max_horizon_hours(fc),
        "horizon_check": {
            "lookback_hours": s.forecast_lookback_hours,
            "margin_hours": s.horizon_margin_hours,
        },
        "actual_revisions": revisions,
        "conflicts": [asdict(c) for c in conflicts],
        "gaps": {
            "missing_actual_half_hours": v.missing_times(act_window["start_time"], ws, we, "30min"),
            "target_hours_without_forecast": v.missing_times(fc_window["start_time"], ws, we, "1h"),
            "unusual_publication_days": {d: n for d, n in per_day.items() if n != typical},
        },
    }
    return Snapshot(fc_window, act_window, manifest)


def problems(snap: Snapshot, s: Settings, allow_conflicts: bool) -> list[str]:
    """Reasons to refuse writing the snapshot (empty list = OK)."""
    m = snap.manifest
    out: list[str] = []
    if m["conflicts"] and not allow_conflicts:
        out.append(
            f"{len(m['conflicts'])} forecast conflicts (see above); --allow-conflicts to write"
        )
    max_h = m["max_horizon_hours"]
    if max_h is None:
        out.append("no forecasts fetched")
    elif s.forecast_lookback_hours <= max_h + s.horizon_margin_hours:
        out.append(
            f"look-back {s.forecast_lookback_hours} h does not exceed max horizon {max_h} h "
            f"+ margin {s.horizon_margin_hours} h: early targets would miss long-horizon forecasts"
        )
    if snap.actuals.empty:
        out.append("no actuals fetched")
    return out


def write_snapshot(snap: Snapshot, out_dir: Path) -> None:
    """Write all files to a temp dir, then swap it in: a failure never leaves a partial snapshot."""
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    old = out_dir.with_name(f".{out_dir.name}-old")
    shutil.rmtree(old, ignore_errors=True)  # leftover from a crashed run
    tmp = Path(tempfile.mkdtemp(dir=out_dir.parent, prefix=f".{out_dir.name}-"))
    try:
        write_rows(snap.forecasts, tmp / "forecasts.json.gz")
        write_rows(snap.actuals, tmp / "actuals.json.gz")
        (tmp / "manifest.json").write_text(json.dumps(snap.manifest, indent=2) + "\n")
        if out_dir.exists():
            out_dir.rename(old)
        try:
            tmp.rename(out_dir)
        except OSError:
            if old.exists() and not out_dir.exists():
                old.rename(out_dir)  # put the previous snapshot back
            raise
        shutil.rmtree(old, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cut_fixture(src: Path, out: Path, start: datetime, end: datetime) -> None:
    """Cut a test snapshot (targets in [start, end)) from the real one, keeping its provenance."""
    source = json.loads((src / "manifest.json").read_text())
    fc, act = read_rows(src / "forecasts.json.gz"), read_rows(src / "actuals.json.gz")
    fc = fc[fc["start_time"].between(start, end, inclusive="left")].reset_index(drop=True)
    act = act[act["start_time"].between(start, end, inclusive="left")].reset_index(drop=True)
    gaps = source["gaps"]

    def in_range(times: list[str]) -> list[str]:
        return [t for t in times if _iso(start) <= t < _iso(end)]

    # Top level describes the fixture only; whole-snapshot stats stay under fixture.source.
    manifest = {
        "fetched_at": source["fetched_at"],
        "source_base_url": source["source_base_url"],
        "code_version": source["code_version"],
        "ranges": {"target": {"from": _iso(start), "to": _iso(end)}},
        "row_counts": {"forecasts": len(fc), "actuals": len(act)},
        "conflicts": [],  # conflicting keys never reach the snapshot rows
        "gaps": {
            k: in_range(gaps[k])
            for k in ("missing_actual_half_hours", "target_hours_without_forecast")
        },
        "fixture": {"source": source},
    }
    write_snapshot(Snapshot(fc, act, manifest), out)


def main(argv: list[str] | None = None, transport: httpx.AsyncBaseTransport | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--allow-conflicts", action="store_true")
    parser.add_argument("--cut-fixture", nargs=2, metavar=("FROM", "TO"))
    args = parser.parse_args(argv)
    s = Settings()

    if args.cut_fixture:
        start, end = (datetime.fromisoformat(t) for t in args.cut_fixture)
        if start.tzinfo is None or end.tzinfo is None:
            parser.error("--cut-fixture times need a timezone offset, e.g. 2026-01-09T00:00:00Z")
        cut_fixture(s.snapshot_dir, FIXTURE_DIR, start, end)
        print(f"wrote fixture {FIXTURE_DIR}")
        return 0

    fc_rows, act_rows = asyncio.run(fetch(s, transport))
    snap = build_snapshot(fc_rows, act_rows, s, datetime.now(UTC), _code_version())
    summary = {k: snap.manifest[k] for k in ("row_counts", "dropped", "max_horizon_hours")}
    print(json.dumps(summary | {"conflicts": snap.manifest["conflicts"][:10]}, indent=2))
    errors = problems(snap, s, args.allow_conflicts)
    if errors:
        print("ingest refused, nothing written:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    write_snapshot(snap, s.snapshot_dir)
    print(f"wrote {s.snapshot_dir}")
    return 0


def _code_version() -> str:
    """Last commit, plus "-dirty" if tracked files have uncommitted changes (read-only git)."""

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout

    try:
        head = git("log", "-1", "--format=%h").strip()
        dirty = git("status", "--porcelain", "--untracked-files=no").strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{head}-dirty" if dirty else head


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    sys.exit(main())

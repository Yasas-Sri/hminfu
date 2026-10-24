import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

from app.data.repository import read_rows, write_rows
from app.data.validation import SnapshotValidationError


def write_raw(path: Path, records: list[dict[str, object]]) -> Path:
    path.write_bytes(gzip.compress(json.dumps(records).encode()))
    return path


def test_round_trip_keeps_utc_and_zero(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "publish_time": pd.to_datetime(["2026-01-09T09:30:00Z"], utc=True),
            "start_time": pd.to_datetime(["2026-01-10T16:00:00Z"], utc=True),
            "generation": [0.0],
        }
    )
    write_rows(df, tmp_path / "rows.json.gz")
    back = read_rows(tmp_path / "rows.json.gz")
    pd.testing.assert_frame_equal(back, df)


def test_naive_times_are_rejected(tmp_path: Path) -> None:
    rec = {
        "publish_time": "2026-01-09T09:30:00",
        "start_time": "2026-01-10T16:00:00Z",
        "generation": 1,
    }
    with pytest.raises(SnapshotValidationError, match="UTC 'Z'"):
        read_rows(write_raw(tmp_path / "r.json.gz", [rec]))


def test_unexpected_keys_are_rejected(tmp_path: Path) -> None:
    rec = {
        "publishTime": "2026-01-09T09:30:00Z",
        "startTime": "2026-01-10T16:00:00Z",
        "generation": 1,
    }
    with pytest.raises(SnapshotValidationError, match="expected"):
        read_rows(write_raw(tmp_path / "r.json.gz", [rec]))

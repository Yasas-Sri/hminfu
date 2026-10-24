"""Snapshot row files: gzipped JSON records `{publish_time, start_time, generation}`, UTC `Z`.

Defined once here, so ingest (writer) and the API (reader, M3) can't drift apart.
"""

import gzip
import json
from pathlib import Path

import pandas as pd

from app.data.validation import COLUMNS, SnapshotValidationError

_TIME_COLUMNS = ("publish_time", "start_time")
_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def write_rows(df: pd.DataFrame, path: Path) -> None:
    out = df[COLUMNS].assign(**{c: df[c].dt.strftime(_FORMAT) for c in _TIME_COLUMNS})
    # mtime=0: identical data gives identical gzip bytes, so re-ingesting gives a clean git diff.
    path.write_bytes(gzip.compress(out.to_json(orient="records").encode(), mtime=0))


def read_rows(path: Path) -> pd.DataFrame:
    """Load a row file. Fails on unexpected keys or non-UTC/naive times instead of guessing."""
    records = json.loads(gzip.decompress(path.read_bytes()))
    df = pd.DataFrame.from_records(records, columns=COLUMNS)
    if records and set(records[0]) != set(COLUMNS):
        raise SnapshotValidationError(f"{path.name}: keys {sorted(records[0])}, expected {COLUMNS}")
    for col in _TIME_COLUMNS:
        if not df[col].str.endswith("Z").all():
            raise SnapshotValidationError(f"{path.name}: {col} values must be UTC 'Z' timestamps")
        df[col] = pd.to_datetime(df[col], format=_FORMAT, utc=True)
    return df.astype({"generation": "float64"})

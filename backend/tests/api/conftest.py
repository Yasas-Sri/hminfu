import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.data.repository import write_rows
from app.main import create_app

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "snapshot"


@pytest.fixture(scope="module")
def client() -> TestClient:
    """App on the 9–10 Jan fixture cut from the real snapshot."""
    return TestClient(create_app(Settings(snapshot_dir=FIXTURE)))


def synthetic_client(tmp: Path, start: str, end: str, forecasts: pd.DataFrame) -> TestClient:
    """App on a tiny hand-made snapshot (no actuals), for cases the real data can't reach."""
    empty = forecasts.iloc[0:0]
    write_rows(forecasts, tmp / "forecasts.json.gz")
    write_rows(empty, tmp / "actuals.json.gz")
    manifest = {
        "fetched_at": "2026-10-24T00:00:00Z",
        "ranges": {"target": {"from": start, "to": end}},
        "row_counts": {"forecasts": len(forecasts), "actuals": 0},
        "publications_per_day": {"2026-01-01": 1},
        "conflicts": [],
    }
    (tmp / "manifest.json").write_text(json.dumps(manifest))
    return TestClient(create_app(Settings(snapshot_dir=tmp)))

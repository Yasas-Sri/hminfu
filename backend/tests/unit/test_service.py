"""AnalysisService memo (LRU). The lock in _cached is reviewed, not tested: a stress test
couldn't reproduce the race under the GIL, so it would pass with or without the lock."""

import pandas as pd

from app.data.repository import Snapshot
from app.services.analysis import AnalysisService


def service(size: int) -> AnalysisService:
    empty = pd.DataFrame(columns=["publish_time", "start_time", "generation"])
    return AnalysisService(Snapshot(empty, empty, {}), memo_size=size)


def test_lru_evicts_oldest_and_reports_hits() -> None:
    svc = service(2)
    assert svc._cached("a", lambda: 1) == (1, False)
    assert svc._cached("a", lambda: 99) == (1, True)
    svc._cached("b", lambda: 2)
    svc._cached("c", lambda: 3)  # evicts "a"
    assert svc._cached("a", lambda: 4) == (4, False)

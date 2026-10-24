"""Runs the domain over the loaded snapshot, memoised by the full parameter tuple."""

import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

import pandas as pd

from app.data.repository import Snapshot
from app.domain import metrics
from app.domain.alignment import Aggregation, hourly_actuals
from app.domain.models import Coverage
from app.domain.selection import coverage, decision_forecasts, decision_frame, valid_forecasts
from app.domain.timeutils import cutoff_instants, target_grid


@dataclass(frozen=True)
class Params:
    start: datetime  # UTC, inclusive
    end: datetime  # UTC, exclusive
    gate_closure_local: time
    lag_minutes: int
    aggregation: Aggregation


class AnalysisService:
    def __init__(self, snapshot: Snapshot, memo_size: int) -> None:
        self.snapshot = snapshot
        # Per-process LRU. Routes run in a threadpool, so dict access is locked; compute() isn't,
        # so concurrent misses may compute the same key twice (harmless).
        self._memo: OrderedDict[Hashable, Any] = OrderedDict()
        self._memo_size = memo_size
        self._lock = threading.Lock()

    def decisions(self, p: Params) -> tuple[pd.DataFrame, Coverage, bool]:
        """(decision_frame, coverage, memo_hit)."""

        def compute() -> tuple[pd.DataFrame, Coverage]:
            grid = target_grid(p.start, p.end)
            frame = decision_frame(
                decision_forecasts(
                    self.snapshot.forecasts,
                    grid,
                    p.gate_closure_local,
                    timedelta(minutes=p.lag_minutes),
                ),
                hourly_actuals(self.snapshot.actuals, grid, p.aggregation),
            )
            return frame, coverage(frame)

        (frame, cov), hit = self._cached(("decisions", p), compute)
        return frame, cov, hit

    def actuals_halfhourly(self, p: Params) -> pd.DataFrame:
        act = self.snapshot.actuals
        return act[act["start_time"].between(p.start, p.end, inclusive="left")]

    def headline(self, p: Params) -> tuple[metrics.HeadlineMetrics, Coverage, bool]:
        frame, cov, _ = self.decisions(p)
        result, hit = self._cached(("metrics", p), lambda: metrics.headline_metrics(frame))
        return result, cov, hit

    def by_hour(self, p: Params) -> tuple[pd.DataFrame, Coverage, bool]:
        frame, cov, _ = self.decisions(p)
        rows, hit = self._cached(("by_hour", p), lambda: metrics.by_hour(frame))
        return rows, cov, hit

    def by_horizon(self, p: Params, bucket_hours: int) -> tuple[pd.DataFrame, int, bool]:
        """Uses every valid forecast regardless of cutoff and lag (ANALYSIS.md)."""

        def compute() -> tuple[pd.DataFrame, int]:
            grid = target_grid(p.start, p.end)
            actual = hourly_actuals(self.snapshot.actuals, grid, p.aggregation)
            return metrics.by_horizon(
                valid_forecasts(self.snapshot.forecasts, grid), actual, bucket_hours
            )

        # Cutoff and lag don't affect the result, so they are not part of the key. An impossible
        # cutoff is still rejected (CutoffTimeError), like on every other analytical endpoint.
        cutoff_instants(target_grid(p.start, p.end).to_series(), p.gate_closure_local)
        key = ("by_horizon", p.start, p.end, p.aggregation, bucket_hours)
        (rows, used), hit = self._cached(key, compute)
        return rows, used, hit

    def _cached(self, key: Hashable, compute: Callable[[], Any]) -> tuple[Any, bool]:
        with self._lock:
            if key in self._memo:
                self._memo.move_to_end(key)
                return self._memo[key], True
        value = compute()
        with self._lock:
            self._memo[key] = value
            if len(self._memo) > self._memo_size:
                self._memo.popitem(last=False)
        return value, False

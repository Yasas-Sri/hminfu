"""Hypothesis properties for selection (AGENTS.md §6), checked against a brute-force reference."""

from datetime import UTC, datetime, time, timedelta

import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.alignment import hourly_actuals
from app.domain.selection import coverage, decision_forecasts, decision_frame
from app.domain.timeutils import cutoff_instant, delivery_day, target_grid

# Starts include both DST transitions so the grid and the cutoff cross them.
BASES = [
    datetime(2026, 1, 9, tzinfo=UTC),
    datetime(2026, 3, 27, tzinfo=UTC),
    datetime(2026, 10, 23, tzinfo=UTC),
]
GATES = st.builds(
    time, st.integers(3, 23), st.sampled_from([0, 15, 30, 50])
)  # gate hour >= 3 avoids the 01:00–01:59 local gap/overlap on DST change days


@st.composite
def scenario(draw: st.DrawFn) -> tuple[pd.DatetimeIndex, pd.DataFrame, time, timedelta]:
    base = draw(st.sampled_from(BASES))
    hours = draw(st.integers(1, 96))
    targets = target_grid(base, base + timedelta(hours=hours))
    keys = draw(
        st.sets(st.tuples(st.integers(-96 * 4, hours * 4), st.integers(0, hours - 1)), max_size=80)
    )  # (publish offset in 15-min steps, target index); a set, so keys are unique like the snapshot
    rows = [
        (base + timedelta(minutes=15 * p), targets[i], draw(st.floats(0, 25_000)))
        for p, i in sorted(keys)
    ]
    fc = pd.DataFrame(rows, columns=["publish_time", "start_time", "generation"])
    fc["publish_time"] = pd.to_datetime(fc["publish_time"], utc=True)
    fc["start_time"] = pd.to_datetime(fc["start_time"], utc=True)
    return targets, fc, draw(GATES), timedelta(minutes=draw(st.integers(0, 180)))


def reference(fc: pd.DataFrame, t: pd.Timestamp, gate: time, lag: timedelta) -> pd.Timestamp | None:
    cutoff = cutoff_instant(delivery_day(t.to_pydatetime()), gate)
    eligible = [
        p
        for p, s in zip(fc["publish_time"], fc["start_time"], strict=True)
        if s == t and s > p and p + lag <= cutoff
    ]
    return max(eligible) if eligible else None


@settings(max_examples=200, deadline=None)
@given(scenario())
def test_selection_matches_brute_force(
    case: tuple[pd.DatetimeIndex, pd.DataFrame, time, timedelta],
) -> None:
    targets, fc, gate, lag = case
    decisions = decision_forecasts(fc, targets, gate, lag)

    assert list(decisions.index) == list(targets)  # exactly one row per target hour
    for t, chosen in decisions["forecast_publish_time"].items():
        expected = reference(fc, t, gate, lag)
        if expected is None:
            assert pd.isna(chosen)
            continue
        # chosen is the latest eligible publication...
        assert chosen == expected
        # ...so it was available by the cutoff and is not a past echo.
        assert chosen + lag <= cutoff_instant(delivery_day(t.to_pydatetime()), gate)
        assert t > chosen


@settings(max_examples=100, deadline=None)
@given(scenario(), st.data())
def test_coverage_sums_to_target_hours(
    case: tuple[pd.DatetimeIndex, pd.DataFrame, time, timedelta], data: st.DataObject
) -> None:
    targets, fc, gate, lag = case
    present = data.draw(st.lists(st.booleans(), min_size=len(targets), max_size=len(targets)))
    act = pd.DataFrame({"start_time": targets[present], "generation": 0.0})  # zeros on purpose
    frame = decision_frame(
        decision_forecasts(fc, targets, gate, lag), hourly_actuals(act, targets, "point")
    )
    cov = coverage(frame)
    assert cov.ok + cov.missing_actual + cov.missing_forecast + cov.missing_both == cov.target_hours
    assert cov.target_hours == len(targets)
    assert (frame["actual_mw"].notna().tolist()) == present  # 0 MW counted as present

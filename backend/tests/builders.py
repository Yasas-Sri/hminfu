"""Small synthetic frames for domain tests (same columns as the snapshot rows)."""

import pandas as pd


def ts(s: str) -> pd.Timestamp:
    """Aware UTC timestamp; a naive string fails (tz_convert needs an offset), as it should."""
    return pd.Timestamp(s).tz_convert("UTC")


def forecasts(*rows: tuple[str, str, float]) -> pd.DataFrame:
    """(publish_time, start_time, MW) tuples."""
    return pd.DataFrame(
        {
            "publish_time": pd.DatetimeIndex([ts(r[0]) for r in rows], tz="UTC"),
            "start_time": pd.DatetimeIndex([ts(r[1]) for r in rows], tz="UTC"),
            "generation": pd.Series([float(r[2]) for r in rows], dtype="float64"),
        }
    )


def actuals(*rows: tuple[str, float]) -> pd.DataFrame:
    """(start_time, MW) tuples for half-hourly actuals."""
    return pd.DataFrame(
        {
            "publish_time": pd.DatetimeIndex([ts(r[0]) for r in rows], tz="UTC"),
            "start_time": pd.DatetimeIndex([ts(r[0]) for r in rows], tz="UTC"),
            "generation": pd.Series([float(r[1]) for r in rows], dtype="float64"),
        }
    )

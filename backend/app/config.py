"""All tunables (AGENTS.md §5.6). Override any field with an `APP_`-prefixed env var."""

from datetime import UTC, datetime, time
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")

    # Analysis window = target hours [window_start, window_end). Our reading of the brief (ADR-001).
    window_start: AwareDatetime = datetime(2026, 1, 2, tzinfo=UTC)
    window_end: AwareDatetime = datetime(2026, 2, 2, tzinfo=UTC)
    # Day-ahead gate closure on D−1, Europe/London (N2EX-based default, ADR-002).
    gate_closure_local: time = time(9, 50)
    publish_lag_minutes: int = Field(0, ge=0, le=180)  # ADR-008
    aggregation: Literal["point", "hourly_mean"] = "point"  # ADR-005

    # Ingest only (scripts/ingest.py). Request-time code never touches the network.
    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    http_concurrency: int = Field(4, ge=1)
    http_timeout_s: float = Field(30.0, gt=0)
    http_max_attempts: int = Field(5, ge=1)
    http_backoff_base_s: float = Field(
        1.0, ge=0
    )  # sleeps base, 2·base, 4·base, ... between attempts
    # Forecasts are fetched by publishTime from window_start − look-back, covering every horizon.
    forecast_lookback_hours: int = Field(96, ge=1)
    # Ingest fails unless forecast_lookback_hours > max observed horizon + this margin.
    horizon_margin_hours: int = Field(6, ge=0)

    snapshot_dir: Path = Path(__file__).resolve().parents[1] / "data" / "snapshot"

    @model_validator(mode="after")
    def _window_is_whole_hours_and_ordered(self) -> "Settings":
        for t in (self.window_start, self.window_end):
            if (t.minute, t.second, t.microsecond) != (0, 0, 0):
                raise ValueError(f"window bounds must be whole hours, got {t.isoformat()}")
        if self.window_start >= self.window_end:
            raise ValueError("window_start must be before window_end")
        return self

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_naive_window_is_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        Settings(window_start="2026-01-02T00:00:00")


def test_env_overrides_use_app_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_HORIZON_MARGIN_HOURS", "12")
    assert Settings().horizon_margin_hours == 12


@pytest.mark.parametrize(
    ("kw", "msg"),
    [
        ({"window_start": "2026-01-02T00:30:00Z"}, "whole hours"),
        ({"window_end": "2026-01-01T00:00:00Z"}, "before window_end"),
        ({"publish_lag_minutes": -1}, "greater than or equal"),
        ({"http_max_attempts": 0}, "greater than or equal"),
    ],
)
def test_invalid_settings_are_rejected(kw: dict[str, object], msg: str) -> None:
    with pytest.raises(ValidationError, match=msg):
        Settings(**kw)


def test_window_whole_hour_is_checked_in_utc() -> None:
    with pytest.raises(ValidationError, match="whole hours"):
        Settings(window_start="2026-01-02T05:00:00+05:30")

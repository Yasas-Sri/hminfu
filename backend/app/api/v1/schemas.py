"""Public `/api/v1` contract. Source of truth for docs/API.md and the generated TS types."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    # ponytail: static until M3 adds the `snapshot` summary from the manifest (additive)
    status: Literal["ok"]

from fastapi import APIRouter

from app.api.v1.schemas import HealthResponse

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")

import json
import logging
import sys
from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.api.v1.routes import router
from app.config import Settings
from app.data.repository import load_snapshot
from app.domain.timeutils import CutoffTimeError
from app.services.analysis import AnalysisService

log = logging.getLogger("app")


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings()
    app = FastAPI(
        title="Wind Forecast Decision Explorer API",
        version="1.0.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
    )
    app.state.settings = cfg
    app.state.service = AnalysisService(load_snapshot(cfg.snapshot_dir), cfg.memo_size)
    app.include_router(router)
    _configure_logging()

    @app.exception_handler(CutoffTimeError)
    async def cutoff_time_error(request: Request, exc: CutoffTimeError) -> JSONResponse:
        cutoff = request.query_params.get("cutoff")
        detail = [
            {"type": "value_error", "loc": ["query", "cutoff"], "msg": str(exc), "input": cutoff}
        ]
        return JSONResponse({"detail": detail}, status_code=422)

    @app.middleware("http")
    async def request_log(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = uuid4().hex
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception(_line(request, request_id, 500, started))
            response = JSONResponse(
                {"detail": "Internal error", "request_id": request_id}, status_code=500
            )
        else:
            log.info(_line(request, request_id, response.status_code, started))
        response.headers["X-Request-ID"] = request_id
        return response

    return app


def _line(request: Request, request_id: str, status: int, started: float) -> str:
    return json.dumps(
        {
            "request_id": request_id,
            "route": request.url.path,
            "params": getattr(request.state, "params", dict(request.query_params)),
            "status": status,
            "latency_ms": round((perf_counter() - started) * 1000, 1),
            "memo": getattr(request.state, "memo", None),
        }
    )


def _configure_logging() -> None:
    if not log.handlers:  # create_app runs once per test app too
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)


app = create_app()

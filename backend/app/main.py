from fastapi import FastAPI

from app.api.v1.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Wind Forecast Decision Explorer API",
        version="1.0.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
    )
    app.include_router(router)
    return app



app = create_app()

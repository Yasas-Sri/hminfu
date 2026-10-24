from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_health_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_and_docs_live_under_api_prefix() -> None:
    assert client.get("/api/v1/openapi.json").status_code == 200
    assert client.get("/api/v1/docs").status_code == 200

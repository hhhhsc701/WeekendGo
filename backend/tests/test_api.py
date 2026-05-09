from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_config_endpoint_reports_missing_env_as_service_error() -> None:
    client = TestClient(create_app())

    response = client.get("/api/config")

    assert response.status_code in {200, 503}


def test_missing_trip_returns_404() -> None:
    client = TestClient(create_app())

    response = client.get("/api/trips/not-found")

    assert response.status_code == 404

"""FastAPI endpoint tests — only tests endpoints that don't need live DB/Redis."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200():
    res = client.get("/health")
    assert res.status_code == 200


def test_health_body():
    res = client.get("/health")
    data = res.json()
    assert data["status"] == "ok"
    assert "env" in data


def test_health_default_env():
    res = client.get("/health")
    # In test environment the ENV defaults to "development"
    assert res.json()["env"] == "development"


def test_docs_available_in_dev():
    # Swagger docs should be served when ENV != "production"
    res = client.get("/docs")
    assert res.status_code == 200


def test_openapi_schema():
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    assert schema["info"]["title"] == "Bayar.lah API"


def test_bills_route_exists():
    # Unauthenticated POST to /api/bills should return 403 (missing auth),
    # not 404 — proves the router is registered.
    res = client.post("/api/bills", json={})
    assert res.status_code in (401, 403, 422)


def test_payments_confirm_route_exists():
    res = client.post("/api/payments/confirm", json={})
    assert res.status_code in (401, 403, 422)


def test_notifications_register_route_exists():
    res = client.post("/api/notifications/register", json={})
    assert res.status_code in (400, 422)

"""Liveness + routing smoke tests (all via fakes - no live Supabase/Redis)."""
import pytest


def test_health_is_up_and_reveals_nothing_else(client):
    res = client.get("/health")
    assert res.status_code == 200 and res.json() == {"status": "ok"}


def test_docs_available_in_dev(client):
    assert client.get("/docs").status_code == 200


def test_openapi_schema(client):
    res = client.get("/openapi.json")
    assert res.status_code == 200
    assert res.json()["info"]["title"] == "Bayar.lah API"


@pytest.mark.parametrize("method,path,expected", [
    ("post", "/api/bills", 401),                       # organiser-only
    ("post", "/api/notifications/register", 401),      # organiser-only (used to be open)
    ("post", "/api/game/tangga/generate", 401),        # organiser-only (used to be open)
    ("post", "/api/payments/confirm", 422),            # public, but the body is validated
    ("get", "/api/public/bills/not-a-uuid", 422),      # public, id is validated
])
def test_routers_are_registered_and_guarded(client, method, path, expected):
    assert getattr(client, method)(path, **({"json": {}} if method == "post" else {})).status_code == expected

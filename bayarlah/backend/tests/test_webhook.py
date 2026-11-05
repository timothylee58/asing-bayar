"""The gateway webhook settles real money, so it must fail closed.

Uses the real HitPayGateway with real HMAC signatures: forged, tampered,
replayed and wrong-amount callbacks must not mark anyone paid.
"""
import hashlib
import hmac
import json
import urllib.parse

import pytest

from app.core.config import settings
from app.core.ws_manager import manager

SALT = "test-webhook-salt"
URL = "/api/payments/webhook/gateway"


@pytest.fixture
def live_gateway(monkeypatch):
    for name, value in {"PAYMENT_GATEWAY_ENABLED": True, "PAYMENT_GATEWAY_PROVIDER": "hitpay",
                        "HITPAY_API_KEY": "key", "HITPAY_WEBHOOK_SALT": SALT,
                        "HITPAY_SANDBOX": False, "ENV": "production"}.items():
        monkeypatch.setattr(settings, name, value)


@pytest.fixture
def broadcasts(monkeypatch):
    sent = []

    async def record(bill_id, message):
        sent.append((bill_id, message))

    monkeypatch.setattr(manager, "broadcast", record)
    return sent


@pytest.fixture
def pending(db, world):
    ali, bill = world["participants"][0], world["bill"]
    row = db.insert_row("payments", {
        "participant_id": ali["id"], "bill_id": bill["id"], "amount": 20, "method": "tng",
        "status": "pending", "gateway_status": "pending", "gateway_ref": "hp_123"})
    return {"row": row, "reference": f"{bill['id']}:{ali['id']}"}


def payload(pending, **over):
    body = {"payment_request_id": "hp_123", "reference_number": pending["reference"],
            "status": "completed", "amount": "20.00"}
    body.update(over)
    return body


def sign(raw: bytes, salt=SALT) -> str:
    return hmac.new(salt.encode(), raw, hashlib.sha256).hexdigest()


def post_signed(client, body: dict, salt=SALT):
    raw = json.dumps(body).encode()
    return client.post(URL, content=raw, headers={"content-type": "application/json",
                                                  "hitpay-signature": sign(raw, salt)})


def state(db):
    return (db.rows("payments")[0]["gateway_status"], db.rows("payments")[0]["status"])


class TestFailsClosed:
    def test_route_does_not_exist_in_production_without_a_gateway(self, client, db, pending, monkeypatch):
        monkeypatch.setattr(settings, "ENV", "production")  # gateway left disabled (the default)
        res = client.post(URL, json=payload(pending))
        assert res.status_code == 404
        assert state(db) == ("pending", "pending")

    def test_unsigned_request_is_rejected(self, client, db, live_gateway, pending, broadcasts):
        assert client.post(URL, json=payload(pending)).status_code == 401
        assert state(db) == ("pending", "pending") and broadcasts == []

    def test_wrong_secret_is_rejected(self, client, db, live_gateway, pending):
        assert post_signed(client, payload(pending), salt="attacker-guess").status_code == 401
        assert state(db) == ("pending", "pending")

    def test_a_tampered_body_does_not_verify(self, client, db, live_gateway, pending):
        good = json.dumps(payload(pending, amount="0.01")).encode()
        res = client.post(URL, content=json.dumps(payload(pending)).encode(),
                          headers={"hitpay-signature": sign(good)})
        assert res.status_code == 401
        assert state(db) == ("pending", "pending")

    def test_garbage_body_is_a_400(self, client, live_gateway):
        assert client.post(URL, content=b"", headers={"hitpay-signature": sign(b"")}).status_code == 400

    def test_dev_workflow_with_the_stub_gateway_settles_unsigned(self, client, db, world, broadcasts):
        """Local development (ENV=development, gateway disabled): initiate then an
        unsigned stub callback. This convenience must not exist in production
        (see test_route_does_not_exist_in_production_without_a_gateway)."""
        ali, bill = world["participants"][0], world["bill"]
        started = client.post("/api/payments/initiate", json={
            "bill_id": bill["id"], "participant_id": ali["id"], "method": "tng"})
        assert started.status_code == 200 and started.json()["gateway_ref"] == "stub_ref_local"
        res = client.post(URL, json={"reference_number": f"{bill['id']}:{ali['id']}", "amount": "20.00"})
        assert res.status_code == 200
        assert state(db) == ("verified", "confirmed")


class TestSettlement:
    def test_valid_completed_callback_settles_the_payment(self, client, db, live_gateway, pending, broadcasts):
        assert post_signed(client, payload(pending)).json() == {"status": "ok"}
        assert state(db) == ("verified", "confirmed")
        assert broadcasts[0][1]["type"] == "payment_confirmed"

    def test_form_encoded_hmac_field_scheme_is_accepted(self, client, db, live_gateway, pending):
        fields = payload(pending)
        signed = "".join(f"{k}{fields[k]}" for k in sorted(fields))
        fields["hmac"] = hmac.new(SALT.encode(), signed.encode(), hashlib.sha256).hexdigest()
        res = client.post(URL, content=urllib.parse.urlencode(fields).encode(),
                          headers={"content-type": "application/x-www-form-urlencoded"})
        assert res.status_code == 200 and state(db) == ("verified", "confirmed")

    def test_form_encoded_with_bad_hmac_is_rejected(self, client, db, live_gateway, pending):
        fields = {**payload(pending), "hmac": "0" * 64}
        res = client.post(URL, content=urllib.parse.urlencode(fields).encode(),
                          headers={"content-type": "application/x-www-form-urlencoded"})
        assert res.status_code == 401 and state(db) == ("pending", "pending")

    def test_a_replayed_callback_is_idempotent(self, client, db, live_gateway, pending, broadcasts):
        post_signed(client, payload(pending))
        post_signed(client, payload(pending))
        assert len(broadcasts) == 1
        assert state(db) == ("verified", "confirmed")

    def test_wrong_amount_leaves_the_payment_pending(self, client, db, live_gateway, pending, broadcasts):
        res = post_signed(client, payload(pending, amount="1.00"))
        assert res.json() == {"status": "amount_mismatch"}
        assert state(db) == ("pending", "pending") and broadcasts == []

    def test_a_reference_for_a_different_payment_is_ignored(self, client, db, live_gateway, pending):
        other = "11111111-1111-4111-8111-111111111111:22222222-2222-4222-8222-222222222222"
        assert post_signed(client, payload(pending, reference_number=other)).json() == {"status": "ignored"}
        assert state(db) == ("pending", "pending")

    def test_unknown_gateway_ref_is_ignored_with_200(self, client, db, live_gateway, pending):
        res = post_signed(client, payload(pending, payment_request_id="hp_nope"))
        assert res.status_code == 200 and res.json() == {"status": "ignored"}

    def test_a_webhook_cannot_create_a_payment_we_never_initiated(self, client, db, live_gateway, world):
        ref = f"{world['bill']['id']}:{world['participants'][0]['id']}"
        post_signed(client, {"payment_request_id": "hp_new", "reference_number": ref,
                             "status": "completed", "amount": "20.00"})
        assert db.rows("payments") == []

    def test_failed_callback_marks_it_failed_and_the_participant_can_retry(self, client, db, live_gateway, world, pending):
        post_signed(client, payload(pending, status="failed"))
        assert state(db) == ("failed", "failed")
        res = client.post("/api/payments/confirm", json={
            "bill_id": world["bill"]["id"], "participant_id": world["participants"][0]["id"], "method": "cash"})
        assert res.status_code == 200

    def test_a_late_failure_cannot_undo_a_verified_payment(self, client, db, live_gateway, pending):
        post_signed(client, payload(pending))
        post_signed(client, payload(pending, status="failed"))
        assert state(db) == ("verified", "confirmed")


def test_payment_write_routes_are_an_explicit_allowlist():
    """Adding a new write route under /api/payments must be a conscious decision:
    update this set AND add auth/ownership tests for it (see test_auth_matrix.py)."""
    from app.main import app

    # Read the route table from the OpenAPI schema: FastAPI >= 0.16x keeps included routers as
    # lazy `_IncludedRouter` entries, so `app.routes` no longer lists their endpoints.
    write_methods = {"post", "put", "patch", "delete"}
    writes = {
        path for path, ops in app.openapi()["paths"].items()
        if path.startswith("/api/payments") and write_methods & set(ops)
    }
    assert writes == {
        "/api/payments/confirm",           # members, no login: validated + rate limited
        "/api/payments/initiate",          # members, no login: validated + rate limited
        "/api/payments/webhook/gateway",   # gateway: signature checked, 404 in prod when off
        "/api/payments/nudge/{participant_id}",  # organiser only
    }

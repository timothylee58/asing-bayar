"""The live dashboard feed: organiser-only, token sent as a message, always cleaned up."""
import time

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api import ws as ws_module
from app.core.ws_manager import manager
from tests.conftest import MISSING_ID


def wait_until(condition, timeout=3.0):
    """Server-side cleanup runs on the app's event loop after the client closes,
    so poll rather than assert instantly (an instant assert is a race)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def url(bill_id):
    return f"/ws/dashboard/{bill_id}"


def auth(token):
    return {"type": "auth", "token": token}


@pytest.fixture(autouse=True)
def fast_auth_timeout(monkeypatch):
    monkeypatch.setattr(ws_module, "AUTH_TIMEOUT_SECONDS", 0.2)


def closes_with_4401(client, bill_id, first_message=None):
    with client.websocket_connect(url(bill_id)) as sock:
        if first_message is not None:
            sock.send_json(first_message)
        with pytest.raises(WebSocketDisconnect) as exc:
            sock.receive_json()
    return exc.value.code == ws_module.CLOSE_UNAUTHORISED


def test_owner_gets_the_full_init_view(client, db, world, organiser):
    db.insert_row("payments", {"participant_id": world["participants"][0]["id"], "bill_id": world["bill"]["id"],
                               "amount": 20, "method": "cash"})
    with client.websocket_connect(url(world["bill"]["id"])) as sock:
        sock.send_json(auth("tok-22222222-2222-4222-8222-222222222222"))
        msg = sock.receive_json()
    assert msg["type"] == "init"
    data = msg["data"]
    assert data["participants"][0]["phone"]  # organiser sees their own contacts
    assert [p["participant_id"] for p in data["payments"]] == [world["participants"][0]["id"]]  # flat, not nested
    assert data["collected"] == 20


def test_no_auth_message_is_rejected(client, world):
    assert closes_with_4401(client, world["bill"]["id"])  # times out waiting for auth


@pytest.mark.parametrize("first", [
    {"type": "hello"}, {"type": "auth"}, {"type": "auth", "token": ""}, {"type": "auth", "token": "bogus"}, "[]",
], ids=["wrong-type", "no-token", "empty-token", "bad-token", "not-an-object"])
def test_bad_credentials_are_rejected(client, world, first):
    assert closes_with_4401(client, world["bill"]["id"], first)


def test_a_signed_in_stranger_is_rejected(client, world, stranger):
    assert closes_with_4401(client, world["bill"]["id"], auth("tok-99999999-9999-4999-8999-999999999999"))
    assert manager.count(world["bill"]["id"]) == 0


def test_unknown_bill_is_rejected(client, organiser):
    assert closes_with_4401(client, MISSING_ID, auth("tok-22222222-2222-4222-8222-222222222222"))


def test_member_payments_reach_the_connected_organiser(client, world, organiser):
    with client.websocket_connect(url(world["bill"]["id"])) as sock:
        sock.send_json(auth("tok-22222222-2222-4222-8222-222222222222"))
        assert sock.receive_json()["type"] == "init"
        res = client.post("/api/payments/confirm", json={
            "bill_id": world["bill"]["id"], "participant_id": world["participants"][1]["id"], "method": "cash"})
        assert res.status_code == 200
        msg = sock.receive_json()
    assert msg["type"] == "payment_confirmed" and msg["participant_name"] == "Siti"


def test_the_connection_is_always_removed_on_disconnect(client, world, organiser):
    bill = world["bill"]["id"]
    with client.websocket_connect(url(bill)) as sock:
        sock.send_json(auth("tok-22222222-2222-4222-8222-222222222222"))
        sock.receive_json()
        assert wait_until(lambda: manager.count(bill) == 1)
    assert wait_until(lambda: manager.count(bill) == 0), "connection leaked after disconnect"

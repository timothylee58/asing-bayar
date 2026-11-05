import asyncio

from app.api import payments as payments_module
from tests.conftest import FAKE_USER_ID, OTHER_USER_ID

TOKEN = "ExponentPushToken[abcdefghijklmnop]"
TOKEN_2 = "ExponentPushToken[zyxwvutsrqponmlk]"


def register(client, headers, token=TOKEN):
    return client.post("/api/notifications/register", headers=headers, json={"token": token})


def test_registers_the_signed_in_users_token(client, db, organiser):
    assert register(client, organiser).status_code == 200
    assert [(r["user_id"], r["token"]) for r in db.rows("push_tokens")] == [(FAKE_USER_ID, TOKEN)]


def test_the_body_cannot_claim_someone_elses_identity(client, db, organiser):
    res = client.post("/api/notifications/register", headers=organiser,
                      json={"token": TOKEN, "user_id": OTHER_USER_ID, "participant_id": "x"})
    assert res.status_code == 200
    assert [r["user_id"] for r in db.rows("push_tokens")] == [FAKE_USER_ID]


def test_re_registering_replaces_the_token(client, db, organiser):
    register(client, organiser)
    register(client, organiser, TOKEN_2)
    assert [r["token"] for r in db.rows("push_tokens")] == [TOKEN_2]


def test_a_device_handed_to_another_account_stops_getting_the_old_users_pushes(client, db, organiser, stranger):
    register(client, organiser)
    register(client, stranger)  # same physical device token, different account
    assert [(r["user_id"], r["token"]) for r in db.rows("push_tokens")] == [(OTHER_USER_ID, TOKEN)]


def test_rejects_malformed_tokens(client, organiser):
    assert register(client, organiser, "not-an-expo-token-but-long-enough").status_code == 400
    assert register(client, organiser, "short").status_code == 422


def test_unregister_removes_only_your_own(client, db, organiser, stranger):
    register(client, organiser)
    register(client, stranger, TOKEN_2)
    assert client.delete("/api/notifications/unregister", headers=organiser).status_code == 200
    assert [r["user_id"] for r in db.rows("push_tokens")] == [OTHER_USER_ID]


def test_organiser_is_pushed_when_a_member_pays(db, organiser, monkeypatch):
    """The organiser's token is looked up by user id (it never was before)."""
    sent = []

    async def fake_push(tokens, title, body, data=None):
        sent.append((tokens, title, data))

    monkeypatch.setattr(payments_module, "send_expo_push", fake_push)
    db.insert_row("push_tokens", {"user_id": FAKE_USER_ID, "token": TOKEN})
    db.insert_row("push_tokens", {"user_id": OTHER_USER_ID, "token": TOKEN_2})
    asyncio.run(payments_module._notify_organiser(db, FAKE_USER_ID, "Ali", "Mamak", "bill-1"))
    assert sent[0][0] == [TOKEN]
    assert "Ali" in sent[0][1] and sent[0][2]["billId"] == "bill-1"


def test_a_push_failure_never_breaks_the_payment(db, monkeypatch):
    async def boom(**_k):
        raise RuntimeError("expo down")

    monkeypatch.setattr(payments_module, "send_expo_push", boom)
    asyncio.run(payments_module._notify_organiser(db, FAKE_USER_ID, "Ali", "Mamak", "bill-1"))  # no raise

"""Every endpoint that writes money/game state or exposes private data must
require a signed-in organiser, and bill-scoped ones must require ownership.

This is the regression net for the "anyone can mark anyone paid / decide who
pays / read phone numbers" class of bug.
"""
import pytest

from tests.conftest import (
    FAKE_BILL_ID,
    FAKE_PARTICIPANT_ID,
    FAKE_PARTICIPANT_ID_2,
    MISSING_ID,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PIDS = [FAKE_PARTICIPANT_ID, FAKE_PARTICIPANT_ID_2]

# (name, method, path, kwargs, bill-scoped?)  - bill-scoped => stranger gets 403
SPECS = [
    ("create_bill", "post", "/api/bills",
     {"json": {"title": "x", "total_amount": "10", "participants": [{"name": "a"}]}}, False),
    ("list_bills", "get", "/api/bills", {}, False),
    ("balances", "get", "/api/bills/organiser/balances", {}, False),
    ("get_bill", "get", "/api/bills/{bill}", {}, True),
    ("upload_qr", "post", "/api/bills/{bill}/payment-qr", {"files": {"file": ("q.png", PNG, "image/png")}}, True),
    ("upload_receipt", "post", "/api/bills/{bill}/receipt", {"files": {"file": ("r.png", PNG, "image/png")}}, True),
    ("bill_payments", "get", "/api/payments/bill/{bill}", {}, True),
    ("nudge", "post", "/api/payments/nudge/{participant}", {}, True),
    ("tangga_generate", "post", "/api/game/tangga/generate",
     {"json": {"bill_id": "{bill}", "participant_ids": PIDS, "outcome_labels": ["a", "b"]}}, True),
    ("tangga_lock", "post", "/api/game/tangga/lock",
     {"json": {"bill_id": "{bill}", "lanes": {PIDS[0]: 0, PIDS[1]: 1}}}, True),
    ("roulette_spin", "post", "/api/game/roulette/spin",
     {"json": {"bill_id": "{bill}", "participant_ids": PIDS}}, True),
    ("roulette_lock", "post", "/api/game/roulette/lock", {"json": {"bill_id": "{bill}"}}, True),
    ("dadu_roll", "post", "/api/game/dadu/roll",
     {"json": {"bill_id": "{bill}", "participant_ids": PIDS}}, True),
    ("dadu_lock", "post", "/api/game/dadu/lock", {"json": {"bill_id": "{bill}"}}, True),
    ("push_register", "post", "/api/notifications/register",
     {"json": {"token": "ExponentPushToken[abcdefghijklmnop]"}}, False),
    ("push_unregister", "delete", "/api/notifications/unregister", {}, False),
]
IDS = [s[0] for s in SPECS]


def _fill(value, bill, participant):
    if isinstance(value, str):
        return value.replace("{bill}", bill).replace("{participant}", participant)
    if isinstance(value, dict):
        return {k: _fill(v, bill, participant) for k, v in value.items()}
    return value


def _call(client, spec, headers=None, bill=FAKE_BILL_ID, participant=FAKE_PARTICIPANT_ID):
    _, method, path, kwargs, _ = spec
    kwargs = {k: _fill(v, bill, participant) for k, v in kwargs.items()}
    return getattr(client, method)(_fill(path, bill, participant), headers=headers or {}, **kwargs)


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_requires_a_token(client, spec):
    res = _call(client, spec)
    assert res.status_code == 401
    assert res.headers.get("www-authenticate") == "Bearer"


@pytest.mark.parametrize("spec", SPECS, ids=IDS)
def test_rejects_an_invalid_token(client, spec):
    res = _call(client, spec, headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


@pytest.mark.parametrize("spec", [s for s in SPECS if s[4]], ids=[s[0] for s in SPECS if s[4]])
def test_non_owner_is_forbidden(client, db, world, stranger, spec):
    bill = world["bill"]["id"]
    participant = world["participants"][0]["id"]
    # The bill belongs to FAKE_USER_ID; `stranger` is a different signed-in user.
    res = _call(client, spec, headers=stranger, bill=bill, participant=participant)
    assert res.status_code == 403, res.text
    assert not db.rows("game_results")
    assert not db.objects


@pytest.mark.parametrize("spec", [s for s in SPECS if s[4]], ids=[s[0] for s in SPECS if s[4]])
def test_unknown_bill_is_404_not_500(client, organiser, spec):
    res = _call(client, spec, headers=organiser, bill=MISSING_ID, participant=MISSING_ID)
    assert res.status_code == 404, res.text


def test_a_valid_organiser_token_is_accepted(client, world, organiser):
    assert client.get("/api/bills", headers=organiser).status_code == 200

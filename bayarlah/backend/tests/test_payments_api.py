from unittest.mock import MagicMock, AsyncMock
from tests.conftest import FAKE_BILL_ID, FAKE_PARTICIPANT_ID, FAKE_PAYMENT_ID

PAYMENT_ROW = {
    "id": FAKE_PAYMENT_ID,
    "participant_id": FAKE_PARTICIPANT_ID,
    "bill_id": FAKE_BILL_ID,
    "amount": "10.00",
    "method": "duitnow",
    "confirmed_at": "2024-01-01T00:00:00+00:00",
    "status": "confirmed",
}

CONFIRM_PAYLOAD = {
    "participant_id": FAKE_PARTICIPANT_ID,
    "bill_id": FAKE_BILL_ID,
    "amount": "10.00",
    "method": "duitnow",
}


def test_confirm_payment_success(client, mock_supabase):
    # Sequence: duplicate-check → [], insert → [PAYMENT_ROW],
    #           participant single → dict, bill single → dict (organiser_id=None → no push task)
    mock_supabase.table.return_value.execute.side_effect = [
        MagicMock(data=[]),                                                          # no existing payment
        MagicMock(data=[PAYMENT_ROW]),                                               # insert
        MagicMock(data={"name": "Alice", "amount_owed": "10.00", "bill_id": FAKE_BILL_ID}),  # participant
        MagicMock(data={"title": "Makan", "organiser_id": None}),                   # bill (no push task)
    ]
    r = client.post("/api/payments/confirm", json=CONFIRM_PAYLOAD)
    assert r.status_code == 200
    assert r.json()["method"] == "duitnow"
    assert r.json()["status"] == "confirmed"


def test_confirm_payment_duplicate_returns_409(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = [{"id": "existing-pay"}]
    r = client.post("/api/payments/confirm", json=CONFIRM_PAYLOAD)
    assert r.status_code == 409


def test_get_bill_payments_success(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = [PAYMENT_ROW]
    r = client.get(f"/api/payments/bill/{FAKE_BILL_ID}")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_get_bill_payments_empty(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = []
    r = client.get(f"/api/payments/bill/{FAKE_BILL_ID}")
    assert r.status_code == 200
    assert r.json() == []


def test_nudge_success_with_phone(client, mock_redis, mock_supabase):
    mock_redis.exists = AsyncMock(return_value=0)
    # Sequence: participant lookup, push_tokens lookup (empty → no push)
    mock_supabase.table.return_value.execute.side_effect = [
        MagicMock(data={"name": "Alice", "phone": "60123456789", "bill_id": FAKE_BILL_ID}),
        MagicMock(data=[]),  # push_tokens
    ]
    r = client.post(f"/api/payments/nudge/{FAKE_PARTICIPANT_ID}")
    assert r.status_code == 200
    body = r.json()
    assert body["nudged"] is True
    assert body["name"] == "Alice"
    assert "wa.me" in body["whatsapp_link"]


def test_nudge_no_phone_returns_null_link(client, mock_redis, mock_supabase):
    mock_redis.exists = AsyncMock(return_value=0)
    mock_supabase.table.return_value.execute.side_effect = [
        MagicMock(data={"name": "Bob", "phone": "", "bill_id": FAKE_BILL_ID}),
        MagicMock(data=[]),
    ]
    r = client.post(f"/api/payments/nudge/{FAKE_PARTICIPANT_ID}")
    assert r.status_code == 200
    assert r.json()["whatsapp_link"] is None


def test_nudge_cooldown_returns_429(client, mock_redis):
    mock_redis.exists = AsyncMock(return_value=1)
    r = client.post(f"/api/payments/nudge/{FAKE_PARTICIPANT_ID}")
    assert r.status_code == 429


def test_nudge_participant_not_found_returns_404(client, mock_redis, mock_supabase):
    mock_redis.exists = AsyncMock(return_value=0)
    mock_supabase.table.return_value.execute.return_value.data = None
    r = client.post(f"/api/payments/nudge/{FAKE_PARTICIPANT_ID}")
    assert r.status_code == 404

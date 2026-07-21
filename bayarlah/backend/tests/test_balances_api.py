from unittest.mock import MagicMock
from tests.conftest import FAKE_BILL_ID, FAKE_USER_ID, FAKE_PARTICIPANT_ID, FAKE_PARTICIPANT_ID_2

FAKE_BILL_ID_2 = "a0000000-0000-4000-8000-000000000006"


def _set_side_effects(mock_supabase, datasets):
    results = iter([MagicMock(data=d) for d in datasets])
    mock_supabase.table.return_value.execute.side_effect = lambda: next(results)


def test_balances_empty_when_no_bills(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = []
    r = client.get("/api/bills/organiser/balances")
    assert r.status_code == 200
    body = r.json()
    assert body["contacts"] == []
    assert float(body["total_outstanding"]) == 0.0


def test_balances_net_single_contact(client, mock_supabase):
    _set_side_effects(mock_supabase, [
        [{"id": FAKE_BILL_ID}],
        [
            {
                "id": FAKE_PARTICIPANT_ID,
                "name": "Alice",
                "phone": "+60123456789",
                "amount_owed": "50.00",
                "bill_id": FAKE_BILL_ID,
            }
        ],
        [{"participant_id": FAKE_PARTICIPANT_ID, "amount": "20.00"}],
    ])
    r = client.get("/api/bills/organiser/balances")
    assert r.status_code == 200
    body = r.json()
    assert len(body["contacts"]) == 1
    c = body["contacts"][0]
    assert c["phone"] == "+60123456789"
    assert float(c["total_owed"]) == 50.0
    assert float(c["total_paid"]) == 20.0
    assert float(c["balance"]) == 30.0
    assert float(body["total_outstanding"]) == 30.0


def test_balances_aggregates_same_phone_across_bills(client, mock_supabase):
    _set_side_effects(mock_supabase, [
        [{"id": FAKE_BILL_ID}, {"id": FAKE_BILL_ID_2}],
        [
            {
                "id": FAKE_PARTICIPANT_ID,
                "name": "Bob",
                "phone": "+60111111111",
                "amount_owed": "30.00",
                "bill_id": FAKE_BILL_ID,
            },
            {
                "id": FAKE_PARTICIPANT_ID_2,
                "name": "Bob",
                "phone": "+60111111111",
                "amount_owed": "20.00",
                "bill_id": FAKE_BILL_ID_2,
            },
        ],
        [],
    ])
    r = client.get("/api/bills/organiser/balances")
    body = r.json()
    assert len(body["contacts"]) == 1
    c = body["contacts"][0]
    assert float(c["total_owed"]) == 50.0
    assert float(c["balance"]) == 50.0
    assert c["bill_count"] == 2


def test_balances_fully_paid_excluded(client, mock_supabase):
    _set_side_effects(mock_supabase, [
        [{"id": FAKE_BILL_ID}],
        [
            {
                "id": FAKE_PARTICIPANT_ID,
                "name": "Carol",
                "phone": "+60199999999",
                "amount_owed": "25.00",
                "bill_id": FAKE_BILL_ID,
            }
        ],
        [{"participant_id": FAKE_PARTICIPANT_ID, "amount": "25.00"}],
    ])
    r = client.get("/api/bills/organiser/balances")
    body = r.json()
    assert body["contacts"] == []
    assert float(body["total_outstanding"]) == 0.0


def test_balances_groups_no_phone_by_name(client, mock_supabase):
    _set_side_effects(mock_supabase, [
        [{"id": FAKE_BILL_ID}],
        [
            {
                "id": FAKE_PARTICIPANT_ID,
                "name": "Dave",
                "phone": None,
                "amount_owed": "40.00",
                "bill_id": FAKE_BILL_ID,
            }
        ],
        [],
    ])
    r = client.get("/api/bills/organiser/balances")
    body = r.json()
    assert len(body["contacts"]) == 1
    c = body["contacts"][0]
    assert c["phone"] is None
    assert c["name"] == "Dave"
    assert float(c["balance"]) == 40.0


def test_balances_sorted_descending_by_balance(client, mock_supabase):
    _set_side_effects(mock_supabase, [
        [{"id": FAKE_BILL_ID}],
        [
            {
                "id": FAKE_PARTICIPANT_ID,
                "name": "Eve",
                "phone": "+60100000001",
                "amount_owed": "10.00",
                "bill_id": FAKE_BILL_ID,
            },
            {
                "id": FAKE_PARTICIPANT_ID_2,
                "name": "Frank",
                "phone": "+60100000002",
                "amount_owed": "50.00",
                "bill_id": FAKE_BILL_ID,
            },
        ],
        [],
    ])
    r = client.get("/api/bills/organiser/balances")
    body = r.json()
    balances = [float(c["balance"]) for c in body["contacts"]]
    assert balances == sorted(balances, reverse=True)
    assert balances[0] == 50.0

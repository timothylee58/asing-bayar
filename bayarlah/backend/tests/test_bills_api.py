from unittest.mock import MagicMock
from tests.conftest import FAKE_BILL_ID, FAKE_USER_ID

BILL_ROW = {
    "id": FAKE_BILL_ID,
    "title": "Makan siang",
    "total_amount": "30.00",
    "per_person": "10.00",
    "description": None,
    "due_date": None,
    "emoji_tag": "🍽️",
    "status": "pending",
    "game_mode": "equal",
    "created_at": "2024-01-01T00:00:00+00:00",
    "organiser_id": FAKE_USER_ID,
}

CREATE_PAYLOAD = {
    "title": "Makan siang",
    "total_amount": "30.00",
    "participants": [{"name": "Alice"}, {"name": "Bob"}, {"name": "Charlie"}],
}


def test_create_bill_returns_200(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = [BILL_ROW]
    r = client.post("/api/bills", json=CREATE_PAYLOAD)
    assert r.status_code == 200


def test_create_bill_share_url_set(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = [BILL_ROW]
    body = client.post("/api/bills", json=CREATE_PAYLOAD).json()
    assert body["share_url"] == f"/pay/{FAKE_BILL_ID}"


def test_create_bill_per_person_calculation(client, mock_supabase):
    # 45 / 3 participants = 15
    row = {**BILL_ROW, "total_amount": "45.00", "per_person": "15.00"}
    mock_supabase.table.return_value.execute.return_value.data = [row]
    body = client.post(
        "/api/bills",
        json={"title": "Trip", "total_amount": "45.00", "participants": [{"name": "X"}, {"name": "Y"}, {"name": "Z"}]},
    ).json()
    assert float(body["per_person"]) == 15.0


def test_get_bill_success(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = BILL_ROW
    r = client.get(f"/api/bills/{FAKE_BILL_ID}")
    assert r.status_code == 200
    assert r.json()["title"] == "Makan siang"
    assert r.json()["share_url"] == f"/pay/{FAKE_BILL_ID}"


def test_get_bill_not_found(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = None
    r = client.get(f"/api/bills/{FAKE_BILL_ID}")
    assert r.status_code == 404


def test_list_bills_returns_array(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = [BILL_ROW]
    r = client.get("/api/bills")
    assert r.status_code == 200
    bills = r.json()
    assert isinstance(bills, list)
    assert bills[0]["title"] == "Makan siang"


def test_list_bills_empty(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = []
    r = client.get("/api/bills")
    assert r.status_code == 200
    assert r.json() == []


# --- Custom / unequal splits ---

CUSTOM_PAYLOAD = {
    "title": "Trip",
    "total_amount": "30.00",
    "split_mode": "custom",
    "participants": [
        {"name": "Alice", "amount_owed": "10.00"},
        {"name": "Bob", "amount_owed": "15.00"},
        {"name": "Charlie", "amount_owed": "5.00"},
    ],
}

CUSTOM_BILL_ROW = {**BILL_ROW, "per_person": None}


def test_custom_split_returns_200(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = [CUSTOM_BILL_ROW]
    r = client.post("/api/bills", json=CUSTOM_PAYLOAD)
    assert r.status_code == 200


def test_custom_split_per_person_is_null(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = [CUSTOM_BILL_ROW]
    body = client.post("/api/bills", json=CUSTOM_PAYLOAD).json()
    assert body["per_person"] is None


def test_custom_split_sum_mismatch_returns_422(client, mock_supabase):
    bad_payload = {
        "title": "Trip",
        "total_amount": "30.00",
        "split_mode": "custom",
        "participants": [
            {"name": "Alice", "amount_owed": "10.00"},
            {"name": "Bob", "amount_owed": "10.00"},
        ],
    }
    r = client.post("/api/bills", json=bad_payload)
    assert r.status_code == 422


def test_custom_split_missing_amount_returns_422(client, mock_supabase):
    bad_payload = {
        "title": "Trip",
        "total_amount": "30.00",
        "split_mode": "custom",
        "participants": [
            {"name": "Alice"},
            {"name": "Bob", "amount_owed": "30.00"},
        ],
    }
    r = client.post("/api/bills", json=bad_payload)
    assert r.status_code == 422


# --- Receipt upload ---

RECEIPT_BILL = {"id": FAKE_BILL_ID, "organiser_id": FAKE_USER_ID}
RECEIPT_URL = "https://test.supabase.co/storage/v1/object/public/receipts/test.jpg"


def test_receipt_upload_returns_200(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = RECEIPT_BILL
    files = {"file": ("receipt.jpg", b"fake-image-data", "image/jpeg")}
    r = client.post(f"/api/bills/{FAKE_BILL_ID}/receipt", files=files)
    assert r.status_code == 200
    assert r.json()["receipt_url"] == RECEIPT_URL


def test_receipt_upload_non_organiser_returns_403(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = {
        "id": FAKE_BILL_ID,
        "organiser_id": "b0000000-0000-4000-8000-000000000001",
    }
    files = {"file": ("receipt.jpg", b"fake-image-data", "image/jpeg")}
    r = client.post(f"/api/bills/{FAKE_BILL_ID}/receipt", files=files)
    assert r.status_code == 403


def test_receipt_upload_non_image_returns_422(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = RECEIPT_BILL
    files = {"file": ("doc.pdf", b"fake-pdf-data", "application/pdf")}
    r = client.post(f"/api/bills/{FAKE_BILL_ID}/receipt", files=files)
    assert r.status_code == 422


def test_get_bill_receipt_url_null_by_default(client, mock_supabase):
    mock_supabase.table.return_value.execute.return_value.data = BILL_ROW
    body = client.get(f"/api/bills/{FAKE_BILL_ID}").json()
    assert body.get("receipt_url") is None

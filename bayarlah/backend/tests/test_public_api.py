"""The unauthenticated share-page endpoint: everything a payer needs, no PII."""
from decimal import Decimal

from tests.conftest import FAKE_USER_ID, MISSING_ID


def test_exposes_no_phone_numbers_or_organiser_id(client, world):
    res = client.get(f"/api/public/bills/{world['bill']['id']}")
    assert res.status_code == 200
    text = res.text
    # (payment_details.tng_phone is the payee number the organiser chose to publish; that is fine)
    assert all("phone" not in p for p in res.json()["participants"])
    for p in world["participants"]:
        assert p["phone"] not in text
    assert FAKE_USER_ID not in text and "organiser_id" not in text


def test_returns_what_a_payer_needs(client, db, world):
    bill = world["bill"]
    db.rows("bills", id=bill["id"])[0]["payment_details"] = {"duitnow_id": "0123456789", "tng_phone": "0123"}
    data = client.get(f"/api/public/bills/{bill['id']}").json()
    assert data["title"] == "Mamak" and data["per_person"] == 20.0 and isinstance(data["per_person"], float)
    assert {p["name"] for p in data["participants"]} == {"Ali", "Siti", "Raj"}
    assert all(p["amount_owed"] == 20 for p in data["participants"])
    assert data["payment_details"]["duitnow_id"] == "0123456789"


def test_payments_are_flat_settled_only_and_summed(client, db, world):
    bill, (ali, siti, _) = world["bill"], world["participants"]
    db.insert_row("payments", {"participant_id": ali["id"], "bill_id": bill["id"], "amount": 20, "method": "cash"})
    db.insert_row("payments", {"participant_id": siti["id"], "bill_id": bill["id"], "amount": 20, "method": "tng",
                               "status": "pending", "gateway_status": "pending"})
    data = client.get(f"/api/public/bills/{bill['id']}").json()
    assert [p["participant_id"] for p in data["payments"]] == [ali["id"]]
    assert Decimal(str(data["collected"])) == Decimal("20")


def test_unknown_bill_is_404(client):
    assert client.get(f"/api/public/bills/{MISSING_ID}").status_code == 404


def test_malformed_id_is_422(client):
    assert client.get("/api/public/bills/not-a-uuid").status_code == 422


def test_is_rate_limited_per_ip(client, redis, world):
    redis.d["rl:public_bill:testclient"] = "600"
    assert client.get(f"/api/public/bills/{world['bill']['id']}").status_code == 429


def test_rate_limiter_fails_open_if_redis_is_down(client, redis, world, monkeypatch):
    async def boom(*_a, **_k):
        raise ConnectionError("redis down")
    monkeypatch.setattr(redis, "incr", boom)
    assert client.get(f"/api/public/bills/{world['bill']['id']}").status_code == 200

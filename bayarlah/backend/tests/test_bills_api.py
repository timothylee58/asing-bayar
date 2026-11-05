from decimal import Decimal

import pytest

from tests.conftest import FAKE_USER_ID

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


def body(**over):
    base = {"title": "Mamak", "total_amount": "100.00",
            "participants": [{"name": "Ali"}, {"name": "Siti"}, {"name": "Raj"}]}
    base.update(over)
    return base


class TestCreate:
    def test_equal_split_keeps_every_sen(self, client, db, organiser):
        res = client.post("/api/bills", json=body(), headers=organiser)
        assert res.status_code == 200, res.text
        amounts = [Decimal(str(p["amount_owed"])) for p in db.rows("participants")]
        assert sorted(amounts, reverse=True) == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]
        assert sum(amounts) == Decimal("100.00")  # RM100 / 3 used to collect only RM99.99
        assert Decimal(str(res.json()["per_person"])) == Decimal("33.33")
        assert db.rows("bills")[0]["organiser_id"] == FAKE_USER_ID

    def test_custom_split(self, client, db, organiser):
        parts = [{"name": "A", "amount_owed": "70.00"}, {"name": "B", "amount_owed": "30.00"}]
        res = client.post("/api/bills", json=body(split_mode="custom", participants=parts), headers=organiser)
        assert res.status_code == 200
        assert res.json()["per_person"] is None

    @pytest.mark.parametrize("amounts", [("70.00", "29.99"), ("70.00", "30.01")])
    def test_custom_split_must_equal_total_exactly(self, client, organiser, amounts):
        parts = [{"name": "A", "amount_owed": amounts[0]}, {"name": "B", "amount_owed": amounts[1]}]
        res = client.post("/api/bills", json=body(split_mode="custom", participants=parts), headers=organiser)
        assert res.status_code == 422

    def test_custom_split_requires_every_amount(self, client, organiser):
        parts = [{"name": "A", "amount_owed": "100.00"}, {"name": "B"}]
        assert client.post("/api/bills", json=body(split_mode="custom", participants=parts),
                           headers=organiser).status_code == 422

    @pytest.mark.parametrize("override", [
        {"participants": []},
        {"participants": [{"name": "x"}] * 51},
        {"total_amount": "0"},
        {"total_amount": "-5"},
        {"total_amount": "1000000"},
        {"total_amount": "10.123"},
        {"title": ""},
        {"title": "x" * 121},
        {"game_mode": "rigged"},
        {"split_mode": "weird"},
        {"participants": [{"name": ""}]},
        {"participants": [{"name": "A", "phone": "123"}]},
    ], ids=lambda o: next(iter(o)))
    def test_rejects_invalid_input(self, client, db, organiser, override):
        assert client.post("/api/bills", json=body(**override), headers=organiser).status_code == 422
        assert not db.rows("bills")

    def test_phone_is_normalised_for_whatsapp(self, client, db, organiser):
        parts = [{"name": "Ali", "phone": "012-345 6789"}, {"name": "Bo", "phone": "+60 19 876 5432"}]
        assert client.post("/api/bills", json=body(participants=parts), headers=organiser).status_code == 200
        assert {p["phone"] for p in db.rows("participants")} == {"60123456789", "60198765432"}

    def test_client_cannot_set_the_qr_url(self, client, db, organiser):
        details = {"duitnow_id": "0123456789", "duitnow_qr_url": "https://evil.example/qr.png"}
        res = client.post("/api/bills", json=body(payment_details=details), headers=organiser)
        assert res.status_code == 200
        stored = db.rows("bills")[0]["payment_details"]
        assert stored == {"duitnow_id": "0123456789"}

    def test_no_orphan_bill_when_participants_fail(self, client, db, organiser):
        db.fail_inserts.add("participants")
        res = client.post("/api/bills", json=body(), headers=organiser)
        assert res.status_code == 500
        assert db.rows("bills") == []


class TestRead:
    def test_organiser_sees_full_view_with_flat_settled_payments(self, client, db, world, organiser):
        bill, (ali, siti, _) = world["bill"], world["participants"]
        db.insert_row("payments", {"participant_id": ali["id"], "bill_id": bill["id"], "amount": 20,
                                   "method": "cash"})
        db.insert_row("payments", {"participant_id": siti["id"], "bill_id": bill["id"], "amount": 20,
                                   "method": "tng", "status": "pending", "gateway_status": "pending"})
        res = client.get(f"/api/bills/{bill['id']}", headers=organiser)
        assert res.status_code == 200
        data = res.json()
        assert [p["phone"] for p in data["participants"]][0] == "60123456789"
        # the pending (unpaid) gateway attempt is not money received
        assert [p["participant_id"] for p in data["payments"]] == [ali["id"]]
        assert Decimal(str(data["collected"])) == Decimal("20")

    def test_list_only_returns_own_bills(self, client, db, world, organiser):
        db.seed_bill("77777777-7777-4777-8777-777777777777")
        res = client.get("/api/bills", headers=organiser)
        assert [b["id"] for b in res.json()] == [world["bill"]["id"]]


class TestUploads:
    @pytest.mark.parametrize("path,bucket", [("payment-qr", "payment-qr"), ("receipt", "receipts")])
    def test_stores_a_valid_image(self, client, db, world, organiser, path, bucket):
        bill = world["bill"]["id"]
        res = client.post(f"/api/bills/{bill}/{path}", headers=organiser,
                          files={"file": ("x.png", PNG, "image/png")})
        assert res.status_code == 200, res.text
        assert f"{bill}.png" in db.objects[bucket]
        assert db.objects[bucket][f"{bill}.png"]["options"]["content-type"] == "image/png"
        url = res.json()["duitnow_qr_url" if path == "payment-qr" else "receipt_url"]
        assert "?v=" in url  # cache-busted so a replaced image shows

    def test_qr_url_is_saved_on_the_bill(self, client, db, world, organiser):
        bill = world["bill"]["id"]
        url = client.post(f"/api/bills/{bill}/payment-qr", headers=organiser,
                          files={"file": ("x.png", PNG, "image/png")}).json()["duitnow_qr_url"]
        assert db.rows("bills", id=bill)[0]["payment_details"]["duitnow_qr_url"] == url

    def test_replacing_with_another_format_removes_the_old_file(self, client, db, world, organiser):
        bill = world["bill"]["id"]
        client.post(f"/api/bills/{bill}/payment-qr", headers=organiser, files={"file": ("a.png", PNG, "image/png")})
        client.post(f"/api/bills/{bill}/payment-qr", headers=organiser, files={"file": ("a.jpg", JPEG, "image/jpeg")})
        assert set(db.objects["payment-qr"]) == {f"{bill}.jpg"}

    def test_svg_is_rejected_even_when_labelled_png(self, client, db, world, organiser):
        res = client.post(f"/api/bills/{world['bill']['id']}/payment-qr", headers=organiser,
                          files={"file": ("x.png", SVG, "image/png")})
        assert res.status_code == 422
        assert not db.objects

    def test_content_type_header_is_not_trusted(self, client, db, world, organiser):
        res = client.post(f"/api/bills/{world['bill']['id']}/receipt", headers=organiser,
                          files={"file": ("x.png", b"not an image at all", "image/png")})
        assert res.status_code == 422

    def test_filename_cannot_choose_the_storage_path(self, client, db, world, organiser):
        bill = world["bill"]["id"]
        client.post(f"/api/bills/{bill}/receipt", headers=organiser,
                    files={"file": ("../../etc/x.p/../ng", PNG, "image/png")})
        assert list(db.objects["receipts"]) == [f"{bill}.png"]

    def test_oversize_is_rejected_without_storing(self, client, db, world, organiser):
        big = PNG + b"\x00" * (3 * 1024 * 1024)
        res = client.post(f"/api/bills/{world['bill']['id']}/payment-qr", headers=organiser,
                          files={"file": ("x.png", big, "image/png")})
        assert res.status_code == 413
        assert not db.objects

    def test_storage_outage_is_a_502_not_a_crash(self, client, db, world, organiser):
        db.fail_uploads.add("payment-qr")
        res = client.post(f"/api/bills/{world['bill']['id']}/payment-qr", headers=organiser,
                          files={"file": ("x.png", PNG, "image/png")})
        assert res.status_code == 502


class TestBalances:
    def test_only_settled_payments_reduce_what_is_owed(self, client, db, world, organiser):
        bill, (ali, siti, _raj) = world["bill"], world["participants"]
        db.insert_row("payments", {"participant_id": ali["id"], "bill_id": bill["id"], "amount": 20, "method": "cash"})
        db.insert_row("payments", {"participant_id": siti["id"], "bill_id": bill["id"], "amount": 20,
                                   "method": "tng", "status": "pending", "gateway_status": "pending"})
        res = client.get("/api/bills/organiser/balances", headers=organiser).json()
        owing = {c["name"]: Decimal(str(c["balance"])) for c in res["contacts"]}
        assert "Ali" not in owing  # paid
        assert owing["Siti"] == Decimal("20")  # pending gateway attempt does not count
        assert owing["Raj"] == Decimal("20")
        assert Decimal(str(res["total_outstanding"])) == Decimal("40")

    def test_empty_when_no_bills(self, client, organiser):
        res = client.get("/api/bills/organiser/balances", headers=organiser).json()
        assert res == {"contacts": [], "total_outstanding": "0"} or res["contacts"] == []

    def test_groups_the_same_phone_across_bills(self, client, db, organiser):
        db.seed_bill(FAKE_USER_ID, names=("Ali",), phones=("60123456789",), total="10.00")
        db.seed_bill(FAKE_USER_ID, names=("Ali B",), phones=("60123456789",), total="30.00")
        contacts = client.get("/api/bills/organiser/balances", headers=organiser).json()["contacts"]
        assert len(contacts) == 1 and contacts[0]["bill_count"] == 2
        assert Decimal(str(contacts[0]["balance"])) == Decimal("40")

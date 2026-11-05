from decimal import Decimal

import pytest

from app.api import payments as payments_module
from app.core.config import settings
from app.core.ws_manager import manager
from app.services.payment_gateway import PaymentResult
from tests.conftest import MISSING_ID


@pytest.fixture
def broadcasts(monkeypatch):
    sent = []

    async def record(bill_id, message):
        sent.append((bill_id, message))

    monkeypatch.setattr(manager, "broadcast", record)
    return sent


def confirm(client, world, who=0, **over):
    body = {"bill_id": world["bill"]["id"], "participant_id": world["participants"][who]["id"], "method": "cash"}
    body.update(over)
    return client.post("/api/payments/confirm", json=body)


class TestConfirm:
    def test_records_what_the_database_says_is_owed(self, client, db, world, broadcasts):
        res = confirm(client, world, method="tng")
        assert res.status_code == 200, res.text
        row = db.rows("payments")[0]
        assert row["amount"] == 20 and row["method"] == "tng"
        assert (row["status"], row["gateway_status"]) == ("confirmed", "manual")

    def test_broadcasts_to_the_organiser_dashboard(self, client, world, broadcasts):
        confirm(client, world)
        bill_id, message = broadcasts[0]
        assert bill_id == world["bill"]["id"]
        assert message["type"] == "payment_confirmed" and message["participant_name"] == "Ali"

    def test_a_client_cannot_pick_the_amount(self, client, db, world):
        assert confirm(client, world, amount="0.01").status_code == 422
        assert db.rows("payments") == []

    def test_a_matching_claimed_amount_is_fine(self, client, world):
        assert confirm(client, world, amount="20.00").status_code == 200

    def test_participant_must_belong_to_the_bill(self, client, db, world):
        other = db.seed_bill("77777777-7777-4777-8777-777777777777")
        res = client.post("/api/payments/confirm", json={
            "bill_id": world["bill"]["id"], "participant_id": other["participants"][0]["id"], "method": "cash"})
        assert res.status_code == 404
        assert db.rows("payments") == []

    def test_unknown_bill_is_404(self, client, world):
        assert confirm(client, world, bill_id=MISSING_ID).status_code == 404

    def test_second_confirmation_is_409_and_stores_nothing_new(self, client, db, world):
        assert confirm(client, world).status_code == 200
        assert confirm(client, world).status_code == 409
        assert len(db.rows("payments")) == 1

    def test_losing_a_race_is_409_not_a_double_payment(self, client, db, world, monkeypatch):
        # Both requests pass the pre-check; the database unique index decides.
        monkeypatch.setattr(payments_module, "_active_payment", lambda *_a, **_k: None)
        assert confirm(client, world).status_code == 200
        assert confirm(client, world).status_code == 409
        assert len(db.rows("payments")) == 1

    def test_a_failed_gateway_attempt_does_not_block_paying(self, client, db, world):
        db.insert_row("payments", {"participant_id": world["participants"][0]["id"], "bill_id": world["bill"]["id"],
                                   "amount": 20, "method": "tng", "status": "failed", "gateway_status": "failed"})
        assert confirm(client, world).status_code == 200

    @pytest.mark.parametrize("method", ["bitcoin", "", None])
    def test_method_is_validated(self, client, world, method):
        assert confirm(client, world, method=method).status_code == 422

    def test_with_the_gateway_on_only_cash_can_be_self_declared(self, client, db, world, monkeypatch):
        monkeypatch.setattr(settings, "PAYMENT_GATEWAY_ENABLED", True)
        assert confirm(client, world, method="tng").status_code == 400
        assert db.rows("payments") == []
        assert confirm(client, world, method="cash").status_code == 200

    def test_is_rate_limited(self, client, redis, world):
        redis.d["rl:confirm:testclient"] = "20"
        assert confirm(client, world).status_code == 429


class TestNudge:
    def test_returns_a_whatsapp_link_to_the_real_share_page(self, client, world, organiser, monkeypatch):
        monkeypatch.setattr(settings, "WEB_BASE_URL", "https://pay.example.my")
        ali = world["participants"][0]
        res = client.post(f"/api/payments/nudge/{ali['id']}", headers=organiser)
        assert res.status_code == 200
        link = res.json()["whatsapp_link"]
        assert link.startswith("https://wa.me/60123456789?text=")
        assert f"pay.example.my%2Fpay%2F{world['bill']['id']}" in link or f"pay.example.my/pay/{world['bill']['id']}" in link
        assert "bayar.lah" not in link  # the old hard-coded, non-resolvable domain

    def test_cooldown_blocks_a_second_nudge(self, client, world, organiser):
        ali = world["participants"][0]["id"]
        assert client.post(f"/api/payments/nudge/{ali}", headers=organiser).status_code == 200
        assert client.post(f"/api/payments/nudge/{ali}", headers=organiser).status_code == 429

    def test_no_link_without_a_phone_number(self, client, db, world, organiser):
        ali = world["participants"][0]
        db.rows("participants", id=ali["id"])[0]["phone"] = None
        assert client.post(f"/api/payments/nudge/{ali['id']}", headers=organiser).json()["whatsapp_link"] is None

    def test_does_not_nudge_someone_who_already_paid(self, client, world, organiser):
        confirm(client, world, who=0)
        res = client.post(f"/api/payments/nudge/{world['participants'][0]['id']}", headers=organiser)
        assert res.status_code == 409

    def test_unknown_participant_is_404(self, client, organiser):
        assert client.post(f"/api/payments/nudge/{MISSING_ID}", headers=organiser).status_code == 404

    def test_a_failed_check_does_not_burn_the_cooldown(self, client, redis, world, stranger):
        ali = world["participants"][0]["id"]
        assert client.post(f"/api/payments/nudge/{ali}", headers=stranger).status_code == 403
        assert f"nudge_cooldown:{ali}" not in redis.d


class TestBillPayments:
    def test_owner_lists_payments_without_phone_numbers(self, client, world, organiser):
        confirm(client, world)
        res = client.get(f"/api/payments/bill/{world['bill']['id']}", headers=organiser)
        assert res.status_code == 200 and res.json()[0]["participants"] == {"name": "Ali"}
        assert "6012345" not in res.text


class RecordingGateway:
    is_stub = False

    def __init__(self):
        self.calls = []

    async def create_payment(self, **kwargs):
        self.calls.append(kwargs)
        return PaymentResult(gateway_ref=f"hp_{len(self.calls)}", payment_url="https://pay.example/x")


@pytest.fixture
def gateway(monkeypatch):
    gw = RecordingGateway()
    monkeypatch.setattr(payments_module, "get_gateway", lambda: gw)
    return gw


def initiate(client, world, who=0, **over):
    body = {"bill_id": world["bill"]["id"], "participant_id": world["participants"][who]["id"], "method": "tng"}
    body.update(over)
    return client.post("/api/payments/initiate", json=body)


class TestInitiate:
    def test_creates_a_pending_row_that_is_not_yet_paid(self, client, db, world, gateway):
        res = initiate(client, world)
        assert res.status_code == 200, res.text
        row = db.rows("payments")[0]
        assert (row["status"], row["gateway_status"], row["gateway_ref"]) == ("pending", "pending", "hp_1")
        assert row["amount"] == 20

    def test_asks_the_gateway_for_the_owed_amount_and_our_own_webhook(self, client, world, gateway, monkeypatch):
        monkeypatch.setattr(settings, "BACKEND_PUBLIC_URL", "https://api.example.my/")
        initiate(client, world)
        call = gateway.calls[0]
        assert call["amount"] == Decimal("20.00")
        assert call["webhook_url"] == "https://api.example.my/api/payments/webhook/gateway"
        assert call["reference"] == f"{world['bill']['id']}:{world['participants'][0]['id']}"

    def test_a_client_cannot_pick_the_amount(self, client, db, world, gateway):
        assert initiate(client, world, amount="0.01").status_code == 422
        assert gateway.calls == [] and db.rows("payments") == []

    def test_cash_is_not_a_gateway_method(self, client, world, gateway):
        assert initiate(client, world, method="cash").status_code == 422

    def test_participant_must_belong_to_the_bill(self, client, db, world, gateway):
        other = db.seed_bill("77777777-7777-4777-8777-777777777777")
        res = client.post("/api/payments/initiate", json={
            "bill_id": world["bill"]["id"], "participant_id": other["participants"][0]["id"], "method": "tng"})
        assert res.status_code == 404 and gateway.calls == []

    def test_an_abandoned_attempt_is_retired_so_the_participant_can_retry(self, client, db, world, gateway):
        initiate(client, world)
        assert initiate(client, world).status_code == 200
        statuses = sorted(r["gateway_status"] for r in db.rows("payments"))
        assert statuses == ["expired", "pending"]

    def test_an_already_paid_participant_cannot_start_another(self, client, world, gateway):
        confirm(client, world)
        assert initiate(client, world).status_code == 409 and gateway.calls == []

    def test_unavailable_in_production_when_the_gateway_is_off(self, client, world, gateway, monkeypatch):
        monkeypatch.setattr(settings, "ENV", "production")
        assert initiate(client, world).status_code == 503

    def test_provider_outage_is_a_502(self, client, db, world, monkeypatch):
        import httpx

        class Down(RecordingGateway):
            async def create_payment(self, **_k):
                raise httpx.ConnectError("boom")

        monkeypatch.setattr(payments_module, "get_gateway", lambda: Down())
        assert initiate(client, world).status_code == 502
        assert db.rows("payments") == []

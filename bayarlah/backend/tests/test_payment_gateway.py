"""Tests for the payment gateway service abstraction layer."""
import asyncio
import hashlib
import hmac as hmac_mod
import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure gateway is in stub mode by default
os.environ.setdefault("PAYMENT_GATEWAY_ENABLED", "false")

from app.services.payment_gateway import (
    HitPayGateway,
    PaymentGateway,
    PaymentResult,
    StubGateway,
    get_gateway,
    HITPAY_METHOD_MAP,
)


# ── PaymentResult ────────────────────────────────────────────────────────────


class TestPaymentResult:
    def test_creation_with_defaults(self):
        r = PaymentResult(gateway_ref="ref123")
        assert r.gateway_ref == "ref123"
        assert r.payment_url is None
        assert r.qr_url is None
        assert r.status == "pending"
        assert r.raw == {}

    def test_creation_with_all_fields(self):
        r = PaymentResult(
            gateway_ref="ref456",
            payment_url="https://pay.example.com/checkout",
            qr_url="https://pay.example.com/qr.png",
            status="completed",
            raw={"id": "ref456", "amount": 25.0},
        )
        assert r.payment_url == "https://pay.example.com/checkout"
        assert r.qr_url == "https://pay.example.com/qr.png"
        assert r.status == "completed"
        assert r.raw["amount"] == 25.0


# ── StubGateway ──────────────────────────────────────────────────────────────


class TestStubGateway:
    def setup_method(self):
        self.gw = StubGateway()

    def test_is_payment_gateway(self):
        assert isinstance(self.gw, PaymentGateway)

    def test_create_payment_returns_stub_result(self):
        result = asyncio.get_event_loop().run_until_complete(
            self.gw.create_payment(
                amount=Decimal("50.00"),
                currency="MYR",
                method="duitnow",
                reference="bill1:part1",
                redirect_url="http://localhost:3000/pay/bill1?status=success",
                webhook_url="http://localhost:8000/api/payments/webhook/gateway",
            )
        )
        assert result.gateway_ref == "stub_ref_local"
        assert result.payment_url is not None
        assert result.status == "pending"

    def test_verify_webhook_always_returns_true(self):
        assert self.gw.verify_webhook(payload=b"anything", signature="anything") is True

    def test_parse_webhook_returns_verified(self):
        parsed = self.gw.parse_webhook({
            "reference_number": "bill123:part456",
            "amount": "25.00",
            "status": "completed",
        })
        assert parsed["status"] == "verified"
        assert parsed["reference"] == "bill123:part456"
        assert parsed["amount"] == Decimal("25.00")

    def test_parse_webhook_empty_body(self):
        parsed = self.gw.parse_webhook({})
        assert parsed["status"] == "verified"
        assert parsed["reference"] == ""
        assert parsed["gateway_ref"] == "stub_ref_local"


# ── HitPayGateway ────────────────────────────────────────────────────────────


class TestHitPayGateway:
    def setup_method(self):
        """Create a HitPayGateway with test credentials."""
        with patch("app.services.payment_gateway.settings") as mock_settings:
            mock_settings.HITPAY_SANDBOX = True
            mock_settings.HITPAY_API_KEY = "test_api_key_123"
            mock_settings.HITPAY_WEBHOOK_SALT = "test_webhook_salt"
            mock_settings.WEB_BASE_URL = "http://localhost:3000"
            self.gw = HitPayGateway()

    def test_is_payment_gateway(self):
        assert isinstance(self.gw, PaymentGateway)

    def test_sandbox_base_url(self):
        assert "sandbox" in self.gw.base_url

    def test_production_base_url(self):
        with patch("app.services.payment_gateway.settings") as mock_settings:
            mock_settings.HITPAY_SANDBOX = False
            mock_settings.HITPAY_API_KEY = "prod_key"
            mock_settings.HITPAY_WEBHOOK_SALT = "prod_salt"
            gw = HitPayGateway()
            assert "sandbox" not in gw.base_url
            assert "api.hit-pay.com" in gw.base_url

    def test_verify_webhook_correct_signature(self):
        payload = b'{"status":"completed","amount":"50.00"}'
        expected_sig = hmac_mod.new(
            b"test_webhook_salt", payload, hashlib.sha256
        ).hexdigest()
        assert self.gw.verify_webhook(payload=payload, signature=expected_sig) is True

    def test_verify_webhook_wrong_signature(self):
        payload = b'{"status":"completed","amount":"50.00"}'
        assert self.gw.verify_webhook(payload=payload, signature="wrong_sig") is False

    def test_verify_webhook_empty_signature(self):
        payload = b"test"
        assert self.gw.verify_webhook(payload=payload, signature="") is False

    def test_parse_webhook_completed(self):
        body = {
            "payment_request_id": "hp_req_abc",
            "reference_number": "bill-id:participant-id",
            "status": "completed",
            "amount": "33.50",
            "payment_methods": "duitnow",
        }
        parsed = self.gw.parse_webhook(body)
        assert parsed["gateway_ref"] == "hp_req_abc"
        assert parsed["reference"] == "bill-id:participant-id"
        assert parsed["status"] == "verified"
        assert parsed["amount"] == Decimal("33.50")
        assert parsed["method"] == "duitnow"

    def test_parse_webhook_failed(self):
        body = {
            "id": "hp_id_xyz",
            "reference_number": "bill1:part1",
            "status": "failed",
            "amount": "10.00",
        }
        parsed = self.gw.parse_webhook(body)
        assert parsed["status"] == "failed"

    def test_parse_webhook_pending(self):
        body = {
            "id": "hp_id_pending",
            "reference_number": "bill2:part2",
            "status": "pending",
            "amount": "20.00",
        }
        parsed = self.gw.parse_webhook(body)
        assert parsed["status"] == "pending"

    @pytest.mark.asyncio
    async def test_create_payment_unsupported_method(self):
        with pytest.raises(ValueError, match="Unsupported gateway method"):
            await self.gw.create_payment(
                amount=Decimal("10.00"),
                currency="MYR",
                method="cash",
                reference="bill:part",
                redirect_url="http://localhost",
                webhook_url="http://localhost",
            )

    @pytest.mark.asyncio
    async def test_create_payment_calls_hitpay_api(self):
        """Test that create_payment makes the correct HTTP call."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "hp_req_new",
            "url": "https://api.sandbox.hit-pay.com/checkout/hp_req_new",
            "qr_code_url": "https://api.sandbox.hit-pay.com/qr/hp_req_new.png",
            "status": "pending",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.payment_gateway.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client_instance

            result = await self.gw.create_payment(
                amount=Decimal("25.00"),
                currency="MYR",
                method="duitnow",
                reference="bill-abc:part-xyz",
                redirect_url="http://localhost:3000/pay/bill-abc?status=success",
                webhook_url="http://localhost:8000/api/payments/webhook/gateway",
                description="Test payment",
            )

            assert result.gateway_ref == "hp_req_new"
            assert result.payment_url == "https://api.sandbox.hit-pay.com/checkout/hp_req_new"
            assert result.qr_url == "https://api.sandbox.hit-pay.com/qr/hp_req_new.png"
            assert result.status == "pending"

            # Verify the POST was called with correct args
            mock_client_instance.post.assert_called_once()
            call_args = mock_client_instance.post.call_args
            assert "payment-requests" in call_args[0][0]
            json_body = call_args[1]["json"]
            assert json_body["amount"] == 25.0
            assert json_body["currency"] == "MYR"
            assert json_body["payment_methods"] == ["duitnow"]
            assert json_body["generate_qr"] is True
            assert json_body["reference_number"] == "bill-abc:part-xyz"

    @pytest.mark.asyncio
    async def test_create_payment_tng_method(self):
        """TnG should map to touch_n_go and not request QR generation."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "hp_tng",
            "url": "https://api.sandbox.hit-pay.com/checkout/hp_tng",
            "status": "pending",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.payment_gateway.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_client_instance

            result = await self.gw.create_payment(
                amount=Decimal("15.00"),
                currency="MYR",
                method="tng",
                reference="bill:part",
                redirect_url="http://localhost:3000",
                webhook_url="http://localhost:8000",
            )

            assert result.gateway_ref == "hp_tng"
            json_body = mock_client_instance.post.call_args[1]["json"]
            assert json_body["payment_methods"] == ["touch_n_go"]
            assert "generate_qr" not in json_body


# ── get_gateway factory ──────────────────────────────────────────────────────


class TestGetGateway:
    def test_returns_stub_when_disabled(self):
        with patch("app.services.payment_gateway.settings") as mock_settings:
            mock_settings.PAYMENT_GATEWAY_ENABLED = False
            gw = get_gateway()
            assert isinstance(gw, StubGateway)

    def test_returns_hitpay_when_enabled_with_key(self):
        with patch("app.services.payment_gateway.settings") as mock_settings:
            mock_settings.PAYMENT_GATEWAY_ENABLED = True
            mock_settings.PAYMENT_GATEWAY_PROVIDER = "hitpay"
            mock_settings.HITPAY_API_KEY = "real_key"
            mock_settings.HITPAY_WEBHOOK_SALT = "real_salt"
            mock_settings.HITPAY_SANDBOX = True
            mock_settings.WEB_BASE_URL = "http://localhost:3000"
            gw = get_gateway()
            assert isinstance(gw, HitPayGateway)

    def test_returns_stub_when_enabled_but_no_key(self):
        with patch("app.services.payment_gateway.settings") as mock_settings:
            mock_settings.PAYMENT_GATEWAY_ENABLED = True
            mock_settings.PAYMENT_GATEWAY_PROVIDER = "hitpay"
            mock_settings.HITPAY_API_KEY = ""
            gw = get_gateway()
            assert isinstance(gw, StubGateway)

    def test_returns_stub_for_unknown_provider(self):
        with patch("app.services.payment_gateway.settings") as mock_settings:
            mock_settings.PAYMENT_GATEWAY_ENABLED = True
            mock_settings.PAYMENT_GATEWAY_PROVIDER = "unknown_provider"
            gw = get_gateway()
            assert isinstance(gw, StubGateway)


# ── HITPAY_METHOD_MAP ────────────────────────────────────────────────────────


class TestMethodMap:
    def test_duitnow_mapping(self):
        assert HITPAY_METHOD_MAP["duitnow"] == ["duitnow"]

    def test_tng_mapping(self):
        assert HITPAY_METHOD_MAP["tng"] == ["touch_n_go"]

    def test_bank_mapping(self):
        assert HITPAY_METHOD_MAP["bank"] == ["fpx"]

    def test_cash_not_in_map(self):
        assert "cash" not in HITPAY_METHOD_MAP

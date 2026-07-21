"""Payment gateway abstraction layer (Level 2 foundation).

Currently provides a HitPay implementation. The gateway is opt-in —
when PAYMENT_GATEWAY_ENABLED=False (default), payments use the honor-system
confirmation flow (Level 1). When enabled, /api/payments/initiate creates a
real payment request via the gateway and /api/payments/webhook/gateway
receives verified callbacks.

Usage:
    from app.services.payment_gateway import get_gateway
    gw = get_gateway()
    result = await gw.create_payment(...)
"""

from __future__ import annotations

import hashlib
import hmac
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import settings


# ── Method mapping ─────────────────────────────────────────────────────────────

HITPAY_METHOD_MAP: dict[str, list[str]] = {
    "duitnow": ["duitnow"],
    "tng": ["touch_n_go"],
    "bank": ["fpx"],
    # "cash" is never gateway-routed
}


# ── Abstract interface ─────────────────────────────────────────────────────────


class PaymentResult:
    """Standardised response from any gateway."""

    def __init__(
        self,
        *,
        gateway_ref: str,
        payment_url: str | None = None,
        qr_url: str | None = None,
        status: str = "pending",
        raw: dict[str, Any] | None = None,
    ):
        self.gateway_ref = gateway_ref
        self.payment_url = payment_url
        self.qr_url = qr_url
        self.status = status
        self.raw = raw or {}


class PaymentGateway(ABC):
    """Abstract payment gateway interface."""

    @abstractmethod
    async def create_payment(
        self,
        *,
        amount: Decimal,
        currency: str,
        method: str,
        reference: str,
        redirect_url: str,
        webhook_url: str,
        description: str = "",
    ) -> PaymentResult:
        """Create a payment request and return the redirect/QR info."""
        ...

    @abstractmethod
    def verify_webhook(self, *, payload: bytes, signature: str) -> bool:
        """Verify the webhook signature from the gateway."""
        ...

    @abstractmethod
    def parse_webhook(self, body: dict[str, Any]) -> dict[str, Any]:
        """Parse webhook body into a normalised dict with: reference, status, amount, method, gateway_ref."""
        ...


# ── HitPay implementation ──────────────────────────────────────────────────────


class HitPayGateway(PaymentGateway):
    """HitPay Malaysia payment gateway.

    Docs: https://docs.hitpayapp.com/apis/payment-request/create-request
    """

    def __init__(self):
        self.sandbox = settings.HITPAY_SANDBOX
        self.api_key = settings.HITPAY_API_KEY
        self.webhook_salt = settings.HITPAY_WEBHOOK_SALT
        self.base_url = (
            "https://api.sandbox.hit-pay.com/v1"
            if self.sandbox
            else "https://api.hit-pay.com/v1"
        )

    async def create_payment(
        self,
        *,
        amount: Decimal,
        currency: str = "MYR",
        method: str,
        reference: str,
        redirect_url: str,
        webhook_url: str,
        description: str = "",
    ) -> PaymentResult:
        payment_methods = HITPAY_METHOD_MAP.get(method)
        if not payment_methods:
            raise ValueError(f"Unsupported gateway method: {method}")

        request_body: dict[str, Any] = {
            "amount": float(amount),
            "currency": currency,
            "payment_methods": payment_methods,
            "reference_number": reference,
            "redirect_url": redirect_url,
            "webhook": webhook_url,
            "purpose": description or "Bayar.lah bill payment",
        }

        # DuitNow: request QR generation
        if method == "duitnow":
            request_body["generate_qr"] = True

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/payment-requests",
                headers={
                    "X-BUSINESS-API-KEY": self.api_key,
                    "Content-Type": "application/json",
                },
                json=request_body,
            )
            resp.raise_for_status()
            data = resp.json()

        return PaymentResult(
            gateway_ref=data.get("id", ""),
            payment_url=data.get("url"),
            qr_url=data.get("qr_code_url") or data.get("qr"),
            status="pending",
            raw=data,
        )

    def verify_webhook(self, *, payload: bytes, signature: str) -> bool:
        """HitPay uses HMAC-SHA256 with the webhook salt."""
        if not self.webhook_salt:
            return False
        expected = hmac.new(
            self.webhook_salt.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, body: dict[str, Any]) -> dict[str, Any]:
        """Normalise HitPay webhook payload."""
        return {
            "gateway_ref": body.get("payment_request_id", body.get("id", "")),
            "reference": body.get("reference_number", ""),
            "status": "verified" if body.get("status") == "completed" else body.get("status", "unknown"),
            "amount": Decimal(str(body.get("amount", "0"))),
            "method": body.get("payment_methods", "unknown"),
        }


# ── Stub gateway for testing without real credentials ──────────────────────────


class StubGateway(PaymentGateway):
    """No-op gateway for local development / testing."""

    async def create_payment(self, **kwargs: Any) -> PaymentResult:
        return PaymentResult(
            gateway_ref="stub_ref_local",
            payment_url=f"{settings.WEB_BASE_URL}/pay/stub-success",
            qr_url=None,
            status="pending",
        )

    def verify_webhook(self, *, payload: bytes, signature: str) -> bool:
        return True

    def parse_webhook(self, body: dict[str, Any]) -> dict[str, Any]:
        return {
            "gateway_ref": "stub_ref_local",
            "reference": body.get("reference_number", ""),
            "status": "verified",
            "amount": Decimal(str(body.get("amount", "0"))),
            "method": "stub",
        }


# ── Factory ────────────────────────────────────────────────────────────────────


def get_gateway() -> PaymentGateway:
    """Return the configured payment gateway instance.

    Uses StubGateway when gateway is disabled or in development without keys.
    """
    if not settings.PAYMENT_GATEWAY_ENABLED:
        return StubGateway()

    provider = settings.PAYMENT_GATEWAY_PROVIDER.lower()
    if provider == "hitpay":
        if not settings.HITPAY_API_KEY:
            return StubGateway()
        return HitPayGateway()

    # Future: add "stripe", "airwallex" branches here
    return StubGateway()

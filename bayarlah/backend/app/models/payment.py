from pydantic import BaseModel, UUID4
from decimal import Decimal
from datetime import datetime
from typing import Optional


class PaymentConfirm(BaseModel):
    participant_id: UUID4
    bill_id: UUID4
    amount: Decimal
    method: str  # duitnow | tng | bank | cash


class PaymentResponse(BaseModel):
    id: UUID4
    participant_id: UUID4
    bill_id: UUID4
    amount: Decimal
    method: str
    confirmed_at: datetime
    status: str
    gateway_ref: Optional[str] = None
    gateway_status: Optional[str] = None


# ── Level 2: Gateway-initiated payment ────────────────────────────────────────


class PaymentInitiateRequest(BaseModel):
    """Request to initiate a gateway-verified payment (Level 2)."""

    participant_id: UUID4
    bill_id: UUID4
    amount: Decimal
    method: str  # duitnow | tng | bank (not cash — cash stays honor-system)


class PaymentInitiateResponse(BaseModel):
    """Response with redirect URL or QR code for member to complete payment."""

    gateway_ref: str
    payment_url: Optional[str] = None
    qr_url: Optional[str] = None
    status: str = "pending"

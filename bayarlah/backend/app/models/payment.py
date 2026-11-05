from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import UUID4, BaseModel, Field

PaymentMethod = Literal["duitnow", "tng", "bank", "cash"]
GatewayMethod = Literal["duitnow", "tng", "bank"]


class PaymentConfirm(BaseModel):
    """Member says "I paid" (honour system, Level 1).

    The amount is always taken from the participant's record on the server. A
    client may still send it; if it disagrees with what is owed the request is
    rejected rather than silently trusted.
    """

    participant_id: UUID4
    bill_id: UUID4
    method: PaymentMethod
    amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)


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
    """Request to initiate a gateway-verified payment (Level 2). Cash stays
    honour-system and is rejected here by the type itself."""

    participant_id: UUID4
    bill_id: UUID4
    method: GatewayMethod
    amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=10, decimal_places=2)


class PaymentInitiateResponse(BaseModel):
    """Response with redirect URL or QR code for member to complete payment."""

    gateway_ref: str
    payment_url: Optional[str] = None
    qr_url: Optional[str] = None
    status: str = "pending"

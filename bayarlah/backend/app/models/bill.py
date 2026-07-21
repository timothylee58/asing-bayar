from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


class PaymentDetails(BaseModel):
    """Organiser-provided payment destination details (Level 1).

    Members see these on the share page so they know *where* to send money.
    """

    duitnow_id: Optional[str] = None
    duitnow_id_type: Optional[str] = None  # "phone" | "nric" | "business"
    duitnow_qr_url: Optional[str] = None  # Supabase Storage URL of uploaded QR image
    tng_phone: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    bank_holder: Optional[str] = None


class ParticipantCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    amount_owed: Optional[Decimal] = None


class BillCreate(BaseModel):
    title: str
    total_amount: Decimal
    description: Optional[str] = None
    due_date: Optional[date] = None
    emoji_tag: str = "🍽️"
    game_mode: str = "equal"
    split_mode: str = "equal"
    participants: list[ParticipantCreate]
    payment_details: Optional[PaymentDetails] = None


class BillResponse(BaseModel):
    id: UUID4
    title: str
    total_amount: Decimal
    per_person: Optional[Decimal]
    description: Optional[str]
    due_date: Optional[date]
    emoji_tag: str
    status: str
    game_mode: str
    created_at: datetime
    share_url: str
    receipt_url: Optional[str] = None
    payment_details: Optional[PaymentDetails] = None


class ParticipantResponse(BaseModel):
    id: UUID4
    name: str
    phone: Optional[str]
    amount_owed: Optional[Decimal]
    is_organiser: bool

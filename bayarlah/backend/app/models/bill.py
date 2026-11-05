import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import UUID4, BaseModel, Field, StringConstraints, field_validator

GameMode = Literal["equal", "tangga", "roulette", "dadu", "toss"]
SplitMode = Literal["equal", "custom"]

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
Money = Annotated[Decimal, Field(max_digits=10, decimal_places=2)]


def normalise_phone(value: Optional[str]) -> Optional[str]:
    """Digits-only international form, as wa.me expects (e.g. 0123456789 -> 60123456789).

    Malaysia is the default market, so a leading 0 is treated as a local number.
    """
    if value is None or not value.strip():
        return None  # genuinely blank means "no phone"
    digits = re.sub(r"\D", "", value)
    if not digits:
        raise ValueError("phone must contain digits")  # "abc" is a typo, not an absence
    if digits.startswith("0"):
        digits = "60" + digits[1:]
    if not 8 <= len(digits) <= 15:
        raise ValueError("phone must be 8-15 digits")
    return digits


class PaymentDetailsInput(BaseModel):
    """Payment destinations an organiser may supply. The QR image URL is
    deliberately absent: it is only ever set by the QR upload endpoint, so
    clients cannot point payers at an arbitrary image."""

    duitnow_id: Optional[ShortText] = None
    duitnow_id_type: Optional[Literal["phone", "nric", "business"]] = None
    tng_phone: Optional[ShortText] = None
    bank_name: Optional[ShortText] = None
    bank_account: Optional[ShortText] = None
    bank_holder: Optional[ShortText] = None


class PaymentDetails(PaymentDetailsInput):
    """As stored / returned: input fields plus the server-managed QR URL."""

    duitnow_qr_url: Optional[str] = None


class ParticipantCreate(BaseModel):
    name: Name
    phone: Optional[str] = None
    amount_owed: Optional[Money] = Field(default=None, ge=0)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: Optional[str]) -> Optional[str]:
        return normalise_phone(v)


class BillCreate(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    total_amount: Money = Field(gt=0, le=100000)
    description: Optional[Annotated[str, StringConstraints(max_length=500)]] = None
    due_date: Optional[date] = None
    emoji_tag: Annotated[str, StringConstraints(max_length=16)] = "🍽️"
    game_mode: GameMode = "equal"
    split_mode: SplitMode = "equal"
    participants: list[ParticipantCreate] = Field(min_length=1, max_length=50)
    payment_details: Optional[PaymentDetailsInput] = None


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


# ── Public (share-link) view ──────────────────────────────────────────────────
# Everything a member needs to pay, and nothing else: no phone numbers, no
# organiser id. response_model filtering makes this a hard guarantee.


class PublicParticipant(BaseModel):
    id: UUID4
    name: str
    amount_owed: Optional[float] = None


class PublicPayment(BaseModel):
    id: UUID4
    participant_id: UUID4
    amount: float
    method: str
    confirmed_at: Optional[datetime] = None


class PublicBillResponse(BaseModel):
    id: UUID4
    title: str
    description: Optional[str] = None
    total_amount: float
    per_person: Optional[float] = None
    due_date: Optional[date] = None
    emoji_tag: str
    status: str
    game_mode: str
    receipt_url: Optional[str] = None
    payment_details: Optional[PaymentDetails] = None
    participants: list[PublicParticipant]
    payments: list[PublicPayment]
    collected: float

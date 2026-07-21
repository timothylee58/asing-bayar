from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


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


class ParticipantResponse(BaseModel):
    id: UUID4
    name: str
    phone: Optional[str]
    amount_owed: Optional[Decimal]
    is_organiser: bool

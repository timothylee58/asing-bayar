from pydantic import BaseModel, UUID4
from typing import Optional
from decimal import Decimal
from datetime import datetime


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

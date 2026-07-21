from pydantic import BaseModel
from typing import Optional
from decimal import Decimal


class ContactBalance(BaseModel):
    phone: Optional[str]
    name: str
    total_owed: Decimal
    total_paid: Decimal
    balance: Decimal
    bill_count: int


class BalancesResponse(BaseModel):
    contacts: list[ContactBalance]
    total_outstanding: Decimal

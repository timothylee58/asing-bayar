from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


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

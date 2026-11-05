"""Unauthenticated, read-only endpoints for the member share page.

Possession of the bill id (the share link) is the capability. Responses are
filtered through PublicBillResponse, so phone numbers and the organiser id can
never leak from here even if the underlying rows contain them.
"""
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from supabase import Client

from app.core.access import fetch_participants, fetch_settled_payments, require_bill
from app.core.dependencies import get_supabase, rate_limit
from app.models.bill import PublicBillResponse
from app.services.money import to_money

router = APIRouter()


@router.get(
    "/bills/{bill_id}",
    response_model=PublicBillResponse,
    # Generous on purpose: mobile carriers put many payers behind one IP (CGNAT), and each
    # open pay page polls every 8s. This only needs to stop scrapers, not friends.
    dependencies=[Depends(rate_limit("public_bill", limit=600, window_seconds=60))],
)
async def get_public_bill(bill_id: UUID, supabase: Client = Depends(get_supabase)):
    bill = require_bill(supabase, bill_id)
    participants = fetch_participants(supabase, bill_id)
    payments = fetch_settled_payments(supabase, bill_id)
    collected = sum((to_money(p["amount"]) for p in payments), Decimal("0"))
    return {**bill, "participants": participants, "payments": payments, "collected": collected}

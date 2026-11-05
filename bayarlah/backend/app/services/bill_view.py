"""One place that assembles a bill with its participants and settled payments,
used by the REST routes and the WebSocket init message so they never diverge."""
from decimal import Decimal

from supabase import Client

from app.core.access import fetch_participants, fetch_settled_payments
from app.services.money import to_money


def build_bill_view(supabase: Client, bill: dict) -> dict:
    """Full view (includes participant phone numbers) - organiser only.

    `payments` is a flat list of *settled* payments (honour-system confirmed or
    gateway verified). Pending/failed gateway attempts are not money received.
    """
    participants = fetch_participants(supabase, bill["id"])
    payments = fetch_settled_payments(supabase, bill["id"])
    collected = sum((to_money(p["amount"]) for p in payments), Decimal("0"))
    return {
        **bill,
        "share_url": f"/pay/{bill['id']}",
        "participants": participants,
        "payments": payments,
        "collected": collected,
    }

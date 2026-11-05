"""Authorisation + data-loading helpers shared by the routers.

The backend talks to Supabase with the service-role key, which bypasses RLS.
That makes these helpers the real access-control layer: any route that reads or
writes a bill's data must go through one of them.
"""
from collections.abc import Iterable
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from supabase import Client

# A payment only counts as money received when it was confirmed by the honour
# system ("manual") or verified by the gateway webhook ("verified").
SETTLED_GATEWAY_STATUSES = ("manual", "verified")
ACTIVE_GATEWAY_STATUSES = ("manual", "pending", "verified")


def first(res: Any) -> dict | None:
    """First row of a PostgREST response, or None. Avoids .single(), which raises
    on zero rows instead of returning nothing."""
    data = getattr(res, "data", None)
    if isinstance(data, list):
        return data[0] if data else None
    return data or None


def fetch_bill(supabase: Client, bill_id: UUID | str) -> dict | None:
    res = supabase.table("bills").select("*").eq("id", str(bill_id)).limit(1).execute()
    return first(res)


def require_bill(supabase: Client, bill_id: UUID | str) -> dict:
    bill = fetch_bill(supabase, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill


def require_bill_owner(supabase: Client, bill_id: UUID | str, user) -> dict:
    """The bill, if `user` organises it. 404 if missing, 403 if someone else's."""
    bill = require_bill(supabase, bill_id)
    if str(bill.get("organiser_id")) != str(user.id):
        raise HTTPException(status_code=403, detail="You do not own this bill")
    return bill


def fetch_participants(supabase: Client, bill_id: UUID | str) -> list[dict]:
    res = (
        supabase.table("participants")
        .select("*")
        .eq("bill_id", str(bill_id))
        .execute()
    )
    return list(res.data or [])


def fetch_participant(
    supabase: Client, bill_id: UUID | str, participant_id: UUID | str
) -> dict | None:
    """A participant, only if they belong to `bill_id`."""
    res = (
        supabase.table("participants")
        .select("*")
        .eq("id", str(participant_id))
        .eq("bill_id", str(bill_id))
        .limit(1)
        .execute()
    )
    return first(res)


def is_settled(payment: dict) -> bool:
    return (payment.get("gateway_status") or "manual") in SETTLED_GATEWAY_STATUSES


def fetch_settled_payments(supabase: Client, bill_id: UUID | str) -> list[dict]:
    res = (
        supabase.table("payments")
        .select("*")
        .eq("bill_id", str(bill_id))
        .execute()
    )
    return [p for p in (res.data or []) if is_settled(p)]


def assert_same_participants(
    supabase: Client, bill_id: UUID | str, participant_ids: Iterable[UUID | str]
) -> list[dict]:
    """Require `participant_ids` to be exactly the bill's participants (no
    strangers, no duplicates, none missing). Returns the participant rows."""
    ids = [str(p) for p in participant_ids]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=422, detail="Duplicate participant ids")
    rows = fetch_participants(supabase, bill_id)
    if set(ids) != {str(r["id"]) for r in rows}:
        raise HTTPException(
            status_code=422,
            detail="participant_ids must be exactly the participants of this bill",
        )
    return rows


def is_unique_violation(exc: Exception) -> bool:
    """True for a Postgres unique-constraint violation surfaced by PostgREST."""
    code = getattr(exc, "code", None)
    if code is None and exc.args and isinstance(exc.args[0], dict):
        code = exc.args[0].get("code")
    return str(code) == "23505"


def amount_owed(participant: dict, bill: dict) -> Decimal:
    owed = participant.get("amount_owed")
    if owed is None:
        owed = bill.get("per_person")
    if owed is None:
        raise HTTPException(status_code=409, detail="No amount is set for this participant")
    return Decimal(str(owed)).quantize(Decimal("0.01"))

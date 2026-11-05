import time
from collections import defaultdict
from collections.abc import Iterator
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from loguru import logger
from supabase import Client

from app.core.access import is_settled, require_bill_owner
from app.core.config import settings
from app.core.dependencies import get_current_user, get_supabase
from app.models.balance import BalancesResponse, ContactBalance
from app.models.bill import BillCreate, BillResponse
from app.services.bill_view import build_bill_view
from app.services.images import read_image
from app.services.money import split_equally, to_money

router = APIRouter()

QR_BUCKET = "payment-qr"
QR_MAX_BYTES = 3 * 1024 * 1024
RECEIPT_MAX_BYTES = 5 * 1024 * 1024
IMAGE_EXTENSIONS = ("png", "jpg", "webp", "gif")


def _chunks(items: list, size: int = 100) -> Iterator[list]:
    """PostgREST puts `in.(...)` filters in the URL; chunk to stay under length limits."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


@router.post("", response_model=BillResponse)
async def create_bill(
    payload: BillCreate,
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    total = to_money(payload.total_amount)
    n = len(payload.participants)

    if payload.split_mode == "custom":
        if any(p.amount_owed is None for p in payload.participants):
            raise HTTPException(
                status_code=422,
                detail="All participants must have amount_owed for custom split",
            )
        shares = [to_money(p.amount_owed) for p in payload.participants]
        if sum(shares, Decimal("0")) != total:
            raise HTTPException(
                status_code=422,
                detail="Sum of participant amounts must equal total_amount",
            )
        per_person = None
    else:
        shares = split_equally(total, n)
        per_person = shares[-1]  # the smaller share when the total doesn't divide evenly

    details = (
        payload.payment_details.model_dump(exclude_none=True)
        if payload.payment_details
        else None
    )
    bill_data = {
        "organiser_id": str(user.id),
        "title": payload.title,
        "description": payload.description,
        "total_amount": float(total),
        "per_person": float(per_person) if per_person is not None else None,
        "due_date": payload.due_date.isoformat() if payload.due_date else None,
        "emoji_tag": payload.emoji_tag,
        "game_mode": payload.game_mode,
        "payment_details": details,
    }

    bill = supabase.table("bills").insert(bill_data).execute().data[0]

    rows = [
        {
            "bill_id": bill["id"],
            "name": p.name,
            "phone": p.phone,
            "amount_owed": float(shares[i]),
            "is_organiser": False,
        }
        for i, p in enumerate(payload.participants)
    ]
    try:
        supabase.table("participants").insert(rows).execute()
    except Exception as exc:  # noqa: BLE001
        # No transaction across the two inserts: don't leave a bill with nobody on it.
        logger.error(f"participant insert failed for bill {bill['id']}: {exc}")
        supabase.table("bills").delete().eq("id", bill["id"]).execute()
        raise HTTPException(status_code=500, detail="Could not create bill") from exc

    return {**bill, "share_url": f"/pay/{bill['id']}"}


@router.get("/organiser/balances", response_model=BalancesResponse)
async def get_balances(
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    bills = supabase.table("bills").select("id").eq("organiser_id", str(user.id)).execute()
    bill_ids = [b["id"] for b in (bills.data or [])]
    if not bill_ids:
        return BalancesResponse(contacts=[], total_outstanding=Decimal("0"))

    participants: list[dict] = []
    for chunk in _chunks(bill_ids):
        res = (
            supabase.table("participants")
            .select("id, name, phone, amount_owed, bill_id")
            .in_("bill_id", chunk)
            .execute()
        )
        participants.extend(res.data or [])
    if not participants:
        return BalancesResponse(contacts=[], total_outstanding=Decimal("0"))

    paid_by_participant: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for chunk in _chunks([p["id"] for p in participants]):
        res = (
            supabase.table("payments")
            .select("participant_id, amount, gateway_status")
            .in_("participant_id", chunk)
            .execute()
        )
        for payment in res.data or []:
            if is_settled(payment):  # pending / failed gateway attempts are not money received
                paid_by_participant[payment["participant_id"]] += to_money(payment["amount"])

    groups: dict[str, dict] = {}
    for p in participants:
        key = p["phone"] if p["phone"] else f"name:{p['name']}"
        group = groups.setdefault(
            key,
            {
                "name": p["name"],
                "total_owed": Decimal("0"),
                "total_paid": Decimal("0"),
                "bills_seen": set(),
            },
        )
        group["name"] = p["name"]
        if p["amount_owed"] is not None:
            group["total_owed"] += to_money(p["amount_owed"])
        group["total_paid"] += paid_by_participant.get(p["id"], Decimal("0"))
        group["bills_seen"].add(p["bill_id"])

    contacts = []
    total_outstanding = Decimal("0")
    for key, group in groups.items():
        balance = group["total_owed"] - group["total_paid"]
        if balance > 0:
            contacts.append(
                ContactBalance(
                    phone=None if key.startswith("name:") else key,
                    name=group["name"],
                    total_owed=group["total_owed"],
                    total_paid=group["total_paid"],
                    balance=balance,
                    bill_count=len(group["bills_seen"]),
                )
            )
            total_outstanding += balance

    contacts.sort(key=lambda c: c.balance, reverse=True)
    return BalancesResponse(contacts=contacts, total_outstanding=total_outstanding)


@router.get("")
async def list_bills(
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    result = (
        supabase.table("bills")
        .select("*")
        .eq("organiser_id", str(user.id))
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.get("/{bill_id}")
async def get_bill(
    bill_id: UUID,
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Organiser's full view of their own bill (includes participant phone numbers).
    Members use the sanitised GET /api/public/bills/{id} instead."""
    bill = require_bill_owner(supabase, bill_id, user)
    return build_bill_view(supabase, bill)


@router.post("/{bill_id}/payment-qr")
async def upload_payment_qr(
    bill_id: UUID,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Upload the organiser's DuitNow QR image, shown to members on the share page."""
    bill = require_bill_owner(supabase, bill_id, user)
    data, mime, ext = await read_image(file, QR_MAX_BYTES)

    path = f"{bill_id}.{ext}"
    bucket = supabase.storage.from_(QR_BUCKET)
    stale = [f"{bill_id}.{e}" for e in IMAGE_EXTENSIONS if e != ext]
    try:
        bucket.remove(stale)  # best effort: drop a previous QR stored under another extension
    except Exception:  # noqa: BLE001
        logger.debug(f"no stale QR to remove for bill {bill_id}")
    try:
        bucket.upload(path, data, {"content-type": mime, "upsert": "true"})
    except Exception as exc:  # noqa: BLE001
        logger.error(f"QR upload failed for bill {bill_id}: {exc}")
        raise HTTPException(status_code=502, detail="Could not store the QR image") from exc
    # Same object key on replace, so version the URL to defeat caches.
    qr_url = f"{bucket.get_public_url(path).split('?')[0]}?v={int(time.time())}"

    details = dict(bill.get("payment_details") or {})
    details["duitnow_qr_url"] = qr_url
    supabase.table("bills").update({"payment_details": details}).eq("id", str(bill_id)).execute()
    return {"duitnow_qr_url": qr_url}


@router.post("/{bill_id}/receipt")
async def upload_receipt(
    bill_id: UUID,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    require_bill_owner(supabase, bill_id, user)
    data, mime, ext = await read_image(file, RECEIPT_MAX_BYTES)

    path = f"{bill_id}.{ext}"
    bucket = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET)
    try:
        bucket.upload(path, data, {"content-type": mime, "upsert": "true"})
    except Exception as exc:  # noqa: BLE001
        logger.error(f"receipt upload failed for bill {bill_id}: {exc}")
        raise HTTPException(status_code=502, detail="Could not store the receipt") from exc
    receipt_url = f"{bucket.get_public_url(path).split('?')[0]}?v={int(time.time())}"

    supabase.table("bills").update({"receipt_url": receipt_url}).eq("id", str(bill_id)).execute()
    return {"receipt_url": receipt_url}

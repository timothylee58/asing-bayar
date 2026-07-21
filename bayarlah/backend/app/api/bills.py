from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from supabase import Client
from uuid import UUID
from decimal import Decimal
from collections import defaultdict

from app.core.dependencies import get_supabase, get_current_user
from app.models.bill import BillCreate, BillResponse

router = APIRouter()


@router.post("", response_model=BillResponse)
async def create_bill(
    payload: BillCreate,
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    n = len(payload.participants)

    if payload.split_mode == "custom":
        for p in payload.participants:
            if p.amount_owed is None:
                raise HTTPException(
                    status_code=422,
                    detail="All participants must have amount_owed for custom split",
                )
        custom_sum = sum(p.amount_owed for p in payload.participants)
        if abs(custom_sum - payload.total_amount) > Decimal("0.02"):
            raise HTTPException(
                status_code=422,
                detail="Sum of participant amounts must equal total_amount",
            )
        per_person = None
        participant_amounts = [p.amount_owed for p in payload.participants]
    else:
        per_person = round(payload.total_amount / n, 2) if n > 0 else payload.total_amount
        participant_amounts = [per_person] * n

    bill_data = {
        "organiser_id": str(user.id),
        "title": payload.title,
        "description": payload.description,
        "total_amount": float(payload.total_amount),
        "per_person": float(per_person) if per_person is not None else None,
        "due_date": payload.due_date.isoformat() if payload.due_date else None,
        "emoji_tag": payload.emoji_tag,
        "game_mode": payload.game_mode,
    }

    result = supabase.table("bills").insert(bill_data).execute()
    bill = result.data[0]

    participants = [
        {
            "bill_id": bill["id"],
            "name": p.name,
            "phone": p.phone,
            "amount_owed": float(participant_amounts[i]),
            "is_organiser": False,
        }
        for i, p in enumerate(payload.participants)
    ]
    supabase.table("participants").insert(participants).execute()

    return {**bill, "share_url": f"/pay/{bill['id']}"}


@router.get("/organiser/balances", response_model=BalancesResponse)
async def get_balances(
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    bills_result = supabase.table("bills").select("id").eq("organiser_id", str(user.id)).execute()
    bill_ids = [b["id"] for b in (bills_result.data or [])]

    if not bill_ids:
        return BalancesResponse(contacts=[], total_outstanding=Decimal("0"))

    participants_result = (
        supabase.table("participants")
        .select("id, name, phone, amount_owed, bill_id")
        .in_("bill_id", bill_ids)
        .execute()
    )
    all_participants = participants_result.data or []

    participant_ids = [p["id"] for p in all_participants]
    if not participant_ids:
        return BalancesResponse(contacts=[], total_outstanding=Decimal("0"))

    payments_result = (
        supabase.table("payments")
        .select("participant_id, amount")
        .in_("participant_id", participant_ids)
        .execute()
    )

    paid_by_participant: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for payment in (payments_result.data or []):
        paid_by_participant[payment["participant_id"]] += Decimal(str(payment["amount"]))

    groups: dict[str, dict] = {}
    for p in all_participants:
        key = p["phone"] if p["phone"] else f"name:{p['name']}"
        if key not in groups:
            groups[key] = {
                "name": p["name"],
                "total_owed": Decimal("0"),
                "total_paid": Decimal("0"),
                "bills_seen": set(),
            }
        groups[key]["name"] = p["name"]
        if p["amount_owed"] is not None:
            groups[key]["total_owed"] += Decimal(str(p["amount_owed"]))
        groups[key]["total_paid"] += paid_by_participant.get(p["id"], Decimal("0"))
        groups[key]["bills_seen"].add(p["bill_id"])

    contacts = []
    total_outstanding = Decimal("0")
    for key, group in groups.items():
        balance = group["total_owed"] - group["total_paid"]
        if balance > 0:
            phone = None if key.startswith("name:") else key
            contacts.append(
                ContactBalance(
                    phone=phone,
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


@router.get("/{bill_id}")
async def get_bill(bill_id: UUID, supabase: Client = Depends(get_supabase)):
    result = supabase.table("bills").select("*, participants(*)").eq("id", str(bill_id)).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Bill not found")
    bill = result.data
    return {**bill, "share_url": f"/pay/{bill['id']}"}


@router.post("/{bill_id}/receipt")
async def upload_receipt(
    bill_id: UUID,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    result = supabase.table("bills").select("organiser_id").eq("id", str(bill_id)).single().execute()
    bill = result.data
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if str(bill["organiser_id"]) != str(user.id):
        raise HTTPException(status_code=403, detail="Only the organiser can upload receipts")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="File must be an image")

    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="File must be under 5MB")

    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg"
    path = f"{bill_id}.{ext}"

    bucket = supabase.storage.from_(settings.SUPABASE_STORAGE_BUCKET)
    bucket.upload(path, data, {"content-type": file.content_type})
    receipt_url = bucket.get_public_url(path)

    supabase.table("bills").update({"receipt_url": receipt_url}).eq("id", str(bill_id)).execute()

    return {"receipt_url": receipt_url}


@router.get("")
async def list_bills(
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    result = supabase.table("bills").select("*").eq("organiser_id", str(user.id)).order("created_at", desc=True).execute()
    return result.data

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from uuid import UUID

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
    per_person = round(payload.total_amount / n, 2) if n > 0 else payload.total_amount

    bill_data = {
        "organiser_id": str(user.id),
        "title": payload.title,
        "description": payload.description,
        "total_amount": float(payload.total_amount),
        "per_person": float(per_person),
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
            "amount_owed": float(per_person),
            "is_organiser": False,
        }
        for p in payload.participants
    ]
    supabase.table("participants").insert(participants).execute()

    return {**bill, "share_url": f"/pay/{bill['id']}"}


@router.get("/{bill_id}")
async def get_bill(bill_id: UUID, supabase: Client = Depends(get_supabase)):
    result = supabase.table("bills").select("*, participants(*)").eq("id", str(bill_id)).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Bill not found")
    bill = result.data
    return {**bill, "share_url": f"/pay/{bill['id']}"}


@router.get("")
async def list_bills(
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    result = supabase.table("bills").select("*").eq("organiser_id", str(user.id)).order("created_at", desc=True).execute()
    return result.data

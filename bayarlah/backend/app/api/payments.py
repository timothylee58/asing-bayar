from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
import redis.asyncio as aioredis
import urllib.parse
import asyncio

from app.core.dependencies import get_supabase, get_redis
from app.core.ws_manager import manager
from app.models.payment import PaymentConfirm, PaymentResponse
from app.services.push_service import send_expo_push, get_participant_tokens

router = APIRouter()

NUDGE_TTL = 86400  # 24h


@router.post("/confirm", response_model=PaymentResponse)
async def confirm_payment(
    payload: PaymentConfirm,
    supabase: Client = Depends(get_supabase),
):
    existing = (
        supabase.table("payments")
        .select("id")
        .eq("participant_id", str(payload.participant_id))
        .eq("bill_id", str(payload.bill_id))
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="Payment already confirmed")

    result = supabase.table("payments").insert({
        "participant_id": str(payload.participant_id),
        "bill_id": str(payload.bill_id),
        "amount": float(payload.amount),
        "method": payload.method,
    }).execute()

    payment = result.data[0]

    # Fetch participant + bill info
    p = supabase.table("participants").select("name, amount_owed, bill_id").eq("id", str(payload.participant_id)).single().execute()
    name = p.data["name"] if p.data else "Someone"

    # Fetch bill for title + check if all paid
    bill = supabase.table("bills").select("title, organiser_id").eq("id", str(payload.bill_id)).single().execute()
    bill_title = bill.data["title"] if bill.data else "Bill"
    organiser_id = bill.data["organiser_id"] if bill.data else None

    # WebSocket broadcast
    await manager.broadcast(str(payload.bill_id), {
        "type": "payment_confirmed",
        "payment": payment,
        "participant_name": name,
    })

    # Push notification to organiser (fire-and-forget)
    if organiser_id:
        asyncio.create_task(_notify_organiser(
            supabase, organiser_id, name, bill_title, str(payload.bill_id)
        ))

    return payment


async def _notify_organiser(supabase, organiser_id: str, payer_name: str, bill_title: str, bill_id: str) -> None:
    """Fire push notification to the bill organiser when a member pays."""
    try:
        # Get organiser's push tokens (stored in push_tokens keyed by user_id for organisers)
        result = supabase.table("push_tokens").select("token").eq("user_id", organiser_id).execute()
        tokens = [r["token"] for r in (result.data or [])]
        await send_expo_push(
            tokens=tokens,
            title=f"💸 {payer_name} bayar dah!",
            body=f"{bill_title} — payment confirmed",
            data={"billId": bill_id, "type": "payment_confirmed"},
        )
    except Exception:
        pass  # Push is non-critical


@router.get("/bill/{bill_id}")
async def get_bill_payments(bill_id: str, supabase: Client = Depends(get_supabase)):
    result = supabase.table("payments").select("*, participants(name)").eq("bill_id", bill_id).execute()
    return result.data


@router.post("/nudge/{participant_id}")
async def nudge_participant(
    participant_id: str,
    redis: aioredis.Redis = Depends(get_redis),
    supabase: Client = Depends(get_supabase),
):
    key = f"nudge_cooldown:{participant_id}"
    if await redis.exists(key):
        raise HTTPException(status_code=429, detail="Nudge cooldown active (24h)")

    p = supabase.table("participants").select("name, phone, bill_id").eq("id", participant_id).single().execute()
    if not p.data:
        raise HTTPException(status_code=404, detail="Participant not found")

    await redis.set(key, "1", ex=NUDGE_TTL)

    name = p.data["name"]
    phone = p.data.get("phone", "")
    bill_id = p.data.get("bill_id", "")

    wa_msg = urllib.parse.quote(f"Eh {name}, bayar lah! 💸\nhttps://bayar.lah/pay/{bill_id}")
    wa_link = f"https://wa.me/{phone}?text={wa_msg}" if phone else None

    # Also push-notify the participant if they have a token
    push_tokens = await get_participant_tokens(supabase, [participant_id])
    if push_tokens:
        asyncio.create_task(send_expo_push(
            tokens=push_tokens,
            title="Eh, bayar lah! 💸",
            body=f"Your organiser is waiting for your payment.",
            data={"billId": bill_id, "type": "nudge"},
        ))

    return {"nudged": True, "whatsapp_link": wa_link, "name": name}

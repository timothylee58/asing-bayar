import asyncio
import json
import urllib.parse
from typing import Any
from uuid import UUID

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from supabase import Client

from app.core.access import (
    ACTIVE_GATEWAY_STATUSES,
    amount_owed,
    fetch_participant,
    first,
    is_settled,
    is_unique_violation,
    require_bill,
    require_bill_owner,
)
from app.core.config import settings
from app.core.dependencies import get_current_user, get_redis, get_supabase, rate_limit
from app.core.ws_manager import manager
from app.models.payment import (
    PaymentConfirm,
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentResponse,
)
from app.services.money import to_money
from app.services.payment_gateway import get_gateway
from app.services.push_service import send_expo_push

router = APIRouter()

NUDGE_TTL = 86400  # 24h

# Hold references so fire-and-forget tasks are not garbage-collected mid-flight.
_background: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


def _active_payment(supabase: Client, bill_id: str, participant_id: str) -> dict | None:
    """The participant's live payment: honour-confirmed, in-flight or verified.
    Failed / expired / superseded attempts do not block a retry."""
    res = (
        supabase.table("payments")
        .select("*")
        .eq("participant_id", str(participant_id))
        .eq("bill_id", str(bill_id))
        .execute()
    )
    for payment in res.data or []:
        if (payment.get("gateway_status") or "manual") in ACTIVE_GATEWAY_STATUSES:
            return payment
    return None


def _check_claimed_amount(claimed, owed) -> None:
    if claimed is not None and to_money(claimed) != owed:
        raise HTTPException(status_code=422, detail=f"Amount must equal amount owed (RM {owed})")


async def _notify_organiser(
    supabase: Client, organiser_id: str, payer_name: str, bill_title: str, bill_id: str
) -> None:
    """Push to the bill organiser when a member pays. Never raises."""
    try:
        result = supabase.table("push_tokens").select("token").eq("user_id", organiser_id).execute()
        tokens = [r["token"] for r in (result.data or [])]
        await send_expo_push(
            tokens=tokens,
            title=f"💸 {payer_name} bayar dah!",
            body=f"{bill_title} — payment confirmed",
            data={"billId": bill_id, "type": "payment_confirmed"},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"organiser push failed for bill {bill_id}: {exc}")


async def _announce_payment(
    supabase: Client, bill: dict, participant_name: str, payment: dict
) -> None:
    bill_id = str(bill["id"])
    await manager.broadcast(
        bill_id,
        {"type": "payment_confirmed", "payment": payment, "participant_name": participant_name},
    )
    if bill.get("organiser_id"):
        _spawn(
            _notify_organiser(
                supabase, str(bill["organiser_id"]), participant_name, bill["title"], bill_id
            )
        )


# ── Level 1: honour-system confirmation (members, no login) ───────────────────


@router.post(
    "/confirm",
    response_model=PaymentResponse,
    dependencies=[Depends(rate_limit("confirm", limit=20, window_seconds=60))],
)
async def confirm_payment(payload: PaymentConfirm, supabase: Client = Depends(get_supabase)):
    # With the gateway on, only cash may be self-declared; everything else must
    # be verified by the gateway or anyone could mark a bank transfer as "paid".
    if settings.PAYMENT_GATEWAY_ENABLED and payload.method != "cash":
        raise HTTPException(
            status_code=400,
            detail="Online payments are verified by the payment gateway; only cash can be self-confirmed.",
        )

    bill = require_bill(supabase, payload.bill_id)
    participant = fetch_participant(supabase, payload.bill_id, payload.participant_id)
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found on this bill")

    owed = amount_owed(participant, bill)
    _check_claimed_amount(payload.amount, owed)

    if _active_payment(supabase, payload.bill_id, payload.participant_id):
        raise HTTPException(status_code=409, detail="Payment already confirmed")

    try:
        result = (
            supabase.table("payments")
            .insert(
                {
                    "participant_id": str(payload.participant_id),
                    "bill_id": str(payload.bill_id),
                    "amount": float(owed),
                    "method": payload.method,
                    "status": "confirmed",
                    "gateway_status": "manual",
                }
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        if is_unique_violation(exc):  # lost a race with a concurrent confirm
            raise HTTPException(status_code=409, detail="Payment already confirmed") from exc
        raise

    payment = result.data[0]
    await _announce_payment(supabase, bill, participant["name"], payment)
    return payment


# ── Organiser-only ────────────────────────────────────────────────────────────


@router.get("/bill/{bill_id}")
async def get_bill_payments(
    bill_id: UUID,
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    require_bill_owner(supabase, bill_id, user)
    payments = supabase.table("payments").select("*").eq("bill_id", str(bill_id)).execute().data or []
    participants = supabase.table("participants").select("id, name").eq("bill_id", str(bill_id)).execute().data or []
    names = {p["id"]: p["name"] for p in participants}
    return [{**p, "participants": {"name": names.get(p["participant_id"])}} for p in payments]


@router.post("/nudge/{participant_id}")
async def nudge_participant(
    participant_id: UUID,
    user=Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
    supabase: Client = Depends(get_supabase),
):
    res = supabase.table("participants").select("*").eq("id", str(participant_id)).limit(1).execute()
    participant = first(res)
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    bill = require_bill_owner(supabase, participant["bill_id"], user)

    active = _active_payment(supabase, bill["id"], participant["id"])
    if active and is_settled(active):
        raise HTTPException(status_code=409, detail="Participant has already paid")

    # SET NX makes check-and-claim atomic, so concurrent taps can't both nudge.
    claimed = await redis.set(f"nudge_cooldown:{participant_id}", "1", ex=NUDGE_TTL, nx=True)
    if not claimed:
        raise HTTPException(status_code=429, detail="Nudge cooldown active (24h)")

    name = participant["name"]
    phone = participant.get("phone")
    pay_url = f"{settings.WEB_BASE_URL.rstrip('/')}/pay/{bill['id']}"
    message = urllib.parse.quote(f"Eh {name}, bayar lah! 💸\n{pay_url}")
    wa_link = f"https://wa.me/{phone}?text={message}" if phone else None
    return {"nudged": True, "whatsapp_link": wa_link, "name": name}


# ── Level 2: gateway-verified payments ────────────────────────────────────────


def _require_gateway_available() -> None:
    if settings.is_production and not settings.PAYMENT_GATEWAY_ENABLED:
        raise HTTPException(status_code=503, detail="Online payments are not enabled")


@router.post(
    "/initiate",
    response_model=PaymentInitiateResponse,
    dependencies=[Depends(rate_limit("initiate", limit=10, window_seconds=60))],
)
async def initiate_payment(payload: PaymentInitiateRequest, supabase: Client = Depends(get_supabase)):
    """Start a gateway-verified payment (Level 2) for what the participant owes."""
    _require_gateway_available()

    bill = require_bill(supabase, payload.bill_id)
    participant = fetch_participant(supabase, payload.bill_id, payload.participant_id)
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found on this bill")
    owed = amount_owed(participant, bill)
    _check_claimed_amount(payload.amount, owed)

    existing = _active_payment(supabase, payload.bill_id, payload.participant_id)
    if existing:
        if existing.get("gateway_status") != "pending":
            raise HTTPException(status_code=409, detail="Payment already confirmed")
        # An abandoned attempt must not lock the participant out: retire it.
        supabase.table("payments").update({"gateway_status": "expired", "status": "expired"}).eq(
            "id", existing["id"]
        ).execute()

    gateway = get_gateway()
    reference = f"{payload.bill_id}:{payload.participant_id}"
    try:
        result = await gateway.create_payment(
            amount=owed,
            currency="MYR",
            method=payload.method,
            reference=reference,
            redirect_url=f"{settings.WEB_BASE_URL.rstrip('/')}/pay/{payload.bill_id}?status=success",
            webhook_url=f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}/api/payments/webhook/gateway",
            description=f"Bayar.lah payment for {bill['title']}"[:100],
        )
    except (httpx.HTTPError, ValueError) as exc:
        logger.error(f"gateway create_payment failed: {exc}")
        raise HTTPException(status_code=502, detail="Payment provider unavailable") from exc

    try:
        supabase.table("payments").insert(
            {
                "participant_id": str(payload.participant_id),
                "bill_id": str(payload.bill_id),
                "amount": float(owed),
                "method": payload.method,
                "gateway_ref": result.gateway_ref,
                "gateway_status": "pending",
                "status": "pending",
            }
        ).execute()
    except Exception as exc:  # noqa: BLE001
        if is_unique_violation(exc):
            raise HTTPException(status_code=409, detail="Payment already in progress") from exc
        raise

    return PaymentInitiateResponse(
        gateway_ref=result.gateway_ref,
        payment_url=result.payment_url,
        qr_url=result.qr_url,
        status=result.status,
    )


def _parse_webhook_body(raw: bytes) -> dict[str, Any]:
    """Gateways send JSON or form-encoded bodies; accept either."""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except ValueError:
        pass
    try:
        pairs = urllib.parse.parse_qsl(raw.decode(), keep_blank_values=True)
    except UnicodeDecodeError:
        pairs = []
    if not pairs:
        raise HTTPException(status_code=400, detail="Unparseable webhook body")
    return dict(pairs)


@router.post("/webhook/gateway")
async def gateway_webhook(request: Request, supabase: Client = Depends(get_supabase)):
    """Gateway callback. Fails closed: with no real gateway configured in
    production the route does not exist, and every request must carry a valid
    signature. A webhook can only settle a payment *we* initiated (matched by
    gateway_ref), and only for the amount we asked for."""
    if settings.is_production and not settings.PAYMENT_GATEWAY_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")

    gateway = get_gateway()
    raw = await request.body()
    fields = _parse_webhook_body(raw)

    if not gateway.verify_webhook(raw_body=raw, headers=request.headers, fields=fields):
        logger.warning("rejected gateway webhook with invalid signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    parsed = gateway.parse_webhook(fields)
    gateway_ref = parsed.get("gateway_ref") or ""
    status = parsed.get("status", "unknown")

    payment = first(
        supabase.table("payments").select("*").eq("gateway_ref", gateway_ref).limit(1).execute()
    ) if gateway_ref else None
    if not payment:
        return {"status": "ignored"}  # 200 so the gateway doesn't retry forever

    if parsed.get("reference") != f"{payment['bill_id']}:{payment['participant_id']}":
        logger.warning(f"webhook reference mismatch for gateway_ref {gateway_ref}")
        return {"status": "ignored"}

    if status == "verified":
        if to_money(parsed.get("amount", 0)) != to_money(payment["amount"]):
            logger.error(f"webhook amount mismatch for gateway_ref {gateway_ref}; left pending")
            return {"status": "amount_mismatch"}
        # Conditional on 'pending' => idempotent under webhook retries.
        updated = (
            supabase.table("payments")
            .update({"gateway_status": "verified", "status": "confirmed"})
            .eq("id", payment["id"])
            .eq("gateway_status", "pending")
            .execute()
        )
        if updated.data:
            bill = require_bill(supabase, payment["bill_id"])
            participant = fetch_participant(supabase, payment["bill_id"], payment["participant_id"])
            await _announce_payment(
                supabase, bill, participant["name"] if participant else "Someone", updated.data[0]
            )
    elif status in ("failed", "expired"):
        supabase.table("payments").update({"gateway_status": status, "status": status}).eq(
            "id", payment["id"]
        ).eq("gateway_status", "pending").execute()

    return {"status": "ok"}

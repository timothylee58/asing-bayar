from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from app.core.dependencies import get_supabase
from app.models.notification import PushTokenRegister

router = APIRouter()


@router.post("/register")
async def register_push_token(
    payload: PushTokenRegister,
    supabase: Client = Depends(get_supabase),
):
    if not payload.token.startswith("ExponentPushToken["):
        raise HTTPException(status_code=400, detail="Invalid Expo push token format")

    # Upsert — same participant re-registers on reinstall
    supabase.table("push_tokens").upsert(
        {"participant_id": payload.participant_id, "token": payload.token},
        on_conflict="participant_id",
    ).execute()

    return {"registered": True}


@router.delete("/unregister/{participant_id}")
async def unregister_push_token(
    participant_id: str,
    supabase: Client = Depends(get_supabase),
):
    supabase.table("push_tokens").delete().eq("participant_id", participant_id).execute()
    return {"unregistered": True}

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.core.dependencies import get_current_user, get_supabase
from app.models.notification import PushTokenRegister

router = APIRouter()


@router.post("/register")
async def register_push_token(
    payload: PushTokenRegister,
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Register the signed-in organiser's device for 'X paid' notifications.

    Identity comes from the auth token; a caller can only ever set their own token.
    """
    if not payload.token.startswith("ExponentPushToken["):
        raise HTTPException(status_code=400, detail="Invalid Expo push token format")

    # A device handed to another account must stop receiving the previous user's pushes.
    supabase.table("push_tokens").delete().eq("token", payload.token).neq(
        "user_id", str(user.id)
    ).execute()
    supabase.table("push_tokens").upsert(
        {"user_id": str(user.id), "token": payload.token}, on_conflict="user_id"
    ).execute()
    return {"registered": True}


@router.delete("/unregister")
async def unregister_push_token(
    user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    supabase.table("push_tokens").delete().eq("user_id", str(user.id)).execute()
    return {"unregistered": True}

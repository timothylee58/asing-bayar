import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from loguru import logger
from supabase import Client

from app.core.access import require_bill_owner
from app.core.dependencies import get_supabase, verify_token
from app.core.ws_manager import manager
from app.services.bill_view import build_bill_view

router = APIRouter()

AUTH_TIMEOUT_SECONDS = 5
PING_INTERVAL_SECONDS = 30
CLOSE_UNAUTHORISED = 4401


@router.websocket("/ws/dashboard/{bill_id}")
async def dashboard_ws(websocket: WebSocket, bill_id: UUID, supabase: Client = Depends(get_supabase)):
    """Live feed for the bill's organiser.

    The first client message must be {"type": "auth", "token": "<supabase jwt>"}
    (sent as a message, not a query string, so the token never lands in access
    logs). Only the bill's owner is let in.
    """
    await websocket.accept()
    try:
        hello = await asyncio.wait_for(websocket.receive_json(), AUTH_TIMEOUT_SECONDS)
        token = hello.get("token") if isinstance(hello, dict) and hello.get("type") == "auth" else None
        if not token:
            raise ValueError("missing auth message")
        user = await run_in_threadpool(verify_token, supabase, token)
        bill = await run_in_threadpool(require_bill_owner, supabase, bill_id, user)
    except Exception:  # noqa: BLE001 - timeout, bad JSON, bad token, not the owner...
        try:
            await websocket.close(code=CLOSE_UNAUTHORISED)
        except Exception:  # noqa: BLE001
            pass
        return

    key = str(bill_id)
    manager.add(key, websocket)
    try:
        view = await run_in_threadpool(build_bill_view, supabase, bill)
        await websocket.send_json({"type": "init", "data": jsonable_encoder(view)})
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), PING_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"dashboard websocket for bill {key} ended: {exc}")
    finally:
        manager.remove(key, websocket)  # always, or dead sockets accumulate

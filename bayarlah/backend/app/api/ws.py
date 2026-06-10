from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from supabase import create_client
from app.core.config import settings
from app.core.ws_manager import manager
import asyncio

router = APIRouter()


@router.websocket("/ws/dashboard/{bill_id}")
async def dashboard_ws(websocket: WebSocket, bill_id: str):
    await websocket.accept()
    manager.add(bill_id, websocket)

    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        result = supabase.table("bills").select("*, participants(*, payments(*))").eq("id", bill_id).single().execute()
        await websocket.send_json({"type": "init", "data": result.data})

        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        manager.remove(bill_id, websocket)

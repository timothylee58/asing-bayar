"""WebSocket connection registry with cross-worker fan-out.

Each uvicorn worker (and each replica) only knows about the sockets connected to
*itself*, but a payment webhook can land on any worker. So `broadcast` publishes
to a Redis channel and every worker's listener delivers to its own local sockets.

If the listener isn't running (tests, or Redis is down) `broadcast` delivers
locally instead, so a single-process deployment keeps working without Redis.
"""
import asyncio
import json

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder
from loguru import logger

CHANNEL_PREFIX = "ws:bill:"


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._task: asyncio.Task | None = None
        self._listening = False
        self._redis = None

    def add(self, bill_id: str, ws: WebSocket) -> None:
        self._connections.setdefault(bill_id, []).append(ws)

    def remove(self, bill_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(bill_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._connections.pop(bill_id, None)

    def count(self, bill_id: str) -> int:
        return len(self._connections.get(bill_id, []))

    async def deliver_local(self, bill_id: str, message: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(bill_id, [])):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.remove(bill_id, ws)

    async def broadcast(self, bill_id: str, message: dict) -> None:
        """Send to every connected organiser socket on every worker."""
        if self._listening and self._redis is not None:
            try:
                await self._redis.publish(CHANNEL_PREFIX + bill_id, json.dumps(jsonable_encoder(message)))
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"redis publish failed, delivering locally only: {exc}")
        await self.deliver_local(bill_id, message)

    # lifecycle ------------------------------------------------------------
    async def start(self, redis) -> None:
        self._redis = redis
        if self._task is None:
            self._task = asyncio.create_task(self._listen(redis))

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None
        self._listening = False

    async def _listen(self, redis) -> None:
        while True:
            pubsub = redis.pubsub()
            try:
                await pubsub.psubscribe(CHANNEL_PREFIX + "*")
                self._listening = True
                async for item in pubsub.listen():
                    if item.get("type") != "pmessage":
                        continue
                    try:
                        bill_id = str(item["channel"])[len(CHANNEL_PREFIX):]
                        await self.deliver_local(bill_id, json.loads(item["data"]))
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(f"bad pubsub message: {exc}")
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"pubsub listener lost, retrying: {exc}")
            finally:
                self._listening = False
                try:
                    await pubsub.aclose()
                except Exception:  # noqa: BLE001
                    pass
            await asyncio.sleep(2)


manager = ConnectionManager()

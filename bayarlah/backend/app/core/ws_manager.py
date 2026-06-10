from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    def add(self, bill_id: str, ws: WebSocket) -> None:
        self._connections.setdefault(bill_id, []).append(ws)

    def remove(self, bill_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(bill_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._connections.pop(bill_id, None)

    async def broadcast(self, bill_id: str, message: dict) -> None:
        conns = self._connections.get(bill_id, [])
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.remove(bill_id, ws)

    def count(self, bill_id: str) -> int:
        return len(self._connections.get(bill_id, []))


manager = ConnectionManager()

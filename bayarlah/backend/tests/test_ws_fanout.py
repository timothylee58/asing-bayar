"""Cross-worker WebSocket fan-out through Redis pub/sub."""
import asyncio
import json

import pytest

from app.core.ws_manager import CHANNEL_PREFIX, ConnectionManager


class FakeSocket:
    def __init__(self):
        self.sent = []

    async def send_json(self, m):
        self.sent.append(m)


class Bus:
    """Tiny pub/sub shared by two 'workers'."""

    def __init__(self):
        self.subs = []

    def client(self):
        return BusClient(self)


class BusClient:
    def __init__(self, bus):
        self.bus = bus

    async def publish(self, channel, data):
        for q in self.bus.subs:
            await q.put({"type": "pmessage", "channel": channel, "data": data})

    def pubsub(self):
        return BusPubSub(self.bus)


class BusPubSub:
    def __init__(self, bus):
        self.bus, self.q = bus, asyncio.Queue()

    async def psubscribe(self, _pattern):
        self.bus.subs.append(self.q)

    async def listen(self):
        while True:
            yield await self.q.get()

    async def aclose(self):
        if self.q in self.bus.subs:
            self.bus.subs.remove(self.q)


async def _until(pred, tries=100):
    for _ in range(tries):
        if pred():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not met")


@pytest.mark.asyncio
async def test_message_published_on_one_worker_reaches_socket_on_another():
    bus = Bus()
    a, b = ConnectionManager(), ConnectionManager()
    await a.start(bus.client())
    await b.start(bus.client())
    await _until(lambda: a._listening and b._listening)
    sock = FakeSocket()
    b.add("bill-1", sock)

    await a.broadcast("bill-1", {"type": "payment_confirmed", "n": 1})
    await _until(lambda: sock.sent)

    assert sock.sent == [{"type": "payment_confirmed", "n": 1}]
    await a.stop()
    await b.stop()


@pytest.mark.asyncio
async def test_delivered_once_even_when_publisher_holds_the_socket():
    bus = Bus()
    m = ConnectionManager()
    await m.start(bus.client())
    await _until(lambda: m._listening)
    sock = FakeSocket()
    m.add("b", sock)
    await m.broadcast("b", {"x": 1})
    await _until(lambda: sock.sent)
    await asyncio.sleep(0.05)
    assert len(sock.sent) == 1
    await m.stop()


@pytest.mark.asyncio
async def test_delivers_locally_when_listener_not_running():
    m = ConnectionManager()
    sock = FakeSocket()
    m.add("b", sock)
    await m.broadcast("b", {"x": 1})
    assert sock.sent == [{"x": 1}]


@pytest.mark.asyncio
async def test_falls_back_to_local_when_publish_fails():
    class Broken(BusClient):
        async def publish(self, *_):
            raise ConnectionError("down")

    bus = Bus()
    m = ConnectionManager()
    await m.start(Broken(bus))
    await _until(lambda: m._listening)
    sock = FakeSocket()
    m.add("b", sock)
    await m.broadcast("b", {"x": 1})
    assert sock.sent == [{"x": 1}]
    await m.stop()


@pytest.mark.asyncio
async def test_channel_is_namespaced_per_bill():
    bus = Bus()
    m = ConnectionManager()
    await m.start(bus.client())
    await _until(lambda: m._listening)
    other = FakeSocket()
    m.add("other-bill", other)
    await m.broadcast("this-bill", {"x": 1})
    await asyncio.sleep(0.05)
    assert other.sent == []
    assert json.dumps({"x": 1})  # payload is JSON-serialisable
    assert CHANNEL_PREFIX == "ws:bill:"
    await m.stop()

"""
ParamX Hunter - WebSocket Live Feed
Streams real-time scan progress, new parameters, and crawl events to the frontend.
"""

import asyncio
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from backend.auth.dependencies import decode_token
from backend.config import settings

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections, grouped by scan_id."""

    def __init__(self):
        # scan_id -> list of websockets
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, scan_id: str, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(scan_id, []).append(ws)

    def disconnect(self, scan_id: str, ws: WebSocket):
        conns = self._connections.get(scan_id, [])
        if ws in conns:
            conns.remove(ws)

    async def broadcast(self, scan_id: str, message: dict):
        payload = json.dumps(message)
        dead = []
        for ws in self._connections.get(scan_id, []):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(scan_id, ws)

    async def broadcast_all(self, message: dict):
        for scan_id in list(self._connections.keys()):
            await self.broadcast(scan_id, message)


manager = ConnectionManager()


@router.websocket("/scan/{scan_id}")
async def scan_live_feed(
    websocket: WebSocket,
    scan_id: str,
    token: str = Query(...),
):
    """
    Live WebSocket feed for a specific scan.
    Requires a valid JWT passed as query param: ?token=<access_token>

    Emits events:
      - scan_progress: { percent, total_requests, total_params, queue_size }
      - new_parameter: { name, type, endpoint, risk_level }
      - new_endpoint:  { url, method, status_code }
      - scan_complete: { summary }
      - error:         { message }
    """
    # Authenticate via token query param
    try:
        decode_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(scan_id, websocket)

    # Subscribe to Redis pub/sub channel for this scan
    redis = aioredis.from_url(settings.REDIS_URL)
    pubsub = redis.pubsub()
    channel = f"paramx:scan:{scan_id}:events"
    await pubsub.subscribe(channel)

    try:
        # Send initial connected ack
        await websocket.send_json({"event": "connected", "scan_id": scan_id})

        async def redis_listener():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await websocket.send_json(data)
                    except Exception:
                        pass

        listener_task = asyncio.create_task(redis_listener())

        # Keep connection alive, handle client pings
        while True:
            try:
                text = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if text == "ping":
                    await websocket.send_json({"event": "pong"})
            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({"event": "keepalive"})
            except WebSocketDisconnect:
                break

    finally:
        listener_task.cancel()
        await pubsub.unsubscribe(channel)
        await redis.close()
        manager.disconnect(scan_id, websocket)


async def publish_scan_event(scan_id: str, event: str, data: dict):
    """
    Called by the scan worker to push events to connected WebSocket clients.
    """
    redis = aioredis.from_url(settings.REDIS_URL)
    payload = json.dumps({"event": event, "scan_id": scan_id, **data})
    await redis.publish(f"paramx:scan:{scan_id}:events", payload)
    await redis.close()

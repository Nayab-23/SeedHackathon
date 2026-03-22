"""WebSocket manager for live query feed.

Maintains a set of connected WebSocket clients and broadcasts events.
"""

import asyncio
import json
from typing import Set
from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        self._clients: Set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the asyncio event loop for cross-thread broadcasting."""
        self._loop = loop

    async def connect(self, websocket: WebSocket):
        """Accept and register a WebSocket client."""
        await websocket.accept()
        self._clients.add(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket client."""
        self._clients.discard(websocket)

    async def broadcast(self, event: dict):
        """Broadcast an event to all connected clients (async)."""
        if not self._clients:
            return
        message = json.dumps(event)
        dead = set()
        for client in self._clients.copy():
            try:
                await client.send_text(message)
            except Exception:
                dead.add(client)
        for client in dead:
            self._clients.discard(client)

    def broadcast_sync(self, event: dict):
        """Broadcast from a non-async context (e.g., QueryLogger thread)."""
        if not self._clients or not self._loop:
            return
        try:
            asyncio.run_coroutine_threadsafe(self.broadcast(event), self._loop)
        except Exception:
            pass

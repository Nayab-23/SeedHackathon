"""FastAPI app factory for the OpenClaw Dashboard."""

import asyncio
import os
import threading
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from dashboard.database import init_db, cleanup_old_queries
from dashboard.websocket import WebSocketManager
from dashboard.routes import lists, profiles, focus, queries, stats, analysis, system


def create_app(config: dict, domain_filter=None) -> FastAPI:
    dashboard_config = config.get("dashboard", {})
    db_path = dashboard_config.get("db_path", "data/dashboard.db")
    lists_config = config.get("lists", {})
    lists_dir = os.path.dirname(lists_config.get("blacklist", "lists/blacklist.txt")) or "lists"

    init_db(db_path)
    cleanup_old_queries(db_path)

    ws_manager = WebSocketManager()

    lists.configure(lists_dir=lists_dir, domain_filter=domain_filter)

    app = FastAPI(title="OpenClaw Dashboard", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(lists.router)
    app.include_router(profiles.router)
    app.include_router(focus.router)
    app.include_router(queries.router)
    app.include_router(stats.router)
    app.include_router(analysis.router)
    app.include_router(system.router)

    @app.websocket("/ws/live")
    async def websocket_live(websocket: WebSocket):
        ws_manager.set_loop(asyncio.get_event_loop())
        await ws_manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
        except Exception:
            ws_manager.disconnect(websocket)

    app.state.ws_manager = ws_manager

    @app.on_event("startup")
    async def startup_cleanup():
        ws_manager.set_loop(asyncio.get_event_loop())

        def periodic_cleanup():
            while True:
                time.sleep(86400)
                try:
                    cleanup_old_queries()
                except Exception as e:
                    print(f"[Dashboard] Cleanup error: {e}")

        threading.Thread(target=periodic_cleanup, daemon=True).start()

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            file_path = os.path.join(static_dir, full_path)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            index_path = os.path.join(static_dir, "index.html")
            if os.path.isfile(index_path):
                return FileResponse(index_path)
            return {"detail": "not found"}

    return app

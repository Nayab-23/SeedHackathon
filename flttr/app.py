from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from flttr.routes import lists, queries, stats, system


def create_app(config: dict, domain_filter=None) -> FastAPI:
    app = FastAPI(title="FLTTR", description="DNS Filtering Dashboard")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    db_path = config.get("flttr", {}).get("db_path", "../flttr/data/flttr.db")
    blacklist_txt = config.get("lists", {}).get("blacklist", "lists/blacklist.txt")

    # Wire db_path and domain_filter into route modules
    lists.db_path = db_path
    lists.domain_filter = domain_filter
    lists.blacklist_txt_path = blacklist_txt
    queries.db_path = db_path
    stats.db_path = db_path
    system.db_path = db_path

    app.include_router(lists.router)
    app.include_router(queries.router)
    app.include_router(stats.router)
    app.include_router(system.router)

    # Serve React static files if they exist
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.exists(static_dir) and os.listdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app

#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "dns-server"))

import yaml
import uvicorn
from dashboard.database import init_db
from dashboard.app import create_app

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "dns-server", "config.yaml")
    with open(config_path) as f:
        return yaml.safe_load(f)

def main():
    config = load_config()
    dashboard_cfg = config.get("dashboard", {})

    # Resolve db_path relative to dns-server/
    db_path = os.path.join("dns-server", dashboard_cfg.get("db_path", "data/dashboard.db"))
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Resolve list paths relative to dns-server/
    config["lists"]["blacklist"] = os.path.join("dns-server", config["lists"]["blacklist"])
    config["lists"]["whitelist"] = os.path.join("dns-server", config["lists"]["whitelist"])
    config["dashboard"]["db_path"] = db_path

    init_db(db_path)

    app = create_app(config)

    host = dashboard_cfg.get("host", "0.0.0.0")
    port = dashboard_cfg.get("port", 8080)

    print(f"  OpenClaw Dashboard → http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()

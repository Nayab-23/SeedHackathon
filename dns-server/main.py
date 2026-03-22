#!/usr/bin/env python3
import yaml
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from server.dns_server import DNSServer


def load_config(config_path="config.yaml"):
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        print(f"[!] Config file not found: {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"[!] Error parsing config file: {e}")
        sys.exit(1)


def main():
    config = load_config()

    # Try to set up FLTTR query logger (optional — works without it)
    query_logger = None
    try:
        from flttr.database import init_db
        from flttr.query_logger import QueryLogger

        db_path = config.get("flttr", {}).get("db_path", "../flttr/data/flttr.db")
        init_db(db_path)
        query_logger = QueryLogger(db_path)
        print("[FLTTR] Database initialized, query logging active")
    except ImportError:
        print("[FLTTR] flttr module not found — running DNS only (no logging)")
    except Exception as e:
        print(f"[FLTTR] Could not init database: {e} — running DNS only")

    # Try to start dashboard (optional)
    try:
        from flttr.app import create_app
        import uvicorn
        import threading

        server_tmp = DNSServer(config, query_logger=query_logger)
        dashboard_app = create_app(config, domain_filter=server_tmp.domain_filter)
        host = config.get("flttr", {}).get("dashboard_host", "0.0.0.0")
        port = config.get("flttr", {}).get("dashboard_port", 8080)

        threading.Thread(
            target=uvicorn.run,
            kwargs={"app": dashboard_app, "host": host, "port": port, "log_level": "warning"},
            daemon=True,
        ).start()
        print(f"[FLTTR] Dashboard at http://{host}:{port}")

        # Use the same server instance
        server = server_tmp
    except ImportError:
        print("[FLTTR] Dashboard dependencies not installed — skipping")
        server = DNSServer(config, query_logger=query_logger)
    except Exception as e:
        print(f"[FLTTR] Dashboard failed to start: {e}")
        server = DNSServer(config, query_logger=query_logger)

    print()
    try:
        server.start()
    except Exception as e:
        print(f"[!] Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import yaml
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from server.dns_server import DNSServer

try:
    from flttr.logger import log
except ImportError:
    log = None


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

    if log:
        log.banner()

    # Try to set up FLTTR query logger (optional — works without it)
    query_logger = None
    try:
        from flttr.database import init_db
        from flttr.query_logger import QueryLogger

        db_path = config.get("flttr", {}).get("db_path", "../flttr/data/flttr.db")
        init_db(db_path)
        query_logger = QueryLogger(db_path)
        if log:
            log.system("Database initialized — query logging active")
    except ImportError:
        if log:
            log.error("flttr module not found — running DNS only (no logging)")
    except Exception as e:
        if log:
            log.error(f"Could not init database: {e} — running DNS only")

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
        if log:
            log.system(f"Dashboard running at http://{host}:{port}")

        server = server_tmp
    except ImportError:
        if log:
            log.error("Dashboard dependencies not installed — skipping")
        server = DNSServer(config, query_logger=query_logger)
    except Exception as e:
        if log:
            log.error(f"Dashboard failed to start: {e}")
        server = DNSServer(config, query_logger=query_logger)

    # Start the Focus Agent (reviews DNS logs for distracting sites)
    try:
        from flttr.focus_agent import FocusAgent

        flttr_cfg = config.get("flttr", {})
        focus_agent = FocusAgent(
            db_path=flttr_cfg.get("db_path", "../flttr/data/flttr.db"),
            ollama_base=config.get("ollama", {}).get("base_url", "http://localhost:11434"),
            api_base=f"http://127.0.0.1:{config.get('flttr', {}).get('dashboard_port', 8080)}",
            model=config.get("ollama", {}).get("model", "nemotron-3-nano:4b"),
            poll_interval=config.get("focus_agent", {}).get("poll_interval", 30),
        )
        focus_agent.start()
    except ImportError:
        if log:
            log.error("Focus agent module not found — skipping")
    except Exception as e:
        if log:
            log.error(f"Focus agent failed to start: {e}")

    if log:
        log.system("Ready — press Ctrl+C to stop\n")

    try:
        server.start()
    except Exception as e:
        if log:
            log.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

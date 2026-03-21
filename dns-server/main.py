#!/usr/bin/env python3
import yaml
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openclaw.observer import OpenClaw
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

    openclaw = OpenClaw(
        enabled=config["openclaw"]["enabled"], log_file=config["openclaw"]["log_file"]
    )

    openclaw.startup_banner()

    server = DNSServer(config, openclaw)

    try:
        server.start()
    except Exception as e:
        print(f"[!] Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

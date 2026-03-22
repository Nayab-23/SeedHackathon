"""QueryLogger: non-blocking bridge from DNS server to SQLite.

Uses a background writer thread with a queue to avoid blocking DNS resolution.
Also pushes events to the WebSocket manager for live feed.
"""

import sqlite3
import threading
import queue
import time
from typing import Optional, Dict


class QueryLogger:
    def __init__(self, db_path: str, ws_manager=None):
        self.db_path = db_path
        self.ws_manager = ws_manager
        self._queue: queue.Queue = queue.Queue()
        self._ip_to_profile: Dict[str, Optional[str]] = {}
        self._ip_to_profile_name: Dict[str, Optional[str]] = {}
        self._last_refresh: float = 0
        self._start_writer()

    def log(self, client_ip: str, domain: str, query_type: str, action: str, response_ms: float):
        """Queue a query for background writing. Non-blocking."""
        self._queue.put((client_ip, domain, query_type, action, response_ms))

    def _load_ip_map(self, conn: sqlite3.Connection):
        """Load device IP -> profile_id mapping from the database."""
        ip_to_profile = {}
        ip_to_name = {}
        try:
            cursor = conn.execute(
                "SELECT d.ip, d.profile_id, p.name "
                "FROM devices d JOIN profiles p ON d.profile_id = p.id"
            )
            for row in cursor:
                ip_to_profile[row[0]] = row[1]
                ip_to_name[row[0]] = row[2]
        except Exception:
            pass
        return ip_to_profile, ip_to_name

    def _start_writer(self):
        """Start the background writer thread."""
        def writer():
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            self._ip_to_profile, self._ip_to_profile_name = self._load_ip_map(conn)
            self._last_refresh = time.time()

            while True:
                try:
                    item = self._queue.get(timeout=5)
                except queue.Empty:
                    continue

                # Refresh IP mapping every 60 seconds
                if time.time() - self._last_refresh > 60:
                    self._ip_to_profile, self._ip_to_profile_name = self._load_ip_map(conn)
                    self._last_refresh = time.time()

                client_ip, domain, query_type, action, response_ms = item
                profile_id = self._ip_to_profile.get(client_ip)
                profile_name = self._ip_to_profile_name.get(client_ip)

                try:
                    conn.execute(
                        "INSERT INTO query_log (client_ip, profile_id, domain, query_type, action, response_ms) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (client_ip, profile_id, domain, query_type, action, response_ms),
                    )
                    conn.commit()
                except Exception as e:
                    print(f"[QueryLogger] DB write error: {e}")

                # Push to WebSocket live feed
                if self.ws_manager:
                    import datetime
                    event = {
                        "type": "query",
                        "data": {
                            "client_ip": client_ip,
                            "profile_name": profile_name,
                            "domain": domain,
                            "query_type": query_type,
                            "action": action,
                            "response_ms": round(response_ms, 1),
                            "logged_at": datetime.datetime.utcnow().isoformat() + "Z",
                        },
                    }
                    try:
                        self.ws_manager.broadcast_sync(event)
                    except Exception:
                        pass

        t = threading.Thread(target=writer, daemon=True)
        t.start()

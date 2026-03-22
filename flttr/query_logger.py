import sqlite3
import threading
import queue


class QueryLogger:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._queue = queue.Queue()
        self._start_writer()

    def log(self, client_ip: str, domain: str, query_type: str, action: str, response_ms: float):
        self._queue.put((client_ip, domain, query_type, action, response_ms))

    def _start_writer(self):
        def writer():
            conn = sqlite3.connect(self.db_path)
            while True:
                item = self._queue.get()
                if item is None:
                    break
                client_ip, domain, query_type, action, response_ms = item
                conn.execute(
                    "INSERT INTO query_log (client_ip, domain, query_type, action, response_ms) VALUES (?,?,?,?,?)",
                    (client_ip, domain, query_type, action, response_ms),
                )
                conn.commit()

        t = threading.Thread(target=writer, daemon=True)
        t.start()

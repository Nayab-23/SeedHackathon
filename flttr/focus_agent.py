"""
FLTTR Focus Agent — monitors DNS query logs and uses Nemotron to evaluate
whether queried domains are productive/focused or distracting.

Runs as a background thread. Each cycle it reads new (unseen) queries from
the database, deduplicates domains, sends them to Nemotron for classification,
and auto-blocks domains the model flags as distracting.

Usage (started automatically from main.py):
    agent = FocusAgent(db_path, ollama_base, api_base, poll_interval=30)
    agent.start()
"""

import sqlite3
import threading
import time
import json
import requests

from flttr.logger import log
from flttr.database import get_connection

FOCUS_SYSTEM_PROMPT = """You are a focus evaluator for a DNS filtering system used for parental controls.

You will receive a list of domains that were recently queried on the network.
Your job is to classify each domain as either "focused" or "distracting".

Guidelines:
- "focused" = educational, productivity tools, work/school related, development tools,
  reference material, news, system/infrastructure domains (CDNs, APIs, OS updates)
- "distracting" = social media, gaming, entertainment streaming, gossip, adult content,
  gambling, clickbait, time-wasting sites

Respond with ONLY a valid JSON object in this exact format, no other text:
{
    "classifications": [
        {"domain": "example.com", "verdict": "focused", "reason": "educational resource"},
        {"domain": "tiktok.com", "verdict": "distracting", "reason": "social media platform"}
    ]
}

Be reasonable — don't flag infrastructure domains (e.g. cdn.*, *.googleapis.com, *.akamai.net).
Only flag domains that a human would clearly consider distracting or inappropriate for a student."""


class FocusAgent:
    def __init__(
        self,
        db_path: str,
        ollama_base: str = "http://localhost:11434",
        api_base: str = "http://localhost:8080",
        model: str = "nemotron-3-nano:4b",
        poll_interval: int = 30,
        batch_size: int = 50,
    ):
        self.db_path = db_path
        self.ollama_base = ollama_base.rstrip("/")
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self._last_id = 0
        self._reviewed_domains: set[str] = set()
        self._stop_event = threading.Event()

    def start(self):
        """Start the focus agent as a daemon thread."""
        self._init_last_id()
        t = threading.Thread(target=self._run_loop, daemon=True, name="focus-agent")
        t.start()
        log.agent("focus-agent started", detail=f"polling every {self.poll_interval}s")

    def stop(self):
        self._stop_event.set()

    def _init_last_id(self):
        """Set the watermark to the current max ID so we only review new queries."""
        try:
            conn = get_connection(self.db_path)
            row = conn.execute("SELECT MAX(id) FROM query_log").fetchone()
            self._last_id = row[0] or 0
            conn.close()
            log.agent("focus-agent", detail=f"starting from query_log id={self._last_id}")
        except Exception as e:
            log.error(f"focus-agent: could not read last id: {e}")
            self._last_id = 0

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self._poll_and_review()
            except Exception as e:
                log.error(f"focus-agent cycle error: {e}")
            self._stop_event.wait(self.poll_interval)

    def _poll_and_review(self):
        """Fetch new allowed queries, deduplicate, and send to Nemotron for review."""
        conn = get_connection(self.db_path)
        rows = conn.execute(
            """SELECT id, domain FROM query_log
               WHERE id > ? AND action = 'ALLOWED'
               ORDER BY id ASC LIMIT ?""",
            (self._last_id, 500),
        ).fetchall()
        conn.close()

        if not rows:
            return

        # Advance watermark
        self._last_id = rows[-1]["id"]

        # Deduplicate: only evaluate domains we haven't reviewed yet
        new_domains = set()
        for row in rows:
            domain = row["domain"].rstrip(".")
            if domain not in self._reviewed_domains:
                new_domains.add(domain)

        if not new_domains:
            return

        log.agent("focus-agent", detail=f"reviewing {len(new_domains)} new domain(s)")

        # Process in batches
        domain_list = sorted(new_domains)
        for i in range(0, len(domain_list), self.batch_size):
            batch = domain_list[i : i + self.batch_size]
            self._evaluate_batch(batch)

    def _evaluate_batch(self, domains: list[str]):
        """Send a batch of domains to Nemotron and block distracting ones."""
        prompt = "Classify these domains:\n" + "\n".join(f"- {d}" for d in domains)

        try:
            response = requests.post(
                f"{self.ollama_base}/api/generate",
                json={
                    "model": self.model,
                    "system": FOCUS_SYSTEM_PROMPT,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=60,
            )
            response.raise_for_status()
            raw = response.json()["response"]
        except requests.RequestException as e:
            log.error(f"focus-agent: Ollama request failed: {e}")
            return

        try:
            parsed = json.loads(raw)
            classifications = parsed.get("classifications", [])
        except (json.JSONDecodeError, KeyError) as e:
            log.error(f"focus-agent: bad response from model: {e}")
            return

        to_block = []
        for entry in classifications:
            domain = entry.get("domain", "")
            verdict = entry.get("verdict", "")
            reason = entry.get("reason", "")

            self._reviewed_domains.add(domain)

            if verdict == "distracting":
                to_block.append((domain, reason))
                log.agent(
                    "focus-agent DISTRACTING",
                    detail=f"{domain} — {reason}",
                )
            else:
                log.agent("focus-agent ok", detail=f"{domain}")

        # Block distracting domains via the REST API
        for domain, reason in to_block:
            self._block_domain(domain, reason)

    def _block_domain(self, domain: str, reason: str):
        """Add a domain to the blacklist via the REST API."""
        try:
            resp = requests.post(
                f"{self.api_base}/api/lists",
                json={
                    "domain": domain,
                    "reason": f"focus-agent: {reason}",
                    "added_by": "focus-agent",
                },
                timeout=10,
            )
            if resp.status_code == 201:
                log.agent("focus-agent BLOCKED", [domain])
            elif resp.status_code == 409:
                pass  # already blocked
            else:
                log.error(f"focus-agent: block {domain} returned {resp.status_code}")
        except requests.RequestException as e:
            log.error(f"focus-agent: failed to block {domain}: {e}")

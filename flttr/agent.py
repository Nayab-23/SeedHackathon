"""
FLTTR Agent — Nemotron via Ollama on Jetson Orin Nano.

The agent interprets natural language commands to modify the DNS blacklist.
It does NOT sit on the hot path (no LLM call per DNS query).
Instead, it's a control plane that modifies the blacklist via the REST API.

Usage:
    agent = FlttrAgent(api_base="http://localhost:8080", ollama_base="http://localhost:11434")
    agent.process_command("block tiktok and instagram")
    agent.process_command("unblock reddit.com")
"""

import requests
import json


SYSTEM_PROMPT = """You are FLTTR, a DNS filtering assistant. You help manage a DNS blacklist.

When the user gives a command, respond with a JSON object describing the actions to take.

Actions you can perform:
- "block": Add domains to the blacklist
- "unblock": Remove domains from the blacklist
- "list": Show current blacklist
- "status": Show system status

Response format (always valid JSON, no other text):
{
    "action": "block" | "unblock" | "list" | "status",
    "domains": ["domain1.com", "domain2.com"],
    "reason": "why this action is being taken"
}

Examples:
User: "block tiktok and instagram"
{"action": "block", "domains": ["tiktok.com", "instagram.com"], "reason": "user requested block"}

User: "unblock reddit"
{"action": "unblock", "domains": ["reddit.com"], "reason": "user requested unblock"}

User: "what's blocked right now?"
{"action": "list", "domains": [], "reason": "user wants to see blacklist"}
"""


class FlttrAgent:
    def __init__(self, api_base: str = "http://localhost:8080", ollama_base: str = "http://localhost:11434", model: str = "nemotron"):
        self.api_base = api_base.rstrip("/")
        self.ollama_base = ollama_base.rstrip("/")
        self.model = model

    def _call_nemotron(self, user_message: str) -> str:
        response = requests.post(
            f"{self.ollama_base}/api/generate",
            json={
                "model": self.model,
                "system": SYSTEM_PROMPT,
                "prompt": user_message,
                "stream": False,
                "format": "json",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["response"]

    def _parse_response(self, raw: str) -> dict:
        return json.loads(raw)

    def _block_domains(self, domains: list, reason: str) -> list:
        results = []
        for domain in domains:
            resp = requests.post(
                f"{self.api_base}/api/lists",
                json={"domain": domain, "reason": reason, "added_by": "agent"},
            )
            results.append({"domain": domain, "status": resp.status_code})
        return results

    def _unblock_domains(self, domains: list) -> list:
        results = []
        for domain in domains:
            resp = requests.delete(f"{self.api_base}/api/lists/{domain}")
            results.append({"domain": domain, "status": resp.status_code})
        return results

    def _get_blacklist(self) -> dict:
        resp = requests.get(f"{self.api_base}/api/lists")
        return resp.json()

    def _get_status(self) -> dict:
        resp = requests.get(f"{self.api_base}/api/system/health")
        return resp.json()

    def process_command(self, command: str) -> dict:
        raw = self._call_nemotron(command)
        parsed = self._parse_response(raw)

        action = parsed.get("action")
        domains = parsed.get("domains", [])
        reason = parsed.get("reason", "agent action")

        if action == "block":
            results = self._block_domains(domains, reason)
            return {"action": "block", "results": results}
        elif action == "unblock":
            results = self._unblock_domains(domains)
            return {"action": "unblock", "results": results}
        elif action == "list":
            return {"action": "list", "data": self._get_blacklist()}
        elif action == "status":
            return {"action": "status", "data": self._get_status()}
        else:
            return {"action": "unknown", "raw": parsed}

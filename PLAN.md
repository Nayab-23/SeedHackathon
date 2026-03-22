# Build Plan: FLTTR — AI-Powered DNS Filtering

## Overview

A Python-based DNS server that filters domains using a global blacklist, powered by an AI agent running **Nemotron via Ollama** on a Jetson Orin Nano. Blacklisted domains are always blocked. The agent can interpret natural language commands (from a robot listener, added later) to modify the blacklist at runtime.

**Core rule:** If a domain is on the blacklist, it's blocked. Everything else is allowed. The only way to unblock is through the agent.

---

## Architecture

```
Client query (UDP:53)
        │
        ▼
┌──────────────────┐
│   DNS Listener    │  ← UDP socket, threaded per-request
│  (dns_server.py)  │     EXISTING CODE — don't touch
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   Blacklist Check │  ← Fast local check, no LLM call
│   (filter.py)     │     Blacklist-only, no whitelist
└────────┬─────────┘
         │
    ┌────┴─────┐
    │          │
    ▼          ▼
┌────────┐  ┌──────────┐
│ Blocker│  │ Resolver  │
│0.0.0.0 │  │ forward   │
│response │  │ to 1.1.1.1│
└────────┘  └──────────┘
    │          │
    └────┬─────┘
         │
         ▼
   Log to SQLite ──→ Dashboard (FastAPI + React)
                           ↑
                     FLTTR Agent (Nemotron via Ollama)
                       │
                       ├── Reads query logs via API
                       ├── Modifies blacklist via API
                       └── Later: listens to robot for commands
```

---

## Project Structure

```
SeedHackathon/
├── dns-server/                  # EXISTING — DNS server (keep as-is)
│   ├── main.py
│   ├── config.yaml
│   ├── requirements.txt
│   ├── server/
│   │   ├── dns_server.py
│   │   ├── resolver.py
│   │   ├── filter.py
│   │   └── blocker.py
│   └── lists/
│       └── blacklist.txt
├── flttr/                       # NEW — Dashboard + Agent
│   ├── app.py                   # FastAPI app factory
│   ├── database.py              # SQLite connection + schema
│   ├── query_logger.py          # DNS → DB bridge (background writer)
│   ├── agent.py                 # FLTTR agent (Nemotron via Ollama)
│   ├── requirements.txt
│   ├── routes/
│   │   ├── lists.py             # Blacklist CRUD
│   │   ├── queries.py           # Query log
│   │   ├── stats.py             # Counters
│   │   └── system.py            # Health check
│   ├── static/                  # React build output
│   └── data/
│       └── flttr.db             # SQLite database
├── frontend/                    # React source
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── pages/
│       │   ├── Overview.jsx
│       │   ├── Lists.jsx
│       │   └── QueryLog.jsx
│       └── components/
│           ├── Layout.jsx
│           ├── Sidebar.jsx
│           ├── StatCard.jsx
│           ├── DomainTable.jsx
│           └── QueryTicker.jsx
├── PLAN.md
└── DASHBOARD.md
```

---

## DNS Server Changes

The existing DNS server works. Minimal changes needed:

1. **Remove whitelist** from `filter.py` — blacklist-only
2. **Remove OpenClaw** imports and observer — replaced by QueryLogger
3. **Add QueryLogger** — writes every query to SQLite (non-blocking, background thread)
4. **Wire QueryLogger** into `dns_server.py` handle flow

---

## FLTTR Agent (agent.py)

The agent uses Nemotron running on the Jetson Orin Nano via Ollama.

**What it does:**
- Sits on the control plane (not the hot path)
- Interprets natural language commands to modify the blacklist
- Calls the same REST API as the dashboard
- Later: receives commands from a robot listener

**How it calls Nemotron:**
```python
import requests

response = requests.post("http://localhost:11434/api/generate", json={
    "model": "nemotron",
    "prompt": "...",
    "stream": False
})
```

**Hot path (per DNS query):** No LLM call. Just a fast set lookup against the blacklist.

**Control plane (on command):** LLM interprets intent → calls API → blacklist updated → filter reloaded.

---

## Implementation Order

| Step | What to build                              | Depends on  |
|------|--------------------------------------------|-------------|
| 1    | SQLite schema + database.py                | Nothing     |
| 2    | QueryLogger (DNS → DB bridge)              | Step 1      |
| 3    | Simplify filter.py (blacklist-only)        | Nothing     |
| 4    | Remove OpenClaw from dns-server            | Nothing     |
| 5    | Wire QueryLogger into dns_server.py        | Steps 2, 4  |
| 6    | Lists API (routes/lists.py)                | Step 1      |
| 7    | Queries API (routes/queries.py)            | Step 1      |
| 8    | Stats API (routes/stats.py)                | Step 1      |
| 9    | System health (routes/system.py)           | Nothing     |
| 10   | FastAPI app (app.py)                       | Steps 6-9   |
| 11   | Agent skeleton (agent.py)                  | Step 6      |
| 12   | Frontend: scaffold + Overview              | Step 8      |
| 13   | Frontend: Lists page                       | Step 6      |
| 14   | Frontend: Query Log page                   | Step 7      |
| 15   | Integration test                           | All above   |

---

## Testing

```bash
# Start DNS on port 5353 for testing
sudo venv/bin/python main.py

# Normal domain → resolves
dig @127.0.0.1 -p 5353 google.com

# Blacklisted domain → 0.0.0.0
dig @127.0.0.1 -p 5353 tiktok.com

# Check dashboard
curl http://localhost:8080/api/stats/overview

# Add domain via API
curl -X POST http://localhost:8080/api/lists/blacklist \
  -H "Content-Type: application/json" \
  -d '{"domain": "instagram.com"}'

# Verify it's now blocked
dig @127.0.0.1 -p 5353 instagram.com
```

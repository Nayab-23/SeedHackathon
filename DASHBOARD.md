# FLTTR Dashboard — MVP Build Plan
## FastAPI + React + Tailwind | SQLite Backend | Agent-Ready API

---

## Assumptions

- **The DNS server is already running** and logging queries via QueryLogger to SQLite.
- **The dashboard runs on the same machine as the DNS server** (Jetson Orin Nano), served on port 8080.
- **One global blacklist.** No per-user profiles, no whitelist, no device tracking.
- **The FLTTR agent (Nemotron via Ollama) uses the same REST API** to read query logs and modify the blacklist.
- **Frontend is React + Tailwind CSS.** Single-page app.
- **This is an MVP for a hackathon demo.**

---

## What the Dashboard Does

Three pages:

1. **Overview** — at-a-glance stats, live query ticker, charts
2. **List Manager** — blacklist CRUD with search
3. **Query Log** — searchable, filterable log of all DNS queries

Plus:
- SQLite database as single source of truth
- REST API consumed by both frontend and FLTTR agent
- WebSocket for live query feed

---

## Architecture

```
Browser
  │
  │  http://<jetson-ip>:8080
  ▼
┌─────────────────────────────────┐
│       React Frontend             │
│       (static files served by    │
│        FastAPI)                   │
│                                  │
│  ┌──────────┐ ┌──────────────┐  │
│  │ Overview  │ │ List Manager │  │
│  └──────────┘ └──────────────┘  │
│  ┌──────────────────────────┐   │
│  │ Query Log                │   │
│  └──────────────────────────┘   │
└──────────────┬──────────────────┘
               │  REST API + WebSocket
               ▼
┌─────────────────────────────────┐
│       FastAPI Backend            │
│       Port 8080                  │
│                                  │
│  /api/lists/*     — BL CRUD     │
│  /api/queries/*   — query log   │
│  /api/stats/*     — counters    │
│  /api/system/*    — health      │
│  /ws/live         — live feed   │
│                                  │
│  Reads/writes: data/flttr.db    │
│  Reads/writes: lists/blacklist  │
│  Calls: domain_filter.reload()  │
└──────────────┬──────────────────┘
               │
     ┌─────────┴──────────┐
     │                    │
     ▼                    ▼
┌──────────┐    ┌──────────────────┐
│  SQLite   │    │  DNS Server       │
│  database │    │  (writes query    │
│           │    │   log to DB)      │
└──────────┘    └──────────────────┘
     │
     ▼
┌──────────────────┐
│  FLTTR Agent      │  ← consumes the same REST API
│  (Nemotron/Ollama)│     reads queries, writes to blacklist
└──────────────────┘
```

---

## Project Structure

```
flttr/
├── app.py                      # FastAPI app factory
├── database.py                 # SQLite connection + migrations
├── query_logger.py             # DNS → DB bridge (background writer)
├── agent.py                    # FLTTR agent (Nemotron via Ollama)
├── requirements.txt
├── routes/
│   ├── __init__.py
│   ├── lists.py                # Blacklist CRUD
│   ├── queries.py              # Query log + history
│   ├── stats.py                # Aggregated counters
│   └── system.py               # Health check
├── static/                     # React build output
│   ├── index.html
│   └── assets/
└── data/
    └── flttr.db                # SQLite database
```

---

## Dependencies

### Backend (flttr/requirements.txt)

```
fastapi>=0.115
uvicorn>=0.32
websockets>=13.0
```

SQLite is built into Python.

### Frontend (frontend/package.json)

```json
{
  "name": "flttr-dashboard",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vite build --outDir ../flttr/static --emptyOutDir",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3",
    "react-dom": "^18.3",
    "react-router-dom": "^6.26",
    "recharts": "^2.12",
    "lucide-react": "^0.400",
    "clsx": "^2.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3",
    "vite": "^5.4",
    "tailwindcss": "^3.4",
    "autoprefixer": "^10.4",
    "postcss": "^8.4"
  }
}
```

---

## SQLite Schema

Single database file: `flttr/data/flttr.db`

```sql
-- Blacklist: source of truth (replaces .txt files)
CREATE TABLE domain_lists (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    domain      TEXT NOT NULL UNIQUE,
    added_by    TEXT DEFAULT 'manual',       -- "manual" | "agent"
    reason      TEXT,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_domain_lists_domain ON domain_lists(domain);

-- Query log: every DNS query
CREATE TABLE query_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_ip   TEXT NOT NULL,
    domain      TEXT NOT NULL,
    query_type  TEXT,                        -- "A", "AAAA", etc.
    action      TEXT NOT NULL,               -- "ALLOWED" | "BLOCKED"
    response_ms REAL,
    logged_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_query_log_time ON query_log(logged_at);
CREATE INDEX idx_query_log_action ON query_log(action);
CREATE INDEX idx_query_log_domain ON query_log(domain);
```

---

## REST API

No auth for the MVP — it's on a local network.

### Lists

```
GET /api/lists
  Query:    ?search=<term>&page=1&per_page=50
  Response: {
    "domains": [
      { "id": 1, "domain": "tiktok.com", "added_by": "manual", "reason": "...", "added_at": "..." }
    ],
    "total": 142,
    "page": 1,
    "pages": 3
  }

POST /api/lists
  Body:     { "domain": "badsite.com", "reason": "optional" }
  Response: 201 { "ok": true, "id": 143 }
  Effects:  inserts into domain_lists, regenerates blacklist.txt, calls filter.reload()

DELETE /api/lists/:domain
  Response: 200 { "ok": true }
  Effects:  deletes from domain_lists, regenerates blacklist.txt, calls filter.reload()

POST /api/lists/bulk
  Body:     { "domains": ["a.com", "b.com"], "reason": "bulk import" }
  Response: 201 { "ok": true, "added": 2, "duplicates": 0 }
```

### Query Log

```
GET /api/queries
  Query:    ?action=BLOCKED&search=youtube&page=1&per_page=100
  Response: {
    "queries": [
      {
        "id": 12345,
        "client_ip": "192.168.1.5",
        "domain": "youtube.com",
        "query_type": "A",
        "action": "BLOCKED",
        "response_ms": 2.3,
        "logged_at": "2026-03-21T18:30:45Z"
      }
    ],
    "total": 8734,
    "page": 1,
    "pages": 88
  }
```

### Stats

```
GET /api/stats/overview
  Response: {
    "today": {
      "total_queries": 4521,
      "blocked": 312,
      "allowed": 4209,
      "block_rate": 6.9
    }
  }

GET /api/stats/hourly
  Query:    ?date=2026-03-21
  Response: {
    "hours": [
      { "hour": 0, "total": 12, "blocked": 1 },
      ...
    ]
  }

GET /api/stats/top_blocked
  Query:    ?limit=10
  Response: {
    "domains": [
      { "domain": "tiktok.com", "count": 234 }
    ]
  }
```

### System Health

```
GET /api/system/health
  Response: {
    "dns_server": "running",
    "database_size_mb": 12.4,
    "query_log_rows": 31247,
    "blacklist_count": 142
  }
```

### WebSocket — Live Query Feed

```
WS /ws/live

Server pushes as queries arrive:
{
  "type": "query",
  "data": {
    "client_ip": "192.168.1.5",
    "domain": "youtube.com",
    "query_type": "A",
    "action": "BLOCKED",
    "response_ms": 2.1,
    "logged_at": "2026-03-21T18:30:45Z"
  }
}
```

---

## Frontend Pages

### Page 1: Overview

```
┌─────────────────────────────────────────────────┐
│  Sidebar │  OVERVIEW                             │
│          │                                       │
│  Overview│  ┌────────┐ ┌────────┐ ┌────────┐   │
│  Lists   │  │Queries │ │Blocked │ │Block % │   │
│  Log     │  │ 4,521  │ │  312   │ │  6.9%  │   │
│          │  └────────┘ └────────┘ └────────┘   │
│          │                                       │
│          │  ┌─────────────────────────────────┐  │
│          │  │  Live Query Feed (WebSocket)     │  │
│          │  │  18:30:45  youtube.com   BLOCKED │  │
│          │  │  18:30:45  google.com    ALLOWED │  │
│          │  └─────────────────────────────────┘  │
│          │                                       │
│          │  ┌───────────────┐ ┌───────────────┐  │
│          │  │Queries/Hour   │ │Top Blocked    │  │
│          │  │(bar chart)    │ │(horiz bars)   │  │
│          │  └───────────────┘ └───────────────┘  │
└─────────────────────────────────────────────────┘
```

### Page 2: List Manager (Blacklist)

```
┌─────────────────────────────────────────────────┐
│  Sidebar │  BLACKLIST                            │
│          │                                       │
│          │  Search...          [+ Add] [Bulk]    │
│          │                                       │
│          │  ┌─────────────────────────────────┐  │
│          │  │ Domain       Added By  Date  [x]│  │
│          │  │ tiktok.com   manual    3/21  [x]│  │
│          │  │ instagram.com agent   3/20  [x] │  │
│          │  │                                 │  │
│          │  │ < 1 2 3 >              50/page  │  │
│          │  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Page 3: Query Log

```
┌─────────────────────────────────────────────────┐
│  Sidebar │  QUERY LOG                            │
│          │                                       │
│          │  Action: [All]  Search: [       ]     │
│          │                                       │
│          │  ┌─────────────────────────────────┐  │
│          │  │Time      Domain     Type Action │  │
│          │  │18:30:45  youtube    A    BLOCK  │  │
│          │  │18:30:45  google     A    ALLOW  │  │
│          │  │                                 │  │
│          │  │ < 1 2 3 ... 88 >     100/page  │  │
│          │  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## How to Connect to main.py

```python
# In dns-server/main.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flttr.app import create_app
from flttr.database import init_db
from flttr.query_logger import QueryLogger
import uvicorn
import threading

# Init DB
init_db(config["dashboard"]["db_path"])

# Query logger for DNS → DB
query_logger = QueryLogger(config["dashboard"]["db_path"])

# Pass to DNS server
server = DNSServer(config, query_logger=query_logger)

# Dashboard in background thread
dashboard_app = create_app(config, domain_filter=server.domain_filter)
threading.Thread(
    target=uvicorn.run,
    kwargs={"app": dashboard_app, "host": "0.0.0.0", "port": 8080, "log_level": "warning"},
    daemon=True,
).start()

print(f"  [FLTTR] Dashboard at http://0.0.0.0:8080")

# DNS server blocks main thread
server.start()
```

---

## Implementation Order

| Step | Task                                          | Depends on |
|------|-----------------------------------------------|------------|
| 1    | SQLite schema + database.py                   | Nothing    |
| 2    | QueryLogger                                   | Step 1     |
| 3    | Wire QueryLogger into dns_server.py           | Step 2     |
| 4    | Lists API (routes/lists.py)                   | Step 1     |
| 5    | Queries API (routes/queries.py)               | Step 1     |
| 6    | Stats API (routes/stats.py)                   | Step 1     |
| 7    | System health (routes/system.py)              | Nothing    |
| 8    | WebSocket (live feed)                         | Step 2     |
| 9    | FastAPI app (app.py)                          | Steps 4-8  |
| 10   | Agent skeleton (agent.py)                     | Step 4     |
| 11   | Frontend: scaffold + Overview                 | Step 6     |
| 12   | Frontend: Lists page                          | Step 4     |
| 13   | Frontend: Query Log                           | Step 5     |
| 14   | Integration test                              | All above  |

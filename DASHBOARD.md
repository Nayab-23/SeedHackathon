# OpenClaw Dashboard — Updated Build Plan
## React + Tailwind | Tailscale Network | SQLite Backend | Agent-Ready API

---

## Assumptions

- **No OpenClaw dependency.** The observation/classification layer will be handled
  by LangChain/LangGraph agents separately. This plan covers only the dashboard
  frontend, the REST API backend, and the SQLite data layer.
- **The DNS server is already running** and logging queries. The dashboard reads
  from the same SQLite database the DNS server writes to.
- **All devices are on the same Tailnet.** Each device has a stable Tailscale IP
  (100.x.x.x range) that doesn't change. Device identification is done by IP.
- **The dashboard runs on the same machine as the DNS server** (Jetson Orin Nano),
  served on port 8080.
- **The parent is the only dashboard user.** Simple token auth, no multi-user system.
- **An AI agent (LangChain/LangGraph) will interact with the backend API** to read
  query logs, read/write lists, read user profiles and focus notes, and make
  decisions. The API must be clean and predictable for agent consumption.
- **Frontend is React + Tailwind CSS.** Single-page app, mobile responsive.

---

## What the Dashboard Does

Four core features:

1. **Overview** — at-a-glance stats, live query ticker, charts
2. **List Manager** — blacklist/whitelist CRUD with search, bulk ops, metadata
3. **Devices & Profiles** — assign Tailscale IPs to people, set focus notes with expiry
4. **Query Log & History** — searchable, filterable log of all DNS queries

Plus:
- SQLite database as the single source of truth (agent-readable)
- REST API that both the frontend and the LangChain agent consume
- WebSocket for live query feed

---

## Architecture

```
Parent's browser (any device on Tailnet)
          │
          │  http://<jetson-tailscale-ip>:8080
          ▼
┌─────────────────────────────────────┐
│         React Frontend               │
│         (static files served by      │
│          FastAPI)                     │
│                                      │
│  ┌───────────┐  ┌────────────────┐  │
│  │ Overview   │  │ List Manager   │  │
│  └───────────┘  └────────────────┘  │
│  ┌───────────┐  ┌────────────────┐  │
│  │ Devices &  │  │ Query Log &    │  │
│  │ Profiles   │  │ History        │  │
│  └───────────┘  └────────────────┘  │
└──────────────┬──────────────────────┘
               │  REST API + WebSocket
               ▼
┌─────────────────────────────────────┐
│         FastAPI Backend              │
│         Port 8080                    │
│                                      │
│  /api/auth/*        — login/check    │
│  /api/lists/*       — BL/WL CRUD     │
│  /api/profiles/*    — people + IPs   │
│  /api/focus/*       — focus notes    │
│  /api/queries/*     — query log      │
│  /api/stats/*       — counters       │
│  /api/system/*      — health         │
│  /ws/live           — live feed      │
│                                      │
│  Reads/writes: data/dashboard.db     │
│  Reads/writes: lists/*.txt           │
│  Calls: domain_filter.reload()       │
└──────────────┬──────────────────────┘
               │
     ┌─────────┴──────────┐
     │                    │
     ▼                    ▼
┌──────────┐    ┌──────────────────┐
│  SQLite   │    │  DNS Server       │
│  database │    │  (reads filter    │
│           │    │   + writes query  │
│           │    │   log to DB)      │
└──────────┘    └──────────────────┘
     │
     ▼
┌──────────────────┐
│  LangChain Agent  │  ← consumes the same REST API
│  (separate)       │     reads queries, profiles, focus notes
│                   │     writes to blacklist/whitelist
└──────────────────┘
```

---

## Project Structure

```
dns-server/
├── main.py                         # Starts DNS server + dashboard
├── config.yaml
├── requirements.txt
├── server/                         # Existing DNS server code
│   ├── dns_server.py
│   ├── resolver.py
│   ├── filter.py
│   └── blocker.py
├── dashboard/
│   ├── app.py                      # FastAPI app factory
│   ├── auth.py                     # Token-based auth middleware
│   ├── database.py                 # SQLite connection + migrations
│   ├── models.py                   # Pydantic request/response models
│   ├── websocket.py                # Live query feed over WebSocket
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── lists.py                # Blacklist/whitelist CRUD
│   │   ├── profiles.py             # People + device IP assignment
│   │   ├── focus.py                # Focus notes with expiry
│   │   ├── queries.py              # Query log + history
│   │   ├── stats.py                # Aggregated counters + charts
│   │   └── system.py               # Health check
│   └── static/                     # React build output
│       ├── index.html
│       └── assets/
├── frontend/                       # React source
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api.js                  # API client helper
│       ├── pages/
│       │   ├── Overview.jsx
│       │   ├── Lists.jsx
│       │   ├── Profiles.jsx
│       │   └── QueryLog.jsx
│       ├── components/
│       │   ├── Layout.jsx          # Shell: sidebar + content area
│       │   ├── Sidebar.jsx
│       │   ├── StatCard.jsx
│       │   ├── DomainTable.jsx     # Reusable sortable/searchable table
│       │   ├── QueryTicker.jsx     # Live scrolling query feed
│       │   ├── FocusTimer.jsx      # Countdown timer
│       │   ├── ActionBadge.jsx     # ALLOWED/BLOCKED/WHITELISTED badge
│       │   ├── AddDomainModal.jsx
│       │   ├── BulkImportModal.jsx
│       │   ├── CreateProfileModal.jsx
│       │   ├── SetFocusModal.jsx
│       │   └── ConfirmDialog.jsx
│       └── hooks/
│           ├── useWebSocket.js
│           └── useApi.js
├── lists/
│   ├── blacklist.txt
│   └── whitelist.txt
├── data/
│   └── dashboard.db                # SQLite database
└── logs/
    └── queries.log                 # Fallback plaintext log
```

---

## Dependencies

### Backend (add to requirements.txt)

```
fastapi>=0.115
uvicorn>=0.32
python-multipart>=0.0.9
websockets>=13.0
```

SQLite is built into Python — no extra dependency.

### Frontend (frontend/package.json)

```json
{
  "name": "openclaw-dashboard",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vite build --outDir ../dashboard/static --emptyOutDir",
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

Build: `cd frontend && npm install && npm run build`
Output lands in `dashboard/static/`, served by FastAPI.

---

## Configuration

```yaml
# Add to config.yaml

dashboard:
  enabled: true
  host: "0.0.0.0"
  port: 8080
  db_path: "data/dashboard.db"

  auth:
    admin_token: "GENERATE_WITH_python3 -c 'import secrets;print(secrets.token_urlsafe(32))'"
    cookie_max_age: 604800    # 7 days
```

---

## SQLite Schema

Single database file: `data/dashboard.db`

```sql
-- ============================================================
-- PROFILES: people on the network
-- ============================================================
CREATE TABLE profiles (
    id          TEXT PRIMARY KEY,                -- uuid4
    name        TEXT NOT NULL,                   -- "Alex", "Emma"
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- DEVICES: Tailscale IPs assigned to a profile
-- Each IP belongs to exactly one person
-- ============================================================
CREATE TABLE devices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id  TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    ip          TEXT NOT NULL UNIQUE,            -- Tailscale IP, e.g. "100.100.14.23"
    label       TEXT,                            -- "Alex's iPad", "Alex's Laptop"
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- FOCUS NOTES: what someone should be doing, with expiry
-- A profile can have multiple focus notes (stacked or sequential)
-- Only notes where NOW() is between starts_at and expires_at are active
-- ============================================================
CREATE TABLE focus_notes (
    id          TEXT PRIMARY KEY,                -- uuid4
    profile_id  TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    note        TEXT NOT NULL,                   -- "studying for history midterm"
    strictness  TEXT DEFAULT 'moderate',         -- "relaxed" | "moderate" | "strict"
    starts_at   TIMESTAMP NOT NULL,             -- when this focus period begins
    expires_at  TIMESTAMP NOT NULL,             -- when it auto-expires
    ended_early BOOLEAN DEFAULT 0,              -- manually ended before expiry
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for quick "active focus" lookups
CREATE INDEX idx_focus_active ON focus_notes(profile_id, expires_at)
    WHERE ended_early = 0;

-- ============================================================
-- DOMAIN LISTS: blacklist and whitelist with metadata
-- This is the source of truth. The .txt files are regenerated from here.
-- ============================================================
CREATE TABLE domain_lists (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    domain      TEXT NOT NULL,
    list_type   TEXT NOT NULL CHECK(list_type IN ('blacklist', 'whitelist')),
    added_by    TEXT DEFAULT 'manual',           -- "manual" | "agent" | "telegram"
    reason      TEXT,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(domain, list_type)
);

CREATE INDEX idx_domain_lists_type ON domain_lists(list_type);
CREATE INDEX idx_domain_lists_domain ON domain_lists(domain);

-- ============================================================
-- QUERY LOG: every DNS query that passes through the server
-- Written by the DNS server, read by the dashboard and agent
-- ============================================================
CREATE TABLE query_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_ip   TEXT NOT NULL,                   -- Tailscale IP of the device
    profile_id  TEXT,                            -- resolved from client_ip → devices → profile
    domain      TEXT NOT NULL,
    query_type  TEXT,                            -- "A", "AAAA", "CNAME", "MX", etc.
    action      TEXT NOT NULL,                   -- "ALLOWED" | "BLOCKED" | "WHITELISTED"
    response_ms REAL,
    logged_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_query_log_time ON query_log(logged_at);
CREATE INDEX idx_query_log_profile ON query_log(profile_id);
CREATE INDEX idx_query_log_action ON query_log(action);
CREATE INDEX idx_query_log_domain ON query_log(domain);

-- ============================================================
-- ANALYSIS LOG: results from the LangChain agent's analysis
-- Written by the agent via API, read by the dashboard
-- ============================================================
CREATE TABLE analysis_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    domain      TEXT NOT NULL,
    profile_id  TEXT,
    risk_level  TEXT,                            -- "safe" | "low" | "medium" | "high" | "critical"
    category    TEXT,
    reasoning   TEXT,
    action_taken TEXT,                           -- "none" | "alerted" | "blocked" | "allowed"
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analysis_log_risk ON analysis_log(risk_level);
CREATE INDEX idx_analysis_log_domain ON analysis_log(domain);
```

### Data Retention

The `query_log` table grows fast (5,000-20,000 rows/day for a household).
A daily cleanup job keeps the last 7 days:

```sql
DELETE FROM query_log WHERE logged_at < datetime('now', '-7 days');
```

The dashboard backend runs this on startup and every 24 hours.

---

## REST API Specification

Every endpoint except `/api/auth/login` requires authentication via
`Authorization: Bearer <token>` header or `openclaw_token` cookie.

The agent uses the same API with the same token.

### Auth

```
POST /api/auth/login
  Body:     { "token": "the_admin_token" }
  Success:  200 { "ok": true }   + Set-Cookie: openclaw_token=<token>
  Failure:  401 { "error": "invalid token" }

GET /api/auth/check
  Success:  200 { "authenticated": true }
  Failure:  401 { "authenticated": false }
```

### Lists

```
GET /api/lists/:type
  :type = "blacklist" | "whitelist"
  Query:    ?search=<term>&page=1&per_page=50&sort=added_at&order=desc
  Response: {
    "domains": [
      {
        "id": 1,
        "domain": "tiktok.com",
        "added_by": "manual",
        "reason": "social media distraction",
        "added_at": "2026-03-21T18:30:00Z"
      }
    ],
    "total": 142,
    "page": 1,
    "pages": 3
  }

POST /api/lists/:type
  Body:     { "domain": "badsite.com", "reason": "optional reason" }
  Response: 201 { "ok": true, "id": 143 }
  Effects:  inserts into domain_lists, regenerates .txt, calls filter.reload()

POST /api/lists/:type/bulk
  Body:     { "domains": ["a.com", "b.com"], "reason": "bulk import" }
  Response: 201 { "ok": true, "added": 2, "duplicates": 0 }

DELETE /api/lists/:type/:domain
  Response: 200 { "ok": true }
  Effects:  deletes from domain_lists, regenerates .txt, calls filter.reload()

POST /api/lists/:type/import
  Multipart: file (text file, one domain per line)
  Response: 201 { "ok": true, "added": 47, "duplicates": 3 }
```

### Profiles

```
GET /api/profiles
  Response: {
    "profiles": [
      {
        "id": "uuid",
        "name": "Alex",
        "devices": [
          { "id": 1, "ip": "100.100.14.23", "label": "Alex's iPad" },
          { "id": 2, "ip": "100.100.14.24", "label": "Alex's Laptop" }
        ],
        "active_focus": {
          "id": "uuid",
          "note": "studying for history midterm",
          "strictness": "moderate",
          "starts_at": "2026-03-21T16:00:00Z",
          "expires_at": "2026-03-21T18:00:00Z",
          "remaining_minutes": 47
        } | null,
        "stats": {
          "queries_today": 342,
          "blocked_today": 28
        }
      }
    ]
  }

POST /api/profiles
  Body:     { "name": "Alex" }
  Response: 201 { "id": "uuid", "name": "Alex", ... }

PUT /api/profiles/:id
  Body:     { "name": "Alexander" }
  Response: 200 updated profile

DELETE /api/profiles/:id
  Response: 200 { "ok": true }
  Effects:  cascades to devices and focus_notes

POST /api/profiles/:id/devices
  Body:     { "ip": "100.100.14.23", "label": "Alex's iPad" }
  Response: 201 { "id": 1, ... }

DELETE /api/profiles/:id/devices/:device_id
  Response: 200 { "ok": true }
```

### Focus Notes

```
GET /api/focus
  Query:    ?profile_id=<uuid>&active_only=true
  Response: {
    "notes": [
      {
        "id": "uuid",
        "profile_id": "uuid",
        "profile_name": "Alex",
        "note": "studying for history midterm",
        "strictness": "moderate",
        "starts_at": "2026-03-21T16:00:00Z",
        "expires_at": "2026-03-21T18:00:00Z",
        "remaining_minutes": 47,
        "active": true
      }
    ]
  }

POST /api/focus
  Body: {
    "profile_id": "uuid",
    "note": "studying for history midterm",
    "strictness": "moderate",
    "duration_minutes": 120
  }
  Response: 201 {
    "id": "uuid",
    "starts_at": "2026-03-21T16:00:00Z",
    "expires_at": "2026-03-21T18:00:00Z",
    ...
  }

  `starts_at` is set to NOW by the server.
  `expires_at` is calculated as NOW + duration_minutes.

PUT /api/focus/:id/extend
  Body:     { "extra_minutes": 30 }
  Response: 200 { updated note with new expires_at }

DELETE /api/focus/:id
  Response: 200 { "ok": true }
  Effects:  sets ended_early = 1 (soft delete, keeps history)

GET /api/focus/history
  Query:    ?profile_id=<uuid>&days=30
  Response: list of past focus notes with durations
```

### Query Log

```
GET /api/queries
  Query:    ?profile_id=<uuid>&action=BLOCKED&search=youtube
            &from=2026-03-21T00:00:00Z&to=2026-03-21T23:59:59Z
            &page=1&per_page=100
  Response: {
    "queries": [
      {
        "id": 12345,
        "client_ip": "100.100.14.23",
        "profile_name": "Alex",
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

GET /api/queries/export
  Query:    same filters as above
  Response: CSV file download
```

### Analysis Log (written by the agent, read by dashboard)

```
GET /api/analysis
  Query:    ?risk_level=high&profile_id=<uuid>&page=1&per_page=50
  Response: {
    "analyses": [
      {
        "id": 1,
        "domain": "sketchy-site.com",
        "profile_name": "Alex",
        "risk_level": "high",
        "category": "gambling",
        "reasoning": "Site contains online slot machines...",
        "action_taken": "blocked",
        "analyzed_at": "2026-03-21T18:30:45Z"
      }
    ],
    "total": 34
  }

POST /api/analysis
  Body: {
    "domain": "sketchy-site.com",
    "profile_id": "uuid",
    "risk_level": "high",
    "category": "gambling",
    "reasoning": "Site contains online slot machines...",
    "action_taken": "blocked"
  }
  Response: 201 { "id": 1 }
  
  This endpoint exists for the LangChain agent to write analysis results.
```

### Stats

```
GET /api/stats/overview
  Response: {
    "today": {
      "total_queries": 4521,
      "blocked": 312,
      "allowed": 4102,
      "whitelisted": 107,
      "block_rate": 6.9
    },
    "per_profile": [
      {
        "profile_id": "uuid",
        "name": "Alex",
        "queries": 1823,
        "blocked": 189,
        "top_domains": ["youtube.com", "google.com", "discord.com"],
        "top_blocked": ["tiktok.com", "instagram.com"]
      }
    ]
  }

GET /api/stats/hourly
  Query:    ?date=2026-03-21
  Response: {
    "hours": [
      { "hour": 0, "total": 12, "blocked": 1 },
      { "hour": 1, "total": 3, "blocked": 0 },
      ...
      { "hour": 23, "total": 89, "blocked": 7 }
    ]
  }

GET /api/stats/top_blocked
  Query:    ?days=7&limit=20
  Response: {
    "domains": [
      { "domain": "tiktok.com", "count": 234 },
      { "domain": "instagram.com", "count": 178 }
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
    "uptime_seconds": 172800,
    "active_profiles": 3,
    "active_focus_sessions": 1,
    "blacklist_count": 142,
    "whitelist_count": 23
  }
```

### WebSocket — Live Query Feed

```
WS /ws/live?token=<admin_token>

Server pushes JSON events as queries arrive:

{
  "type": "query",
  "data": {
    "client_ip": "100.100.14.23",
    "profile_name": "Alex",
    "domain": "youtube.com",
    "query_type": "A",
    "action": "BLOCKED",
    "response_ms": 2.1,
    "logged_at": "2026-03-21T18:30:45Z"
  }
}

{
  "type": "focus_expired",
  "data": {
    "profile_name": "Alex",
    "note": "studying for history midterm"
  }
}
```

The DNS server pushes query events to a `queue.Queue`. The WebSocket
handler reads from this queue and broadcasts to connected clients.

---

## Frontend Pages

### Page 1: Overview

The landing page. Parent opens the dashboard and immediately sees what's happening.

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  Sidebar  │  OVERVIEW                                    │
│           │                                              │
│  Overview │  ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  Lists    │  │ Queries  │ │ Blocked  │ │ Active   │    │
│  Profiles │  │ Today    │ │ Today    │ │ Focus    │    │
│  Log      │  │   4,521  │ │   312    │ │   1      │    │
│           │  └──────────┘ └──────────┘ └──────────┘    │
│           │                                              │
│           │  ┌──────────────────────────────────────┐   │
│           │  │  Live Query Feed                      │   │
│           │  │  ↕ auto-scrolling, color-coded        │   │
│           │  │                                        │   │
│           │  │  18:30:45  Alex  youtube.com   BLOCKED │   │
│           │  │  18:30:45  Alex  google.com   ALLOWED │   │
│           │  │  18:30:46  Emma  wikipedia.org ALLOWED│   │
│           │  │  ...                                   │   │
│           │  └──────────────────────────────────────┘   │
│           │                                              │
│           │  ┌─────────────────┐ ┌──────────────────┐   │
│           │  │ Queries/Hour    │ │ Top Blocked       │   │
│           │  │ (bar chart)     │ │ (horizontal bars) │   │
│           │  └─────────────────┘ └──────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Components:**
- 3 stat cards at the top: total queries, blocked count (with % badge), active focus sessions
- Live query ticker (WebSocket-fed, auto-scrolling, pause button)
  - Each row: timestamp, profile name, domain, action badge (green/red/blue)
  - Click a row → navigates to query log filtered to that domain
- Queries per hour bar chart (recharts)
- Top 10 blocked domains horizontal bar chart

### Page 2: List Manager

Two tabs: Blacklist / Whitelist

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  Sidebar  │  LISTS                                       │
│           │                                              │
│           │  [Blacklist] [Whitelist]          tabs        │
│           │                                              │
│           │  ┌────────────────────────────────────────┐  │
│           │  │ 🔍 Search domains...                   │  │
│           │  │                                        │  │
│           │  │ [+ Add Domain]  [Bulk Import]          │  │
│           │  └────────────────────────────────────────┘  │
│           │                                              │
│           │  ┌────────────────────────────────────────┐  │
│           │  │ Domain         Added By  Reason  Date  │  │
│           │  │─────────────────────────────────────── │  │
│           │  │ tiktok.com     manual    social  3/21  │  │
│           │  │ instagram.com  agent     distrac 3/20  │  │
│           │  │ malware.com    telegram  phishi  3/19  │  │
│           │  │                                    [x] │  │
│           │  │                                        │  │
│           │  │ < 1 2 3 ... 5 >              50/page  │  │
│           │  └────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Features:**
- Search bar: filters table as you type (client-side for current page, server-side for full search)
- Add Domain button → modal: domain input + optional reason text field
- Bulk Import button → modal: textarea to paste domains OR file upload (.txt)
- Table columns: Domain, Added By (badge: manual/agent/telegram), Reason, Date Added
- Each row has a delete button with confirmation dialog
- Sortable columns (click header to sort)
- Pagination: 50 per page

### Page 3: Profiles & Devices

Card layout — one card per person.

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  Sidebar  │  PROFILES                                    │
│           │                                              │
│           │  [+ New Profile]                             │
│           │                                              │
│           │  ┌────────────────────────────────────────┐  │
│           │  │  👤 Alex                                │  │
│           │  │                                        │  │
│           │  │  Devices:                              │  │
│           │  │    100.100.14.23 — Alex's iPad    [x]  │  │
│           │  │    100.100.14.24 — Alex's Laptop  [x]  │  │
│           │  │    [+ Add Device]                      │  │
│           │  │                                        │  │
│           │  │  Focus:                                │  │
│           │  │  ┌──────────────────────────────────┐  │  │
│           │  │  │ 📚 studying for history midterm  │  │  │
│           │  │  │ Moderate · 47 min remaining      │  │  │
│           │  │  │ [Extend ▾] [End Now]             │  │  │
│           │  │  └──────────────────────────────────┘  │  │
│           │  │  [Set Focus]                           │  │
│           │  │                                        │  │
│           │  │  Today: 342 queries · 28 blocked       │  │
│           │  │  [View Query Log →]                    │  │
│           │  └────────────────────────────────────────┘  │
│           │                                              │
│           │  ┌────────────────────────────────────────┐  │
│           │  │  👤 Emma                                │  │
│           │  │  ...                                    │  │
│           │  └────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Features per card:**
- Profile name (editable inline or via edit button)
- Device list: Tailscale IP + label, delete button per device, add device button
  - Add device modal: IP input + label input
- Active focus note (if any):
  - Note text, strictness badge (relaxed/moderate/strict)
  - Live countdown timer (updates every second)
  - Extend dropdown: +15, +30, +60 minutes
  - End Now button (confirm dialog)
- Set Focus button → modal:
  - Note text area ("what should they be doing?")
  - Duration: preset buttons (30m, 1h, 2h, 4h) + custom input
  - Strictness: three radio options with descriptions
    - Relaxed: only block harmful content (adult, malware, phishing)
    - Moderate: also block social media and entertainment
    - Strict: block everything not related to the focus note
  - Start button
- Quick stats: queries today, blocked today
- "View Query Log" link → navigates to log page filtered by this profile

**New Profile modal:**
- Name input
- At least one device IP + label
- Optional: set initial focus note

### Page 4: Query Log & History

Full searchable, filterable DNS query history.

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  Sidebar  │  QUERY LOG                                   │
│           │                                              │
│           │  ┌────────────────────────────────────────┐  │
│           │  │ Profile: [All ▾]  Action: [All ▾]      │  │
│           │  │ Search: [          ]  Date: [Today ▾]  │  │
│           │  │                           [Export CSV]  │  │
│           │  └────────────────────────────────────────┘  │
│           │                                              │
│           │  ┌────────────────────────────────────────┐  │
│           │  │ Time      Who    Domain     Type Action │  │
│           │  │────────────────────────────────────────│  │
│           │  │ 18:30:45  Alex   youtube    A   BLOCK  │  │
│           │  │ 18:30:45  Alex   google     A   ALLOW  │  │
│           │  │ 18:30:46  Emma   wikipedia  A   ALLOW  │  │
│           │  │ 18:30:47  —      unknown    AAAA ALLOW │  │
│           │  │                                        │  │
│           │  │ < 1 2 3 ... 88 >            100/page  │  │
│           │  └────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Filters:**
- Profile dropdown: All / specific person
- Action dropdown: All / Allowed / Blocked / Whitelisted
- Search: domain contains (debounced, triggers API call)
- Date range: Today / Yesterday / Last 7 days / Custom
- Export CSV button: downloads filtered results as .csv

**Table:**
- Columns: Timestamp, Profile Name (or "—" if unrecognized IP), Domain, Query Type, Action (color badge), Response Time
- Sortable by any column
- Pagination: 100 per page
- Unrecognized IPs (not assigned to a profile) show as "—" with the raw IP in a tooltip

---

## How the DNS Server Writes to the Database

The DNS server needs to log queries to SQLite. Modify `dns_server.py` to:

1. Accept a `db_path` parameter
2. After resolving each query, insert a row into `query_log`
3. Look up `client_ip` in the `devices` table to resolve `profile_id`
4. Use a background writer thread with a queue to avoid blocking DNS resolution

```python
# Pseudocode for the DNS → DB bridge
class QueryLogger:
    def __init__(self, db_path):
        self.queue = queue.Queue()
        self.db_path = db_path
        self._start_writer()

    def log(self, client_ip, domain, query_type, action, response_ms):
        self.queue.put((client_ip, domain, query_type, action, response_ms))

    def _start_writer(self):
        def writer():
            conn = sqlite3.connect(self.db_path)
            # Cache device→profile mapping, refresh every 60s
            ip_to_profile = self._load_ip_map(conn)
            last_refresh = time.time()

            while True:
                item = self.queue.get()
                if time.time() - last_refresh > 60:
                    ip_to_profile = self._load_ip_map(conn)
                    last_refresh = time.time()

                client_ip, domain, query_type, action, response_ms = item
                profile_id = ip_to_profile.get(client_ip)
                conn.execute(
                    "INSERT INTO query_log (client_ip, profile_id, domain, query_type, action, response_ms) VALUES (?,?,?,?,?,?)",
                    (client_ip, profile_id, domain, query_type, action, response_ms)
                )
                conn.commit()

        t = threading.Thread(target=writer, daemon=True)
        t.start()
```

This is a non-blocking bridge. The DNS handler calls `logger.log(...)` which
is instant (queue.put), and the background thread handles the DB write.

---

## How the List Manager Syncs with the DNS Filter

When the dashboard adds or removes a domain:

1. Update `domain_lists` table in SQLite
2. Regenerate `lists/blacklist.txt` from DB:
   ```sql
   SELECT domain FROM domain_lists WHERE list_type = 'blacklist' ORDER BY domain;
   ```
3. Regenerate `lists/whitelist.txt` similarly
4. Call `domain_filter.reload()` on the DNS server's filter instance

The .txt files are generated artifacts. The DB is the source of truth.
This allows the agent, Telegram bot, and dashboard to all modify lists
without race conditions on flat files.

---

## How Focus Notes Reach the Agent

The LangChain agent queries the API to get the active focus note for a profile:

```
GET /api/focus?profile_id=<uuid>&active_only=true
```

When analyzing a domain query, the agent:
1. Looks up which profile the query came from (via client_ip → device → profile)
2. Fetches that profile's active focus note
3. Includes the note as context in the LLM prompt

The dashboard doesn't run the agent — it just stores the data. The agent
reads it through the same API.

---

## How to Connect Dashboard to main.py

```python
# In main.py

from dashboard.app import create_app
from dashboard.database import init_db
import uvicorn
import threading

# Initialize database (creates tables if needed)
init_db(config["dashboard"]["db_path"])

# Create query logger for DNS → DB bridge
from dashboard.query_logger import QueryLogger
query_logger = QueryLogger(config["dashboard"]["db_path"])

# Pass logger to DNS server
server = DNSServer(
    ...,
    query_logger=query_logger,
)

# Create dashboard app
dashboard_app = create_app(
    config=config,
    domain_filter=server.domain_filter,
)

# Run dashboard in background thread
threading.Thread(
    target=uvicorn.run,
    kwargs={
        "app": dashboard_app,
        "host": config["dashboard"]["host"],
        "port": config["dashboard"]["port"],
        "log_level": "warning",
    },
    daemon=True,
).start()

print(f"  [✓] Dashboard at http://0.0.0.0:{config['dashboard']['port']}")

# DNS server blocks main thread
server.start()
```

---

## Implementation Order

| Step | Task                                                   | Depends on      |
|------|--------------------------------------------------------|-----------------|
| 1    | SQLite schema + database.py + init_db()                | Nothing         |
| 2    | QueryLogger (DNS → DB bridge)                          | Step 1          |
| 3    | Wire QueryLogger into dns_server.py                    | Step 2          |
| 4    | Auth module (auth.py)                                   | Nothing         |
| 5    | Lists API (routes/lists.py) + .txt regeneration        | Steps 1, 4      |
| 6    | Profiles API (routes/profiles.py)                      | Steps 1, 4      |
| 7    | Focus API (routes/focus.py)                            | Step 6          |
| 8    | Queries API (routes/queries.py)                        | Steps 1, 4      |
| 9    | Stats API (routes/stats.py)                            | Step 1          |
| 10   | Analysis API (routes/analysis.py — agent writes here)  | Step 1          |
| 11   | System health (routes/system.py)                       | Nothing         |
| 12   | WebSocket handler (websocket.py)                       | Step 2          |
| 13   | FastAPI app factory (app.py)                           | Steps 4-12      |
| 14   | Wire dashboard into main.py                            | Step 13         |
| 15   | Test all API routes with curl                          | Step 14         |
| 16   | Frontend: scaffold (Vite + React + Tailwind)           | Nothing         |
| 17   | Frontend: Layout + Sidebar                             | Step 16         |
| 18   | Frontend: Overview page                                | Steps 9, 12     |
| 19   | Frontend: Lists page                                   | Step 5          |
| 20   | Frontend: Profiles page                                | Steps 6, 7      |
| 21   | Frontend: Query Log page                               | Step 8          |
| 22   | Frontend: build → dashboard/static/                    | Steps 17-21     |
| 23   | Integration testing                                    | All above       |

---

## Testing Checklist

### API
- [ ] Auth: correct token → 200 + cookie
- [ ] Auth: wrong token → 401
- [ ] Auth: no token → 401 on all /api/* routes
- [ ] Lists: add domain → in DB + .txt regenerated + filter reloaded
- [ ] Lists: remove domain → removed from DB + .txt + filter reloaded
- [ ] Lists: bulk import 100 domains → correct count, dupes skipped
- [ ] Lists: search works (partial match)
- [ ] Profiles: create profile + assign devices
- [ ] Profiles: delete profile cascades to devices + focus notes
- [ ] Focus: create note → starts_at and expires_at correct
- [ ] Focus: extend → new expires_at
- [ ] Focus: end early → ended_early = 1
- [ ] Focus: expired notes not returned with active_only=true
- [ ] Queries: filter by profile, action, domain, date range
- [ ] Queries: pagination works
- [ ] Queries: CSV export downloads correctly
- [ ] Stats: counts match query_log data
- [ ] System: health returns correct DB size and counts
- [ ] WebSocket: receives live events as dig commands run
- [ ] Analysis: agent can POST results, dashboard can GET them

### Frontend
- [ ] Overview: stats load, live ticker scrolls, charts render
- [ ] Lists: add, remove, search, bulk import, pagination
- [ ] Profiles: create, edit, delete, add/remove devices
- [ ] Profiles: set focus, see timer, extend, end early
- [ ] Query log: all filters work, sort works, pagination
- [ ] Mobile: all pages usable on phone screen
- [ ] Works on Chrome, Firefox, Safari

### Integration
- [ ] dig command → appears in dashboard query log within 1 second
- [ ] Add domain in dashboard → dig returns blocked response
- [ ] Remove domain in dashboard → dig resolves normally
- [ ] Set focus note → agent can read it via API
- [ ] Agent writes analysis → visible in dashboard
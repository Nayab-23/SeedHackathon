# Build Plan: BasicDNS Server with Blacklist, Whitelist & OpenClaw Observer
 
## Overview
 
A Python-based DNS server that listens on UDP port 53, resolves queries by forwarding to an upstream DNS, and filters domains using a blacklist and whitelist. Every request passes through **OpenClaw**, an observer module that logs and inspects all DNS traffic in real time.
 
**Core rule:** Whitelist always overrides blacklist. Blacklist blocks a domain and all its subdomains.
 
---
 
## Architecture
 
```
Client query (UDP:53)
        │
        ▼
┌──────────────────┐
│   DNS Listener    │  ← UDP socket, threaded per-request
│  (dns_server.py)  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│    OpenClaw       │  ← Observes EVERY request: logs domain, client IP,
│  (observer.py)    │     query type, action, response time to terminal + file
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Domain Filter    │  ← Checks whitelist first, then blacklist, then default allow
│   (filter.py)     │
└────────┬─────────┘
         │
    ┌────┴─────┐
    │          │
    ▼          ▼
┌────────┐  ┌──────────┐
│ Blocker│  │ Resolver  │
│blocked │  │ forward   │
│response│  │ to 8.8.8.8│
└────────┘  └──────────┘
    │          │
    └────┬─────┘
         │
         ▼
   Response → Client
```
 
---
 
## Project Structure
 
```
dns-server/
├── main.py                  # Entry point — loads config, inits OpenClaw, starts server
├── config.yaml              # All settings (listen addr, upstream, block mode, paths)
├── requirements.txt         # Python deps: dnslib, colorama, pyyaml
├── README.md                # User-facing docs with install + usage instructions
├── server/
│   ├── __init__.py
│   ├── dns_server.py        # UDP listener + threaded request handler
│   ├── resolver.py          # Forwards allowed queries to upstream DNS
│   ├── filter.py            # Loads lists, matches domains (exact + subdomain)
│   └── blocker.py           # Generates blocked DNS responses (0.0.0.0 or NXDOMAIN)
├── openclaw/
│   ├── __init__.py
│   └── observer.py          # Logs every request to terminal (colored) + log file
├── lists/
│   ├── blacklist.txt        # Blocked domains, one per line
│   └── whitelist.txt        # Always-allowed domains, one per line
└── logs/
    └── openclaw.log         # Persistent query log (auto-created)
```
 
---
 
## Pre-Installation Steps (before running)

### 1. System requirements
- Python 3.10+
- pip
 
### 2. Create virtual environment
```bash
cd dns-server/
python3 -m venv venv
source venv/bin/activate
```
 
### 3. Install Python dependencies
```bash
pip install -r requirements.txt
```
 
**requirements.txt contents:**
```
dnslib>=0.9.24
colorama>=0.4.6
pyyaml>=6.0
```
 
| Package  | Why                                      |
|----------|------------------------------------------|
| dnslib   | Parse and build DNS packets              |
| colorama | Colored terminal output for OpenClaw     |
| pyyaml   | Read config.yaml                         |
 
### 4. ONLY when we run this on the Orin Nano, IGNORE for now.
```bash
sudo systemctl stop systemd-resolved
sudo systemctl disable systemd-resolved
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
```
 
---
 
## Module Specifications
 
### Module 1: `config.yaml`
 
YAML config file with these sections:
 
| Section          | Keys                                    | Defaults                  |
|------------------|-----------------------------------------|---------------------------|
| `server`         | `listen_address`, `port`                | `"0.0.0.0"`, `53`        |
| `upstream`       | `dns_server`, `port`, `timeout`         | `"8.8.8.8"`, `53`, `3`   |
| `blocking`       | `mode` (`"zero_ip"` or `"nxdomain"`)   | `"zero_ip"`              |
| `openclaw`       | `enabled`, `log_file`                   | `true`, `"logs/openclaw.log"` |
| `lists`          | `blacklist`, `whitelist`                | `"lists/blacklist.txt"`, `"lists/whitelist.txt"` |
 
---
 
### Module 2: `server/filter.py` — DomainFilter
 
**Responsibilities:**
- Load domains from blacklist.txt and whitelist.txt (one domain per line, `#` comments, blank lines ignored)
- Strip trailing dots, normalize to lowercase
- `check(domain) → Action` — returns WHITELISTED, BLOCKED, or ALLOWED
- Subdomain matching: blocking `example.com` also blocks `sub.example.com`, `a.b.example.com`, etc.
- Evaluation order: whitelist first → blacklist → default ALLOWED
- `reload()` method to re-read lists from disk
 
**Key logic for subdomain matching:**
Walk up the domain hierarchy. For `ads.tracker.example.com`, check: `ads.tracker.example.com` → `tracker.example.com` → `example.com` → `com`. If any segment matches a list entry, it's a match.
 
---
 
### Module 3: `server/resolver.py` — Resolver
 
**Responsibilities:**
- Open a UDP socket to the upstream DNS server
- Send the raw query bytes, receive the raw response
- Respect a configurable timeout (default 3s)
- Return `None` on timeout or socket error (caller handles SERVFAIL)
 
---
 
### Module 4: `server/blocker.py` — Blocked Response Builder
 
**Responsibilities:**
- Parse the incoming query with `dnslib.DNSRecord.parse()`
- Build a reply using `request.reply()`
- Two modes:
  - `"zero_ip"` — add an A record for `0.0.0.0` with TTL 300. For AAAA queries, return empty answer.
  - `"nxdomain"` — set `reply.header.rcode = RCODE.NXDOMAIN`
- Return packed bytes
 
---
 
### Module 5: `openclaw/observer.py` — OpenClaw
 
**This is the core observer. Every single DNS request passes through it.**
 
**Responsibilities:**
- `observe(client_ip, domain, query_type, action, response_ms, extra)` — the single chokepoint method
- Print color-coded line to terminal per request:
  - GREEN for ALLOWED
  - RED for BLOCKED
  - CYAN for WHITELISTED
  - YELLOW for ERROR
- Write plain-text version to the log file
- Track counters: `total_queries`, `blocked_count`, `allowed_count`, `whitelisted_count`
- `startup_banner()` — print ASCII art banner on server start
- `print_stats()` — print session summary on shutdown
- Uses `colorama` for cross-platform color support
- File logger uses Python's `logging` module with a FileHandler
 
**Log line format:**
```
[2026-03-21 18:30:45 UTC] [  BLOCKED   ] A      ads.example.com                        from 192.168.1.5      2.3ms
[2026-03-21 18:30:46 UTC] [  ALLOWED   ] A      google.com                             from 192.168.1.5      15.7ms
[2026-03-21 18:30:47 UTC] [WHITELISTED ] AAAA   safe.example.com                       from 192.168.1.5      12.1ms
```
 
---
 
### Module 6: `server/dns_server.py` — DNSServer
 
**Responsibilities:**
- Bind a UDP socket to `listen_address:port`
- Main loop: `recvfrom()` with 1-second timeout (allows clean Ctrl+C shutdown)
- Spawn a daemon thread per incoming query → `_handle_query()`
- `_handle_query()` flow:
  1. Parse raw packet with `dnslib.DNSRecord.parse()` — on failure, log ERROR via OpenClaw and return
  2. Extract domain name and query type
  3. Call `domain_filter.check(domain)` to get the Action
  4. If BLOCKED → call `blocker.build_blocked_response()`
  5. If ALLOWED or WHITELISTED → call `resolver.resolve()`; if upstream fails, build SERVFAIL
  6. Measure elapsed time
  7. Call `openclaw.observe()` with all details
  8. Send response bytes back to client
- `stop()` — close socket, print OpenClaw stats
 
---
 
### Module 7: `main.py` — Entry Point
 
**Responsibilities:**
- Load and parse `config.yaml` with PyYAML
- Instantiate `OpenClaw` with config values
- Call `claw.startup_banner()`
- Instantiate `DNSServer` passing all config + the OpenClaw instance
- Print "Press Ctrl+C to stop" message
- Call `server.start()` (blocks until interrupted)
 
---
 
## Implementation Order
 
| Step | What to build                     | Depends on        |
|------|-----------------------------------|--------------------|
| 1    | `config.yaml` + `requirements.txt` | Nothing           |
| 2    | `openclaw/observer.py`            | Nothing            |
| 3    | `server/filter.py`                | `openclaw` (imports Action enum) |
| 4    | `server/resolver.py`              | Nothing            |
| 5    | `server/blocker.py`               | `dnslib`           |
| 6    | `server/dns_server.py`            | All of the above   |
| 7    | `main.py`                         | All of the above   |
| 8    | `lists/blacklist.txt`, `lists/whitelist.txt` | Nothing |
| 9    | `README.md`                       | Everything (document last) |
 
---
 
## Testing Checklist
 
Run the server on port 5353 for unprivileged testing, then use `dig`:
 
```bash
# 1. Normal domain → should resolve with real IP
dig @127.0.0.1 -p 5353 google.com
 
# 2. Blacklisted domain → should return 0.0.0.0 (or NXDOMAIN)
dig @127.0.0.1 -p 5353 ads.example.com
 
# 3. Subdomain of blacklisted → should also be blocked
dig @127.0.0.1 -p 5353 sub.ads.example.com
 
# 4. Whitelisted domain → should resolve even if it matches blacklist
dig @127.0.0.1 -p 5353 safe.example.com
 
# 5. Verify OpenClaw terminal output shows all 4 queries with correct actions
# 6. Verify logs/openclaw.log contains matching entries
# 7. Send malformed data → server should not crash
echo "garbage" | nc -u 127.0.0.1 5353
```
 
---
 
## Running in Production
 
```bash
# Port 53 requires root on Linux/macOS
sudo venv/bin/python main.py
 
# Point a client machine's DNS to this server's IP
# Then all DNS traffic flows through OpenClaw
```
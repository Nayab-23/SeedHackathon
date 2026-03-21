# SeedHackathon - Smart DNS Parental Control System

A goal-driven DNS filtering and parental control system that uses the Reachy Mini robot as a goal-setting companion. This DNS handler ensures devices only access websites aligned with daily goals, with built-in screen time management.

## Features

### Core DNS Filtering
- **Goal-based filtering**: Create daily goals and associate allowed domains
- **Global blocklist/allowlist**: System-wide domain blocking and whitelisting
- **Subdomain matching**: Intelligently handles subdomains (e.g., `docs.github.com` matches `github.com`)
- **Request approval workflow**: Unknown domains require approval before access

### Screen Time Management
- **Per-device limits**: Set daily screen time limits for each device
- **Time-based blocking**: Restrict internet access to specific hours
- **Usage tracking**: Monitor how much time each device spends online

### Configuration
- **JSON-based persistence**: Goals and rules stored in `config.json`
- **Easy CLI management**: Command-line interface for setup and testing

## Project Structure

```
├── goal_manager.py          # Goal creation and management
├── dns_filter.py            # Core DNS filtering logic
├── screen_time_manager.py   # Screen time tracking and enforcement
├── dns_server.py            # DNS server implementation
├── config_manager.py        # Configuration file management
├── main.py                  # CLI application
├── test_dns_filter.py       # Test suite
├── config.json              # Configuration file (auto-generated)
└── requirements.txt         # Python dependencies
```

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Make main.py executable
chmod +x main.py
```

## Quick Start

### 1. Create a Goal

```bash
python main.py create-goal goal_1 "Morning Study" \
  --category educational \
  --domains wikipedia.org github.com stackoverflow.com python.org
```

### 2. List Goals

```bash
python main.py list-goals
```

### 3. Test the Filter

```bash
python main.py test-filter github.com
python main.py test-filter facebook.com  # Unknown domain
```

### 4. Set Screen Time Limits

```bash
python main.py set-screen-time phone_1 120  # 120 minutes per day
```

### 5. Add Domains to Blocklist

```bash
python main.py block-domain facebook.com
```

### 6. Start the DNS Server

**Note**: Requires root access to run on port 53. For testing, use port 5053.

```bash
# Testing (no root required)
python main.py start-server  # Listens on 0.0.0.0:5053

# Production (requires root)
sudo python main.py start-server
```

## Usage Examples

### Example 1: Educational Goal with Multiple Domains

```bash
python main.py create-goal school_2024 "School Study" \
  --category educational \
  --domains \
    wikipedia.org \
    khan-academy.com \
    github.com \
    stackoverflow.com \
    coursera.org
```

### Example 2: Filter Testing

```bash
# Test allowed domain
python main.py test-filter wikipedia.org
# Output: Result: allow, Reason: Allowed by goal: School Study

# Test blocked domain
python main.py block-domain tiktok.com
python main.py test-filter tiktok.com
# Output: Result: block, Reason: Domain in global blocklist: tiktok.com

# Test unknown domain
python main.py test-filter unknown-site.example.com
# Output: Result: require_approval, Reason: Domain not in any active goal
```

### Example 3: Multiple Devices with Different Limits

```bash
python main.py set-screen-time phone_1 60    # 1 hour/day
python main.py set-screen-time phone_2 120   # 2 hours/day
python main.py set-screen-time laptop_1 240  # 4 hours/day
```

## Testing

Run the full test suite:

```bash
python test_dns_filter.py
```

## Configuration File

The `config.json` file stores:

```json
{
  "goals": [
    {
      "id": "goal_1",
      "name": "Morning Study",
      "category": "educational",
      "allowed_domains": ["wikipedia.org", "github.com"],
      "blocked_domains": [],
      "active": true,
      "created_at": "2024-03-21T10:30:00"
    }
  ],
  "screen_time_rules": [],
  "global_blocklist": ["facebook.com", "tiktok.com"],
  "global_allowlist": ["google.com", "github.com"],
  "dns_server": {
    "listen_port": 5053,
    "upstream_dns": "8.8.8.8",
    "listen_address": "0.0.0.0"
  }
}
```

## DNS Filtering Flow

```
DNS Query Received
    ↓
Check Global Blocklist → Block
    ↓
Check Global Allowlist → Allow
    ↓
Check Screen Time Limits → Block (if exceeded/outside allowed hours)
    ↓
Check Active Goals → Allow (if domain in goal)
    ↓
Default: Require Approval
```

## Future Features

- [ ] Reachy Mini robot integration for voice-based goal setting
- [ ] Agora integration for parent-child communication
- [ ] Multilingual support (Chinese, Spanish, etc.)
- [ ] Study time tracking with detailed analytics
- [ ] Machine learning for intelligent filtering
- [ ] Mobile app for parents to manage rules remotely
- [ ] Reward system for completing goals

## Architecture Notes

### For Nvidia Orin Nano Deployment

The system is designed to run on Nvidia Orin Nano with OpenClaw:

1. **DNS Server**: Runs as a background service (requires root for port 53)
2. **Goal Manager**: Stores goals and user preferences
3. **DNS Filter**: Applies rules in real-time
4. **Screen Time Manager**: Tracks and enforces time limits
5. **Config Manager**: Persists settings to JSON

### Permission Requirements

- **Port 53**: Requires root/admin access
- **Port 5053 (testing)**: No special permissions needed
- **Config file**: Requires write permissions to application directory

## Technical Details

- **DNS Protocol**: Uses `dnslib` for DNS packet parsing/generation
- **Threading**: DNS server uses threading for handling multiple queries
- **Caching**: Upstream DNS responses are cached by the resolver
- **Logging**: Detailed logging for debugging and monitoring

## Troubleshooting

### "Permission denied" when starting server

Use port 5053 for testing (no root required):
```bash
python main.py start-server --port 5053
```

### Domains not being filtered

1. Check configuration: `python main.py list-goals`
2. Test filter: `python main.py test-filter your-domain.com`
3. Check if domain is in allowlist: Check `config.json`

### DNS queries not reaching server

Ensure devices are configured to use your DNS server:
- On Linux: `/etc/resolv.conf` or NetworkManager
- On macOS: System Preferences → Network → DNS
- On Windows: Network Settings → DNS

## Contributing

Current milestone: MVP DNS filter implementation ✓

Next phase: Integration with Reachy Mini robot and Agora communication platform.

## License

Part of the SeedHackathon project

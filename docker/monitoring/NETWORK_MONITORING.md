# Network Monitoring & Firewall for Docker Container

Interactive network access control for the Docker development environment. Monitor and control all network requests with fine-grained permissions.

## Features

- **Real-time Network Monitoring**: See all HTTP/HTTPS requests from the container
- **Web-based Dashboard**: Modern browser interface with live updates
- **Interactive Permission Control**: Approve or deny each request with prompts
- **Multiple Permission Levels**:
  - `allow-once`: Allow this single request
  - `deny-once`: Deny this single request
  - `allow-domain`: Always allow all requests to this domain
  - `deny-domain`: Always deny all requests to this domain
  - `allow-url`: Always allow this specific URL
  - `deny-url`: Always deny this specific URL
- **Persistent Rules**: Rules are saved and reloaded automatically
- **Access Logging**: All requests are logged with timestamps and decisions
- **Statistics Dashboard**: View request counts, recent activity, and active rules
- **Multiple Interfaces**: Web UI, CLI, or programmatic API access

## Quick Start

### 1. Start Container with Network Monitoring

```bash
./docker/run-isolated.sh
```

**Note**: Network monitoring is **enabled by default**. To disable it:
```bash
./docker/run-isolated.sh --no-monitoring
```

This will:
- Start a network proxy on the host (port 8080)
- Start a web UI server (port 8081)
- Launch the Docker container configured to use the proxy
- Prompt you for permission on each new domain/URL accessed

### 2. Access the Web Dashboard

Open your browser to **http://localhost:8081** for:
- 🔴 **Live Activity Feed**: See requests in real-time as they happen
- 📊 **Statistics Dashboard**: View allowed/denied counts and trends
- ⚙️ **Rule Management**: Add, edit, or remove firewall rules with a click
- 📥 **Import/Export**: Save and load rule configurations

The web UI updates automatically via Server-Sent Events - no refresh needed!

### 3. Manage Firewall Rules (CLI Alternative)

Prefer the terminal? Run:

```bash
./docker/monitoring/manage-firewall.sh
```

This opens an interactive menu where you can:
- View statistics and recent requests
- Add/remove rules manually
- Export/import rule configurations
- Clear all rules

Or for quick stats:

```bash
./docker/monitoring/manage-firewall.sh --stats
```

## How It Works

```
┌─────────────────────┐
│  Docker Container   │
│                     │
│  HTTP_PROXY=        │
│  host:8080          │
└──────────┬──────────┘
           │
           │ All HTTP/HTTPS
           │ traffic
           ▼
┌─────────────────────┐
│  Network Proxy      │
│  (mitmproxy)        │
│                     │
│  - Checks rules     │
│  - Prompts user     │
│  - Logs requests    │
└──────────┬──────────┘
           │
           │ Allowed
           │ requests
           ▼
┌─────────────────────┐
│     Internet        │
└─────────────────────┘
```

## Permission Workflow

When the container makes a network request:

1. **Check Existing Rules**: If a rule exists for this URL or domain, apply it
2. **Prompt User**: If no rule exists, show interactive prompt:
   ```
   ================================================================================
   Network Access Request
   Host: api.github.com
   Method: GET
   Path: /repos/user/repo
   ================================================================================

   Choose action:
     1. Allow this request once
     2. Deny this request once
     3. Always allow api.github.com
     4. Always deny api.github.com
     5. Always allow this exact URL
     6. Always deny this exact URL

   Your choice [1]:
   ```
3. **Apply Decision**: Allow or deny the request based on user choice
4. **Save Rule**: If user chose a persistent rule, save it for future requests

## Configuration Files

All configuration and logs are stored in `~/docker-agent-data/`:

- `network-rules.json`: Persistent firewall rules
- `network-access.log`: Complete access log with timestamps

### Rules File Format

```json
{
  "github.com": "allow-domain",
  "api.openai.com": "allow-domain",
  "suspicious-site.com": "deny-domain",
  "https://specific-endpoint.com/api/sensitive": "deny"
}
```

## Web UI and API

### Web Dashboard

The web UI (http://localhost:8081) provides a modern, real-time interface:

**Live Activity Feed**
- See network requests as they happen (auto-updates every 1-2 seconds)
- Color-coded decision indicators (green=allow, red=deny)
- Filter and search through request history
- Request details: timestamp, method, URL, decision

**Statistics Dashboard**
- Total requests counter
- Allowed vs denied breakdown
- Active rules count
- Visual indicators and charts

**Rule Management**
- Add new rules with dropdown action selector
- Delete existing rules with one click
- Import rules from JSON file
- Export current rules for backup/sharing
- Clear all rules with confirmation

**Browser Features**
- Dark mode interface optimized for long sessions
- Responsive design works on desktop and mobile
- No refresh needed - uses Server-Sent Events for live updates
- Clean, minimal UI inspired by GitHub's design system

### REST API

The web UI is powered by a REST API that you can use programmatically:

**GET /api/rules**
```bash
curl http://localhost:8081/api/rules
```
Returns all firewall rules and metadata.

**POST /api/rules**
```bash
curl -X POST http://localhost:8081/api/rules \
  -H 'Content-Type: application/json' \
  -d '{"target": "example.com", "action": "allow-domain"}'
```
Add or update a firewall rule.

**DELETE /api/rules/{target}**
```bash
curl -X DELETE http://localhost:8081/api/rules/example.com
```
Remove a specific rule.

**GET /api/stats**
```bash
curl http://localhost:8081/api/stats
```
Get network access statistics.

**GET /api/requests**
```bash
curl http://localhost:8081/api/requests?limit=50
```
Get recent network requests.

**GET /api/stream**
```bash
curl http://localhost:8081/api/stream
```
Server-Sent Events stream for live updates.

**GET /api/health**
```bash
curl http://localhost:8081/api/health
```
Health check endpoint.

### Programmatic Usage Example

```python
import requests

# Add a rule
requests.post('http://localhost:8081/api/rules', json={
    'target': 'api.github.com',
    'action': 'allow-domain'
})

# Get statistics
stats = requests.get('http://localhost:8081/api/stats').json()
print(f"Total requests: {stats['stats']['total']}")

# Export all rules
rules = requests.get('http://localhost:8081/api/export').json()
with open('my-rules.json', 'w') as f:
    json.dump(rules, f, indent=2)
```

## Common Workflows

### Whitelist Common Services

Pre-configure trusted domains before running:

```bash
# Edit rules file
cat > ~/docker-agent-data/network-rules.json <<EOF
{
  "github.com": "allow-domain",
  "*.github.com": "allow-domain",
  "pypi.org": "allow-domain",
  "files.pythonhosted.org": "allow-domain",
  "npmjs.org": "allow-domain",
  "registry.npmjs.org": "allow-domain"
}
EOF
```

### Block Telemetry/Analytics

```json
{
  "analytics.google.com": "deny-domain",
  "*.analytics.google.com": "deny-domain",
  "telemetry.microsoft.com": "deny-domain",
  "*.telemetry.microsoft.com": "deny-domain"
}
```

### Review Network Activity

```bash
# View recent requests
./docker/monitoring/manage-firewall.sh --stats

# View full access log
tail -f ~/docker-agent-data/network-access.log

# Search for specific domain
grep "github.com" ~/docker-agent-data/network-access.log
```

### Export/Import Rules

```bash
# Export current rules
./docker/manage-firewall.sh
# Choose option 6, specify filename

# Import rules
cp my-rules.json ~/docker-agent-data/network-rules.json
```

## Advanced Usage

### Run Without Monitoring

To run the container without network monitoring, use the `--no-monitoring` flag:

```bash
./docker/run-isolated.sh --no-monitoring
```

### Custom Proxy Port

Edit `network-monitor.py` and change the port in the `run_proxy()` function, then update `run-isolated.sh` accordingly.

### HTTPS Certificate Trust

For HTTPS interception, mitmproxy creates a CA certificate. To avoid certificate warnings:

1. The certificate is at `~/.mitmproxy/mitmproxy-ca-cert.pem`
2. Install it in the container or configure tools to trust it
3. Alternatively, use `--no-verify` flags for development (not recommended for production)

### Monitoring Non-HTTP Traffic

The current implementation monitors HTTP/HTTPS only. For other protocols:

- Use iptables/nftables rules on the host
- Configure Docker with custom network plugins
- Use container network namespaces with custom routing

## Troubleshooting

### Proxy Won't Start

```bash
# Check if port 8080 is in use
lsof -i :8080

# View proxy logs
tail -f /tmp/network-monitor.log
```

### Container Can't Reach Network

```bash
# Verify proxy is running
pgrep -f network-monitor.py

# Check proxy is accessible from container
# Inside container:
curl -x http://host.docker.internal:8080 http://example.com
```

### Certificate Errors

```bash
# For curl
curl --cacert ~/.mitmproxy/mitmproxy-ca-cert.pem https://example.com

# For Python requests
export REQUESTS_CA_BUNDLE=~/.mitmproxy/mitmproxy-ca-cert.pem

# For Node.js
export NODE_EXTRA_CA_CERTS=~/.mitmproxy/mitmproxy-ca-cert.pem
```

### Rules Not Persisting

```bash
# Check rules file permissions
ls -la ~/docker-agent-data/network-rules.json

# Verify JSON is valid
cat ~/docker-agent-data/network-rules.json | python3 -m json.tool
```

## Security Considerations

- **Trust**: The proxy can see all HTTP/HTTPS traffic (including headers, bodies)
- **Certificate**: mitmproxy creates a local CA that can decrypt HTTPS
- **Rules File**: Contains your allow/deny decisions - review periodically
- **Logs**: May contain sensitive URLs or data - rotate/clean regularly

**Recommendation**: Only use network monitoring when analyzing or debugging network behavior. For normal development, use `run-isolated.sh` without the proxy.

## Implementation Details

- **Proxy**: mitmproxy (Python-based HTTP/HTTPS proxy with addon API)
- **UI**: Rich library for terminal UI and formatting
- **Storage**: JSON files for rules and plain text for logs
- **Language**: Python 3.12+ with inline dependencies (PEP 723)

## Examples

### Example 1: Analyze Package Installation

```bash
# Start container with monitoring (on by default)
./docker/run-isolated.sh

# In container, install package
pip install requests

# Observe all network requests in web UI or:
./docker/monitoring/manage-firewall.sh --stats
```

### Example 2: Restrict to Essential Services Only

```bash
# Pre-configure minimal rules (allow-list approach)
cat > ~/docker-agent-data/network-rules.json <<EOF
{
  "github.com": "allow-domain",
  "pypi.org": "allow-domain"
}
EOF

# Run container - only GitHub and PyPI allowed
# All other requests are denied and added to pending queue for approval
./docker/run-isolated.sh
```

**Note:** There is no wildcard catch-all deny rule. Requests that don't match any allow rule are automatically denied and added to the pending approval queue visible in the web UI.

### Example 3: Audit AI Tool Network Usage

```bash
# Start with clean rules
rm ~/docker-agent-data/network-rules.json

# Run with monitoring (on by default)
./docker/run-isolated.sh

# In container, use AI tool
claude "Write hello world in Python"

# Review what endpoints were accessed
./docker/monitoring/manage-firewall.sh --stats
```

## Current Limitations

**Protocol Coverage**: Only HTTP/HTTPS traffic that respects proxy settings is monitored.

**NOT Currently Covered**:
- ❌ Local network access (`localhost`, `127.0.0.1`, `192.168.x.x`, `10.x.x.x`)
- ❌ Direct TCP/UDP connections
- ❌ DNS queries
- ❌ SSH, FTP, SMTP, database connections
- ❌ WebSocket connections (may bypass proxy)
- ❌ Applications that ignore HTTP_PROXY environment variables

**Workaround**: For HTTP/HTTPS to localhost, remove `NO_PROXY` setting in `run-isolated.sh`. For comprehensive coverage including all protocols, see Future Enhancements below.

## Future Enhancements

Potential improvements:

- [ ] **Comprehensive network monitoring with iptables/nftables** (HIGH PRIORITY)
  - Monitor ALL protocols (TCP, UDP, ICMP, etc.)
  - Cover local network access (localhost, private IPs, host machine)
  - DNS query monitoring and filtering
  - Interactive prompts for all connection types
  - Userspace daemon for permission management
  - Complete visibility into container network activity
- [x] **Web-based UI for monitoring and management** (COMPLETED ✓)
  - Real-time dashboard with live updates
  - Statistics and analytics
  - Rule management interface
  - REST API for programmatic access
- [ ] Bandwidth limiting per domain
- [ ] Request/response content inspection and logging
- [ ] Rate limiting (e.g., max 10 requests/minute to a domain)
- [ ] Scheduling (allow during work hours only)
- [ ] Multiple rule profiles (strict, normal, permissive)
- [ ] Per-process network filtering (track which binary makes requests)
- [ ] Network namespace isolation with custom routing tables
- [ ] TLS certificate pinning for specific domains
- [ ] Geo-blocking based on IP address location

## See Also

- [Docker Documentation](../README.md)
- [mitmproxy Documentation](https://docs.mitmproxy.org/)
- [Container Networking](https://docs.docker.com/network/)

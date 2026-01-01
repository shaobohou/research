# Network Monitoring & Firewall for Docker Container

Interactive network access control for the Docker development environment. Monitor and control all network requests with fine-grained permissions.

## Features

- **Real-time Network Monitoring**: See all HTTP/HTTPS requests from the container
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

## Quick Start

### 1. Start Container with Network Monitoring

```bash
./docker/run-monitored.sh
```

This will:
- Start a network proxy on the host (port 8080)
- Launch the Docker container configured to use the proxy
- Prompt you for permission on each new domain/URL accessed

### 2. Manage Firewall Rules (Optional)

In a separate terminal, run:

```bash
./docker/manage-firewall.sh
```

This opens an interactive menu where you can:
- View statistics and recent requests
- Add/remove rules manually
- Export/import rule configurations
- Clear all rules

### 3. View Statistics Only

```bash
./docker/manage-firewall.sh --stats
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
./docker/manage-firewall.sh --stats

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

To run the container without network monitoring, use the standard script:

```bash
./docker/run-isolated.sh
```

### Custom Proxy Port

Edit `network-monitor.py` and change the port in the `run_proxy()` function, then update `run-monitored.sh` accordingly.

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
# Start monitored container
./docker/run-monitored.sh

# In container, install package
pip install requests

# Observe all network requests:
# - pypi.org (package index)
# - files.pythonhosted.org (package files)
# - etc.
```

### Example 2: Restrict to Essential Services Only

```bash
# Pre-configure minimal rules
cat > ~/docker-agent-data/network-rules.json <<EOF
{
  "github.com": "allow-domain",
  "pypi.org": "allow-domain",
  "*": "deny"
}
EOF

# Run container - only GitHub and PyPI allowed
./docker/run-monitored.sh
```

### Example 3: Audit AI Tool Network Usage

```bash
# Start with clean rules
rm ~/docker-agent-data/network-rules.json

# Run monitored
./docker/run-monitored.sh

# In container, use AI tool
claude "Write hello world in Python"

# Review what endpoints were accessed
./docker/manage-firewall.sh --stats
```

## Future Enhancements

Potential improvements:

- [ ] Web-based UI for remote management
- [ ] Bandwidth limiting per domain
- [ ] Request/response content inspection and logging
- [ ] Integration with iptables for non-HTTP protocols
- [ ] Rate limiting (e.g., max 10 requests/minute to a domain)
- [ ] Scheduling (allow during work hours only)
- [ ] Multiple rule profiles (strict, normal, permissive)
- [ ] Browser extension for managing rules via GUI

## See Also

- [Docker Documentation](../README.md)
- [mitmproxy Documentation](https://docs.mitmproxy.org/)
- [Container Networking](https://docs.docker.com/network/)

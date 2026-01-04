# Network Enforcement with iptables

This document describes OS-level network enforcement to prevent containers from bypassing the proxy.

## Overview

The network monitoring proxy is **cooperative** - it relies on environment variables (`HTTP_PROXY`, `HTTPS_PROXY`). Malicious code can bypass it by:
- Ignoring environment variables
- Making raw socket connections
- Using non-HTTP protocols

**OS-level enforcement** uses iptables to force **ALL** network traffic through the proxy at the kernel level.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Host Machine                                               │
│                                                             │
│  ┌──────────────┐         ┌──────────────┐                │
│  │  iptables    │────────▶│  Proxy:8080  │                │
│  │  Rules       │         │  (mitmproxy) │                │
│  │              │         └──────┬───────┘                │
│  │ ALLOW:       │                │                         │
│  │  container   │                │                         │
│  │  → host:8080 │                │                         │
│  │              │                ▼                         │
│  │ DENY:        │         ┌──────────────┐                │
│  │  container   │         │   Internet   │                │
│  │  → *         │         └──────────────┘                │
│  └──────────────┘                                          │
│         │                                                  │
│         ▼                                                  │
│  ┌──────────────────────────────────────┐                 │
│  │  Docker Container                    │                 │
│  │                                      │                 │
│  │  ✅ curl http://github.com          │                 │
│  │     → Forced through proxy           │                 │
│  │                                      │                 │
│  │  ❌ nc -z google.com 443             │                 │
│  │     → BLOCKED by iptables            │                 │
│  │                                      │                 │
│  │  ❌ python -c "import socket..."     │                 │
│  │     → BLOCKED by iptables            │                 │
│  └──────────────────────────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

## Implementation

### Requirements

- Linux host (iptables support)
- sudo access for iptables rules
- Docker version with `--network` support

### How It Works

1. **Create isolated Docker network** with no default gateway
2. **Add iptables rules** to allow ONLY traffic to proxy port
3. **Container is enforced** - cannot bypass proxy even with raw sockets

### iptables Rules

```bash
# Get container IP
CONTAINER_IP="172.17.0.5"  # Example

# Allow container → host proxy (port 8080)
sudo iptables -I DOCKER-USER -s $CONTAINER_IP -p tcp --dport 8080 -j ACCEPT

# Allow DNS (necessary for domain resolution)
sudo iptables -I DOCKER-USER -s $CONTAINER_IP -p udp --dport 53 -j ACCEPT
sudo iptables -I DOCKER-USER -s $CONTAINER_IP -p tcp --dport 53 -j ACCEPT

# Block all other outbound traffic from container
sudo iptables -I DOCKER-USER -s $CONTAINER_IP -j DROP
```

### Cleanup

Rules are automatically removed when container stops:

```bash
# Remove container-specific rules
sudo iptables -D DOCKER-USER -s $CONTAINER_IP -p tcp --dport 8080 -j ACCEPT
sudo iptables -D DOCKER-USER -s $CONTAINER_IP -p udp --dport 53 -j ACCEPT
sudo iptables -D DOCKER-USER -s $CONTAINER_IP -p tcp --dport 53 -j ACCEPT
sudo iptables -D DOCKER-USER -s $CONTAINER_IP -j DROP
```

## Security Considerations

### Advantages

✅ **Kernel-level enforcement** - cannot be bypassed by container code
✅ **Protocol-agnostic** - blocks TCP, UDP, raw sockets
✅ **Defense in depth** - proxy provides visibility, iptables provides enforcement
✅ **Transparent** - container code doesn't need modification

### Limitations

❌ **Linux-only** - iptables not available on macOS/Windows
❌ **Requires sudo** - users must have root access
❌ **DNS visibility** - DNS queries not monitored (only HTTP/HTTPS via proxy)
❌ **Localhost access** - container cannot access other containers directly

### macOS Alternative

macOS doesn't have iptables, but offers similar enforcement via:
- **pfctl (Packet Filter)** - macOS firewall rules
- **Docker Desktop network isolation** - Limited compared to Linux
- **Sandbox profiles** - Application-level restrictions (see Anthropic's sandbox-runtime)

For macOS users, the proxy-only approach provides **monitoring and visibility** but not **enforcement**.

## Performance Impact

- **Minimal overhead** - iptables rules are very efficient
- **No proxy latency for denied traffic** - blocked at kernel level before reaching proxy
- **DNS lookup required** - Adds ~10-50ms per unique domain

## Use Cases

### When to Enable Enforcement

- ✅ Running untrusted code (AI-generated, third-party scripts)
- ✅ Testing sandbox escape attempts
- ✅ Auditing network behavior of tools
- ✅ Compliance requirements for network isolation

### When to Skip Enforcement

- ❌ Development on macOS/Windows (not supported)
- ❌ User doesn't have sudo access
- ❌ Performance-critical applications (use monitoring-only)
- ❌ Simple trusted workflows

## Comparison Matrix

| Feature | Proxy Only | Proxy + iptables |
|---------|-----------|------------------|
| HTTP/HTTPS visibility | ✅ Yes | ✅ Yes |
| Interactive approval | ✅ Yes | ✅ Yes |
| Bypass protection | ❌ No | ✅ Yes |
| Raw socket blocking | ❌ No | ✅ Yes |
| DNS monitoring | ❌ No | ❌ No* |
| Requires sudo | ❌ No | ✅ Yes |
| Platform support | All | Linux only |

\* DNS queries are allowed but not monitored

## Future Enhancements

- [ ] DNS query logging via `dnsproxy` or `dnsmasq`
- [ ] Per-IP and per-port granular rules
- [ ] Dynamic rule updates without restart
- [ ] macOS `pfctl` implementation
- [ ] Rate limiting and quota enforcement
- [ ] Audit log of blocked connection attempts

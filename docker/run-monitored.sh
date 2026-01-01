#!/usr/bin/env bash
set -euo pipefail

#
# Run Docker container with network monitoring and interactive firewall control
#
# This script starts a network proxy on the host that intercepts all traffic
# from the Docker container, allowing you to interactively allow/deny requests
# with different permission levels.
#

# Defaults: copy Codex auth, skip Claude creds
COPY_CODEX_CREDS="${COPY_CODEX_CREDS:-true}"
COPY_CLAUDE_CREDS="${COPY_CLAUDE_CREDS:-false}"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Get repo root and name, or use current directory if not a git repo
if git rev-parse --git-dir > /dev/null 2>&1; then
  ROOT_DIR="$(git rev-parse --show-toplevel)"
  REPO_NAME="$(basename "$ROOT_DIR")"
else
  ROOT_DIR="$(pwd)"
  REPO_NAME="local"
fi

# Deterministic per-repo project ID
PROJECT_ID="$(echo -n "$ROOT_DIR" | shasum -a 256 | cut -c1-12)"

DATA_DIR="$HOME/docker-agent-data/$REPO_NAME/$PROJECT_ID"

# Ensure host paths exist
mkdir -p "$DATA_DIR/.codex"
mkdir -p "$DATA_DIR/.claude"

# Copy Codex auth if enabled and missing
if [ "$COPY_CODEX_CREDS" = "true" ] && [ ! -f "$DATA_DIR/.codex/auth.json" ]; then
  if [ -f "$HOME/.codex/auth.json" ]; then
    if cp "$HOME/.codex/auth.json" "$DATA_DIR/.codex/auth.json" 2>/dev/null; then
      echo "[codex] Copied auth.json"
    else
      echo "[codex] Failed to copy auth.json" >&2
    fi
  else
    echo "[codex] auth.json not found at ~/.codex/auth.json" >&2
  fi
fi

# Copy Claude credentials if enabled and missing
if [ "$COPY_CLAUDE_CREDS" = "true" ] && [ ! -f "$DATA_DIR/.claude/.credentials.json" ]; then
  if [ -f "$HOME/.claude/.credentials.json" ]; then
    if cp "$HOME/.claude/.credentials.json" "$DATA_DIR/.claude/.credentials.json" 2>/dev/null; then
      echo "[claude] Copied credentials"
    else
      echo "[claude] Failed to copy credentials" >&2
    fi
  else
    echo "[claude] credentials not found at ~/.claude/.credentials.json" >&2
  fi
fi

# Ensure valid JSON config file
CLAUDE_JSON="$DATA_DIR/.claude.json"
if [ ! -f "$CLAUDE_JSON" ]; then
  echo '{}' > "$CLAUDE_JSON"
fi

# Check if network monitor is already running
if pgrep -f "network-monitor.py" > /dev/null; then
  echo "✓ Network monitor already running"
else
  echo "Starting network monitor proxy on port 8080..."
  echo "Run './docker/manage-firewall.sh' in another terminal to manage rules"
  echo ""

  # Start the proxy in the background
  uv run "$SCRIPT_DIR/network-monitor.py" > /tmp/network-monitor.log 2>&1 &
  PROXY_PID=$!

  # Wait for proxy to start
  sleep 2

  if ! ps -p $PROXY_PID > /dev/null; then
    echo "ERROR: Network monitor failed to start. Check /tmp/network-monitor.log" >&2
    exit 1
  fi

  echo "✓ Network monitor started (PID: $PROXY_PID)"
  echo ""

  # Create cleanup function
  cleanup() {
    echo ""
    echo "Stopping network monitor..."
    kill $PROXY_PID 2>/dev/null || true
    wait $PROXY_PID 2>/dev/null || true
    echo "✓ Cleanup complete"
  }

  trap cleanup EXIT INT TERM
fi

# Determine host IP for Docker to reach host
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS: use special DNS name
  HOST_IP="host.docker.internal"
else
  # Linux: get actual host IP
  HOST_IP=$(ip -4 addr show docker0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "172.17.0.1")
fi

PROXY_URL="http://${HOST_IP}:8080"

echo "=========================================="
echo "Network Monitoring Enabled"
echo "=========================================="
echo "Proxy URL: $PROXY_URL"
echo "All HTTP/HTTPS traffic will be monitored"
echo "You'll be prompted to allow/deny each domain"
echo "=========================================="
echo ""

# Run Docker with proxy configuration
docker run --rm -it \
  --add-host=host.docker.internal:host-gateway \
  -e OPENAI_API_KEY \
  -e GEMINI_API_KEY \
  -e HTTP_PROXY="$PROXY_URL" \
  -e HTTPS_PROXY="$PROXY_URL" \
  -e http_proxy="$PROXY_URL" \
  -e https_proxy="$PROXY_URL" \
  -e NO_PROXY="localhost,127.0.0.1" \
  -e no_proxy="localhost,127.0.0.1" \
  -v "$ROOT_DIR":/home/dev/workspace \
  -v "$DATA_DIR/.codex":/home/dev/.codex \
  -v "$DATA_DIR/.claude":/home/dev/.claude \
  -v "$CLAUDE_JSON":/home/dev/.claude.json \
  claude-dev-agents

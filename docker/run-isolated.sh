#!/usr/bin/env bash
set -euo pipefail

#
# Run Docker container with project-isolated configs
#
# Features:
# - Isolated config directories per project
# - Optional network monitoring and firewall (enabled by default)
# - Credential copying from host
#
# Environment Variables:
#   COPY_CODEX_CREDS=true|false    - Copy Codex credentials (default: true)
#   COPY_CLAUDE_CREDS=true|false   - Copy Claude credentials (default: false)
#   ENABLE_MONITORING=true|false   - Enable network monitoring (default: true)
#
# Examples:
#   ./docker/run-isolated.sh                           # Default: monitoring ON
#   ENABLE_MONITORING=false ./docker/run-isolated.sh   # Monitoring OFF
#

# Defaults
COPY_CODEX_CREDS="${COPY_CODEX_CREDS:-true}"
COPY_CLAUDE_CREDS="${COPY_CLAUDE_CREDS:-false}"
ENABLE_MONITORING="${ENABLE_MONITORING:-true}"

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

# Copy Codex auth if enabled
if [ "$COPY_CODEX_CREDS" = "true" ]; then
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

# Copy Claude credentials if enabled
if [ "$COPY_CLAUDE_CREDS" = "true" ]; then
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

# Network monitoring setup (if enabled)
PROXY_ALREADY_RUNNING=false
WEB_UI_ALREADY_RUNNING=false
PROXY_PID=""
WEB_UI_PID=""

if [ "$ENABLE_MONITORING" = "true" ]; then
  # Check if network monitor is already running
  if pgrep -f "network-monitor.py" > /dev/null; then
    echo "✓ Network monitor already running"
    PROXY_ALREADY_RUNNING=true
  fi

  if pgrep -f "web-ui.py" > /dev/null; then
    echo "✓ Web UI already running"
    WEB_UI_ALREADY_RUNNING=true
  fi

  # Start proxy if not running
  if [ "$PROXY_ALREADY_RUNNING" = false ]; then
    echo "Starting network monitor proxy on port 8080..."

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
  fi

  # Start web UI if not running
  if [ "$WEB_UI_ALREADY_RUNNING" = false ]; then
    echo "Starting web UI on port 8081..."

    # Start the web UI in the background
    cd "$SCRIPT_DIR" && uv run "$SCRIPT_DIR/web-ui.py" > /tmp/web-ui.log 2>&1 &
    WEB_UI_PID=$!

    # Wait for web UI to start
    sleep 2

    if ! ps -p $WEB_UI_PID > /dev/null; then
      echo "WARNING: Web UI failed to start. Check /tmp/web-ui.log" >&2
      echo "Continuing without web UI..."
    else
      echo "✓ Web UI started (PID: $WEB_UI_PID)"
      echo "✓ Web UI available at: http://localhost:8081"
    fi
  fi

  echo ""

  # Create cleanup function for monitoring services
  if [ "$PROXY_ALREADY_RUNNING" = false ] || [ "$WEB_UI_ALREADY_RUNNING" = false ]; then
    cleanup() {
      echo ""
      echo "Stopping services..."
      if [ "$PROXY_ALREADY_RUNNING" = false ] && [ -n "${PROXY_PID:-}" ]; then
        kill $PROXY_PID 2>/dev/null || true
        wait $PROXY_PID 2>/dev/null || true
      fi
      if [ "$WEB_UI_ALREADY_RUNNING" = false ] && [ -n "${WEB_UI_PID:-}" ]; then
        kill $WEB_UI_PID 2>/dev/null || true
        wait $WEB_UI_PID 2>/dev/null || true
      fi
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
  echo ""
  echo "Web UI: http://localhost:8081"
  echo "  - Real-time monitoring dashboard"
  echo "  - Manage firewall rules"
  echo "  - View statistics and logs"
  echo ""
  echo "CLI: ./docker/manage-firewall.sh"
  echo "  - Terminal-based management"
  echo ""
  echo "To disable monitoring:"
  echo "  ENABLE_MONITORING=false ./docker/run-isolated.sh"
  echo "=========================================="
  echo ""
else
  echo "=========================================="
  echo "Network Monitoring Disabled"
  echo "=========================================="
  echo "Container will have unrestricted network access"
  echo ""
  echo "To enable monitoring:"
  echo "  ENABLE_MONITORING=true ./docker/run-isolated.sh"
  echo "  (or omit ENABLE_MONITORING - it's on by default)"
  echo "=========================================="
  echo ""
fi

# Build docker run command based on monitoring setting
DOCKER_ARGS=(
  "--rm" "-it"
  "-e" "OPENAI_API_KEY"
  "-e" "GEMINI_API_KEY"
  "-v" "$ROOT_DIR:/home/dev/workspace"
  "-v" "$DATA_DIR/.codex:/home/dev/.codex"
  "-v" "$DATA_DIR/.claude:/home/dev/.claude"
  "-v" "$CLAUDE_JSON:/home/dev/.claude.json"
)

# Add monitoring-specific arguments if enabled
if [ "$ENABLE_MONITORING" = "true" ]; then
  DOCKER_ARGS+=(
    "--add-host=host.docker.internal:host-gateway"
    "-e" "HTTP_PROXY=$PROXY_URL"
    "-e" "HTTPS_PROXY=$PROXY_URL"
    "-e" "http_proxy=$PROXY_URL"
    "-e" "https_proxy=$PROXY_URL"
    "-e" "NO_PROXY=localhost,127.0.0.1"
    "-e" "no_proxy=localhost,127.0.0.1"
  )
fi

# Run Docker container
docker run "${DOCKER_ARGS[@]}" claude-dev-agents

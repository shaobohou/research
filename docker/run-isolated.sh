#!/usr/bin/env bash
set -euo pipefail

# Defaults: copy Codex auth, skip Claude creds, Tailscale disabled unless auth key provided
COPY_CODEX_CREDS="${COPY_CODEX_CREDS:-true}"
COPY_CLAUDE_CREDS="${COPY_CLAUDE_CREDS:-false}"
ENABLE_TAILSCALE="${ENABLE_TAILSCALE:-auto}"  # "auto", "true", or "false"

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

# Auto-detect Tailscale requirement: enable if auth key is set or explicitly enabled
if [ "$ENABLE_TAILSCALE" = "auto" ]; then
  if [ -n "${TAILSCALE_AUTH_KEY:-}" ]; then
    ENABLE_TAILSCALE="true"
  else
    ENABLE_TAILSCALE="false"
  fi
fi

# Ensure host paths exist
mkdir -p "$DATA_DIR/.codex"
mkdir -p "$DATA_DIR/.claude"
if [ "$ENABLE_TAILSCALE" = "true" ]; then
  mkdir -p "$DATA_DIR/tailscale"
fi

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

# Build docker run command with conditional Tailscale flags
DOCKER_ARGS=(
  --rm -it
  -e OPENAI_API_KEY
  -e GEMINI_API_KEY
  -v "$ROOT_DIR":/home/dev/workspace
  -v "$DATA_DIR/.codex":/home/dev/.codex
  -v "$DATA_DIR/.claude":/home/dev/.claude
  -v "$CLAUDE_JSON":/home/dev/.claude.json
)

# Add Tailscale capabilities only if enabled
if [ "$ENABLE_TAILSCALE" = "true" ]; then
  DOCKER_ARGS+=(
    --cap-add=NET_ADMIN
    --cap-add=NET_RAW
    --device=/dev/net/tun
    -e TAILSCALE_AUTH_KEY
    -e TAILSCALE_HOSTNAME
    -v "$DATA_DIR/tailscale":/var/lib/tailscale
  )
  echo "[tailscale] Enabled with required capabilities"
fi

docker run "${DOCKER_ARGS[@]}" claude-dev-agents

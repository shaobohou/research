#!/usr/bin/env bash
set -euo pipefail

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

# Copy Codex auth into the isolated config so login isn't required in-container
if [ ! -f "$DATA_DIR/.codex/auth.json" ] && [ -f "$HOME/.codex/auth.json" ]; then
  if ! cp "$HOME/.codex/auth.json" "$DATA_DIR/.codex/auth.json"; then
    echo "[codex] Failed to copy auth.json from $HOME/.codex/auth.json" >&2
  fi
elif [ ! -f "$DATA_DIR/.codex/auth.json" ]; then
  echo "[codex] auth.json not found at $HOME/.codex/auth.json; run 'codex login' locally to reuse it in Docker" >&2
fi

# Copy Claude credentials if not already present in the isolated config
if [ ! -f "$DATA_DIR/.claude/.credentials.json" ] && [ -f "$HOME/.claude/.credentials.json" ]; then
  if ! cp "$HOME/.claude/.credentials.json" "$DATA_DIR/.claude/.credentials.json"; then
    echo "[claude] Failed to copy .credentials.json from $HOME/.claude/.credentials.json" >&2
  fi
elif [ ! -f "$DATA_DIR/.claude/.credentials.json" ]; then
  echo "[claude] .credentials.json not found at $HOME/.claude/.credentials.json; run 'claude login' locally to reuse it in Docker" >&2
fi

# Ensure valid JSON config file
CLAUDE_JSON="$DATA_DIR/.claude.json"
if [ ! -f "$CLAUDE_JSON" ]; then
  echo '{}' > "$CLAUDE_JSON"
fi

docker run --rm -it \
  -e OPENAI_API_KEY \
  -v "$ROOT_DIR":/home/dev/workspace \
  -v "$DATA_DIR/.codex":/home/dev/.codex \
  -v "$DATA_DIR/.claude":/home/dev/.claude \
  -v "$CLAUDE_JSON":/home/dev/.claude.json \
  claude-dev-agents

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(pwd)"

# Deterministic per-path project ID
PROJECT_ID="$(echo -n "$ROOT_DIR" | shasum -a 256 | cut -c1-12)"

DATA_DIR="$HOME/.docker-agent-data/$PROJECT_ID"

# Ensure host paths exist
mkdir -p "$DATA_DIR/.codex"
mkdir -p "$DATA_DIR/.claude"

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

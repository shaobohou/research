#!/usr/bin/env bash
set -euo pipefail

uv tool install ruff

npm install -g \
  @anthropic-ai/claude-code \
  @openai/codex \
  @google/gemini-cli \
  @github/copilot \
  eslint

# Research Codespaces

Minimal development environment for AI-assisted research and experimentation.

## Setup

**Environment**: Python 3.12, Node.js, uv package manager, GitHub CLI

**Dev Container**: `.devcontainer/` auto-installs Claude Code, Gemini, and Codex CLIs via uv post-create script

**CI**: `.github/workflows/ci.yml` runs linting and pytest on Python code changes

## Workflow

See `AGENTS.md` for research investigation guidelines.

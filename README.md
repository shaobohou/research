# Research Codespaces

Minimal development environment for AI-assisted research and experimentation.

## Setup

**Environment**: Python 3.12, Node.js, uv package manager, GitHub CLI

**Dev Container**: `.devcontainer/` configures VS Code with Python 3.12, uv, GitHub CLI, and AI assistant CLIs (Claude Code, Codex, Gemini). Auto-installs dependencies via post-create script.

**Docker**: `docker/` provides lightweight standalone container with AI CLIs. Built on Debian Bookworm with smart entrypoint for auto-installation and updates. See [docker/README.md](docker/README.md) for details.

**CI**: `.github/workflows/ci.yml` runs linting and pytest on Python code changes

## Quick Start

**Dev Container (VS Code)**: Open in VS Code → `F1` → "Dev Containers: Reopen in Container"

**Docker (Standalone)**:
```bash
cd docker && docker build -t claude-dev-agents .
docker run --rm -it -v "$PWD":/home/dev/workspace claude-dev-agents
```

## Workflow

See [AGENTS.md](AGENTS.md) for research investigation guidelines.

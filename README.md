# Research Codespaces

Minimal development environment for AI-assisted research and experimentation.

## Setup

**Environment**: Python 3.12, Node.js, uv package manager, GitHub CLI

**Dev Container**: `.devcontainer/` configures VS Code with Python 3.12, uv, GitHub CLI, and AI assistant CLIs (Claude Code, Codex, Gemini). Auto-installs dependencies via post-create script.

**Docker**: `docker/` provides lightweight standalone container with AI CLIs. Built on Debian Bookworm with smart entrypoint for auto-installation and updates. See [docker/README.md](docker/README.md) for details.

**CI**: `.github/workflows/ci.yml` runs linting and pytest on Python code changes

## Quick Start

### Dev Container (VS Code / Codespaces)

Open in VS Code → `F1` → "Dev Containers: Reopen in Container"

**Codespaces Authentication**: When using Claude Code or Codex CLI in GitHub Codespaces, subscription login requires SSH port forwarding. In a local terminal:

```bash
# Find your codespace name
gh codespace list

# Create SSH tunnel for authentication (keep running during login)
gh codespace ssh -c <YOUR_CODESPACE_NAME> -- -N -L 1455:localhost:1455
```

This forwards port 1455 to your local machine, allowing authentication to complete in your local browser.

### Docker (Standalone)

Build the image (one-time setup):
```bash
cd docker && docker build -t claude-dev-agents .
```

Run with workspace mounted:
```bash
docker run --rm -it -v "$PWD":/home/dev/workspace claude-dev-agents
```

Run with config mounting for AI CLIs:
```bash
docker run --rm -it \
  -e OPENAI_API_KEY \
  -e GOOGLE_API_KEY \
  -v "$PWD":/home/dev/workspace \
  -v "$HOME/.codex":/home/dev/.codex \
  -v "$HOME/.claude":/home/dev/.claude \
  -v "$HOME/.claude.json":/home/dev/.claude.json \
  claude-dev-agents
```

Or use the helper script for project-isolated configs:
```bash
./docker/run-isolated.sh                             # Default: copy Codex, skip Claude
COPY_CODEX_CREDS=false ./docker/run-isolated.sh      # Don't copy Codex
COPY_CLAUDE_CREDS=true ./docker/run-isolated.sh      # Copy Claude credentials
```

**Security Note**: Mounting config directories and passing API keys gives the container access to sensitive credentials. Only use with trusted code. For untrusted workloads, use read-only mounts (`:ro`) and avoid mounting configs. See [docker/README.md](docker/README.md) for details.

## Workflow

See [AGENTS.md](AGENTS.md) for research investigation guidelines.

# Docker Development Environment

Lightweight Docker container with AI assistant CLIs (Claude Code, Codex, Gemini) and uv Python package manager.

## Features

- **Base**: `debian:bookworm-slim`
- **User**: Non-root `dev` user with passwordless sudo
- **Tools**: Claude Code, uv, Codex CLI, Gemini CLI, Git, Node.js
- **Smart entrypoint**: Auto-installs/updates tools on startup with error handling

## Usage

```bash
# Build image
docker build -t claude-dev-agents .

# Run interactively with workspace mounted
docker run --rm -it -v "$PWD":/home/dev/workspace claude-dev-agents

# Run specific command
docker run --rm -it claude-dev-agents claude --version
```

## Python Development with uv

```bash
# Create new project
uv init my-project && cd my-project

# Add dependencies
uv add requests pandas
uv add --dev pytest ruff

# Run code
uv run main.py
uv run -m pytest
```

## Advanced Usage

```bash
# Persist tool configs
docker run --rm -it \
  -v "$PWD":/home/dev/workspace \
  -v claude-config:/home/dev/.claude \
  claude-dev-agents

# CI/CD usage
docker run --rm -v "$PWD":/home/dev/workspace claude-dev-agents \
  bash -c "cd workspace && uv run pytest"
```

## Details

**Environment**:
- Base: `debian:bookworm-slim`, user: `dev`, home: `/home/dev`
- PATH includes: `~/.local/bin`, `~/.claude/bin`, `~/.npm-global/bin`
- Tools installed via entrypoint on first run

**Entrypoint**: Auto-installs/updates tools, reports versions, handles failures gracefully

**Docker vs Dev Container**:
- Docker: Standalone, CI/CD, command-line workflows
- Dev Container: VS Code integration, GitHub Codespaces, pre-configured extensions

## License

MIT

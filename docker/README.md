# Docker Development Environment

Lightweight Docker container with AI assistant CLIs (Claude Code, Codex, Gemini) and uv Python package manager.

## Features

- **Base**: `debian:bookworm-slim`
- **User**: Non-root `dev` user with passwordless sudo
- **Tools**: Claude Code, uv, Codex CLI, Gemini CLI, Git, GitHub CLI, Node.js
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

## API Keys

AI tools require API keys. Pass them from your host environment:

```bash
export OPENAI_API_KEY="sk-..."

docker run --rm -it \
  -e OPENAI_API_KEY \
  -v "$PWD":/home/dev/workspace \
  claude-dev-agents
```

**Note:** Using `-e VAR_NAME` (without `=value`) keeps the key out of command history. For multiple keys, add more `-e` flags.

To let Codex CLI commands inherit these variables inside the container, add the following to your Codex config (for example `~/.codex/config.toml`):

```toml
[shell_environment_policy]
inherit = "all"            # pass all env vars to subprocesses
ignore_default_excludes = true
```

Then mount your Codex/Claude configs so both tools can use the environment settings:

```bash
docker run --rm -it \
  -e OPENAI_API_KEY \
  -v "$PWD":/home/dev/workspace \
  -v "$HOME/.codex":/home/dev/.codex \
  -v "$HOME/.claude":/home/dev/.claude \
  -v "$HOME/.claude.json":/home/dev/.claude.json \
  claude-dev-agents
```

## Helper Script with Isolated Directories

The `run.sh` helper script simplifies launching containers with project-isolated configuration directories. This prevents different projects from sharing AI CLI state:

```bash
# From any project directory
./docker/run.sh
```

**What it does:**
- Creates a unique project ID based on your current directory path
- Stores Claude/Codex configs in `~/.docker-agent-data/<project-id>/`
- Auto-creates required directories and config files
- Mounts workspace and isolated configs into the container
- Passes through `OPENAI_API_KEY` from your environment

**Benefits:**
- Each project gets its own AI CLI configuration and history
- No conflicts between different projects' CLI state
- Clean separation of concerns for multi-project workflows

Example directory structure created:
```
~/.docker-agent-data/
├── a1b2c3d4e5f6/  # project at /home/user/project-a
│   ├── .claude/
│   ├── .codex/
│   └── .claude.json
└── f6e5d4c3b2a1/  # project at /home/user/project-b
    ├── .claude/
    ├── .codex/
    └── .claude.json
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

## Volume Mounts

The `-v "$PWD":/home/dev/workspace` flag makes your current directory accessible at `/home/dev/workspace` inside the container. Files sync bidirectionally.

**Read-only mounts** prevent the container from modifying your files:

```bash
# Add :ro for read-only access
docker run --rm -it \
  -v "$PWD":/home/dev/workspace:ro \
  claude-dev-agents
```

Use read-only mounts when running untrusted code or when files shouldn't be modified (linting, testing, analysis).

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

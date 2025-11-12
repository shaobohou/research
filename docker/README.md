# Minimal AI Development Container

Lightweight Docker environment with Claude Code, uv, Codex, and Gemini CLIs.

**Included:**
- Claude Code (Anthropic)
- uv (Python package manager)
- Codex CLI (OpenAI)
- Gemini CLI (Google)
- Non-root `dev` user with passwordless sudo

## Quickstart

```bash
# Build the image
docker build -t claude-dev-agents .

# Run interactively (installs/updates tools and opens bash)
docker run --rm -it -v "$PWD":/home/dev/workspace claude-dev-agents
```

Inside the container:

```bash
claude --version
uv --version
codex --version
gemini --version
```

Or run a specific tool directly:

```bash
docker run --rm -it claude-dev-agents claude
docker run --rm -it claude-dev-agents codex --help
docker run --rm -it claude-dev-agents gemini --help
```

## Python Development with uv

```bash
# Create a new Python project
uv init my-project
cd my-project

# (Optional) Install or select Python version
uv python install 3.12

# Add dependencies
uv add requests jax

# Run code directly in the project environment
uv run main.py
```

## Environment Details

| Component | Details |
|------------|----------|
| **Base image** | `debian:bookworm-slim` |
| **User** | `dev` (non-root, passwordless sudo) |
| **Included tools** | Claude Code, uv, Codex CLI, Gemini CLI |
| **Node/npm** | Installed for Codex & Gemini CLIs |
| **TLS** | `ca-certificates` preinstalled |
| **PATH** | `~/.local/bin`, `~/.claude/bin`, `~/.npm-global/bin` |

## License

MIT

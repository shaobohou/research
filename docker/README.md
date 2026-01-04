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
export GEMINI_API_KEY="..."

docker run --rm -it \
  -e OPENAI_API_KEY \
  -e GEMINI_API_KEY \
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
  -e GEMINI_API_KEY \
  -v "$PWD":/home/dev/workspace \
  -v "$HOME/.codex":/home/dev/.codex \
  -v "$HOME/.claude":/home/dev/.claude \
  -v "$HOME/.claude.json":/home/dev/.claude.json \
  claude-dev-agents
```

## Helper Scripts

### Simple Usage: `run-isolated.sh`

For quick, simple container launches with isolated configs:

```bash
./docker/run-isolated.sh
```

**Features**:
- Isolated config directories per project (`~/docker-agent-data/<repo>/<project-id>/`)
- Each project gets separate `.claude/`, `.codex/`, and `.claude.json` files
- Fast startup with no monitoring overhead
- Automatic credential copying from host

**Environment Variables**:
- `COPY_CODEX_CREDS` - Copy Codex credentials (default: `true`)
- `COPY_CLAUDE_CREDS` - Copy Claude credentials (default: `false`)

**Examples**:
```bash
# Default: copy Codex creds
./docker/run-isolated.sh

# Copy Claude creds too
COPY_CLAUDE_CREDS=true ./docker/run-isolated.sh
```

### Network Monitoring: `run-monitored.sh`

For development with network monitoring and firewall:

```bash
./docker/run-monitored.sh
```

**Features**:
- All features from `run-isolated.sh` PLUS:
- 🔒 **Network monitoring and firewall** with mitmproxy
  - **DEFAULT DENY security model**: All requests denied unless explicitly allowed
  - Real-time HTTP/HTTPS request monitoring
  - Web dashboard at http://localhost:8081 with live updates
  - Pending approval queue for unknown requests
  - Multiple permission levels (allow-domain, deny-domain, allow-url, deny-url)
  - Persistent rules and complete access logging
  - REST API for programmatic access
  - Default allow-list for common services (GitHub, npm, etc.)

**Options**:
- `--no-monitoring` - Disable network monitoring (bypass monitoring overhead)
- `--help` - Show usage information

**Examples**:
```bash
# Default: monitoring ON
./docker/run-monitored.sh

# Open browser to http://localhost:8081
# - Real-time activity feed
# - Statistics dashboard
# - Rule management interface

# Or use CLI: ./docker/monitoring/manage-firewall.sh
```

See [monitoring/NETWORK_MONITORING.md](monitoring/NETWORK_MONITORING.md) for complete documentation on:
- How the network monitoring works
- Using the web dashboard and REST API
- Permission levels and rule management
- Pre-configuring trusted domains
- Viewing statistics and logs
- Security considerations

#### Security Limitations

**Important**: The network monitoring is **cooperative, not enforced**.

- ✅ **Provides visibility**: All HTTP/HTTPS traffic via standard libraries is logged
- ✅ **Interactive control**: Approve/deny requests via web UI
- ✅ **Good for development**: Audit network behavior of AI tools and scripts
- ⚠️ **Can be bypassed**: Malicious code can ignore `HTTP_PROXY` environment variables
- ⚠️ **Not enforcement**: Code can make raw socket connections that bypass the proxy

**Why this limitation exists**: Docker Desktop on macOS runs containers in a managed Linux VM that doesn't expose network enforcement tools (like iptables). True kernel-level enforcement would require:
- Native Linux host (not macOS/Windows)
- iptables or nftables configuration
- Root/sudo access

**Recommendation**: Use network monitoring for:
- ✅ Development and debugging
- ✅ Auditing trusted code with unknown network behavior
- ✅ Understanding what AI tools are accessing
- ✅ Creating allow-lists for known-good services

**Not suitable for**:
- ❌ Running untrusted/malicious code
- ❌ Security enforcement against adversarial actors
- ❌ Preventing determined bypass attempts

For true network isolation, use a Linux host or VM where iptables-based enforcement can be implemented.

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

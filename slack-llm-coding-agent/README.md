# Slack LLM Coding Agent

A simple LLM-powered Slack bot that acts as a coding agent. Built with [pi-mono](https://github.com/badlogic/pi-mono)'s `@mariozechner/pi-ai` unified LLM API and Slack's Bolt framework.

## What it does

When you @mention the bot in a Slack channel (or DM it directly), it uses an LLM to understand your request and can:

- **Read files** from a workspace directory
- **Write files** (creating directories as needed)
- **Edit files** with find-and-replace
- **Run shell commands** (tests, git, builds, etc.)

The agent runs in a tool-calling loop — the LLM decides which tools to invoke, executes them, reads the results, and continues until it has a final answer.

## Architecture

```
Slack (Socket Mode)
  └─> Bolt event handler
        └─> Agent loop (agent.ts)
              ├─> pi-ai complete() → LLM response
              ├─> Tool execution (read/write/edit/bash)
              └─> Loop until final text response
```

### Key files

| File | Purpose |
|------|---------|
| `src/index.ts` | Slack bot entry point (Bolt + Socket Mode) |
| `src/agent.ts` | Agent loop: LLM calls + tool execution |
| `src/tools.ts` | Tool definitions (TypeBox schemas) and implementations |
| `src/config.ts` | Environment variable loading |

## Setup

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app
2. Enable **Socket Mode** (generates an `xapp-` app-level token)
3. Add **Bot Token Scopes**: `app_mentions:read`, `chat:write`, `im:history`, `im:read`, `im:write`
4. Subscribe to **Events**: `app_mention`, `message.im`
5. Install the app to your workspace (generates an `xoxb-` bot token)

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your tokens and API key
```

Required variables:

| Variable | Description |
|----------|-------------|
| `SLACK_BOT_TOKEN` | Bot User OAuth Token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | App-Level Token for Socket Mode (`xapp-...`) |
| `ANTHROPIC_API_KEY` | Anthropic API key (or the key for your chosen provider) |

Optional variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `anthropic` | Any pi-ai provider: `openai`, `google`, `xai`, `groq`, etc. |
| `LLM_MODEL` | `claude-sonnet-4-20250514` | Model ID for the chosen provider |
| `WORKSPACE_DIR` | Current directory | Working directory for file/bash tools |

### 3. Install and run

```bash
npm install
npm run build
npm start
```

For development with auto-rebuild:

```bash
npm run dev        # watches for changes
node dist/index.js # in another terminal
```

## Supported LLM Providers

Via `@mariozechner/pi-ai`, you can use any of these providers by setting `LLM_PROVIDER` and the corresponding API key:

- **Anthropic** (`anthropic`) — Claude models
- **OpenAI** (`openai`) — GPT-4o, o1, etc.
- **Google** (`google`) — Gemini models
- **xAI** (`xai`) — Grok models
- **Groq** (`groq`) — Fast inference
- **Cerebras** (`cerebras`) — Fast inference
- **OpenRouter** (`openrouter`) — Multi-provider routing
- **Amazon Bedrock** (`amazon-bedrock`)
- **Azure OpenAI** (`azure-openai-responses`)

## How the agent loop works

1. User sends a message in Slack
2. The message (with a system prompt) is sent to the LLM via `pi-ai`'s `complete()` function
3. If the LLM responds with tool calls, each tool is executed and results are appended to the context
4. Steps 2-3 repeat until the LLM responds with plain text (max 25 rounds)
5. The final text is posted back to Slack

## Limitations

- One request per channel at a time (queued, not concurrent)
- Shell commands have a 60-second timeout
- File operations are unrestricted within the workspace directory
- No persistent conversation history across restarts

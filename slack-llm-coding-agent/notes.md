# Slack LLM Coding Agent — Development Notes

## 2026-02-15: Initial Implementation

### Research

- Investigated [pi-mono](https://github.com/badlogic/pi-mono) by Mario Zechner — a monorepo AI agent toolkit with seven packages
- Key package for this project: `@mariozechner/pi-ai` — unified multi-provider LLM API
- pi-mono also includes `pi-mom` (a full Slack bot) and `pi-agent-core` (agent runtime), but we used just `pi-ai` to keep things simple
- pi-ai provides `stream()` and `complete()` functions, TypeBox-based tool schemas, and `validateToolCall()` for argument validation

### Design decisions

- **Used `pi-ai` directly** instead of `pi-agent-core` to keep the agent loop transparent and easy to understand
- **Used `@slack/bolt`** (Socket Mode) for Slack integration — simpler than raw `@slack/socket-mode` + `@slack/web-api`
- **Four tools**: read_file, write_file, edit_file, bash — same core set as pi's coding agent
- **Agent loop**: simple `complete()` in a loop with max 25 rounds, no streaming (keeps code minimal)
- **Per-channel locking**: prevents overlapping agent runs in the same channel

### What worked

- pi-ai's `complete()` + `validateToolCall()` pattern is straightforward for building an agent loop
- TypeBox schemas for tool parameters integrate cleanly with the pi-ai type system
- Bolt's Socket Mode requires minimal setup (no public URL/webhook needed)

### What to explore next

- Add streaming responses (use `stream()` + update Slack messages incrementally)
- Add conversation persistence (save/load context per channel like pi-mom's log.jsonl)
- Add Docker sandbox for bash commands (security isolation)
- Use `pi-agent-core` for more sophisticated state management and auto-compaction
- Add file upload support (Slack attachments → agent context)

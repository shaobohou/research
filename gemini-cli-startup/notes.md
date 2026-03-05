# Gemini CLI Startup Investigation

## Setup
- Gemini CLI v0.32.1, Node.js v22.22.0 (installed via `npm install -g @google/gemini-cli`)
- Environment: Linux 4.4.0, no TTY (headless), no GEMINI_API_KEY configured

## Findings

### Problem 1: CLI hangs without TTY
Running `gemini -p "hello" < /dev/null` never exits (>30 second hang). Root cause:
1. Without a TTY, `main()` detects non-interactive mode and calls `validateNonInteractiveAuth`
2. With no auth configured, it calls `runExitCleanup()` before `process.exit()`
3. `runExitCleanup()` tries to flush OpenTelemetry SDK and telemetry buffers, which may block
4. Additionally, `relaunchAppInChildProcess()` always spawns a second Node.js process

### Problem 2: Massive cold-start overhead (~16 seconds)
Measured by timing `import('/path/to/gemini.js')`:

| Phase | Time |
|-------|------|
| Node.js startup | ~48ms |
| `@opentelemetry/api` | +150ms |
| `@opentelemetry/sdk-node` | **+3,900ms** ← biggest single hit |
| `gcp-exporters` (Google Cloud libs) | +2,900ms |
| `clearcut-logger` | +700ms |
| Rest of `telemetry/sdk.js` | +1,400ms |
| `config/config.js` (extensions, memory loading) | +4,800ms |
| **TOTAL imports** | **~16,000ms** |

### Root cause: Static OpenTelemetry imports
`telemetry/sdk.js` does static (top-level) imports of:
- `@opentelemetry/sdk-node` (~4s) — loads all auto-instrumentation
- `./gcp-exporters.js` (~3s) — loads Google Cloud Trace/Metrics/Logging SDKs
- `./clearcut-logger/clearcut-logger.js` (~700ms)

These are unconditional static imports — they load regardless of whether telemetry is enabled (`GEMINI_TELEMETRY_DISABLED`, etc.).

### Process architecture adds cost
`relaunchAppInChildProcess()` always spawns a child process (except when `GEMINI_CLI_NO_RELAUNCH=true`), doubling CPU usage. Both processes pay the 16s import cost.

## What was tried
- `gemini -p "hello" < /dev/null` — hangs
- `echo "" | gemini -p "hello"` — hangs
- `GEMINI_CLI_NO_RELAUNCH=true gemini -p "hello" < /dev/null` — still hangs
- `GEMINI_API_KEY=fake gemini -p "hello" < /dev/null` — still hangs
- Profiling with `node --input-type=module` import timing scripts — works

## Conclusion
In v0.32.1, there is no way to speed up cold start — the ~16s import time is hard-coded into the module structure. The fastest non-interactive invocation is still `-p "prompt"` but first response takes at minimum:

```
~16s (module imports) + network RTT to Gemini API
```

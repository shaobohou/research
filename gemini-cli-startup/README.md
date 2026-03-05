# Gemini CLI Startup Performance

**Gemini CLI v0.32.1 — cold start takes ~16 seconds before the first API call.**

## TL;DR

The fastest way to invoke Gemini CLI non-interactively is:

```bash
gemini -p "Your prompt here" -m gemini-2.5-flash
```

But the cold start overhead is ~16 seconds regardless of flags, due to static OpenTelemetry imports.

## Measured Startup Breakdown

Benchmarked on Node.js v22.22.0 (Linux), 5 runs each:

| Component | Mean | Min |
|-----------|------|-----|
| Node.js process start | 48ms | 47ms |
| `@opentelemetry/api` import | 150ms | 146ms |
| **`@opentelemetry/sdk-node` import** | **4,047ms** | **3,874ms** |
| `gcp-exporters` (Google Cloud SDKs) | 2,892ms | 2,817ms |
| `clearcut-logger` | 724ms | 709ms |
| All other telemetry sub-modules | ~1,400ms | — |
| `config/config.js` (extensions, memory scan) | ~4,800ms | — |
| **Total `gemini.js` import** | **15,828ms** | **15,743ms** |

## Why It's Slow

`telemetry/sdk.js` uses **static top-level imports** of:

```js
import { NodeSDK } from '@opentelemetry/sdk-node';          // ~4s
import { GcpTraceExporter, ... } from './gcp-exporters.js'; // ~3s
import { ClearcutLogger } from './clearcut-logger/...';     // ~700ms
```

These load **unconditionally** — even if telemetry is disabled — because they are static imports, not dynamic `import()`. The Node.js module system evaluates them at startup.

Additionally, every invocation spawns a **child process** (`relaunchAppInChildProcess`), so both parent and child pay the 16s cost simultaneously.

## Flags Reference

| Flag | Effect |
|------|--------|
| `-p "prompt"` | Non-interactive mode (fastest invocation style) |
| `-m gemini-2.5-flash` | Faster/cheaper model |
| `--output-format json` | Machine-readable output, skips TTY rendering |
| `GEMINI_CLI_NO_RELAUNCH=true` | Skip child process relaunch (saves one process spawn, not import time) |

## Workarounds

1. **Keep a warm session open** — the interactive REPL avoids cold start on follow-up prompts
2. **Use the Gemini API directly** — `curl` or an SDK bypasses the CLI entirely
3. **Wait for upstream fix** — the correct fix is to make the OTel imports dynamic/lazy

## Files

- `benchmark.py` — measures import times for each module (run with `uv run benchmark.py`)
- `profile_imports.mjs` — times individual module imports
- `profile_core.mjs` — drills into `gemini-cli-core` sub-modules
- `profile_otel.mjs` — pinpoints which OpenTelemetry package is slowest
- `notes.md` — investigation log

# fastmcp generate-cli — minimal reimplementation

A single-file reimplementation of [`fastmcp generate-cli`](https://gofastmcp.com/clients/generate-cli) using only the official [`mcp`](https://pypi.org/project/mcp/) Python SDK — no `fastmcp`, no `cyclopts`, no `rich`.

## What it does

Connects to any MCP server, reads its tool schemas, and writes a standalone Python CLI script where each tool becomes an `argparse` subcommand with typed flags and help text. Also generates a `SKILL.md` for Claude Code agent integration.

## Files

| File | Purpose |
|------|---------|
| `generate_cli.py` | The generator (run this) |
| `example_server.py` | Demo MCP server with 4 tools for testing |
| `test_cli.py` | Generated example output (committed for reference) |
| `SKILL.md` | Generated SKILL.md for the example server |

## Usage

```bash
# Generate a CLI from a stdio server (python script)
uv run generate_cli.py "python my_server.py" cli.py

# Generate from a URL (HTTP/SSE transport)
uv run generate_cli.py http://localhost:8000/mcp cli.py

# Overwrite existing output
uv run generate_cli.py "python my_server.py" cli.py -f

# Skip SKILL.md generation
uv run generate_cli.py "python my_server.py" cli.py --no-skill
```

The generated `cli.py` is itself runnable with `uv run`:

```bash
uv run cli.py --help
uv run cli.py list-tools
uv run cli.py <tool-name> --arg1 val1 --arg2 val2
uv run cli.py call-tool <tool-name> key=value ...   # generic form
```

## Dependencies

**Generator** (`generate_cli.py`): `mcp>=1.0` — fetched automatically by `uv run`.

**Generated script** (`cli.py`): same — `mcp>=1.0` declared in uv inline metadata.

## Comparison with fastmcp generate-cli

| Feature | fastmcp | This impl |
|---------|---------|-----------|
| CLI framework | cyclopts | argparse (stdlib) |
| Console output | rich | print() |
| MCP client | fastmcp.Client | mcp.ClientSession |
| Type mapping | identical | identical |
| SKILL.md | ✓ | ✓ |
| URL transport | ✓ | ✓ (streamable HTTP or SSE) |
| Stdio transport | ✓ | ✓ |
| Array parameters | `list[T]` repeatable flags | `nargs='+'` |
| Complex params | JSON string | JSON string |

## How it works

1. **Schema → type**: JSON Schema types map to Python types (`string→str`, `integer→int`, `array[string]→list[str]`, complex objects → `str` accepting JSON).
2. **Code generation**: For each tool, `_tool_function_source()` emits:
   - `_setup_<tool>(sub)` — registers an argparse subparser with typed flags
   - `_handle_<tool>(args)` — filters `None` values, JSON-parses complex args, calls `session.call_tool()`
3. **Transport**: The generated script picks the right MCP transport at import time (streamable HTTP → SSE → stdio) and exposes a single `_get_session()` async context manager.

## Example session

```
$ uv run generate_cli.py "python example_server.py" cli.py
Connecting to python example_server.py …
Discovered 4 tool(s).
Wrote cli.py with 4 tool command(s).
Wrote SKILL.md.
Run: python cli.py --help

$ uv run cli.py add --a 3 --b 4
7.0

$ uv run cli.py greet --name World --loud --times 2
HELLO, WORLD!
HELLO, WORLD!

$ uv run cli.py join --words hello world foo --sep ,
hello,world,foo

$ uv run cli.py echo_json --payload '{"key":"value","num":42}'
{
  "key": "value",
  "num": 42
}
```

# Notes: Replicating fastmcp generate-cli with minimal deps

## Goal

Replicate `fastmcp generate-cli` using only the official `mcp` Python SDK — no `fastmcp`, no `cyclopts`, no `rich`.

## Research

Read the fastmcp source:
`https://github.com/jlowin/fastmcp/blob/main/src/fastmcp/cli/generate.py`

Key observations:
- Generator connects to MCP server, calls `list_tools()` → gets JSON Schema per tool
- Maps JSON Schema → Python type annotations → CLI arguments
- Uses `cyclopts` for generated CLI (not stdlib argparse)
- Uses `rich` for styled console output
- Uses `fastmcp.Client` for transport in the generated script

## Design decisions

| Concern | fastmcp | This impl |
|---------|---------|-----------|
| CLI framework in generated script | cyclopts | argparse (stdlib) |
| Console output | rich | print() |
| MCP client | fastmcp.Client | mcp.ClientSession directly |
| Transport | fastmcp transports | mcp.client.stdio / sse / streamable_http |
| Code generation deps | pydantic_core (JSON), cyclopts | none beyond mcp |

## Type mapping

Same logic as fastmcp:
- `string/integer/number/boolean` → Python scalar
- `array` of scalars → `list[T]`, rendered as `nargs='+'`
- complex (object, nested) → `str` that gets `json.loads()`-ed

## argparse vs cyclopts

cyclopts advantages (in fastmcp):
- `list[T]` natively handled
- `Annotated[T, Parameter(help=...)]` for rich metadata
- automatic camelCase→kebab-case flag naming

argparse approach here:
- `nargs='+'` for list types
- explicit `help=` on each `add_argument` call
- flag name = prop_name with non-alnum → `-`

## Bugs encountered

1. `_HEADER_TMPL.format(...)` — literal `{...}` in generated Python code (f-strings, dict comprehensions) conflicts with `.format()` named fields.
   Fix: use `.replace()` for each field instead.

2. `textwrap.dedent` + f-string interpolation of multiline `setup_body` — only the first line of an interpolated multiline string gets the surrounding indentation; remaining lines start at column 0.
   Fix: build tool function source line-by-line with explicit `L.append(f"    ...")`.

## Testing

```bash
# Run generator against stdio server
uv run generate_cli.py "python example_server.py" test_cli.py -f

# Exercise generated CLI
uv run test_cli.py list-tools
uv run test_cli.py add --a 3 --b 4          # → 7.0
uv run test_cli.py greet --name World --loud --times 2
uv run test_cli.py join --words hello world foo --sep ,
uv run test_cli.py echo_json --payload '{"k":1}'
```

All commands produced correct output.

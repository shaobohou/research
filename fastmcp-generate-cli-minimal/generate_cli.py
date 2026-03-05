#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.0"]
# ///
"""Minimal reimplementation of `fastmcp generate-cli`.

Reads tool schemas from an MCP server and writes a standalone Python CLI
script that can invoke them directly. Uses only the official `mcp` SDK
(no fastmcp, no cyclopts, no rich).

Usage:
    uv run generate_cli.py <server-spec> [output.py] [-f] [--no-skill]

Server spec can be:
    - A URL:            http://localhost:8000/mcp
    - A stdio command:  python server.py
    - A uvx command:    uvx some-server
"""

import argparse
import asyncio
import json
import keyword
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


# ── Schema helpers (mirrors fastmcp logic) ────────────────────────────────────

_SIMPLE = {"string", "integer", "number", "boolean", "null"}


def _is_simple(schema: dict[str, Any]) -> bool:
    t = schema.get("type")
    if isinstance(t, list):
        return all(x in _SIMPLE for x in t)
    return t in _SIMPLE


def _simple_array(schema: dict[str, Any]) -> tuple[bool, str | None]:
    if schema.get("type") != "array":
        return False, None
    items = schema.get("items", {})
    if not _is_simple(items):
        return False, None
    t = items.get("type", "string")
    if isinstance(t, list):
        return False, None
    type_map = {"string": "str", "integer": "int", "number": "float", "boolean": "bool"}
    return True, type_map.get(t)


def _py_type(schema: dict[str, Any]) -> tuple[str, bool]:
    """Return (python_type_str, needs_json_parse)."""
    ok, item_t = _simple_array(schema)
    if ok:
        return f"list[{item_t}]", False
    if _is_simple(schema):
        t = schema.get("type", "string")
        TM = {"string": "str", "integer": "int", "number": "float",
              "boolean": "bool", "null": "None"}
        if isinstance(t, list):
            return " | ".join(TM.get(x, "str") for x in t), False
        return TM.get(t, "str"), False
    return "str", True   # complex type → accept as JSON string


def _to_id(name: str) -> str:
    """Sanitize a string into a valid Python identifier."""
    s = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if s and s[0].isdigit():
        s = f"_{s}"
    if keyword.iskeyword(s):
        s = f"{s}_"
    return s or "_unnamed"


def _derive_name(spec: str) -> str:
    if spec.startswith(("http://", "https://")):
        return urlparse(spec).hostname or "server"
    if spec.endswith((".py", ".js", ".json")):
        return Path(spec).stem
    if ":" in spec:
        return spec.split(":", 1)[1] or spec.split(":", 1)[0]
    return spec.split()[0]


def _is_url(spec: str) -> bool:
    return spec.startswith(("http://", "https://"))


# ── Generated-script helpers ──────────────────────────────────────────────────

def _add_argument_lines(prop_name: str, prop_schema: dict[str, Any], is_required: bool) -> list[str]:
    """Return add_argument() source lines for one property."""
    py_t, needs_json = _py_type(prop_schema)
    flag = "--" + re.sub(r"[^a-zA-Z0-9]", "-", prop_name).strip("-")
    dest = _to_id(prop_name)
    desc = prop_schema.get("description", "")
    if needs_json:
        desc = f"{desc} (JSON string)" if desc else "JSON string"
    desc_r = repr(desc)
    req = "True" if is_required else "False"

    if py_t == "bool":
        return [f"p.add_argument({flag!r}, dest={dest!r}, action='store_true', help={desc_r})"]

    if py_t.startswith("list["):
        inner = py_t[5:-1]
        type_fns = {"str": "str", "int": "int", "float": "float", "bool": "bool"}
        type_fn = type_fns.get(inner, "str")
        return [f"p.add_argument({flag!r}, dest={dest!r}, nargs='+', type={type_fn}, required={req}, help={desc_r})"]

    # scalar / JSON blob
    type_fn_map = {"str": "str", "int": "int", "float": "float", "None": "str"}
    scalar = py_t.split(" | ")[0]
    type_fn = type_fn_map.get(scalar, "str")
    return [f"p.add_argument({flag!r}, dest={dest!r}, type={type_fn}, required={req}, help={desc_r})"]


def _tool_function_source(tool: Any) -> str:
    """Generate subparser-setup + async handler for one tool."""
    schema: dict[str, Any] = tool.inputSchema or {}
    if not isinstance(schema, dict):
        schema = {}
    props: dict[str, Any] = schema.get("properties", {})
    required: set[str] = set(schema.get("required", []))

    fn = _to_id(tool.name)
    desc = (tool.description or "").replace("\\", "\\\\").replace("'", "\\'")

    # Build lines explicitly to avoid f-string / textwrap.dedent indentation bugs.
    L: list[str] = []

    # --- _setup_<fn> ---
    L.append(f"def _setup_{fn}(sub):")
    L.append(f"    p = sub.add_parser({tool.name!r}, help='{desc}')")
    for pname, pschema in props.items():
        for line in _add_argument_lines(pname, pschema, pname in required):
            L.append(f"    {line}")
    if not props:
        L.append("    pass  # no parameters")
    L.append(f"    p.set_defaults(_handler=_handle_{fn})")
    L.append("")

    # --- _handle_<fn> ---
    L.append(f"async def _handle_{fn}(args):")
    if props:
        L.append("    arguments = {")
        for pname, pschema in props.items():
            safe = _to_id(pname)
            _, needs_json = _py_type(pschema)
            if needs_json:
                L.append(
                    f"        {pname!r}: json.loads(args.{safe})"
                    f" if isinstance(args.{safe}, str) else args.{safe},"
                )
            else:
                L.append(f"        {pname!r}: args.{safe},")
        L.append("    }")
    else:
        L.append("    arguments = {}")
    L.append("    arguments = {k: v for k, v in arguments.items() if v is not None}")
    L.append(f"    await _call_tool({tool.name!r}, arguments)")
    L.append("")

    return "\n".join(L)


# ── Full script generation ────────────────────────────────────────────────────

_HEADER_TMPL = """\
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.0"]
# ///
\"\"\"CLI for {server_name} MCP server.

Generated by: generate_cli.py {server_spec}
Usage:
    uv run {output_name} --help
    uv run {output_name} list-tools
    uv run {output_name} <tool-name> [--arg val ...]
    uv run {output_name} call-tool <tool-name> [key=value ...]
\"\"\"

import argparse
import asyncio
import json
import sys
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

try:
    from mcp.client.streamable_http import streamablehttp_client
    _HAS_STREAMABLE = True
except ImportError:
    _HAS_STREAMABLE = False

try:
    from mcp.client.sse import sse_client
    _HAS_SSE = True
except ImportError:
    _HAS_SSE = False

# Modify this to change how the CLI connects to the MCP server.
CLIENT_SPEC = {client_spec}
CLIENT_TYPE = {client_type!r}  # "url" or "stdio"


@asynccontextmanager
async def _get_session():
    \"\"\"Yield an initialized MCP ClientSession.\"\"\"
    if CLIENT_TYPE == "url":
        if _HAS_STREAMABLE:
            async with streamablehttp_client(CLIENT_SPEC) as (r, w, _):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    yield session
        elif _HAS_SSE:
            async with sse_client(CLIENT_SPEC) as (r, w):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    yield session
        else:
            raise RuntimeError(
                "No HTTP transport available. "
                "Install mcp with: pip install 'mcp[http]'"
            )
    else:
        params = StdioServerParameters(**CLIENT_SPEC)
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                yield session


async def _call_tool(name: str, arguments: dict) -> None:
    async with _get_session() as session:
        result = await session.call_tool(name, arguments)
        is_error = getattr(result, "isError", False)
        if is_error:
            for block in result.content:
                print("Error:", getattr(block, "text", repr(block)), file=sys.stderr)
            sys.exit(1)
        for block in result.content:
            text = getattr(block, "text", None)
            if text is not None:
                print(text)
            else:
                print(repr(block))


# ── Utility command handlers ──────────────────────────────────────────────────

async def _handle_list_tools(args):
    async with _get_session() as session:
        result = await session.list_tools()
        if not result.tools:
            print("No tools found.")
            return
        for tool in result.tools:
            schema = tool.inputSchema or {}
            props = schema.get("properties", {}) if isinstance(schema, dict) else {}
            req = set(schema.get("required", [])) if isinstance(schema, dict) else set()
            parts = []
            for pname, pschema in props.items():
                pt = pschema.get("type", "?")
                parts.append(f"{pname}: {pt}" if pname in req else f"[{pname}: {pt}]")
            print(f"  {tool.name}({', '.join(parts)})")
            if tool.description:
                print(f"    {tool.description}")
            print()


async def _handle_list_resources(args):
    async with _get_session() as session:
        result = await session.list_resources()
        if not result.resources:
            print("No resources found.")
            return
        for r in result.resources:
            print(f"  {r.uri}")
            if r.description:
                print(f"    {r.description}")
        print()


async def _handle_read_resource(args):
    async with _get_session() as session:
        result = await session.read_resource(args.uri)
        for block in result.contents:
            text = getattr(block, "text", None)
            if text is not None:
                print(text)
            else:
                print(repr(block))


async def _handle_list_prompts(args):
    async with _get_session() as session:
        result = await session.list_prompts()
        if not result.prompts:
            print("No prompts found.")
            return
        for p in result.prompts:
            arg_names = [a.name for a in (p.arguments or [])]
            suffix = f"({', '.join(arg_names)})" if arg_names else ""
            print(f"  {p.name}{suffix}")
            if p.description:
                print(f"    {p.description}")
        print()


async def _handle_call_tool_generic(args):
    \"\"\"Generic call-tool handler: name + key=value pairs.\"\"\"
    parsed: dict = {}
    for item in args.tool_args:
        if "=" not in item:
            print(f"Error: expected key=value, got {item!r}", file=sys.stderr)
            sys.exit(1)
        k, v = item.split("=", 1)
        try:
            parsed[k] = json.loads(v)
        except json.JSONDecodeError:
            parsed[k] = v
    await _call_tool(args.tool_name, parsed)


"""

_FOOTER_TMPL = """\

# ── CLI wiring ────────────────────────────────────────────────────────────────

_UTIL_HANDLERS = {
    "list-tools":      _handle_list_tools,
    "list-resources":  _handle_list_resources,
    "read-resource":   _handle_read_resource,
    "list-prompts":    _handle_list_prompts,
    "call-tool":       _handle_call_tool_generic,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="CLI for %s MCP server",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # Utility commands
    sub.add_parser("list-tools",      help="List available tools")
    sub.add_parser("list-resources",  help="List available resources")
    rr = sub.add_parser("read-resource", help="Read a resource by URI")
    rr.add_argument("uri", help="Resource URI")
    sub.add_parser("list-prompts",    help="List available prompts")

    ct = sub.add_parser("call-tool",  help="Call a tool by name with key=value args")
    ct.add_argument("tool_name",  help="Tool name")
    ct.add_argument("tool_args",  nargs="*", metavar="key=value", help="Tool arguments")

    # Generated per-tool subcommands
    _setup_tool_subparsers(sub)

    return parser


def _setup_tool_subparsers(sub):
%s


def main():
    parser = _build_parser()
    args = parser.parse_args()

    handler = getattr(args, "_handler", None)
    if handler is None:
        handler = _UTIL_HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    asyncio.run(handler(args))


if __name__ == "__main__":
    main()
"""

_SKILL_TMPL = """\
---
name: "{skill_name}-cli"
description: "CLI for the {server_name} MCP server. Call tools, list resources, and get prompts."
---

# {server_name} CLI

## Tool Commands

{tool_sections}
## Utility Commands

```bash
uv run {cli_name} list-tools
uv run {cli_name} list-resources
uv run {cli_name} read-resource <uri>
uv run {cli_name} list-prompts
uv run {cli_name} call-tool <tool-name> [key=value ...]
```
"""


def _tool_skill_section(tool: Any, cli_name: str) -> str:
    schema = tool.inputSchema or {}
    if not isinstance(schema, dict):
        schema = {}
    props: dict[str, Any] = schema.get("properties", {})
    required: set[str] = set(schema.get("required", []))

    flag_parts: list[str] = []
    for pname in props:
        flag = "--" + re.sub(r"[^a-zA-Z0-9]", "-", pname).strip("-")
        pschema = props[pname]
        if pschema.get("type") == "boolean":
            flag_parts.append(flag)
        else:
            flag_parts.append(f"{flag} <value>")

    invocation = f"uv run {cli_name} {tool.name}"
    if flag_parts:
        invocation += " " + " ".join(flag_parts)

    rows: list[str] = []
    for pname, pschema in props.items():
        flag = f"`--{re.sub(r'[^a-zA-Z0-9]', '-', pname).strip('-')}`"
        ptype = pschema.get("type", "string")
        if isinstance(ptype, list):
            ptype = " \\| ".join(ptype)
        is_req = "yes" if pname in required else "no"
        desc = pschema.get("description", "").replace("|", "\\|").replace("\n", " ")
        _, needs_json = _py_type(pschema)
        if needs_json:
            desc = f"{desc} (JSON string)" if desc else "JSON string"
        rows.append(f"| {flag} | {ptype} | {is_req} | {desc} |")

    lines = [f"### {tool.name}"]
    if tool.description:
        lines += ["", tool.description]
    lines += ["", "```bash", invocation, "```"]
    if rows:
        lines += [
            "",
            "| Flag | Type | Required | Description |",
            "|------|------|----------|-------------|",
            *rows,
        ]
    return "\n".join(lines)


def generate_skill_content(server_name: str, cli_name: str, tools: list[Any]) -> str:
    skill_name = re.sub(r"[^a-zA-Z0-9-]", "-", server_name).lower().strip("-")
    sections = "\n\n".join(_tool_skill_section(t, cli_name) for t in tools)
    return (
        _SKILL_TMPL
        .replace("{skill_name}", skill_name)
        .replace("{server_name}", server_name)
        .replace("{cli_name}", cli_name)
        .replace("{tool_sections}", sections + "\n\n" if sections else "")
    )


def generate_cli_script(
    server_name: str,
    server_spec: str,
    tools: list[Any],
    output_name: str,
) -> str:
    """Build the full generated CLI script as a string."""
    # Transport config
    if _is_url(server_spec):
        client_spec = repr(server_spec)
        client_type = "url"
    else:
        parts = server_spec.split()
        client_spec = repr({"command": parts[0], "args": parts[1:]})
        client_type = "stdio"

    # Use .replace() to avoid conflicts between .format() placeholders and
    # literal Python braces (dict comprehensions, f-strings) in the template.
    header = (
        _HEADER_TMPL
        .replace("{server_name}", server_name)
        .replace("{server_spec}", server_spec)
        .replace("{output_name}", output_name)
        .replace("{client_spec}", client_spec)
        .replace("{client_type!r}", repr(client_type))
    )

    # Per-tool setup + handler functions
    tool_funcs = "".join(_tool_function_source(t) for t in tools)

    # _setup_tool_subparsers body
    if tools:
        setup_calls = "\n".join(
            f"    _setup_{_to_id(t.name)}(sub)" for t in tools
        )
    else:
        setup_calls = "    pass  # no tools"

    footer = _FOOTER_TMPL % (server_name, setup_calls)

    return header + tool_funcs + footer


# ── MCP connection ────────────────────────────────────────────────────────────

async def _connect_and_list_tools(spec: str) -> tuple[list[Any], Any]:
    """Connect to the MCP server and return (tools, server_info)."""
    from mcp import ClientSession, StdioServerParameters

    if _is_url(spec):
        # Try streamable HTTP first, then SSE
        try:
            from mcp.client.streamable_http import streamablehttp_client
            async with streamablehttp_client(spec) as (r, w, _):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return result.tools, getattr(session, "server_info", None)
        except ImportError:
            pass

        from mcp.client.sse import sse_client
        async with sse_client(spec) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                result = await session.list_tools()
                return result.tools, getattr(session, "server_info", None)
    else:
        from mcp.client.stdio import stdio_client
        parts = spec.split()
        params = StdioServerParameters(command=parts[0], args=parts[1:])
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                result = await session.list_tools()
                return result.tools, getattr(session, "server_info", None)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "server_spec",
        help="Server URL (http://...) or stdio command (python server.py)",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default="cli.py",
        help="Output file path (default: cli.py)",
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Overwrite output file if it exists",
    )
    parser.add_argument(
        "--no-skill",
        action="store_true",
        help="Skip generating a SKILL.md agent skill file",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    skill_path = output_path.parent / "SKILL.md"

    # Check for existing files before doing any network I/O
    existing: list[Path] = []
    if output_path.exists() and not args.force:
        existing.append(output_path)
    if not args.no_skill and skill_path.exists() and not args.force:
        existing.append(skill_path)
    if existing:
        names = ", ".join(str(p) for p in existing)
        print(f"Error: {names} already exist(s). Use -f to overwrite.", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to {args.server_spec} …", file=sys.stderr)
    try:
        tools, server_info = asyncio.run(_connect_and_list_tools(args.server_spec))
    except Exception as exc:
        print(f"Error: could not connect: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Discovered {len(tools)} tool(s).", file=sys.stderr)

    server_name = _derive_name(args.server_spec)
    script = generate_cli_script(
        server_name=server_name,
        server_spec=args.server_spec,
        tools=tools,
        output_name=output_path.name,
    )

    output_path.write_text(script)
    output_path.chmod(output_path.stat().st_mode | 0o111)
    print(f"Wrote {output_path} with {len(tools)} tool command(s).")

    if not args.no_skill:
        skill_content = generate_skill_content(
            server_name=server_name,
            cli_name=output_path.name,
            tools=tools,
        )
        skill_path.write_text(skill_content)
        print(f"Wrote {skill_path}.")

    print(f"Run: python {output_path} --help")


if __name__ == "__main__":
    main()

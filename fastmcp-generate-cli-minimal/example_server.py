#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.0"]
# ///
"""Minimal MCP server for testing generate_cli.py.

Run directly (stdio mode):
    uv run example_server.py

The server exposes a few demo tools with different parameter types.
"""

import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

app = Server("example-server")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="add",
            description="Add two numbers together.",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First operand"},
                    "b": {"type": "number", "description": "Second operand"},
                },
                "required": ["a", "b"],
            },
        ),
        types.Tool(
            name="greet",
            description="Return a personalised greeting.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name to greet"},
                    "loud": {"type": "boolean", "description": "Shout the greeting"},
                    "times": {"type": "integer", "description": "How many times to repeat"},
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="join",
            description="Join a list of strings with a separator.",
            inputSchema={
                "type": "object",
                "properties": {
                    "words": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Words to join",
                    },
                    "sep": {"type": "string", "description": "Separator (default: space)"},
                },
                "required": ["words"],
            },
        ),
        types.Tool(
            name="echo_json",
            description="Echo back a JSON object.",
            inputSchema={
                "type": "object",
                "properties": {
                    "payload": {
                        "type": "object",
                        "description": "Any JSON object",
                        "additionalProperties": True,
                    },
                },
                "required": ["payload"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "add":
        result = arguments["a"] + arguments["b"]
        return [types.TextContent(type="text", text=str(result))]

    if name == "greet":
        greeting = f"Hello, {arguments['name']}!"
        if arguments.get("loud"):
            greeting = greeting.upper()
        times = int(arguments.get("times", 1))
        return [types.TextContent(type="text", text="\n".join([greeting] * times))]

    if name == "join":
        sep = arguments.get("sep", " ")
        return [types.TextContent(type="text", text=sep.join(arguments["words"]))]

    if name == "echo_json":
        return [types.TextContent(type="text", text=json.dumps(arguments["payload"], indent=2))]

    raise ValueError(f"Unknown tool: {name}")


async def main():
    async with stdio_server() as (r, w):
        await app.run(r, w, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

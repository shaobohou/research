"""MCP server exposing one world to an exploring LLM agent.

    uv run mcp_server.py --world worlds/seed-9021 [--explorer seeker]
                         [--role seeker|archivist] [--no-llm] [--model ...]

Speaks MCP over stdio; register it with any MCP client, e.g. Claude Code:

    claude mcp add lore -- uv run --project /path/to/souls-lore-gen \
        /path/to/souls-lore-gen/mcp_server.py --world worlds/seed-9021 --no-llm

The seeker role sees only the diegetic surface; grading and world state live
server-side (see explore.py). The archivist role additionally gets `canon`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from explore import Exploration
from loregen import DEFAULT_MODEL


def build_server(exp: Exploration) -> FastMCP:
    mcp = FastMCP(
        "souls-lore",
        instructions=(
            "You are exploring the lore of a lost world through what its "
            "objects remember. Descriptions are fragmentary, biased, and "
            "sometimes wrong; the truth must be triangulated. Loop: survey, "
            "examine items, follow leads (ask about names, delve into "
            "places/events), and when you believe you understand what truly "
            "happened, submit theories. Budgets are limited — spend delves "
            "and asks where the story feels deliberately silent."),
    )

    @mcp.tool()
    def survey() -> dict:
        """List what exists: items, factions heard of, ages, your budget."""
        return exp.survey()

    @mcp.tool()
    def examine(item: str) -> dict:
        """Read an item's description (by name or substring). Free. Returns
        leads: names the description mentions, each a thread to pull."""
        return exp.examine(item)

    @mcp.tool()
    def ask(question: str) -> dict:
        """Ask the archives a question; answered in-world, from surviving
        records only. Costs 1 ask."""
        return exp.ask(question)

    @mcp.tool()
    def delve(target: str) -> dict:
        """Dig into a lead (item, figure, faction, place, or event id like
        'e14'). Materializes deeper history behind it: new accounts, and
        sometimes new items. Costs 1 delve; a dead-end trail is refunded."""
        return exp.delve(target)

    @mcp.tool()
    def theorize(claims: list[str]) -> dict:
        """Submit up to 12 claims about the true history. Each is graded:
        established / consistent / unsupported / contradicted / veiled —
        without revealing what you haven't found."""
        return exp.theorize(claims)

    @mcp.tool()
    def progress() -> dict:
        """Your exploration status: items examined, budget, best score."""
        return exp.progress()

    if exp.role == "archivist":
        @mcp.tool()
        def canon() -> dict:
            """[archivist] The full ledger, veils included. Spoils everything."""
            return exp.canon()

    return mcp


def main():
    ap = argparse.ArgumentParser(description="Souls-lore MCP server")
    ap.add_argument("--world", type=Path, default=Path("worlds/seed-107"),
                    help="world directory containing ledger.json")
    ap.add_argument("--explorer", default="seeker",
                    help="named exploration state (fog of war) to use")
    ap.add_argument("--role", choices=["seeker", "archivist"], default="seeker")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--no-llm", action="store_true",
                    help="template answering/grading, no API key needed")
    args = ap.parse_args()

    exp = Exploration(args.world, explorer=args.explorer, role=args.role,
                      model=None if args.no_llm else args.model)
    build_server(exp).run()


if __name__ == "__main__":
    main()

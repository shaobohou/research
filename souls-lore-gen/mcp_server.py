"""MCP server exposing one world to an exploring LLM agent.

    uv run mcp_server.py --world worlds/seed-9021 [--explorer seeker]
                         [--role seeker|archivist] [--model ...]

Speaks MCP over stdio; register it with any MCP client, e.g. Claude Code:

    claude mcp add lore -- uv run --project /path/to/souls-lore-gen \
        /path/to/souls-lore-gen/mcp_server.py --world worlds/seed-9021

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
            "You are a body in a lost world, reading its history off the "
            "objects it left behind. You learn a place's relics only by "
            "walking there; each relic's resting place is itself a clue. "
            "Descriptions are fragmentary, biased, and sometimes wrong — the "
            "truth must be triangulated across many. Loop: survey (your map), "
            "travel, look, examine, follow leads (ask, delve), travel on. "
            "When you have a theory, lay it before the antiquary — but know "
            "that in this world no one will ever tell you that you are right. "
            "Silence, where you expected an answer, is itself the answer. "
            "Steps, asks, and delves are limited; spend them where the story "
            "feels deliberately quiet."),
    )

    @mcp.tool()
    def survey() -> dict:
        """Your charted map: where you stand, the places you know (walked vs
        only heard of), the ages, and your remaining strength. Not a
        catalogue — you learn what a place holds only by going there."""
        return exp.survey()

    @mcp.tool()
    def look() -> dict:
        """What lies where you stand: the relics here (with how each was
        found — a clue in itself) and the ways onward."""
        return exp.look()

    @mcp.tool()
    def travel(place: str) -> dict:
        """Walk to a place you have heard of. New ground costs a step;
        returning is free. Arriving reveals what lies there and the ways on."""
        return exp.travel(place)

    @mcp.tool()
    def examine(item: str) -> dict:
        """Study a relic you stand beside or have already found. Free.
        Returns its description, how it lies, and leads (names it mentions)."""
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
        """Lay up to 12 claims before a fellow antiquary. You receive their
        in-world reaction — never a verdict. The world will not confirm you;
        if they fall silent on a claim, you have touched something buried."""
        return exp.theorize(claims)

    @mcp.tool()
    def progress() -> dict:
        """Your exploration status: items examined, budget, best score."""
        return exp.progress()

    @mcp.tool()
    def compendium() -> str:
        """The Book of Found Things: everything you have discovered so far,
        as one markdown document. Free."""
        return exp.compendium()

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
    ap.add_argument("--benchmark", action="store_true",
                    help="expose theorize verdicts+scores (for eval harnesses; "
                         "off by default — seekers play in purist mode)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    exp = Exploration(args.world, explorer=args.explorer, role=args.role,
                      model=args.model,
                      purist=not args.benchmark)
    build_server(exp).run()


if __name__ == "__main__":
    main()

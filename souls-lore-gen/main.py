"""CLI: generate a world, then deepen it on demand.

    uv run main.py generate --seed 107 --items 14
    uv run main.py deepen --seed 107 --item "Oathbreaker"   # or --node e12
    uv run main.py ask --seed 107 "Who was Irveth?"
    uv run main.py codex --seed 107                          # re-render only

All prose is written by Claude, so a working credential is required
(ANTHROPIC_API_KEY or `ant auth login`). Bare `uv run main.py --seed N`
still works and means `generate`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ledger import (Ledger, LedgerError, ensure_geography,
                    render_chronicle, render_codex)
from loregen import (DEFAULT_MODEL, NoCredentials, ask_world, describe_items,
                     elaborate)
from expand import expand_event
from worldsim import generate_world


def _world_dir(args) -> Path:
    return args.out / f"seed-{args.seed}"


def _load(args) -> Ledger:
    path = _world_dir(args) / "ledger.json"
    if not path.exists():
        sys.exit(f"no world at {path} — run `generate --seed {args.seed}` first")
    return Ledger.load(path)


def _write(args, lg: Ledger):
    d = _world_dir(args)
    d.mkdir(parents=True, exist_ok=True)
    ensure_geography(lg)
    lg.save(d / "ledger.json")
    (d / "chronicle.md").write_text(render_chronicle(lg))
    (d / "codex.md").write_text(render_codex(lg))


def cmd_generate(args) -> int:
    world = generate_world(args.seed, args.items)
    lg = Ledger.from_world(world)
    aids = [i for i, _ in lg.of_type("artifact")]
    describe_items(lg, aids, args.model, want_epigraph=True)
    mode = args.model
    _write(args, lg)
    print(f"world generated: archetype={lg.meta['archetype_key']}, "
          f"{len(lg.of_type('event'))} events, {len(aids)} items [{mode}]",
          file=sys.stderr)
    print(f"wrote {_world_dir(args)}/{{ledger.json,chronicle.md,codex.md}}",
          file=sys.stderr)
    return 0


def _resolve_node(lg: Ledger, args) -> str:
    if args.node:
        return args.node
    if args.item:
        aid, a = lg.find_artifact(args.item)
        # Deepen the last event in the item's provenance; if that's already
        # expanded, walk down to its first unexpanded child.
        node = a["provenance"][-1]
        while lg.get(node)["expanded"]:
            kids = [cid for cid, c in lg.children_of(node) if not c["expanded"]]
            if not kids:
                raise LedgerError(f"everything beneath {node} is expanded; "
                                  f"pass --node explicitly")
            node = kids[0]
        return node
    raise LedgerError("pass --node <event-id> or --item <name substring>")


def cmd_deepen(args) -> int:
    lg = _load(args)
    try:
        node = _resolve_node(lg, args)
        child_ids, item_ids = expand_event(lg, node)
    except LedgerError as e:
        sys.exit(f"cannot deepen: {e}")

    elaborate(lg, node, child_ids, item_ids, args.model)
    _write(args, lg)
    parent = lg.get(node)
    print(f"deepened {node} (\"{parent['kind']}\", year {parent['year']}, "
          f"depth {parent['depth']} -> {parent['depth'] + 1})", file=sys.stderr)
    for cid in child_ids:
        c = lg.get(cid)
        print(f"  + {cid} (year {c['year']}, {c['kind']}): {c['text'][:70]}...",
              file=sys.stderr)
    for aid in item_ids:
        print(f"  + item {aid}: {lg.get(aid)['name']}", file=sys.stderr)
    return 0


def cmd_ask(args) -> int:
    lg = _load(args)
    answer = ask_world(lg, args.question, args.model)
    print(answer)
    with (_world_dir(args) / "answers.md").open("a") as fh:
        fh.write(f"\n**Q: {args.question}**\n\n{answer}\n")
    return 0


def cmd_lore(args) -> int:
    from explore import Exploration
    exp = Exploration(_world_dir(args), explorer=args.explorer,
                      model=args.model)
    out = _world_dir(args) / "explorations" / f"{args.explorer}-lore.md"
    out.write_text(exp.compendium())
    print(f"wrote {out}", file=sys.stderr)
    return 0


def cmd_codex(args) -> int:
    lg = _load(args)
    _write(args, lg)
    print(f"re-rendered {_world_dir(args)}/{{chronicle.md,codex.md}}", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Souls-style procedural lore generator")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--seed", type=int, default=107)
        p.add_argument("--out", type=Path, default=Path("worlds"))
        p.add_argument("--model", default=DEFAULT_MODEL)

    g = sub.add_parser("generate", help="create a new world")
    common(g)
    g.add_argument("--items", type=int, default=14)
    g.set_defaults(fn=cmd_generate)

    d = sub.add_parser("deepen", help="expand one event a level deeper")
    common(d)
    d.add_argument("--node", help="event id, e.g. e12")
    d.add_argument("--item", help="item name substring; deepens its provenance")
    d.set_defaults(fn=cmd_deepen)

    a = sub.add_parser("ask", help="ask the world a question, answered in-world")
    common(a)
    a.add_argument("question")
    a.set_defaults(fn=cmd_ask)

    c = sub.add_parser("codex", help="re-render chronicle.md and codex.md")
    common(c)
    c.set_defaults(fn=cmd_codex)

    lo = sub.add_parser("lore", help="write an explorer's discovered-lore compendium")
    common(lo)
    lo.add_argument("--explorer", default="seeker")
    lo.set_defaults(fn=cmd_lore)

    argv = sys.argv[1:]
    if not argv or argv[0].startswith("-"):
        argv = ["generate"] + argv          # back-compat: bare flags = generate
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except NoCredentials as e:
        sys.exit(str(e))                    # a message, not a traceback


if __name__ == "__main__":
    raise SystemExit(main())

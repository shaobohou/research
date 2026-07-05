"""CLI: generate a world and render its chronicle + item codex.

Usage:
    uv run main.py --seed 107 --items 14 --out worlds
    uv run main.py --seed 107 --no-llm          # template mode, no API key needed
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from worldsim import generate_world, render_chronicle
from loregen import DEFAULT_MODEL, fallback_descriptions, llm_descriptions, render_codex


def main() -> int:
    ap = argparse.ArgumentParser(description="Souls-style procedural lore generator")
    ap.add_argument("--seed", type=int, default=107, help="world seed (default 107)")
    ap.add_argument("--items", type=int, default=14, help="target number of items")
    ap.add_argument("--out", type=Path, default=Path("worlds"), help="output directory")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model (default {DEFAULT_MODEL})")
    ap.add_argument("--no-llm", action="store_true",
                    help="use the deterministic template writer instead of Claude")
    args = ap.parse_args()

    world = generate_world(args.seed, args.items)
    print(f"world generated: archetype={world.archetype_key}, "
          f"{len(world.events)} events, {len(world.figures)} figures, "
          f"{len(world.artifacts)} items", file=sys.stderr)

    if args.no_llm:
        epigraph, descs = fallback_descriptions(world)
        mode = "template"
    else:
        try:
            epigraph, descs = llm_descriptions(world, model=args.model)
            mode = f"llm ({args.model})"
        except Exception as e:
            if os.environ.get("ANTHROPIC_API_KEY"):
                raise
            print(f"LLM call failed ({type(e).__name__}) and no ANTHROPIC_API_KEY is set; "
                  f"falling back to template mode. Set a key for the real prose.",
                  file=sys.stderr)
            epigraph, descs = fallback_descriptions(world)
            mode = "template (fallback)"

    outdir = args.out / f"seed-{args.seed}"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "chronicle.md").write_text(render_chronicle(world))
    (outdir / "codex.md").write_text(render_codex(world, epigraph, descs))
    (outdir / "world.json").write_text(json.dumps(world.to_dict(), indent=2))

    print(f"wrote {outdir}/chronicle.md (ground truth), codex.md ({mode}), world.json",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

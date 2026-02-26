# rodney test drive — origamisimulator.org

## Summary

A quick exploration of [`rodney`](https://pypi.org/project/rodney/) (v0.4.0), a headless Chrome automation CLI, against [Origami Simulator](https://origamisimulator.org) — a WebGL-based physics simulation of origami folding.

## What is rodney?

`rodney` is a CLI tool for driving Chrome from the command line. Key commands:

| Command | Purpose |
|---|---|
| `rodney start` | Launch headless Chrome (auto-downloads Chromium) |
| `rodney open <url>` | Navigate; returns page title |
| `rodney screenshot <file>` | Save PNG |
| `rodney js <expr>` | Evaluate JS (single expressions) |
| `rodney ax-tree` | Dump accessibility tree |
| `rodney click <selector>` | Click element |
| `rodney stop` | Shut down browser |

## Key findings

- **Zero setup friction**: `uvx rodney` downloads and runs with no install; Chromium is fetched automatically (~11 MB)
- **JS evaluation**: Works well for single expressions; jQuery (if available on page) is a useful bridge for complex interactions
- **Screenshots**: Instant, clean PNG output — great for visual verification
- **Accessibility tree**: `ax-tree` is useful for mapping SPA UIs without inspecting source
- **Gotcha**: `--show` (visible browser) is listed in help but not implemented in v0.4.0

## Origami Simulator tour

The site has 80+ examples across categories: Origami, Tessellations, Curved Creases, Kirigami, Popups, Maze Foldings, Pleating, Bases, Simple Folds, Bistable.

### Screenshots

**Default load — magenta tessellation at 60% fold:**

`screenshot-landing.png`

**Crane (3D) fully folded at 100%:**

`screenshot-crane-folded.png`

**Miura-Ori flat (0%) — crease pattern visible:**

`screenshot-miura-flat.png`

The Miura-Ori is a classic rigid-foldable tessellation used in deployable space structures (solar panels, satellite arrays). It compresses from a flat sheet to a compact brick with a single degree of freedom.

## Next steps

- Automate fold animation: scrub slider 0→100 with `rodney js` + `requestAnimationFrame` and capture frames
- Test `rodney pdf` for saving pattern diagrams
- Explore the FOLD file format export/import pipeline
- Try curved crease examples (Origami Sphere, Boomerang Tessellation)

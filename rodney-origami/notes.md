# rodney test drive on origamisimulator.org

## Setup
- Tool: `uvx rodney` (v0.4.0) — Chrome automation CLI
- Target: https://origamisimulator.org
- Date: 2026-02-25

## Commands used

### Start browser
```
uvx rodney start       # headless Chrome (note: --show flag shown in help is not yet implemented in v0.4.0)
uvx rodney status      # confirm running + debug WS URL
```

### Navigation & inspection
```
uvx rodney open https://origamisimulator.org   # returns page title on success
uvx rodney url                                  # prints current URL
uvx rodney title                                # prints page title
uvx rodney ax-tree --depth 3                    # accessibility tree for UI mapping
uvx rodney js "..."                             # evaluate JS expression (single expressions only, no multi-line)
uvx rodney screenshot <file>                    # save PNG
```

## What worked well
- `rodney start` auto-downloads Chromium on first run (~10.9 MB)
- `rodney open <url>` returns the page title — nice quick confirmation
- `rodney ax-tree` gave a clean structural overview of the UI
- `rodney js` with single expressions works well; jQuery was available on the page
- `rodney screenshot` produces clean PNGs instantly
- `rodney stop` cleanly shuts down

## Gotchas / quirks
- `--show` flag listed in help output is NOT implemented in v0.4.0 (exits with error)
- `rodney js` only accepts single-expression JS — no `var`, `if`, multi-line, etc.
  - Workaround: use arrow functions and ternary operators
- `rodney click 'complex-selector'` can timeout; falling back to `rodney js "el.click()"` works
- First `rodney status` check before Chromium finished downloading returned "No active browser session"

## Origami Simulator exploration
- Loaded default (magenta tessellation at 60% fold)
- Opened File menu — saw Import/Export options (SVG, FOLD, STL, OBJ, GIF, video)
- Clicked "Crane (3D)" example — loaded classic origami crane
- Used `sliderEndPt` link click via JS to animate from 60% → 100% fold
- Loaded "Miura-Ori" tessellation (famous deployable fold used in space solar panels)
- Toggled Flat (0%) ↔ Folded (100%) views

## Screenshots taken
- screenshot-landing.png — default magenta tessellation at 60%
- screenshot-menu.png — File menu open (model rotated)
- screenshot-crane.png — Crane (3D) at 60% fold
- screenshot-crane-folded.png — Crane at 100% fold (fully folded)
- screenshot-miura.png — Miura-Ori at 100% (compact folded state)
- screenshot-miura-flat.png — Miura-Ori at 0% (flat sheet with crease pattern visible)

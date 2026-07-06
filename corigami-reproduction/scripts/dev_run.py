"""Dev harness: run one figure through pack -> solve -> verify -> fold."""
import sys
import time

from corigami.stickfigure import example_figures, grid_size_heuristic
from corigami.packing import pack_sweep
from corigami.solver import build_crease_pattern, assign_mv
from corigami.foldability import check_pattern
from corigami.fold import fold

name = sys.argv[1] if len(sys.argv) > 1 else "seedling"
sf = next(f for f in example_figures() if f.name == name)
print(f"figure={sf.name!r} flaps={len(sf.flaps)} rivers={len(sf.rivers)}")
errs = sf.validate()
print("validate:", errs or "ok")

g0 = grid_size_heuristic(sf)
print("grid heuristic:", g0, "diameter:", sf.diameter())

t = time.time()
G, packs = pack_sweep(sf, g0)
print(f"packing: G={G} solutions={len(packs)} ({time.time()-t:.2f}s)")
if not packs:
    sys.exit(1)

for pi, pk in enumerate(packs[:2]):
    print(f"--- packing {pi} ---")
    for r in pk.regions:
        print("   ", type(r).__name__, r.stick_label, r.rect,
              getattr(r, "tip", ""))
    t = time.time()
    cp, kinds = build_crease_pattern(pk)
    cpp = cp.planarize()
    print(f"creases: {len(cp.edges)} segs, planarized {len(cpp.edges)} "
          f"({time.time()-t:.2f}s)")
    t = time.time()
    solved = assign_mv(cpp)
    print(f"assign_mv: {'ok' if solved else 'FAILED'} ({time.time()-t:.2f}s)")
    if solved is None:
        continue
    ok, reports = check_pattern(solved)
    bad = [r for r in reports if not r.flat_foldable]
    print(f"check_pattern: {'PASS' if ok else 'FAIL'} bad={len(bad)}")
    t = time.time()
    st = fold(solved)
    print(f"fold: mean strain={st.mean_axial_strain:.2e} "
          f"max={st.max_axial_strain:.2e} ({time.time()-t:.2f}s)")
    break

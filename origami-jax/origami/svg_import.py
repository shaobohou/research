"""Standalone SVG -> FOLD importer for origami crease patterns.

Reimplements (in Python, from scratch) the import pipeline of
amandaghassaei/OrigamiSimulator (MIT): js/pattern.js loadSVG/parseSVG plus the
fold.js filter/convert helpers it relies on. Completely independent of the
solver and renderer: input is an SVG file, output is a FOLD dict that
origami.model.load_fold accepts.

Pipeline (matching the original's order and quirks):
  1. parse <path>/<line>/<rect>/<polygon>/<polyline>, classify by stroke color:
       black=border(B), red=mountain(M), blue=valley(V), green=cut(C),
       yellow=facet(F), magenta=hinge(U); anything else ignored (collected in
       result["ignored_strokes"]). Mountain/valley fold angle = opacity*180
       (M negative). Elements inside <symbol>/<defs> are dropped; transforms
       are applied per element, innermost first.
       Styling sources: presentation attributes, inline style="...", and
       class/element selectors from <style> blocks (no full CSS cascade).
       Path commands M/m L/l H/h V/v Z/z (curves are not supported, like the
       original's non-curve importer).
  2. merge vertices within vert_tol (grid hash, strict < tol, last coordinate
     wins), drop zero-length and duplicate edges (last assignment wins),
  3. split crossing edges at intersections (pairwise, with vert_tol endpoint
     snapping), then merge/dedupe again,
  4. drop stray vertices, dissolve collinear degree-2 vertices (angle epsilon
     0.01 on the dot product, only when both edge assignments agree),
  5. find planar faces by counterclockwise edge traversal, drop the outer face
     (negative orientation) and faces bounded entirely by border edges (holes),
  6. return FOLD dict: vertices_coords (2D, SVG x/y), edges_vertices,
     edges_assignment, edges_foldAngle (degrees, null for B/U/C),
     faces_vertices (CCW polygons, winding reversed like the original).
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET

__all__ = ["svg_to_fold", "SVGImportError"]

VERT_TOL = 3.0  # default vertex merge tolerance (globals.vertTol)
REDUNDANT_EPS = 0.01  # collinearity epsilon for dissolving degree-2 vertices

_COLOR_TYPES = {
    "border": {"#000000", "#000", "black", "rgb(0,0,0)"},
    "mountain": {"#ff0000", "#f00", "red", "rgb(255,0,0)"},
    "valley": {"#0000ff", "#00f", "blue", "rgb(0,0,255)"},
    "cut": {"#00ff00", "#0f0", "green", "rgb(0,255,0)"},
    "triangulation": {"#ffff00", "#ff0", "yellow", "rgb(255,255,0)"},
    "hinge": {"#ff00ff", "#f0f", "magenta", "rgb(255,0,255)"},
}
_TYPE_ASSIGNMENT = [  # parse order = the original's findType/parseSVG order
    ("border", "B"),
    ("mountain", "M"),
    ("valley", "V"),
    ("triangulation", "F"),
    ("hinge", "U"),
    ("cut", "C"),
]


class SVGImportError(Exception):
    pass


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


# ------------------------------------------------------------------ styling


def _parse_style_blocks(root) -> dict[str, dict[str, str]]:
    """Minimal CSS: 'sel1, sel2 { prop: val; }' for .class / element selectors."""
    rules: dict[str, dict[str, str]] = {}
    for el in root.iter():
        if _localname(el.tag) == "style" and el.text:
            css = re.sub(r"/\*.*?\*/", "", el.text, flags=re.S)
            for sels, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
                props = {}
                for decl in body.split(";"):
                    if ":" in decl:
                        k, v = decl.split(":", 1)
                        props[k.strip().lower()] = v.strip()
                for sel in sels.split(","):
                    sel = sel.strip()
                    if sel:
                        rules.setdefault(sel, {}).update(props)
    return rules


def _style_prop(el, css_rules, prop: str) -> str | None:
    """Resolve a styling property: CSS class/element rules, inline style,
    then presentation attribute (closest approximation of computed style)."""
    value = None
    tag = _localname(el.tag)
    if tag in css_rules and prop in css_rules[tag]:
        value = css_rules[tag][prop]
    for cls in (el.get("class") or "").split():
        sel = "." + cls
        if sel in css_rules and prop in css_rules[sel]:
            value = css_rules[sel][prop]
    if value is None:
        value = el.get(prop)
    style = el.get("style")
    if style:
        for decl in style.split(";"):
            if ":" in decl:
                k, v = decl.split(":", 1)
                if k.strip().lower() == prop:
                    value = v.strip()
    return value


def _stroke_type(el, css_rules) -> str | None:
    stroke = _style_prop(el, css_rules, "stroke")
    if stroke is None:
        return None
    stroke = re.sub(r"\s", "", stroke).lower()
    for typ, colors in _COLOR_TYPES.items():
        if stroke in colors:
            return typ
    return stroke  # unknown color string (reported, then ignored)


def _opacity(el, css_rules) -> float:
    def num(prop):
        v = _style_prop(el, css_rules, prop)
        if v is None:
            return 1.0
        try:
            return float(v)
        except ValueError:
            return 1.0

    return num("opacity") * num("stroke-opacity")


# ------------------------------------------------------------------ transforms

_TRANSFORM_RE = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)")


def _parse_transform(attr: str | None) -> list[list[float]]:
    """Parse a transform attribute into a list of 3x3 matrices (row-major)."""
    if not attr:
        return []
    mats = []
    for name, args in _TRANSFORM_RE.findall(attr):
        a = [float(x) for x in re.split(r"[\s,]+", args.strip()) if x]
        if name == "matrix" and len(a) == 6:
            m = [[a[0], a[2], a[4]], [a[1], a[3], a[5]], [0, 0, 1]]
        elif name == "translate":
            tx, ty = a[0], a[1] if len(a) > 1 else 0.0
            m = [[1, 0, tx], [0, 1, ty], [0, 0, 1]]
        elif name == "scale":
            sx, sy = a[0], a[1] if len(a) > 1 else a[0]
            m = [[sx, 0, 0], [0, sy, 0], [0, 0, 1]]
        elif name == "rotate":
            r = math.radians(a[0])
            c, s = math.cos(r), math.sin(r)
            m = [[c, -s, 0], [s, c, 0], [0, 0, 1]]
            if len(a) == 3:
                cx, cy = a[1], a[2]
                t1 = [[1, 0, cx], [0, 1, cy], [0, 0, 1]]
                t2 = [[1, 0, -cx], [0, 1, -cy], [0, 0, 1]]
                m = _matmul(_matmul(t1, m), t2)
        elif name == "skewX":
            m = [[1, math.tan(math.radians(a[0])), 0], [0, 1, 0], [0, 0, 1]]
        elif name == "skewY":
            m = [[1, 0, 0], [math.tan(math.radians(a[0])), 1, 0], [0, 0, 1]]
        else:
            continue
        mats.append(m)
    return mats


def _matmul(m1, m2):
    return [[sum(m1[i][k] * m2[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _apply_transforms(pt, transform_list):
    """Apply matrices in list order (innermost element first, like pattern.js
    applyTransformation, which walks element -> ancestors applying each)."""
    x, y = pt
    for m in transform_list:
        x, y = (m[0][0] * x + m[0][1] * y + m[0][2], m[1][0] * x + m[1][1] * y + m[1][2])
    return (x, y)


# ------------------------------------------------------------------ element parsing

_PATH_CMD_RE = re.compile(r"([MmLlHhVvZzCcSsQqTtAa])([^MmLlHhVvZzCcSsQqTtAa]*)")
_NUM_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def _path_segments(d: str, warn: list[str]):
    """Yield (vertices, segment index pairs) per the supported command set."""
    verts: list[tuple[float, float]] = []
    segs: list[tuple[int, int]] = []
    start = None  # index of current subpath start
    for cmd, argstr in _PATH_CMD_RE.findall(d or ""):
        args = [float(x) for x in _NUM_RE.findall(argstr)]
        if cmd in "Mm":
            pairs = list(zip(args[0::2], args[1::2]))
            for k, (px, py) in enumerate(pairs):
                if k == 0:
                    if cmd == "m" and verts:
                        lx, ly = verts[-1]
                        px, py = lx + px, ly + py
                    start = len(verts)
                    verts.append((px, py))
                else:  # implicit lineto
                    lx, ly = verts[-1]
                    if cmd == "m":
                        px, py = lx + px, ly + py
                    segs.append((len(verts) - 1, len(verts)))
                    verts.append((px, py))
        elif cmd in "Ll":
            for px, py in zip(args[0::2], args[1::2]):
                lx, ly = verts[-1]
                if cmd == "l":
                    px, py = lx + px, ly + py
                segs.append((len(verts) - 1, len(verts)))
                verts.append((px, py))
        elif cmd in "Hh":
            for px in args:
                lx, ly = verts[-1]
                nx = lx + px if cmd == "h" else px
                segs.append((len(verts) - 1, len(verts)))
                verts.append((nx, ly))
        elif cmd in "Vv":
            for py in args:
                lx, ly = verts[-1]
                ny = ly + py if cmd == "v" else py
                segs.append((len(verts) - 1, len(verts)))
                verts.append((lx, ny))
        elif cmd in "Zz":
            if start is not None and verts:
                segs.append((len(verts) - 1, start))
                start = None
        else:
            warn.append(f"unsupported path command '{cmd}' ignored (curves not supported)")
    return verts, segs


def _element_geometry(el, warn):
    """Returns (vertices, segments) in element-local coordinates."""
    tag = _localname(el.tag)
    f = lambda attr, default=0.0: float(el.get(attr, default))  # noqa: E731
    if tag == "path":
        return _path_segments(el.get("d", ""), warn)
    if tag == "line":
        return [(f("x1"), f("y1")), (f("x2"), f("y2"))], [(0, 1)]
    if tag == "rect":
        x, y, w, h = f("x"), f("y"), f("width"), f("height")
        return ([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], [(0, 1), (1, 2), (2, 3), (3, 0)])
    if tag in ("polygon", "polyline"):
        nums = [float(v) for v in _NUM_RE.findall(el.get("points", ""))]
        pts = list(zip(nums[0::2], nums[1::2]))
        segs = [(i, i + 1) for i in range(len(pts) - 1)]
        if tag == "polygon" and len(pts) > 1:
            segs.append((len(pts) - 1, 0))
        return pts, segs
    return [], []


# ------------------------------------------------------------------ graph cleanup


def _collapse_nearby_vertices(verts, edges, tol):
    """Grid-hash merge of vertices within tol (strict <). The representative
    index is the first inserted; its coordinate is the last merged (matching
    fold.js collapseNearbyVertices + remapField last-wins)."""
    grid: dict[tuple[int, int], list[int]] = {}
    coords: list[tuple[float, float]] = []
    old2new = []
    for x, y in verts:
        kx, ky = round(x / tol), round(y / tol)
        found = None
        for gx in (kx, kx - 1, kx + 1):
            for gy in (ky, ky - 1, ky + 1):
                for idx in grid.get((gx, gy), ()):  # match against insert-time coords
                    cx, cy = coords[idx]
                    if math.hypot(cx - x, cy - y) < tol:
                        found = idx
                        break
                if found is not None:
                    break
            if found is not None:
                break
        if found is None:
            found = len(coords)
            coords.append((x, y))
            grid.setdefault((kx, ky), []).append(found)
        old2new.append(found)
    # last-wins coordinates
    new_coords = list(coords)
    for i, j in enumerate(old2new):
        new_coords[j] = verts[i]
    new_edges = [(old2new[a], old2new[b], asn, ang) for a, b, asn, ang in edges]
    return new_coords, new_edges


def _dedupe_edges(edges):
    out: dict[tuple[int, int], tuple] = {}
    for a, b, asn, ang in edges:
        if a == b:
            continue  # loop edge
        out[(a, b) if a < b else (b, a)] = (a, b, asn, ang)  # last wins
    return list(out.values())


def _find_intersections(verts, edges, tol):
    """Pairwise edge-crossing split, replicating pattern.js findIntersections
    (including endpoint snapping within tol and in-place splice behavior)."""
    edges = [list(e) for e in edges]
    i = len(edges) - 1
    while i >= 0:
        j = i - 1
        while j >= 0:
            (x1, y1), (x2, y2) = verts[edges[i][0]], verts[edges[i][1]]
            (x3, y3), (x4, y4) = verts[edges[j][0]], verts[edges[j][1]]
            denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
            if denom != 0.0:
                ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
                ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denom
                len1 = math.hypot(x2 - x1, y2 - y1)
                len2 = math.hypot(x4 - x3, y4 - y3)
                d1, d2 = ua * len1, ub * len2
                if -tol <= d1 <= len1 + tol and -tol <= d2 <= len2 + tol:
                    seg1_int = tol < d1 < len1 - tol
                    seg2_int = tol < d2 < len2 - tol
                    if seg1_int or seg2_int:
                        if seg1_int and seg2_int:
                            vert_index = len(verts)
                            verts.append((x1 + ua * (x2 - x1), y1 + ua * (y2 - y1)))
                        elif seg1_int:
                            vert_index = edges[j][0] if d2 <= tol else edges[j][1]
                        else:
                            vert_index = edges[i][0] if d1 <= tol else edges[i][1]
                        if seg1_int:
                            a, b, asn, ang = edges[i]
                            edges[i : i + 1] = [[vert_index, a, asn, ang], [vert_index, b, asn, ang]]
                            i += 1
                        if seg2_int:
                            a, b, asn, ang = edges[j]
                            edges[j : j + 1] = [[vert_index, a, asn, ang], [vert_index, b, asn, ang]]
                            j += 1
                            i += 1
            j -= 1
        i -= 1
    return verts, [tuple(e) for e in edges]


def _vertices_vertices(n_verts, edges):
    vv: list[list[int]] = [[] for _ in range(n_verts)]
    for a, b, *_ in edges:
        vv[a].append(b)
        vv[b].append(a)
    return vv


def _remap_vertices(verts, edges, keep_mask):
    old2new, out = [], []
    for v, keep in enumerate(keep_mask):
        if keep:
            old2new.append(len(out))
            out.append(verts[v])
        else:
            old2new.append(None)
    edges = [(old2new[a], old2new[b], asn, ang) for a, b, asn, ang in edges]
    return out, edges, old2new


def _remove_redundant_vertices(verts, edges, eps):
    """Dissolve degree-2 vertices whose two edges are collinear and share the
    same assignment (pattern.js removeRedundantVertices + mergeEdge)."""
    while True:
        vv = _vertices_vertices(len(verts), edges)
        merged_any = False
        removed = [False] * len(verts)
        edges = [list(e) for e in edges]
        for v, nbrs in enumerate(vv):
            if len(nbrs) != 2 or removed[v] or removed[nbrs[0]] or removed[nbrs[1]]:
                continue
            (x, y) = verts[v]
            (x0, y0), (x1, y1) = verts[nbrs[0]], verts[nbrs[1]]
            v0, v1 = (x0 - x, y0 - y), (x1 - x, y1 - y)
            m0, m1 = math.hypot(*v0), math.hypot(*v1)
            if m0 == 0.0 or m1 == 0.0:
                continue
            dot = (v0[0] * v1[0] + v0[1] * v1[1]) / (m0 * m1)
            if abs(dot + 1.0) >= eps:
                continue
            incident = [k for k, e in enumerate(edges) if v in (e[0], e[1])]
            if len(incident) != 2:
                continue
            asns = {edges[k][2] for k in incident}
            if len(asns) > 1:
                continue  # different assignments: keep the vertex
            angs = [edges[k][3] for k in incident if edges[k][3] is not None]
            ang = sum(angs) / len(angs) if angs else None
            for k in sorted(incident, reverse=True):
                del edges[k]
            edges.append([nbrs[0], nbrs[1], asns.pop(), ang])
            removed[v] = True
            merged_any = True
        edges = [tuple(e) for e in edges]
        if any(removed):
            verts, edges, _ = _remap_vertices(verts, edges, [not r for r in removed])
        if not merged_any:
            return verts, edges


def _planar_faces(verts, edges):
    """Faces of the planar graph: at each vertex sort neighbors by angle, then
    traverse next[(u,v)] = neighbor before u in v's sorted list; keep faces
    with positive orientation (drops the outer face)."""
    vv = _vertices_vertices(len(verts), edges)
    for v, nbrs in enumerate(vv):
        ox, oy = verts[v]
        nbrs.sort(key=lambda u: math.atan2(verts[u][1] - oy, verts[u][0] - ox))
    nxt: dict[tuple[int, int], int | None] = {}
    for v, nbrs in enumerate(vv):
        n = len(nbrs)
        for i, u in enumerate(nbrs):
            nxt[(u, v)] = nbrs[(i - 1) % n]
    faces = []
    for uv in list(nxt.keys()):
        w = nxt[uv]
        if w is None:
            continue
        nxt[uv] = None
        u, v = uv
        face = [u, v]
        while w != face[0]:
            if w is None:
                break
            face.append(w)
            u, v = v, w
            w = nxt.get((u, v))
            nxt[(u, v)] = None
        nxt[(face[-1], face[0])] = None
        if w is not None:
            area2 = sum(
                verts[face[k]][0] * verts[face[(k + 1) % len(face)]][1]
                - verts[face[(k + 1) % len(face)]][0] * verts[face[k]][1]
                for k in range(len(face))
            )
            if area2 > 0:
                faces.append(face)
    return faces


def _remove_border_faces(faces, edges):
    """Drop faces bounded entirely by border edges (holes in the pattern)."""
    edge_assignment = {}
    for a, b, asn, _ in edges:
        edge_assignment[(a, b) if a < b else (b, a)] = asn
    out = []
    for face in faces:
        all_border = True
        for k in range(len(face)):
            a, b = face[k], face[(k + 1) % len(face)]
            asn = edge_assignment.get((a, b) if a < b else (b, a))
            if asn != "B":
                all_border = False
                break
        if not all_border:
            out.append(face)
    return out


# ------------------------------------------------------------------ public API


def svg_to_fold(svg: str, vert_tol: float = VERT_TOL) -> dict:
    """Import an origami crease-pattern SVG; returns a FOLD dict (2D, polygon
    faces) suitable for origami.model.load_fold. `svg` is a path or an SVG
    string. Extra keys: "ignored_strokes", "warnings"."""
    text = svg if svg.lstrip().startswith("<") else open(svg, encoding="utf-8-sig").read()
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text)
    root = ET.fromstring(text)
    css_rules = _parse_style_blocks(root)
    warnings: list[str] = []
    ignored: set[str] = set()

    # collect drawable elements with their ancestor transform chains, skipping
    # <symbol> and <defs> content like the original. Each color pass parses
    # element kinds in the original's fixed order (paths, lines, rects,
    # polygons, polylines), so group by kind here.
    kind_order = ("path", "line", "rect", "polygon", "polyline")
    by_kind: dict[str, list] = {k: [] for k in kind_order}  # (element, transforms)

    def walk(el, chain):
        tag = _localname(el.tag)
        if tag in ("symbol", "defs", "style"):
            return
        own = _parse_transform(el.get("transform"))
        if tag in by_kind:
            by_kind[tag].append((el, own + chain))
        for child in el:
            walk(child, own + chain)

    walk(root, [])
    elements = [pair for kind in kind_order for pair in by_kind[kind]]

    verts: list[tuple[float, float]] = []
    edges: list[tuple[int, int, str, float | None]] = []  # (a, b, assignment, angle)
    for typ, assignment in _TYPE_ASSIGNMENT:
        for el, chain in elements:
            stroke_type = _stroke_type(el, css_rules)
            if stroke_type != typ:
                if stroke_type is not None and stroke_type not in _COLOR_TYPES:
                    ignored.add(stroke_type)
                continue
            if assignment == "M":
                angle = -_opacity(el, css_rules) * 180.0
            elif assignment == "V":
                angle = _opacity(el, css_rules) * 180.0
            elif assignment == "F":
                angle = 0.0
            else:
                angle = None
            local_verts, local_segs = _element_geometry(el, warnings)
            base = len(verts)
            verts.extend(_apply_transforms(p, chain) for p in local_verts)
            edges.extend((base + a, base + b, assignment, angle) for a, b in local_segs)

    if not verts or not edges:
        raise SVGImportError("no valid geometry found in SVG (check stroke colors)")
    if any(e[2] == "C" for e in edges):
        raise SVGImportError("cut ('C', green) edges are not supported by this importer")

    verts, edges = _collapse_nearby_vertices(verts, edges, vert_tol)
    edges = _dedupe_edges(edges)
    verts, edges = _find_intersections(list(verts), edges, vert_tol)
    verts, edges = _collapse_nearby_vertices(verts, edges, vert_tol)
    edges = _dedupe_edges(edges)

    # strays, then collinear degree-2 dissolve
    vv = _vertices_vertices(len(verts), edges)
    verts, edges, _ = _remap_vertices(verts, edges, [len(n) > 0 for n in vv])
    verts, edges = _remove_redundant_vertices(verts, edges, REDUNDANT_EPS)

    faces = _planar_faces(verts, edges)
    faces = _remove_border_faces(faces, edges)
    faces = [face[::-1] for face in faces]  # original reverses to CCW for y-up

    return {
        "file_spec": 1.1,
        "file_creator": "origami-jax svg_import",
        "frame_classes": ["creasePattern"],
        "vertices_coords": [list(v) for v in verts],
        "edges_vertices": [[a, b] for a, b, _, _ in edges],
        "edges_assignment": [asn for _, _, asn, _ in edges],
        "edges_foldAngle": [ang for _, _, _, ang in edges],
        "faces_vertices": faces,
        "ignored_strokes": sorted(ignored),
        "warnings": warnings,
    }

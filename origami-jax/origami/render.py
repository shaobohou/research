"""Pure-NumPy software renderer replicating OrigamiSimulator's three.js (r87) view.

Replicates, per the original threeView.js / model.js:
  - PerspectiveCamera fov 60, near 0.1, far 500, zoom 7, at (5,5,5) looking at origin
  - six white directional lights
  - front faces: MeshPhongMaterial flatShading color #ec008b (specular #111111,
    shininess 30), back faces: same with color #dddddd, normals flipped viewer-facing
    (three.js flat shading derives normals from screen-space derivatives)
  - polygonOffset factor 0.5 / units 1 on the mesh, so the black 1px crease/boundary
    lines (LineBasicMaterial) drawn on the surface pass the LEQUAL depth test
  - white background, no gamma correction / tone mapping (three.js r87 defaults)
  - antialias=true: emulated as 4-sample MSAA (Vulkan/D3D standard sample
    locations, shading once per pixel at the pixel center, per-sample depth),
    which is what chromium/SwiftShader does for a WebGL canvas.

Lighting follows three.js r87 meshphong shaders (legacy, non-physically-correct):
  diffuse  += dotNL * lightColor * diffuseColor
  specular += dotNL * lightColor * F_Schlick(spec, dotLH) * 0.25
              * (shininess*0.5 + 1) * dotNH^shininess
"""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------- scene constants

CAMERA = dict(
    fov=60.0, near=0.1, far=500.0, zoom=7.0, position=(5.0, 5.0, 5.0), target=(0.0, 0.0, 0.0), up=(0.0, 1.0, 0.0)
)

LIGHTS = [  # (position -> direction, intensity), all white, from threeView.js
    ((0.0, 100.0, 0.0), 0.8),
    ((0.0, -100.0, 0.0), 0.3),
    ((100.0, -30.0, 0.0), 0.8),
    ((-100.0, -30.0, 0.0), 0.8),
    ((0.0, 30.0, 100.0), 0.3),
    ((0.0, 30.0, -100.0), 0.3),
]

FRONT_COLOR = "ec008b"
BACK_COLOR = "dddddd"
SPECULAR = 0x11 / 255.0
SHININESS = 30.0
POLY_OFFSET_FACTOR = 0.5
POLY_OFFSET_UNITS = 1.0
DEPTH_EPS = 2.0**-24  # minimum resolvable depth diff (24-bit depth buffer)

# 4x MSAA sample locations: standard Vulkan/D3D rotated-grid pattern, y-flipped
# into our image (y-down) coordinates -- empirically the best match against
# chromium/SwiftShader MSAA output
MSAA4_OFFSETS = np.array([(0.375, 0.875), (0.875, 0.625), (0.125, 0.375), (0.625, 0.125)])


def hex_to_rgb(h: str) -> np.ndarray:
    return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float64) / 255.0


# ---------------------------------------------------------------- camera matrices


def look_at_inverse(eye, target, up) -> np.ndarray:
    """three.js Object3D.lookAt camera convention -> matrixWorldInverse (view matrix)."""
    eye, target, up = map(np.asarray, (eye, target, up))
    z = eye - target
    z = z / np.linalg.norm(z)
    x = np.cross(up, z)
    x = x / np.linalg.norm(x)
    y = np.cross(z, x)
    view = np.eye(4)
    view[:3, :3] = np.stack([x, y, z])  # R^T
    view[:3, 3] = -view[:3, :3] @ eye
    return view


def perspective_matrix(fov, aspect, near, far, zoom) -> np.ndarray:
    """three.js r87 PerspectiveCamera.updateProjectionMatrix()."""
    top = near * np.tan(np.radians(0.5 * fov)) / zoom
    height = 2.0 * top
    width = aspect * height
    left = -0.5 * width
    right, bottom = left + width, top - height
    m = np.zeros((4, 4))
    m[0, 0] = 2 * near / (right - left)
    m[0, 2] = (right + left) / (right - left)
    m[1, 1] = 2 * near / (top - bottom)
    m[1, 2] = (top + bottom) / (top - bottom)
    m[2, 2] = -(far + near) / (far - near)
    m[2, 3] = -2 * far * near / (far - near)
    m[3, 2] = -1.0
    return m


def default_camera(width: int, height: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (view, projection, camera_position) matching the original app."""
    view = look_at_inverse(CAMERA["position"], CAMERA["target"], CAMERA["up"])
    proj = perspective_matrix(CAMERA["fov"], width / height, CAMERA["near"], CAMERA["far"], CAMERA["zoom"])
    return view, proj, np.asarray(CAMERA["position"], dtype=np.float64)


# ---------------------------------------------------------------- shading


def _shade(world_pos, normal, mat_rgb, camera_pos, light_dirs, light_int):
    """three.js r87 MeshPhongMaterial (BlinnPhong) for white directional lights.

    world_pos: (P,3) fragment positions; normal: (3,) flat face normal.
    Returns (P,3) linear colors (unclamped)."""
    view_dir = camera_pos[None] - world_pos
    view_dir /= np.linalg.norm(view_dir, axis=1, keepdims=True)
    dot_nl = np.clip(light_dirs @ normal, 0.0, 1.0)  # (L,)
    irradiance = dot_nl * light_int  # (L,)
    half = light_dirs[None] + view_dir[:, None]  # (P,L,3)
    half /= np.linalg.norm(half, axis=2, keepdims=True)
    dot_nh = np.clip(half @ normal, 0.0, 1.0)  # (P,L)
    dot_lh = np.clip(np.sum(half * light_dirs[None], axis=2), 0.0, 1.0)
    fresnel = SPECULAR + (1.0 - SPECULAR) * np.exp2((-5.55473 * dot_lh - 6.98316) * dot_lh)
    spec = (irradiance[None] * fresnel * 0.25 * (SHININESS * 0.5 + 1.0) * dot_nh**SHININESS).sum(axis=1)
    return irradiance.sum() * mat_rgb[None] + spec[:, None]


# ---------------------------------------------------------------- rasterization


def _project(positions, view, proj, width, height):
    """world -> (screen xy in pixels, window z in [0,1], clip w)."""
    n = positions.shape[0]
    hom = np.concatenate([positions, np.ones((n, 1))], axis=1)
    clip = hom @ (proj @ view).T
    w = clip[:, 3]
    ndc = clip[:, :3] / w[:, None]
    sx = (ndc[:, 0] + 1.0) * 0.5 * width
    sy = (1.0 - ndc[:, 1]) * 0.5 * height
    zwin = (ndc[:, 2] + 1.0) * 0.5
    return np.stack([sx, sy], axis=1), zwin, w


def render(
    positions: np.ndarray,
    faces: np.ndarray,
    line_segments: np.ndarray | None = None,
    width: int = 800,
    height: int = 600,
    view: np.ndarray | None = None,
    proj: np.ndarray | None = None,
    camera_pos: np.ndarray | None = None,
    front_color: str = FRONT_COLOR,
    back_color: str = BACK_COLOR,
    background: str = "ffffff",
    sample_offsets: np.ndarray = MSAA4_OFFSETS,
) -> np.ndarray:
    """Render the model; returns (height, width, 3) uint8 image."""
    if view is None or proj is None or camera_pos is None:
        view, proj, camera_pos = default_camera(width, height)
    W, H = width, height
    S = len(sample_offsets)
    off_x = sample_offsets[:, 0]
    off_y = sample_offsets[:, 1]

    color = np.empty((H, W, S, 3), dtype=np.float64)
    color[:] = hex_to_rgb(background)
    depth = np.ones((H, W, S), dtype=np.float64)

    positions = np.asarray(positions, dtype=np.float64)
    xy, zwin, clip_w = _project(positions, view, proj, width, height)

    front_rgb = hex_to_rgb(front_color)
    back_rgb = hex_to_rgb(back_color)
    light_dirs = np.array([p for p, _ in LIGHTS], dtype=np.float64)
    light_dirs /= np.linalg.norm(light_dirs, axis=1, keepdims=True)
    light_int = np.array([i for _, i in LIGHTS], dtype=np.float64)

    tri_xy = xy[faces]  # (F,3,2)
    tri_z = zwin[faces]  # (F,3)
    tri_w = clip_w[faces]  # (F,3)
    tri_world = positions[faces]

    a2 = np.cross(tri_xy[:, 1] - tri_xy[:, 0], tri_xy[:, 2] - tri_xy[:, 0])
    # screen y points down here; GL front-facing (CCW in GL window coords) => a2 < 0
    is_front = a2 < 0.0

    n_geo = np.cross(tri_world[:, 1] - tri_world[:, 0], tri_world[:, 2] - tri_world[:, 0])
    n_geo /= np.maximum(np.linalg.norm(n_geo, axis=1, keepdims=True), 1e-30)

    # draw order = original: frontside mesh (front-facing tris), then backside mesh
    order = np.concatenate([np.nonzero(is_front)[0], np.nonzero(~is_front)[0]])

    for fi in order:
        v = tri_xy[fi]
        area2 = a2[fi]
        if area2 == 0.0 or np.any(tri_w[fi] <= 0.0):
            continue
        front = is_front[fi]
        xmin = max(int(np.floor(v[:, 0].min())), 0)
        xmax = min(int(np.ceil(v[:, 0].max())), W - 1)
        ymin = max(int(np.floor(v[:, 1].min())), 0)
        ymax = min(int(np.ceil(v[:, 1].max())), H - 1)
        if xmin > xmax or ymin > ymax:
            continue
        nx, ny = xmax - xmin + 1, ymax - ymin + 1
        gx = np.arange(xmin, xmax + 1)
        gy = np.arange(ymin, ymax + 1)
        # sample positions: (ny, nx, S)
        sx = gx[None, :, None] + off_x[None, None, :]
        sy = gy[:, None, None] + off_y[None, None, :]

        # edge functions / barycentric at every sample
        lam = np.empty((3, ny, nx, S))
        for k in range(3):
            i, j = (k + 1) % 3, (k + 2) % 3
            lam[k] = ((v[i, 0] - sx) * (v[j, 1] - sy) - (v[i, 1] - sy) * (v[j, 0] - sx)) / area2
        covered = (lam >= 0.0).all(axis=0)  # (ny,nx,S)
        if not covered.any():
            continue

        # depth plane (window z linear in screen space) + polygon offset
        plane = np.linalg.lstsq(np.concatenate([v, np.ones((3, 1))], axis=1), tri_z[fi], rcond=None)[0]
        m = max(abs(plane[0]), abs(plane[1]))
        offset = POLY_OFFSET_FACTOR * m + POLY_OFFSET_UNITS * DEPTH_EPS

        pix_any = covered.any(axis=2)  # (ny,nx) pixels needing shading
        py, px = np.nonzero(pix_any)

        # shade once per pixel at the pixel center (MSAA-style)
        cx = px + xmin + 0.5
        cy = py + ymin + 0.5
        lam_c = np.empty((3, len(px)))
        for k in range(3):
            i, j = (k + 1) % 3, (k + 2) % 3
            lam_c[k] = ((v[i, 0] - cx) * (v[j, 1] - cy) - (v[i, 1] - cy) * (v[j, 0] - cx)) / area2
        inv_w = lam_c.T @ (1.0 / tri_w[fi])
        world = (lam_c.T @ (tri_world[fi] / tri_w[fi][:, None])) / inv_w[:, None]
        nrm = n_geo[fi] if front else -n_geo[fi]
        mat = front_rgb if front else back_rgb
        rgb = np.clip(_shade(world, nrm, mat, camera_pos, light_dirs, light_int), 0.0, 1.0)

        # per-sample depth test + write
        for s in range(S):
            cov_s = covered[py, px, s]
            if not cov_s.any():
                continue
            ps_y = py[cov_s] + ymin
            ps_x = px[cov_s] + xmin
            z = plane[0] * (ps_x + off_x[s]) + plane[1] * (ps_y + off_y[s]) + plane[2] + offset
            ok = z <= depth[ps_y, ps_x, s]
            depth[ps_y[ok], ps_x[ok], s] = z[ok]
            color[ps_y[ok], ps_x[ok], s] = rgb[cov_s][ok]

    # ---- 1px black lines (LineBasicMaterial), depth-tested LEQUAL, no offset ----
    if line_segments is not None and len(line_segments):
        seg_xy = xy[line_segments]  # (n,2,2)
        seg_z = zwin[line_segments]  # (n,2)
        half_w = 0.5
        for si in range(len(seg_xy)):
            p0, p1 = seg_xy[si]
            z0, z1 = seg_z[si]
            t_dir = p1 - p0
            length = np.hypot(*t_dir)
            if length == 0.0:
                continue
            t_dir = t_dir / length
            n_dir = np.array([-t_dir[1], t_dir[0]])
            xmin = max(int(np.floor(min(p0[0], p1[0]) - half_w)), 0)
            xmax = min(int(np.ceil(max(p0[0], p1[0]) + half_w)), W - 1)
            ymin = max(int(np.floor(min(p0[1], p1[1]) - half_w)), 0)
            ymax = min(int(np.ceil(max(p0[1], p1[1]) + half_w)), H - 1)
            if xmin > xmax or ymin > ymax:
                continue
            gx = np.arange(xmin, xmax + 1)
            gy = np.arange(ymin, ymax + 1)
            sx = gx[None, :, None] + off_x[None, None, :]
            sy = gy[:, None, None] + off_y[None, None, :]
            relx = sx - p0[0]
            rely = sy - p0[1]
            along = relx * t_dir[0] + rely * t_dir[1]
            across = relx * n_dir[0] + rely * n_dir[1]
            covered = (np.abs(across) <= half_w) & (along >= 0.0) & (along <= length)
            if not covered.any():
                continue
            iy, ix, isamp = np.nonzero(covered)
            z = z0 + (z1 - z0) * (along[covered] / length)
            ys = iy + ymin
            xs = ix + xmin
            ok = z <= depth[ys, xs, isamp]
            depth[ys[ok], xs[ok], isamp[ok]] = z[ok]
            color[ys[ok], xs[ok], isamp[ok]] = 0.0

    img = color.mean(axis=2)  # MSAA resolve
    return np.clip(np.round(img * 255.0), 0, 255).astype(np.uint8)


def visible_line_segments(model_lines: dict[str, np.ndarray]) -> np.ndarray:
    """Default-visible line sets: mountains, valleys, boundary (globals.js defaults)."""
    parts = [model_lines[k] for k in ("M", "V", "B") if len(model_lines.get(k, []))]
    if not parts:
        return np.zeros((0, 2), dtype=np.int32)
    return np.concatenate(parts, axis=0)

"""JAX reimplementation of OrigamiSimulator's compliant-dynamics folding solver.

Algorithm reference: amandaghassaei/OrigamiSimulator (MIT), js/dynamic/dynamicSolver.js
and the GLSL passes in index.html (normalCalc, thetaCalc, updateCreaseGeo,
velocityCalc, positionCalc), i.e. the solver described in Ghassaei et al.,
"Fast, Interactive Origami Simulation using GPU Computation" (7OSME 2018).

The GPU version loops over a node's incident beams/creases/faces inside one
fragment shader. Here the same forces are computed per-edge / per-crease /
per-face and scatter-added to nodes, which is mathematically identical
(everything is read from last positions/velocities, Jacobi style) and maps
naturally onto XLA. Everything is float32, like the GPU textures.

State: positions p (absolute), velocities v, unwrapped crease angles theta.
Explicit Euler integration (the original's default).
"""
from __future__ import annotations

from functools import partial
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from .model import OrigamiModel

TWO_PI = 6.283185307179586
GEO_TOL = 1e-6   # crease degeneracy tolerance (updateCreaseGeo shader)
FACE_TOL = 1e-7  # face edge-length tolerance (velocityCalc shader)


class SolverState(NamedTuple):
    pos: jnp.ndarray    # (N,3) float32
    vel: jnp.ndarray    # (N,3) float32
    theta: jnp.ndarray  # (C,)  float32 unwrapped dihedral angles


class SolverConstants(NamedTuple):
    pos0: jnp.ndarray
    mass: jnp.ndarray
    fixed: jnp.ndarray
    edge_i: jnp.ndarray     # (2E,) both directions
    edge_j: jnp.ndarray
    edge_k: jnp.ndarray
    edge_d: jnp.ndarray
    edge_l0: jnp.ndarray
    faces: jnp.ndarray
    nominal_angles: jnp.ndarray
    face_stiffness: jnp.ndarray
    crease_faces: jnp.ndarray
    crease_nodes: jnp.ndarray
    crease_k: jnp.ndarray
    crease_target: jnp.ndarray
    dt: jnp.ndarray


def make_constants(model: OrigamiModel, face_stiffness: float = 0.2) -> SolverConstants:
    e0, e1 = model.edges[:, 0], model.edges[:, 1]
    return SolverConstants(
        pos0=jnp.asarray(model.pos0),
        mass=jnp.asarray(model.mass),
        fixed=jnp.asarray(model.fixed),
        edge_i=jnp.concatenate([jnp.asarray(e0), jnp.asarray(e1)]),
        edge_j=jnp.concatenate([jnp.asarray(e1), jnp.asarray(e0)]),
        edge_k=jnp.concatenate([jnp.asarray(model.edge_k)] * 2),
        edge_d=jnp.concatenate([jnp.asarray(model.edge_d)] * 2),
        edge_l0=jnp.concatenate([jnp.asarray(model.edge_l0)] * 2),
        faces=jnp.asarray(model.faces),
        nominal_angles=jnp.asarray(model.nominal_angles),
        face_stiffness=jnp.float32(face_stiffness),
        crease_faces=jnp.asarray(model.crease_faces),
        crease_nodes=jnp.asarray(model.crease_nodes),
        crease_k=jnp.asarray(model.crease_k),
        crease_target=jnp.asarray(model.crease_target),
        dt=jnp.float32(model.dt),
    )


def init_state(model: OrigamiModel) -> SolverState:
    n_creases = model.crease_k.shape[0]
    return SolverState(
        pos=jnp.asarray(model.pos0),
        vel=jnp.zeros((model.num_nodes, 3), jnp.float32),
        theta=jnp.zeros((n_creases,), jnp.float32),
    )


def _normalize(v, eps=0.0):
    return v / jnp.linalg.norm(v, axis=-1, keepdims=True)


def step(c: SolverConstants, state: SolverState, crease_percent) -> SolverState:
    p, v, last_theta = state

    # ---- face normals (normalCalc) ----
    fa, fb, fc = p[c.faces[:, 0]], p[c.faces[:, 1]], p[c.faces[:, 2]]
    normals = _normalize(jnp.cross(fb - fa, fc - fa))

    # ---- dihedral angles (thetaCalc) ----
    n1 = normals[c.crease_faces[:, 0]]
    n2 = normals[c.crease_faces[:, 1]]
    p3 = p[c.crease_nodes[:, 2]]
    p4 = p[c.crease_nodes[:, 3]]
    crease_vec = _normalize(p4 - p3)
    x = jnp.clip(jnp.sum(n1 * n2, axis=-1), -1.0, 1.0)
    y = jnp.sum(jnp.cross(n1, crease_vec) * n2, axis=-1)
    theta = jnp.arctan2(y, x)
    diff = theta - last_theta
    diff = jnp.where(diff < -5.0, diff + TWO_PI, jnp.where(diff > 5.0, diff - TWO_PI, diff))
    theta = last_theta + diff

    # ---- crease geometry (updateCreaseGeo) ----
    p1 = p[c.crease_nodes[:, 0]]
    p2 = p[c.crease_nodes[:, 1]]
    cv = p4 - p3
    crease_len = jnp.linalg.norm(cv, axis=-1)
    safe_len = jnp.where(crease_len < GEO_TOL, 1.0, crease_len)
    cvn = cv / safe_len[:, None]
    v1 = p1 - p3
    v2 = p2 - p3
    proj1 = jnp.sum(cvn * v1, axis=-1)
    proj2 = jnp.sum(cvn * v2, axis=-1)
    h1 = jnp.sqrt(jnp.abs(jnp.sum(v1 * v1, axis=-1) - proj1 * proj1))
    h2 = jnp.sqrt(jnp.abs(jnp.sum(v2 * v2, axis=-1) - proj2 * proj2))
    enabled = (crease_len >= GEO_TOL) & (h1 >= GEO_TOL) & (h2 >= GEO_TOL)
    h1 = jnp.where(enabled, h1, 1.0)
    h2 = jnp.where(enabled, h2, 1.0)
    coef1 = proj1 / safe_len
    coef2 = proj2 / safe_len

    force = jnp.zeros_like(p)

    # ---- axial beams ----
    dp = p[c.edge_j] - p[c.edge_i]
    dist = jnp.linalg.norm(dp, axis=-1, keepdims=True)
    f_beam = dp * (1.0 - c.edge_l0[:, None] / dist) * c.edge_k[:, None] \
        + (v[c.edge_j] - v[c.edge_i]) * c.edge_d[:, None]
    force = force.at[c.edge_i].add(f_beam)

    # ---- crease angular springs ----
    target = c.crease_target * crease_percent
    ang_force = jnp.where(enabled, c.crease_k * (target - theta), 0.0)
    f1 = (ang_force / h1)[:, None] * n1
    f2 = (ang_force / h2)[:, None] * n2
    force = force.at[c.crease_nodes[:, 0]].add(f1)
    force = force.at[c.crease_nodes[:, 1]].add(f2)
    force = force.at[c.crease_nodes[:, 2]].add(
        -((1.0 - coef1)[:, None] * f1 + (1.0 - coef2)[:, None] * f2))
    force = force.at[c.crease_nodes[:, 3]].add(
        -(coef1[:, None] * f1 + coef2[:, None] * f2))

    # ---- face angular constraints ----
    ab = fb - fa
    ac = fc - fa
    bc = fc - fb
    lab = jnp.linalg.norm(ab, axis=-1)
    lac = jnp.linalg.norm(ac, axis=-1)
    lbc = jnp.linalg.norm(bc, axis=-1)
    ok = (lab >= FACE_TOL) & (lac >= FACE_TOL) & (lbc >= FACE_TOL)
    lab = jnp.where(ok, lab, 1.0)
    lac = jnp.where(ok, lac, 1.0)
    lbc = jnp.where(ok, lbc, 1.0)
    uab = ab / lab[:, None]
    uac = ac / lac[:, None]
    ubc = bc / lbc[:, None]
    dot = lambda u, w: jnp.clip(jnp.sum(u * w, axis=-1), -1.0, 1.0)
    angles = jnp.stack(
        [jnp.arccos(dot(uab, uac)), jnp.arccos(-dot(uab, ubc)), jnp.arccos(dot(uac, ubc))],
        axis=-1)
    a_diff = (c.nominal_angles - angles) * c.face_stiffness * ok[:, None]
    n_x_ab = jnp.cross(normals, uab) / lab[:, None]
    n_x_ac = jnp.cross(normals, uac) / lac[:, None]
    n_x_bc = jnp.cross(normals, ubc) / lbc[:, None]
    d0, d1, d2 = a_diff[:, 0:1], a_diff[:, 1:2], a_diff[:, 2:3]
    f_a = -d0 * (n_x_ac - n_x_ab) - d1 * n_x_ab + d2 * n_x_ac
    f_b = -d0 * n_x_ab + d1 * (n_x_ab + n_x_bc) - d2 * n_x_bc
    f_c = d0 * n_x_ac - d1 * n_x_bc + d2 * (n_x_bc - n_x_ac)
    force = force.at[c.faces[:, 0]].add(f_a)
    force = force.at[c.faces[:, 1]].add(f_b)
    force = force.at[c.faces[:, 2]].add(f_c)

    # ---- explicit Euler (velocityCalc + positionCalc) ----
    v_new = v + force * c.dt / c.mass[:, None]
    v_new = jnp.where(c.fixed[:, None], 0.0, v_new)
    p_new = jnp.where(c.fixed[:, None], p, p + v_new * c.dt)
    return SolverState(p_new, v_new, theta)


@partial(jax.jit, static_argnames="n_steps", donate_argnames="state")
def simulate(c: SolverConstants, state: SolverState, crease_percent, n_steps: int) -> SolverState:
    crease_percent = jnp.float32(crease_percent)
    return jax.lax.fori_loop(
        0, n_steps, lambda _, s: step(c, s, crease_percent), state)


def fold_to_percent(
    model: OrigamiModel,
    crease_percent: float,
    n_steps: int = 3000,
    face_stiffness: float = 0.2,
    state: SolverState | None = None,
) -> SolverState:
    """Convenience wrapper: (re)start from flat and fold to a target percent."""
    c = make_constants(model, face_stiffness)
    if state is None:
        state = init_state(model)
    return simulate(c, state, crease_percent, n_steps)

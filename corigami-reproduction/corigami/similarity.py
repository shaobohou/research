"""Tree similarity score via Procrustes analysis (paper Appendix C.2).

The joints common to the target stick figure and a folded/shaped model are
centred, normalised to unit Frobenius norm (scale invariance), and aligned
with the optimal rotation from SVD. The score is 1 - d^2 where d is the
Procrustes distance, equivalently trace(Sigma)^2 for the singular values of
the cross-covariance; 1.0 is a perfect geometric match under rigid motion.
"""

from __future__ import annotations

import numpy as np


def tree_similarity(target: np.ndarray, model: np.ndarray) -> float:
    """Both inputs are (n, 3) arrays of corresponding joint coordinates."""
    if target.shape != model.shape or target.ndim != 2:
        raise ValueError("point sets must have identical (n, d) shapes")
    a = target - target.mean(axis=0)
    b = model - model.mean(axis=0)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    a, b = a / na, b / nb
    s = np.linalg.svd(a.T @ b, compute_uv=False)
    # d^2 = 1 - trace(Sigma)^2  =>  score = trace(Sigma)^2
    return float(np.clip(s.sum() ** 2, 0.0, 1.0))

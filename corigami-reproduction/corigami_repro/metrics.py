"""Evaluation metrics, matching the official C.Origami metrics.

Includes the insulation score (used to call TAD boundaries) and the correlation
metrics the paper reports (per-map Pearson, distance-stratified correlation,
insulation-score correlation, observed-vs-expected correlation).
"""

import numpy as np
from scipy.stats import pearsonr


def mse(preds, targets):
    return ((preds - targets) ** 2).mean(axis=(1, 2)).astype(float)


def insulation_score(matrix, res=64, radius=320, pseudocount_coeff=30):
    """Sliding-diamond insulation score (official insulation_score.chr_score).

    Low score => strong insulation => TAD boundary. Default radius scaled to the
    synthetic resolution (paper uses 500 kb at 10 kb res).
    """
    pseudocount = matrix.mean() * pseudocount_coeff
    pixel_radius = max(1, int(radius / res))
    scores = []
    n = len(matrix)
    for loc in range(n):
        lo = max(loc - pixel_radius, 0)
        hi = min(loc + pixel_radius, n)
        left = matrix[lo:loc, lo:loc]
        right = matrix[loc:hi, loc:hi]
        center = matrix[lo:loc, loc:hi]
        left_m = left.mean() if left.size else 0.0
        right_m = right.mean() if right.size else 0.0
        center_m = center.mean() if center.size else 0.0
        scores.append((max(left_m, right_m) + pseudocount) / (center_m + pseudocount))
    return np.array(scores)


def map_pearson(preds, targets):
    """Per-map flattened Pearson correlation."""
    out = []
    for p, t in zip(preds, targets):
        out.append(pearsonr(p.reshape(-1), t.reshape(-1))[0])
    return np.array(out)


def insulation_pearson(preds, targets, res=64):
    out = []
    for p, t in zip(preds, targets):
        ip, it = insulation_score(p, res), insulation_score(t, res)
        nas = np.logical_or(np.isnan(ip), np.isnan(it))
        out.append(np.nan if nas.all() else pearsonr(ip[~nas], it[~nas])[0])
    return np.array(out)


def observed_vs_expected(preds, targets):
    """Pearson after removing the distance-averaged (expected) map across a set."""
    pm = preds.mean(axis=0, keepdims=True)
    tm = targets.mean(axis=0, keepdims=True)
    out = []
    for p, t in zip(preds - pm, targets - tm):
        out.append(pearsonr(p.reshape(-1), t.reshape(-1))[0])
    return np.array(out)


def distance_stratified_correlation(preds, targets):
    """Pearson per genomic distance (diagonal offset), averaged over maps."""
    n = preds.shape[1]
    per_offset = [[] for _ in range(n)]
    for p, t in zip(preds, targets):
        for d in range(n):
            pd, td = np.diagonal(p, d), np.diagonal(t, d)
            if len(pd) < 2 or pd.std() == 0 or td.std() == 0:
                continue
            per_offset[d].append(pearsonr(pd, td)[0])
    return np.array([np.mean(v) if v else np.nan for v in per_offset])


def summarize(preds, targets, res=64):
    return {
        "mse": float(mse(preds, targets).mean()),
        "map_pearson": float(np.nanmean(map_pearson(preds, targets))),
        "insulation_pearson": float(np.nanmean(insulation_pearson(preds, targets, res))),
        "obs_vs_exp": float(np.nanmean(observed_vs_expected(preds, targets))),
    }

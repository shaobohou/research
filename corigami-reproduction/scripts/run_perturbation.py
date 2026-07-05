"""In-silico perturbation demo: reproduce C.Origami's headline causal result.

Loads the trained model and, on a held-out synthetic chromosome:
  1. Deletion — delete a CTCF-bound TAD boundary and show the neighbouring TADs
     fuse in the predicted contact map (the paper's key finding).
  2. Screening — slide a fixed-width deletion across a region and show the impact
     score peaks precisely at CTCF boundaries, recovering boundary locations de
     novo from the model's sensitivity.

    python scripts/run_perturbation.py
"""

import json
import os

import numpy as np
import torch

from corigami_repro import inference, plotting
from corigami_repro.data import SyntheticGenome
from corigami_repro.model import build_model

OUT = os.path.join(os.path.dirname(__file__), "..", "outputs")


def load_model(device):
    ckpt = torch.load(os.path.join(OUT, "model_checkpoint.pt"), map_location=device, weights_only=False)
    model = build_model(**ckpt["config"])
    model.load_state_dict(ckpt["state_dict"])
    model.to(device).eval()
    return model, ckpt["window_bp"], ckpt["res"]


def pick_interior_boundary(genome, window_bp, res):
    """Choose a strong CTCF boundary comfortably inside a window."""
    margin = window_bp // res
    cands = genome.boundaries[(genome.boundaries > 2 * margin) & (genome.boundaries < genome.n_bins - 2 * margin)]
    # boundary with the largest local CTCF peak
    strengths = [genome.ctcf[int(b * res)] for b in cands]
    return int(cands[int(np.argmax(strengths))])


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, window_bp, res = load_model(device)
    genome = SyntheticGenome("chr_test", length_bp=150_000, res=res, seed=200)
    map_size = model.map_size
    print(f"window_bp={window_bp} res={res} map={map_size}")

    # ---- 1. Single-boundary deletion ----------------------------------------
    b = pick_interior_boundary(genome, window_bp, res)
    boundary_bp = b * res
    # Centre a window so the boundary sits near the middle of the map.
    start = boundary_bp - window_bp // 2
    del_width = res * 3  # delete ~3 bins around the site
    del_start = boundary_bp - del_width // 2
    del_bin_in_map = int((boundary_bp - start) / window_bp * map_size)

    pred_ref, pred_del, diff = inference.delete_and_predict(
        model, genome, start, del_start, del_width, window_bp, device
    )
    plotting.plot_deletion(
        pred_ref,
        pred_del,
        os.path.join(OUT, "deletion_boundary.png"),
        del_bin=del_bin_in_map,
        title=f"Delete CTCF boundary at {boundary_bp:,} bp -> TADs fuse (mean |Δ|={np.abs(diff).mean():.4f})",
    )

    # Clean quantitative contrast via in-place ablation (no shift artifact):
    # ablate the boundary CTCF site vs an equal-width non-boundary control.
    ctrl_bp = boundary_bp + window_bp // 4
    while any(abs(ctrl_bp - bb * res) < 4 * res for bb in genome.boundaries):
        ctrl_bp += res
    ab_width = res * 3
    _, _, bd_diff = inference.ablate_and_predict(
        model, genome, boundary_bp - window_bp // 2, boundary_bp - ab_width // 2, ab_width, window_bp, device
    )
    _, _, ct_diff = inference.ablate_and_predict(
        model, genome, ctrl_bp - window_bp // 2, ctrl_bp - ab_width // 2, ab_width, window_bp, device
    )
    boundary_impact = float(np.abs(bd_diff).mean())
    control_impact = float(np.abs(ct_diff).mean())
    print(
        f"boundary-ablation impact {boundary_impact:.4f} vs "
        f"control-ablation impact {control_impact:.4f} "
        f"(ratio {boundary_impact / max(control_impact, 1e-9):.1f}x)"
    )

    # ---- 2. Screening across a region ---------------------------------------
    # In-place feature ablation slid across a wide region: impact peaks should
    # localise at CTCF boundaries (recovering them de novo from model sensitivity).
    screen_start = boundary_bp - int(window_bp * 0.45)
    screen_end = boundary_bp + int(window_bp * 0.45)
    centers, impact = inference.screen(
        model,
        genome,
        screen_start,
        screen_end,
        perturb_width=res * 3,
        step_size=res,
        window_bp=window_bp,
        device=device,
        mode="ablation",
    )

    # CTCF track over the screened region for overlay.
    cx = np.arange(screen_start, screen_end)
    ctcf_track = genome.ctcf[screen_start:screen_end]
    plotting.plot_screen(
        centers,
        impact,
        os.path.join(OUT, "screening_track.png"),
        ctcf_track=ctcf_track,
        ctcf_x=cx,
        title="In-silico ablation screen: impact score peaks at CTCF boundaries",
    )

    # Quantify: correlation between impact score and local CTCF signal.
    ctcf_at_centers = np.array([genome.ctcf[int(c)] for c in centers])
    if impact.std() > 0 and ctcf_at_centers.std() > 0:
        corr = float(np.corrcoef(impact, ctcf_at_centers)[0, 1])
    else:
        corr = float("nan")
    boundaries_bp = genome.boundaries * res
    in_screen = boundaries_bp[(boundaries_bp >= screen_start) & (boundaries_bp < screen_end)]
    peak_center = int(centers[int(np.argmax(impact))])
    nearest_boundary = int(in_screen[np.argmin(np.abs(in_screen - peak_center))])
    print(
        f"impact-vs-CTCF correlation {corr:.3f}; "
        f"impact peak at {peak_center:,} bp, nearest boundary "
        f"{nearest_boundary:,} bp (|Δ|={abs(peak_center - nearest_boundary)} bp)"
    )

    report = {
        "boundary_bp": boundary_bp,
        "boundary_ablation_impact": boundary_impact,
        "control_ablation_impact": control_impact,
        "impact_ratio_boundary_over_control": boundary_impact / max(control_impact, 1e-9),
        "screen_impact_vs_ctcf_corr": corr,
        "impact_peak_bp": peak_center,
        "nearest_true_boundary_bp": nearest_boundary,
        "peak_to_boundary_dist_bp": abs(peak_center - nearest_boundary),
    }
    with open(os.path.join(OUT, "perturbation_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print("saved deletion_boundary.png, screening_track.png, perturbation_report.json")


if __name__ == "__main__":
    main()

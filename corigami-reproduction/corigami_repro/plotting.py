"""Plotting helpers: contact-map panels, deletion comparisons, screening tracks.

Uses the red 'fall'-style colormap the paper uses for Hi-C maps.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CMAP = "Reds"


def _imshow(ax, mat, title, vmax=None):
    im = ax.imshow(mat, cmap=CMAP, vmin=0, vmax=vmax, interpolation="nearest")
    ax.set_title(title, fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])
    return im


def plot_prediction(pred, target, path, title=""):
    vmax = max(pred.max(), target.max())
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6))
    _imshow(axes[0], target, "Ground truth Hi-C", vmax)
    _imshow(axes[1], pred, "C.Origami prediction", vmax)
    im = _imshow(axes[2], pred - target, "Prediction - truth")
    axes[2].images[0].set_cmap("bwr")
    lim = np.abs(pred - target).max()
    axes[2].images[0].set_clim(-lim, lim)
    if title:
        fig.suptitle(title, fontsize=11)
    fig.colorbar(im, ax=axes[2], fraction=0.046)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_deletion(pred_ref, pred_del, path, del_bin=None, title=""):
    vmax = max(pred_ref.max(), pred_del.max())
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6))
    _imshow(axes[0], pred_ref, "Reference prediction", vmax)
    _imshow(axes[1], pred_del, "After CTCF deletion", vmax)
    diff = pred_del - pred_ref
    _imshow(axes[2], diff, "Difference (del - ref)")
    axes[2].images[0].set_cmap("bwr")
    lim = np.abs(diff).max()
    axes[2].images[0].set_clim(-lim, lim)
    if del_bin is not None:
        for ax in axes[:2]:
            ax.axhline(del_bin, color="cyan", lw=0.7, ls="--")
            ax.axvline(del_bin, color="cyan", lw=0.7, ls="--")
    if title:
        fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_screen(positions_bp, impact, path, ctcf_track=None, ctcf_x=None, title="in-silico ablation screen"):
    n = 2 if ctcf_track is not None else 1
    fig, axes = plt.subplots(n, 1, figsize=(9, 2.4 * n), sharex=True, squeeze=False)
    ax = axes[0, 0]
    ax.fill_between(positions_bp, impact, color="#b22222", alpha=0.8)
    ax.set_ylabel("impact score\n(mean |Δmap|)")
    ax.set_title(title, fontsize=11)
    if ctcf_track is not None:
        axes[1, 0].fill_between(ctcf_x, ctcf_track, color="#333333")
        axes[1, 0].set_ylabel("CTCF signal")
    axes[-1, 0].set_xlabel("genomic position (bp)")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_training_curve(history, path):
    fig, ax1 = plt.subplots(figsize=(7, 4))
    ep = [h["epoch"] for h in history]
    ax1.plot(ep, [h["train_loss"] for h in history], label="train MSE", color="#1f77b4")
    ax1.plot(ep, [h["val_loss"] for h in history], label="val MSE", color="#d62728")
    ax1.set_xlabel("epoch")
    ax1.set_ylabel("MSE loss")
    ax1.legend(loc="upper right")
    ax2 = ax1.twinx()
    ax2.plot(ep, [h["val_pearson"] for h in history], label="val map Pearson", color="#2ca02c", ls="--")
    ax2.set_ylabel("val map Pearson")
    ax2.legend(loc="lower right")
    ax1.set_title("Training curve")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_synthetic_overview(genome, path, n_bins_show=200):
    """Show a synthetic chromosome: Hi-C + CTCF/ATAC tracks + boundaries."""
    n = min(n_bins_show, genome.n_bins)
    hic = np.log1p(genome.hic[:n, :n])
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), gridspec_kw={"height_ratios": [4, 1]})
    axes[0].imshow(hic, cmap=CMAP, interpolation="nearest")
    axes[0].set_title(f"Synthetic Hi-C ({genome.name}) with CTCF-defined TADs")
    for b in genome.boundaries[genome.boundaries < n]:
        axes[0].axhline(b, color="cyan", lw=0.4, alpha=0.5)
        axes[0].axvline(b, color="cyan", lw=0.4, alpha=0.5)
    axes[0].set_xticks([])
    axes[0].set_yticks([])
    bp = np.arange(n * genome.res)
    axes[1].fill_between(bp / genome.res, genome.ctcf[: n * genome.res], color="#333", label="CTCF")
    axes[1].fill_between(bp / genome.res, genome.atac[: n * genome.res], color="#2ca02c", alpha=0.5, label="ATAC")
    axes[1].set_xlabel("bin")
    axes[1].legend(loc="upper right", fontsize=8)
    axes[1].set_xlim(0, n)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)

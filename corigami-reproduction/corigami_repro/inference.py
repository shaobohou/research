"""Inference tasks: prediction, in-silico deletion (editing), and screening.

Mirrors the official corigami.inference package. `editing.deletion_with_padding`
removes a genomic interval from every input track (DNA padded with N, CTCF/ATAC
padded with 0 at the tail) and re-predicts; `screening` slides a fixed-width
deletion across a region and records an impact score = mean(|Δmap|) per position.
Operates on a SyntheticGenome standing in for the real seq/CTCF/ATAC loaders.
"""

import numpy as np
import torch


def _assemble_inputs(seq_onehot, ctcf, atac):
    """(L,5),(L,),(L,) -> torch tensor (1, L, 7) with ATAC log1p-normalised."""
    atac = np.log(np.asarray(atac) + 1.0)
    x = np.concatenate([seq_onehot, np.asarray(ctcf)[:, None], atac[:, None]], axis=1)
    return torch.tensor(x[None], dtype=torch.float32)


def _raw_window(genome, start, length):
    """Fetch raw (un-log) tracks over [start, start+length)."""
    end = start + length
    seq = genome.get_seq_onehot(start, end)
    ctcf = genome.get_track("ctcf", start, end)
    atac = genome.get_track("atac", start, end)
    return seq, ctcf, atac


@torch.no_grad()
def predict(model, genome, start, window_bp, device="cpu"):
    seq, ctcf, atac = _raw_window(genome, start, window_bp)
    inp = _assemble_inputs(seq, ctcf, atac).to(device)
    model.eval()
    return model(inp)[0].cpu().numpy()


def deletion_with_padding(seq, ctcf, atac, del_offset, del_width, window_bp):
    """Delete [del_offset, del_offset+del_width) and zero/N-pad the tail.

    Inputs cover window_bp + del_width; output is trimmed back to window_bp.
    """
    seq = np.delete(seq, np.s_[del_offset : del_offset + del_width], axis=0)
    ctcf = np.delete(ctcf, np.s_[del_offset : del_offset + del_width])
    atac = np.delete(atac, np.s_[del_offset : del_offset + del_width])
    seq, ctcf, atac = seq[:window_bp], ctcf[:window_bp], atac[:window_bp]
    return seq, ctcf, atac


@torch.no_grad()
def delete_and_predict(model, genome, start, del_start, del_width, window_bp, device="cpu"):
    """Return (pred_ref, pred_del, diff) for deleting a genomic interval."""
    model.eval()
    # Reference prediction over the plain window.
    seq0, ctcf0, atac0 = _raw_window(genome, start, window_bp)
    pred_ref = model(_assemble_inputs(seq0, ctcf0, atac0).to(device))[0].cpu().numpy()

    # Deletion: load a wider window so trimming keeps window_bp after removal.
    seq, ctcf, atac = _raw_window(genome, start, window_bp + del_width)
    seq, ctcf, atac = deletion_with_padding(seq, ctcf, atac, del_start - start, del_width, window_bp)
    pred_del = model(_assemble_inputs(seq, ctcf, atac).to(device))[0].cpu().numpy()
    return pred_ref, pred_del, pred_del - pred_ref


@torch.no_grad()
def ablate_and_predict(model, genome, start, ab_start, ab_width, window_bp, device="cpu"):
    """In-place feature ablation (no coordinate shift): over [ab_start, ab_start+
    ab_width) set CTCF/ATAC to 0 and DNA to N, then re-predict. This isolates a
    genomic element's contribution without the global shift a deletion induces.
    Returns (pred_ref, pred_ablated, diff)."""
    model.eval()
    seq, ctcf, atac = _raw_window(genome, start, window_bp)
    pred_ref = model(_assemble_inputs(seq, ctcf, atac).to(device))[0].cpu().numpy()

    o = ab_start - start
    seq_a, ctcf_a, atac_a = seq.copy(), ctcf.copy(), atac.copy()
    seq_a[o : o + ab_width] = 0.0
    seq_a[o : o + ab_width, 4] = 1.0  # unknown nucleotide N
    ctcf_a[o : o + ab_width] = 0.0
    atac_a[o : o + ab_width] = 0.0
    pred_ab = model(_assemble_inputs(seq_a, ctcf_a, atac_a).to(device))[0].cpu().numpy()
    return pred_ref, pred_ab, pred_ab - pred_ref


@torch.no_grad()
def screen(model, genome, screen_start, screen_end, perturb_width, step_size, window_bp, device="cpu", mode="ablation"):
    """Slide a `perturb_width` deletion across [screen_start, screen_end).

    For each centred perturbation, predict with and without the deletion and
    record impact = mean(|pred_del - pred_ref|). Returns (centers_bp, impact).
    """
    model.eval()
    centers, impact = [], []
    n = int((screen_end - screen_start) / step_size)
    for w in range(n):
        w_start = screen_start + w * step_size
        pred_start = int(w_start + perturb_width / 2 - window_bp / 2)
        if pred_start < 0 or pred_start + window_bp + perturb_width > genome.length_bp:
            continue
        if mode == "ablation":
            _, _, diff = ablate_and_predict(model, genome, pred_start, w_start, perturb_width, window_bp, device)
        else:
            _, _, diff = delete_and_predict(model, genome, pred_start, w_start, perturb_width, window_bp, device)
        centers.append(w_start + perturb_width // 2)
        impact.append(float(np.abs(diff).mean()))
    return np.array(centers), np.array(impact)

"""Data pipeline for the C.Origami reproduction.

Mirrors the structure of the official `corigami.data` package (per-bp DNA one-hot
+ genomic-feature tracks as model input; a Hi-C sub-matrix resized to map_size
and log1p-transformed as target; shift / gaussian-noise / reverse-complement
augmentation), but the source data here is a **synthetic genome** rather than
real IMR-90 bigwigs/cooler files.

Synthetic genome design (biologically motivated so the full method can be
exercised and the paper's causal result can be reproduced):
  * CTCF sites are placed at TAD boundaries; each boundary carries a CTCF peak
    in the CTCF track and a fixed CTCF-like motif embedded in the DNA sequence.
  * ATAC track = accessibility baseline + peaks at boundaries and at random
    active elements.
  * Hi-C = distance decay  x  boundary insulation  x  corner loops between
    consecutive convergent boundaries + noise.
This makes CTCF boundaries *causal* for TAD structure, exactly the relationship
C.Origami learns and that in-silico deletion probes.
"""

from dataclasses import dataclass, field

import numpy as np
from skimage.transform import resize
from torch.utils.data import Dataset

# Fixed 19 bp CTCF-like motif (integer-encoded A,T,C,G = 0,1,2,3) embedded in the
# DNA sequence at every CTCF site so the sequence tower carries boundary signal.
CTCF_MOTIF = np.array([2, 2, 2, 1, 2, 3, 2, 0, 3, 3, 2, 3, 2, 3, 2, 3, 3, 3, 0])
BASES = "atcg"


@dataclass
class SyntheticGenome:
    """One synthetic 'chromosome': DNA + CTCF + ATAC tracks and a dense Hi-C map."""

    name: str
    length_bp: int = 150_000
    res: int = 64  # bp per Hi-C bin
    seed: int = 0
    tad_min_bins: int = 8
    tad_max_bins: int = 22

    seq: np.ndarray = field(init=False, repr=False)  # int8 per-bp (0..4)
    ctcf: np.ndarray = field(init=False, repr=False)  # float32 per-bp
    atac: np.ndarray = field(init=False, repr=False)  # float32 per-bp
    hic: np.ndarray = field(init=False, repr=False)  # (n_bins, n_bins)
    boundaries: np.ndarray = field(init=False, repr=False)  # boundary bin idx

    def __post_init__(self):
        self._build()

    @property
    def n_bins(self):
        return self.length_bp // self.res

    def _build(self):
        rng = np.random.default_rng(self.seed)
        n_bins = self.n_bins

        # --- TAD boundaries (in bins) ---------------------------------------
        bounds = [0]
        while bounds[-1] < n_bins:
            step = int(rng.integers(self.tad_min_bins, self.tad_max_bins))
            bounds.append(bounds[-1] + step)
        bounds = np.array([b for b in bounds if 0 < b < n_bins])
        self.boundaries = bounds
        boundary_strength = rng.uniform(0.6, 1.0, size=len(bounds))

        # --- DNA sequence: random bases + embedded CTCF motif at boundaries --
        seq = rng.integers(0, 4, size=self.length_bp).astype(np.int8)
        for b in bounds:
            pos = int(b * self.res)
            if pos + len(CTCF_MOTIF) < self.length_bp:
                seq[pos : pos + len(CTCF_MOTIF)] = CTCF_MOTIF
        self.seq = seq

        # --- CTCF track: gaussian peak at each boundary ---------------------
        ctcf = np.zeros(self.length_bp, dtype=np.float32)
        atac = rng.gamma(1.0, 0.15, size=self.length_bp).astype(np.float32)  # baseline
        sigma = self.res * 1.5
        x = np.arange(self.length_bp)
        for b, s in zip(bounds, boundary_strength):
            pos = b * self.res
            lo, hi = max(0, pos - 6 * int(sigma)), min(self.length_bp, pos + 6 * int(sigma))
            bump = s * np.exp(-0.5 * ((x[lo:hi] - pos) / sigma) ** 2)
            ctcf[lo:hi] += bump
            atac[lo:hi] += 0.5 * bump  # boundaries are accessible too
        # random active elements add ATAC peaks (no CTCF, no boundary)
        for _ in range(int(n_bins * 0.4)):
            pos = int(rng.integers(0, self.length_bp))
            lo, hi = max(0, pos - 3 * int(sigma)), min(self.length_bp, pos + 3 * int(sigma))
            atac[lo:hi] += rng.uniform(0.3, 0.9) * np.exp(-0.5 * ((x[lo:hi] - pos) / sigma) ** 2)
        self.ctcf = ctcf
        self.atac = atac

        # --- Hi-C dense matrix ----------------------------------------------
        self.hic = self._build_hic(n_bins, bounds, boundary_strength, rng)

    # Hi-C generation parameters (tuned so TAD structure is a large, learnable
    # fraction of variance, as in real Hi-C, rather than being drowned out by the
    # distance-decay envelope).
    ALPHA = 0.85  # distance-decay exponent (gentler => filled TADs)
    COUNTS_SCALE = 120.0  # bring contacts to count-like magnitude for log1p
    INSULATION = 4.0  # cross-boundary suppression strength
    LOOP_GAIN = 0.6  # corner-loop intensity

    @classmethod
    def _build_hic(cls, n_bins, bounds, strength, rng):
        idx = np.arange(n_bins)
        dist = np.abs(idx[:, None] - idx[None, :])
        mat = 1.0 / (dist + 1.0) ** cls.ALPHA  # distance decay

        # Boundary insulation: sharply damp contacts crossing each boundary so
        # TADs appear as strong blocks along the diagonal.
        strength_by_bin = np.zeros(n_bins)
        strength_by_bin[bounds] = strength
        cum = np.cumsum(strength_by_bin)  # cum[k] = sum strengths <= k
        crossed = np.abs(cum[:, None] - cum[None, :])  # boundaries between i and j
        mat *= np.exp(-cls.INSULATION * crossed)

        # Per-TAD intensity: each TAD gets its own contact density (analogous to
        # cell-type/locus-specific activity) so windows differ structurally.
        tad_id = np.searchsorted(bounds, idx, side="right")
        tad_intensity = rng.uniform(0.6, 1.6, size=tad_id.max() + 1)
        same_tad = tad_id[:, None] == tad_id[None, :]
        block = np.where(same_tad, tad_intensity[tad_id][:, None], 1.0)
        mat *= block

        # Corner loops between consecutive convergent boundaries.
        edges = np.concatenate([[0], bounds, [n_bins - 1]])
        for a, b in zip(edges[:-1], edges[1:]):
            if b - a < 3:
                continue
            peak = cls.LOOP_GAIN * mat[a, min(a + 1, n_bins - 1)]
            for ci, cj in ((a, b), (b, a)):
                lo_i, hi_i = max(0, ci - 1), min(n_bins, ci + 2)
                lo_j, hi_j = max(0, cj - 1), min(n_bins, cj + 2)
                mat[lo_i:hi_i, lo_j:hi_j] += peak

        mat *= cls.COUNTS_SCALE
        mat *= rng.uniform(0.9, 1.1, size=mat.shape)  # multiplicative noise
        mat = 0.5 * (mat + mat.T)  # enforce symmetry
        return mat.astype(np.float32)

    # -- per-window accessors (bp coordinates) -------------------------------
    def get_seq_onehot(self, start, end):
        s = self.seq[start:end]
        onehot = np.zeros((len(s), 5), dtype=np.float32)
        onehot[np.arange(len(s)), s] = 1.0
        return onehot

    def get_track(self, name, start, end):
        return (self.ctcf if name == "ctcf" else self.atac)[start:end].astype(np.float32)

    def get_hic_window(self, start_bp, n_raw_bins, map_size):
        b0 = start_bp // self.res
        sub = self.hic[b0 : b0 + n_raw_bins, b0 : b0 + n_raw_bins]
        sub = np.asarray(resize(sub, (map_size, map_size), anti_aliasing=True))
        return np.log(sub + 1.0).astype(np.float32)


class GenomeDataset(Dataset):
    """Sliding-window dataset over one or more SyntheticGenome chromosomes.

    Yields (inputs, target) where
        inputs : (window_bp, 5 + 2)   one-hot DNA + [ctcf, atac]
        target : (map_size, map_size) log1p Hi-C contact map
    """

    def __init__(self, genomes, window_bp, map_size, stride_bp=None, augment=False):
        self.genomes = genomes
        self.window_bp = window_bp
        self.map_size = map_size
        self.res = genomes[0].res
        self.n_raw_bins = window_bp // self.res
        self.augment = augment
        stride_bp = stride_bp or window_bp // 2
        self.max_shift = window_bp // 8

        self.index = []  # (genome_idx, start_bp)
        for gi, g in enumerate(genomes):
            last = g.length_bp - window_bp - self.max_shift - 1
            for start in range(self.max_shift, last, stride_bp):
                self.index.append((gi, start))

    def __len__(self):
        return len(self.index)

    def __getitem__(self, idx):
        gi, start = self.index[idx]
        g = self.genomes[gi]

        if self.augment:
            start += int(np.random.randint(-self.max_shift, self.max_shift + 1))
            start = max(0, min(start, g.length_bp - self.window_bp))
        end = start + self.window_bp

        seq = g.get_seq_onehot(start, end)
        ctcf = g.get_track("ctcf", start, end)
        atac = np.log(g.get_track("atac", start, end) + 1.0)
        target = g.get_hic_window(start, self.n_raw_bins, self.map_size)

        if self.augment:
            ctcf = ctcf + np.random.randn(*ctcf.shape).astype(np.float32) * 0.05
            atac = atac + np.random.randn(*atac.shape).astype(np.float32) * 0.05
            if np.random.rand() < 0.5:  # reverse-complement
                seq = reverse_complement(seq)
                ctcf, atac = ctcf[::-1].copy(), atac[::-1].copy()
                target = target[::-1, ::-1].copy()

        inputs = np.concatenate([seq, ctcf[:, None], atac[:, None]], axis=1).astype(np.float32)
        return inputs, target


def reverse_complement(onehot):
    """Reverse the sequence and swap A<->T, C<->G channels (N unchanged)."""
    rc = onehot[::-1].copy()
    rc = rc[:, [1, 0, 3, 2, 4]]
    return rc


def make_splits(window_bp, map_size, n_train=4, res=64, length_bp=150_000, base_seed=0):
    """Build train/val/test genome splits (distinct chromosomes, like the paper
    holding out chr10/chr15)."""
    train = [SyntheticGenome(f"chr_tr{i}", length_bp, res, seed=base_seed + i) for i in range(n_train)]
    val = [SyntheticGenome("chr_val", length_bp, res, seed=base_seed + 100)]
    test = [SyntheticGenome("chr_test", length_bp, res, seed=base_seed + 200)]
    return (
        GenomeDataset(train, window_bp, map_size, augment=True),
        GenomeDataset(val, window_bp, map_size, augment=False),
        GenomeDataset(test, window_bp, map_size, augment=False),
    )


if __name__ == "__main__":
    from corigami_repro.model import DEMO_CONFIG, build_model

    m = build_model(**DEMO_CONFIG)
    tr, va, te = make_splits(m.input_length, m.map_size)
    print(f"windows: train={len(tr)} val={len(va)} test={len(te)}")
    x, y = tr[0]
    print("inputs", x.shape, "target", y.shape, "target range", float(y.min()), float(y.max()))

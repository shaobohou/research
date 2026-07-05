# C.Origami reproduction — working notes

## Paper
Tan et al., "Cell-type-specific prediction of 3D chromatin organization enables
high-throughput in silico genetic screening", *Nature Biotechnology* 2023.
DOI: 10.1038/s41587-022-01612-8. Official code: github.com/tanjimin/C.Origami
(studied at commit fetched 2026-07-05).

## What C.Origami does
Predicts a cell-type-specific Hi-C contact map (256x256, over a 2,097,152 bp
window at 10 kb resolution) from three genomic tracks aligned to the same window:
- DNA sequence (one-hot, 5 channels: A,T,C,G,N)
- CTCF ChIP-seq  (log2 fold-change track, no extra norm)
- ATAC-seq       (log-normalised accessibility track)

## Architecture ("Origami" = ConvTransModel)
1. `EncoderSplit`: two parallel 1D-CNN towers.
   - sequence tower: Conv1d(5->16, k3, s2) then 12 residual ConvBlocks
   - epigenomic tower: Conv1d(2->16, k3, s2) then 12 residual ConvBlocks
   - each ConvBlock halves length (stride-2 scale conv) + residual; channels
     ramp 32->256 (halved per-tower so concat gives full width).
   - concat towers -> Conv1d(256->256, k1). Length 2,097,152 -> 256 tokens.
2. `AttnModule`: sinusoidal positional encoding + 8-layer pre-LN Transformer
   encoder (d=256, 8 heads, ffn=512, dropout 0.1).
3. `diagonalize`: outer concatenation — tile the 256 x C token matrix into a
   256x256x2C map (feature i broadcast over rows, feature j over cols). This is
   how a 1D track becomes a 2D contact map.
4. `Decoder`: Conv2d(2C->256) + 5 dilated residual ResBlocks (dilation
   2,4,8,16,32) + Conv2d(256->1) -> 256x256 predicted map.
Loss: MSE against log(Hi-C+1). Optim: Adam lr 2e-4, gradient clip 1,
linear-warmup (10 ep) + cosine anneal. Train chrs = all but chr10/chr15/chrX;
val = chr10; test = chr15. Augmentation: random genomic shift, gaussian noise
on tracks, reverse-complement.

## Inference tasks (all reproduced)
- prediction: forward pass -> contact map.
- editing (in-silico deletion): delete a genomic interval from all input tracks,
  pad the tail, re-predict, compare. Paper's key finding: deleting a CTCF-bound
  TAD boundary fuses neighbouring TADs.
- screening: slide a fixed-width deletion across a region, record impact score =
  mean(|pred_deleted - pred_ref|) per position -> 1D importance track.

## Reproduction strategy in this environment
No GPU (4 CPU, 15 GB). Cannot download/train on real multi-GB IMR-90 data.
So: (a) reimplement the architecture faithfully and parametrically; (b) build a
biologically-motivated **synthetic genome** where CTCF sites define TAD
boundaries and convergent CTCF pairs define corner loops, and Hi-C is generated
with realistic distance-decay + TAD insulation + loop dots; (c) train the real
model end-to-end and show it learns (loss down, high map correlation on held-out
test); (d) demonstrate the causal perturbation result — deleting a boundary CTCF
site fuses TADs and produces a localized impact-score peak in screening.
The synthetic task is the honest way to exercise the *full method* on CPU while
keeping the architecture identical to the paper.

For CPU tractability the runnable demo uses a documented reduced config
(fewer downsampling blocks => shorter window, same 256x256 output, same
architecture family). The faithful paper config (num_blocks=12, 2,097,152 bp) is
the module default and is what `model.py` builds by default.

## Progress log
- Studied official src (model/blocks.py, data/*, training/main.py, inference/*).
- Built clean self-contained package `corigami_repro` (model/data/train/metrics/
  inference/plotting) + scripts + tests.
- Reimplemented ConvTransModel exactly: EncoderSplit (2 towers, 12 ResBlocks) ->
  8-layer pre-LN Transformer -> outer-concat -> 5-block dilated 2D decoder.
  Verified paper config builds at input_length=2,097,152, 12.84M params.
- CPU timing: the 2D decoder over map_size**2 dominates (input length barely
  matters: 17s/step at both 2Mb and 32kb windows). So exposed map_size / channel
  widths / num_blocks; DEMO_CONFIG (map=64, 1.17M params, 0.4s/step) is the
  CPU-tractable end-to-end run, PAPER_CONFIG is the faithful default.

### Iteration on the synthetic task
- First synthetic Hi-C had only ~6% window-specific variance (distance-decay
  dominated). Model learned the decay (map-r 0.89) but obs-vs-exp ~0 => it did
  NOT use CTCF to place TADs. This is the classic Hi-C-prediction trap.
- Strengthened TAD structure (stronger insulation, per-TAD intensity, gentler
  decay, count-scale before log1p) -> window-specific variance 29%. Model then
  learned structure: obs-vs-exp climbed 0 -> 0.67 by epoch 8.

### Final results (DEMO_CONFIG, 40 epochs, ~17 min CPU, seed 0)
Held-out test chromosome vs mean-map baseline:
| metric              | model  | mean-map baseline |
|---------------------|--------|-------------------|
| map Pearson         | 0.967  | 0.846             |
| insulation Pearson  | 0.974  | 0.314             |
| observed/expected r | 0.880  | ~0 (undefined)    |
| MSE                 | 0.147  | 0.626             |

In-silico perturbation (the paper's headline causal result):
- Deleting a CTCF boundary visibly FUSES the two neighbouring TADs in the
  predicted map (see outputs/deletion_boundary.png).
- Ablating a boundary CTCF site vs a control non-boundary region: 60x larger
  impact.
- Sliding ablation screen: impact-score peaks align with CTCF peaks at r=0.926;
  the top impact peak lands 19 bp from a true boundary.

### Quality gates
ruff check + ruff format --check clean; pyright (standard) 0 errors;
6/6 pytest pass.

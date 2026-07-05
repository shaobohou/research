"""End-to-end C.Origami reproduction: build synthetic data, train, evaluate.

Trains the Origami model to predict Hi-C contact maps from DNA+CTCF+ATAC, then
reports held-out test metrics and saves example predictions, the training curve,
and a checkpoint used by the perturbation demo.

    python scripts/run_training.py --epochs 15          # demo config (default)
    python scripts/run_training.py --paper              # paper config (needs GPU)
"""

import argparse
import json
import os
import time

import numpy as np
import torch

from corigami_repro import metrics, plotting
from corigami_repro.data import make_splits
from corigami_repro.model import DEMO_CONFIG, PAPER_CONFIG, build_model
from corigami_repro.train import evaluate, train

OUT = os.path.join(os.path.dirname(__file__), "..", "outputs")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--paper", action="store_true", help="use the paper config (2Mb window, 256 map; needs a GPU)")
    ap.add_argument("--n-train-chr", type=int, default=4)
    ap.add_argument("--chr-len", type=int, default=150_000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    torch.set_num_threads(os.cpu_count() or 4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    cfg = PAPER_CONFIG if args.paper else DEMO_CONFIG
    res = 10_000 if args.paper else 64
    print(f"config={'paper' if args.paper else 'demo'} {cfg} device={device}")

    model = build_model(**cfg)
    window_bp = model.input_length
    print(
        f"model params={sum(p.numel() for p in model.parameters()) / 1e6:.2f}M "
        f"window_bp={window_bp} map={model.map_size}"
    )

    train_ds, val_ds, test_ds = make_splits(
        window_bp, model.map_size, n_train=args.n_train_chr, res=res, length_bp=args.chr_len, base_seed=args.seed
    )
    print(f"windows: train={len(train_ds)} val={len(val_ds)} test={len(test_ds)}")

    # Save a synthetic-genome overview figure.
    plotting.plot_synthetic_overview(train_ds.genomes[0], os.path.join(OUT, "synthetic_overview.png"))

    t0 = time.time()
    history = train(
        model, train_ds, val_ds, epochs=args.epochs, batch_size=args.batch_size, device=device, res=res, seed=args.seed
    )
    print(f"training done in {time.time() - t0:.0f}s")

    # Held-out test evaluation.
    from torch.utils.data import DataLoader

    test_loader = DataLoader(test_ds, batch_size=args.batch_size)
    test_summary, preds, targets = evaluate(model, test_loader, device, res)
    print("TEST metrics:", json.dumps(test_summary, indent=2))

    # Baseline: distance-decay-only predictor (mean target map) for context.
    mean_map = targets.mean(axis=0, keepdims=True).repeat(len(targets), axis=0)
    baseline = metrics.summarize(mean_map, targets, res=res)

    plotting.plot_training_curve(history, os.path.join(OUT, "training_curve.png"))
    # A few example predictions (pick varied windows).
    for k, i in enumerate(np.linspace(0, len(preds) - 1, 4).astype(int)):
        r = float(metrics.map_pearson(preds[i : i + 1], targets[i : i + 1])[0])
        plotting.plot_prediction(
            preds[i],
            targets[i],
            os.path.join(OUT, f"test_prediction_{k}.png"),
            title=f"test window {i}  (map Pearson r={r:.3f})",
        )

    torch.save(
        {"state_dict": model.state_dict(), "config": cfg, "res": res, "window_bp": window_bp},
        os.path.join(OUT, "model_checkpoint.pt"),
    )

    report = {
        "config": "paper" if args.paper else "demo",
        "model_config": cfg,
        "epochs": args.epochs,
        "window_bp": window_bp,
        "test": test_summary,
        "mean_map_baseline": baseline,
        "history": history,
    }
    with open(os.path.join(OUT, "training_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print("saved checkpoint, figures, and training_report.json to outputs/")

    print("\n=== SUMMARY ===")
    print(
        f"Held-out test map Pearson : {test_summary['map_pearson']:.3f} "
        f"(mean-map baseline {baseline['map_pearson']:.3f})"
    )
    print(
        f"Held-out test insulation-r: {test_summary['insulation_pearson']:.3f} "
        f"(baseline {baseline['insulation_pearson']:.3f})"
    )
    print(f"Held-out test MSE         : {test_summary['mse']:.4f} (baseline {baseline['mse']:.4f})")


if __name__ == "__main__":
    main()

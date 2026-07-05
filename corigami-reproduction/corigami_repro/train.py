"""Training loop for the Origami model.

Mirrors the paper's optimisation: Adam (lr 2e-4, weight_decay 0), gradient
clipping at 1.0, and a linear-warmup + cosine-annealing LR schedule, with MSE
loss against the log1p Hi-C target. Implemented in plain PyTorch (the official
code uses PyTorch-Lightning + lightning-bolts for the same recipe) so it runs
without those extra dependencies.
"""

import math

import numpy as np
import torch
from torch.utils.data import DataLoader

from corigami_repro import metrics


def warmup_cosine_lr(step, total_steps, warmup_steps, base_lr):
    if step < warmup_steps:
        return base_lr * (step + 1) / max(1, warmup_steps)
    progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
    return 0.5 * base_lr * (1 + math.cos(math.pi * min(1.0, progress)))


@torch.no_grad()
def evaluate(model, loader, device, res):
    """Return (summary_dict, preds, targets) over a data loader."""
    model.eval()
    preds, targets = [], []
    for x, y in loader:
        out = model(x.to(device)).cpu().numpy()
        preds.append(out)
        targets.append(y.numpy())
    preds = np.concatenate(preds)
    targets = np.concatenate(targets)
    summary = metrics.summarize(preds, targets, res=res)
    return summary, preds, targets


def train(
    model,
    train_ds,
    val_ds,
    *,
    epochs=15,
    batch_size=8,
    base_lr=2e-4,
    warmup_frac=0.15,
    grad_clip=1.0,
    device="cpu",
    res=64,
    seed=0,
    num_workers=0,
    log_fn=print,
):
    torch.manual_seed(seed)
    np.random.seed(seed)
    model.to(device)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)

    opt = torch.optim.Adam(model.parameters(), lr=base_lr, weight_decay=0)
    criterion = torch.nn.MSELoss()

    total_steps = epochs * len(train_loader)
    warmup_steps = int(warmup_frac * total_steps)
    history = []
    step = 0
    lr = base_lr

    for epoch in range(epochs):
        model.train()
        running = 0.0
        for x, y in train_loader:
            lr = warmup_cosine_lr(step, total_steps, warmup_steps, base_lr)
            for pg in opt.param_groups:
                pg["lr"] = lr
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            loss = criterion(model(x), y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            opt.step()
            running += loss.item()
            step += 1
        train_loss = running / len(train_loader)
        val, _, _ = evaluate(model, val_loader, device, res)
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "val_loss": val["mse"],
                "val_pearson": val["map_pearson"],
                "val_ins_pearson": val["insulation_pearson"],
                "val_obs_vs_exp": val["obs_vs_exp"],
                "lr": lr,
            }
        )
        log_fn(
            f"epoch {epoch:2d} | lr {lr:.2e} | train MSE {train_loss:.4f} "
            f"| val MSE {val['mse']:.4f} | val map-r {val['map_pearson']:.3f} "
            f"| val ins-r {val['insulation_pearson']:.3f} "
            f"| val o/e-r {val['obs_vs_exp']:.3f}"
        )
    return history

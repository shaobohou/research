"""Origami architecture (C.Origami ConvTransModel), reimplemented faithfully.

Reference: Tan et al., Nat Biotechnol 2023; official code
github.com/tanjimin/C.Origami (src/corigami/model/{corigami_models,blocks}.py).

The model maps three genome tracks aligned to a window
    input:  (batch, L, 5 + num_features)   # one-hot DNA (5) + genomic features
to a symmetric Hi-C contact map
    output: (batch, 256, 256)

L must equal 256 * 2**(num_blocks + 1). With the paper's num_blocks=12 that is
2,097,152 bp (a 2 Mb window at ~10 kb -> 256 bins). num_blocks is exposed so the
same architecture can be run with a shorter window for CPU experiments.
"""

import copy
from typing import Any

import numpy as np
import torch
import torch.nn as nn


# --------------------------------------------------------------------------- #
# 1D encoder (sequence + epigenomic towers)
# --------------------------------------------------------------------------- #
class ConvBlock(nn.Module):
    """Stride-2 downsampling conv + residual conv pair (1D)."""

    def __init__(self, size, stride=2, hidden_in=64, hidden=64):
        super().__init__()
        pad = size // 2
        self.scale = nn.Sequential(
            nn.Conv1d(hidden_in, hidden, size, stride, pad),
            nn.BatchNorm1d(hidden),
            nn.ReLU(),
        )
        self.res = nn.Sequential(
            nn.Conv1d(hidden, hidden, size, padding=pad),
            nn.BatchNorm1d(hidden),
            nn.ReLU(),
            nn.Conv1d(hidden, hidden, size, padding=pad),
            nn.BatchNorm1d(hidden),
        )
        self.relu = nn.ReLU()

    def forward(self, x):
        scaled = self.scale(x)
        return self.relu(self.res(scaled) + scaled)


# Channel schedule from the paper (ramps 32 -> 256 over 12 blocks).
_HIDDENS = [32, 32, 32, 32, 64, 64, 128, 128, 128, 128, 256, 256]
_HIDDEN_INS = [32, 32, 32, 32, 32, 64, 64, 128, 128, 128, 128, 256]


def _res_blocks(filter_size, hidden_ins, hiddens):
    return nn.Sequential(*[ConvBlock(filter_size, hidden_in=hi, hidden=h) for hi, h in zip(hidden_ins, hiddens)])


class EncoderSplit(nn.Module):
    """Two parallel 1D-CNN towers: DNA sequence and epigenomic features.

    Each tower uses half the channel width; the towers are concatenated back to
    full width before a final 1x1 conv. This is the "split" encoder used by the
    released model (lets the two modalities be processed independently first).
    """

    def __init__(self, num_features, output_size=256, filter_size=5, num_blocks=12):
        super().__init__()
        self.conv_start_seq = nn.Sequential(nn.Conv1d(5, 16, 3, 2, 1), nn.BatchNorm1d(16), nn.ReLU())
        self.conv_start_epi = nn.Sequential(nn.Conv1d(num_features, 16, 3, 2, 1), nn.BatchNorm1d(16), nn.ReLU())

        hiddens = _HIDDENS[:num_blocks]
        hidden_ins = _HIDDEN_INS[:num_blocks]
        # 32 for the first block's input regardless of how many blocks we keep.
        hidden_ins = [32] + hiddens[:-1] if num_blocks != 12 else hidden_ins
        half_h = (np.array(hiddens) / 2).astype(int)
        half_hi = (np.array(hidden_ins) / 2).astype(int)

        self.res_blocks_seq = _res_blocks(filter_size, half_hi, half_h)
        self.res_blocks_epi = _res_blocks(filter_size, half_hi, half_h)
        self.conv_end = nn.Conv1d(hiddens[-1], output_size, 1)

    def forward(self, x):
        seq = self.res_blocks_seq(self.conv_start_seq(x[:, :5, :]))
        epi = self.res_blocks_epi(self.conv_start_epi(x[:, 5:, :]))
        return self.conv_end(torch.cat([seq, epi], dim=1))


# --------------------------------------------------------------------------- #
# Transformer trunk (pre-LN encoder + sinusoidal positional encoding)
# --------------------------------------------------------------------------- #
class PositionalEncoding(nn.Module):
    pe: torch.Tensor

    def __init__(self, hidden, dropout=0.1, max_len=1024):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        position = torch.arange(max_len).unsqueeze(1)
        div = torch.exp(torch.arange(0, hidden, 2) * (-np.log(10000.0) / hidden))
        pe = torch.zeros(max_len, 1, hidden)
        pe[:, 0, 0::2] = torch.sin(position * div)
        pe[:, 0, 1::2] = torch.cos(position * div)
        self.register_buffer("pe", pe)

    def forward(self, x):  # x: (seq_len, batch, hidden) if not batch_first
        return self.dropout(x + self.pe[: x.size(0)])


class TransformerLayer(nn.TransformerEncoderLayer):
    """Pre-LN transformer encoder layer that also returns attention weights."""

    def forward(self, src, src_mask=None, src_key_padding_mask=None, **kw):  # type: ignore[override]
        n = self.norm1(src)
        side, attn = self.self_attn(n, n, n, attn_mask=src_mask, key_padding_mask=src_key_padding_mask)
        src = src + self.dropout1(side)
        n = self.norm2(src)
        side = self.linear2(self.dropout(self.activation(self.linear1(n))))
        return src + self.dropout2(side), attn


class TransformerEncoder(nn.Module):
    def __init__(self, layer, num_layers, record_attn=False):
        super().__init__()
        self.layers = nn.ModuleList([copy.deepcopy(layer) for _ in range(num_layers)])
        self.record_attn = record_attn

    def forward(self, src):
        out = src
        attns = []
        for mod in self.layers:
            out, attn = mod(out)
            attns.append(attn.unsqueeze(0).detach())
        if self.record_attn:
            return out, torch.cat(attns)
        return out


class AttnModule(nn.Module):
    def __init__(self, hidden=256, layers=8, record_attn=False, max_len=1024):
        super().__init__()
        self.record_attn = record_attn
        self.pos_encoder = PositionalEncoding(hidden, dropout=0.1, max_len=max_len)
        layer = TransformerLayer(hidden, nhead=8, dropout=0.1, dim_feedforward=512, batch_first=True)
        self.module = TransformerEncoder(layer, layers, record_attn=record_attn)

    def forward(self, x):
        return self.module(self.pos_encoder(x))


# --------------------------------------------------------------------------- #
# Full model
# --------------------------------------------------------------------------- #
class ConvTransModel(nn.Module):
    """Origami: CNN encoder -> Transformer -> outer-concat -> 2D dilated decoder.

    Paper config: map_size=256, mid_hidden=256, decoder_hidden=256, num_blocks=12
    (a 2,097,152 bp window -> 256x256 contact map). map_size / channel widths /
    num_blocks are exposed so the identical architecture can be run at reduced
    cost on CPU; the 2D decoder over map_size**2 dominates compute.
    """

    def __init__(
        self, num_genomic_features=2, mid_hidden=256, num_blocks=12, map_size=256, decoder_hidden=256, record_attn=False
    ):
        super().__init__()
        self.num_blocks = num_blocks
        self.map_size = map_size
        self.encoder = EncoderSplit(num_genomic_features, output_size=mid_hidden, num_blocks=num_blocks)
        self.attn = AttnModule(hidden=mid_hidden, record_attn=record_attn, max_len=max(map_size, 256))
        self.decoder = Decoder(mid_hidden * 2, hidden=decoder_hidden)
        self.record_attn = record_attn

    @property
    def input_length(self):
        return self.map_size * 2 ** (self.num_blocks + 1)

    def forward(self, x):
        attn = None
        x = x.transpose(1, 2).contiguous().float()  # (b, C, L)
        x = self.encoder(x)  # (b, mid, map)
        x = x.transpose(1, 2)  # (b, map, mid)
        if self.record_attn:
            x, attn = self.attn(x)
        else:
            x = self.attn(x)
        x = x.transpose(1, 2)  # (b, mid, map)
        x = self.diagonalize(x, self.map_size)  # (b, 2*mid, map, map)
        x = self.decoder(x).squeeze(1)  # (b, map, map)
        if self.record_attn:
            return x, attn
        return x

    @staticmethod
    def diagonalize(x, map_size):
        """Outer concatenation: 1D token features -> 2D pairwise feature map."""
        xi = x.unsqueeze(2).repeat(1, 1, map_size, 1)
        xj = x.unsqueeze(3).repeat(1, 1, 1, map_size)
        return torch.cat([xi, xj], dim=1)


# --------------------------------------------------------------------------- #
# 2D dilated decoder
# --------------------------------------------------------------------------- #
class ResBlockDilated(nn.Module):
    def __init__(self, size, hidden=256, dil=2):
        super().__init__()
        self.res = nn.Sequential(
            nn.Conv2d(hidden, hidden, size, padding=dil, dilation=dil),
            nn.BatchNorm2d(hidden),
            nn.ReLU(),
            nn.Conv2d(hidden, hidden, size, padding=dil, dilation=dil),
            nn.BatchNorm2d(hidden),
        )
        self.relu = nn.ReLU()

    def forward(self, x):
        return self.relu(self.res(x) + x)


class Decoder(nn.Module):
    def __init__(self, in_channel, hidden=256, filter_size=3, num_blocks=5):
        super().__init__()
        self.conv_start = nn.Sequential(nn.Conv2d(in_channel, hidden, 3, 1, 1), nn.BatchNorm2d(hidden), nn.ReLU())
        self.res_blocks = nn.Sequential(
            *[ResBlockDilated(filter_size, hidden=hidden, dil=2 ** (i + 1)) for i in range(num_blocks)]
        )
        self.conv_end = nn.Conv2d(hidden, 1, 1)

    def forward(self, x):
        return self.conv_end(self.res_blocks(self.conv_start(x)))


def build_model(
    num_genomic_features=2, mid_hidden=256, num_blocks=12, map_size=256, decoder_hidden=256, record_attn=False
):
    return ConvTransModel(num_genomic_features, mid_hidden, num_blocks, map_size, decoder_hidden, record_attn)


# Paper's released configuration.
PAPER_CONFIG: dict[str, Any] = dict(mid_hidden=256, num_blocks=12, map_size=256, decoder_hidden=256)
# Reduced configuration used for CPU end-to-end demos (same architecture family).
DEMO_CONFIG: dict[str, Any] = dict(mid_hidden=64, num_blocks=5, map_size=64, decoder_hidden=64)


if __name__ == "__main__":
    for name, cfg in (("PAPER", PAPER_CONFIG), ("DEMO", DEMO_CONFIG)):
        m = build_model(**cfg)
        print(
            f"{name}: input_length={m.input_length} map={m.map_size} "
            f"params={sum(p.numel() for p in m.parameters()) / 1e6:.2f}M"
        )
    m = build_model(**DEMO_CONFIG)
    y = m(torch.randn(2, m.input_length, 7))
    print("demo output:", tuple(y.shape))

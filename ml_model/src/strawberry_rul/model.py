"""Model D: MobileNetV2 → CBAM → GRU → RUL regression head.

Layer names match the original checkpoint so weights load strictly without conversion.
"""
from __future__ import annotations

import torch
from torch import nn
from torchvision.models import mobilenet_v2

from .attention import CBAM


class VisualEncoder(nn.Module):
    def __init__(self, dropout: float = 0.1) -> None:
        super().__init__()
        self.features = mobilenet_v2(weights=None).features
        self.cbam = CBAM(in_channels=1280)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.dropout = nn.Dropout(dropout)

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        features = self.cbam(self.features(images))
        return self.dropout(self.pool(features).flatten(1))


class StrawberryRULModel(nn.Module):
    def __init__(self, hidden_size: int = 160, dropout: float = 0.25, backbone_dropout: float = 0.1) -> None:
        super().__init__()
        self.visual_encoder = VisualEncoder(backbone_dropout)
        self.rnn = nn.GRU(input_size=1280, hidden_size=hidden_size, batch_first=True, num_layers=1)
        self.head = nn.Sequential(
            nn.Linear(hidden_size * 3, max(hidden_size, 128)),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(max(hidden_size, 128), max(hidden_size // 2, 64)),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(max(hidden_size // 2, 64), 1),
        )

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        batch, sequence, channels, height, width = images.shape
        features = self.visual_encoder(images.view(batch * sequence, channels, height, width))
        outputs, _ = self.rnn(features.view(batch, sequence, -1))
        pooled = torch.cat([outputs[:, -1, :], outputs.mean(dim=1), outputs.max(dim=1).values], dim=1)
        return self.head(pooled).squeeze(-1)

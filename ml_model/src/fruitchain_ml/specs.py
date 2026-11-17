"""Architecture names used in trained checkpoint metadata."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    key: str
    backbone: str
    recurrent: str


MODEL_SPECS = {
    "A": ModelSpec("A", "efficientnet_b0", "gru"),
    "B": ModelSpec("B", "mobilenet_v2", "lstm"),
    "C": ModelSpec("C", "efficientnet_b0", "lstm"),
    "D": ModelSpec("D", "mobilenet_v2", "gru"),
}

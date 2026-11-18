"""Load a trained checkpoint, preprocess images and predict RUL in hours."""
from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
import torch

from .image import numpy_to_tensor, remove_alpha
from .model import StrawberryRULModel
from .preprocessing import PreprocessResult, preprocess


class RulPredictor:
    """Inference only; dimensions, normalization and architecture follow the checkpoint."""

    def __init__(self, model_dir: str | Path, checkpoint: str | Path | None = None, device: str = "auto"):
        self.root = Path(model_dir).resolve()
        manifest = json.loads((self.root / "fruitchain_model.json").read_text(encoding="utf-8"))
        self.config = json.loads((self.root / manifest["config"]).read_text(encoding="utf-8"))
        self.checkpoint_path = Path(checkpoint or manifest["checkpoint"])
        if not self.checkpoint_path.is_absolute():
            self.checkpoint_path = self.root / self.checkpoint_path
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda" and not torch.cuda.is_available():
            device = "cpu"
        self.device = torch.device(device)
        # State dict + primitive training metadata; no legacy application objects are loaded.
        self.checkpoint = torch.load(self.checkpoint_path, map_location="cpu", weights_only=True)
        if not isinstance(self.checkpoint, dict):
            raise ValueError("Expected a checkpoint dictionary with model_state_dict and config")
        trained = self.checkpoint.get("config") or {}
        fallback = self.config.get("model") or {}
        self.image_size = int(trained.get("image_size") or fallback.get("image_size") or 224)
        self.seq_len = int(trained.get("seq_len") or fallback.get("seq_len") or 8)
        if not 16 <= self.image_size <= 4096 or not 1 <= self.seq_len <= 256:
            raise ValueError("Invalid checkpoint image_size or seq_len")
        model_key = str(self.checkpoint.get("model_key") or trained.get("model_key") or fallback.get("key", "D"))
        supported = {"use_cbam": True, "fusion_mode": "image_only", "temporal_pooling": "last_mean_max"}
        if model_key != "D" or any(trained.get(key, fallback.get(key, value)) != value for key, value in supported.items()):
            raise ValueError("Only strawberry model D with CBAM, image_only and last_mean_max is supported")
        parameters = {
            key: trained.get(key, fallback.get(key, default))
            for key, default in {
                "hidden_size": 160, "dropout": 0.25, "backbone_dropout": 0.1,
            }.items()
        }
        self.model = StrawberryRULModel(**parameters)
        state = next((self.checkpoint[key] for key in ("model_state_dict", "state_dict", "model")
                      if isinstance(self.checkpoint.get(key), dict) and self.checkpoint[key]), None)
        if state is None:
            raise ValueError("Checkpoint has no model state_dict")
        self.model.load_state_dict(state, strict=True)
        self.model.to(self.device).eval()
        self.target_scaler = self.checkpoint.get("target_scaler") or {}
        self.metadata = {
            key: self.checkpoint[key] for key in ("model_key", "fold_name", "test_group", "val_mae", "epoch")
            if key in self.checkpoint
        }
        self.metadata.update(
            imageSize=self.image_size, seqLen=self.seq_len, outputUnit="hours", format="checkpoint-dict",
            config={key: trained[key] for key in ("run_name", "seq_len", "fusion_mode", "temporal_pooling", "image_size")
                    if key in trained},
            fusionMode="image_only", singleImageStrategy="repeat_frame",
            confidenceNote="Regression checkpoint has no calibrated confidence or prediction interval.",
        )

    def preprocess(self, image_bgr: np.ndarray) -> PreprocessResult:
        # GrabCut initializes randomly. Reset only its seed, leaving the migrated algorithm unchanged.
        cv2.setRNGSeed(0)
        result = preprocess(image_bgr, self.config["preprocessing"])
        if result is None:
            raise ValueError("Không tìm thấy quả trong ảnh đầu vào")
        return result

    def predict_hours(self, segmented_image: np.ndarray, temperature_c: float | None = None,
                      humidity_pct: float | None = None) -> float:
        """Image-only prediction. Optional sensor arguments preserve the bundle adapter interface."""
        frame = numpy_to_tensor(remove_alpha(segmented_image), self.image_size, self.device)
        images = frame.unsqueeze(0).unsqueeze(0).repeat(1, self.seq_len, 1, 1, 1)
        with torch.inference_mode():
            hours = float(self.model(images).squeeze().item())
        hours = hours * (float(self.target_scaler.get("scale", 1.0)) or 1.0) + float(self.target_scaler.get("center", 0.0))
        if not math.isfinite(hours):
            raise ValueError("Model returned non-finite RUL")
        return hours

"""Load a trained checkpoint, preprocess images and predict RUL in hours."""
from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
import torch

from .image import numpy_to_tensor, remove_alpha
from .networks import build_model
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
        parameters = {
            key: trained.get(key, fallback.get(key, default))
            for key, default in {
                "use_cbam": True, "hidden_size": 160, "env_hidden_size": 64,
                "dropout": 0.25, "backbone_dropout": 0.1,
                "temporal_pooling": "last_mean_max", "fusion_mode": "image_only",
            }.items()
        }
        self.model = build_model(model_key, pretrained_backbone=False, **parameters)
        state = next((self.checkpoint[key] for key in ("model_state_dict", "state_dict", "model")
                      if isinstance(self.checkpoint.get(key), dict) and self.checkpoint[key]), None)
        if state is None:
            raise ValueError("Checkpoint has no model state_dict")
        self.model.load_state_dict(state, strict=True)
        self.model.to(self.device).eval()
        self.target_scaler = self.checkpoint.get("target_scaler") or {}
        environment = self.checkpoint.get("env_stats") or {}
        self.env_mean = np.asarray(environment.get("mean", [0.0, 0.0]), dtype=np.float32)
        env_std = np.asarray(environment.get("std", [1.0, 1.0]), dtype=np.float32)
        if self.env_mean.shape != (2,) or env_std.shape != (2,):
            raise ValueError("Expected two environment statistics: temperature and humidity")
        self.env_std = np.where((~np.isfinite(env_std)) | (env_std < 1e-6), 1.0, env_std)
        self.metadata = {
            key: self.checkpoint[key] for key in ("model_key", "fold_name", "test_group", "val_mae", "epoch")
            if key in self.checkpoint
        }
        self.metadata.update(
            imageSize=self.image_size, seqLen=self.seq_len, outputUnit="hours", format="checkpoint-dict",
            config={key: trained[key] for key in ("run_name", "seq_len", "fusion_mode", "temporal_pooling", "image_size")
                    if key in trained},
            fusionMode=parameters["fusion_mode"], singleImageStrategy="repeat_frame",
            confidenceNote="Regression checkpoint has no calibrated confidence or prediction interval.",
        )

    def preprocess(self, image_bgr: np.ndarray) -> PreprocessResult:
        # GrabCut initializes randomly. Reset only its seed, leaving the migrated algorithm unchanged.
        cv2.setRNGSeed(0)
        result = preprocess(image_bgr, self.config)
        if result is None:
            raise ValueError("Không tìm thấy quả trong ảnh đầu vào")
        return result

    def _environment_sequence(self, temperature_c: float | None, humidity_pct: float | None) -> torch.Tensor:
        values = np.asarray([np.nan if temperature_c is None else temperature_c,
                             np.nan if humidity_pct is None else humidity_pct], dtype=np.float32)
        missing = (~np.isfinite(values)).astype(np.float32)
        filled = np.where(missing > 0, self.env_mean, values)
        normalized = np.where(missing > 0, 0.0, (filled - self.env_mean) / self.env_std)
        row = np.concatenate([normalized, missing]).astype(np.float32)
        return torch.from_numpy(row).to(self.device).view(1, 1, 4).repeat(1, self.seq_len, 1)

    def predict_hours(self, segmented_image: np.ndarray, temperature_c: float | None = None,
                      humidity_pct: float | None = None) -> float:
        frame = numpy_to_tensor(remove_alpha(segmented_image), self.image_size, self.device)
        images = frame.unsqueeze(0).unsqueeze(0).repeat(1, self.seq_len, 1, 1, 1)
        environment = self._environment_sequence(temperature_c, humidity_pct)
        with torch.inference_mode():
            hours = float(self.model(images, environment).squeeze().item())
        hours = hours * (float(self.target_scaler.get("scale", 1.0)) or 1.0) + float(self.target_scaler.get("center", 0.0))
        if not math.isfinite(hours):
            raise ValueError("Model returned non-finite RUL")
        return hours

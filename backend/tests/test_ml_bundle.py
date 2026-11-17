"""Relocation, provenance, checkpoint compatibility and persisted model choices."""
import json
from pathlib import Path
import shutil

import pytest
import torch

from app import config
from app.services.rul import ImageModelManager
from app.services.rul_adapters.custom import CustomModel


def copy_runtime(destination: Path) -> Path:
    source = config.DEFAULT_MODEL_DIR
    destination.mkdir()
    shutil.copy2(source / "fruitchain_model.json", destination)
    for directory in ("src", "configs", "artifacts"):
        shutil.copytree(source / directory, destination / directory, ignore=shutil.ignore_patterns("__pycache__"))
    return destination


def test_bundle_relocates_without_global_imports_and_hashes_inference_code(tmp_path):
    import sys
    before_path = list(sys.path)
    before_modules = set(sys.modules)
    relocated = copy_runtime(tmp_path / "relocated-model")
    original = CustomModel(config.DEFAULT_MODEL_DIR, device="cpu")
    model = CustomModel(relocated, device="cpu")
    assert model.model_hash() == original.model_hash()
    try:
        model.load()
        assert sys.path == before_path
        assert not ({"services", "training", "utils_app", "strawberry"} & (set(sys.modules) - before_modules))
        assert model.meta["imageSize"] == 224
    finally:
        model.unload()
    code = relocated / "src/fruitchain_ml/image.py"
    code.write_text(code.read_text(encoding="utf-8") + "\n# provenance regression test\n", encoding="utf-8")
    assert CustomModel(relocated).model_hash() != original.model_hash()


def test_checkpoint_with_missing_weights_is_rejected(tmp_path):
    source = config.DEFAULT_MODEL_DIR / "artifacts/strawberry/model_d.pt"
    checkpoint = torch.load(source, map_location="cpu", weights_only=True)
    checkpoint["model_state_dict"].pop(next(iter(checkpoint["model_state_dict"])))
    broken = tmp_path / "missing-layer.pt"
    torch.save(checkpoint, broken)
    model = CustomModel(config.DEFAULT_MODEL_DIR, str(broken), device="cpu")
    try:
        with pytest.raises(RuntimeError, match="Missing key"):
            model.load()
    finally:
        model.unload()


def test_unloaded_model_stays_unloaded_until_explicit_override(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODEL_SETTINGS_FILE", tmp_path / "model_settings.json")
    monkeypatch.setattr(config, "RUL_MODEL", "")
    manager = ImageModelManager()
    manager.load(None, path=str(config.DEFAULT_MODEL_DIR), device="cpu", fruits=["strawberry"])
    with pytest.raises(ValueError, match="strawberry"):
        manager.update_options(fruits=["mango"])
    assert manager.model.fruits == ["strawberry"]
    manager.unload()
    saved = json.loads(config.MODEL_SETTINGS_FILE.read_text())
    saved["path"] = str(tmp_path / "old-location")
    config.MODEL_SETTINGS_FILE.write_text(json.dumps(saved))
    restarted = ImageModelManager()
    restarted.autoload(None)
    assert restarted.model is None
    assert json.loads(config.MODEL_SETTINGS_FILE.read_text())["mode"] == "q10"
    monkeypatch.setattr(config, "RUL_MODEL", "custom")
    restarted.autoload(None)
    assert restarted.model is not None
    restarted.unload()


def test_strawberry_bundle_cannot_be_loaded_for_a_different_fruit():
    with pytest.raises(ValueError, match="strawberry"):
        CustomModel(config.DEFAULT_MODEL_DIR, fruits=["mango"])


def test_missing_selected_checkpoint_does_not_silently_load_default(tmp_path):
    with pytest.raises(FileNotFoundError):
        CustomModel(config.DEFAULT_MODEL_DIR, str(tmp_path / "not-found.pt"))

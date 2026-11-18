"""Bundled sample inference; no Desktop source or training dataset is required."""
import hashlib
import json

import cv2
import pytest

from app import config
from app.services.preprocess import read_image
from app.services.rul_adapters.base import RulInput
from app.services.rul_adapters.custom import CustomModel
from conftest import auth


def test_bundled_runtime_preserves_preprocessing_and_rul(tmp_path):
    manifest = json.loads((config.DEFAULT_MODEL_DIR / "examples/reference.json").read_text(encoding="utf-8"))
    model = CustomModel(config.DEFAULT_MODEL_DIR, device="cpu", fruits=["strawberry"]).load()
    try:
        assert model.meta["imageSize"] == 224 and model.meta["seqLen"] == 8
        assert model.meta["checkpointSha256"] == manifest["checkpointSha256"]
        results = {}
        for sample in manifest["samples"]:
            image = config.DEFAULT_MODEL_DIR / "examples" / sample["path"]
            assert hashlib.sha256(image.read_bytes()).hexdigest() == sample["imageSha256"]
            prepared, _ = model.preprocess(read_image(image))
            encoded = cv2.imencode(".png", prepared)[1].tobytes()
            assert hashlib.sha256(encoded).hexdigest() == sample["preprocessedSha256"]
            pre_path = tmp_path / f"{sample['name']}.png"
            pre_path.write_bytes(encoded)
            output = model.predict(RulInput(batch_id="REGRESSION", fruit_id="strawberry", image_path=str(pre_path)))
            assert output.extra["rawOutput"] == pytest.approx(sample["referenceRulHours"], abs=0.05)
            assert output.ci_low_days is None and output.ci_high_days is None
            assert "modelConfidence" not in output.extra
            results[sample["name"]] = output.extra["rawOutput"]
        assert results["fresh"] - results["expired"] > 24
    finally:
        model.unload()


def test_model_api_distinguishes_bundled_samples(client):
    headers = auth(client, "admin")
    response = client.post("/api/settings/model/load", headers=headers,
                           json={"path": str(config.DEFAULT_MODEL_DIR), "device":"cpu", "fruits":["strawberry"]})
    assert response.status_code == 200, response.text
    outputs = {}
    for name in ("fresh", "expired"):
        source = config.DEFAULT_MODEL_DIR / f"examples/{name}.png"
        response = client.post("/api/settings/model/test", headers=headers,
                               files={"file":(source.name, source.read_bytes(), "image/png")})
        assert response.status_code == 200, response.text
        outputs[name] = response.json()["rulHours"]
    assert outputs["fresh"] - outputs["expired"] > 24
    client.post("/api/settings/model/unload", headers=headers)

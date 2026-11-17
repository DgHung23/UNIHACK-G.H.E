"""M1b: T-IMG-1, T-IMG-2, T-PREPROC, T-MODEL-SWAP + trang Cài đặt (duyệt thư mục, nạp, chạy thử)."""
import hashlib
from pathlib import Path

import cv2
import numpy as np
import pytest
from conftest import USER_MODEL_DIR, auth

from app import config
from app.db import SessionLocal
from app.models import Inspection

MODEL_DIR = USER_MODEL_DIR if (USER_MODEL_DIR / "src").is_dir() else getattr(config, "DEFAULT_MODEL_DIR", USER_MODEL_DIR)
HAS_USER_MODEL = (MODEL_DIR / "src").is_dir()
needs_model = pytest.mark.skipif(not HAS_USER_MODEL, reason=f"Không thấy dự án model ở {MODEL_DIR}")


def synthetic_jpg() -> bytes:
    img = np.full((300, 300, 3), 255, np.uint8)
    cv2.circle(img, (150, 160), 80, (40, 40, 210), -1)
    cv2.ellipse(img, (150, 80), (40, 15), 0, 0, 360, (40, 160, 40), -1)
    return cv2.imencode(".jpg", img)[1].tobytes()


def sample_image() -> bytes:
    for base in (MODEL_DIR, getattr(config, "DEFAULT_MODEL_DIR", None)):
        if base and (base / "data").is_dir():
            imgs = sorted((base / "data").rglob("*.png"))
            if imgs:
                return imgs[0].read_bytes()
    return synthetic_jpg()


@pytest.fixture(autouse=True, scope="module")
def _seed(fresh):
    fresh()


def _upload(client, bid, data, user="admin", name="a.jpg"):
    return client.post(f"/api/batches/{bid}/inspections", headers=auth(client, user),
                       files={"file": (name, data, "image/jpeg")}, data={"note": "test"})


def test_img_upload_q10(client):
    bid = "FC-2026-001"
    head = client.get(f"/api/batches/{bid}/events", headers=auth(client, "admin")).json()[-1]["eventHash"]
    data = synthetic_jpg()
    r = _upload(client, bid, data, user="store_q7")
    assert r.status_code == 201, r.text
    body = r.json()
    ev = body["event"]
    assert ev["type"] == "INSPECTION" and ev["dataHash"] == hashlib.sha256(data).hexdigest()
    assert ev["prevHash"] == head
    with SessionLocal() as db:
        insp = db.get(Inspection, body["inspectionId"])
        assert Path(insp.raw_image_path).read_bytes() == data
    assert body["rulImage"] is None and body["rulFinal"] == body["rulSensor"]
    # người không giữ lô → 403
    assert _upload(client, bid, data, user="truck_dalat").status_code == 403
    v = client.post(f"/api/batches/{bid}/verify", headers=auth(client, "admin")).json()
    assert v["overall"] == "PASS" and any(s["type"] == "INSPECTION" and s["match"] for s in v["segments"])


def test_img_tamper_detected(client):
    bid = "FC-2026-001"
    with SessionLocal() as db:
        insp = db.query(Inspection).filter(Inspection.batch_id == bid).first()
        p = Path(insp.raw_image_path)
    b = bytearray(p.read_bytes())
    b[len(b) // 2] ^= 0xFF
    p.write_bytes(bytes(b))
    v = client.post(f"/api/batches/{bid}/verify", headers=auth(client, "admin")).json()
    assert v["overall"] == "FAIL"
    seg = [s for s in v["segments"] if s["type"] == "INSPECTION"][0]
    assert seg["match"] is False


def test_fs_browse(client):
    h = auth(client, "admin")
    root = client.get("/api/settings/fs", headers=h).json()
    assert root["drives"] and root["shortcuts"]
    home = client.get("/api/settings/fs", headers=h, params={"path": str(Path.home())}).json()
    assert home["path"] and isinstance(home["entries"], list)
    assert client.get("/api/settings/fs", headers=auth(client, "store_q7")).status_code == 403


@needs_model
def test_model_swap_preproc_and_inference(client):
    h = auth(client, "admin")
    q10_hash = client.get("/api/meta/models", headers=h).json()["sensorModel"]["modelHash"]

    info = client.post("/api/settings/model/inspect", headers=h, json={"path": str(MODEL_DIR)}).json()
    assert info["kind"] == "project" and info["checkpoints"]
    assert "production" in info["defaultCheckpoint"].replace("\\", "/")

    r = client.post("/api/settings/model/load", headers=h,
                    json={"path": str(MODEL_DIR), "fruits": ["strawberry"], "fusion": "min"})
    assert r.status_code == 200, r.text
    st = r.json()
    assert st["active"] == "custom"
    custom_hash = st["model"]["modelHash"]
    assert custom_hash != q10_hash
    versions = [m["version"] for m in client.get("/api/meta/models", headers=h).json()["versions"]]
    assert st["model"]["version"] in versions

    # A bad checkpoint must not evict the working model or overwrite its saved selection.
    from app import config

    saved_settings = config.MODEL_SETTINGS_FILE.read_bytes()
    broken = config.STORAGE_DIR / "broken.pt"
    broken.write_bytes(b"not a PyTorch checkpoint")
    failed = client.post("/api/settings/model/load", headers=h,
                         json={"path": str(MODEL_DIR), "checkpoint": str(broken), "fruits": ["strawberry"]})
    assert failed.status_code == 422
    current = client.get("/api/settings/model", headers=h).json()
    assert current["active"] == "custom" and current["model"]["modelHash"] == custom_hash
    assert config.MODEL_SETTINGS_FILE.read_bytes() == saved_settings

    # T-PREPROC: services/preprocess.py cho kết quả giống hệt hàm preprocess gốc của dự án
    import json
    import sys

    from app import config
    from app.services import preprocess as svc

    img_bytes = sample_image()
    raw = config.STORAGE_DIR / "t_preproc_input.png"
    raw.write_bytes(img_bytes)
    out = config.STORAGE_DIR / "t_preproc_out.png"
    svc.run(raw, out)
    orig_pre = sys.modules["services.preprocessing"].preprocess
    orig_read = sys.modules["utils_app.image_utils"].read_image
    cfg = json.loads((MODEL_DIR / "src/strawberry/config_app/config.json").read_text(encoding="utf-8-sig"))
    ref = orig_pre(orig_read(img_bytes), cfg).roi
    assert hashlib.sha256(cv2.imencode(".png", ref)[1].tobytes()).hexdigest() == \
        hashlib.sha256(out.read_bytes()).hexdigest()

    # chạy thử
    t = client.post("/api/settings/model/test", headers=h, files={"file": ("s.png", img_bytes, "image/png")})
    assert t.status_code == 200, t.text
    assert t.json()["rulDays"] >= 0 and t.json()["preprocessedImage"].startswith("data:image/png;base64,")

    # inspection thật trên lô dâu tây 004 → có rulImage, INSPECTION ghi modelHash của model bạn
    r = _upload(client, "FC-2026-004", img_bytes, user="store_q1", name="s.png")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["rulImage"] is not None and body["modelHash"] == custom_hash
    assert body["rulFinal"] == min(body["rulImage"], body["rulSensor"])
    assert body["event"]["rulSnapshot"]["modelHash"] == custom_hash
    # loại quả không hỗ trợ (xoài) → không dùng model ảnh
    r = _upload(client, "FC-2026-001", synthetic_jpg(), user="store_q7")
    assert r.status_code in (201, 422)

    # quay về Q10
    st = client.post("/api/settings/model/unload", headers=h).json()
    assert st["active"] == "q10"
    r = _upload(client, "FC-2026-004", synthetic_jpg(), user="store_q1")
    assert r.status_code == 201 and r.json()["modelHash"] == q10_hash


@pytest.mark.parametrize("options", [
    {"device": "typo"}, {"outputUnit": "seconds"}, {"fruits": []}, {"fruits": ["unknown-fruit"]},
])
def test_invalid_model_configuration(client, options):
    body = {"path": str(MODEL_DIR), **options}
    response = client.post("/api/settings/model/load", headers=auth(client, "admin"), json=body)
    assert response.status_code == 422


def test_model_settings_require_admin(client):
    h = auth(client, "store_q7")
    for route in ("load", "unload", "options", "inspect"):
        response = client.post(f"/api/settings/model/{route}", headers=h,
                               json={"path": str(MODEL_DIR), "fusion": "min"})
        assert response.status_code == 403

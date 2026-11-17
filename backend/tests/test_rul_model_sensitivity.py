"""Hồi quy: model ảnh phải phân biệt quả tươi và quả đã qua EOL (không được kẹt ở ~44 giờ ≈ 1.86 ngày).

Nguyên nhân lỗi cũ: predictor.py gốc resize ảnh theo image.crop_width (1116) thay vì 224 lúc train,
khiến output luôn ≈ tâm chuẩn hoá. Adapter phải ép image_size theo checkpoint với MỌI thư mục dự án.
"""
from pathlib import Path

import pandas as pd
import pytest
from conftest import auth

from app import config

CANDIDATES = [Path(r"C:\Users\admin\Desktop\Strawberry-RUL-prediction"), config.PROJECT_DIR / "ml_model"]
DIRS = [d for d in CANDIDATES if (d / "src").is_dir() and (d / "data/02_processed/strawberry/final/metadata.csv").is_file()]


def _frames(root: Path):
    meta = pd.read_csv(root / "data/02_processed/strawberry/final/metadata.csv")
    f = meta[meta.fruit_id == "F01"].sort_values("timestamp").reset_index(drop=True)  # F01 = fold giữ lại của model D
    fresh = f.iloc[7]            # RUL thật ≈ 186 giờ
    eol = f.iloc[len(f) // 2 + 60]   # đã qua EOL (RUL thật = 0)
    assert fresh.rul_hours > 150 and eol.rul_hours == 0
    return root / fresh.image_path, root / eol.image_path


@pytest.mark.skipif(not DIRS, reason="Không có dự án model kèm dữ liệu ảnh có nhãn")
@pytest.mark.parametrize("model_dir", DIRS, ids=[d.name for d in DIRS])
def test_model_distinguishes_fresh_and_eol(client, model_dir):
    h = auth(client, "admin")
    r = client.post("/api/settings/model/load", headers=h, json={"path": str(model_dir), "fruits": ["strawberry"]})
    assert r.status_code == 200, r.text
    assert r.json()["model"]["meta"]["imageSize"] == 224
    fresh, eol = _frames(model_dir)
    out = {}
    for name, p in (("fresh", fresh), ("eol", eol)):
        t = client.post("/api/settings/model/test", headers=h, files={"file": (p.name, p.read_bytes(), "image/png")})
        assert t.status_code == 200, t.text
        out[name] = t.json()["rulHours"]
    assert out["fresh"] - out["eol"] > 24, out          # cách nhau > 1 ngày
    assert abs(out["fresh"] - 44.5) > 5 or abs(out["eol"] - 44.5) > 5, out   # không kẹt ở tâm chuẩn hoá
    client.post("/api/settings/model/unload", headers=h)

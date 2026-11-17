"""Tiền xử lý ảnh kiểm tra.

KHÔNG viết lại thuật toán: hàm tiền xử lý thật đến từ dự án model của bạn (nạp ở trang Cài đặt,
adapter `rul_adapters/custom.py` import nguyên văn `services/preprocessing.py::preprocess`).
Khi chưa gắn model ảnh, ảnh được giữ nguyên (chỉ đổi sang PNG).
"""
from __future__ import annotations

from pathlib import Path

from .rul import image_models


def read_image(path: str | Path):  # noqa: ANN201
    import cv2
    import numpy as np

    data = Path(path).read_bytes()
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("File không phải ảnh hợp lệ")
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:  # giống remove_alpha của dự án: nền trắng
        bgr = img[:, :, :3].astype(np.float32)
        a = img[:, :, 3:4].astype(np.float32) / 255.0
        img = np.clip(bgr * a + 255.0 * (1 - a), 0, 255).astype(np.uint8)
    return img


def run(raw_path: str | Path, out_path: str | Path, fruit_id: str | None = None) -> dict:
    """Đọc ảnh gốc → preprocess → ghi PNG (lossless) vào out_path. Trả về thông tin.
    fruit_id: nếu model ảnh không hỗ trợ loại quả này thì giữ nguyên ảnh."""
    import cv2

    img = read_image(raw_path)
    if fruit_id is not None and not image_models.supports(fruit_id):
        result, info = img, {"method": "none"}
    else:
        result, info = image_models.preprocess(img)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", result)
    if not ok:
        raise ValueError("Không ghi được ảnh đã tiền xử lý")
    out_path.write_bytes(buf.tobytes())
    info = dict(info)
    info["outputShape"] = list(result.shape)
    info["path"] = str(out_path)
    return info

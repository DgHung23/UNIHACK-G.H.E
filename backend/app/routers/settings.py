"""Trang Cài đặt: duyệt thư mục trên máy chạy backend, chọn model ảnh, nạp & chạy thử."""
from __future__ import annotations

import base64
import os
import string
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import config
from ..auth import require_roles
from ..db import get_db
from ..models import Fruit
from ..schemas import DialogIn, ModelLoadIn, ModelOptionsIn, PathIn
from ..services import preprocess as preprocess_svc
from ..services.rul import FUSION_MODES, image_models
from ..services.rul_adapters.custom import MODEL_EXTS, checkpoint_info, find_bundle_root, find_project_root, inspect_folder

router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(require_roles())])


def _validate_fruits(db: Session, fruits: Optional[list[str]]) -> None:
    if fruits is not None:
        unknown = [fid for fid in fruits if db.get(Fruit, fid) is None]
        if unknown:
            raise HTTPException(422, f"Loại quả không tồn tại: {', '.join(unknown)}")


def _shortcuts() -> list[dict]:
    out: list[dict] = []
    if config.DEFAULT_MODEL_DIR.is_dir():
        out.append({"name": "Model tích hợp sẵn (Bundled)", "path": str(config.DEFAULT_MODEL_DIR)})
    last = image_models.settings.get("path")
    if last and Path(last).is_dir():
        try:
            is_same = config.DEFAULT_MODEL_DIR.is_dir() and Path(last).resolve() == config.DEFAULT_MODEL_DIR.resolve()
        except Exception:
            is_same = False
        if not is_same:
            out.append({"name": "Model đã chọn gần nhất", "path": last})
    home = Path.home()
    out.append({"name": "Thư mục người dùng", "path": str(home)})
    for n, label in (("Desktop", "Desktop"), ("Downloads", "Downloads"), ("Documents", "Documents")):
        p = home / n
        if p.is_dir():
            out.append({"name": label, "path": str(p)})
    return out


def _drives() -> list[str]:
    if os.name != "nt":
        return ["/"]
    return [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]


@router.get("/fs")
def browse(path: Optional[str] = None, showHidden: bool = False) -> dict:
    """Liệt kê thư mục con + file model trong `path` (trên máy chạy backend)."""
    if not path:
        return {"path": None, "parent": None, "entries": [], "drives": _drives(), "shortcuts": _shortcuts()}
    p = Path(path).expanduser()
    if not p.exists() or not p.is_dir():
        raise HTTPException(404, f"Không phải thư mục: {path}")
    p = p.resolve()
    entries = []
    try:
        items = list(os.scandir(p))
    except PermissionError:
        raise HTTPException(403, f"Không có quyền đọc: {p}") from None
    for it in items:
        if not showHidden and (it.name.startswith(".") or it.name.startswith("$")):
            continue
        try:
            is_dir = it.is_dir()
        except OSError:
            continue
        ext = Path(it.name).suffix.lower()
        if is_dir:
            entries.append({"name": it.name, "path": it.path, "isDir": True})
        elif ext in MODEL_EXTS or it.name in ("fruitchain_model.json", "preprocess.py"):
            try:
                size = it.stat().st_size
            except OSError:
                size = 0
            entries.append({"name": it.name, "path": it.path, "isDir": False, "isModel": ext in MODEL_EXTS,
                            "sizeMb": round(size / 1e6, 2)})
    entries.sort(key=lambda e: (not e["isDir"], e["name"].lower()))
    proj = find_project_root(p)
    bundled = find_bundle_root(p)
    parent = str(p.parent) if p.parent != p else None
    return {"path": str(p), "parent": parent, "entries": entries[:1000], "truncated": len(entries) > 1000,
            "drives": _drives(), "shortcuts": _shortcuts(),
            "projectRoot": str(bundled or proj[0]) if bundled or proj else None,
            "modelFilesHere": sum(1 for e in entries if e.get("isModel"))}


_DIALOG_SCRIPT = r"""
import sys, tkinter as tk
from tkinter import filedialog
r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True); r.update()
p = filedialog.askdirectory(initialdir=sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else None,
                            title='Chọn thư mục model', mustexist=True)
r.destroy()
sys.stdout.write(p or '')
"""


@router.post("/fs/native-dialog")
def native_dialog(body: DialogIn) -> dict:
    """Mở hộp thoại chọn thư mục của Windows trên máy chạy backend (chỉ khi backend chạy trên máy bạn)."""
    try:
        res = subprocess.run([sys.executable, "-c", _DIALOG_SCRIPT, body.initial or ""], capture_output=True,
                             text=True, timeout=600, encoding="utf-8")
    except subprocess.TimeoutExpired:
        raise HTTPException(408, "Hết thời gian chờ chọn thư mục") from None
    except Exception as e:  # noqa: BLE001
        raise HTTPException(501, f"Không mở được hộp thoại: {e}") from None
    if res.returncode != 0:
        raise HTTPException(501, f"Không mở được hộp thoại hệ thống: {res.stderr.strip()[-300:]}")
    path = res.stdout.strip()
    return {"path": str(Path(path).resolve()) if path else None}


@router.post("/model/inspect")
def inspect(body: PathIn) -> dict:
    try:
        info = inspect_folder(body.path)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from None
    if info.get("defaultCheckpoint"):
        info["defaultCheckpointInfo"] = checkpoint_info(info["defaultCheckpoint"])
    return info


@router.post("/model/checkpoint-info")
def ckpt_info(body: PathIn) -> dict:
    if not Path(body.path).is_file():
        raise HTTPException(404, "Không thấy file")
    return checkpoint_info(body.path)


@router.get("/model")
def model_status(db: Session = Depends(get_db)) -> dict:
    st = image_models.status()
    st["fruits"] = [{"fruitId": f.fruit_id, "nameVi": f.name_vi} for f in db.query(Fruit).all()]
    st["settingsFile"] = str(config.MODEL_SETTINGS_FILE)
    st["defaultModelPath"] = str(config.DEFAULT_MODEL_DIR) if config.DEFAULT_MODEL_DIR.is_dir() else None
    return st


@router.post("/model/load")
def load_model(body: ModelLoadIn, db: Session = Depends(get_db)) -> dict:
    _validate_fruits(db, body.fruits)
    if body.fusion and body.fusion not in FUSION_MODES:
        raise HTTPException(422, f"fusion phải là một trong {FUSION_MODES}")
    try:
        return image_models.load(db, path=body.path, checkpoint=body.checkpoint, device=body.device,
                                 output_unit=body.outputUnit, fruits=body.fruits, fusion=body.fusion,
                                 use_sensor_inputs=body.useSensorInputs)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from None
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Nạp model thất bại — {type(e).__name__}: {e}") from None


@router.post("/model/unload")
def unload_model() -> dict:
    return image_models.unload()


@router.post("/model/options")
def model_options(body: ModelOptionsIn, db: Session = Depends(get_db)) -> dict:
    _validate_fruits(db, body.fruits)
    if body.fusion and body.fusion not in FUSION_MODES:
        raise HTTPException(422, f"fusion phải là một trong {FUSION_MODES}")
    try:
        return image_models.update_options(**body.model_dump())
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


@router.post("/model/test")
async def test_model(file: UploadFile = File(...), fruitId: Optional[str] = Form(None),
                     tempC: Optional[float] = Form(None), humidityPct: Optional[float] = Form(None),
                     db: Session = Depends(get_db)) -> dict:
    """Chạy thử: ảnh → preprocess của dự án → model → RUL. Không ghi DB/ledger."""
    m = image_models.model
    if m is None:
        raise HTTPException(409, "Chưa nạp model. Chọn thư mục và bấm 'Nạp model' trước.")
    content = await file.read()
    fid = fruitId or (m.fruits[0] if m.fruits else "strawberry")
    fruit = db.get(Fruit, fid)
    if fruit is None:
        raise HTTPException(422, f"Không có loại quả {fid}")
    if not image_models.supports(fid):
        raise HTTPException(422, f"Model không áp dụng cho loại quả '{fid}' (xem mục 'Áp dụng cho loại quả')")
    tmp = Path(tempfile.mkdtemp(prefix="fc_test_", dir=str(config.STORAGE_DIR)))
    try:
        raw = tmp / ("input" + (Path(file.filename or "").suffix or ".jpg"))
        raw.write_bytes(content)
        t0 = time.perf_counter()
        try:
            pre = preprocess_svc.run(raw, tmp / "pre.png")
        except Exception as e:  # noqa: BLE001
            raise HTTPException(422, f"Tiền xử lý thất bại: {e}") from None
        t1 = time.perf_counter()
        readings = [{"tempC": tempC, "humidityPct": humidityPct}] if (tempC is not None or humidityPct is not None) else None
        try:
            out = image_models.predict(fruit, "TEST", str(tmp / "pre.png"), readings)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(422, f"Model lỗi khi suy luận — {type(e).__name__}: {e}") from None
        t2 = time.perf_counter()
        if out is None:
            raise HTTPException(422, f"Model không áp dụng cho loại quả '{fid}' (xem mục 'Áp dụng cho loại quả')")
        img_b64 = base64.b64encode((tmp / "pre.png").read_bytes()).decode()
        return {"fruitId": fid, "rulDays": out.rul_days, "rulHours": round(out.rul_days * 24, 2),
                "ciLowDays": out.ci_low_days, "ciHighDays": out.ci_high_days, "freshness": out.freshness,
                "extra": out.extra, "preprocess": {k: v for k, v in pre.items() if k != "path"},
                "preprocessedImage": f"data:image/png;base64,{img_b64}", "modelVersion": m.version,
                "modelHash": m.model_hash(),
                "latencyMs": {"preprocess": round((t1 - t0) * 1000, 1), "predict": round((t2 - t1) * 1000, 1)}}
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)

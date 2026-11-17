"""Adapter cho model ảnh ĐÃ HUẤN LUYỆN của bạn (mục 5.1).

Bạn chỉ cần trỏ tới một thư mục (trang Cài đặt → Duyệt thư mục). Adapter tự nhận dạng:

1. **Dự án model** (ví dụ `Strawberry-RUL-prediction`): có `src/<pkg>/services/predictor.py` và
   `src/<pkg>/services/preprocessing.py`. Adapter import NGUYÊN VĂN hàm `preprocess()` và lớp
   `FruitRULPredictor` của dự án (không viết lại → không lệch với lúc huấn luyện) và nạp checkpoint
   được chọn trong thư mục.
2. **Model rời** (`.onnx`, TorchScript `.pt`, hoặc `nn.Module` lưu nguyên bằng `torch.save`):
   resize + chuẩn hoá ImageNet; nếu thư mục có `preprocess.py` với hàm `preprocess(image_bgr)` thì gọi hàm đó.
   Có thể ghi `fruitchain_model.json` để khai báo `imageSize`, `seqLen`, `outputUnit`, `labels`...
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import math
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from .base import RulInput, RulOutput

MODEL_EXTS = {".pt", ".pth", ".onnx", ".ts", ".torchscript", ".jit"}
SKIP_DIRS = {".git", ".venv", "venv", "env", "node_modules", "__pycache__", "site-packages", ".idea", ".vscode",
             "data", "dataset", "datasets", "logs", "output", "outputs", "notebooks", "docs", "research", "samples"}
PROJECT_MODULES = ("services", "utils_app", "schemas", "api", "config_app", "shared", "training")
MAX_SCAN_FILES = 400


def find_bundle_root(folder: Path) -> Optional[Path]:
    for candidate in (folder.resolve(), *list(folder.resolve().parents)[:6]):
        manifest = candidate / "fruitchain_model.json"
        if manifest.is_file():
            document = json.loads(manifest.read_text(encoding="utf-8-sig"))
            if document.get("format") == "fruitchain-bundle":
                return candidate
    return None


def bundle_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise FileNotFoundError(f"File bundle không hợp lệ hoặc không tồn tại: {relative}")
    return path


# ---------------------------------------------------------------- nhận dạng thư mục

def find_project_root(folder: Path) -> Optional[tuple[Path, str]]:
    """Tìm thư mục gốc dự án (chứa src/<pkg>/services/predictor.py) từ folder hoặc các thư mục cha."""
    cur = folder.resolve()
    for _ in range(6):
        src = cur / "src"
        if src.is_dir():
            for pkg in sorted(p for p in src.iterdir() if p.is_dir()):
                svc = pkg / "services"
                if (svc / "predictor.py").is_file() and (svc / "preprocessing.py").is_file():
                    return cur, pkg.name
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def scan_model_files(folder: Path) -> list[Path]:
    found: list[Path] = []
    for root, dirs, files in os.walk(folder):
        rel_depth = len(Path(root).relative_to(folder).parts)
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS and not d.startswith(".")] if rel_depth < 8 else []
        for f in files:
            if Path(f).suffix.lower() in MODEL_EXTS:
                found.append(Path(root) / f)
                if len(found) >= MAX_SCAN_FILES:
                    return found
    return found


def _project_config(root: Path, pkg: str) -> tuple[dict, Optional[Path]]:
    cfg_path = root / "src" / pkg / "config_app" / "config.json"
    if cfg_path.is_file():
        with open(cfg_path, "r", encoding="utf-8-sig") as f:
            return json.load(f), cfg_path
    return {}, None


def _rank_checkpoint(p: Path, preferred: Optional[Path]) -> tuple:
    s = p.as_posix().lower()
    return (
        0 if preferred and p.resolve() == preferred.resolve() else 1,
        0 if "production" in s else 1,
        0 if p.name.lower().startswith("best") else 1,
        len(p.parts),
        s,
    )


def inspect_folder(folder: str | Path | None = None) -> dict:
    """Xem thư mục chứa gì (không nạp trọng số)."""
    if folder is None or (isinstance(folder, str) and not folder.strip()):
        from ... import config
        folder = config.DEFAULT_MODEL_DIR
    folder = Path(folder).expanduser()
    if not folder.exists():
        raise FileNotFoundError(f"Không tồn tại: {folder}")
    if folder.is_file():
        folder = folder.parent
    folder = folder.resolve()
    bundle_root = find_bundle_root(folder)
    if bundle_root:
        manifest = json.loads((bundle_root / "fruitchain_model.json").read_text(encoding="utf-8-sig"))
        if manifest.get("schemaVersion") != 1:
            raise ValueError("Phiên bản manifest model chưa được hỗ trợ")
        preferred = bundle_file(bundle_root, manifest["checkpoint"])
        config_path = bundle_file(bundle_root, manifest["config"])
        package = manifest["package"]
        if not package.isidentifier():
            raise ValueError("Tên package model không hợp lệ")
        return dict(path=str(bundle_root), kind="bundle", projectRoot=str(bundle_root), package=package,
                    configPath=str(config_path), manifestPath=str(bundle_root / "fruitchain_model.json"), fruits=manifest["fruits"],
                    preprocessFn=f"{package}.runtime.RulPredictor.preprocess",
                    predictorClass=f"{package}.runtime.RulPredictor", notes=["Runtime suy luận độc lập, không import pipeline huấn luyện."],
                    checkpoints=[dict(path=str(p.resolve()), rel=p.relative_to(bundle_root).as_posix(),
                                      sizeMb=round(p.stat().st_size / 1e6, 2),
                                      modified=time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime)))
                                 for p in sorted(scan_model_files(bundle_root), key=lambda p: _rank_checkpoint(p, preferred))],
                    defaultCheckpoint=str(preferred))
    proj = find_project_root(folder)
    scan_root = folder
    files = scan_model_files(scan_root)
    preferred: Optional[Path] = None
    info: dict[str, Any] = {"path": str(folder), "kind": "unknown", "projectRoot": None, "package": None,
                            "notes": []}
    if proj:
        root, pkg = proj
        cfg, cfg_path = _project_config(root, pkg)
        mp = (cfg.get("model") or {}).get("path") or cfg.get("model_path")
        if mp:
            preferred = Path(mp) if Path(mp).is_absolute() else root / mp
        if not files and scan_root == root:
            files = scan_model_files(root / "models") if (root / "models").is_dir() else []
        info.update(kind="project", projectRoot=str(root), package=pkg,
                    configPath=str(cfg_path) if cfg_path else None,
                    preprocessFn=f"src/{pkg}/services/preprocessing.py::preprocess",
                    predictorClass=f"src/{pkg}/services/predictor.py::FruitRULPredictor",
                    projectModel=(cfg.get("model") or {}))
        info["notes"].append("Dùng nguyên văn hàm preprocess() và FruitRULPredictor của dự án.")
        if preferred and preferred.is_file() and preferred.resolve() not in {f.resolve() for f in files}:
            files.insert(0, preferred)
    elif files:
        info["kind"] = "generic"
        if (folder / "preprocess.py").is_file():
            info["preprocessFn"] = "preprocess.py::preprocess"
        if (folder / "fruitchain_model.json").is_file():
            info["configPath"] = str(folder / "fruitchain_model.json")
        info["notes"].append("Model rời: hỗ trợ .onnx, TorchScript, hoặc nn.Module lưu nguyên. "
                             "Checkpoint chỉ có state_dict cần chọn thư mục dự án chứa code model.")
    else:
        info["notes"].append("Không thấy file model (.pt/.pth/.onnx) hay dự án có src/<pkg>/services/predictor.py.")

    files = sorted(set(files), key=lambda p: _rank_checkpoint(p, preferred))
    base = Path(info["projectRoot"]) if info["projectRoot"] else folder
    info["checkpoints"] = []
    for p in files:
        try:
            rel = p.resolve().relative_to(base).as_posix()
        except ValueError:
            rel = str(p)
        st = p.stat()
        info["checkpoints"].append({"path": str(p.resolve()), "rel": rel, "sizeMb": round(st.st_size / 1e6, 2),
                                    "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))})
    info["defaultCheckpoint"] = info["checkpoints"][0]["path"] if info["checkpoints"] else None
    return info


def checkpoint_info(path: str | Path) -> dict:
    """Đọc metadata trong checkpoint (model_key, config, val_mae...) — không dựng model."""
    p = Path(path)
    out: dict[str, Any] = {"path": str(p), "sizeMb": round(p.stat().st_size / 1e6, 2)}
    if p.suffix.lower() == ".onnx":
        try:
            import onnxruntime as ort  # type: ignore
            sess = ort.InferenceSession(str(p), providers=["CPUExecutionProvider"])
            out["format"] = "onnx"
            out["inputs"] = [{"name": i.name, "shape": [str(d) for d in i.shape]} for i in sess.get_inputs()]
            out["outputs"] = [{"name": o.name, "shape": [str(d) for d in o.shape]} for o in sess.get_outputs()]
        except Exception as e:  # noqa: BLE001
            out["error"] = str(e)
        return out
    import torch

    try:
        torch.jit.load(str(p), map_location="cpu")
        out["format"] = "torchscript"
        return out
    except Exception:  # noqa: BLE001
        pass
    try:
        ck = torch.load(str(p), map_location="cpu", weights_only=False)
    except Exception as e:  # noqa: BLE001
        out["error"] = f"Không đọc được checkpoint: {e}"
        return out
    if isinstance(ck, torch.nn.Module):
        out["format"] = "torch-module"
        out["class"] = type(ck).__name__
        return out
    if isinstance(ck, dict):
        out["format"] = "checkpoint-dict"
        out["keys"] = list(ck.keys())[:30]
        for k in ("model_key", "epoch", "fold_name", "test_group", "val_group", "val_mae", "target_scaler"):
            if k in ck:
                v = ck[k]
                out[k] = float(v) if hasattr(v, "item") else v
        cfg = ck.get("config")
        if isinstance(cfg, dict):
            out["config"] = {k: cfg[k] for k in ("run_name", "seq_len", "fusion_mode", "temporal_pooling",
                                                 "image_size", "use_cbam", "hidden_size") if k in cfg}
    return out


def file_sha256(*paths: Optional[Path]) -> str:
    h = hashlib.sha256()
    for p in paths:
        if p and Path(p).is_file():
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- model

class CustomModel:
    """Model ảnh của bạn. Dùng: CustomModel(folder, checkpoint).load()"""

    name = "custom"
    uses_images = True

    def __init__(self, folder: str | Path | None = None, checkpoint: Optional[str] = None, *, device: str = "auto",
                 output_unit: str = "auto", fruits: Optional[list[str]] = None, use_sensor_inputs: bool = True):
        if folder is None or (isinstance(folder, str) and not folder.strip()):
            from ... import config
            folder = config.DEFAULT_MODEL_DIR
        self.info = inspect_folder(folder)
        self.folder = Path(self.info["path"])
        ck = checkpoint or self.info.get("defaultCheckpoint")
        if not ck:
            raise FileNotFoundError("Thư mục không có file model (.pt/.pth/.onnx).")
        ckp = Path(ck)
        if not ckp.is_absolute():
            base = Path(self.info["projectRoot"] or self.folder)
            ckp = base / ckp
        if not ckp.is_file():
            raise FileNotFoundError(f"Không thấy checkpoint: {ckp}")
        self.checkpoint = ckp.resolve()
        self.kind = self.info["kind"] if self.info["kind"] != "unknown" else "generic"
        if self.kind == "bundle":
            manifest = json.loads(Path(self.info["manifestPath"]).read_text(encoding="utf-8-sig"))
            supported = manifest.get("fruits") or []
            if fruits is not None and not set(fruits).issubset(supported):
                raise ValueError(f"Bundle chỉ hỗ trợ: {', '.join(supported)}")
            fruits = fruits if fruits is not None else supported
        self.device_name = device
        self.output_unit = output_unit
        self.use_sensor_inputs = use_sensor_inputs
        self.uses_readings = use_sensor_inputs
        self.fruits = fruits
        self._lock = threading.Lock()
        self._sys_paths: list[str] = []
        self._bundle_namespace: Optional[str] = None
        self._bundle_runtime = None
        self._preprocess_fn: Optional[Callable] = None
        self._predict_fn: Optional[Callable] = None
        self.meta: dict[str, Any] = {}
        self.config_path: Optional[Path] = Path(self.info["configPath"]) if self.info.get("configPath") else None
        self._hash: Optional[str] = None
        self.version = "custom"
        self.loaded_at: Optional[str] = None
        self.load_seconds: Optional[float] = None

    # ---------------- public
    def model_hash(self) -> str:
        if self._hash is None:
            if self.kind == "bundle":
                root = Path(self.info["projectRoot"])
                manifest = json.loads((root / "fruitchain_model.json").read_text(encoding="utf-8-sig"))
                paths = ["fruitchain_model.json", manifest["config"], *manifest["provenanceFiles"]]
                digest = hashlib.sha256()
                digest.update(b"checkpoint\0")
                with self.checkpoint.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1 << 20), b""):
                        digest.update(chunk)
                for relative in sorted(set(paths)):
                    digest.update(relative.encode("utf-8") + b"\0")
                    digest.update(bundle_file(root, relative).read_bytes())
                self._hash = digest.hexdigest()
            else:
                self._hash = file_sha256(self.checkpoint, self.config_path)
        return self._hash

    def describe(self) -> dict:
        return {
            "name": self.name, "version": self.version, "modelHash": self.model_hash(), "kind": self.kind,
            "folder": str(self.folder), "projectRoot": self.info.get("projectRoot"), "checkpoint": str(self.checkpoint),
            "configPath": str(self.config_path) if self.config_path else None, "device": self.device_name,
            "outputUnit": self.output_unit, "fruits": self.fruits, "useSensorInputs": self.use_sensor_inputs,
            "preprocessFn": self.info.get("preprocessFn"), "meta": self.meta, "loadedAt": self.loaded_at,
            "loadSeconds": self.load_seconds,
        }

    def load(self) -> "CustomModel":
        t0 = time.time()
        if self.device_name == "auto":
            try:
                import torch
                self.device_name = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:  # noqa: BLE001
                self.device_name = "cpu"
        if self.kind == "bundle":
            self._load_bundle()
        elif self.kind == "project":
            self._load_project()
        else:
            self._load_generic()
        if self.output_unit == "auto":
            self.output_unit = self.meta.get("outputUnit", "hours" if self.kind in ("project", "bundle") else "days")
        h = self.model_hash()
        key = self.meta.get("model_key") or self.checkpoint.stem
        self.version = f"custom-{key}-{h[:8]}"
        self.loaded_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.load_seconds = round(time.time() - t0, 2)
        return self

    def unload(self) -> None:
        self._predict_fn = None
        self._preprocess_fn = None
        self._bundle_runtime = None
        if self._bundle_namespace:
            for name in list(sys.modules):
                if name == self._bundle_namespace or name.startswith(self._bundle_namespace + "."):
                    del sys.modules[name]
            self._bundle_namespace = None
        for p in self._sys_paths:
            while p in sys.path:
                sys.path.remove(p)
        self._sys_paths = []

    def preprocess(self, image_bgr) -> tuple[Any, dict]:  # noqa: ANN001
        """Trả về (ảnh đã tiền xử lý dạng ndarray, thông tin)."""
        if self._preprocess_fn is None:
            return image_bgr, {"method": "none"}
        with self._lock:
            return self._preprocess_fn(image_bgr)

    def predict(self, x: RulInput) -> RulOutput:
        if self._predict_fn is None:
            raise RuntimeError("Model chưa được nạp")
        import cv2

        img = cv2.imread(str(x.image_path), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"Không đọc được ảnh: {x.image_path}")
        temp = hum = None
        if self.use_sensor_inputs and x.readings:
            last = x.readings[-1]
            temp, hum = last.get("tempC"), last.get("humidityPct")
        with self._lock:
            raw, extra = self._predict_fn(img, temp, hum)
        raw = float(raw)
        if not math.isfinite(raw):
            raise ValueError("Model trả về RUL không hữu hạn (NaN/Infinity). Kiểm tra checkpoint và đầu vào.")
        unit = self.output_unit
        days = raw / 24.0 if unit == "hours" else raw
        days = max(0.0, days)
        extra = dict(extra or {})
        extra.update(rawOutput=round(raw, 4), outputUnit=unit, sensorInputs={"tempC": temp, "humidityPct": hum})
        return RulOutput(rul_days=round(days, 2), ci_low_days=extra.pop("ciLowDays", None),
                         ci_high_days=extra.pop("ciHighDays", None), freshness=extra.pop("freshness", None),
                         extra=extra)

    def _load_bundle(self) -> None:
        root = Path(self.info["projectRoot"])
        package = self.info["package"]
        package_dir = root / "src" / package
        initializer = bundle_file(root, f"src/{package}/__init__.py")
        # An instance-specific package namespace prevents folder switches from sharing cached modules.
        namespace = f"_fruitchain_ml_{uuid.uuid4().hex}"
        self._bundle_namespace = namespace
        spec = importlib.util.spec_from_file_location(namespace, initializer,
                                                      submodule_search_locations=[str(package_dir)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[namespace] = module
        spec.loader.exec_module(module)
        runtime_module = importlib.import_module(f"{namespace}.runtime")
        predictor = runtime_module.RulPredictor(root, self.checkpoint, self.device_name)
        self._bundle_runtime = predictor
        self.device_name = str(predictor.device)
        self.meta.update(predictor.metadata)
        self.meta["supportedFruits"] = json.loads(Path(self.info["manifestPath"]).read_text(encoding="utf-8-sig"))["fruits"]
        self.meta["checkpointSha256"] = file_sha256(self.checkpoint)

        def prepare(image_bgr):
            result = predictor.preprocess(image_bgr)
            return result.roi, dict(method=self.info["preprocessFn"], confidence=round(float(result.confidence), 4),
                                    bbox=[int(value) for value in result.bbox])

        def predict(img, temp, humidity):
            return predictor.predict_hours(img, temp, humidity), {"confidenceNote": predictor.metadata["confidenceNote"]}

        self._preprocess_fn, self._predict_fn = prepare, predict

    # ---------------- dự án có sẵn (vd. Strawberry-RUL-prediction)
    def _purge_project_modules(self) -> None:
        pkg = self.info["package"]
        # Module của FruitChain đều nằm dưới gói `app.` nên không bị ảnh hưởng.
        for name in list(sys.modules):
            top = name.split(".")[0]
            if top in PROJECT_MODULES or top == pkg:
                del sys.modules[name]

    def _load_project(self) -> None:
        root = Path(self.info["projectRoot"])
        pkg = self.info["package"]
        self._purge_project_modules()
        for p in (str(root), str(root / "src" / pkg), str(root / "src")):
            if p not in sys.path:
                sys.path.insert(0, p)
                self._sys_paths.append(p)
        prep_mod = importlib.import_module("services.preprocessing")
        pred_mod = importlib.import_module("services.predictor")
        preprocess = getattr(prep_mod, "preprocess")
        Predictor = getattr(pred_mod, "FruitRULPredictor")

        cfg, _ = _project_config(root, pkg)
        cfg = json.loads(json.dumps(cfg))
        cfg.setdefault("model", {})["path"] = str(self.checkpoint)
        cfg.setdefault("model", {})["image_size"] = 224
        cfg["device"] = self.device_name
        predictor = Predictor(config=cfg, project_root=root)
        ensure = getattr(predictor, "_ensure_model", None)
        if callable(ensure):
            ensure()
        ck = getattr(predictor, "checkpoint", None) or {}
        if isinstance(ck, dict):
            for k in ("model_key", "fold_name", "test_group", "val_mae", "epoch"):
                if k in ck:
                    v = ck[k]
                    self.meta[k] = float(v) if hasattr(v, "item") else v
            c = ck.get("config") or {}
            self.meta["config"] = {k: c[k] for k in ("run_name", "seq_len", "fusion_mode", "temporal_pooling",
                                                     "image_size") if k in c}
        # Kích thước ảnh phải đúng như lúc train (checkpoint config.image_size, mặc định 224).
        # predictor.py gốc của dự án lấy nhầm image.crop_width (=1116) → output luôn ≈ tâm chuẩn hoá
        # (~44 giờ ≈ 1.86 ngày) với MỌI ảnh. Sửa ở adapter để không phụ thuộc bản predictor.py nào được chọn.
        train_size = int(((ck.get("config") or {}) if isinstance(ck, dict) else {}).get("image_size") or 224)
        found_size = getattr(predictor, "image_size", None)
        if found_size != train_size:
            predictor.image_size = train_size
            self.meta["imageSizeFix"] = f"predictor.image_size {found_size} → {train_size} (theo checkpoint)"
        self.meta["imageSize"] = train_size
        self.meta["seqLen"] = getattr(predictor, "seq_len", None)
        self.meta["outputUnit"] = "hours"  # target huấn luyện: rul_hours
        self.uses_readings = self.use_sensor_inputs

        def _pre(image_bgr):  # noqa: ANN001, ANN202
            # Gọi y hệt route POST /api/predict của dự án: preprocess(image, config)
            res = preprocess(image_bgr, cfg)
            if res is None:
                raise ValueError("Tiền xử lý không tìm thấy quả trong ảnh (preprocess() trả về None).")
            return res.roi, {"method": self.info["preprocessFn"], "confidence": round(float(res.confidence), 4),
                             "bbox": [int(v) for v in res.bbox]}

        def _pred(img, temp, hum):  # noqa: ANN001, ANN202
            rul, conf = predictor.predict(img, temperature_c=temp, humidity_pct=hum)
            return rul, {"modelConfidence": round(float(conf), 4)}

        self._preprocess_fn = _pre
        self._predict_fn = _pred

    # ---------------- model rời
    def _load_generic(self) -> None:
        import numpy as np

        cfg: dict[str, Any] = {}
        cfg_file = self.folder / "fruitchain_model.json"
        if cfg_file.is_file():
            cfg = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
            self.config_path = cfg_file
        size = int(cfg.get("imageSize", 224))
        seq_len = int(cfg.get("seqLen", 1))
        labels = cfg.get("labels")
        class_rul = cfg.get("classRulDays") or {}
        mean = np.array(cfg.get("mean", [0.485, 0.456, 0.406]), dtype=np.float32)
        std = np.array(cfg.get("std", [0.229, 0.224, 0.225]), dtype=np.float32)
        if "outputUnit" in cfg:
            self.meta["outputUnit"] = cfg["outputUnit"]

        user_pre = None
        pp = self.folder / "preprocess.py"
        if pp.is_file():
            spec = importlib.util.spec_from_file_location("fruitchain_user_preprocess", pp)
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            user_pre = getattr(mod, "preprocess", None)

        def _pre(image_bgr):  # noqa: ANN001, ANN202
            if user_pre is None:
                return image_bgr, {"method": "none"}
            out = user_pre(image_bgr)
            if out is None:
                raise ValueError("preprocess.py trả về None")
            return out, {"method": "preprocess.py::preprocess"}

        def to_array(img, five_d: bool):  # noqa: ANN001, ANN202
            import cv2

            if img.ndim == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            if img.shape[2] == 4:
                a = img[:, :, 3:4].astype(np.float32) / 255.0
                img = (img[:, :, :3].astype(np.float32) * a + 255.0 * (1 - a)).astype(np.uint8)
            img = cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            arr = ((rgb - mean) / std).transpose(2, 0, 1)[None]
            if five_d:
                arr = np.repeat(arr[:, None], seq_len, axis=1)
            return arr.astype(np.float32)

        def interpret(out) -> tuple[float, dict]:  # noqa: ANN001
            flat = np.asarray(out, dtype=np.float32).reshape(-1)
            if flat.size == 1 or not labels:
                return float(flat[0]), {}
            e = np.exp(flat - flat.max())
            prob = e / e.sum()
            i = int(prob.argmax())
            lab = labels[i] if i < len(labels) else str(i)
            rul = float(class_rul.get(lab, 0.0))
            ext = {"label": lab, "probabilities": {labels[j]: round(float(prob[j]), 4) for j in range(len(labels))}}
            if lab in ("FRESH", "GOOD", "NEAR_EXPIRY", "EXPIRED"):
                ext["freshness"] = lab
            return rul, ext

        suffix = self.checkpoint.suffix.lower()
        if suffix == ".onnx":
            import onnxruntime as ort  # type: ignore

            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if self.device_name == "cuda" else ["CPUExecutionProvider"]
            sess = ort.InferenceSession(str(self.checkpoint), providers=providers)
            inp = sess.get_inputs()[0]
            five = len(inp.shape) == 5
            if not five and len(inp.shape) == 4 and isinstance(inp.shape[2], int):
                size = int(inp.shape[2])
            self.meta.update(format="onnx", input=[str(d) for d in inp.shape])

            def _pred(img, _t, _h):  # noqa: ANN001, ANN202
                out = sess.run(None, {inp.name: to_array(img, five)})[0]
                return interpret(out)
        else:
            import torch

            dev = torch.device(self.device_name if (self.device_name != "cuda" or torch.cuda.is_available()) else "cpu")
            try:
                model = torch.jit.load(str(self.checkpoint), map_location=dev)
                self.meta["format"] = "torchscript"
            except Exception:  # noqa: BLE001
                obj = torch.load(str(self.checkpoint), map_location=dev, weights_only=False)
                if not isinstance(obj, torch.nn.Module):
                    raise ValueError("Checkpoint chỉ chứa trọng số (state_dict), không có kiến trúc model. "
                                     "Hãy chọn thư mục DỰ ÁN chứa code model (src/<pkg>/services/predictor.py), "
                                     "hoặc xuất model sang TorchScript/ONNX.")
                model = obj
                self.meta["format"] = "torch-module"
            model.eval()
            five = seq_len > 1

            def _pred(img, _t, _h):  # noqa: ANN001, ANN202
                with torch.no_grad():
                    out = model(torch.from_numpy(to_array(img, five)).to(dev))
                if isinstance(out, (tuple, list)):
                    out = out[0]
                return interpret(out.detach().cpu().numpy())

        self.meta["seqLen"] = seq_len
        self._preprocess_fn = _pre
        self._predict_fn = _pred

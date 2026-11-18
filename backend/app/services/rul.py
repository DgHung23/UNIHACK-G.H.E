"""Dịch vụ RUL: baseline Q10 cho cảm biến + quản lý model ảnh (chọn adapter q10|custom)."""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from .. import config
from ..models import Fruit, ModelVersion, RulPoint
from .rul_adapters.base import RulInput, RulOutput, freshness_from_rul
from .rul_adapters.custom import CustomModel
from .rul_adapters.q10 import VERSION as Q10_VERSION, Q10Model, compute_series, next_point, q10_model_hash  # noqa: F401

log = logging.getLogger("fruitchain.rul")

ADAPTERS = {"q10": None, "custom": CustomModel}
FUSION_MODES = ("min", "mean", "sensor_only", "image_only", "model")


def fruits_map(db: Session) -> dict[str, Fruit]:
    return {f.fruit_id: f for f in db.query(Fruit).all()}


def sensor_model(db: Session) -> Q10Model:
    fr = db.query(Fruit).all()
    return Q10Model({f.fruit_id: f for f in fr}, [f.raw for f in fr])


def point_dict(p: RulPoint) -> dict:
    return dict(batchId=p.batch_id, ts=p.ts, tempC=p.temp_c, effectiveHoursConsumed=p.effective_hours,
                fractionUsed=p.fraction_used, rulDaysAtCurrent=p.rul_at_current, rulDaysAtOptimal=p.rul_at_optimal,
                ciLowDays=p.ci_low, ciHighDays=p.ci_high, freshness=p.freshness)


def latest_point(db: Session, batch_id: str) -> Optional[RulPoint]:
    return db.query(RulPoint).filter(RulPoint.batch_id == batch_id).order_by(RulPoint.ts.desc()).first()


def snapshot_from_point(p: Optional[RulPoint], model_hash: str, fruit: Optional[Fruit] = None) -> dict:
    if p is None:
        shelf = float(fruit.shelf_ref_days) if fruit else 0.0
        return dict(rulDaysAtCurrent=shelf, rulDaysAtOptimal=shelf, ciLowDays=round(shelf * 0.85, 2),
                    ciHighDays=round(shelf * 1.15, 2), freshness="FRESH", tempC=None,
                    modelVersion=Q10_VERSION, modelHash=model_hash)
    return dict(rulDaysAtCurrent=p.rul_at_current, rulDaysAtOptimal=p.rul_at_optimal, ciLowDays=p.ci_low,
                ciHighDays=p.ci_high, freshness=p.freshness, tempC=p.temp_c, modelVersion=Q10_VERSION,
                modelHash=model_hash)


def fuse(rul_sensor: Optional[float], rul_image: Optional[float], mode: str) -> Optional[float]:
    if rul_image is None:
        return rul_sensor
    if rul_sensor is None:
        return rul_image
    if mode == "mean":
        return round((rul_sensor + rul_image) / 2, 2)
    if mode == "sensor_only":
        return rul_sensor
    if mode in ("image_only", "model"):
        return rul_image
    return min(rul_sensor, rul_image)


# ---------------------------------------------------------------- model ảnh (trang Cài đặt)

DEFAULT_SETTINGS = {
    "mode": "custom" if config.DEFAULT_MODEL_DIR.is_dir() else "q10",
    "path": str(config.DEFAULT_MODEL_DIR) if config.DEFAULT_MODEL_DIR.is_dir() else "",
    "checkpoint": "",
    "device": "auto",
    "outputUnit": "auto",
    "fruits": ["strawberry"],
    "fusion": config.FUSION if config.FUSION in FUSION_MODES else "min",
    "useSensorInputs": True,
}


class ImageModelManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.model: Optional[CustomModel] = None
        self.error: Optional[str] = None
        self.loading = False
        self.settings = self._read_settings()

    # -------- settings
    def _read_settings(self) -> dict:
        s = dict(DEFAULT_SETTINGS)
        try:
            if config.MODEL_SETTINGS_FILE.exists():
                s.update(json.loads(config.MODEL_SETTINGS_FILE.read_text(encoding="utf-8")))
        except Exception as e:  # noqa: BLE001
            log.warning("Không đọc được %s: %s", config.MODEL_SETTINGS_FILE, e)
        if config.DEFAULT_MODEL_DIR.is_dir():
            configured_path = s.get("path")
            if not configured_path or not Path(configured_path).exists():
                s["path"] = str(config.DEFAULT_MODEL_DIR)
                if s.get("checkpoint") and not Path(s["checkpoint"]).exists():
                    s["checkpoint"] = ""
                if s.get("mode") != "q10" or not config.MODEL_SETTINGS_FILE.exists():
                    s["mode"] = "custom"
        return s

    def _write_settings(self) -> None:
        config.MODEL_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = config.MODEL_SETTINGS_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(config.MODEL_SETTINGS_FILE)

    @property
    def fusion(self) -> str:
        return self.settings.get("fusion", "min")

    def update_options(self, **kw: Any) -> dict:
        with self._lock:
            if self.model is not None and self.model.kind == "bundle" and kw.get("fruits") is not None:
                supported = self.model.meta.get("supportedFruits") or []
                if not set(kw["fruits"]).issubset(supported):
                    raise ValueError(f"Bundle chỉ hỗ trợ: {', '.join(supported)}")
            for k in ("fusion", "fruits", "useSensorInputs"):
                if k in kw and kw[k] is not None:
                    self.settings[k] = kw[k]
            if self.model is not None:
                if "fruits" in kw and kw["fruits"] is not None:
                    self.model.fruits = kw["fruits"]
                if "useSensorInputs" in kw and kw["useSensorInputs"] is not None:
                    self.model.use_sensor_inputs = self.model.uses_readings = bool(kw["useSensorInputs"])
            self._write_settings()
            return self.status()

    # -------- status
    def status(self) -> dict:
        m = self.model
        return {
            "active": "custom" if m else "q10",
            "loading": self.loading,
            "error": self.error,
            "settings": self.settings,
            "fusionModes": list(FUSION_MODES),
            "model": m.describe() if m else None,
        }

    def supports(self, fruit_id: str) -> bool:
        m = self.model
        return bool(m) and (not m.fruits or fruit_id in m.fruits)

    # -------- load/unload
    def load(self, db: Optional[Session], *, path: str, checkpoint: Optional[str] = None, device: str = "auto",
             output_unit: str = "auto", fruits: Optional[list[str]] = None, fusion: Optional[str] = None,
             use_sensor_inputs: bool = True, persist: bool = True) -> dict:
        with self._lock:
            self.loading = True
            self.error = None
            previous = self.model
            previous_settings = dict(self.settings)
            new = None
            try:
                new = CustomModel(path, checkpoint or None, device=device, output_unit=output_unit,
                                  fruits=fruits, use_sensor_inputs=use_sensor_inputs)
                new.load()
                self.model = new
                if persist:
                    self.settings.update(mode="custom", path=str(new.folder), checkpoint=str(new.checkpoint),
                                         device=device, outputUnit=output_unit, fruits=fruits or [],
                                         useSensorInputs=use_sensor_inputs)
                    if fusion:
                        self.settings["fusion"] = fusion
                if db is not None:
                    self.register(db)
                if persist:
                    self._write_settings()
                if previous is not None:
                    # Both adapters can share import paths. Transfer their ownership before unloading.
                    if new.kind == "project":
                        new._sys_paths = list(dict.fromkeys(previous._sys_paths + new._sys_paths))
                        previous._sys_paths = []
                    previous.unload()
                log.info("Đã nạp model ảnh %s (%s)", new.version, new.checkpoint)
            except Exception as e:  # noqa: BLE001
                if new is not None:
                    new.unload()
                self.model = previous
                self.settings = previous_settings
                if db is not None:
                    db.rollback()
                self.error = f"{type(e).__name__}: {e}"
                log.exception("Nạp model thất bại")
                raise
            finally:
                self.loading = False
            return self.status()

    def unload(self) -> dict:
        with self._lock:
            if self.model is not None:
                self.model.unload()
            self.model = None
            self.error = None
            self.settings["mode"] = "q10"
            self._write_settings()
            return self.status()

    def register(self, db: Session) -> None:
        m = self.model
        if m is None:
            return
        h = m.model_hash()
        row = db.get(ModelVersion, m.version)
        if row is None:
            db.add(ModelVersion(version=m.version, model_hash=h,
                                registered_ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                description=f"Model ảnh của bạn: {m.checkpoint}", kind="image",
                                details=m.describe()))
            db.commit()
        try:
            from .ledger import get_ledger

            get_ledger().register_model(h, m.version)
        except Exception as e:  # noqa: BLE001
            log.warning("registerModel trên ledger thất bại: %s", e)

    def autoload(self, db: Session) -> None:
        """Khi khởi động: ưu tiên biến môi trường RUL_MODEL=custom, sau đó tới cài đặt đã lưu."""
        if config.RUL_MODEL == "custom":
            args = dict(path=config.RUL_MODEL_PATH or str(config.DEFAULT_MODEL_DIR), checkpoint=config.RUL_MODEL_CHECKPOINT or None, persist=False,
                        fruits=self.settings.get("fruits"), fusion=None)
        elif config.RUL_MODEL == "q10":
            return
        elif self.settings.get("mode") == "q10" and config.MODEL_SETTINGS_FILE.exists():
            return
        elif self.settings.get("mode") == "custom" and self.settings.get("path"):
            target_path = self.settings["path"]
            if not Path(target_path).exists() and config.DEFAULT_MODEL_DIR.is_dir():
                target_path = str(config.DEFAULT_MODEL_DIR)
            s = self.settings
            checkpoint = s.get("checkpoint") or None
            refresh_paths = target_path != s["path"]
            if target_path != s["path"]:
                checkpoint = None
            elif checkpoint and not Path(checkpoint).is_file() and (Path(target_path) / "fruitchain_model.json").is_file():
                checkpoint = None
                refresh_paths = True
            args = dict(path=target_path, checkpoint=checkpoint, device=s.get("device", "auto"),
                        output_unit=s.get("outputUnit", "auto"), fruits=s.get("fruits"),
                        use_sensor_inputs=s.get("useSensorInputs", True), persist=refresh_paths)
        elif config.DEFAULT_MODEL_DIR.is_dir():
            args = dict(path=str(config.DEFAULT_MODEL_DIR), checkpoint=config.RUL_MODEL_CHECKPOINT or None, persist=False,
                        fruits=self.settings.get("fruits"), fusion=None)
        else:
            return
        try:
            self.load(db, **args)
        except Exception:  # noqa: BLE001
            pass  # lỗi đã lưu trong self.error, hệ thống chạy tiếp với Q10

    # -------- inference
    def preprocess(self, image_bgr):  # noqa: ANN001, ANN201
        with self._lock:
            if self.model is None:
                return image_bgr, {"method": "none"}
            return self.model.preprocess(image_bgr)

    def predict(self, fruit: Fruit, batch_id: str, image_path: str, readings: Optional[list]) -> Optional[RulOutput]:
        with self._lock:
            m = self.model
            if m is None or not self.supports(fruit.fruit_id):
                return None
            out = m.predict(RulInput(batch_id=batch_id, fruit_id=fruit.fruit_id, readings=readings, image_path=image_path))
            if out.freshness is None:
                out.freshness = freshness_from_rul(out.rul_days, float(fruit.shelf_ref_days))
                out.extra["freshnessDerived"] = True
            return out


image_models = ImageModelManager()


def readings_for_model(rows: list) -> list[dict]:
    return [dict(ts=r.ts, tempC=r.temp_c, humidityPct=r.humidity_pct, ethylenePpm=r.ethylene_ppm) for r in rows]


__all__ = ["image_models", "fuse", "compute_series", "next_point", "sensor_model", "snapshot_from_point",
           "latest_point", "point_dict", "fruits_map", "q10_model_hash", "Q10_VERSION", "Path"]

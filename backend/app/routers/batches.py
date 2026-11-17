from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import config
from ..auth import current_user, require_roles
from ..db import get_db
from ..models import Actor, Batch, Fruit, Inspection, RulPoint, SensorReading, User
from ..schemas import BatchCreateIn, HandoffIn, SoldIn, TamperIn
from ..serializers import batch_dict, inspection_dict, reading_dict
from ..services import preprocess as preprocess_svc
from ..services.events import append_event, custody_timeline, utc_now_iso
from ..services.hashing import (ZERO_HASH, canonical_reading_row, event_hash, metadata_hash, segment_hash, sha_bytes,
                                sold_hash)
from ..services.ingest import after_last
from ..services.ledger import get_ledger
from ..services.rul import (Q10_VERSION, fuse, image_models, latest_point, point_dict, readings_for_model,
                            sensor_model, snapshot_from_point)
from ..services.verify import verify_batch

router = APIRouter(prefix="/batches", tags=["batches"])

STATUS_BY_ROLE = {"TRANSPORT": "IN_TRANSIT", "WAREHOUSE": "IN_STORAGE", "DISTRIBUTOR": "AT_DISTRIBUTOR",
                  "RETAILER": "IN_STORE", "FARMER": "HARVESTED"}


def get_batch(db: Session, batch_id: str) -> Batch:
    b = db.get(Batch, batch_id)
    if b is None:
        raise HTTPException(404, f"Không có lô {batch_id}")
    return b


def ensure_holder(user: User, b: Batch, *extra_roles: str) -> None:
    if user.role == "ADMIN" or user.role in extra_roles:
        return
    if user.actor_id != b.current_actor_id:
        raise HTTPException(403, "Chỉ bên đang giữ lô mới được thực hiện thao tác này")


def ensure_open(b: Batch) -> None:
    if b.status == "SOLD":
        raise HTTPException(409, f"Lô {b.batch_id} đã bán (vòng đời đã đóng)")


# ---------------------------------------------------------------- đọc

@router.get("")
def list_batches(status: Optional[str] = None, fruitId: Optional[str] = None, q: Optional[str] = None,
                 db: Session = Depends(get_db), _u: User = Depends(current_user)) -> list[dict]:
    qry = db.query(Batch)
    if status:
        qry = qry.filter(Batch.status == status)
    if fruitId:
        qry = qry.filter(Batch.fruit_id == fruitId)
    out = [batch_dict(db, b) for b in qry.order_by(Batch.batch_id).all()]
    if q:
        ql = q.lower()
        out = [b for b in out if ql in " ".join(str(b.get(k) or "") for k in
                                                ("batchId", "productName", "variety", "farmName", "currentActorName",
                                                 "originProvince")).lower()]
    return out


@router.get("/{batch_id}")
def batch_detail(batch_id: str, db: Session = Depends(get_db), _u: User = Depends(current_user)) -> dict:
    b = get_batch(db, batch_id)
    d = batch_dict(db, b)
    d["readingCount"] = db.query(SensorReading).filter(SensorReading.batch_id == batch_id).count()
    d["eventCount"] = len(get_ledger().get_events(batch_id, db))
    d["imageModelSupported"] = image_models.supports(b.fruit_id)
    return d


@router.get("/{batch_id}/readings")
def readings(batch_id: str, from_: Optional[str] = Query(None, alias="from"), to: Optional[str] = None,
             db: Session = Depends(get_db), _u: User = Depends(current_user)) -> list[dict]:
    get_batch(db, batch_id)
    q = db.query(SensorReading).filter(SensorReading.batch_id == batch_id)
    if from_:
        q = q.filter(SensorReading.ts >= from_)
    if to:
        q = q.filter(SensorReading.ts <= to)
    return [reading_dict(r) for r in q.order_by(SensorReading.ts).all()]


@router.get("/{batch_id}/rul")
def rul_series(batch_id: str, db: Session = Depends(get_db), _u: User = Depends(current_user)) -> list[dict]:
    get_batch(db, batch_id)
    rows = db.query(RulPoint).filter(RulPoint.batch_id == batch_id).order_by(RulPoint.ts).all()
    return [point_dict(p) for p in rows]


@router.get("/{batch_id}/events")
def events(batch_id: str, db: Session = Depends(get_db), _u: User = Depends(current_user)) -> list[dict]:
    get_batch(db, batch_id)
    evs = get_ledger().get_events(batch_id, db)
    actors = {a.actor_id: a for a in db.query(Actor).all()}
    prev = ZERO_HASH
    for e in evs:
        e["linkOk"] = e["prevHash"] == prev and event_hash(e) == e["eventHash"]
        prev = e["eventHash"]
        for k in ("actorId", "toActorId"):
            a = actors.get(e.get(k) or "")
            e[k.replace("Id", "Name")] = a.name if a else None
    return evs


# ---------------------------------------------------------------- tạo lô

def next_batch_id(db: Session, year: str) -> str:
    n = 0
    for (bid,) in db.query(Batch.batch_id).all():
        m = re.fullmatch(rf"FC-{year}-(\d+)", bid)
        if m:
            n = max(n, int(m.group(1)))
    return f"FC-{year}-{n + 1:03d}"


@router.post("", status_code=201)
def create_batch(body: BatchCreateIn, db: Session = Depends(get_db),
                 user: User = Depends(require_roles("FARMER"))) -> dict:
    if user.role == "FARMER" and user.actor_id != body.farmId:
        raise HTTPException(403, "Nông hộ chỉ được tạo lô cho farm của mình")
    farm = db.get(Actor, body.farmId)
    if farm is None or farm.role != "FARMER":
        raise HTTPException(422, "farmId không hợp lệ")
    fruit = db.get(Fruit, body.fruitId)
    if fruit is None:
        raise HTTPException(422, "fruitId không hợp lệ")
    harvest_ts = body.harvestTs or utc_now_iso()
    bid = next_batch_id(db, harvest_ts[:4])
    qty = int(body.quantityKg) if float(body.quantityKg).is_integer() else body.quantityKg
    mh = metadata_hash(bid, body.fruitId, body.variety, body.farmId, qty, harvest_ts, body.certifications)
    b = Batch(batch_id=bid, fruit_id=body.fruitId, variety=body.variety, farm_id=body.farmId,
              origin_province=body.originProvince or farm.province, quantity_kg=qty, harvest_ts=harvest_ts,
              certifications=body.certifications, status="HARVESTED", current_actor_id=body.farmId,
              metadata_hash=mh, qr_payload=f"https://fruitchain.demo/trace/{bid}")
    db.add(b)
    db.flush()
    append_event(db, batch_id=bid, type="HARVEST", ts=harvest_ts, actor_id=body.farmId, to_actor_id=None,
                 lat=farm.lat, lon=farm.lon, data_hash=mh,
                 payload=dict(quantityKg=qty, variety=body.variety, certifications=body.certifications),
                 rul_snapshot=snapshot_from_point(None, sensor_model(db).model_hash(), fruit))
    db.commit()
    return batch_dict(db, b)


# ---------------------------------------------------------------- chuyển giao / bán

@router.post("/{batch_id}/handoff")
def handoff(batch_id: str, body: HandoffIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    b = get_batch(db, batch_id)
    ensure_holder(user, b)
    ensure_open(b)
    to = db.get(Actor, body.toActorId)
    if to is None or to.actor_id == b.current_actor_id or to.role == "REGULATOR":
        raise HTTPException(422, "toActorId không hợp lệ")
    evs = get_ledger().get_events(batch_id, db)
    timeline = custody_timeline(evs)
    start = timeline[-1][0] if timeline else b.harvest_ts
    rows = db.query(SensorReading).filter(SensorReading.batch_id == batch_id, SensorReading.ts >= start) \
        .order_by(SensorReading.ts).all()
    if not rows:
        raise HTTPException(409, "Chặng hiện tại chưa có dữ liệu cảm biến để chốt hash")
    last = rows[-1]
    leg_index = sum(1 for e in evs if e["type"] == "HANDOFF")
    holder = db.get(Actor, b.current_actor_id)
    ev = append_event(
        db, batch_id=batch_id, type="HANDOFF", ts=after_last(db, batch_id, utc_now_iso()),
        actor_id=b.current_actor_id, to_actor_id=to.actor_id, lat=last.lat, lon=last.lon,
        data_hash=segment_hash(canonical_reading_row(r) for r in rows),
        payload=dict(legIndex=leg_index, legLabel=holder.name if holder else b.current_actor_id,
                     fromReading=rows[0].ts, toReading=last.ts, readingCount=len(rows)),
        rul_snapshot=snapshot_from_point(db.get(RulPoint, (batch_id, last.ts)), sensor_model(db).model_hash()))
    b.current_actor_id = to.actor_id
    b.status = STATUS_BY_ROLE.get(to.role, b.status)
    db.commit()
    return {"event": ev, "batch": batch_dict(db, b)}


@router.post("/{batch_id}/sold")
def sold(batch_id: str, body: Optional[SoldIn] = None, db: Session = Depends(get_db),
         user: User = Depends(require_roles("RETAILER"))) -> dict:
    body = body or SoldIn()
    b = get_batch(db, batch_id)
    ensure_holder(user, b)
    ensure_open(b)
    holder = db.get(Actor, b.current_actor_id)
    if user.role == "ADMIN" and holder and holder.role != "RETAILER":
        raise HTTPException(409, "Lô chưa tới cửa hàng")
    qty = body.quantityKg if body.quantityKg is not None else b.quantity_kg
    qty = int(qty) if float(qty).is_integer() else qty
    ts = after_last(db, batch_id, utc_now_iso())
    last = db.query(SensorReading).filter(SensorReading.batch_id == batch_id).order_by(SensorReading.ts.desc()).first()
    ev = append_event(db, batch_id=batch_id, type="SOLD", ts=ts, actor_id=b.current_actor_id, to_actor_id=None,
                      lat=last.lat if last else None, lon=last.lon if last else None,
                      data_hash=sold_hash(batch_id, ts, qty), payload=dict(quantityKg=qty),
                      rul_snapshot=snapshot_from_point(latest_point(db, batch_id), sensor_model(db).model_hash()))
    b.status = "SOLD"
    db.commit()
    return {"event": ev, "batch": batch_dict(db, b)}


# ---------------------------------------------------------------- kiểm chứng

@router.post("/{batch_id}/verify")
def verify(batch_id: str, db: Session = Depends(get_db), _u: User = Depends(current_user)) -> dict:
    get_batch(db, batch_id)
    return verify_batch(db, batch_id)


_TAMPER_BACKUPS: dict[str, dict] = {}


@router.post("/{batch_id}/simulate-tamper")
def simulate_tamper(batch_id: str, body: Optional[TamperIn] = None, db: Session = Depends(get_db),
                    _u: User = Depends(current_user)) -> dict:
    get_batch(db, batch_id)
    ttype = (body.tamperType if body else "sensor") or "sensor"
    if batch_id not in _TAMPER_BACKUPS:
        _TAMPER_BACKUPS[batch_id] = {}

    if ttype == "sensor":
        reading = db.query(SensorReading).filter(SensorReading.batch_id == batch_id).order_by(SensorReading.ts.desc()).first()
        if not reading:
            raise HTTPException(400, "Lô không có dữ liệu cảm biến để can thiệp")
        if "sensor" not in _TAMPER_BACKUPS[batch_id]:
            _TAMPER_BACKUPS[batch_id]["sensor"] = {
                "ts": reading.ts,
                "temp_c": reading.temp_c,
                "device_sig": reading.device_sig,
            }
        reading.temp_c = round(reading.temp_c + 12.5, 2)
        db.commit()
        return {
            "status": "tampered",
            "batchId": batch_id,
            "tamperType": "sensor",
            "readingTs": reading.ts,
            "newTempC": reading.temp_c,
            "message": "Đã sửa đổi nhiệt độ trong CSDL (+12.5°C). Trong CSDL thông thường, thay đổi này bị che giấu hoàn toàn. Hãy bấm 'Verify' để xem Blockchain phát hiện!",
            "explanation": {
                "traditionalDb": "CSDL tập trung ghi đè giá trị mới, người dùng mù quáng tin vào dữ liệu giả mạo.",
                "blockchain": "Smart Contract trên Avalanche lưu trữ Merkle Hash bất biến. Khi đối chiếu, hash tính lại không khớp và chữ ký thiết bị bị phát hiện sai lệch ngay lập tức.",
            },
        }
    elif ttype == "image":
        insp = db.query(Inspection).filter(Inspection.batch_id == batch_id).first()
        if not insp or not Path(insp.raw_image_path).is_file():
            raise HTTPException(400, "Lô chưa có ảnh kiểm tra (Inspection). Vui lòng tải một ảnh lên ở tab 'Ảnh kiểm tra' của lô này trước khi thử nghiệm tráo ảnh!")
        img_p = Path(insp.raw_image_path)
        if "image" not in _TAMPER_BACKUPS[batch_id]:
            _TAMPER_BACKUPS[batch_id]["image"] = {
                "path": str(img_p),
                "bytes": img_p.read_bytes(),
            }
        b = bytearray(img_p.read_bytes())
        b[len(b) // 2] ^= 0xFF
        b[len(b) // 2 + 1] ^= 0xAA
        img_p.write_bytes(bytes(b))
        return {
            "status": "tampered",
            "batchId": batch_id,
            "tamperType": "image",
            "imagePath": str(img_p),
            "message": "Đã làm biến đổi file ảnh kiểm tra trong ổ đĩa/DB. Trong CSDL thông thường, file ảnh bị sửa/tráo sẽ không bị phát hiện. Hãy bấm 'Verify' để xem Blockchain bắt lỗi!",
            "explanation": {
                "traditionalDb": "CSDL tập trung chỉ lưu đường dẫn file; nếu tráo ảnh dâu hỏng thành dâu đẹp, hệ thống sẽ tin tưởng mù quáng.",
                "blockchain": "Smart Contract đã neo chặt imageHash (SHA-256) trên Avalanche. Khi đối chiếu ảnh với sổ cái, tính toàn vẹn bị vi phạm lập tức.",
            },
        }
    else:
        raise HTTPException(400, f"Loại can thiệp không hợp lệ: {ttype}")


@router.post("/{batch_id}/restore-tamper")
def restore_tamper(batch_id: str, db: Session = Depends(get_db), _u: User = Depends(current_user)) -> dict:
    get_batch(db, batch_id)
    backup = _TAMPER_BACKUPS.pop(batch_id, None)
    restored = []
    if backup:
        if "sensor" in backup:
            s_bk = backup["sensor"]
            reading = db.query(SensorReading).filter(SensorReading.batch_id == batch_id, SensorReading.ts == s_bk["ts"]).first()
            if reading:
                reading.temp_c = s_bk["temp_c"]
                reading.device_sig = s_bk["device_sig"]
                db.commit()
                restored.append("sensor")
        if "image" in backup:
            i_bk = backup["image"]
            p = Path(i_bk["path"])
            if p.parent.exists():
                p.write_bytes(i_bk["bytes"])
                restored.append("image")
    return {
        "status": "restored",
        "batchId": batch_id,
        "restoredComponents": restored,
        "message": "Dữ liệu đã được khôi phục về trạng thái toàn vẹn ban đầu.",
    }


# ---------------------------------------------------------------- ảnh kiểm tra

@router.post("/{batch_id}/inspections", status_code=201)
async def create_inspection(batch_id: str, file: UploadFile = File(...), note: Optional[str] = Form(None),
                            db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    b = get_batch(db, batch_id)
    ensure_holder(user, b, "REGULATOR")
    ensure_open(b)
    content = await file.read()
    if not content:
        raise HTTPException(422, "File rỗng")
    fruit = db.get(Fruit, b.fruit_id)
    image_hash = sha_bytes(content)
    ts = after_last(db, batch_id, utc_now_iso())
    stamp = ts.replace("-", "").replace(":", "")
    ext = (Path(file.filename or "").suffix.lower() or ".jpg")
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
        ext = ".jpg"
    raw_path = config.RAW_DIR / batch_id / f"{stamp}_{image_hash}{ext}"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(content)
    pre_path = config.PRE_DIR / batch_id / f"{stamp}_{image_hash}.png"

    try:
        pre_info = preprocess_svc.run(raw_path, pre_path, b.fruit_id)
    except Exception as e:  # noqa: BLE001
        raw_path.unlink(missing_ok=True)
        raise HTTPException(422, f"Tiền xử lý ảnh thất bại: {e}") from None

    readings = readings_for_model(db.query(SensorReading).filter(SensorReading.batch_id == batch_id)
                                  .order_by(SensorReading.ts).all())
    lp = latest_point(db, batch_id)
    rul_sensor = lp.rul_at_current if lp else None
    img_out = None
    img_error = None
    if image_models.supports(b.fruit_id):
        try:
            img_out = image_models.predict(fruit, batch_id, str(pre_path), readings)
        except Exception as e:  # noqa: BLE001
            img_error = f"{type(e).__name__}: {e}"
    elif image_models.model is not None:
        img_error = f"Model ảnh hiện tại không hỗ trợ loại quả '{b.fruit_id}'"
    else:
        img_error = "Chưa nạp model ảnh (Cài đặt → Model) — chỉ dùng RUL cảm biến"

    m = image_models.model if img_out is not None else None
    model_version = m.version if m else Q10_VERSION
    model_hash = m.model_hash() if m else sensor_model(db).model_hash()
    rul_image = img_out.rul_days if img_out else None
    mode = image_models.fusion
    rul_final = fuse(rul_sensor, rul_image, mode)
    freshness = (img_out.freshness if img_out else (lp.freshness if lp else None))
    n = db.query(Inspection).filter(Inspection.batch_id == batch_id).count() + 1
    insp_id = f"IN-{batch_id[-3:]}-{n:03d}"
    actor_id = user.actor_id or b.current_actor_id
    snapshot = dict(rulDaysAtCurrent=rul_final, rulSensorDays=rul_sensor, rulImageDays=rul_image,
                    ciLowDays=img_out.ci_low_days if img_out else (lp.ci_low if lp else None),
                    ciHighDays=img_out.ci_high_days if img_out else (lp.ci_high if lp else None),
                    freshness=freshness, tempC=lp.temp_c if lp else None, fusion=mode,
                    modelVersion=model_version, modelHash=model_hash)
    last = db.query(SensorReading).filter(SensorReading.batch_id == batch_id).order_by(SensorReading.ts.desc()).first()
    ev = append_event(db, batch_id=batch_id, type="INSPECTION", ts=ts, actor_id=actor_id, to_actor_id=None,
                      lat=last.lat if last else None, lon=last.lon if last else None, data_hash=image_hash,
                      payload=dict(imageId=insp_id, imageHash=image_hash, rulImageDays=rul_image,
                                   freshnessLabel=freshness, modelVersion=model_version),
                      rul_snapshot=snapshot)
    extra = {"preprocess": pre_info, "imageModelError": img_error, "fusion": mode}
    if img_out:
        extra["model"] = img_out.extra
    insp = Inspection(inspection_id=insp_id, batch_id=batch_id, ts=ts, raw_image_path=str(raw_path),
                      image_hash=image_hash, preprocessed_path=str(pre_path), rul_image_days=rul_image,
                      rul_sensor_days=rul_sensor, rul_final_days=rul_final,
                      ci_low=snapshot["ciLowDays"], ci_high=snapshot["ciHighDays"], freshness_label=freshness,
                      model_version=model_version, model_hash=model_hash, event_id=ev["eventId"], note=note,
                      extra=extra, actor_id=actor_id)
    db.add(insp)
    db.commit()
    return {**inspection_dict(insp), "event": ev}


@router.get("/{batch_id}/inspections")
def list_inspections(batch_id: str, db: Session = Depends(get_db), _u: User = Depends(current_user)) -> list[dict]:
    get_batch(db, batch_id)
    rows = db.query(Inspection).filter(Inspection.batch_id == batch_id).order_by(Inspection.ts.desc()).all()
    return [inspection_dict(i) for i in rows]


@router.get("/{batch_id}/inspections/{inspection_id}/image")
def inspection_image(batch_id: str, inspection_id: str, kind: str = "raw", db: Session = Depends(get_db),
                     _u: User = Depends(current_user)) -> FileResponse:
    i = db.get(Inspection, inspection_id)
    if i is None or i.batch_id != batch_id:
        raise HTTPException(404, "Không có ảnh")
    p = Path(i.preprocessed_path if kind == "pre" else i.raw_image_path)
    if not p.is_file():
        raise HTTPException(404, "File ảnh không còn trên đĩa")
    return FileResponse(p)

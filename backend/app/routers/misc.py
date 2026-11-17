"""ingest, alerts, public trace, ledger explorer, what-if RUL, admin."""
from __future__ import annotations

from typing import Optional, Union

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..auth import current_user, require_roles
from ..db import create_all, drop_all, get_db
from ..models import Actor, Alert, Batch, Fruit, LedgerEvent, RulPoint, User
from ..schemas import IngestIn, PredictIn, ReadingIn
from ..serializers import alert_dict, batch_dict
from ..services import ingest as ingest_svc
from ..services.hashing import ZERO_HASH, event_hash
from ..services.ledger import get_ledger, row_to_event
from ..services.rul import compute_series, sensor_model
from ..services.verify import verify_batch

router = APIRouter()


# ---------------------------------------------------------------- ingest
@router.post("/ingest/readings", tags=["ingest"])
def ingest_readings(body: Union[IngestIn, list[ReadingIn]], x_device_id: Optional[str] = Header(None),
                    db: Session = Depends(get_db)) -> dict:
    if not x_device_id:
        raise HTTPException(401, "Thiếu header X-Device-Id")
    items = body.readings if isinstance(body, IngestIn) else body
    return ingest_svc.ingest(db, x_device_id, [r.model_dump() for r in items])


# ---------------------------------------------------------------- alerts
@router.get("/alerts", tags=["alerts"])
def list_alerts(batchId: Optional[str] = None, acknowledged: Optional[bool] = None, db: Session = Depends(get_db),
                _u: User = Depends(current_user)) -> list[dict]:
    q = db.query(Alert)
    if batchId:
        q = q.filter(Alert.batch_id == batchId)
    if acknowledged is not None:
        q = q.filter(Alert.acknowledged.is_(acknowledged))
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    rows = sorted(q.all(), key=lambda a: (a.acknowledged, rank.get(a.severity, 3), a.ts), reverse=False)
    return [alert_dict(a) for a in rows]


@router.post("/alerts/{alert_id}/ack", tags=["alerts"])
def ack_alert(alert_id: str, db: Session = Depends(get_db), _u: User = Depends(current_user)) -> dict:
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(404, "Không có cảnh báo")
    a.acknowledged = True
    db.commit()
    return alert_dict(a)


# ---------------------------------------------------------------- public trace
@router.get("/public/trace/{batch_id}", tags=["public"])
def public_trace(batch_id: str, db: Session = Depends(get_db)) -> dict:
    b = db.get(Batch, batch_id)
    if b is None:
        raise HTTPException(404, "Không tìm thấy lô")
    d = batch_dict(db, b)
    actors = {a.actor_id: a for a in db.query(Actor).all()}
    evs = get_ledger().get_events(batch_id, db)
    timeline = []
    for e in evs:
        a = actors.get(e.get("actorId") or "")
        to = actors.get(e.get("toActorId") or "")
        snap = e.get("rulSnapshot") or {}
        p = e.get("payload") or {}
        timeline.append({"type": e["type"], "ts": e["ts"], "actorName": a.name if a else None,
                         "actorRole": a.role if a else None, "toActorName": to.name if to else None,
                         "rulDaysAtCurrent": snap.get("rulDaysAtCurrent"), "freshness": snap.get("freshness"),
                         "tempC": snap.get("tempC"), "txHash": e["txHash"], "blockNumber": e["blockNumber"],
                         "violation": {k: p.get(k) for k in ("durationHours", "maxTempC", "thresholdC", "ongoing")}
                         if e["type"] == "VIOLATION" else None})
    pts = db.query(RulPoint).filter(RulPoint.batch_id == batch_id).order_by(RulPoint.ts).all()
    step = max(1, len(pts) // 120)
    curve = [{"ts": p.ts, "rulDaysAtCurrent": p.rul_at_current, "rulDaysAtOptimal": p.rul_at_optimal,
              "tempC": p.temp_c} for i, p in enumerate(pts) if i % step == 0 or i == len(pts) - 1]
    v = verify_batch(db, batch_id)
    farm = actors.get(b.farm_id)
    return {
        "batchId": b.batch_id, "fruitId": b.fruit_id, "productName": d["productName"], "variety": b.variety,
        "farmName": farm.name if farm else None, "originProvince": b.origin_province, "harvestTs": b.harvest_ts,
        "certifications": b.certifications, "status": b.status, "quantityKg": b.quantity_kg,
        "currentHolder": d["currentActorName"], "latestRul": d["latestRul"], "metadataHash": b.metadata_hash,
        "timeline": timeline, "rulCurve": curve,
        "ledgerNetwork": get_ledger().network_info(),
        "verification": {"overall": v["overall"], "chainLinkIntact": v["chainLinkIntact"],
                         "segmentsChecked": len(v["segments"]),
                         "segmentsMismatched": sum(1 for s in v["segments"] if not s["match"]),
                         "checkedAt": v["checkedAt"]},
    }


# ---------------------------------------------------------------- ledger explorer
@router.get("/ledger/network", tags=["ledger"])
def ledger_network() -> dict:
    """Public network identity; never returns signing keys or RPC credentials."""
    return get_ledger().network_info()


@router.get("/ledger/events", tags=["ledger"])
def ledger_events(batchId: Optional[str] = None, type: Optional[str] = None, db: Session = Depends(get_db),
                  _u: User = Depends(current_user)) -> dict:
    q = db.query(LedgerEvent)
    if batchId:
        q = q.filter(LedgerEvent.batch_id == batchId)
    if type:
        q = q.filter(LedgerEvent.type == type)
    rows = [row_to_event(r) for r in q.order_by(LedgerEvent.block_number).all()]
    # trạng thái liên kết hash theo từng lô
    heads: dict[str, str] = {}
    all_rows = [row_to_event(r) for r in db.query(LedgerEvent).order_by(LedgerEvent.block_number).all()]
    link = {}
    for e in all_rows:
        prev = heads.get(e["batchId"], ZERO_HASH)
        link[e["eventId"]] = {"prevOk": e["prevHash"] == prev, "hashOk": event_hash(e) == e["eventHash"]}
        heads[e["batchId"]] = e["eventHash"]
    for e in rows:
        e.update(link.get(e["eventId"], {}))
    return {"mode": get_ledger().mode, "count": len(rows), "events": list(reversed(rows))}


# ---------------------------------------------------------------- what-if
@router.post("/rul/predict", tags=["rul"])
def rul_predict(body: PredictIn, db: Session = Depends(get_db), _u: User = Depends(current_user)) -> dict:
    fruit = db.get(Fruit, body.fruitId)
    if fruit is None:
        raise HTTPException(404, "Không có loại quả")
    series = compute_series(fruit, [r.tempC for r in body.readings])
    for s, r in zip(series, body.readings):
        s["ts"] = r.ts
        s["tempC"] = r.tempC
    sm = sensor_model(db)
    return {"fruitId": body.fruitId, "modelVersion": sm.version, "modelHash": sm.model_hash(), "series": series}


# ---------------------------------------------------------------- admin
admin = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_roles())])


@admin.post("/seed")
def admin_seed() -> dict:
    from ..seed import reset_and_seed

    ledger = get_ledger()
    if ledger.mode == "evm" and not ledger.is_local:
        raise HTTPException(409, "Không reset dữ liệu đã gắn chain công khai. Dùng DATABASE_URL riêng cho demo Fuji.")
    return {"ok": True, "counts": reset_and_seed()}


@admin.post("/reset")
def admin_reset() -> dict:
    from ..seed import _clear_storage

    ledger = get_ledger()
    if ledger.mode == "evm" and not ledger.is_local:
        raise HTTPException(409, "Không xoá DB đang gắn chain công khai vì bằng chứng on-chain không thể xoá.")
    drop_all()
    create_all()
    _clear_storage()
    return {"ok": True, "message": "Đã xoá toàn bộ dữ liệu. Gọi /admin/seed để nạp lại demo."}


@admin.post("/simulate/tick")
def admin_tick(db: Session = Depends(get_db)) -> dict:
    res = ingest_svc.simulate_tick(db)
    return {"ok": True, "batches": {k: {"ts": v["rul"][-1]["ts"], "rulDaysAtCurrent": v["rul"][-1]["rulDaysAtCurrent"],
                                        "violations": v["violations"], "alerts": v["alerts"]} for k, v in res.items()}}

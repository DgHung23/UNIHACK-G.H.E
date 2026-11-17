"""Phát hiện vi phạm chuỗi lạnh + cảnh báo RUL thấp (mục 5)."""
from __future__ import annotations

from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from ..models import Alert, Batch, Fruit, RulPoint, SensorReading
from .events import actor_roles, append_event, custody_timeline, holder_at
from .hashing import canonical_reading_row, segment_hash
from .ledger import get_ledger
from .rul import snapshot_from_point, sensor_model


def detect_runs(readings: list[Any], alert_temp: float, skip: Callable[[Any], bool]) -> list[tuple[list, bool]]:
    """Đợt vi phạm = ≥2 reading liên tiếp có temp > alert_temp, bỏ qua reading bị skip (chặng farm).
    Trả về [(run, ongoing)]."""
    runs, run = [], []
    for r in readings:
        temp = r["tempC"] if isinstance(r, dict) else r.temp_c
        if not skip(r) and temp > alert_temp:
            run.append(r)
        else:
            if len(run) >= 2:
                runs.append((run, False))
            run = []
    if len(run) >= 2:
        runs.append((run, True))
    return runs


def low_rul_severity(rul_current: float) -> Optional[str]:
    return "HIGH" if rul_current < 2 else ("MEDIUM" if rul_current < 4 else None)


def next_alert_id(db: Session) -> str:
    ids = [a.alert_id for a in db.query(Alert.alert_id).all()]
    n = max((int(i.split("-")[1]) for i in ids if i.startswith("AL-")), default=0)
    return f"AL-{n + 1:03d}"


def process_batch(db: Session, batch: Batch) -> dict:
    """Chạy sau khi có reading mới: sinh VIOLATION (nếu là đợt mới) và cảnh báo."""
    fruit = db.get(Fruit, batch.fruit_id)
    events = get_ledger().get_events(batch.batch_id, db)
    timeline = custody_timeline(events)
    roles = actor_roles(db)
    readings = db.query(SensorReading).filter(SensorReading.batch_id == batch.batch_id).order_by(SensorReading.ts).all()

    def skip(r):  # noqa: ANN001, ANN202
        return roles.get(holder_at(timeline, r.ts) or "", "") == "FARMER"

    known_starts = {(e.get("payload") or {}).get("startTs") for e in events if e["type"] == "VIOLATION"}
    model_hash = sensor_model(db).model_hash()
    created = {"violations": [], "alerts": []}
    for run, ongoing in detect_runs(readings, fruit.alert_temp_c, skip):
        if run[0].ts in known_starts:
            continue
        last = run[-1]
        pt = db.get(RulPoint, (batch.batch_id, last.ts))
        ev = append_event(
            db, batch_id=batch.batch_id, type="VIOLATION", ts=last.ts, actor_id=holder_at(timeline, run[0].ts),
            to_actor_id=None, lat=last.lat, lon=last.lon,
            data_hash=segment_hash(canonical_reading_row(r) for r in run),
            payload=dict(violationType="TEMP_EXCURSION", thresholdC=fruit.alert_temp_c, startTs=run[0].ts,
                         endTs=last.ts, durationHours=len(run), maxTempC=max(r.temp_c for r in run), ongoing=ongoing),
            rul_snapshot=snapshot_from_point(pt, model_hash))
        created["violations"].append(ev["eventId"])
        p = ev["payload"]
        al = Alert(alert_id=next_alert_id(db), batch_id=batch.batch_id, type="COLD_CHAIN_VIOLATION", severity="HIGH",
                   ts=ev["ts"], related_event_id=ev["eventId"], acknowledged=False,
                   message=f"Nhiệt độ vượt {p['thresholdC']}°C trong {p['durationHours']} giờ (tối đa {p['maxTempC']}°C)"
                           + (" - đang tiếp diễn" if ongoing else ""))
        db.add(al)
        db.flush()
        created["alerts"].append(al.alert_id)

    if batch.status != "SOLD":
        lp = db.query(RulPoint).filter(RulPoint.batch_id == batch.batch_id).order_by(RulPoint.ts.desc()).first()
        sev = low_rul_severity(lp.rul_at_current) if lp else None
        if sev:
            existing = db.query(Alert).filter(Alert.batch_id == batch.batch_id, Alert.type == "LOW_RUL",
                                              Alert.acknowledged.is_(False)).all()
            rank = {"MEDIUM": 1, "HIGH": 2}
            if not any(rank.get(a.severity, 0) >= rank[sev] for a in existing):
                al = Alert(alert_id=next_alert_id(db), batch_id=batch.batch_id, type="LOW_RUL", severity=sev, ts=lp.ts,
                           related_event_id=None, acknowledged=False,
                           message=f"RUL còn {lp.rul_at_current} ngày ở điều kiện hiện tại")
                db.add(al)
                db.flush()
                created["alerts"].append(al.alert_id)
    return created

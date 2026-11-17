"""Nhận reading mới từ thiết bị: kiểm chữ ký → lưu → tính tiếp RUL → vi phạm/cảnh báo."""
from __future__ import annotations

import datetime as dt
import random
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Batch, Fruit, RulPoint, SensorReading
from .alerts import process_batch
from .hashing import canonical_reading, device_sig
from .rul import next_point


def device_for(batch_id: str) -> str:
    return f"TAG-{batch_id[-3:]}"


def parse_ts(ts: str) -> dt.datetime:
    return dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def fmt_ts(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def after_last(db: Session, batch_id: str, now_iso: str) -> str:
    """Thời điểm cho sự kiện mới: hiện tại, nhưng không sớm hơn reading cuối + 1 giờ."""
    last = db.query(SensorReading).filter(SensorReading.batch_id == batch_id).order_by(SensorReading.ts.desc()).first()
    if last is None:
        return now_iso
    nxt = fmt_ts(parse_ts(last.ts) + dt.timedelta(hours=1))
    return max(now_iso, nxt)


def ingest(db: Session, device_id: str, items: list[dict]) -> dict:
    if not items:
        raise HTTPException(422, "Danh sách reading rỗng")
    bad, batches = [], {}
    for i, r in enumerate(items):
        b = batches.get(r["batchId"]) or db.get(Batch, r["batchId"])
        if b is None:
            raise HTTPException(404, f"Không có lô {r['batchId']}")
        if b.status == "SOLD":
            raise HTTPException(409, f"Lô {b.batch_id} đã bán, không nhận dữ liệu")
        batches[b.batch_id] = b
        if r.get("deviceId") and r["deviceId"] != device_id:
            bad.append({"index": i, "reason": "deviceId khác header X-Device-Id"})
            continue
        if device_id != device_for(b.batch_id):
            bad.append({"index": i, "reason": f"Thiết bị {device_id} không gắn với lô {b.batch_id}"})
            continue
        canon = canonical_reading(r["batchId"], r["ts"], r["tempC"], r["humidityPct"], r["ethylenePpm"], r["lat"], r["lon"])
        if device_sig(device_id, canon) != r["deviceSig"]:
            bad.append({"index": i, "reason": "deviceSig sai"})
    if bad:
        raise HTTPException(422, {"message": "Chữ ký thiết bị không hợp lệ — không ghi dữ liệu", "errors": bad})

    out_points = []
    for bid in batches:
        rows = sorted((r for r in items if r["batchId"] == bid), key=lambda r: r["ts"])
        last = db.query(SensorReading).filter(SensorReading.batch_id == bid).order_by(SensorReading.ts.desc()).first()
        for r in rows:
            if last is not None and r["ts"] <= last.ts:
                raise HTTPException(422, f"Reading {bid} {r['ts']} không mới hơn reading cuối ({last.ts})")
            try:
                parse_ts(r["ts"])
            except ValueError:
                raise HTTPException(422, f"ts sai định dạng: {r['ts']}") from None
    for bid, b in batches.items():
        fruit = db.get(Fruit, b.fruit_id)
        rows = sorted((r for r in items if r["batchId"] == bid), key=lambda r: r["ts"])
        lp = db.query(RulPoint).filter(RulPoint.batch_id == bid).order_by(RulPoint.ts.desc()).first()
        consumed: Optional[float] = lp.effective_hours if lp else None
        for r in rows:
            db.add(SensorReading(batch_id=bid, ts=r["ts"], temp_c=round(float(r["tempC"]), 1),
                                 humidity_pct=int(r["humidityPct"]), ethylene_ppm=round(float(r["ethylenePpm"]), 1),
                                 lat=round(float(r["lat"]), 4), lon=round(float(r["lon"]), 4), device_id=device_id,
                                 device_sig=r["deviceSig"]))
            p = next_point(fruit, consumed, float(r["tempC"]))
            consumed = p["effectiveHoursConsumed"]
            db.add(RulPoint(batch_id=bid, ts=r["ts"], temp_c=round(float(r["tempC"]), 1), effective_hours=consumed,
                            fraction_used=p["fractionUsed"], rul_at_current=p["rulDaysAtCurrent"],
                            rul_at_optimal=p["rulDaysAtOptimal"], ci_low=p["ciLowDays"], ci_high=p["ciHighDays"],
                            freshness=p["freshness"]))
            out_points.append(dict(p, batchId=bid, ts=r["ts"], tempC=r["tempC"]))
        db.flush()
    created = {"violations": [], "alerts": []}
    for b in batches.values():
        c = process_batch(db, b)
        created["violations"] += c["violations"]
        created["alerts"] += c["alerts"]
    db.commit()
    return {"accepted": len(items), "rul": out_points, **created}


def simulate_tick(db: Session, rng: Optional[random.Random] = None) -> dict:
    """Thêm 1 reading/giờ cho mọi lô chưa bán (demo thời gian thực)."""
    rng = rng or random.Random()
    results = {}
    for b in db.query(Batch).filter(Batch.status != "SOLD").all():
        rows = db.query(SensorReading).filter(SensorReading.batch_id == b.batch_id).order_by(SensorReading.ts.desc()).limit(6).all()
        if not rows:
            continue
        last = rows[0]
        mean_t = sum(r.temp_c for r in rows) / len(rows)
        ts = fmt_ts(parse_ts(last.ts) + dt.timedelta(hours=1))
        temp = round(rng.gauss(mean_t, 0.3), 1)
        hum = int(round(min(99, max(40, rng.gauss(last.humidity_pct, 1.5)))))
        eth = round(max(0.0, rng.gauss(last.ethylene_ppm, 0.1)), 1)
        dev = device_for(b.batch_id)
        canon = canonical_reading(b.batch_id, ts, temp, hum, eth, last.lat, last.lon)
        item = dict(batchId=b.batch_id, ts=ts, tempC=temp, humidityPct=hum, ethylenePpm=eth, lat=last.lat,
                    lon=last.lon, deviceSig=device_sig(dev, canon))
        results[b.batch_id] = ingest(db, dev, [item])
    return results

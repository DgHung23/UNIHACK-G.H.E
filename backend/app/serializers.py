from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from .models import Actor, Alert, Batch, Fruit, Inspection, ModelVersion, RulPoint, SensorReading


def actor_dict(a: Actor) -> dict:
    return {"actorId": a.actor_id, "name": a.name, "role": a.role, "province": a.province, "lat": a.lat, "lon": a.lon}


def fruit_dict(f: Fruit) -> dict:
    return dict(f.raw)


def model_dict(m: ModelVersion) -> dict:
    return {"version": m.version, "modelHash": m.model_hash, "registeredTs": m.registered_ts,
            "description": m.description, "kind": m.kind}


def reading_dict(r: SensorReading, with_sig: bool = True) -> dict:
    d = {"batchId": r.batch_id, "ts": r.ts, "tempC": r.temp_c, "humidityPct": r.humidity_pct,
         "ethylenePpm": r.ethylene_ppm, "lat": r.lat, "lon": r.lon}
    if with_sig:
        d.update(deviceId=r.device_id, deviceSig=r.device_sig)
    return d


def latest_rul(db: Session, batch_id: str) -> Optional[dict]:
    p = db.query(RulPoint).filter(RulPoint.batch_id == batch_id).order_by(RulPoint.ts.desc()).first()
    if not p:
        return None
    return {"ts": p.ts, "rulDaysAtCurrent": p.rul_at_current, "rulDaysAtOptimal": p.rul_at_optimal,
            "ciLowDays": p.ci_low, "ciHighDays": p.ci_high, "freshness": p.freshness, "fractionUsed": p.fraction_used,
            "tempC": p.temp_c}


def alert_dict(a: Alert) -> dict:
    return {"alertId": a.alert_id, "batchId": a.batch_id, "type": a.type, "severity": a.severity, "ts": a.ts,
            "relatedEventId": a.related_event_id, "acknowledged": a.acknowledged, "message": a.message}


def batch_dict(db: Session, b: Batch) -> dict:
    fruit = db.get(Fruit, b.fruit_id)
    farm = db.get(Actor, b.farm_id)
    cur = db.get(Actor, b.current_actor_id)
    last = db.query(SensorReading).filter(SensorReading.batch_id == b.batch_id).order_by(SensorReading.ts.desc()).first()
    alerts = db.query(Alert).filter(Alert.batch_id == b.batch_id, Alert.acknowledged.is_(False)).all()
    return {
        "batchId": b.batch_id, "fruitId": b.fruit_id, "productName": fruit.name_vi if fruit else b.fruit_id,
        "variety": b.variety, "farmId": b.farm_id, "farmName": farm.name if farm else None,
        "originProvince": b.origin_province, "quantityKg": b.quantity_kg, "harvestTs": b.harvest_ts,
        "certifications": b.certifications, "status": b.status, "currentActorId": b.current_actor_id,
        "currentActorName": cur.name if cur else None, "currentActorRole": cur.role if cur else None,
        "currentLat": last.lat if last else (cur.lat if cur else None),
        "currentLon": last.lon if last else (cur.lon if cur else None),
        "latestRul": latest_rul(db, b.batch_id), "metadataHash": b.metadata_hash, "qrPayload": b.qr_payload,
        "demoNote": b.demo_note, "openAlerts": len(alerts),
        "openAlertsBySeverity": {s: sum(1 for a in alerts if a.severity == s) for s in ("HIGH", "MEDIUM", "LOW")},
        "hasViolation": any(a.type == "COLD_CHAIN_VIOLATION" for a in alerts),
    }


def inspection_dict(i: Inspection) -> dict:
    return {"inspectionId": i.inspection_id, "batchId": i.batch_id, "ts": i.ts, "imageHash": i.image_hash,
            "hasPreprocessed": bool(i.preprocessed_path), "rulImage": i.rul_image_days, "rulSensor": i.rul_sensor_days,
            "rulFinal": i.rul_final_days, "ciLowDays": i.ci_low, "ciHighDays": i.ci_high,
            "freshnessLabel": i.freshness_label, "modelVersion": i.model_version, "modelHash": i.model_hash,
            "eventId": i.event_id, "note": i.note, "extra": i.extra, "actorId": i.actor_id}

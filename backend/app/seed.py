"""Nạp dữ liệu demo (mục 10). KHÔNG sửa dữ liệu lô FC-2026-006."""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

import bcrypt
from sqlalchemy.orm import Session

from . import config
from .db import SessionLocal, create_all, drop_all
from .models import Actor, Alert, Batch, Fruit, LedgerEvent, ModelVersion, RulPoint, SensorReading, User
from .services.ledger import get_ledger

log = logging.getLogger("fruitchain.seed")
EXPECTED = {"batches": 6, "sensor_readings": 714, "ledger_events": 29, "alerts": 5, "actors": 12, "users": 12}


def _j(name: str):  # noqa: ANN202
    return json.loads((config.DEMO_DATA_DIR / name).read_text(encoding="utf-8"))


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=config.BCRYPT_ROUNDS)).decode()


def is_empty(db: Session) -> bool:
    return db.query(Batch).count() == 0


def seed(db: Session) -> dict:
    d = config.DEMO_DATA_DIR
    for a in _j("actors.json"):
        db.add(Actor(actor_id=a["actorId"], name=a["name"], role=a["role"], province=a.get("province"),
                     lat=a.get("lat"), lon=a.get("lon")))
    db.flush()
    for u in _j("users.json"):
        db.add(User(username=u["username"], password_hash=hash_password(u["demoPassword"]), role=u["role"],
                    actor_id=u.get("actorId")))
    for f in _j("fruits.json"):
        db.add(Fruit(fruit_id=f["fruitId"], name_vi=f["nameVi"], shelf_ref_days=f["shelfRefDays"],
                     ref_temp_c=f["refTempC"], q10=f["q10"], optimal_temp_min_c=f["optimalTempMinC"],
                     optimal_temp_max_c=f["optimalTempMaxC"], alert_temp_c=f["alertTempC"],
                     optimal_humidity_pct=f["optimalHumidityPct"], raw=f))
    for m in _j("model_versions.json"):
        db.add(ModelVersion(version=m["version"], model_hash=m["modelHash"], registered_ts=m["registeredTs"],
                            description=m.get("description"), kind="sensor", details={"params": m.get("params")}))
    db.flush()
    for b in _j("batches.json"):
        db.add(Batch(batch_id=b["batchId"], fruit_id=b["fruitId"], variety=b["variety"], farm_id=b["farmId"],
                     origin_province=b.get("originProvince"), quantity_kg=b["quantityKg"], harvest_ts=b["harvestTs"],
                     certifications=b.get("certifications", []), status=b["status"],
                     current_actor_id=b["currentActorId"], metadata_hash=b["metadataHash"],
                     qr_payload=b["qrPayload"], demo_note=b.get("demoNote")))
    db.flush()
    with open(d / "sensor_readings.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            db.add(SensorReading(batch_id=r["batchId"], ts=r["ts"], temp_c=float(r["tempC"]),
                                 humidity_pct=int(r["humidityPct"]), ethylene_ppm=float(r["ethylenePpm"]),
                                 lat=float(r["lat"]), lon=float(r["lon"]), device_id=r["deviceId"],
                                 device_sig=r["deviceSig"]))
    with open(d / "rul_timeseries.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            db.add(RulPoint(batch_id=r["batchId"], ts=r["ts"], temp_c=float(r["tempC"]),
                            effective_hours=float(r["effectiveHoursConsumed"]), fraction_used=float(r["fractionUsed"]),
                            rul_at_current=float(r["rulDaysAtCurrent"]), rul_at_optimal=float(r["rulDaysAtOptimal"]),
                            ci_low=float(r["ciLowDays"]), ci_high=float(r["ciHighDays"]), freshness=r["freshness"]))
    for a in _j("alerts.json"):
        db.add(Alert(alert_id=a["alertId"], batch_id=a["batchId"], type=a["type"], severity=a["severity"], ts=a["ts"],
                     related_event_id=a.get("relatedEventId"), acknowledged=bool(a.get("acknowledged")),
                     message=a["message"]))
    db.flush()

    ledger = get_ledger()
    events = sorted(_j("events_ledger.json")["events"], key=lambda e: e["blockNumber"])
    if ledger.mode == "evm":
        ledger.replay(events, db, [m["modelHash"] for m in _j("model_versions.json")])  # type: ignore[attr-defined]
    else:
        for e in events:
            ledger.import_event(e, db)  # type: ignore[attr-defined]
    db.commit()
    return self_check(db)


def self_check(db: Session) -> dict:
    counts = {"batches": db.query(Batch).count(), "sensor_readings": db.query(SensorReading).count(),
              "ledger_events": db.query(LedgerEvent).count(), "alerts": db.query(Alert).count(),
              "actors": db.query(Actor).count(), "users": db.query(User).count()}
    for k, v in EXPECTED.items():
        if counts[k] != v:
            log.warning("Seed self-check: %s = %s (mong đợi %s)", k, counts[k], v)
    return counts


def reset_and_seed() -> dict:
    ledger = get_ledger()
    if ledger.mode == "evm" and not ledger.is_local:  # type: ignore[attr-defined]
        raise RuntimeError("Không reset DB đang gắn chain công khai. Dùng DATABASE_URL riêng cho demo Fuji.")
    drop_all()
    create_all()
    _clear_storage()
    with SessionLocal() as db:
        return seed(db)


def _clear_storage() -> None:
    import shutil

    for p in (config.RAW_DIR, config.PRE_DIR):
        if Path(p).exists():
            shutil.rmtree(p, ignore_errors=True)
        Path(p).mkdir(parents=True, exist_ok=True)


def ensure_seeded() -> None:
    create_all()
    ledger = get_ledger()
    with SessionLocal() as db:
        empty = is_empty(db)
    if not empty and ledger.mode == "evm" and not ledger.is_ready():  # type: ignore[attr-defined]
        if not ledger.is_local:  # type: ignore[attr-defined]
            raise RuntimeError("Không tìm thấy contract trên mạng công khai; giữ nguyên DB. Kiểm tra EVM_CHAIN_ID/EVM_CONTRACT_ADDRESS.")
        log.warning("Chain mới (node khởi động lại) — seed lại toàn bộ để đồng bộ DB với chain")
        log.info("Đã seed lại: %s", reset_and_seed())
        return
    if not empty and ledger.mode == "evm" and not ledger.is_local:  # type: ignore[attr-defined]
        with SessionLocal() as db:
            for batch in db.query(Batch).all():
                events = db.query(LedgerEvent).filter(LedgerEvent.batch_id == batch.batch_id).order_by(LedgerEvent.block_number).all()
                count = ledger.contract.functions.getEventCount(batch.batch_id).call()  # type: ignore[attr-defined]
                if count != len(events) or (events and ledger.get_head_hash(batch.batch_id) != events[-1].event_hash):
                    raise RuntimeError("DB không khớp contract công khai; giữ nguyên dữ liệu. Dùng DATABASE_URL/STORAGE_DIR riêng cho Fuji.")
                # A matching head alone is insufficient when DB receipts came from mock mode or another deployment.
                for event in events:
                    try:
                        rc = ledger.w3.eth.get_transaction_receipt(event.tx_hash)  # type: ignore[attr-defined]
                    except Exception as exc:
                        raise RuntimeError("Receipt trong DB không có trên chain này; dùng database Fuji riêng.") from exc
                    if rc.status != 1 or not rc.to or rc.to.lower() != ledger.contract.address.lower():  # type: ignore[attr-defined]
                        raise RuntimeError("Receipt không thuộc contract công khai đang chọn; giữ nguyên DB.")
    if empty:
        with SessionLocal() as db:
            counts = seed(db)
        log.info("Đã seed dữ liệu demo: %s", counts)

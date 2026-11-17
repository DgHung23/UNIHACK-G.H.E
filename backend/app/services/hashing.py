"""Quy tắc hash mục 6 của spec — phải đúng từng ký tự."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

DEVICE_KEY = "demo-device-key"  # CHỈ DÙNG CHO DEMO
ZERO_HASH = "0" * 64
EVENT_HASH_EXCLUDE = ("eventHash", "blockNumber", "txHash")


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_reading(batch_id: str, ts: str, temp_c: float, humidity_pct: int, ethylene_ppm: float,
                      lat: float, lon: float) -> str:
    return f"{batch_id}|{ts}|{float(temp_c):.1f}|{int(humidity_pct):d}|{float(ethylene_ppm):.1f}|{float(lat):.4f}|{float(lon):.4f}"


def canonical_reading_row(r: Any) -> str:
    """r: SensorReading ORM hoặc dict có các khoá camelCase."""
    if isinstance(r, dict):
        return canonical_reading(r["batchId"], r["ts"], r["tempC"], r["humidityPct"], r["ethylenePpm"], r["lat"], r["lon"])
    return canonical_reading(r.batch_id, r.ts, r.temp_c, r.humidity_pct, r.ethylene_ppm, r.lat, r.lon)


def device_sig(device_id: str, canonical: str) -> str:
    return sha(f"{device_id}|{canonical}|{DEVICE_KEY}")[:32]


def segment_hash(canonicals: Iterable[str]) -> str:
    return sha("\n".join(canonicals))


def metadata_hash(batch_id: str, fruit_id: str, variety: str, farm_id: str, quantity_kg: Any,
                  harvest_ts: str, certifications: list) -> str:
    return sha(canonical_json(dict(batchId=batch_id, fruitId=fruit_id, variety=variety, farmId=farm_id,
                                   quantityKg=quantity_kg, harvestTs=harvest_ts, certifications=certifications)))


def sold_hash(batch_id: str, sold_ts: str, quantity_kg: Any) -> str:
    return sha(canonical_json(dict(batchId=batch_id, soldTs=sold_ts, quantityKg=quantity_kg)))


def event_hash(event: dict) -> str:
    core = {k: v for k, v in event.items() if k not in EVENT_HASH_EXCLUDE}
    return sha(canonical_json(core))


def tx_hash_mock(ev_hash: str, block_number: int) -> str:
    return "0x" + sha(ev_hash + str(block_number))

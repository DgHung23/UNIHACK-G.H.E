"""Tạo sự kiện mới và ghi lên Ledger (eventId, prevHash, eventHash theo mục 6.7–6.8)."""
from __future__ import annotations

import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models import Actor, LedgerEvent
from .hashing import event_hash
from .ledger import get_ledger


def utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def next_event_id(db: Session, batch_id: str) -> str:
    n = db.query(LedgerEvent).filter(LedgerEvent.batch_id == batch_id).count()
    return f"EV-{batch_id[-3:]}-{n + 1:02d}"


def append_event(db: Session, *, batch_id: str, type: str, ts: str, actor_id: Optional[str],
                 to_actor_id: Optional[str], lat: Optional[float], lon: Optional[float], data_hash: str,
                 payload: dict, rul_snapshot: dict) -> dict:
    ledger = get_ledger()
    ev: dict[str, Any] = dict(batchId=batch_id, type=type, ts=ts, actorId=actor_id, toActorId=to_actor_id,
                              lat=lat, lon=lon, dataHash=data_hash, payload=payload, rulSnapshot=rul_snapshot,
                              eventId=next_event_id(db, batch_id), prevHash=ledger.get_head_hash(batch_id, db))
    ev["eventHash"] = event_hash(ev)
    res = ledger.append(ev, db)
    ev.update(res)
    return ev


def custody_timeline(events: list[dict]) -> list[tuple[str, str]]:
    out = []
    for e in sorted(events, key=lambda e: e["blockNumber"]):
        if e["type"] == "HARVEST":
            out.append((e["ts"], e["actorId"]))
        elif e["type"] == "HANDOFF":
            out.append((e["ts"], e["toActorId"]))
    return sorted(out)


def holder_at(timeline: list[tuple[str, str]], ts: str) -> Optional[str]:
    holder = None
    for t, a in timeline:
        if t <= ts:
            holder = a
        else:
            break
    return holder


def actor_roles(db: Session) -> dict[str, str]:
    return {a.actor_id: a.role for a in db.query(Actor).all()}

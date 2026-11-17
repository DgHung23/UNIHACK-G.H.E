"""Thuật toán Verify (mục 6.9 + 6.10)."""
from __future__ import annotations

import time
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import Inspection, SensorReading
from .hashing import ZERO_HASH, canonical_reading_row, device_sig, event_hash, segment_hash, sha_bytes
from .ledger import get_ledger


def verify_batch(db: Session, batch_id: str) -> dict:
    events = get_ledger().get_events(batch_id, db)
    readings = db.query(SensorReading).filter(SensorReading.batch_id == batch_id).order_by(SensorReading.ts).all()
    by_ts = {r.ts: r for r in readings}
    ts_sorted = sorted(by_ts)

    chain_ok = True
    chain_issues = []
    prev = ZERO_HASH
    for e in events:
        if e["prevHash"] != prev:
            chain_ok = False
            chain_issues.append({"eventId": e["eventId"], "issue": "prevHash không khớp"})
        if event_hash(e) != e["eventHash"]:
            chain_ok = False
            chain_issues.append({"eventId": e["eventId"], "issue": "eventHash tính lại không khớp"})
        prev = e["eventHash"]

    segments = []
    for e in events:
        t = e["type"]
        p = e.get("payload") or {}
        if t in ("HANDOFF", "VIOLATION"):
            lo, hi = (p["fromReading"], p["toReading"]) if t == "HANDOFF" else (p["startTs"], p["endTs"])
            keys = [k for k in ts_sorted if lo <= k <= hi]
            recomputed = segment_hash(canonical_reading_row(by_ts[k]) for k in keys)
            segments.append(dict(eventId=e["eventId"], type=t, onChainDataHash=e["dataHash"],
                                 recomputedHash=recomputed, match=recomputed == e["dataHash"]))
        elif t == "INSPECTION":
            insp = db.query(Inspection).filter(Inspection.event_id == e["eventId"]).first()
            recomputed = None
            if insp and Path(insp.raw_image_path).is_file():
                recomputed = sha_bytes(Path(insp.raw_image_path).read_bytes())
            segments.append(dict(eventId=e["eventId"], type=t, onChainDataHash=e["dataHash"],
                                 recomputedHash=recomputed, match=recomputed == e["dataHash"]))

    sig_fail = [r.ts for r in readings if device_sig(r.device_id, canonical_reading_row(r)) != r.device_sig]
    ok = all(s["match"] for s in segments) and not sig_fail and chain_ok
    return dict(batchId=batch_id, chainLinkIntact=chain_ok, segments=segments,
                signatureFailureCount=len(sig_fail), overall="PASS" if ok else "FAIL",
                signatureFailures=sig_fail, chainIssues=chain_issues, eventCount=len(events),
                readingCount=len(readings), ledgerMode=get_ledger().mode,
                checkedAt=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

from __future__ import annotations

from typing import Optional, Protocol

from sqlalchemy.orm import Session

from ...models import LedgerEvent

EVENT_KEYS = ("eventId", "batchId", "type", "ts", "actorId", "toActorId", "lat", "lon", "dataHash", "payload",
              "rulSnapshot", "prevHash")


class Ledger(Protocol):
    mode: str

    def network_info(self) -> dict: ...

    def append(self, event: dict, db: Optional[Session] = None) -> dict: ...          # {blockNumber, txHash}
    def get_events(self, batch_id: str, db: Optional[Session] = None) -> list[dict]: ...
    def get_head_hash(self, batch_id: str, db: Optional[Session] = None) -> str: ...
    def register_model(self, model_hash: str, version: str) -> None: ...


def row_to_event(r: LedgerEvent) -> dict:
    return dict(eventId=r.event_id, batchId=r.batch_id, type=r.type, ts=r.ts, actorId=r.actor_id,
                toActorId=r.to_actor_id, lat=r.lat, lon=r.lon, dataHash=r.data_hash, payload=r.payload,
                rulSnapshot=r.rul_snapshot, prevHash=r.prev_hash, eventHash=r.event_hash,
                blockNumber=r.block_number, txHash=r.tx_hash)


def event_to_row(e: dict) -> LedgerEvent:
    return LedgerEvent(event_id=e["eventId"], batch_id=e["batchId"], type=e["type"], ts=e["ts"],
                       actor_id=e.get("actorId"), to_actor_id=e.get("toActorId"), lat=e.get("lat"), lon=e.get("lon"),
                       data_hash=e["dataHash"], payload=e.get("payload"), rul_snapshot=e.get("rulSnapshot"),
                       prev_hash=e["prevHash"], event_hash=e["eventHash"], block_number=e["blockNumber"],
                       tx_hash=e["txHash"])

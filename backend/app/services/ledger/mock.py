"""MockLedger: bảng ledger_events append-only (mặc định, chạy offline)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ...db import SessionLocal
from ...models import LedgerEvent
from ..hashing import ZERO_HASH, tx_hash_mock
from .base import event_to_row, row_to_event

FIRST_BLOCK = 1000001


class MockLedger:
    mode = "mock"

    def network_info(self) -> dict:
        return dict(mode="mock", network="Offline demo", chainId=None, connected=False, ready=True,
                    contractAddress=None, explorerUrl=None, explorerTxUrl=None, accountAddress=None,
                    canWrite=True, isCompetitionNetwork=False, trustModel="Sổ cái mô phỏng lưu trong cùng database.",
                    message="Chế độ demo offline; chưa có bằng chứng trên Avalanche. Chọn EVM + Fuji để dự thi.")

    def _session(self, db: Optional[Session]) -> tuple[Session, bool]:
        return (db, False) if db is not None else (SessionLocal(), True)

    def append(self, event: dict, db: Optional[Session] = None) -> dict:
        s, own = self._session(db)
        try:
            mx = s.query(func.max(LedgerEvent.block_number)).scalar()
            block = FIRST_BLOCK if mx is None else int(mx) + 1
            e = dict(event, blockNumber=block, txHash=tx_hash_mock(event["eventHash"], block))
            s.add(event_to_row(e))
            s.flush()
            if own:
                s.commit()
            return {"blockNumber": block, "txHash": e["txHash"]}
        finally:
            if own:
                s.close()

    def import_event(self, event: dict, db: Session) -> None:
        """Seed: nạp nguyên sự kiện (giữ eventHash, blockNumber, txHash)."""
        db.add(event_to_row(event))

    def get_events(self, batch_id: str, db: Optional[Session] = None) -> list[dict]:
        s, own = self._session(db)
        try:
            rows = s.query(LedgerEvent).filter(LedgerEvent.batch_id == batch_id).order_by(LedgerEvent.block_number).all()
            return [row_to_event(r) for r in rows]
        finally:
            if own:
                s.close()

    def get_head_hash(self, batch_id: str, db: Optional[Session] = None) -> str:
        ev = self.get_events(batch_id, db)
        return ev[-1]["eventHash"] if ev else ZERO_HASH

    def register_model(self, model_hash: str, version: str) -> None:  # noqa: ARG002
        return None

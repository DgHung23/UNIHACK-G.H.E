"""Real EVM evidence ledger: local Hardhat or Avalanche Fuji/C-Chain.

Public RPCs have no unlocked accounts: sign locally and send raw transactions.
Only local development chains may auto-deploy. No private key reaches the UI.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from threading import Lock
from typing import Optional

from sqlalchemy.orm import Session

from ... import config
from ...db import SessionLocal
from ...models import LedgerEvent
from ..hashing import ZERO_HASH
from .base import event_to_row, row_to_event

log = logging.getLogger("fruitchain.evm")
ARTIFACT = config.CONTRACTS_DIR / "artifacts" / "contracts" / "FruitChain.sol" / "FruitChain.json"
DEPLOYMENT = config.STORAGE_DIR / "evm_deployment.json"
LOCAL_CHAINS = {1337, 31337}


def _b32(h: Optional[str]) -> bytes:
    if not h:
        return bytes(32)
    h = h.removeprefix("0x")
    if len(h) != 64:
        raise ValueError("Hash bằng chứng phải có đúng 32 byte")
    return bytes.fromhex(h)


def _hex(b: bytes) -> str:
    return bytes(b).hex()


def _epoch(ts: str) -> int:
    return int(dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp())


class EvmLedger:
    mode = "evm"

    def __init__(self, rpc: str):
        from web3 import Web3

        self.w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))
        if not self.w3.is_connected():
            raise RuntimeError("Không kết nối được EVM RPC. Kiểm tra EVM_RPC hoặc chạy Hardhat node.")
        self.chain_id = int(self.w3.eth.chain_id)
        if config.EVM_CHAIN_ID is not None and self.chain_id != config.EVM_CHAIN_ID:
            raise RuntimeError(f"Sai EVM chain ID: nhận {self.chain_id}, yêu cầu {config.EVM_CHAIN_ID}")
        self.is_local = self.chain_id in LOCAL_CHAINS
        if not ARTIFACT.is_file():
            raise RuntimeError("Chưa compile contract: chạy npm run compile trong contracts/.")
        art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        self.abi, self.bytecode = art["abi"], art["bytecode"]
        self._signer = self.w3.eth.account.from_key(config.EVM_PRIVATE_KEY) if config.EVM_PRIVATE_KEY else None
        accounts = self.w3.eth.accounts if self.is_local and self._signer is None else []
        self.account = self._signer.address if self._signer else (accounts[0] if accounts else None)
        self._tx_lock = Lock()
        self.contract = None
        self.deployment_block = config.EVM_DEPLOYMENT_BLOCK
        saved = json.loads(DEPLOYMENT.read_text(encoding="utf-8")) if DEPLOYMENT.is_file() else {}
        saved_matches = saved.get("chainId") == self.chain_id
        addr = config.EVM_CONTRACT_ADDRESS or (saved.get("address") if saved_matches else None)
        if addr:
            addr = Web3.to_checksum_address(addr)
            if saved_matches and saved.get("address", "").lower() == addr.lower():
                self.deployment_block = self.deployment_block or saved.get("blockNumber")
            code = self.w3.eth.get_code(addr)
            expected = bytes.fromhex(art["deployedBytecode"].removeprefix("0x"))
            if code and bytes(code) == expected:
                self.contract = self.w3.eth.contract(address=addr, abi=self.abi)
            elif not self.is_local or config.EVM_CONTRACT_ADDRESS:
                raise RuntimeError("Contract không tồn tại hoặc bytecode khác bản hiện tại. Kiểm tra EVM_CONTRACT_ADDRESS và mạng.")

    def is_ready(self) -> bool:
        return self.contract is not None

    def network_info(self) -> dict:
        explorer = {43113: "https://testnet.snowtrace.io", 43114: "https://snowtrace.io"}.get(self.chain_id)
        address = self.contract.address if self.contract else None
        return dict(
            mode=self.mode, network={43113: "Avalanche Fuji", 43114: "Avalanche C-Chain"}.get(
                self.chain_id, "Hardhat local" if self.is_local else "Custom EVM"),
            chainId=self.chain_id, connected=self.w3.is_connected(), ready=self.is_ready(),
            contractAddress=address, explorerUrl=explorer,
            explorerTxUrl=f"{explorer}/tx/" if explorer else None, accountAddress=self.account,
            canWrite=self.account is not None and self.is_ready(), isCompetitionNetwork=self.chain_id in {43113, 43114},
            trustModel="Backend ký giao dịch với vai trò relayer; đăng nhập và quyền người dùng được kiểm tra off-chain.",
            message="Bằng chứng được đối chiếu trực tiếp với smart contract trên mạng đã kết nối.",
        )

    def _receipt(self, fn):
        if self.account is None:
            raise RuntimeError("Chế độ chỉ đọc: cần EVM_PRIVATE_KEY của ví testnet để ghi bằng chứng.")
        with self._tx_lock:
            if self._signer:
                tx = fn.build_transaction({
                    "from": self.account, "chainId": self.chain_id,
                    "nonce": self.w3.eth.get_transaction_count(self.account, "pending"),
                    "gasPrice": self.w3.eth.gas_price,
                })
                signed = self._signer.sign_transaction(tx)
                tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            else:
                tx_hash = fn.transact({"from": self.account})
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt.status != 1:
                raise RuntimeError("Giao dịch bị revert; bằng chứng chưa được ghi lên chain.")
            return receipt

    def deploy(self) -> str:
        if not self.is_local or not config.EVM_AUTO_DEPLOY:
            raise RuntimeError("Tự deploy chỉ hỗ trợ chain local. Với Fuji, chạy npm run deploy:fuji rồi đặt EVM_CONTRACT_ADDRESS.")
        rc = self._receipt(self.w3.eth.contract(abi=self.abi, bytecode=self.bytecode).constructor())
        self.contract = self.w3.eth.contract(address=rc.contractAddress, abi=self.abi)
        self.deployment_block = int(rc.blockNumber)
        DEPLOYMENT.parent.mkdir(parents=True, exist_ok=True)
        DEPLOYMENT.write_text(json.dumps({"address": rc.contractAddress, "chainId": self.chain_id,
                                          "blockNumber": self.deployment_block}), encoding="utf-8")
        log.info("Đã deploy FruitChain tại %s (chain %s)", rc.contractAddress, self.chain_id)
        return rc.contractAddress

    def _tx(self, fn) -> dict:
        rc = self._receipt(fn)
        return {"blockNumber": int(rc.blockNumber), "txHash": "0x" + _hex(rc.transactionHash)}

    def register_model(self, model_hash: str, version: str) -> None:
        if self.contract is None:
            return
        if not self.contract.functions.registeredModels(_b32(model_hash)).call():
            self._tx(self.contract.functions.registerModel(_b32(model_hash), version))

    def _send(self, e: dict) -> dict:
        f = self.contract.functions
        snap = e.get("rulSnapshot") or {}
        rul = snap.get("rulDaysAtCurrent")
        rul = max(0, min(2**32 - 1, int(round(float(rul) * 100)))) if rul is not None else 0
        mh = snap.get("modelHash")
        if mh and not f.registeredModels(_b32(mh)).call():
            self.register_model(mh, snap.get("modelVersion") or "unknown")
        mh_b = _b32(mh)
        bid, ts, a = e["batchId"], _epoch(e["ts"]), e.get("actorId") or ""
        dh, ph, eh = _b32(e["dataHash"]), _b32(e["prevHash"]), _b32(e["eventHash"])
        t = e["type"]
        if t == "HARVEST":
            fn = f.createBatch(bid, a, ts, dh, eh, rul, mh_b)
        elif t == "HANDOFF":
            fn = f.recordHandoff(bid, a, e.get("toActorId") or "", ts, dh, ph, eh, rul, mh_b)
        elif t == "VIOLATION":
            fn = f.recordViolation(bid, a, ts, dh, ph, eh, rul, mh_b)
        elif t == "SOLD":
            fn = f.recordSold(bid, a, ts, dh, ph, eh, rul, mh_b)
        elif t == "INSPECTION":
            fn = f.recordInspection(bid, a, ts, dh, ph, eh, rul, mh_b)
        else:
            raise ValueError(f"Loại sự kiện không hỗ trợ: {t}")
        return self._tx(fn)

    def _existing_receipts(self, batch_ids: set[str]) -> dict:
        if self.deployment_block is None:
            raise RuntimeError("Để khôi phục DB từ contract đã có, cần EVM_DEPLOYMENT_BLOCK (block deploy).")
        out = {}
        latest = self.w3.eth.block_number
        for start in range(int(self.deployment_block), latest + 1, 2000):
            logs = self.contract.events.BatchEventRecorded().get_logs(from_block=start, to_block=min(start + 1999, latest))
            for item in logs:
                if item["args"]["batchId"] in batch_ids:
                    out[_hex(item["args"]["eventHash"])] = {
                        "blockNumber": int(item["blockNumber"]), "txHash": "0x" + _hex(item["transactionHash"]),
                    }
        return out

    def replay(self, events: list[dict], db: Session, model_hashes: list[str]) -> None:
        """Local resets deploy anew; public replay reuses matching evidence without duplicate txs."""
        if self.is_local:
            self.deploy()
        elif self.contract is None:
            raise RuntimeError("Chưa cấu hình contract Fuji. Deploy bằng script trước khi seed.")
        existing_counts = {}
        positions = {}
        for e in events:
            bid = e["batchId"]
            if bid not in existing_counts:
                existing_counts[bid] = self.contract.functions.getEventCount(bid).call()
            index = positions.get(bid, 0)
            if index < existing_counts[bid]:
                onchain = self.contract.functions.getEvent(bid, index).call()
                if _hex(onchain[7]) != e["eventHash"]:
                    raise RuntimeError(f"Contract đã chứa dữ liệu khác cho {bid}; cần contract demo riêng.")
            positions[bid] = index + 1
        if any(existing_counts[bid] > positions[bid] for bid in positions):
            raise RuntimeError("Contract có sự kiện ngoài seed; không thể reset DB từ demo vì sẽ mất dữ liệu off-chain.")
        receipts = self._existing_receipts(set(positions)) if any(existing_counts.values()) else {}
        for mh in model_hashes:
            self.register_model(mh, "seed")
        for e in sorted(events, key=lambda item: item["blockNumber"]):
            res = receipts.get(e["eventHash"]) or self._send(e)
            db.add(event_to_row(dict(e, **res)))

    def append(self, event: dict, db: Optional[Session] = None) -> dict:
        if self.contract is None:
            raise RuntimeError("Contract chưa deploy hoặc chưa cấu hình.")
        res = self._send(event)
        s = db or SessionLocal()
        try:
            s.add(event_to_row(dict(event, **res)))
            s.flush()
            if db is None:
                s.commit()
        finally:
            if db is None:
                s.close()
        return res

    def get_events(self, batch_id: str, db: Optional[Session] = None) -> list[dict]:
        if self.contract is None:
            raise RuntimeError("Không có contract để đối chiếu bằng chứng on-chain.")
        s = db or SessionLocal()
        try:
            rows = [row_to_event(r) for r in s.query(LedgerEvent).filter(LedgerEvent.batch_id == batch_id)
                    .order_by(LedgerEvent.block_number, LedgerEvent.ts, LedgerEvent.event_id).all()]
        finally:
            if db is None:
                s.close()
        f = self.contract.functions
        n = f.getEventCount(batch_id).call()
        for i, r in enumerate(rows):
            if i >= n:
                r["eventHash"] = "MISSING_ON_CHAIN"
                continue
            ev = f.getEvent(batch_id, i).call()
            r["dataHash"], r["prevHash"], r["eventHash"] = _hex(ev[5]), _hex(ev[6]), _hex(ev[7])
        # Fail closed if an off-chain event was deleted, including deletion of every row.
        if n > len(rows):
            rows.append(dict(eventId="MISSING_OFFCHAIN_EVENT", batchId=batch_id, type="CHAIN_COUNT_MISMATCH",
                             ts="1970-01-01T00:00:00Z", actorId=None, toActorId=None, lat=None, lon=None,
                             dataHash=ZERO_HASH, payload={}, rulSnapshot=None, prevHash=ZERO_HASH,
                             eventHash="MISSING_OFFCHAIN_EVENT", blockNumber=0, txHash=None))
        return rows

    def get_head_hash(self, batch_id: str, db: Optional[Session] = None) -> str:
        if self.contract is None:
            raise RuntimeError("Không có contract để đọc chain head.")
        return _hex(self.contract.functions.headHash(batch_id).call())

    def import_event(self, event: dict, db: Session) -> None:
        raise NotImplementedError


__all__ = ["EvmLedger", "Path"]

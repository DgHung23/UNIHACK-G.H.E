"""Network disclosure, public-chain safeguards, signed EVM writes and missing evidence."""
import json
from types import SimpleNamespace

import pytest

from app import config
from app.db import SessionLocal
from app.models import LedgerEvent
from app.routers import misc
from app.services.ledger import get_ledger
from app.services.ledger.mock import MockLedger
from app.services.verify import verify_batch
from conftest import auth


def test_network_identity_is_public_and_has_no_secrets(client):
    response = client.get("/api/ledger/network")
    assert response.status_code == 200
    info = response.json()
    assert {"mode", "chainId", "network", "connected", "ready", "contractAddress", "explorerUrl",
            "explorerTxUrl", "canWrite", "isCompetitionNetwork", "trustModel"} <= info.keys()
    assert info["mode"] == config.LEDGER_MODE
    assert "private" not in response.text.lower()
    assert "EVM_RPC" not in response.text
    if config.EVM_PRIVATE_KEY:
        assert config.EVM_PRIVATE_KEY not in response.text
    trace = client.get("/api/public/trace/FC-2026-001").json()
    assert trace["ledgerNetwork"]["chainId"] == info["chainId"]


def test_mock_is_explicitly_not_avalanche():
    info = MockLedger().network_info()
    assert info["mode"] == "mock"
    assert info["isCompetitionNetwork"] is False
    assert info["connected"] is False
    assert info["contractAddress"] is None
    assert info["explorerTxUrl"] is None


@pytest.mark.parametrize("endpoint", ["/api/admin/seed", "/api/admin/reset"])
def test_public_chain_reset_rejected_before_database_changes(client, monkeypatch, endpoint):
    headers = auth(client, "admin")
    monkeypatch.setattr(misc, "get_ledger", lambda: SimpleNamespace(mode="evm", is_local=False))
    response = client.post(endpoint, headers=headers)
    assert response.status_code == 409
    # The denial happens before dropping tables or clearing storage.
    assert client.get("/api/batches", headers=headers).status_code == 200


@pytest.mark.parametrize("remove_all", [False, True])
def test_evm_deleted_offchain_rows_fail_verification(client, remove_all):
    ledger = get_ledger()
    if ledger.mode != "evm":
        pytest.skip("EVM integration: run with LEDGER_MODE=evm and a local Hardhat node")
    # Simulate a database deletion without bypassing the append-only production triggers.
    with SessionLocal() as db:
        rows = db.query(LedgerEvent).filter(LedgerEvent.batch_id == "FC-2026-001").order_by(LedgerEvent.block_number).all()

        class MissingRows:
            def filter(self, *_args):
                return self

            def order_by(self, *_args):
                return self

            def all(self):
                return [] if remove_all else rows[1:]

        class DatabaseView:
            def query(self, model):
                return MissingRows() if model is LedgerEvent else db.query(model)

        result = verify_batch(DatabaseView(), "FC-2026-001")
        assert result["overall"] == "FAIL"
        assert result["chainLinkIntact"] is False
        assert any(issue["eventId"] == "MISSING_OFFCHAIN_EVENT" for issue in result["chainIssues"])


def test_signed_evm_transactions_and_public_deploy_guard(client, monkeypatch):
    ledger = get_ledger()
    if ledger.mode != "evm" or not ledger.is_local:
        pytest.skip("Signed integration test uses local test ETH only")
    from app.services.ledger.evm import EvmLedger

    wallet = ledger.w3.eth.account.create()
    # Fresh wallet is not unlocked by the RPC, so success requires raw signed transactions.
    assert wallet.address not in ledger.w3.eth.accounts
    tx_hash = ledger.w3.eth.send_transaction({"from": ledger.w3.eth.accounts[0], "to": wallet.address,
                                               "value": ledger.w3.to_wei(1, "ether")})
    assert ledger.w3.eth.wait_for_transaction_receipt(tx_hash).status == 1
    monkeypatch.setattr(config, "EVM_PRIVATE_KEY", wallet.key.hex())
    monkeypatch.setattr(config, "EVM_CONTRACT_ADDRESS", "")
    signed = EvmLedger(config.EVM_RPC)
    signed.deploy()
    assert signed.account == wallet.address
    assert signed.contract.functions.admin().call() == wallet.address
    model_hash = "ab" * 32
    signed.register_model(model_hash, "signed-test")
    assert signed.contract.functions.registeredModels(bytes.fromhex(model_hash)).call()
    # Public chains cannot auto-deploy even when a signer is configured.
    signed.is_local = False
    with pytest.raises(RuntimeError, match="Tự deploy"):
        signed.deploy()


def test_evm_chain_id_mismatch_is_rejected(client, monkeypatch):
    ledger = get_ledger()
    if ledger.mode != "evm":
        pytest.skip("EVM integration")
    from app.services.ledger.evm import EvmLedger
    monkeypatch.setattr(config, "EVM_CHAIN_ID", ledger.chain_id + 1)
    with pytest.raises(RuntimeError, match="chain ID"):
        EvmLedger(config.EVM_RPC)


def test_public_replay_reuses_receipts_without_duplicate_transactions(client):
    ledger = get_ledger()
    if ledger.mode != "evm" or not ledger.is_local:
        pytest.skip("Recovery flow is exercised against a local chain only")
    from app.services.ledger.evm import EvmLedger

    recovering = EvmLedger(config.EVM_RPC)
    recovering.deploy()
    # Exercise the public recovery branch using only local test ETH.
    recovering.is_local = False
    all_events = json.loads((config.DEMO_DATA_DIR / "events_ledger.json").read_text(encoding="utf-8"))["events"]
    events = sorted(all_events, key=lambda item: item["blockNumber"])[:2]
    model_hashes = list({event["rulSnapshot"]["modelHash"] for event in events})
    rows = []
    database = SimpleNamespace(add=rows.append)
    recovering.replay(events, database, model_hashes)
    first = [(row.event_hash, row.tx_hash, row.block_number) for row in rows]
    head_block = recovering.w3.eth.block_number
    rows.clear()
    recovering.replay(events, database, model_hashes)
    assert [(row.event_hash, row.tx_hash, row.block_number) for row in rows] == first
    assert recovering.w3.eth.block_number == head_block


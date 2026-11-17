from __future__ import annotations

from typing import Optional

from ... import config
from .base import Ledger, row_to_event  # noqa: F401

_ledger: Optional[Ledger] = None


def get_ledger() -> Ledger:
    global _ledger
    if _ledger is None:
        if config.LEDGER_MODE == "evm":
            from .evm import EvmLedger

            _ledger = EvmLedger(config.EVM_RPC)
        else:
            from .mock import MockLedger

            _ledger = MockLedger()
    return _ledger


def reset_ledger() -> None:
    global _ledger
    _ledger = None

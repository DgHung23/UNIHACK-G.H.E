"""Cấu hình đọc từ biến môi trường (xem .env.example)."""
from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


def _load_dotenv() -> None:
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()


def _path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    if not raw:
        return default
    p = Path(raw)
    return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


DEMO_DATA_DIR = _path("DEMO_DATA_DIR", PROJECT_DIR / "demo_data")
STORAGE_DIR = _path("STORAGE_DIR", BACKEND_DIR / "storage")
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{(BACKEND_DIR / 'fruitchain.db').as_posix()}"
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
JWT_HOURS = int(os.environ.get("JWT_HOURS", "12"))
LEDGER_MODE = os.environ.get("LEDGER_MODE", "mock").lower()
EVM_RPC = os.environ.get("EVM_RPC", "http://127.0.0.1:8545")
EVM_PRIVATE_KEY = os.environ.get("EVM_PRIVATE_KEY", "")
EVM_CHAIN_ID = int(os.environ["EVM_CHAIN_ID"]) if os.environ.get("EVM_CHAIN_ID") else None
EVM_CONTRACT_ADDRESS = os.environ.get("EVM_CONTRACT_ADDRESS", "")
EVM_DEPLOYMENT_BLOCK = int(os.environ["EVM_DEPLOYMENT_BLOCK"]) if os.environ.get("EVM_DEPLOYMENT_BLOCK") else None
EVM_AUTO_DEPLOY = os.environ.get("EVM_AUTO_DEPLOY", "1") == "1"
CONTRACTS_DIR = _path("CONTRACTS_DIR", PROJECT_DIR / "contracts")
DEFAULT_MODEL_DIR = _path("DEFAULT_MODEL_DIR", PROJECT_DIR / "ml_model")

# Model ảnh: q10 (không có model ảnh) | custom (model của bạn). Có thể đổi lúc chạy ở trang Cài đặt.
RUL_MODEL = os.environ.get("RUL_MODEL", "").lower()
RUL_MODEL_PATH = os.environ.get("RUL_MODEL_PATH", "")
RUL_MODEL_CHECKPOINT = os.environ.get("RUL_MODEL_CHECKPOINT", "")
FUSION = os.environ.get("FUSION", "min").lower()
AUTO_SEED = os.environ.get("AUTO_SEED", "1") != "0"
BCRYPT_ROUNDS = int(os.environ.get("BCRYPT_ROUNDS", "10"))

RAW_DIR = STORAGE_DIR / "raw"
PRE_DIR = STORAGE_DIR / "preprocessed"
MODEL_SETTINGS_FILE = STORAGE_DIR / "model_settings.json"
for _d in (RAW_DIR, PRE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

import os
import sys
import tempfile
from pathlib import Path

import pytest
sys.dont_write_bytecode = True

_TMP = Path(tempfile.mkdtemp(prefix="fruitchain_test_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ.setdefault("LEDGER_MODE", "mock")
os.environ["RUL_MODEL"] = os.environ.get("TEST_RUL_MODEL", "q10")
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ["AUTO_SEED"] = "1"

BACKEND = Path(__file__).resolve().parents[1]
os.environ["DEMO_DATA_DIR"] = str(BACKEND.parent / "demo_data")
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.main import app  # noqa: E402

DEMO = config.DEMO_DATA_DIR


def _resolve_user_model_dir() -> Path:
    env_dir = os.environ.get("USER_MODEL_DIR")
    if env_dir:
        p = Path(env_dir)
        if not p.is_absolute():
            p = (config.PROJECT_DIR / p).resolve() if not p.exists() else p.resolve()
        if p.is_dir() and (p / "src").is_dir():
            return p
    bundled = getattr(config, "DEFAULT_MODEL_DIR", (config.PROJECT_DIR / "ml_model").resolve())
    if bundled.is_dir() and (bundled / "src").is_dir():
        return bundled
    return bundled


# Dự án model của bạn (mặc định trỏ tới bundled ml_model nếu không cấu hình khác)
USER_MODEL_DIR = _resolve_user_model_dir()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def fresh(client):
    """Seed lại trước các test có ghi dữ liệu."""
    def _do():
        r = client.post("/api/admin/seed", headers=auth(client, "admin"))
        assert r.status_code == 200, r.text
    return _do


_tokens = {}


def auth(client, username, password="demo1234"):
    key = username
    if key not in _tokens:
        r = client.post("/api/auth/login", json={"username": username, "password": password})
        assert r.status_code == 200, r.text
        _tokens[key] = r.json()["token"]
    return {"Authorization": f"Bearer {_tokens[key]}"}


def clear_tokens():
    _tokens.clear()

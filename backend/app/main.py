from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .db import SessionLocal, create_all
from .routers import auth, batches, meta, misc, settings
from .seed import ensure_seeded
from .services.ledger import get_ledger
from .services.rul import image_models

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("fruitchain")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if config.AUTO_SEED:
        ensure_seeded()
    else:
        create_all()
    with SessionLocal() as db:
        image_models.autoload(db)
    log.info("FruitChain sẵn sàng | ledger=%s | model ảnh=%s", get_ledger().mode, image_models.status()["active"])
    yield


app = FastAPI(title="FruitChain API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, meta.router, batches.router, misc.router, misc.admin, settings.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "ledgerMode": get_ledger().mode, "imageModel": image_models.status()["active"]}


# Phục vụ frontend đã build (frontend/dist) nếu có → chỉ cần chạy 1 lệnh uvicorn.
DIST = config.PROJECT_DIR / "frontend" / "dist"
if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            from fastapi import HTTPException

            raise HTTPException(404, "Not Found")
        f = DIST / full_path
        if full_path and f.is_file() and Path(f).resolve().is_relative_to(DIST.resolve()):
            return FileResponse(f)
        return FileResponse(DIST / "index.html")

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import Actor, Fruit, ModelVersion
from ..serializers import actor_dict, fruit_dict, model_dict
from ..services.ledger import get_ledger
from ..services.rul import FUSION_MODES, image_models, sensor_model

router = APIRouter(prefix="/meta", tags=["meta"], dependencies=[Depends(current_user)])


@router.get("/actors")
def actors(db: Session = Depends(get_db)) -> list[dict]:
    return [actor_dict(a) for a in db.query(Actor).order_by(Actor.actor_id).all()]


@router.get("/fruits")
def fruits(db: Session = Depends(get_db)) -> list[dict]:
    return [fruit_dict(f) for f in db.query(Fruit).order_by(Fruit.fruit_id).all()]


@router.get("/models")
def models(db: Session = Depends(get_db)) -> dict:
    sm = sensor_model(db)
    return {
        "versions": [model_dict(m) for m in db.query(ModelVersion).order_by(ModelVersion.registered_ts).all()],
        "sensorModel": {"name": sm.name, "version": sm.version, "modelHash": sm.model_hash()},
        "imageModel": image_models.status(),
        "fusion": image_models.fusion, "fusionModes": list(FUSION_MODES),
        "ledgerMode": get_ledger().mode,
    }

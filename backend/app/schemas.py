from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str
    password: str


class BatchCreateIn(BaseModel):
    fruitId: str
    variety: str
    farmId: str
    quantityKg: float = Field(gt=0)
    harvestTs: Optional[str] = None
    certifications: list[str] = []
    originProvince: Optional[str] = None


class HandoffIn(BaseModel):
    toActorId: str


class SoldIn(BaseModel):
    quantityKg: Optional[float] = None


class ReadingIn(BaseModel):
    batchId: str
    ts: str
    tempC: float
    humidityPct: int
    ethylenePpm: float
    lat: float
    lon: float
    deviceSig: str
    deviceId: Optional[str] = None


class IngestIn(BaseModel):
    readings: list[ReadingIn]


class PredictReading(BaseModel):
    ts: Optional[str] = None
    tempC: float


class PredictIn(BaseModel):
    fruitId: str
    readings: list[PredictReading]


class ModelLoadIn(BaseModel):
    path: str = Field(min_length=1)
    checkpoint: Optional[str] = None
    device: Literal["auto", "cpu", "cuda"] = "auto"
    outputUnit: Literal["auto", "hours", "days"] = "auto"
    fruits: list[str] = Field(default_factory=lambda: ["strawberry"], min_length=1)
    fusion: Optional[str] = None
    useSensorInputs: bool = True


class ModelOptionsIn(BaseModel):
    fusion: Optional[str] = None
    fruits: Optional[list[str]] = Field(default=None, min_length=1)
    useSensorInputs: Optional[bool] = None


class PathIn(BaseModel):
    path: str


class DialogIn(BaseModel):
    initial: Optional[str] = None


class TamperIn(BaseModel):
    tamperType: str = "sensor"


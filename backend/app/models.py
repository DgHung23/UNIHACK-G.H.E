from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Actor(Base):
    __tablename__ = "actors"
    actor_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    province: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class User(Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String, primary_key=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    actor_id: Mapped[Optional[str]] = mapped_column(ForeignKey("actors.actor_id"), nullable=True)


class Fruit(Base):
    __tablename__ = "fruits"
    fruit_id: Mapped[str] = mapped_column(String, primary_key=True)
    name_vi: Mapped[str] = mapped_column(String)
    shelf_ref_days: Mapped[float] = mapped_column(Float)
    ref_temp_c: Mapped[float] = mapped_column(Float)
    q10: Mapped[float] = mapped_column(Float)
    optimal_temp_min_c: Mapped[float] = mapped_column(Float)
    optimal_temp_max_c: Mapped[float] = mapped_column(Float)
    alert_temp_c: Mapped[float] = mapped_column(Float)
    optimal_humidity_pct: Mapped[float] = mapped_column(Float)
    raw: Mapped[dict] = mapped_column(JSON)  # bản gốc trong fruits.json (dùng tính modelHash Q10)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    version: Mapped[str] = mapped_column(String, primary_key=True)
    model_hash: Mapped[str] = mapped_column(String)
    registered_ts: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String, default="sensor")  # sensor | image
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class Batch(Base):
    __tablename__ = "batches"
    batch_id: Mapped[str] = mapped_column(String, primary_key=True)
    fruit_id: Mapped[str] = mapped_column(ForeignKey("fruits.fruit_id"))
    variety: Mapped[str] = mapped_column(String)
    farm_id: Mapped[str] = mapped_column(ForeignKey("actors.actor_id"))
    origin_province: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    quantity_kg: Mapped[float] = mapped_column(Float)
    harvest_ts: Mapped[str] = mapped_column(String)
    certifications: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String)
    current_actor_id: Mapped[str] = mapped_column(ForeignKey("actors.actor_id"))
    metadata_hash: Mapped[str] = mapped_column(String)
    qr_payload: Mapped[str] = mapped_column(String)
    demo_note: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (UniqueConstraint("batch_id", "ts"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.batch_id"), index=True)
    ts: Mapped[str] = mapped_column(String)
    temp_c: Mapped[float] = mapped_column(Float)
    humidity_pct: Mapped[int] = mapped_column(Integer)
    ethylene_ppm: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    device_id: Mapped[str] = mapped_column(String)
    device_sig: Mapped[str] = mapped_column(String)


class RulPoint(Base):
    __tablename__ = "rul_points"
    batch_id: Mapped[str] = mapped_column(String, primary_key=True)
    ts: Mapped[str] = mapped_column(String, primary_key=True)
    temp_c: Mapped[float] = mapped_column(Float)
    effective_hours: Mapped[float] = mapped_column(Float)
    fraction_used: Mapped[float] = mapped_column(Float)
    rul_at_current: Mapped[float] = mapped_column(Float)
    rul_at_optimal: Mapped[float] = mapped_column(Float)
    ci_low: Mapped[float] = mapped_column(Float)
    ci_high: Mapped[float] = mapped_column(Float)
    freshness: Mapped[str] = mapped_column(String)


class LedgerEvent(Base):
    __tablename__ = "ledger_events"
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String, index=True)
    type: Mapped[str] = mapped_column(String)
    ts: Mapped[str] = mapped_column(String)
    actor_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    to_actor_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    data_hash: Mapped[str] = mapped_column(String)
    payload: Mapped[Any] = mapped_column(JSON)
    rul_snapshot: Mapped[Any] = mapped_column(JSON)
    prev_hash: Mapped[str] = mapped_column(String)
    event_hash: Mapped[str] = mapped_column(String)
    block_number: Mapped[int] = mapped_column(Integer, index=True)
    tx_hash: Mapped[str] = mapped_column(String)


class Alert(Base):
    __tablename__ = "alerts"
    alert_id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String, index=True)
    type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    ts: Mapped[str] = mapped_column(String)
    related_event_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[str] = mapped_column(String)


class Inspection(Base):
    __tablename__ = "inspections"
    inspection_id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.batch_id"), index=True)
    ts: Mapped[str] = mapped_column(String)
    raw_image_path: Mapped[str] = mapped_column(String)
    image_hash: Mapped[str] = mapped_column(String)
    preprocessed_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rul_image_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rul_sensor_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rul_final_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ci_low: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ci_high: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    freshness_label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    model_version: Mapped[str] = mapped_column(String)
    model_hash: Mapped[str] = mapped_column(String)
    event_id: Mapped[Optional[str]] = mapped_column(ForeignKey("ledger_events.event_id"), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

"""Interface chung cho mọi model RUL (mục 5.1). Q10 và model của bạn đều đi qua đây."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass
class RulInput:
    batch_id: str
    fruit_id: str
    readings: Optional[list] = None      # chuỗi cảm biến (dict có tempC, humidityPct, ts...)
    image_path: Optional[str] = None     # ảnh ĐÃ tiền xử lý


@dataclass
class RulOutput:
    rul_days: float
    ci_low_days: Optional[float] = None
    ci_high_days: Optional[float] = None
    freshness: Optional[str] = None      # FRESH | GOOD | NEAR_EXPIRY | EXPIRED
    extra: dict = field(default_factory=dict)


class RulModel(Protocol):
    name: str
    version: str
    uses_images: bool
    uses_readings: bool

    def model_hash(self) -> str: ...
    def predict(self, x: RulInput) -> RulOutput: ...


def freshness_from_fraction(frac: float) -> str:
    if frac >= 1:
        return "EXPIRED"
    if frac >= 0.8:
        return "NEAR_EXPIRY"
    if frac >= 0.5:
        return "GOOD"
    return "FRESH"


def freshness_from_rul(rul_days: float, shelf_ref_days: float) -> str:
    """Suy ra nhãn độ tươi từ RUL (khi model chỉ trả số ngày)."""
    if shelf_ref_days <= 0:
        return "GOOD"
    frac = 1.0 - max(0.0, rul_days) / shelf_ref_days
    return freshness_from_fraction(max(0.0, frac))

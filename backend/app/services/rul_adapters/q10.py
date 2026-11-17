"""Baseline Q10 (mục 5) — dùng cho chuỗi cảm biến, mặc định."""
from __future__ import annotations

from typing import Any, Iterable

from ..hashing import canonical_json, sha
from .base import RulInput, RulOutput, freshness_from_fraction

VERSION = "rul-q10-v0.1"


def _params(fruit: Any) -> tuple[float, float, float]:
    if isinstance(fruit, dict):
        return float(fruit["shelfRefDays"]), float(fruit["refTempC"]), float(fruit["q10"])
    return float(fruit.shelf_ref_days), float(fruit.ref_temp_c), float(fruit.q10)


def rate(fruit: Any, temp_c: float) -> float:
    _shelf, ref, q10 = _params(fruit)
    return q10 ** ((float(temp_c) - ref) / 10.0)


def point(fruit: Any, consumed: float, temp_c: float) -> dict:
    shelf, _ref, _q = _params(fruit)
    frac = consumed / (shelf * 24)
    remaining_ref = max(0.0, shelf - consumed / 24)
    rul_current = remaining_ref / rate(fruit, temp_c)
    return dict(
        effectiveHoursConsumed=round(consumed, 4),
        fractionUsed=round(min(frac, 1.0), 4),
        rulDaysAtOptimal=round(remaining_ref, 2),
        rulDaysAtCurrent=round(rul_current, 2),
        ciLowDays=round(rul_current * 0.85, 2),   # demo: ±15%, giả định
        ciHighDays=round(rul_current * 1.15, 2),
        freshness=freshness_from_fraction(frac),
    )


def compute_series(fruit: Any, temps: Iterable[float]) -> list[dict]:
    """temps: nhiệt độ theo giờ; reading đầu = 0 giờ tiêu thụ."""
    consumed = 0.0
    out = []
    for i, t in enumerate(temps):
        if i > 0:
            consumed += rate(fruit, t)
        out.append(point(fruit, consumed, t))
    return out


def next_point(fruit: Any, prev_consumed: float | None, temp_c: float) -> dict:
    """Tính tiếp 1 giờ (dùng khi ingest), prev_consumed=None nghĩa là reading đầu tiên."""
    consumed = 0.0 if prev_consumed is None else prev_consumed + rate(fruit, temp_c)
    return point(fruit, consumed, temp_c)


def q10_model_hash(fruits_raw: list[dict]) -> str:
    return sha(canonical_json({f["fruitId"]: f for f in fruits_raw}))


class Q10Model:
    name = "q10"
    version = VERSION
    uses_images = False
    uses_readings = True

    def __init__(self, fruits: dict[str, Any], fruits_raw: list[dict]):
        self.fruits = fruits
        self._hash = q10_model_hash(fruits_raw)

    def model_hash(self) -> str:
        return self._hash

    def predict(self, x: RulInput) -> RulOutput:
        fruit = self.fruits[x.fruit_id]
        temps = [r["tempC"] for r in (x.readings or [])]
        if not temps:
            shelf, _r, _q = _params(fruit)
            return RulOutput(rul_days=shelf, ci_low_days=shelf * 0.85, ci_high_days=shelf * 1.15, freshness="FRESH")
        last = compute_series(fruit, temps)[-1]
        return RulOutput(rul_days=last["rulDaysAtCurrent"], ci_low_days=last["ciLowDays"],
                         ci_high_days=last["ciHighDays"], freshness=last["freshness"], extra=last)

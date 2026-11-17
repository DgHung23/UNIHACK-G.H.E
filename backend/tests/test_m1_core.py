"""M1: T-SEED, T-RUL, T-RULNOW, T-HASH, T-VIOL."""
import csv
import json

from conftest import DEMO, auth

from app.db import SessionLocal
from app.models import Fruit, SensorReading
from app.services.alerts import detect_runs
from app.services.hashing import ZERO_HASH, event_hash
from app.services.rul import compute_series, q10_model_hash
from app.seed import self_check


def _csv(name):
    with open(DEMO / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_seed_counts(client, fresh):
    fresh()
    with SessionLocal() as db:
        c = self_check(db)
    assert c == {"batches": 6, "sensor_readings": 714, "ledger_events": 29, "alerts": 5, "actors": 12, "users": 12}


def test_rul_reproduces_timeseries(client):
    """T-RUL: tính lại từ sensor_readings.csv khớp rul_timeseries.csv (±0.01).
    Lưu ý: lô 006 có 6 reading bị sửa có chủ đích trong sensor_readings.csv, còn rul_timeseries.csv
    giữ nhiệt độ gốc — nên với 006 ta tính lại từ cột tempC gốc của rul_timeseries."""
    fruits = {f["fruitId"]: f for f in json.loads((DEMO / "fruits.json").read_text(encoding="utf-8"))}
    batches = {b["batchId"]: b["fruitId"] for b in json.loads((DEMO / "batches.json").read_text(encoding="utf-8"))}
    sensor, expected = {}, {}
    for r in _csv("sensor_readings.csv"):
        sensor.setdefault(r["batchId"], []).append(float(r["tempC"]))
    for r in _csv("rul_timeseries.csv"):
        expected.setdefault(r["batchId"], []).append(r)
    for bid, exp in expected.items():
        temps = sensor[bid] if bid != "FC-2026-006" else [float(r["tempC"]) for r in exp]
        got = compute_series(fruits[batches[bid]], temps)
        assert len(got) == len(exp)
        for g, e in zip(got, exp):
            for k in ("rulDaysAtCurrent", "rulDaysAtOptimal", "ciLowDays", "ciHighDays", "fractionUsed"):
                assert abs(g[k] - float(e[k])) <= 0.01, (bid, e["ts"], k)
            assert g["freshness"] == e["freshness"]


def test_rul_now(client):
    exp = {"FC-2026-001": 7.80, "FC-2026-002": 5.47, "FC-2026-003": 4.94, "FC-2026-004": 1.22,
           "FC-2026-005": 5.55, "FC-2026-006": 3.22}
    r = client.get("/api/batches", headers=auth(client, "admin"))
    got = {b["batchId"]: b["latestRul"]["rulDaysAtCurrent"] for b in r.json()}
    for k, v in exp.items():
        assert abs(got[k] - v) <= 0.01, k


def test_event_hashes_and_links(client):
    ledger = json.loads((DEMO / "events_ledger.json").read_text(encoding="utf-8"))
    prev = {}
    ok = 0
    for e in sorted(ledger["events"], key=lambda e: e["blockNumber"]):
        assert e["prevHash"] == prev.get(e["batchId"], ZERO_HASH)
        assert event_hash(e) == e["eventHash"]
        prev[e["batchId"]] = e["eventHash"]
        ok += 1
    assert ok == 29
    # và qua API (dữ liệu đã nạp vào DB)
    r = client.get("/api/ledger/events", headers=auth(client, "admin")).json()
    assert r["count"] == 29 and all(e["prevOk"] and e["hashOk"] for e in r["events"])


def test_q10_model_hash_matches_demo(client):
    with SessionLocal() as db:
        raw = [f.raw for f in db.query(Fruit).all()]
    mv = json.loads((DEMO / "model_versions.json").read_text(encoding="utf-8"))[0]
    assert q10_model_hash(raw) == mv["modelHash"]


def test_violation_detection_original_data(client):
    """T-VIOL: dữ liệu gốc (nhiệt độ gốc nằm trong rul_timeseries.csv)."""
    fruits = {f["fruitId"]: f for f in json.loads((DEMO / "fruits.json").read_text(encoding="utf-8"))}
    batches = {b["batchId"]: b for b in json.loads((DEMO / "batches.json").read_text(encoding="utf-8"))}
    events = json.loads((DEMO / "events_ledger.json").read_text(encoding="utf-8"))["events"]
    first_handoff = {}
    for e in sorted(events, key=lambda e: e["blockNumber"]):
        if e["type"] == "HANDOFF" and e["batchId"] not in first_handoff:
            first_handoff[e["batchId"]] = e["ts"]
    rows = {}
    for r in _csv("rul_timeseries.csv"):
        rows.setdefault(r["batchId"], []).append({"ts": r["ts"], "tempC": float(r["tempC"])})
    found = {}
    for bid, rs in rows.items():
        fr = fruits[batches[bid]["fruitId"]]
        runs = detect_runs(rs, fr["alertTempC"], skip=lambda r, b=bid: r["ts"] < first_handoff[b])
        for run, ongoing in runs:
            found[bid] = (len(run), max(x["tempC"] for x in run), ongoing)
    assert found == {"FC-2026-003": (6, 25.3, False), "FC-2026-004": (18, 12.8, True),
                     "FC-2026-006": (6, 26.5, False)}


def test_db_readings_match_csv(client):
    n = sum(1 for r in _csv("sensor_readings.csv") if r["batchId"] == "FC-2026-006")
    with SessionLocal() as db:
        assert db.query(SensorReading).filter(SensorReading.batch_id == "FC-2026-006").count() == n

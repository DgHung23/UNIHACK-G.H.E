"""M2: T-VERIFY-*, T-INGEST-*, T-HANDOFF, T-CLOSED, T-RBAC, T-PUBLIC, T-APPEND."""
import json

import pytest
from conftest import DEMO, auth
from sqlalchemy import text

from app.db import SessionLocal, engine
from app.models import SensorReading
from app.services.hashing import canonical_reading, canonical_reading_row, device_sig, segment_hash


@pytest.fixture(autouse=True, scope="module")
def _seed(fresh):
    fresh()


def test_verify_pass_001_005(client):
    for i in range(1, 6):
        r = client.post(f"/api/batches/FC-2026-00{i}/verify", headers=auth(client, "auditor")).json()
        assert r["overall"] == "PASS" and r["signatureFailureCount"] == 0, r


def test_verify_fail_006(client):
    r = client.post("/api/batches/FC-2026-006/verify", headers=auth(client, "auditor")).json()
    assert r["overall"] == "FAIL"
    bad = {s["eventId"] for s in r["segments"] if not s["match"]}
    assert bad == {"EV-006-03", "EV-006-04"}
    assert r["signatureFailureCount"] == 6


def test_verify_matches_expected(client):
    exp = json.loads((DEMO / "expected_verification.json").read_text(encoding="utf-8"))
    for e in exp:
        r = client.post(f"/api/batches/{e['batchId']}/verify", headers=auth(client, "admin")).json()
        assert {k: r[k] for k in e} == e


def test_unauthenticated_401(client):
    assert client.get("/api/batches").status_code == 401


def _reading(bid, ts, temp, hum=88, eth=4.0, lat=10.7, lon=106.7, dev=None, sig=None):
    dev = dev or f"TAG-{bid[-3:]}"
    canon = canonical_reading(bid, ts, temp, hum, eth, lat, lon)
    return dict(batchId=bid, ts=ts, tempC=temp, humidityPct=hum, ethylenePpm=eth, lat=lat, lon=lon,
                deviceSig=sig or device_sig(dev, canon))


def test_ingest_bad_signature_422(client):
    with SessionLocal() as db:
        before = db.query(SensorReading).count()
    r = client.post("/api/ingest/readings", headers={"X-Device-Id": "TAG-002"},
                    json={"readings": [_reading("FC-2026-002", "2026-11-17T06:00:00Z", 14.5, sig="0" * 32)]})
    assert r.status_code == 422
    with SessionLocal() as db:
        assert db.query(SensorReading).count() == before


def test_ingest_ok_and_violation(client):
    bid = "FC-2026-002"
    rul_before = client.get(f"/api/batches/{bid}", headers=auth(client, "admin")).json()["latestRul"]
    r = client.post("/api/ingest/readings", headers={"X-Device-Id": "TAG-002"},
                    json={"readings": [_reading(bid, "2026-11-17T06:00:00Z", 14.6)]})
    assert r.status_code == 200, r.text
    assert r.json()["rul"][0]["effectiveHoursConsumed"] > 0
    # 2 giờ liên tiếp > 18°C → VIOLATION + alert
    r = client.post("/api/ingest/readings", headers={"X-Device-Id": "TAG-002"},
                    json=[_reading(bid, "2026-11-17T07:00:00Z", 19.5), _reading(bid, "2026-11-17T08:00:00Z", 20.1)])
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["violations"]) == 1 and body["alerts"]
    rul_after = client.get(f"/api/batches/{bid}", headers=auth(client, "admin")).json()["latestRul"]
    assert rul_after["rulDaysAtOptimal"] < rul_before["rulDaysAtOptimal"]
    evs = client.get(f"/api/batches/{bid}/events", headers=auth(client, "admin")).json()
    v = [e for e in evs if e["type"] == "VIOLATION"][-1]
    assert v["payload"]["durationHours"] == 2 and v["payload"]["ongoing"] is True
    assert all(e["linkOk"] for e in evs)
    ver = client.post(f"/api/batches/{bid}/verify", headers=auth(client, "admin")).json()
    assert ver["overall"] == "PASS"


def test_handoff(client):
    bid = "FC-2026-001"
    evs = client.get(f"/api/batches/{bid}/events", headers=auth(client, "admin")).json()
    head = evs[-1]["eventHash"]
    # sai bên → 403
    r = client.post(f"/api/batches/{bid}/handoff", headers=auth(client, "store_q1"), json={"toActorId": "R002"})
    assert r.status_code == 403
    r = client.post(f"/api/batches/{bid}/handoff", headers=auth(client, "store_q7"), json={"toActorId": "R002"})
    assert r.status_code == 200, r.text
    ev = r.json()["event"]
    assert ev["prevHash"] == head
    p = ev["payload"]
    with SessionLocal() as db:
        rows = db.query(SensorReading).filter(SensorReading.batch_id == bid, SensorReading.ts >= p["fromReading"],
                                              SensorReading.ts <= p["toReading"]).order_by(SensorReading.ts).all()
        assert ev["dataHash"] == segment_hash(canonical_reading_row(x) for x in rows)
    assert r.json()["batch"]["currentActorId"] == "R002"
    assert client.post(f"/api/batches/{bid}/verify", headers=auth(client, "admin")).json()["overall"] == "PASS"


def test_closed_409(client):
    bid = "FC-2026-005"
    assert client.post(f"/api/batches/{bid}/handoff", headers=auth(client, "store_q7"),
                       json={"toActorId": "R002"}).status_code == 409
    assert client.post(f"/api/batches/{bid}/sold", headers=auth(client, "store_q7"), json={}).status_code == 409
    assert client.post(f"/api/batches/{bid}/handoff", headers=auth(client, "admin"),
                       json={"toActorId": "R002"}).status_code == 409


def test_rbac_create_batch(client):
    body = {"fruitId": "strawberry", "variety": "Dâu tây New Zealand", "quantityKg": 50, "certifications": ["VietGAP"]}
    r = client.post("/api/batches", headers=auth(client, "farm_dalat"), json={**body, "farmId": "F001"})
    assert r.status_code == 403
    r = client.post("/api/batches", headers=auth(client, "farm_dalat"), json={**body, "farmId": "F004"})
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["batchId"] == "FC-2026-007"
    evs = client.get(f"/api/batches/{b['batchId']}/events", headers=auth(client, "admin")).json()
    assert len(evs) == 1 and evs[0]["type"] == "HARVEST" and evs[0]["dataHash"] == b["metadataHash"]
    # tài khoản vận tải không được tạo lô
    assert client.post("/api/batches", headers=auth(client, "truck_dalat"),
                       json={**body, "farmId": "F004"}).status_code == 403


def test_public_trace(client):
    r = client.get("/api/public/trace/FC-2026-001")
    assert r.status_code == 200
    s = r.text
    for bad in ("deviceSig", "passwordHash", "password_hash", "demoPassword", "username"):
        assert bad not in s
    assert r.json()["verification"]["overall"] in ("PASS", "FAIL")
    assert client.get("/api/public/trace/FC-2026-006").json()["verification"]["overall"] == "FAIL"


def test_append_only(client):
    routes = [(m, r.path) for r in client.app.routes for m in getattr(r, "methods", []) or []]
    assert not any(p.startswith("/api/ledger") and m in ("PUT", "PATCH", "DELETE") for m, p in routes)
    with engine.connect() as conn:
        with pytest.raises(Exception):
            conn.execute(text("UPDATE ledger_events SET data_hash='x' WHERE event_id='EV-001-01'"))
        conn.rollback()
        with pytest.raises(Exception):
            conn.execute(text("DELETE FROM ledger_events"))
        conn.rollback()


def test_whatif_predict(client):
    r = client.post("/api/rul/predict", headers=auth(client, "admin"),
                    json={"fruitId": "mango", "readings": [{"tempC": 13}, {"tempC": 13}, {"tempC": 25}]})
    s = r.json()["series"]
    assert len(s) == 3 and s[0]["rulDaysAtOptimal"] == 14.0 and s[2]["rulDaysAtCurrent"] < s[1]["rulDaysAtCurrent"]


def test_alerts_and_ack(client):
    al = client.get("/api/alerts", headers=auth(client, "admin")).json()
    assert len(al) >= 5
    r = client.post(f"/api/alerts/{al[0]['alertId']}/ack", headers=auth(client, "admin"))
    assert r.json()["acknowledged"] is True


def test_simulate_tick(client):
    r = client.post("/api/admin/simulate/tick", headers=auth(client, "admin"))
    assert r.status_code == 200 and r.json()["batches"]
    assert client.post("/api/admin/simulate/tick", headers=auth(client, "store_q7")).status_code == 403

#!/usr/bin/env python3
"""
FruitChain - sinh du lieu demo (deterministic, seed co dinh).

Chay:  python3 tools/generate_demo_data.py demo_data
Ket qua: actors, users, fruits, model_versions, batches, sensor_readings.csv,
         rul_timeseries.csv, events_ledger.json, alerts.json, expected_verification.json
"""
import csv
import hashlib
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "demo_data")
OUT.mkdir(parents=True, exist_ok=True)
random.seed(20261117)

NOW = datetime(2026, 11, 17, 6, 0, 0, tzinfo=timezone.utc)  # 13:00 gio VN
DEVICE_KEY = "demo-device-key"  # CHI DUNG CHO DEMO
MODEL_VERSION = "rul-q10-v0.1"


def utc(y, m, d, h=0):
    return datetime(y, m, d, h, 0, 0, tzinfo=timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def canon_json(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def clip(x, a, b):
    return max(a, min(b, x))


# ---------------------------------------------------------------- tham so qua
FRUITS = {
    "banana": dict(fruitId="banana", nameVi="Chuối Cavendish", shelfRefDays=10, refTempC=14.0, q10=2.3,
                   optimalTempMinC=13.0, optimalTempMaxC=15.0, alertTempC=18.0, optimalHumidityPct=90),
    "mango": dict(fruitId="mango", nameVi="Xoài cát Hòa Lộc", shelfRefDays=14, refTempC=13.0, q10=2.5,
                  optimalTempMinC=12.0, optimalTempMaxC=14.0, alertTempC=17.0, optimalHumidityPct=88),
    "dragonfruit": dict(fruitId="dragonfruit", nameVi="Thanh long ruột đỏ", shelfRefDays=14, refTempC=10.0, q10=2.2,
                        optimalTempMinC=8.0, optimalTempMaxC=12.0, alertTempC=15.0, optimalHumidityPct=85),
    "strawberry": dict(fruitId="strawberry", nameVi="Dâu tây Đà Lạt", shelfRefDays=7, refTempC=2.0, q10=3.0,
                       optimalTempMinC=0.0, optimalTempMaxC=4.0, alertTempC=8.0, optimalHumidityPct=90),
}
MODEL_HASH = sha(canon_json(FRUITS))


def rate(fr, temp):
    return fr["q10"] ** ((temp - fr["refTempC"]) / 10.0)


# ---------------------------------------------------------------- doi tuong
LOC = {
    "F001": (10.4600, 105.6330), "F002": (10.4500, 106.4000), "F003": (10.8500, 107.9000), "F004": (11.9404, 108.4583),
    "W001": (10.0452, 105.7469), "W002": (10.8010, 106.6520),
    "D001": (10.6740, 106.5700), "R001": (10.7340, 106.7220), "R002": (10.7769, 106.7009),
}

ACTORS = [
    dict(actorId="F001", name="HTX Xoài Cao Lãnh", role="FARMER", province="Đồng Tháp"),
    dict(actorId="F002", name="Hợp tác xã Chuối Châu Thành", role="FARMER", province="Long An"),
    dict(actorId="F003", name="Nông trại Thanh long Hàm Thuận Nam", role="FARMER", province="Bình Thuận"),
    dict(actorId="F004", name="Trang trại Dâu tây Đà Lạt Xanh", role="FARMER", province="Lâm Đồng"),
    dict(actorId="W001", name="Kho lạnh Cần Thơ", role="WAREHOUSE", province="Cần Thơ"),
    dict(actorId="W002", name="Kho lạnh Tân Bình", role="WAREHOUSE", province="TP.HCM"),
    dict(actorId="T001", name="Vận tải lạnh Mekong (xe 51C-123.45)", role="TRANSPORT", province="TP.HCM"),
    dict(actorId="T002", name="Đà Lạt Express Cold Chain (xe 49C-678.90)", role="TRANSPORT", province="Lâm Đồng"),
    dict(actorId="D001", name="Trung tâm phân phối Bình Chánh", role="DISTRIBUTOR", province="TP.HCM"),
    dict(actorId="R001", name="Siêu thị FreshMart Quận 7", role="RETAILER", province="TP.HCM"),
    dict(actorId="R002", name="Siêu thị GreenMart Quận 1", role="RETAILER", province="TP.HCM"),
    dict(actorId="A001", name="Chi cục Quản lý chất lượng NLTS (demo)", role="REGULATOR", province="TP.HCM"),
]
for a in ACTORS:
    loc = LOC.get(a["actorId"])
    a["lat"], a["lon"] = (loc if loc else (None, None))

USERS = [
    ("admin", "ADMIN", None), ("farm_caolanh", "FARMER", "F001"), ("farm_longan", "FARMER", "F002"),
    ("farm_binhthuan", "FARMER", "F003"), ("farm_dalat", "FARMER", "F004"), ("cold_cantho", "WAREHOUSE", "W001"),
    ("truck_mekong", "TRANSPORT", "T001"), ("truck_dalat", "TRANSPORT", "T002"),
    ("dc_binhchanh", "DISTRIBUTOR", "D001"), ("store_q7", "RETAILER", "R001"), ("store_q1", "RETAILER", "R002"),
    ("auditor", "REGULATOR", "A001"),
]
USERS = [dict(username=u, role=r, actorId=a, demoPassword="demo1234") for u, r, a in USERS]


# ---------------------------------------------------------------- kich ban lo
def leg(kind, actor, hours, temp, sd, hum, eth, label, frm=None, to=None, anomaly=None):
    return dict(kind=kind, actor=actor, hours=hours, temp=temp, sd=sd, hum=hum, eth=eth,
                label=label, frm=frm, to=to, anomaly=anomaly)


BATCHES = [
    dict(batchId="FC-2026-001", fruit="mango", variety="Xoài cát Hòa Lộc", farm="F001", province="Đồng Tháp", qty=500,
         harvest=utc(2026, 11, 12, 0), end=NOW, status="IN_STORE", certs=["VietGAP"],
         note="Chuỗi lạnh tốt, không vi phạm.",
         legs=[leg("farm", "F001", 6, 29, 1.0, 70, 1.5, "Thu hoạch & sơ chế"),
               leg("warehouse", "W001", 24, 13, 0.4, 90, 2.0, "Kho lạnh Cần Thơ"),
               leg("transport", "T001", 12, 13.5, 0.6, 88, 2.0, "Vận chuyển lạnh", frm="W001", to="D001"),
               leg("distributor", "D001", 24, 13, 0.5, 88, 2.0, "Trung tâm phân phối"),
               leg("retailer", "R001", None, 14, 0.8, 85, 2.5, "Bày bán tại cửa hàng")]),
    dict(batchId="FC-2026-002", fruit="banana", variety="Chuối Cavendish", farm="F002", province="Long An", qty=800,
         harvest=utc(2026, 11, 13, 0), end=NOW, status="IN_TRANSIT", certs=["GlobalGAP"],
         note="Đang vận chuyển đến cửa hàng, chuỗi lạnh tốt.",
         legs=[leg("farm", "F002", 4, 28, 1.0, 80, 3.0, "Thu hoạch & sơ chế"),
               leg("transport", "T001", 16, 14.5, 0.5, 88, 4.0, "Vận chuyển lạnh", frm="F002", to="D001"),
               leg("distributor", "D001", 64, 14, 0.5, 90, 8.0, "Trung tâm phân phối (ủ chín nhẹ)"),
               leg("transport", "T001", None, 14.5, 0.6, 88, 6.0, "Vận chuyển đến cửa hàng", frm="D001", to="R001")]),
    dict(batchId="FC-2026-003", fruit="dragonfruit", variety="Thanh long ruột đỏ", farm="F003", province="Bình Thuận",
         qty=600, harvest=utc(2026, 11, 10, 0), end=NOW, status="IN_STORE", certs=["VietGAP"],
         note="Sự cố lạnh xe T001: nhiệt độ ~24.5C trong 6 giờ -> cảnh báo vi phạm.",
         legs=[leg("farm", "F003", 6, 30, 1.0, 70, 0.5, "Thu hoạch & sơ chế"),
               leg("transport", "T001", 12, 10, 0.6, 85, 0.8, "Vận chuyển lạnh", frm="F003", to="D001",
                   anomaly=(2, 8, 24.5, 1.0)),
               leg("distributor", "D001", 54, 10, 0.5, 85, 0.8, "Trung tâm phân phối"),
               leg("retailer", "R002", None, 10.5, 0.8, 85, 0.8, "Bày bán tại cửa hàng")]),
    dict(batchId="FC-2026-004", fruit="strawberry", variety="Dâu tây Đà Lạt", farm="F004", province="Lâm Đồng", qty=120,
         harvest=utc(2026, 11, 16, 0), end=NOW, status="IN_STORE", certs=["VietGAP", "Hữu cơ"],
         note="Tủ trưng bày ~12C (quá ấm) -> RUL thấp, cảnh báo.",
         legs=[leg("farm", "F004", 3, 18, 1.5, 85, 0.3, "Thu hoạch & sơ chế"),
               leg("transport", "T002", 9, 4, 0.5, 90, 0.3, "Vận chuyển lạnh", frm="F004", to="R002"),
               leg("retailer", "R002", None, 12, 0.8, 80, 0.4, "Bày bán tại cửa hàng (tủ trưng bày hỏng)")]),
    dict(batchId="FC-2026-005", fruit="mango", variety="Xoài cát Hòa Lộc", farm="F001", province="Đồng Tháp", qty=450,
         harvest=utc(2026, 11, 5, 0), end=utc(2026, 11, 11, 12), status="SOLD", certs=["VietGAP"],
         note="Lô đã bán xong (vòng đời hoàn tất).",
         legs=[leg("farm", "F001", 6, 29, 1.0, 70, 1.5, "Thu hoạch & sơ chế"),
               leg("warehouse", "W001", 24, 13, 0.4, 90, 2.0, "Kho lạnh Cần Thơ"),
               leg("transport", "T001", 12, 13.5, 0.6, 88, 2.0, "Vận chuyển lạnh", frm="W001", to="D001"),
               leg("distributor", "D001", 48, 13, 0.5, 88, 2.0, "Trung tâm phân phối"),
               leg("retailer", "R001", None, 14.5, 0.8, 85, 2.5, "Bày bán tại cửa hàng")]),
    dict(batchId="FC-2026-006", fruit="banana", variety="Chuối Cavendish", farm="F002", province="Long An", qty=700,
         harvest=utc(2026, 11, 12, 0), end=NOW, status="IN_STORE", certs=["GlobalGAP"], tamper=True,
         note="TAMPER DEMO: sự cố nhiệt thật (25C, 6h) bị sửa trong sensor_readings.csv -> Verify phải báo FAIL.",
         legs=[leg("farm", "F002", 4, 28, 1.0, 80, 3.0, "Thu hoạch & sơ chế"),
               leg("transport", "T001", 16, 14.5, 0.5, 88, 4.0, "Vận chuyển lạnh", frm="F002", to="D001",
                   anomaly=(4, 10, 25.0, 0.8)),
               leg("distributor", "D001", 48, 14, 0.5, 90, 8.0, "Trung tâm phân phối"),
               leg("retailer", "R002", None, 14.5, 0.8, 88, 7.0, "Bày bán tại cửa hàng")]),
]


# ---------------------------------------------------------------- tien ich
def position(l, h):
    if l["kind"] == "transport":
        a, b = LOC[l["frm"]], LOC[l["to"]]
        f = (h + 1) / l["hours"]
        return round(a[0] + (b[0] - a[0]) * f, 4), round(a[1] + (b[1] - a[1]) * f, 4)
    p = LOC[l["actor"]]
    return round(p[0], 4), round(p[1], 4)


def canon_reading(batch_id, ts, temp, hum, eth, lat, lon):
    return f"{batch_id}|{ts}|{temp:.1f}|{hum:d}|{eth:.1f}|{lat:.4f}|{lon:.4f}"


def sign(device_id, canon):
    return sha(f"{device_id}|{canon}|{DEVICE_KEY}")[:32]


def seg_hash(canons):
    return sha("\n".join(canons))


def freshness(frac):
    if frac >= 1:
        return "EXPIRED"
    if frac >= 0.8:
        return "NEAR_EXPIRY"
    if frac >= 0.5:
        return "GOOD"
    return "FRESH"


def build_batch(b):
    fr = FRUITS[b["fruit"]]
    t0 = b["harvest"]
    n = int((b["end"] - t0).total_seconds() // 3600)
    fixed = sum(l["hours"] for l in b["legs"] if l["hours"] is not None)
    for l in b["legs"]:
        if l["hours"] is None:
            l["hours"] = n - fixed
    assert sum(l["hours"] for l in b["legs"]) == n, b["batchId"]

    device = "TAG-" + b["batchId"][-3:]
    readings, ranges, idx, consumed = [], [], 0, 0.0
    for li, l in enumerate(b["legs"]):
        start = idx
        for h in range(l["hours"]):
            ts = iso(t0 + timedelta(hours=idx))
            mean, sd = l["temp"], l["sd"]
            if l["anomaly"] and l["anomaly"][0] <= h < l["anomaly"][1]:
                mean, sd = l["anomaly"][2], l["anomaly"][3]
            temp = round(random.gauss(mean, sd), 1)
            hum = int(round(clip(random.gauss(l["hum"], 3), 40, 99)))
            eth = round(max(0.0, random.gauss(l["eth"], l["eth"] * 0.15 + 0.1)), 1)
            lat, lon = position(l, h)
            if idx > 0:
                consumed += rate(fr, temp)
            frac = consumed / (fr["shelfRefDays"] * 24.0)
            remaining_ref = max(0.0, fr["shelfRefDays"] - consumed / 24.0)
            rul_cur = remaining_ref / rate(fr, temp)
            canon = canon_reading(b["batchId"], ts, temp, hum, eth, lat, lon)
            readings.append(dict(
                idx=idx, leg=li, kind=l["kind"], ts=ts, temp=temp, hum=hum, eth=eth, lat=lat, lon=lon,
                device=device, canon=canon, sig=sign(device, canon),
                consumed=round(consumed, 4), frac=round(min(frac, 1.0), 4),
                rulCur=round(rul_cur, 2), rulOpt=round(remaining_ref, 2),
                ciLow=round(rul_cur * 0.85, 2), ciHigh=round(rul_cur * 1.15, 2), fresh=freshness(frac)))
            idx += 1
        ranges.append((start, idx))
    return readings, ranges


def snapshot(r):
    return dict(rulDaysAtCurrent=r["rulCur"], rulDaysAtOptimal=r["rulOpt"], ciLowDays=r["ciLow"],
                ciHighDays=r["ciHigh"], freshness=r["fresh"], tempC=r["temp"], modelVersion=MODEL_VERSION,
                modelHash=MODEL_HASH)


PRIO = {"HARVEST": 0, "VIOLATION": 1, "HANDOFF": 2, "SOLD": 3}

all_readings, all_events, batch_out, tamper_info = {}, [], [], {}
for b in BATCHES:
    fr = FRUITS[b["fruit"]]
    readings, ranges = build_batch(b)
    all_readings[b["batchId"]] = readings
    meta = dict(batchId=b["batchId"], fruitId=b["fruit"], variety=b["variety"], farmId=b["farm"],
                quantityKg=b["qty"], harvestTs=iso(b["harvest"]), certifications=b["certs"])
    meta_hash = sha(canon_json(meta))

    ev = []
    ev.append(dict(batchId=b["batchId"], type="HARVEST", ts=iso(b["harvest"]), actorId=b["farm"], toActorId=None,
                   lat=readings[0]["lat"], lon=readings[0]["lon"], dataHash=meta_hash,
                   payload=dict(quantityKg=b["qty"], variety=b["variety"], certifications=b["certs"]),
                   rulSnapshot=snapshot(readings[0])))
    for li in range(len(b["legs"]) - 1):
        s, e = ranges[li]
        l, nxt = b["legs"][li], b["legs"][li + 1]
        last = readings[e - 1]
        ev.append(dict(batchId=b["batchId"], type="HANDOFF", ts=readings[e]["ts"], actorId=l["actor"],
                       toActorId=nxt["actor"], lat=last["lat"], lon=last["lon"],
                       dataHash=seg_hash([r["canon"] for r in readings[s:e]]),
                       payload=dict(legIndex=li, legLabel=l["label"], fromReading=readings[s]["ts"],
                                    toReading=last["ts"], readingCount=e - s),
                       rulSnapshot=snapshot(last)))
    # vi pham chuoi lanh (bo qua giai doan 'farm' = lam mat ban dau)
    run = []
    def flush(run, ongoing):
        if len(run) >= 2:
            ev.append(dict(batchId=b["batchId"], type="VIOLATION", ts=run[-1]["ts"], actorId=b["legs"][run[0]["leg"]]["actor"],
                           toActorId=None, lat=run[-1]["lat"], lon=run[-1]["lon"],
                           dataHash=seg_hash([r["canon"] for r in run]),
                           payload=dict(violationType="TEMP_EXCURSION", thresholdC=fr["alertTempC"],
                                        startTs=run[0]["ts"], endTs=run[-1]["ts"], durationHours=len(run),
                                        maxTempC=max(r["temp"] for r in run), ongoing=ongoing),
                           rulSnapshot=snapshot(run[-1])))
    for r in readings:
        if r["kind"] != "farm" and r["temp"] > fr["alertTempC"]:
            run.append(r)
        else:
            flush(run, False)
            run = []
    flush(run, True)
    if b["status"] == "SOLD":
        last = readings[-1]
        ev.append(dict(batchId=b["batchId"], type="SOLD", ts=iso(b["end"]), actorId=b["legs"][-1]["actor"], toActorId=None,
                       lat=last["lat"], lon=last["lon"],
                       dataHash=sha(canon_json(dict(batchId=b["batchId"], soldTs=iso(b["end"]), quantityKg=b["qty"]))),
                       payload=dict(quantityKg=b["qty"]), rulSnapshot=snapshot(last)))
    all_events.extend(ev)

    last = readings[-1]
    batch_out.append(dict(
        batchId=b["batchId"], fruitId=b["fruit"], productName=fr["nameVi"], variety=b["variety"], farmId=b["farm"],
        originProvince=b["province"], quantityKg=b["qty"], harvestTs=iso(b["harvest"]), certifications=b["certs"],
        status=b["status"], currentActorId=b["legs"][-1]["actor"], currentLat=last["lat"], currentLon=last["lon"],
        latestRul=dict(ts=last["ts"], rulDaysAtCurrent=last["rulCur"], rulDaysAtOptimal=last["rulOpt"],
                       ciLowDays=last["ciLow"], ciHighDays=last["ciHigh"], freshness=last["fresh"],
                       fractionUsed=last["frac"]),
        metadataHash=meta_hash, qrPayload=f"https://fruitchain.demo/trace/{b['batchId']}",
        demoNote=b["note"]))
    if b.get("tamper"):
        s, e = ranges[1]
        a0, a1 = b["legs"][1]["anomaly"][:2]
        tamper_info[b["batchId"]] = [s + a0, s + a1]  # chi so reading bi sua

# ---------------------------------------------------------------- ledger gia lap
all_events.sort(key=lambda e: (e["ts"], PRIO[e["type"]], e["batchId"]))
prev, seq = {}, {}
for i, e in enumerate(all_events):
    bid = e["batchId"]
    seq[bid] = seq.get(bid, 0) + 1
    e["eventId"] = f"EV-{bid[-3:]}-{seq[bid]:02d}"
    e["prevHash"] = prev.get(bid, "0" * 64)
    core = {k: v for k, v in e.items()}
    e["eventHash"] = sha(canon_json(core))
    e["blockNumber"] = 1000001 + i
    e["txHash"] = "0x" + sha(e["eventHash"] + str(e["blockNumber"]))
    prev[bid] = e["eventHash"]

# ---------------------------------------------------------------- ghi CSV (kem tamper)
rng2 = random.Random(7)
tamper_rows = set()
for bid, (a, b_) in tamper_info.items():
    for i in range(a, b_):
        tamper_rows.add((bid, i))

with open(OUT / "sensor_readings.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["batchId", "ts", "tempC", "humidityPct", "ethylenePpm", "lat", "lon", "deviceId", "deviceSig"])
    for bid, rs in all_readings.items():
        for r in rs:
            temp = r["temp"]
            if (bid, r["idx"]) in tamper_rows:
                temp = round(14.5 + rng2.gauss(0, 0.4), 1)  # gian lan: che sự cố nhiệt
            w.writerow([bid, r["ts"], f"{temp:.1f}", r["hum"], f"{r['eth']:.1f}", f"{r['lat']:.4f}",
                        f"{r['lon']:.4f}", r["device"], r["sig"]])  # giu nguyen chu ky goc

with open(OUT / "rul_timeseries.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["batchId", "ts", "tempC", "effectiveHoursConsumed", "fractionUsed", "rulDaysAtCurrent",
                "rulDaysAtOptimal", "ciLowDays", "ciHighDays", "freshness"])
    for bid, rs in all_readings.items():
        for r in rs:
            w.writerow([bid, r["ts"], f"{r['temp']:.1f}", r["consumed"], r["frac"], r["rulCur"], r["rulOpt"],
                        r["ciLow"], r["ciHigh"], r["fresh"]])

# ---------------------------------------------------------------- alerts
alerts, n = [], 0
for e in all_events:
    if e["type"] == "VIOLATION":
        n += 1
        p = e["payload"]
        alerts.append(dict(alertId=f"AL-{n:03d}", batchId=e["batchId"], type="COLD_CHAIN_VIOLATION", severity="HIGH",
                           ts=e["ts"], relatedEventId=e["eventId"], acknowledged=False,
                           message=f"Nhiệt độ vượt {p['thresholdC']}°C trong {p['durationHours']} giờ "
                                   f"(tối đa {p['maxTempC']}°C)" + (" - đang tiếp diễn" if p["ongoing"] else "")))
for b in batch_out:
    if b["status"] == "SOLD":
        continue
    r = b["latestRul"]
    sev = "HIGH" if r["rulDaysAtCurrent"] < 2 else ("MEDIUM" if r["rulDaysAtCurrent"] < 4 else None)
    if sev:
        n += 1
        alerts.append(dict(alertId=f"AL-{n:03d}", batchId=b["batchId"], type="LOW_RUL", severity=sev, ts=r["ts"],
                           relatedEventId=None, acknowledged=False,
                           message=f"RUL còn {r['rulDaysAtCurrent']} ngày ở điều kiện hiện tại"))

# ---------------------------------------------------------------- JSON tinh
def dump(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


dump("actors.json", ACTORS)
dump("users.json", USERS)
dump("fruits.json", list(FRUITS.values()))
dump("model_versions.json", [dict(version=MODEL_VERSION, modelHash=MODEL_HASH, registeredTs="2026-11-01T00:00:00Z",
                                  description="Mo hinh Q10 don gian (demo). Thay bang mo hinh ML that.",
                                  params=list(FRUITS.values()))])
dump("batches.json", batch_out)
dump("events_ledger.json", dict(chainId="mock-ledger", genesisHash="0" * 64, events=all_events))
dump("alerts.json", alerts)

# ---------------------------------------------------------------- expected verification (doc lai tu CSV)
rows = {}
with open(OUT / "sensor_readings.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        rows.setdefault(r["batchId"], []).append(r)


def csv_canon(r):
    return canon_reading(r["batchId"], r["ts"], float(r["tempC"]), int(r["humidityPct"]), float(r["ethylenePpm"]),
                         float(r["lat"]), float(r["lon"]))


expected = []
for b in batch_out:
    bid = b["batchId"]
    rs = rows[bid]
    by_ts = {r["ts"]: r for r in rs}
    sig_bad = [r["ts"] for r in rs if sign(r["deviceId"], csv_canon(r)) != r["deviceSig"]]
    segs = []
    for e in all_events:
        if e["batchId"] != bid or e["type"] not in ("HANDOFF", "VIOLATION"):
            continue
        if e["type"] == "HANDOFF":
            p = e["payload"]
            keys = sorted(t for t in by_ts if p["fromReading"] <= t <= p["toReading"])
        else:
            p = e["payload"]
            keys = sorted(t for t in by_ts if p["startTs"] <= t <= p["endTs"])
        recomputed = seg_hash([csv_canon(by_ts[t]) for t in keys])
        segs.append(dict(eventId=e["eventId"], type=e["type"], onChainDataHash=e["dataHash"],
                         recomputedHash=recomputed, match=recomputed == e["dataHash"]))
    ok = all(s["match"] for s in segs) and not sig_bad
    expected.append(dict(batchId=bid, chainLinkIntact=True, segments=segs, signatureFailureCount=len(sig_bad),
                         overall="PASS" if ok else "FAIL"))
dump("expected_verification.json", expected)

# ---------------------------------------------------------------- tom tat
print("Batches:", len(batch_out), "| readings:", sum(len(v) for v in all_readings.values()),
      "| events:", len(all_events), "| alerts:", len(alerts))
for b in batch_out:
    r = b["latestRul"]
    print(f"  {b['batchId']} {b['status']:<10} RULcur={r['rulDaysAtCurrent']:>6} RULopt={r['rulDaysAtOptimal']:>6} {r['freshness']}")
for e in all_events:
    if e["type"] == "VIOLATION":
        print("  VIOLATION", e["eventId"], e["payload"])
for x in expected:
    print("  verify", x["batchId"], x["overall"], "sigFail=", x["signatureFailureCount"])

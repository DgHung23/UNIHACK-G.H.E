# FruitChain — Đặc tả xây dựng phần mềm kiểm tra & quản lý vòng đời trái cây trên blockchain

> **Cách dùng file này:** đưa nguyên file (cùng thư mục `demo_data/` và `tools/`) cho lập trình viên hoặc AI coding agent (ví dụ Claude Code) với câu lệnh:
> *"Hãy xây dựng dự án theo `FRUITCHAIN_SPEC.md`, làm lần lượt từng Milestone ở mục 14, chạy các Acceptance Test ở mục 13 sau mỗi Milestone."*

---

## 1. Mục tiêu

Xây một hệ thống web gồm:

1. **Quản lý vòng đời lô trái cây** từ thu hoạch → kho lạnh → vận chuyển → phân phối → cửa hàng → bán.
2. **Dự đoán RUL** (Remaining Useful Life – số ngày còn dùng được) cho từng lô dựa trên dữ liệu cảm biến (nhiệt độ, độ ẩm, ethylene, GPS).
3. **Lưu bằng chứng trên blockchain**: mọi mốc quan trọng (thu hoạch, chuyển giao, vi phạm chuỗi lạnh, bán) được ghi dưới dạng **hash** vào một chuỗi sự kiện bất biến.
4. **Kiểm chứng toàn vẹn (Verify):** tính lại hash từ dữ liệu trong DB và đối chiếu với hash đã ghi để phát hiện dữ liệu bị sửa.
5. **Truy xuất nguồn gốc công khai** bằng QR: người tiêu dùng xem timeline và đường cong RUL mà không cần đăng nhập.

**Nguyên tắc thiết kế:** DB lưu dữ liệu đầy đủ (nhanh, truy vấn được); blockchain chỉ lưu *bằng chứng* (hash + mốc sự kiện + snapshot RUL).

**Đã có sẵn:** dự án đã có **mô hình dự đoán RUL** và **bước tiền xử lý ảnh**. Phần mềm này **không huấn luyện lại**; nó gắn các thành phần đó vào qua adapter (mục 5.1). Mô hình Q10 ở mục 5 chỉ là *baseline/fallback* để hệ thống chạy được ngay khi chưa gắn model thật và để làm dữ liệu demo.

**Ngoài phạm vi:** thanh toán, bảo hiểm tự động, phần cứng IoT thật, huấn luyện mô hình.

---

## 2. Kiến trúc & công nghệ

```
React (Vite, TS)  ──►  FastAPI (Python 3.11)  ──►  SQLite (demo) / PostgreSQL
 Recharts, Leaflet          │
                            ├── RUL service (module Python, mục 5)
                            ├── Verify service (mục 6)
                            └── Ledger adapter (interface chung)
                                   ├── MockLedger  : bảng ledger_events (append-only)  ← MẶC ĐỊNH
                                   └── EvmLedger   : web3.py → Hardhat node + FruitChain.sol (mục 7)
```

| Thành phần | Lựa chọn |
|---|---|
| Backend | FastAPI, SQLAlchemy 2.x, Pydantic v2, PyJWT, passlib(bcrypt), pytest |
| DB | SQLite file `fruitchain.db` (demo); schema tương thích PostgreSQL |
| Frontend | React 18 + Vite + TypeScript, React Router, TanStack Query, Recharts, Leaflet, TailwindCSS |
| Blockchain | Solidity ^0.8.24, Hardhat (mạng local `npx hardhat node`) |
| Chạy | `docker compose up` (tuỳ chọn) hoặc chạy tay từng phần (mục 12) |

**Ledger adapter** (interface bắt buộc, hai bản cài đặt hoán đổi bằng biến môi trường `LEDGER_MODE=mock|evm`):

```python
class Ledger(Protocol):
    def append(self, event: dict) -> dict: ...          # trả về {blockNumber, txHash}
    def get_events(self, batch_id: str) -> list[dict]: ...
    def get_head_hash(self, batch_id: str) -> str: ...  # eventHash mới nhất của lô, "0"*64 nếu chưa có
```

Chế độ `mock` là mặc định và phải chạy được hoàn toàn offline, không cần Hardhat.

---

## 3. Cấu trúc thư mục

```
fruitchain/
├── FRUITCHAIN_SPEC.md
├── demo_data/                 # dữ liệu demo (đã có sẵn, mục 4)
├── tools/generate_demo_data.py
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, CORS, router include
│   │   ├── config.py          # env: DATABASE_URL, JWT_SECRET, LEDGER_MODE, DEMO_DATA_DIR
│   │   ├── db.py, models.py, schemas.py
│   │   ├── auth.py            # JWT + RBAC dependency
│   │   ├── services/
│   │   │   ├── rul.py         # mục 5 (baseline Q10) + chọn adapter
│   │   │   ├── rul_adapters/{base,q10,custom}.py   # mục 5.1: custom = model có sẵn của bạn
│   │   │   ├── preprocess.py  # gọi lại ĐÚNG hàm preprocess ảnh có sẵn (mục 5.1)
│   │   │   ├── hashing.py     # mục 6
│   │   │   ├── verify.py
│   │   │   ├── alerts.py
│   │   │   └── ledger/{base.py, mock.py, evm.py}
│   │   ├── routers/{auth,batches,ingest,verify,public,alerts,admin,meta}.py
│   │   └── seed.py            # nạp demo_data (mục 10)
│   ├── storage/{raw,preprocessed}/   # ảnh gốc & ảnh đã tiền xử lý (không commit)
│   └── tests/                 # pytest cho mục 13
├── contracts/
│   ├── contracts/FruitChain.sol
│   ├── test/FruitChain.test.ts
│   └── hardhat.config.ts
└── frontend/src/{pages,components,api}/
```

---

## 4. Dữ liệu demo (`demo_data/`)

Sinh bằng `python3 tools/generate_demo_data.py demo_data` (deterministic, seed cố định — chạy lại ra đúng cùng kết quả). **Thời điểm "hiện tại" của demo là `2026-11-17T06:00:00Z`.** Tất cả timestamp là UTC, định dạng `YYYY-MM-DDTHH:MM:SSZ`.

| File | Nội dung | Số lượng |
|---|---|---|
| `actors.json` | Nông hộ, kho, vận tải, phân phối, cửa hàng, kiểm định | 12 |
| `users.json` | Tài khoản demo (mật khẩu `demo1234`, **backend phải bcrypt khi seed**) | 12 |
| `fruits.json` | Tham số RUL từng loại quả | 4 |
| `model_versions.json` | Phiên bản mô hình RUL + `modelHash` | 1 |
| `batches.json` | Lô hàng + RUL mới nhất + `metadataHash` + `qrPayload` | 6 |
| `sensor_readings.csv` | Cảm biến mỗi giờ, kèm `deviceSig` | 714 dòng |
| `rul_timeseries.csv` | RUL tính sẵn theo từng giờ (để vẽ biểu đồ & test) | 714 dòng |
| `events_ledger.json` | Sổ cái giả lập: chuỗi sự kiện có `prevHash`, `eventHash`, `blockNumber`, `txHash` | 29 sự kiện |
| `alerts.json` | Cảnh báo sinh sẵn | 5 |
| `expected_verification.json` | **Kết quả Verify mong đợi** của từng lô (dùng làm test) | 6 |

### 4.1 Schema chính

**`sensor_readings.csv`**: `batchId, ts, tempC, humidityPct, ethylenePpm, lat, lon, deviceId, deviceSig`
(`tempC` 1 chữ số thập phân, `humidityPct` số nguyên, `ethylenePpm` 1 chữ số, `lat/lon` 4 chữ số.)

**`events_ledger.json`**: `{ chainId, genesisHash, events: [ ... ] }`, mỗi sự kiện:

```json
{
  "eventId": "EV-005-01", "batchId": "FC-2026-005",
  "type": "HARVEST | HANDOFF | VIOLATION | SOLD | INSPECTION",
  "ts": "2026-11-05T00:00:00Z",
  "actorId": "F001", "toActorId": null, "lat": 10.46, "lon": 105.633,
  "dataHash": "<sha256 hex>",
  "payload": { "...tuỳ loại..." },
  "rulSnapshot": { "rulDaysAtCurrent": 2.87, "rulDaysAtOptimal": 14.0, "ciLowDays": 2.44, "ciHighDays": 3.3,
                   "freshness": "FRESH", "tempC": 30.3, "modelVersion": "rul-q10-v0.1", "modelHash": "<sha256>" },
  "prevHash": "<eventHash của sự kiện trước trong cùng lô, hoặc 64 số 0>",
  "eventHash": "<sha256 hex>", "blockNumber": 1000001, "txHash": "0x..."
}
```

`payload` theo loại:
- `HANDOFF`: `legIndex, legLabel, fromReading, toReading, readingCount`
- `VIOLATION`: `violationType="TEMP_EXCURSION", thresholdC, startTs, endTs, durationHours, maxTempC, ongoing`
- `HARVEST`: `quantityKg, variety, certifications`; `SOLD`: `quantityKg`
- `INSPECTION` (**không có trong demo**, sinh khi upload ảnh): `imageId, imageHash, rulImageDays, freshnessLabel, modelVersion`

**Quy ước timestamp sự kiện:** `HANDOFF.ts` = timestamp reading **đầu tiên của chặng kế tiếp**; `rulSnapshot` lấy từ reading **cuối cùng của chặng vừa kết thúc**. `VIOLATION.ts` = timestamp reading cuối của đợt vi phạm.

### 4.2 Kịch bản 6 lô (dùng để demo & test)

| Lô | Loại quả | Trạng thái | RUL hiện tại / nếu bảo quản chuẩn (ngày) | Độ tươi | Kịch bản | Verify |
|---|---|---|---|---|---|---|
| FC-2026-001 | Xoài cát Hòa Lộc | IN_STORE | 7.80 / 7.73 | FRESH | Chuỗi lạnh tốt | PASS |
| FC-2026-002 | Chuối Cavendish | IN_TRANSIT | 5.47 / 5.42 | FRESH | Đang chở đến cửa hàng | PASS |
| FC-2026-003 | Thanh long ruột đỏ | IN_STORE | 4.94 / 5.30 | GOOD | **Sự cố lạnh trên xe T001** (~25°C trong 6 giờ) | PASS |
| FC-2026-004 | Dâu tây Đà Lạt | IN_STORE | **1.22** / 3.79 | FRESH | **Tủ trưng bày ~12°C** (vi phạm đang tiếp diễn 18 giờ), RUL thấp | PASS |
| FC-2026-005 | Xoài cát Hòa Lộc | SOLD | 5.55 / 6.42 | GOOD | Vòng đời hoàn tất (có sự kiện SOLD) | PASS |
| FC-2026-006 | Chuối Cavendish | IN_STORE | 3.22 / 3.93 | GOOD | **TAMPER DEMO**: sự cố nhiệt thật (~25°C, 6 giờ) bị sửa trong `sensor_readings.csv` | **FAIL** |

Tổng sự kiện: 29 (6 HARVEST, 19 HANDOFF, 3 VIOLATION, 1 SOLD). Cảnh báo: 5 (3 `COLD_CHAIN_VIOLATION` cho lô 003, 004, 006; 2 `LOW_RUL`: lô 004 HIGH, lô 006 MEDIUM).

**Lô 006 là bằng chứng để demo giá trị của blockchain:** dữ liệu trong DB trông bình thường (không có vi phạm), nhưng hash đã ghi trên sổ cái được tính từ dữ liệu gốc nên Verify phải phát hiện: 2 đoạn không khớp (`EV-006-03` VIOLATION và `EV-006-04` HANDOFF) và 6 reading sai chữ ký thiết bị.

---

## 5. Mô hình RUL (mặc định: Q10, thay thế được)

Tham số ở `fruits.json`: `shelfRefDays` (hạn dùng ở nhiệt độ chuẩn), `refTempC`, `q10`, `optimalTempMinC/MaxC`, `alertTempC`.

```python
def rate(fruit, temp_c):               # tốc độ lão hoá so với nhiệt độ chuẩn
    return fruit.q10 ** ((temp_c - fruit.refTempC) / 10.0)

def compute_series(fruit, readings):   # readings: danh sách theo thời gian, cách nhau 1 giờ
    consumed = 0.0                     # "giờ-quy-đổi" ở nhiệt độ chuẩn đã tiêu thụ
    out = []
    for i, r in enumerate(readings):
        if i > 0:
            consumed += rate(fruit, r.temp)      # mỗi reading đại diện 1 giờ trước đó; reading đầu = 0
        frac = consumed / (fruit.shelfRefDays * 24)
        remaining_ref = max(0.0, fruit.shelfRefDays - consumed / 24)
        rul_current = remaining_ref / rate(fruit, r.temp)   # nếu giữ nhiệt độ hiện tại
        out.append(dict(
            effectiveHoursConsumed=round(consumed, 4),
            fractionUsed=round(min(frac, 1.0), 4),
            rulDaysAtOptimal=round(remaining_ref, 2),       # nếu từ giờ bảo quản đúng chuẩn
            rulDaysAtCurrent=round(rul_current, 2),
            ciLowDays=round(rul_current * 0.85, 2),         # demo: ±15%, ghi rõ là giả định
            ciHighDays=round(rul_current * 1.15, 2),
            freshness=("EXPIRED" if frac >= 1 else "NEAR_EXPIRY" if frac >= 0.8 else "GOOD" if frac >= 0.5 else "FRESH")))
    return out
```

**Yêu cầu:**
- `services/rul.py` phải tái tạo `rul_timeseries.csv` với sai số ≤ 0.01 ngày (test T-RUL).
- Bọc sau interface `RulModel.predict(batch, readings) -> RulResult` để sau này thay bằng mô hình ML (ONNX/sklearn) mà không sửa chỗ khác. Mỗi kết quả ghi `modelVersion` + `modelHash`.
- `POST /api/rul/predict` nhận danh sách reading bất kỳ và trả về chuỗi RUL (dùng cho trang "What-if").

### 5.1 Tích hợp model RUL & tiền xử lý ảnh có sẵn

Interface (mọi model, kể cả Q10, đều đi qua đây):

```python
class RulModel(Protocol):
    name: str
    version: str
    def model_hash(self) -> str: ...        # sha256 của file trọng số (+ file cấu hình), tính lúc khởi động
    def predict(self, x: "RulInput") -> "RulOutput": ...

@dataclass
class RulInput:
    batch_id: str
    fruit_id: str
    readings: list | None        # chuỗi cảm biến (nếu model dùng)
    image_path: str | None       # ảnh ĐÃ tiền xử lý (nếu model dùng ảnh)

@dataclass
class RulOutput:
    rul_days: float
    ci_low_days: float | None
    ci_high_days: float | None
    freshness: str | None        # FRESH | GOOD | NEAR_EXPIRY | EXPIRED (nếu model có)
    extra: dict                  # xác suất lớp, điểm tin cậy...
```

- Adapter đặt ở `services/rul_adapters/`: `q10.py` (baseline, mặc định) và `custom.py` (**model có sẵn của bạn**: nạp file model, gọi suy luận, đổi output về `RulOutput`).
- Chọn bằng biến môi trường: `RUL_MODEL=q10|custom`, `RUL_MODEL_PATH=...`. Đổi model **không được** sửa code ngoài thư mục adapter.
- Khi khởi động: tính `model_hash()`, nếu chưa có thì ghi vào bảng `model_versions` và (chế độ evm) gọi `registerModel`. Mọi dự đoán lưu `modelVersion` + `modelHash`.

**Luồng ảnh kiểm tra** (`POST /api/batches/{id}/inspections`, multipart):
1. Lưu **ảnh gốc** vào `storage/raw/{batchId}/{ts}_{sha256}.jpg`, tính `imageHash = sha256(bytes file gốc)`.
2. `services/preprocess.py` gọi lại **đúng hàm tiền xử lý hiện có** của dự án (import hoặc sao chép nguyên văn, không viết lại để tránh lệch với lúc huấn luyện); lưu kết quả vào `storage/preprocessed/`.
3. `RulModel.predict` với `image_path`, (và `readings` nếu model dùng cảm biến).
4. Lưu bảng `inspections`, ghi sự kiện `INSPECTION` lên ledger với `dataHash = imageHash`, kèm RUL snapshot và `modelHash`.

**Hợp nhất kết quả** khi có cả cảm biến và ảnh: cấu hình `FUSION=min|mean|sensor_only|image_only|model`. Mặc định `min` (bảo thủ: lấy RUL nhỏ hơn). Hiển thị riêng `rulSensor`, `rulImage`, `rulFinal`. Nếu model của bạn đã nhận cả hai đầu vào thì dùng `FUSION=model` (lấy thẳng output).

**Cần chốt khi gắn model thật (điền vào `README`):** định dạng model (`.pt/.onnx/.h5/.pkl`), input (chuỗi cảm biến? ảnh? kích thước, chuẩn hoá), output (số ngày? lớp? khoảng tin cậy?), tên hàm preprocess và loại quả được hỗ trợ.

**Quy tắc cảnh báo vi phạm chuỗi lạnh:** đợt vi phạm = **≥ 2 reading liên tiếp** có `tempC > alertTempC`, **bỏ qua chặng loại `farm`** (làm mát ban đầu). Mỗi đợt tạo đúng 1 sự kiện `VIOLATION` (đợt chưa kết thúc: `ongoing=true`).
**Cảnh báo RUL thấp:** `rulDaysAtCurrent < 2` → HIGH; `< 4` → MEDIUM (bỏ qua lô SOLD).

---

## 6. Quy tắc hash & kiểm chứng (BẮT BUỘC đúng từng ký tự)

Mọi hash là **SHA-256, hex thường 64 ký tự**, tính trên chuỗi UTF-8.

**6.1 Reading chuẩn hoá (canonical)**
```
{batchId}|{ts}|{tempC:.1f}|{humidityPct:d}|{ethylenePpm:.1f}|{lat:.4f}|{lon:.4f}
```
**6.2 Hash đoạn dữ liệu** = `sha256("\n".join(canonical readings sắp theo ts tăng dần))`
- `HANDOFF.dataHash`: các reading có `fromReading ≤ ts ≤ toReading` (lấy từ payload).
- `VIOLATION.dataHash`: các reading có `startTs ≤ ts ≤ endTs`.

**6.3 Chữ ký thiết bị:** `deviceSig = sha256(f"{deviceId}|{canonicalReading}|demo-device-key")[:32]` (khoá demo; bản thật dùng HMAC/ký số theo thiết bị).

**6.4 HARVEST.dataHash (`metadataHash`)** = `sha256(canonical_json({batchId, fruitId, variety, farmId, quantityKg, harvestTs, certifications}))`
**6.5 SOLD.dataHash** = `sha256(canonical_json({batchId, soldTs, quantityKg}))`

**6.6 canonical_json** = `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`

**6.7 eventHash** = `sha256(canonical_json(event))` trong đó `event` là sự kiện **không có** `eventHash`, `blockNumber`, `txHash` (có `eventId`, `prevHash`, `rulSnapshot`, `payload`...).
**6.8 Chuỗi liên kết:** `prevHash` của sự kiện đầu mỗi lô = `"0"*64`; các sự kiện sau = `eventHash` của sự kiện ngay trước **trong cùng lô** (sắp theo `ts`, ưu tiên cùng `ts`: HARVEST < VIOLATION < HANDOFF < SOLD).
> Lưu ý: backend dùng Python để tính `eventHash` (định dạng số thực của `json.dumps` phải giữ nguyên, ví dụ `14.0`). Không tính lại `eventHash` ở frontend JS.

**6.9 Thuật toán Verify cho 1 lô** (`POST /api/batches/{id}/verify`):
1. Lấy chuỗi sự kiện từ Ledger.
2. Kiểm tra liên kết: `prevHash` khớp và `eventHash` tính lại khớp → `chainLinkIntact`.
3. Với mỗi `HANDOFF`/`VIOLATION`: tính lại hash đoạn từ bảng `sensor_readings` trong DB, so với `dataHash` → `match`.
4. Với mỗi reading: tính lại `deviceSig`, đếm số sai → `signatureFailureCount`.
5. `overall = PASS` nếu mọi `match` đúng **và** `signatureFailureCount == 0`, ngược lại `FAIL`.
6. Trả về cùng định dạng `expected_verification.json`:
```json
{ "batchId": "...", "chainLinkIntact": true,
  "segments": [{ "eventId": "EV-006-03", "type": "VIOLATION", "onChainDataHash": "...", "recomputedHash": "...", "match": false }],
  "signatureFailureCount": 6, "overall": "FAIL" }
```

**6.10 Ảnh kiểm tra (INSPECTION):** `imageHash = sha256(bytes của file ảnh GỐC)`; `INSPECTION.dataHash = imageHash`. Verify tính lại sha256 từ file trong `storage/raw/` và so với `dataHash`; ảnh bị thay/sửa → segment `INSPECTION` có `match=false` → `overall=FAIL`. (Demo data chưa có INSPECTION; test T-IMG tự tạo.)

---

## 7. Smart contract (`contracts/contracts/FruitChain.sol`)

Contract chỉ lưu bằng chứng; payload đầy đủ nằm off-chain. `eventHash` được tính off-chain (SHA-256) và truyền vào dưới dạng `bytes32`; contract **bắt buộc tính liên tục của `prevHash`** và **kiểm tra quyền theo vai trò**.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract FruitChain {
    enum Role { NONE, ADMIN, FARMER, WAREHOUSE, TRANSPORT, DISTRIBUTOR, RETAILER, REGULATOR }
    enum EventType { HARVEST, HANDOFF, VIOLATION, SOLD, INSPECTION }

    struct BatchEvent {
        EventType eventType;
        address actor;
        string  actorId;
        string  toActorId;
        uint64  ts;
        bytes32 dataHash;
        bytes32 prevHash;
        bytes32 eventHash;
        uint32  rulCentiDays;   // RUL * 100
        bytes32 modelHash;
    }

    address public admin;
    mapping(address => Role) public roles;
    mapping(bytes32 => bool) public registeredModels;
    mapping(bytes32 => BatchEvent[]) private _events;      // key = keccak256(bytes(batchId))

    event BatchEventRecorded(bytes32 indexed batchKey, string batchId, EventType eventType, bytes32 eventHash, uint64 ts);
    event ModelRegistered(bytes32 indexed modelHash, string version);

    modifier onlyRole(Role a, Role b) {
        Role r = roles[msg.sender];
        require(r == Role.ADMIN || r == a || r == b, "forbidden");
        _;
    }

    constructor() { admin = msg.sender; roles[msg.sender] = Role.ADMIN; }

    function grantRole(address who, Role r) external {
        require(msg.sender == admin, "only admin");
        roles[who] = r;
    }

    function registerModel(bytes32 modelHash, string calldata version) external {
        require(roles[msg.sender] == Role.ADMIN, "only admin");
        registeredModels[modelHash] = true;
        emit ModelRegistered(modelHash, version);
    }

    function createBatch(string calldata batchId, string calldata farmId, uint64 ts, bytes32 metadataHash,
                         bytes32 eventHash, uint32 rulCentiDays, bytes32 modelHash)
        external onlyRole(Role.FARMER, Role.FARMER)
    {
        bytes32 k = keccak256(bytes(batchId));
        require(_events[k].length == 0, "batch exists");
        _append(k, batchId, EventType.HARVEST, farmId, "", ts, metadataHash, bytes32(0), eventHash, rulCentiDays, modelHash);
    }

    function recordHandoff(string calldata batchId, string calldata fromId, string calldata toId, uint64 ts,
                           bytes32 dataHash, bytes32 prevHash, bytes32 eventHash, uint32 rulCentiDays, bytes32 modelHash)
        external onlyRole(Role.WAREHOUSE, Role.TRANSPORT)
    {
        _append(keccak256(bytes(batchId)), batchId, EventType.HANDOFF, fromId, toId, ts, dataHash, prevHash, eventHash, rulCentiDays, modelHash);
    }

    function recordViolation(string calldata batchId, string calldata actorId, uint64 ts, bytes32 evidenceHash,
                             bytes32 prevHash, bytes32 eventHash, uint32 rulCentiDays, bytes32 modelHash)
        external onlyRole(Role.REGULATOR, Role.DISTRIBUTOR)
    {
        _append(keccak256(bytes(batchId)), batchId, EventType.VIOLATION, actorId, "", ts, evidenceHash, prevHash, eventHash, rulCentiDays, modelHash);
    }

    function recordSold(string calldata batchId, string calldata retailerId, uint64 ts, bytes32 dataHash,
                        bytes32 prevHash, bytes32 eventHash, uint32 rulCentiDays, bytes32 modelHash)
        external onlyRole(Role.RETAILER, Role.RETAILER)
    {
        _append(keccak256(bytes(batchId)), batchId, EventType.SOLD, retailerId, "", ts, dataHash, prevHash, eventHash, rulCentiDays, modelHash);
    }

    function recordInspection(string calldata batchId, string calldata actorId, uint64 ts, bytes32 imageHash,
                              bytes32 prevHash, bytes32 eventHash, uint32 rulCentiDays, bytes32 modelHash)
        external onlyRole(Role.RETAILER, Role.REGULATOR)
    {
        _append(keccak256(bytes(batchId)), batchId, EventType.INSPECTION, actorId, "", ts, imageHash, prevHash, eventHash, rulCentiDays, modelHash);
    }

    function getEventCount(string calldata batchId) external view returns (uint256) {
        return _events[keccak256(bytes(batchId))].length;
    }

    function getEvent(string calldata batchId, uint256 i) external view returns (BatchEvent memory) {
        return _events[keccak256(bytes(batchId))][i];
    }

    function headHash(string calldata batchId) external view returns (bytes32) {
        BatchEvent[] storage e = _events[keccak256(bytes(batchId))];
        return e.length == 0 ? bytes32(0) : e[e.length - 1].eventHash;
    }

    function _append(bytes32 k, string memory batchId, EventType t, string memory actorId, string memory toId, uint64 ts,
                     bytes32 dataHash, bytes32 prevHash, bytes32 eventHash, uint32 rul, bytes32 modelHash) internal {
        BatchEvent[] storage e = _events[k];
        if (e.length > 0) {
            require(prevHash == e[e.length - 1].eventHash, "bad prevHash");
            require(e[e.length - 1].eventType != EventType.SOLD, "batch closed");
        }
        require(modelHash == bytes32(0) || registeredModels[modelHash], "unknown model");
        e.push(BatchEvent(t, msg.sender, actorId, toId, ts, dataHash, prevHash, eventHash, rul, modelHash));
        emit BatchEventRecorded(k, batchId, t, eventHash, ts);
    }
}
```

> Ghi chú: modifier `onlyRole(a, b)` cho phép ADMIN + 2 vai trò. Trong bản đầy đủ, hãy mở rộng để HANDOFF cho phép FARMER/WAREHOUSE/TRANSPORT/DISTRIBUTOR, VIOLATION cho mọi bên tham gia + REGULATOR. Khi seed chế độ `evm`, backend dùng 1 tài khoản deployer được cấp tất cả vai trò (chấp nhận được cho demo) và đặt `actorId` thật vào tham số.

**Hardhat tests tối thiểu:** tạo lô thành công; tạo trùng bị từ chối; `prevHash` sai bị từ chối; sai vai trò bị từ chối; sau `SOLD` không ghi thêm được; `modelHash` chưa đăng ký bị từ chối.

---

## 8. Backend API (`/api`, JSON, JWT Bearer)

| Method & Path | Vai trò | Mô tả |
|---|---|---|
| `POST /auth/login` | công khai | `{username,password}` → `{token, user}` |
| `GET /me` | đăng nhập | Thông tin user + actor |
| `GET /meta/actors`, `/meta/fruits`, `/meta/models` | đăng nhập | Danh mục |
| `GET /batches` | đăng nhập | Lọc `status`, `fruitId`, `q`; kèm `latestRul` |
| `GET /batches/{id}` | đăng nhập | Chi tiết + vị trí hiện tại |
| `POST /batches` | FARMER, ADMIN | Tạo lô → sinh `metadataHash`, QR, ghi sự kiện HARVEST |
| `GET /batches/{id}/readings?from&to` | đăng nhập | Dữ liệu cảm biến |
| `GET /batches/{id}/rul` | đăng nhập | Chuỗi RUL (như `rul_timeseries.csv`) |
| `GET /batches/{id}/events` | đăng nhập | Sự kiện từ Ledger (có `txHash`, `blockNumber`) |
| `POST /batches/{id}/handoff` | bên đang giữ lô, ADMIN | `{toActorId}` → tính `dataHash` đoạn vừa qua + RUL snapshot, ghi sự kiện |
| `POST /batches/{id}/sold` | RETAILER, ADMIN | Đóng vòng đời |
| `POST /ingest/readings` | thiết bị (header `X-Device-Id`) | Danh sách reading có `deviceSig`; sai chữ ký → 422; tự tính RUL, sinh VIOLATION/alert nếu cần |
| `POST /batches/{id}/inspections` | bên đang giữ lô, REGULATOR, ADMIN | multipart: ảnh (+ ghi chú) → lưu gốc → preprocess → model RUL → ghi `INSPECTION`; trả `rulImage`, `rulFinal` (mục 5.1) |
| `GET /batches/{id}/inspections` | đăng nhập | Danh sách ảnh kiểm tra + kết quả |
| `POST /batches/{id}/verify` | đăng nhập | Thuật toán mục 6.9 (+ 6.10 nếu có ảnh) |
| `POST /rul/predict` | đăng nhập | What-if: danh sách reading + loại quả → chuỗi RUL |
| `GET /alerts`, `POST /alerts/{id}/ack` | đăng nhập | Cảnh báo |
| `GET /public/trace/{batchId}` | **công khai** | Dữ liệu rút gọn cho người tiêu dùng (không lộ `deviceSig`, không lộ thông tin nội bộ) |
| `POST /admin/seed`, `POST /admin/reset` | ADMIN | Nạp lại / xoá dữ liệu demo |
| `POST /admin/simulate/tick` | ADMIN | (Tuỳ chọn) thêm 1 reading mới cho các lô đang hoạt động để demo "thời gian thực" |

**Phân quyền (RBAC):** FARMER chỉ tạo lô của farm mình; TRANSPORT/WAREHOUSE/DISTRIBUTOR/RETAILER chỉ chuyển giao/bán lô mà `currentActorId` là chính họ; REGULATOR và ADMIN xem tất cả; chỉ ADMIN dùng `/admin/*`. Lỗi: 401 chưa đăng nhập, 403 sai quyền, 404 không có lô, 409 trạng thái sai (ví dụ handoff lô đã SOLD).

---

## 9. Frontend (React)

| Trang | Nội dung |
|---|---|
| `/login` | Đăng nhập; hiển thị danh sách tài khoản demo để bấm điền nhanh |
| `/` Dashboard | Thẻ tổng quan (số lô, số cảnh báo HIGH, lô sắp hết hạn); bảng lô sắp hết hạn sắp theo `rulDaysAtCurrent` tăng dần; biểu đồ phân bố độ tươi |
| `/batches` | Bảng lô: mã, loại quả, trạng thái, bên đang giữ, RUL (thanh màu theo độ tươi), huy hiệu cảnh báo; lọc & tìm kiếm |
| `/batches/:id` | Tab **Tổng quan** (thông tin, QR, hash), **RUL** (đường RUL theo thời gian + nhiệt độ chồng lên, vùng tin cậy, vạch ngưỡng cảnh báo), **Timeline** (sự kiện: loại, bên thực hiện, RUL snapshot, `txHash` rút gọn, block), **Bản đồ** (tuyến đường theo GPS, Leaflet), **Cảm biến** (bảng + lọc), **Ảnh kiểm tra** (tải ảnh lên, xem ảnh gốc / ảnh đã preprocess, RUL từ ảnh so với RUL từ cảm biến), **Kiểm chứng** (nút *Verify*) |
| `/batches/new` | Form tạo lô (FARMER) |
| `/alerts` | Danh sách cảnh báo, bấm xác nhận (ack) |
| `/ledger` | Trình khám phá sổ cái: danh sách sự kiện toàn hệ thống, bấm xem JSON + trạng thái liên kết hash |
| `/trace/:batchId` | **Công khai**, không cần đăng nhập, di động trước: nguồn gốc, timeline rút gọn, đường cong RUL, huy hiệu "Đã xác minh toàn vẹn / Phát hiện sai lệch" |
| `/admin` | Nạp lại demo, reset, xem phiên bản mô hình, (tuỳ chọn) nút *Simulate tick* |

**Kết quả Verify hiển thị:** banner xanh **PASS** / đỏ **FAIL**; bảng từng đoạn (loại sự kiện, hash trên sổ cái, hash tính lại, ✔/✘); số reading sai chữ ký; với lô FC-2026-006 làm nổi bật các đoạn lệch. Màu độ tươi: FRESH xanh lá, GOOD vàng lục, NEAR_EXPIRY cam, EXPIRED đỏ. Giao diện phải dùng được trên điện thoại (đặc biệt `/trace/:batchId`).

---

## 10. Nạp dữ liệu demo (`backend/app/seed.py`)

1. Khi khởi động, nếu DB trống (hoặc gọi `POST /admin/seed`): nạp theo thứ tự `actors → users (bcrypt) → fruits → model_versions → batches → sensor_readings.csv → rul_timeseries.csv → alerts`.
2. **Sổ cái:**
   - `LEDGER_MODE=mock`: nạp nguyên `events_ledger.json` vào bảng `ledger_events` (giữ nguyên `eventHash`, `blockNumber`, `txHash`).
   - `LEDGER_MODE=evm`: deploy `FruitChain.sol`, `registerModel`, rồi **phát lại** từng sự kiện theo thứ tự `blockNumber` qua `createBatch/recordHandoff/recordViolation/recordSold` với đúng `eventHash/prevHash` trong file (`txHash` sẽ do chain thật cấp, lưu lại vào DB).
3. **Không được "sửa lại" dữ liệu lô FC-2026-006** khi nạp: `sensor_readings.csv` đã chứa dữ liệu bị chỉnh sửa có chủ đích.
4. Sau khi nạp, chạy tự kiểm tra: số lượng bản ghi khớp bảng ở mục 4; log cảnh báo nếu không.

---

## 11. Mô hình dữ liệu (SQL, tóm tắt)

`actors(actor_id PK, name, role, province, lat, lon)` · `users(username PK, password_hash, role, actor_id FK)` · `fruits(fruit_id PK, name_vi, shelf_ref_days, ref_temp_c, q10, optimal_temp_min_c, optimal_temp_max_c, alert_temp_c, optimal_humidity_pct)` · `model_versions(version PK, model_hash, registered_ts, description)` · `batches(batch_id PK, fruit_id FK, variety, farm_id FK, origin_province, quantity_kg, harvest_ts, certifications JSON, status, current_actor_id FK, metadata_hash, qr_payload)` · `sensor_readings(id PK, batch_id FK, ts, temp_c, humidity_pct, ethylene_ppm, lat, lon, device_id, device_sig; UNIQUE(batch_id, ts))` · `rul_points(batch_id, ts, temp_c, effective_hours, fraction_used, rul_at_current, rul_at_optimal, ci_low, ci_high, freshness; PK(batch_id, ts))` · `ledger_events(event_id PK, batch_id, type, ts, actor_id, to_actor_id, lat, lon, data_hash, payload JSON, rul_snapshot JSON, prev_hash, event_hash, block_number, tx_hash)` · `alerts(alert_id PK, batch_id, type, severity, ts, related_event_id, acknowledged, message)`

`inspections(inspection_id PK, batch_id FK, ts, raw_image_path, image_hash, preprocessed_path, rul_image_days, ci_low, ci_high, freshness_label, model_version, model_hash, event_id FK)`

`ledger_events` là **append-only**: không có API nào UPDATE/DELETE (trừ `/admin/reset`).

---

## 12. Chạy dự án

```bash
# Backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export LEDGER_MODE=mock DEMO_DATA_DIR=../demo_data JWT_SECRET=dev-secret
uvicorn app.main:app --reload --port 8000        # tự seed lần đầu

# Frontend
cd frontend && npm install && npm run dev        # http://localhost:5173 (proxy /api → :8000)

# (Tuỳ chọn) Blockchain thật
cd contracts && npm install && npx hardhat node  # cửa sổ 1
npx hardhat test                                  # cửa sổ 2
LEDGER_MODE=evm EVM_RPC=http://127.0.0.1:8545 uvicorn app.main:app   # backend dùng chain thật

# Sinh lại dữ liệu demo
python3 tools/generate_demo_data.py demo_data
```

Cung cấp `.env.example`, `README.md` ngắn, và `docker-compose.yml` (backend + frontend + hardhat node) nếu thời gian cho phép.

---

## 13. Acceptance Tests (pytest + Playwright/Vitest cơ bản)

| ID | Kiểm tra | Kỳ vọng |
|---|---|---|
| T-SEED | Sau seed | 6 lô, 714 reading, 29 sự kiện, 5 cảnh báo, 12 actor, 12 user |
| T-RUL | Tính lại RUL từ `sensor_readings.csv` bằng `services/rul.py` | Khớp `rul_timeseries.csv`, sai số ≤ 0.01 |
| T-RULNOW | RUL mới nhất `rulDaysAtCurrent` | 001=7.80, 002=5.47, 003=4.94, 004=1.22, 005=5.55, 006=3.22 (±0.01) |
| T-HASH | Tính lại `eventHash` của mọi sự kiện theo mục 6.7 | 29/29 khớp, `prevHash` liên kết đúng |
| T-VERIFY-PASS | `verify` lô 001–005 | `overall=PASS`, `signatureFailureCount=0` |
| T-VERIFY-FAIL | `verify` lô 006 | `overall=FAIL`; `EV-006-03` và `EV-006-04` `match=false`; `signatureFailureCount=6` |
| T-VERIFY-EXP | So sánh toàn bộ kết quả verify | Khớp `expected_verification.json` |
| T-VIOL | Chạy lại phát hiện vi phạm trên dữ liệu gốc | Đúng 3 đợt: lô 003 (6h, max 25.3°C), 004 (18h, ongoing, max 12.8°C), 006 (6h, max 26.5°C) |
| T-INGEST-SIG | `POST /ingest/readings` với `deviceSig` sai | 422, không ghi DB |
| T-INGEST-OK | Ingest reading hợp lệ mới cho lô 002 | RUL được tính tiếp, nếu >18°C liên tiếp 2 giờ thì sinh VIOLATION + alert |
| T-HANDOFF | Handoff lô 001 bởi đúng bên đang giữ | Sự kiện mới có `prevHash` = head cũ, `dataHash` đúng đoạn; sai bên → 403 |
| T-IMG-1 | Upload ảnh hợp lệ cho lô 001 | 201; file gốc được lưu; có sự kiện `INSPECTION` với `dataHash == sha256(file)`; `prevHash` = head cũ |
| T-IMG-2 | Sửa 1 byte file ảnh trong `storage/raw/` rồi `verify` | `overall=FAIL`, segment `INSPECTION` `match=false` |
| T-PREPROC | Chạy `services/preprocess.py` trên ảnh mẫu | Kết quả giống hệt script preprocess gốc (so hash đầu ra) |
| T-MODEL-SWAP | Đổi `RUL_MODEL=q10` ↔ `custom` | Hệ thống chạy bình thường, `modelHash` thay đổi tương ứng, không sửa code ngoài adapter |
| T-CLOSED | Handoff/bán lô 005 (đã SOLD) | 409 |
| T-RBAC | `farm_dalat` tạo lô cho farm F001 / cho farm F004 | 403 / 201 |
| T-PUBLIC | `GET /public/trace/FC-2026-001` không token | 200, không chứa `deviceSig`, `passwordHash`, thông tin user |
| T-APPEND | Cố UPDATE/DELETE `ledger_events` qua API | Không có endpoint; (mức DB) trigger hoặc test xác nhận không bị sửa |
| T-UI-1 | Dashboard | Lô 004 đứng đầu bảng "sắp hết hạn"; badge 3 vi phạm |
| T-UI-2 | Trang lô 006 → Verify | Hiện banner đỏ FAIL và 2 đoạn lệch |
| T-UI-3 | `/trace/FC-2026-001` trên viewport 390px | Không cần login, không vỡ layout |
| T-SC | Hardhat tests (mục 7) | Tất cả xanh |

---

## 14. Lộ trình (Milestones)

1. **M1 – Lõi dữ liệu:** DB, models, seed từ `demo_data`, `services/rul.py`, `hashing.py`. *Xong khi* T-SEED, T-RUL, T-RULNOW, T-HASH xanh.
2. **M1b – Gắn model & ảnh có sẵn:** `RulModel` interface, adapter `q10` + `custom`, `preprocess.py`, `inspections` + `/inspections`, sự kiện INSPECTION, hash ảnh (6.10). *Xong khi* T-PREPROC, T-MODEL-SWAP, T-IMG-1, T-IMG-2 xanh.
3. **M2 – API & Verify:** auth + RBAC, các router, `verify.py`, `MockLedger`, ingest + cảnh báo. *Xong khi* T-VERIFY-*, T-VIOL, T-INGEST-*, T-HANDOFF, T-CLOSED, T-RBAC, T-PUBLIC xanh.
4. **M3 – Giao diện:** Dashboard, danh sách/chi tiết lô (RUL chart, timeline, bản đồ, Verify), cảnh báo, ledger explorer, trang `/trace`. *Xong khi* T-UI-1..3 đạt.
5. **M4 – Blockchain thật:** `FruitChain.sol`, Hardhat tests, `EvmLedger`, seed chế độ `evm`. *Xong khi* T-SC xanh và `LEDGER_MODE=evm` chạy được cùng bộ test M2.
6. **M5 – Hoàn thiện:** simulate tick, `/rul/predict` what-if, `docker-compose`, README, `.env.example`.

---

## 15. Hạn chế đã biết & hướng mở rộng

- **Oracle problem:** blockchain chỉ chứng minh dữ liệu *không bị sửa sau khi ghi*, không chứng minh cảm biến đo đúng. Bản thật cần chữ ký số theo thiết bị (secure element), hiệu chuẩn định kỳ, đối chiếu nhiều nguồn.
- **Mô hình RUL demo là Q10 đơn giản** với khoảng tin cậy ±15% giả định; thay bằng mô hình ML huấn luyện từ dữ liệu thực địa, ghi `modelVersion/modelHash` mỗi lần dự đoán.
- **Riêng tư:** bản thật nên dùng mạng permissioned (Hyperledger Fabric) và kênh riêng cho dữ liệu thương mại nhạy cảm.
- **Chuẩn hoá:** cân nhắc GS1 EPCIS cho định dạng sự kiện chuỗi cung ứng để liên thông với doanh nghiệp khác.
- **Khoá demo/mật khẩu demo** (`demo-device-key`, `demo1234`) chỉ để thử nghiệm; không dùng ở môi trường thật.

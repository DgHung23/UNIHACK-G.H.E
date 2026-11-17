# FruitChain

Quản lý vòng đời lô trái cây + dự đoán RUL + bằng chứng blockchain — xây theo [FRUITCHAIN_SPEC.md](FRUITCHAIN_SPEC.md).

## Chạy nhanh (Windows)

```powershell
cd fruitchain
powershell -ExecutionPolicy Bypass -File run.ps1        # http://127.0.0.1:8000
```

Hoặc chạy tay:

```powershell
cd backend;  pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000      # tự seed demo lần đầu (SQLite backend/fruitchain.db)
cd ..\frontend;  npm install;  npm run dev      # http://localhost:5173 (proxy /api → :8000)
```

Đăng nhập: bấm một tài khoản demo ở trang login (mật khẩu `demo1234`). Trang **Cài đặt model** dành cho `admin`.

Script ưu tiên Python trong `backend/.venv`, môi trường đang kích hoạt, hoặc Python 3.10 qua `py`; tự cài dependency còn thiếu và build lại frontend trước khi chạy. Có thể chỉ định rõ bằng `-Python 'C:\Program Files\Python310\python.exe'`. Đăng nhập `admin` / `demo1234` rồi mở `/settings` để chọn thư mục.

## Bản đồ vận chuyển

Bản đồ trên trang **Tổng quan** và tab **Bản đồ** của từng lô dùng chung hai chế độ, không cần API key:

- **Bản đồ**: nền Việt Nam và lớp nhãn của [NARENCA](https://cosodulieu.bando.com.vn/).
- **Vệ tinh**: ảnh Esri World Imagery kết hợp lớp nhãn NARENCA. Tên **QĐ. Hoàng Sa** và **QĐ. Trường Sa** hiển thị bằng tiếng Việt ở cả hai chế độ; nhãn có viền sáng khi xem vệ tinh.

Cuộn chuột, nhấp đúp hoặc chụm hai ngón tay để thu phóng; kéo để di chuyển. Các nút bên phải cho phép **Toàn màn hình** (Escape để thoát), **Về vị trí các lô / Về tuyến đường**, **Toàn cảnh Việt Nam** và phóng to/thu nhỏ. Các lô gần nhau được gom thành điểm có số lượng; bấm để mở danh sách từng lô, phóng to để tách các điểm.

Các lớp bản đồ cần Internet. Khi tải lỗi, bản đồ hiển thị nút **Thử lại**. Nền bản đồ thường tập trung vào Việt Nam; mức chi tiết phụ thuộc nhà cung cấp. Cấu hình nguồn, lớp nhãn và ghi công: [docs/MAP_LAYERS.md](docs/MAP_LAYERS.md).

## Gắn model ảnh của bạn (trang ⚙️ Cài đặt model)

Dự án chạy độc lập với runtime tích hợp trong `ml_model/`. Cấu trúc và CLI suy luận: [ml_model/README.md](ml_model/README.md). Phân tích/refactor: [docs/ML_ENGINE_ARCHITECTURE.md](docs/ML_ENGINE_ARCHITECTURE.md). Mã nghiên cứu cũ nằm trong `ml_model/research/` và không được import khi chạy ứng dụng.

1. Chọn **Model tích hợp** để dùng `ml_model/`, hoặc **Duyệt…** tới một thư mục model khác → *Chọn thư mục này*.
   (Hoặc **🪟 Hộp thoại Windows** để mở hộp chọn thư mục gốc của Windows, hoặc dán đường dẫn.)
2. Hệ thống nhận dạng bundle/dự án và liệt kê checkpoint; bundle mặc định dùng `artifacts/strawberry/model_d.pt`.
3. Chọn loại quả áp dụng, chế độ hợp nhất (`FUSION`), bấm **🚀 Nạp model**.
4. **▶ Chạy thử** một ảnh: xem ảnh sau tiền xử lý, RUL (ngày/giờ), độ tin cậy, thời gian chạy.

Cài đặt lưu ở `backend/storage/model_settings.json`; lần khởi động sau backend tự nạp lại.
Đổi thư mục sẽ quét lại checkpoint. Nếu checkpoint mới hỏng, model đang dùng và lựa chọn đã lưu được giữ nguyên. Phải chọn ít nhất một loại quả; loại quả không tồn tại, thiết bị hoặc đơn vị không hợp lệ bị từ chối trước khi nạp.
Từ đó, mỗi ảnh tải lên ở tab **Ảnh kiểm tra** của lô (loại quả được hỗ trợ) đi qua đúng luồng mục 5.1:
lưu ảnh gốc → `imageHash` → preprocess của dự án → model → `rulImage` / `rulSensor` / `rulFinal` → sự kiện `INSPECTION` (kèm `modelHash`).

Adapter: `backend/app/services/rul_adapters/custom.py`. Hỗ trợ:
- **Bundle FruitChain**: `fruitchain_model.json` + package runtime, artifacts, config. ModelHash băm cả code suy luận; không cần code/dataset Desktop.
- **Dự án có sẵn** (có `src/<pkg>/services/preprocessing.py` + `predictor.py`): import **nguyên văn** `preprocess()` và `FruitRULPredictor` — không viết lại, nên không lệch với lúc huấn luyện (test T-PREPROC so hash đầu ra).
- **Model rời**: `.onnx`, TorchScript, hoặc `nn.Module` lưu nguyên; tuỳ chọn `preprocess.py` (hàm `preprocess(image_bgr)`) và `fruitchain_model.json` (`imageSize`, `seqLen`, `outputUnit`, `labels`, `classRulDays`, `mean`, `std`).

### Thông tin model đã chốt (Strawberry-RUL-prediction)

| Mục | Giá trị |
|---|---|
| Định dạng | PyTorch `.pt` (dict: `model_state_dict`, `config`, `target_scaler`, `env_stats`, `model_key`) |
| Kiến trúc | A/B/C/D (EfficientNet-B0/MobileNetV2 + CBAM + GRU/LSTM); production = **D** (MobileNetV2+CBAM+GRU) |
| Input | Ảnh đã preprocess (tách quả bằng màu + GrabCut, nền trong suốt) → 224×224, chuẩn hoá ImageNet; chuỗi `seq_len=8` (predictor lặp 1 ảnh 8 lần); `fusion_mode=image_only` (nhiệt độ/độ ẩm truyền vào nhưng model bỏ qua) |
| Output | RUL **giờ** (robust z-score → giải chuẩn hoá) → FruitChain đổi sang **ngày** (÷24); không có khoảng tin cậy; độ tươi suy từ RUL / `shelfRefDays` |
| Hàm preprocess | `ml_model/src/fruitchain_ml/preprocessing.py::preprocess(image, config)` (di chuyển từ bản Strawberry, giữ thuật toán) |
| Loại quả | `strawberry` (Dâu tây Đà Lạt — lô FC-2026-004) |

## Kiểm thử

```powershell
cd backend;   py -3.10 -m pytest                  # gồm nạp model thật, checkpoint lỗi, quyền Settings, cấu hình và blockchain
cd contracts; npm ci; npm test                    # contract: quyền, chuỗi bằng chứng, model và người giữ lô
# chạy bộ test backend trên chain thật:
cd contracts; npx hardhat node                    # cửa sổ 1
cd backend;  $env:LEDGER_MODE="evm"; python -m pytest            # cửa sổ 2
```

Test mặc định dùng bundle và ảnh trong `ml_model/`, không tìm tới Desktop. `USER_MODEL_DIR` có thể chỉ định rõ một dự án ngoài để kiểm tra adapter legacy.

## Avalanche và yêu cầu cuộc thi

UI đã bỏ các nút giả lập can thiệp và tab kiểm chứng. Cách sửa SQLite/file ảnh trực tiếp và audit bằng terminal nằm trong [docs/DEMO_DATA_INTEGRITY.md](docs/DEMO_DATA_INTEGRITY.md). Công cụ đọc độc lập: `py -3.10 tools/check_integrity.py --batch-id MA_LO --json`. Dữ liệu bổ sung nằm trong `.local/` và không đưa lên GitHub; test dùng fixture chuẩn riêng.

Phân tích thể lệ chính thức, thang điểm, hướng dẫn deploy Fuji và kịch bản demo chi tiết nằm ở [docs/COMPETITION_ALIGNMENT.md](docs/COMPETITION_ALIGNMENT.md). Theo [FAQ Team1 Vietnam](https://team1vn.xyz/#faq-submit), dự án có sẵn được tham gia nhưng phải có một phần chạy thật trên Avalanche (Fuji Testnet chain ID `43113` hoặc C-Chain `43114`). `LEDGER_MODE=mock` và Hardhat local chỉ phục vụ phát triển; cần deploy Fuji, ghi giao dịch thật và đưa link explorer vào bài nộp.

### Hồ sơ nộp bài dự thi (Submission Checklist)
Theo quy định nộp bài tại [team1vn.xyz](https://team1vn.xyz/):
1. **GitHub Repository**: Mã nguồn đầy đủ; nếu đặt chế độ Private phải mời collaborator `tuantqse90`.
2. **Video demo (2–3 phút)**: Nạp model, upload ảnh, timeline, sửa một số đo SQLite rồi audit bằng terminal, truy xuất công khai và giao dịch Fuji Explorer. Kịch bản xem tại [docs/DEMO_DATA_INTEGRITY.md](docs/DEMO_DATA_INTEGRITY.md).
3. **Slide thuyết trình**: Trình bày vấn đề hao hụt trái cây, giải pháp RUL + Smart Contract bằng chứng không thể sửa đổi, mô hình relayer và ma trận chấm điểm.
4. **Minh chứng giao dịch Avalanche Fuji**:
   - Chain ID: `43113` | RPC: `https://api.avax-test.network/ext/bc/C/rpc`
   - Lệnh deploy: `npm run deploy:fuji` (trong thư mục `contracts`)
   - Explorer: `https://testnet.snowtrace.io` (địa chỉ hợp đồng `FruitChain.sol` và các mã giao dịch HARVEST, HANDOFF, INSPECTION).

Trang **Sổ cái** và QR truy xuất công khai hiển thị mạng, địa chỉ contract và link giao dịch. API `GET /api/ledger/network` công khai trạng thái mạng, không trả về khóa ký. Backend ký với vai trò relayer; quyền actor được kiểm tra bằng đăng nhập/RBAC, chưa có liên kết ví riêng cho từng nông hộ.

## Ghi chú

- `LEDGER_MODE=mock` (mặc định) không cần kết nối RPC blockchain; các lớp bản đồ vẫn cần Internet. `evm` dùng Hardhat node + `contracts/contracts/FruitChain.sol` hoặc mạng Avalanche theo cấu hình. Nếu node mất trạng thái sau crash, backend giữ nguyên DB và báo lỗi contract; không tự seed lại để tránh mất dữ liệu. Cần khôi phục node hoặc chuẩn bị database trình diễn mới một cách chủ động.
- T-RUL: lô FC-2026-006 có 6 reading bị sửa có chủ đích trong `sensor_readings.csv` nên test tính lại RUL của lô này từ nhiệt độ gốc trong `rul_timeseries.csv`; T-VIOL cũng dùng nhiệt độ gốc đó.
- Contract mở rộng quyền theo ghi chú mục 7: HANDOFF cho mọi bên tham gia, VIOLATION/INSPECTION cho bên tham gia + REGULATOR.
- Python 3.10+ (spec ghi 3.11; mã tương thích cả hai).

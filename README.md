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

## Gắn model ảnh của bạn (trang ⚙️ Cài đặt model)

1. **📁 Duyệt…** → đi tới thư mục dự án model (vd. `C:\Users\admin\Desktop\Strawberry-RUL-prediction`) → *Chọn thư mục này*.
   (Hoặc **🪟 Hộp thoại Windows** để mở hộp chọn thư mục gốc của Windows, hoặc dán đường dẫn.)
2. Hệ thống nhận dạng dự án và liệt kê mọi checkpoint; mặc định chọn `models/strawberry/production/model_D/best_model.pt`.
3. Chọn loại quả áp dụng, chế độ hợp nhất (`FUSION`), bấm **🚀 Nạp model**.
4. **▶ Chạy thử** một ảnh: xem ảnh sau tiền xử lý, RUL (ngày/giờ), độ tin cậy, thời gian chạy.

Cài đặt lưu ở `backend/storage/model_settings.json`; lần khởi động sau backend tự nạp lại.
Đổi thư mục sẽ quét lại checkpoint. Nếu checkpoint mới hỏng, model đang dùng và lựa chọn đã lưu được giữ nguyên. Phải chọn ít nhất một loại quả; loại quả không tồn tại, thiết bị hoặc đơn vị không hợp lệ bị từ chối trước khi nạp.
Từ đó, mỗi ảnh tải lên ở tab **Ảnh kiểm tra** của lô (loại quả được hỗ trợ) đi qua đúng luồng mục 5.1:
lưu ảnh gốc → `imageHash` → preprocess của dự án → model → `rulImage` / `rulSensor` / `rulFinal` → sự kiện `INSPECTION` (kèm `modelHash`).

Adapter: `backend/app/services/rul_adapters/custom.py`. Hỗ trợ:
- **Dự án có sẵn** (có `src/<pkg>/services/preprocessing.py` + `predictor.py`): import **nguyên văn** `preprocess()` và `FruitRULPredictor` — không viết lại, nên không lệch với lúc huấn luyện (test T-PREPROC so hash đầu ra).
- **Model rời**: `.onnx`, TorchScript, hoặc `nn.Module` lưu nguyên; tuỳ chọn `preprocess.py` (hàm `preprocess(image_bgr)`) và `fruitchain_model.json` (`imageSize`, `seqLen`, `outputUnit`, `labels`, `classRulDays`, `mean`, `std`).

### Thông tin model đã chốt (Strawberry-RUL-prediction)

| Mục | Giá trị |
|---|---|
| Định dạng | PyTorch `.pt` (dict: `model_state_dict`, `config`, `target_scaler`, `env_stats`, `model_key`) |
| Kiến trúc | A/B/C/D (EfficientNet-B0/MobileNetV2 + CBAM + GRU/LSTM); production = **D** (MobileNetV2+CBAM+GRU) |
| Input | Ảnh đã preprocess (tách quả bằng màu + GrabCut, nền trong suốt) → 224×224, chuẩn hoá ImageNet; chuỗi `seq_len=8` (predictor lặp 1 ảnh 8 lần); `fusion_mode=image_only` (nhiệt độ/độ ẩm truyền vào nhưng model bỏ qua) |
| Output | RUL **giờ** (robust z-score → giải chuẩn hoá) → FruitChain đổi sang **ngày** (÷24); không có khoảng tin cậy; độ tươi suy từ RUL / `shelfRefDays` |
| Hàm preprocess | `src/strawberry/services/preprocessing.py::preprocess(image, config)` |
| Loại quả | `strawberry` (Dâu tây Đà Lạt — lô FC-2026-004) |

## Kiểm thử

```powershell
cd backend;   py -3.10 -m pytest                  # gồm nạp model thật, checkpoint lỗi, quyền Settings, cấu hình và blockchain
cd contracts; npm ci; npm test                    # contract: quyền, chuỗi bằng chứng, model và người giữ lô
# chạy bộ test backend trên chain thật:
cd contracts; npx hardhat node                    # cửa sổ 1
cd backend;  $env:LEDGER_MODE="evm"; python -m pytest            # cửa sổ 2
```

Đường dẫn dự án model cho test: biến `USER_MODEL_DIR` (mặc định `C:\Users\admin\Desktop\Strawberry-RUL-prediction`; không có thì test model được bỏ qua).

## Avalanche và yêu cầu cuộc thi

Phân tích thể lệ chính thức, thang điểm, hướng dẫn deploy Fuji và kịch bản demo chi tiết nằm ở [docs/COMPETITION_ALIGNMENT.md](docs/COMPETITION_ALIGNMENT.md). Theo [FAQ Team1 Vietnam](https://team1vn.xyz/#faq-submit), dự án có sẵn được tham gia nhưng phải có một phần chạy thật trên Avalanche (Fuji Testnet chain ID `43113` hoặc C-Chain `43114`). `LEDGER_MODE=mock` và Hardhat local chỉ phục vụ phát triển; cần deploy Fuji, ghi giao dịch thật và đưa link explorer vào bài nộp.

### Hồ sơ nộp bài dự thi (Submission Checklist)
Theo quy định nộp bài tại [team1vn.xyz](https://team1vn.xyz/):
1. **GitHub Repository**: Mã nguồn đầy đủ; nếu đặt chế độ Private phải mời collaborator `tuantqse90`.
2. **Video demo (2–3 phút)**: Trình diễn luồng thực tế (Cài đặt nạp model thật, upload ảnh kiểm tra lô dâu tây, timeline Inspection, Verify lô sạch vs lô bị can thiệp 006, trang truy xuất công khai và liên kết giao dịch trên Avalanche Fuji Explorer). Kịch bản phân bổ từng giây xem tại [docs/COMPETITION_ALIGNMENT.md](docs/COMPETITION_ALIGNMENT.md).
3. **Slide thuyết trình**: Trình bày vấn đề hao hụt trái cây, giải pháp RUL + Smart Contract bằng chứng không thể sửa đổi, mô hình relayer và ma trận chấm điểm.
4. **Minh chứng giao dịch Avalanche Fuji**:
   - Chain ID: `43113` | RPC: `https://api.avax-test.network/ext/bc/C/rpc`
   - Lệnh deploy: `npm run deploy:fuji` (trong thư mục `contracts`)
   - Explorer: `https://testnet.snowtrace.io` (địa chỉ hợp đồng `FruitChain.sol` và các mã giao dịch HARVEST, HANDOFF, INSPECTION).

Trang **Sổ cái** và QR truy xuất công khai hiển thị mạng, địa chỉ contract và link giao dịch. API `GET /api/ledger/network` công khai trạng thái mạng, không trả về khóa ký. Backend ký với vai trò relayer; quyền actor được kiểm tra bằng đăng nhập/RBAC, chưa có liên kết ví riêng cho từng nông hộ.

## Ghi chú

- `LEDGER_MODE=mock` (mặc định) chạy offline; `evm` dùng Hardhat node + `contracts/contracts/FruitChain.sol` (cần `npx hardhat compile`). Nếu node khởi động lại, backend tự seed lại để đồng bộ.
- T-RUL: lô FC-2026-006 có 6 reading bị sửa có chủ đích trong `sensor_readings.csv` nên test tính lại RUL của lô này từ nhiệt độ gốc trong `rul_timeseries.csv`; T-VIOL cũng dùng nhiệt độ gốc đó.
- Contract mở rộng quyền theo ghi chú mục 7: HANDOFF cho mọi bên tham gia, VIOLATION/INSPECTION cho bên tham gia + REGULATOR.
- Python 3.10+ (spec ghi 3.11; mã tương thích cả hai).

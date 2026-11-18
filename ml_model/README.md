# FruitChain ML runtime

Phần này chỉ **nạp model đã train và suy luận**. Không cần dự án trên Desktop, FastAPI cũ, notebook hoặc pipeline huấn luyện để chạy.

```text
ml_model/
├── fruitchain_model.json       # manifest: checkpoint, config, package, file được đưa vào modelHash
├── pyproject.toml              # package Python fruitchain-ml
├── requirements.txt            # dependency suy luận
├── artifacts/strawberry/
│   └── model_d.pt              # checkpoint gốc; không train lại/đổi trọng số
├── configs/strawberry.json     # cấu hình tiền xử lý và giá trị dự phòng
├── samples/
│   ├── manifest.json           # nguồn ảnh, nhãn, SHA-256, output tham chiếu trước refactor
│   └── strawberry/             # fresh.png, midlife.png, expired.png
├── src/fruitchain_ml/
│   ├── runtime.py              # RulPredictor: load → preprocess → predict_hours
│   ├── preprocessing.py        # thuật toán phân đoạn di chuyển từ bản cũ
│   ├── image.py                # đọc ảnh, alpha, resize, ImageNet normalization
│   ├── networks.py             # kiến trúc A/B/C/D; giữ tên layer tương thích state_dict
│   ├── attention.py            # CBAM
│   ├── specs.py                # tên backbone/RNN, không import training config
│   └── __main__.py             # CLI độc lập
└── research/                  # bản cũ: acquisition, EDA, train, evaluation, API, dữ liệu mẫu
```

`research/` là kho tham khảo, không nằm trên đường import của ứng dụng. Giữ lại mã/dữ liệu cũ để không mất tài liệu nghiên cứu. Luồng suy luận và cấu trúc runtime được mô tả bên dưới.

## Chạy độc lập

Tại thư mục gốc repo, sau khi cài `backend/requirements.txt` hoặc `ml_model/requirements.txt`:

```powershell
$env:PYTHONPATH = 'ml_model/src'
py -3.10 -m fruitchain_ml --model-dir ml_model --image ml_model/samples/strawberry/fresh.png --device cpu
Remove-Item Env:PYTHONPATH
```

Không tạo DB, không seed, không khởi động web, không tải backbone từ Internet. Có thể cài package editable bằng `py -3.10 -m pip install -e ml_model --no-deps` rồi dùng `fruitchain-predict --model-dir ml_model --image PATH`. Khi cài package ở nơi khác, truyền rõ `--model-dir` trỏ tới bundle có artifacts/configs/manifest.

Backend tự nhận diện bundle qua `fruitchain_model.json`. Trang Model AI vẫn cho chọn thư mục/checkpoint khác. Adapter nạp package trong namespace riêng từng lần, không thêm research vào `sys.path`, không cần import tên chung `services` hoặc `training`.

## Hợp đồng suy luận

- Checkpoint D hiện tại: MobileNetV2 + CBAM + GRU; `image_size=224`, `seq_len=8`, `fusion_mode=image_only` theo checkpoint.
- Input upload: một ảnh; backend tách quả, nền alpha trắng khi chuẩn hóa, RGB/ImageNet. Để tương thích predictor cũ, **lặp cùng frame 8 lần**. Đây không phải 8 quan sát theo thời gian.
- `predict_hours()` trả RUL giờ sau giải chuẩn hóa target. Backend đổi ngày và chặn giá trị âm; output thô vẫn được giữ trong metadata. NaN/Infinity bị từ chối.
- Model image-only không sử dụng nhiệt độ/độ ẩm. Q10 và hợp nhất RUL cảm biến/ảnh vẫn thuộc backend, không trộn vào runtime ảnh.
- Không có confidence/CI được hiệu chuẩn. Không biến điểm sanity cố định 0.9 trong bản cũ thành xác suất tin cậy. Điểm tách quả chỉ mô tả phân đoạn.
- GrabCut được đặt seed 0 trước mỗi lần preprocess để cùng ảnh có kết quả ổn định. Công thức xử lý ảnh và kiến trúc giữ nguyên, chỉ sửa đường import tương đối.
- Loader dùng `weights_only=True` và `load_state_dict(strict=True)`; sai kiến trúc hoặc thiếu layer sẽ báo lỗi, không nạp một phần âm thầm.

SHA-256 checkpoint gốc: `aa75eb2f1ed19d6b63e22268a94235030f2c029034dc17fea59c738791c98fa7`.

`modelHash` của bundle bao gồm checkpoint, config, manifest và code suy luận. Di chuyển thư mục không đổi hash; thay code/config đổi hash. Vì phạm vi băm mở rộng, modelVersion mới khác bản legacy dù trọng số không đổi. Các sự kiện lịch sử giữ nguyên version/hash cũ.

## Kiểm thử

```powershell
cd backend
py -3.10 -m pytest tests/test_ml_bundle.py tests/test_rul_model_sensitivity.py tests/test_m1b_images.py
```

Test đối chiếu SHA-256 ảnh/ảnh preprocess, output CPU với ba mẫu trước refactor, tính độc lập khi chuyển bundle, provenance khi đổi code, checkpoint thiếu layer, tải ảnh qua API và lựa chọn tắt model qua lần khởi động. Nhãn và output tham chiếu trong sample manifest là dữ liệu hồi quy, không phải bộ đánh giá độ chính xác mô hình.

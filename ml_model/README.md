# Strawberry RUL Engine

Engine dự đoán thời gian sử dụng còn lại của **dâu tây**, được tách từ project **Strawberry-RUL-prediction** và tích hợp vào FruitChain. Engine nạp checkpoint đã huấn luyện để xử lý ảnh và suy luận; giữ nguyên trọng số và luồng dự đoán của model gốc.

## Model dự đoán

Model D gồm **MobileNetV2** trích xuất đặc trưng ảnh, **CBAM** tập trung vào đặc trưng quan trọng, **GRU** xử lý chuỗi đặc trưng và lớp hồi quy trả về **RUL theo giờ**. FruitChain chuyển kết quả sang ngày khi hiển thị.

Luồng xử lý: **ảnh dâu tây → tách quả bằng màu và GrabCut → ảnh 224×224, chuẩn hóa ImageNet → model → RUL**. Với một ảnh tải lên, engine lặp cùng ảnh 8 lần theo định dạng đầu vào của checkpoint. Model hiện tại chỉ dùng ảnh; phần RUL cảm biến và hợp nhất kết quả nằm ở backend FruitChain.

## Cấu trúc

```text
ml_model/
├── fruitchain_model.json       # Khai báo bundle để FruitChain nhận diện và nạp
├── config.json                 # Cấu hình model và xử lý ảnh
├── weights/
│   └── strawberry_rul.pt        # Checkpoint model D đã huấn luyện
├── src/strawberry_rul/
│   ├── runtime.py              # Nạp checkpoint, tiền xử lý và predict_hours()
│   ├── model.py                # MobileNetV2 + CBAM + GRU + lớp hồi quy
│   ├── attention.py            # Channel attention và spatial attention của CBAM
│   ├── preprocessing.py        # Tách quả, tạo mask và lấy vùng ảnh dâu tây
│   ├── image.py                # Đọc ảnh, xử lý alpha, resize và chuyển tensor
│   ├── __main__.py             # Chạy dự đoán bằng dòng lệnh
│   └── __init__.py
├── examples/                   # Ba ảnh kiểm tra và kết quả tham chiếu
├── pyproject.toml              # Package strawberry-rul
└── requirements.txt
```

## Sử dụng

Trong FruitChain, mở **Cài đặt model → Model tích hợp → Nạp model**. Khi chọn thư mục, trỏ tới `ml_model/`.

Chạy độc lập từ thư mục gốc repository, sau khi cài dependency:

```powershell
py -3.10 -m pip install -r ml_model/requirements.txt
$env:PYTHONPATH = 'ml_model/src'
py -3.10 -m strawberry_rul --model-dir ml_model --image ml_model/examples/fresh.png --device cpu
Remove-Item Env:PYTHONPATH
```

Engine trả `rulHours`, `rulDays` và thông tin checkpoint. `examples/reference.json` lưu mã băm ảnh, ảnh sau tiền xử lý và đầu ra tham chiếu để kiểm tra tính nhất quán khi thay đổi mã nguồn. `modelHash` của FruitChain bao gồm trọng số, cấu hình và mã suy luận.

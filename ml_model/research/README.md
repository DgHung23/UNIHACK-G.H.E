# Kho nghiên cứu cũ

Các file ở đây được chuyển từ bản Strawberry đã sao chép vào FruitChain trước refactor; không lấy thêm code bằng cách sửa dự án Desktop. Đây là mã tham khảo và dữ liệu mẫu, không phải phần triển khai ứng dụng.

- `src/strawberry/stage1_5_image_inventory`: kiểm kê/khảo sát ảnh.
- `src/strawberry/stage2_eda`: phân tích dữ liệu.
- `src/strawberry/stage3_preprocessing`: xử lý dữ liệu để train, OCR, labels, split.
- `src/strawberry/training`: training/data/metrics/LOOCV và kiến trúc cũ.
- `src/strawberry/stage5_evaluation`: báo cáo/benchmark nghiên cứu.
- `src/strawberry/api`, `services`, `schemas`, `utils_app`, `src/app.py`: ứng dụng model cũ; FruitChain không khởi động app này.
- `configs`, `data`, `ORIGINAL_README.md`, `requirements.txt`: tài liệu/config và 94 ảnh được sao chép trước đó.
- `migrate_legacy_model.py`: công cụ migration lịch sử có đường dẫn máy cũ; không chạy lại trên cấu trúc hiện tại.

Không train lại trong lần refactor này. Research không chứa đầy đủ dữ liệu/nhãn của dự án gốc nên không được trình bày như một pipeline train có thể tái lập hoàn chỉnh. Nếu cần huấn luyện tiếp, nên làm trong một repository nghiên cứu riêng với data/version/dependency riêng; xuất checkpoint sang bundle runtime.

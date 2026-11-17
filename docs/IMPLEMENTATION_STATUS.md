# Trạng thái tiếp tục FruitChain — 17/11/2026

## Phần đã có khi tiếp nhận từ Claude

Đã có backend FastAPI/SQLite, dữ liệu demo, Q10, kiểm chứng hash, phân quyền, ingest/cảnh báo, React dashboard/chi tiết lô/truy xuất QR và trang Settings chọn thư mục. Adapter đã nhận diện được dự án Strawberry-RUL-prediction. Bộ 25 kiểm thử ban đầu đạt sau khi cài dependency vào Python đang dùng.

## Phần đã hoàn thiện trong lần tiếp tục

- Settings duyệt thư mục trên máy chạy backend hoặc mở hộp chọn Windows; tự quét checkpoint khi thay đường dẫn; khôi phục checkpoint đã lưu; kiểm tra loại quả, đơn vị, thiết bị trước khi nạp.
- Nạp checkpoint mới thất bại vẫn giữ model đang chạy và cấu hình cũ. File cấu hình được thay thế nguyên tử; suy luận được khóa khi đổi model. Từ chối output NaN/Infinity.
- Không sửa hoặc train lại dự án model gốc. Tiền xử lý và predictor được import trực tiếp từ `C:\Users\admin\Desktop\Strawberry-RUL-prediction`.
- Launcher Windows tự chọn Python, kiểm tra dependency, build frontend, báo lỗi build/khởi động và chạy ứng dụng tại `127.0.0.1:8000`.
- Blockchain được bổ sung đường triển khai Avalanche Fuji, ký giao dịch, kiểm tra mạng/contract, custody, actor-wallet và kiểm chứng bằng chứng trực tiếp. Xem [đối chiếu cuộc thi](COMPETITION_ALIGNMENT.md).
- Sổ cái và trang truy xuất công khai hiển thị đúng chế độ offline/local/Avalanche, có liên kết explorer khi dùng Fuji.

## Kiểm chứng đã thực hiện

- Frontend: `npm run build` thành công.
- Backend với `LEDGER_MODE=evm` trên Hardhat local: **39/39 PASS**, gồm tiền xử lý gốc, model ảnh thật, checkpoint lỗi vẫn suy luận tiếp, hash ảnh bị sửa, ingest, RBAC và blockchain.
- Contract: **13/13 Hardhat PASS**; TypeScript contract kiểm tra thành công.
- Chế độ mock: toàn bộ test tương ứng đạt; test đặc thù EVM được bỏ qua có lý do.
- Ứng dụng thật đã khởi động qua `run.ps1`, tự nạp `custom-D-bc26b587` trên CUDA; gọi API chạy thử ảnh thành công. Trang `/`, `/settings`, `/ledger`, `/trace/FC-2026-001` trả HTTP 200. Verify lô 001–005 PASS, lô 006 FAIL đúng kịch bản.
- Chưa kiểm tra giao diện trực quan trong browser: công cụ browser không kết nối được trong phiên này. Build/API không thay thế việc kiểm tra layout trên desktop và mobile.

Báo cáo JUnit và log backend nằm trong `backend/storage/validation/`; log ứng dụng ở `backend/storage/server.stdout.log` và `server.stderr.log`.

## Phần cần trước khi nộp thi

Hiện ứng dụng đang chạy **mock**, chưa có contract hoặc giao dịch Fuji công khai. Cần ví testnet có test AVAX, thực hiện deploy/khởi động backend theo `COMPETITION_ALIGNMENT.md`, ghi giao dịch thực tế và lưu liên kết explorer. Chưa tạo repo GitHub, slides hoặc video; tài liệu đã có danh sách bài nộp và kịch bản demo. Không xem kết quả test Hardhat là bằng chứng đã triển khai Avalanche.

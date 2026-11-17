# Trình diễn can thiệp dữ liệu ngoài giao diện

Web không có nút sửa dữ liệu, khôi phục hoặc kiểm chứng. Dùng web xem lô, số đo, ảnh và sổ cái; dùng SQLite/file ảnh và công cụ audit độc lập để chứng minh sai lệch.

Sửa một bản ghi SQLite là sửa **dữ liệu off-chain** mà máy chủ đang giữ, không phải sửa một block đã được Avalanche xác nhận. Khi bằng chứng đã ghi lên contract, sửa DB không thay đổi hash trên chain. Không mô tả thao tác này là đã sửa lịch sử Avalanche thành công.

## Chuẩn bị

- Dữ liệu bổ sung và script sinh/nạp trên máy nằm trong `.local/`, được Git bỏ qua. UI luôn đọc API/DB, không nhúng danh sách lô hoặc chỉ số giả trong component. `demo_data/` là fixture chuẩn có sẵn cho kiểm thử hồi quy, tách khỏi dữ liệu cục bộ.
- Bộ cục bộ đã kiểm tra có 42 lô, 3.187 số đo, 211 sự kiện trước khi tải thêm ảnh, 33 đơn vị, 34 tài khoản và 7 cảnh báo. Đây là dữ liệu trình diễn, không phải số đo thực địa đã được xác thực.
- Dùng `LEDGER_MODE=evm` để có nguồn bằng chứng độc lập với DB. Hardhat local phục vụ kiểm thử; để trình bày tích hợp Avalanche công khai, deploy Fuji theo [COMPETITION_ALIGNMENT.md](COMPETITION_ALIGNMENT.md).

Cấu hình thử độc lập, không ghi đè DB đang dùng:

```powershell
# Terminal 1
cd contracts
npm run node
```

```powershell
# Terminal 2, bắt đầu từ thư mục gốc repo
$env:LEDGER_MODE = 'evm'
$env:EVM_RPC = 'http://127.0.0.1:8545'
$env:DATABASE_URL = "sqlite:///$((Join-Path $PWD '.local/presentation.db').Replace('\','/'))"
$env:STORAGE_DIR = '../.local/runtime'
$env:DEMO_DATA_DIR = '../.local/dataset'
cd backend
py -3.10 -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

`.local/dataset` phải tồn tại và không được đưa lên GitHub. Trên checkout mới, bỏ `DEMO_DATA_DIR` để dùng fixture `demo_data/`. Giữ DB và node trong suốt trình diễn; không reset/seed giữa phần trước và sau can thiệp.

Sau crash/restart máy, Hardhat mặc định có thể mất trạng thái chain dù SQLite/ảnh còn nguyên. Backend sẽ giữ DB và từ chối tự seed khi không tìm thấy contract. Không coi receipt cũ là giao dịch tồn tại trên một node mới; cần khôi phục snapshot node hoặc chủ động chuẩn bị một bản trình diễn mới sau khi sao lưu.

Terminal audit cần cùng `LEDGER_MODE`, `EVM_RPC`, `DATABASE_URL`, `STORAGE_DIR` như backend. Các lệnh sau chạy tại thư mục gốc repo. CLI đọc `backend/.env` và biến môi trường; không tự seed, không nạp model, không gửi giao dịch. Vì `STORAGE_DIR` tương đối được tính từ `backend`, giữ giá trị `../.local/runtime` ở cả hai terminal.

## 1. Kiểm tra trước can thiệp

```powershell
py -3.10 tools/check_integrity.py
# Chọn mã lô PASS có sự kiện HANDOFF, rồi chạy riêng:
py -3.10 tools/check_integrity.py --batch-id THAY_MA_LO --json
```

Mã thoát: `0` = tất cả lô yêu cầu PASS; `1` = có sai lệch; `2` = cấu hình/lỗi kết nối/không thấy lô. Audit toàn bộ fixture chuẩn trả `1` vì lô 006 cố ý bị sửa; chọn lô sạch cho phần trước/sau.

`--database .local/presentation.db` chọn SQLite rõ ràng, nhưng vẫn phải dùng đúng ledger/network và `STORAGE_DIR` chứa deployment tương ứng. Với mock, CLI ghi rõ ledger nằm trong cùng DB và không phải bằng chứng độc lập trên Avalanche.

## 2. Sửa trực tiếp số đo bằng SQL

Mở `.local/presentation.db` bằng SQLite editor trong IDE hoặc DB Browser for SQLite. Sao lưu DB và ghi lại bản ghi sẽ sửa. Chọn số đo đã neo trong HANDOFF; số đo mới nhất có thể chưa thuộc đoạn đã được neo.

Thay `THAY_MA_LO` bằng mã lô đã chọn:

```sql
SELECT r.id, r.batch_id, r.ts, r.temp_c, r.device_sig
FROM sensor_readings AS r
JOIN ledger_events AS e ON e.batch_id = r.batch_id
WHERE e.type = 'HANDOFF'
  AND r.batch_id = 'THAY_MA_LO'
  AND r.ts BETWEEN json_extract(e.payload, '$.fromReading')
               AND json_extract(e.payload, '$.toReading')
ORDER BY e.block_number, r.ts
LIMIT 1;
```

Ghi lại `id` và `temp_c`. UPDATE đúng id đó rồi lưu/commit trong editor:

```sql
UPDATE sensor_readings SET temp_c = temp_c + 7.0 WHERE id = THAY_ID;
```

Không đổi `device_sig`, `ledger_events`, `event_hash` hoặc `data_hash`. Mở lại tab Cảm biến trên web để thấy giá trị mới. RUL đã lưu không tự tính lại khi sửa bằng SQL vì thao tác này bỏ qua ingest hợp lệ.

```powershell
py -3.10 tools/check_integrity.py --batch-id THAY_MA_LO --json
```

Mong đợi: `overall=FAIL`, chữ ký số đo sai và hash đoạn HANDOFF không khớp. Sửa CSV sau khi seed không đổi DB đang chạy, vì vậy cần sửa SQLite hoặc file ảnh thực tế.

## 3. Khôi phục và kiểm tra lại

```sql
UPDATE sensor_readings SET temp_c = GIA_TRI_GOC WHERE id = THAY_ID;
```

Commit rồi audit: lô sạch ban đầu phải PASS. Không dùng seed để khôi phục vì nó tạo lại dữ liệu/bằng chứng thay vì đối chiếu cùng bằng chứng cũ.

## Phương án khác: tráo file ảnh

1. Upload ảnh hợp lệ ở tab Ảnh kiểm tra để có INSPECTION thật.
2. Truy vấn `SELECT inspection_id, raw_image_path, image_hash FROM inspections WHERE batch_id='THAY_MA_LO';`.
3. Sao lưu file `raw_image_path`. Dùng editor ảnh sửa/lưu lại chính file gốc đó; giữ đường dẫn và bản ghi DB.
4. Audit CLI: INSPECTION phải FAIL vì hash byte của ảnh khác hash đã neo.
5. Chép lại đúng byte bản sao lưu, audit lại phải PASS. Không chỉ sửa ảnh preprocessed vì INSPECTION neo ảnh gốc.

## Đã kiểm tra thực tế

Trên Hardhat local: sửa một số đo đã neo bằng SQLite, PASS → FAIL (1 chữ ký sai, đúng đoạn HANDOFF lệch) → khôi phục → PASS. Hash và giao dịch gốc không đổi. Báo cáo trên máy ở `.local/qa/integrity-*.json`; dữ liệu/bản sao lưu không commit.

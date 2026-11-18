# FruitChain

**Theo dõi độ tươi, quản lý chuỗi lạnh và truy xuất hành trình trái cây.**

FruitChain kết hợp dữ liệu bảo quản, AI dự đoán thời gian sử dụng còn lại và bằng chứng blockchain trong một nền tảng quản lý lô hàng. Từ lúc thu hoạch đến khi bán, mỗi lô trái cây có hồ sơ về nguồn gốc, bên đang giữ hàng, điều kiện vận chuyển và các lần kiểm tra chất lượng. Người tiêu dùng có thể mở hồ sơ qua mã QR.

## FruitChain giúp giải quyết điều gì?

Hạn sử dụng ghi trên nhãn chưa phản ánh đầy đủ những gì xảy ra trong quá trình bảo quản. Một lô trái cây trải qua nhiệt độ cao hoặc vận chuyển kéo dài có thể giảm chất lượng nhanh hơn dự kiến. Khi thông tin nằm rải rác giữa nông hộ, đơn vị vận chuyển, kho và cửa hàng, việc xác định lô cần ưu tiên xử lý cũng trở nên khó khăn.

FruitChain tập hợp các thông tin đó theo từng lô để hỗ trợ:

- **Giảm hao hụt:** dùng RUL — Remaining Useful Life, thời gian sử dụng còn lại được ước tính — để cân nhắc ưu tiên phân phối và tiêu thụ.
- **Theo dõi chuỗi lạnh:** xem diễn biến nhiệt độ, độ ẩm, vị trí và những lần vượt ngưỡng bảo quản.
- **Làm rõ trách nhiệm:** biết lô đã đi qua những bên nào, được bàn giao lúc nào và có những sự kiện chất lượng nào.
- **Minh bạch nguồn gốc:** cung cấp hồ sơ truy xuất công khai cùng liên kết giao dịch khi dùng mạng blockchain có explorer.

## Tính năng chính

### Quản lý vòng đời lô hàng

Tạo lô với thông tin sản phẩm, nơi trồng, thời điểm thu hoạch, khối lượng và chứng nhận. Theo dõi trạng thái qua các bước thu hoạch, vận chuyển, lưu kho, phân phối, bán lẻ và bán hàng. Mỗi lần bàn giao được lưu trong dòng thời gian của lô.

### Ước tính thời gian sử dụng còn lại

Theo dõi RUL theo lịch sử nhiệt độ bằng mô hình Q10, đồng thời hỗ trợ tải ảnh để suy luận bằng model đã huấn luyện. Model ảnh tích hợp hiện hỗ trợ **dâu tây**, sử dụng MobileNetV2, CBAM và GRU. Backend có thể kết hợp kết quả từ ảnh và cảm biến theo chế độ cấu hình.

Quản trị viên có thể chọn thư mục model, nạp checkpoint và chạy thử ảnh ngay trên giao diện. Runtime và trọng số được đóng gói trong dự án, không phụ thuộc thư mục nghiên cứu bên ngoài. Chi tiết tại [ML runtime](ml_model/README.md).

### Giám sát bảo quản và vận chuyển

Dashboard tổng hợp tình trạng các lô, độ tươi và các sự kiện gần đây. Biểu đồ thể hiện nhiệt độ, độ ẩm và RUL theo thời gian; bản đồ cho phép xem vị trí các lô hoặc hành trình của một lô.

Bản đồ có chế độ thường và vệ tinh, cuộn/chụm để thu phóng, gom các lô gần nhau và xem toàn màn hình. Lớp nhãn Việt Nam hiển thị **Hoàng Sa** và **Trường Sa** bằng tiếng Việt.

### Bằng chứng blockchain

Các sự kiện như thu hoạch, bàn giao, vi phạm điều kiện bảo quản, kiểm tra ảnh và bán hàng được liên kết bằng mã băm. Dữ liệu chi tiết lưu ngoài chuỗi; mã băm của dữ liệu, ảnh và phiên bản model giúp đối chiếu với bằng chứng đã ghi nhận để phát hiện thay đổi.

Smart contract Solidity hỗ trợ mạng EVM, với cấu hình triển khai trên **Avalanche Fuji** và môi trường phát triển Hardhat. Sổ cái hiển thị mạng đang sử dụng, địa chỉ hợp đồng và liên kết giao dịch khi có explorer. Backend gửi giao dịch qua relayer và kiểm tra quyền thao tác theo tài khoản, vai trò và bên đang giữ lô.

### Truy xuất công khai bằng QR

Mỗi lô có trang truy xuất riêng, mở được bằng mã QR mà không cần đăng nhập. Người xem có thể tìm hiểu nơi sản xuất, thời điểm thu hoạch, chứng nhận, hành trình và RUL được ước tính.

### Phân quyền theo vai trò

Hỗ trợ nông hộ, đơn vị vận chuyển, kho, nhà phân phối, cửa hàng, bên giám sát và quản trị viên. Quyền tạo lô, bàn giao, kiểm tra chất lượng và cấu hình model được kiểm soát theo vai trò.

## Luồng sử dụng

1. **Khởi tạo lô:** ghi nhận sản phẩm, nguồn gốc và thông tin thu hoạch.
2. **Theo dõi bảo quản:** tiếp nhận dữ liệu cảm biến, cập nhật RUL và ghi nhận các lần vượt ngưỡng.
3. **Bàn giao:** chuyển bên giữ lô và lưu dấu mốc trong hành trình.
4. **Kiểm tra bằng ảnh:** tải ảnh trái cây, chạy model và lưu kết quả kèm mã băm ảnh/model.
5. **Truy xuất:** quét QR để xem hồ sơ và các mốc trước khi lô được bán.

## Tech stack

| Thành phần | Công nghệ |
| --- | --- |
| Giao diện | React 18, TypeScript, Vite, Tailwind CSS |
| Dữ liệu giao diện | TanStack Query, React Router |
| Biểu đồ và bản đồ | Recharts, Leaflet, React Leaflet |
| Lớp bản đồ | NARENCA WMS, Esri World Imagery |
| Backend/API | Python, FastAPI, Uvicorn, Pydantic |
| Lưu trữ | SQLite, SQLAlchemy; lưu file ảnh và cấu hình model ngoài chuỗi |
| Xác thực | JWT, bcrypt, phân quyền theo vai trò |
| AI và xử lý ảnh | PyTorch, Torchvision, OpenCV, NumPy, Pillow |
| Blockchain | Solidity, Avalanche/EVM, Hardhat, Web3.py, ethers.js |
| Mã QR | qrcode.react |
| Kiểm thử | pytest, Hardhat, Chai |

## Cấu trúc dự án

```text
fruitchain/
├── frontend/       # Dashboard, quản lý lô, bản đồ và trang truy xuất
├── backend/        # API, xác thực, dữ liệu cảm biến, RUL và tích hợp blockchain
├── contracts/      # Smart contract Solidity, script triển khai và kiểm thử
├── ml_model/       # Runtime suy luận, checkpoint, cấu hình và mã nghiên cứu
├── demo_data/      # Dữ liệu khởi tạo ứng dụng
├── tools/          # Công cụ kiểm tra tính toàn vẹn dữ liệu
└── run.ps1         # Khởi động ứng dụng trên Windows
```

## Chạy ứng dụng

Cần **Python 3.10 trở lên**, **Node.js** và **npm**. Từ thư mục gốc repository trên Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Script chuẩn bị dependency, build frontend và khởi động ứng dụng tại **http://127.0.0.1:8000**. Tài khoản quản trị để trải nghiệm cục bộ: `admin` / `demo1234`.

Mặc định ứng dụng dùng sổ cái cục bộ (`LEDGER_MODE=mock`). Để ghi giao dịch lên blockchain, cấu hình `LEDGER_MODE=evm`, RPC, khóa relayer và hợp đồng tương ứng. Các lớp bản đồ cần Internet để tải nền và nhãn; không cần API key ở cấu hình hiện tại.

Để phát triển giao diện riêng, chạy `npm install` và `npm run dev` trong `frontend/`; Vite phục vụ tại **http://localhost:5173** và chuyển tiếp `/api` đến backend tại cổng 8000.

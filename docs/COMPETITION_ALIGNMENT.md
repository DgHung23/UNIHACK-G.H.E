# FruitChain — đối chiếu Team1 Vietnam UniHack

Cập nhật luồng UI: tab/nút kiểm chứng và các nút giả lập đã được loại bỏ. Phần demo toàn vẹn thực hiện bằng sửa SQLite/file ảnh và audit trên terminal theo [DEMO_DATA_INTEGRITY.md](DEMO_DATA_INTEGRITY.md); các nhắc đến Verify bên dưới được hiểu là công cụ audit này.

Kiểm tra ngày **17/11/2026, UTC+7**. Nguồn chính: [team1vn.xyz](https://team1vn.xyz/) (FAQ + Judging Criteria). Website đọc được bằng `curl.exe -L -A "Mozilla/5.0" https://team1vn.xyz/`; công cụ tìm kiếm không đọc được trang này tại thời điểm kiểm tra.

## Quy định đã xác nhận và điểm cần chú ý

- Sinh viên tại Việt Nam, đội từ 1 đến **3 người**.
- Được dùng ý tưởng riêng hoặc dự án có sẵn. Cần đưa một chức năng thực tế lên **Avalanche L1, Fuji hoặc C-Chain**; các chủ đề gợi ý không bắt buộc.
- Website hiện ghi hạn nộp **23:59 ngày 21/11/2026, giờ Việt Nam**.
- Nộp tại hồ sơ trên team1vn.xyz; chuẩn bị repo GitHub, liên kết slides, video demo **2–3 phút**. Repo private cần mời `tuantqse90`; mọi liên kết phải mở được cho giám khảo.

Nguồn: [FAQ cuộc thi](https://team1vn.xyz/).

**Nguồn có mâu thuẫn:** [trang sự kiện Avalanche Builder Hub](https://docs.avax.network/events/596c0b2d-63aa-4cf0-a0ad-a7e34ddbfdc0) còn ghi hạn 25/11 và lịch sự kiện khác. Tài liệu này chọn mốc sớm hơn trên website mà người dùng chỉ định. Trước khi nộp, đội cần kiểm tra lại thông báo của ban tổ chức; không dựa vào mốc 25/11 để trì hoãn. Thông tin trang thử nghiệm `ecosystem-hub-test` và bài tổng hợp bên thứ ba không dùng làm quy định.

## Ma trận chấm điểm và phần sản phẩm đáp ứng

| Tiêu chí website | Điểm | Bằng chứng trong FruitChain | Cần hoàn tất trước khi nộp |
|---|---:|---|---|
| Technical Implementation | 25 | FastAPI + DB; model ảnh đã train; hash ảnh/cảm biến; kiểm tra chuỗi sự kiện; contract có kiểm soát quyền và custody | Chạy test và trình diễn luồng upload ảnh thật |
| Avalanche Integration | 25 | Contract Solidity; adapter ký giao dịch; cấu hình Fuji 43113; đọc hash trực tiếp từ contract khi Verify; đường dẫn explorer | **Deploy Fuji và cung cấp địa chỉ/tx thật** |
| Creativity & Innovation | 15 | Gắn phiên bản/hash model và bằng chứng ảnh với dự đoán RUL trong vòng đời lô | Slides giải thích lợi ích so với QR chỉ lưu DB |
| Impact & Use Case | 15 | Phát hiện sửa dữ liệu chuỗi lạnh; giúp ưu tiên bán lô sắp hết hạn | Trình bày đối tượng dùng và giả thuyết giảm hao hụt; không bịa số đo hiệu quả |
| Presentation & Pitching | 10 | Kịch bản demo phía dưới | Slides, video, phần trả lời câu hỏi |
| UI/UX & Demo | 10 | Chọn folder model, upload ảnh, timeline, Verify, truy xuất công khai, trạng thái mạng | Quay video luồng thực tế trên Fuji |

Điểm và quy định lấy từ [website ban tổ chức](https://team1vn.xyz/); cột bằng chứng là đánh giá triển khai của dự án, không phải cam kết được ban giám khảo công nhận.

## Kiến trúc blockchain sau thay đổi

`React → FastAPI → EvmLedger → giao dịch ký cục bộ → Avalanche Fuji → FruitChain.sol`

DB giữ dữ liệu đầy đủ. Contract giữ hash bằng chứng, hash sự kiện/prevHash, actor, timestamp, RUL snapshot và modelHash. File ảnh và dữ liệu cảm biến không đưa nguyên bản lên mạng công khai.

- **Mock**: sổ cái nằm trong cùng SQLite, chạy offline. Trạng thái mạng nói rõ đây là mô phỏng, không đủ để chứng minh đã tích hợp Avalanche.
- **Hardhat**: chạy contract EVM thật trên máy để kiểm thử; chưa phải Avalanche. Các test tích hợp được chạy trên mạng này.
- **Fuji**: lựa chọn triển khai dự thi; có giao dịch và địa chỉ contract công khai, phí bằng test AVAX. Adapter nhận `EVM_PRIVATE_KEY`, ký trong backend rồi gửi raw transaction. Khóa không nằm trong React hoặc API trạng thái.

Nguồn cấu hình mạng: [Avalanche Primary Network](https://build.avax.network/docs/primary-network), [C-Chain RPC](https://build.avax.network/docs/rpcs/c-chain). Fuji: chain ID `43113`, RPC `https://api.avax-test.network/ext/bc/C/rpc`. Compiler dùng Solidity 0.8.24, EVM `cancun`.

### Ràng buộc contract

- Quyền theo vai trò; quản lý vai trò có log.
- Ví gọi trực tiếp phải được admin gắn với actor qua `registerActor(actorId, wallet)`; không được giả tên actor của ví khác.
- HARVEST tạo lô duy nhất. HANDOFF phải xuất phát từ actor đang giữ lô, có bên nhận khác bên gửi. SOLD phải do actor đang giữ lô khai báo; lô đã SOLD không nhận thêm sự kiện.
- `prevHash` phải nối đúng head; không nhận hash bằng 0, hash sự kiện tái sử dụng hoặc timestamp lùi.
- Model phải được đăng ký trước khi sử dụng; modelHash gắn phiên bản bất biến.
- Verify đọc hash từ contract thay vì tin bản sao hash trong DB. Nếu DB thiếu một hoặc tất cả sự kiện trong khi chain còn dữ liệu, kết quả FAIL.

### Mô hình tin cậy cần giải thích khi pitching

Ứng dụng hiện dùng **backend relayer có quyền ADMIN** để ghi thay người dùng đã đăng nhập. Contract lưu `actor = địa chỉ relayer`; `actorId` là chủ thể nghiệp vụ được backend xác thực. Quy tắc custody vẫn áp dụng với relayer, nhưng ADMIN được miễn ràng buộc actor–wallet để chuyển tiếp sự kiện cho nhiều chủ thể.

Điều này không phải cơ chế từng nông hộ tự ký bằng ví. Contract đã có đường gọi trực tiếp với ví/actor được đăng ký, nhưng UI hiện chưa cung cấp MetaMask/Core hoặc chữ ký EIP-712. Không trình bày luồng relayer như chữ ký ví độc lập của người nông dân.

Hash giúp phát hiện sửa dữ liệu **sau khi ghi**. Nó không chứng minh ảnh/cảm biến đầu vào là thật hoặc model dự đoán chính xác. Chữ ký thiết bị trong bộ demo là cơ chế minh họa dùng khóa demo; dữ liệu sản xuất cần khóa thiết bị riêng và xác thực nguồn đo. Khoảng tin cậy Q10 là giả định demo; model ảnh trả RUL đã train, không tự bịa khoảng tin cậy.

## Chạy và deploy Fuji

Các bước dưới đây chuẩn bị việc deploy bằng ví testnet của đội. **Chưa có contract Fuji hoặc giao dịch công khai nào được tạo trong lần sửa này** vì chưa có ví testnet được cấp.

### 1. Kiểm thử local

```powershell
cd C:\Users\admin\Downloads\fruitchain\fruitchain\contracts
npm install --legacy-peer-deps
npm test
npx tsc --noEmit
npm run node
```

Trong terminal khác, dùng Python đã cài dependency của ứng dụng:

```powershell
cd C:\Users\admin\Downloads\fruitchain\fruitchain\backend
$env:LEDGER_MODE = 'evm'
$env:EVM_RPC = 'http://127.0.0.1:8545'
python -m pytest
Remove-Item Env:LEDGER_MODE
Remove-Item Env:EVM_RPC
```

Test tạo DB/storage tạm riêng và deploy contract thử trên Hardhat. Không sử dụng tiền thật.

### 2. Chuẩn bị ví Fuji và deploy

Lấy test AVAX từ [Avalanche Faucet](https://build.avax.network/console/primary-network/faucet). Dùng khóa của ví test riêng; không dùng khóa mẫu của Hardhat trên mạng công khai.

```powershell
cd C:\Users\admin\Downloads\fruitchain\fruitchain\contracts
$env:EVM_RPC = 'https://api.avax-test.network/ext/bc/C/rpc'
# Nhập khóa ví test trong terminal riêng, không đưa khóa vào mã nguồn hoặc VITE_*.
$walletKey = Read-Host 'Fuji test wallet private key' -AsSecureString
$env:EVM_PRIVATE_KEY = [System.Net.NetworkCredential]::new('', $walletKey).Password
npm run deploy:fuji
Remove-Item Env:EVM_PRIVATE_KEY
Remove-Variable walletKey
Remove-Item Env:EVM_RPC
```

Script chỉ cho deploy chain local hoặc Fuji; in ra địa chỉ, chainId, deployment block, txHash và explorer. Bản ghi deployment không chứa khóa riêng. Ghi lại `address` và `blockNumber` để cấu hình backend; chúng cần khớp đúng network. Script lưu bản ghi ở `backend/storage/evm_deployment.json`; cấu hình Fuji bên dưới dùng `storage/fuji`, nên cần điền địa chỉ/block rõ ràng.

### 3. Backend dùng DB riêng cho Fuji

```powershell
cd C:\Users\admin\Downloads\fruitchain\fruitchain\backend
Copy-Item .env.fuji.example .env
```

Điền `EVM_CONTRACT_ADDRESS`, `EVM_DEPLOYMENT_BLOCK`, `EVM_PRIVATE_KEY`, và thay `JWT_SECRET`. Chạy backend từ thư mục `backend` để `DATABASE_URL=sqlite:///./fruitchain-fuji.db` trỏ đúng nơi. Không dùng DB mock đang có cho contract mới.

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Lần đầu với DB Fuji rỗng, seed đăng ký model và ghi 29 sự kiện demo lên contract đã deploy. Dữ liệu cố ý bị sửa của lô 006 giữ nguyên để demo Verify FAIL. Khởi động lại với DB/contract cũ không gửi lại seed. Nếu khôi phục DB rỗng từ contract chứa đúng seed, adapter tái sử dụng receipt và không phát giao dịch trùng. Nếu contract có thêm sự kiện ngoài seed, khôi phục demo bị từ chối để tránh mất dữ liệu off-chain; cần phục hồi bản sao lưu DB đầy đủ.

Backend kiểm tra chain ID, runtime bytecode contract, số sự kiện/head và receipt của DB khi mở mạng công khai. Sai cấu hình sẽ dừng và giữ nguyên DB. API reset/seed trả 409 khi đang dùng chain công khai; tự deploy chỉ dành cho local. Các guard này ngăn thao tác demo xoá nhầm DB đang gắn bằng chứng không thể xoá trên chain.

Nếu đã có DB Fuji đầy đủ và chỉ cần đọc/Verify, có thể để trống khóa riêng. Giao diện vẫn hiển thị network; ghi sự kiện sẽ báo cần khóa ký. Không để `AUTO_SEED=1` với DB rỗng nếu chỉ muốn xem dữ liệu của một contract đã có sự kiện ngoài seed.

### 4. Bằng chứng bắt buộc tự kiểm tra trước khi nộp

1. `GET /api/ledger/network` có `mode=evm`, `chainId=43113`, `ready=true`, `isCompetitionNetwork=true` và đúng địa chỉ contract.
2. Mở contract và ít nhất một giao dịch HARVEST, HANDOFF, INSPECTION trên explorer; kiểm tra status thành công.
3. Upload ảnh dâu tây bằng model thật; đối chiếu imageHash, modelHash, eventHash trong luồng Inspection.
4. Verify lô 001 PASS và lô 006 FAIL; giải thích 2 đoạn lệch + 6 chữ ký thiết bị sai của dữ liệu demo.
5. Mở link truy xuất công khai không đăng nhập. Chụp phần network Fuji và liên kết giao dịch làm minh chứng.

## Kịch bản video 2–3 phút

- **0:00–0:25**: vấn đề hao hụt trái cây và lý do cần chứng cứ không thể sửa sau khi ghi; giới thiệu RUL.
- **0:25–0:55**: Settings chọn folder Strawberry-RUL-prediction, production checkpoint; test ảnh để thấy model thật được tải và chạy.
- **0:55–1:30**: mở lô dâu tây, upload ảnh kiểm tra; xem RUL và timeline Inspection. Mở giao dịch Fuji trên explorer.
- **1:30–2:05**: so sánh Verify lô sạch với lô 006 cố ý sửa dữ liệu; nêu rõ chain lưu hash, DB giữ ảnh/cảm biến.
- **2:05–2:35**: QR/truy xuất công khai và quyết định ưu tiên bán lô RUL thấp; trình bày relayer và giới hạn oracle trung thực.
- **2:35–3:00**: hướng mở rộng xác thực thiết bị, ví từng actor và số đo thực địa; kết thúc bằng địa chỉ contract/repo.

Không cần tự thêm token, NFT, thanh toán, x402 hay Avalanche L1 riêng chỉ để có thêm thuật ngữ: chúng không phải yêu cầu bắt buộc đã thấy trên website, và smart contract bằng chứng là phần tích hợp thực tế của sản phẩm này.

## Kết quả kiểm thử phần blockchain trong lần tiếp tục này

- Hardhat: **13 test PASS**, gồm actor wallet, custody, quyền, khóa lô SOLD, prevHash, model bất biến, hash rỗng/tái sử dụng và timestamp lùi.
- `npx tsc --noEmit` trong `contracts`: PASS.
- `tests/test_blockchain.py`: **9 test PASS khi chạy EVM local**; chế độ mock có 4 PASS và 5 test EVM được skip có lý do.
- Các test EVM bao gồm giao dịch ký thật bằng ví mới không được node unlock; phát hiện thiếu toàn bộ/một phần sự kiện DB; sai chainId; không tự deploy trên mạng công khai; không trả khóa ký ở API; chặn reset công khai; replay khôi phục dùng receipt cũ mà không phát giao dịch trùng.

Các kết quả trên là test local. Chỉ sau khi đội thực hiện phần deploy và mở receipt Fuji mới có thể tuyên bố dự án đã chạy trên Avalanche công khai.

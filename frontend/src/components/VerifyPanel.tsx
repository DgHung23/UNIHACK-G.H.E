/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, EVENT_LABEL } from "../api/client";
import { ErrorBox, Hash } from "./ui";

export default function VerifyPanel({ batchId }: { batchId: string }) {
  const qc = useQueryClient();
  const [showComparison, setShowComparison] = useState(false);
  const [tamperMsg, setTamperMsg] = useState<{ title: string; text: string; type: "warn" | "success" } | null>(null);

  const verifyMut = useMutation({
    mutationFn: () => api(`/batches/${batchId}/verify`, { method: "POST" }),
  });

  const tamperMut = useMutation({
    mutationFn: (type: "sensor" | "image") =>
      api(`/batches/${batchId}/simulate-tamper`, {
        method: "POST",
        body: { tamperType: type },
      }),
    onSuccess: (data: any) => {
      setTamperMsg({
        title: "⚠️ Dữ liệu Database đã bị can thiệp trực tiếp!",
        text: data.message || "Đã can thiệp dữ liệu trong DB. Hãy bấm 'Verify' để xem Blockchain phát hiện sự gian lận này!",
        type: "warn",
      });
      ["batch", "batches", "events"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      verifyMut.mutate();
    },
  });

  const restoreMut = useMutation({
    mutationFn: () => api(`/batches/${batchId}/restore-tamper`, { method: "POST" }),
    onSuccess: (data: any) => {
      setTamperMsg({
        title: "✔ Đã khôi phục dữ liệu gốc!",
        text: data.message || "Dữ liệu lô hàng đã được hoàn nguyên về trạng thái ban đầu.",
        type: "success",
      });
      ["batch", "batches", "events"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      verifyMut.mutate();
    },
  });

  const r: any = verifyMut.data;

  return (
    <div className="space-y-6">
      {/* 1. Phần giới thiệu & So sánh Blockchain vs DB thường */}
      <div className="rounded-xl border border-slate-200 bg-gradient-to-r from-slate-50 to-indigo-50/40 p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-slate-800">
              Kiểm chứng Tính toàn vẹn Dữ liệu (Cryptographic Audit)
            </h3>
            <p className="mt-1 text-sm text-slate-600">
              Đối chiếu từng bản ghi nhiệt độ, ảnh chụp và sự kiện trong CSDL với Smart Contract bất biến trên Avalanche Fuji.
            </p>
          </div>
          <button
            type="button"
            className="rounded-lg border border-indigo-200 bg-white px-3 py-1.5 text-xs font-medium text-indigo-700 shadow-sm transition hover:bg-indigo-50"
            onClick={() => setShowComparison(!showComparison)}
          >
            {showComparison ? "Ẩn bảng so sánh" : "📊 So sánh CSDL thường vs Blockchain"}
          </button>
        </div>

        {/* Bảng so sánh trực quan */}
        {showComparison && (
          <div className="mt-4 overflow-x-auto rounded-lg border border-indigo-100 bg-white p-4">
            <h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-indigo-900">
              Sự khác biệt cốt lõi giữa Lưu trữ Thông thường và Blockchain
            </h4>
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-700">
                  <th className="py-2 font-semibold">Tiêu chí</th>
                  <th className="py-2 font-semibold text-amber-700">Lưu trữ CSDL thông thường (SQL / Cloud DB)</th>
                  <th className="py-2 font-semibold text-emerald-700">FruitChain trên Avalanche Fuji (Blockchain)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                <tr>
                  <td className="py-2 font-medium text-slate-800">Tính minh bạch</td>
                  <td className="py-2 text-slate-600">Dữ liệu khép kín trong máy chủ nội bộ; người mua phải tin tưởng lời bên bán.</td>
                  <td className="py-2 text-emerald-800">Công khai, minh bạch on-chain; bất kỳ ai cũng có thể tra cứu qua Snowtrace Explorer.</td>
                </tr>
                <tr>
                  <td className="py-2 font-medium text-slate-800">Khả năng sửa đổi (Immutability)</td>
                  <td className="py-2 text-slate-600">
                    <span className="font-semibold text-red-600">Dễ bị làm giả:</span> Admin hoặc hacker có thể UPDATE/DELETE bản ghi âm thầm mà không để lại dấu vết.
                  </td>
                  <td className="py-2 text-emerald-800">
                    <span className="font-semibold text-emerald-600">Bất biến (Immutable):</span> Smart Contract không thể bị sửa đổi; hàm băm Merkle khoá chặt lịch sử.
                  </td>
                </tr>
                <tr>
                  <td className="py-2 font-medium text-slate-800">Phát hiện vi phạm chuỗi lạnh</td>
                  <td className="py-2 text-slate-600">Nếu tài xế sửa lại file log nhiệt độ để tránh phạt, CSDL thường sẽ chấp nhận và giấu nhẹm lỗi.</td>
                  <td className="py-2 text-emerald-800">Chữ ký phần cứng (Device Signature) + Merkle Segment Hash phát hiện ngay lập tức bất kỳ reading nào bị sửa.</td>
                </tr>
                <tr>
                  <td className="py-2 font-medium text-slate-800">Gian lận ảnh kiểm tra</td>
                  <td className="py-2 text-slate-600">Có thể tráo file ảnh dâu thối thành dâu tươi trực tiếp trên ổ cứng mà giao diện vẫn hiển thị bình thường.</td>
                  <td className="py-2 text-emerald-800">Mỗi ảnh được băm SHA-256 đưa vào on-chain event. Thay đổi 1 pixel là Verify FAIL ngay.</td>
                </tr>
                <tr>
                  <td className="py-2 font-medium text-slate-800">Trách nhiệm pháp lý (Custody)</td>
                  <td className="py-2 text-slate-600">Chỉ là một trường văn bản trong DB, không có chữ ký ràng buộc quyền sở hữu.</td>
                  <td className="py-2 text-emerald-800">Bàn giao (HANDOFF) yêu cầu xác nhận ví điện tử và kiểm tra người giữ lô hiện tại.</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 2. KHU VỰC DEMO TRÌNH DIỄN GIAN LẬN (Live Interactive Tamper Demo) */}
      <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4 shadow-sm">
        <div className="flex items-center gap-2 text-sm font-semibold text-amber-900">
          <span>🧪 Khu vực Trình diễn Demo (Dành cho Pitching & Giám khảo)</span>
        </div>
        <p className="mt-1 text-xs text-amber-800">
          Hãy bấm thử nút <b>Can thiệp CSDL</b> để mô phỏng một kẻ xấu sửa trực tiếp dữ liệu trong Database. Sau đó bấm <b>Verify</b> để chứng kiến Blockchain vạch trần hành vi gian lận như thế nào!
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-amber-700 disabled:opacity-50"
            onClick={() => tamperMut.mutate("sensor")}
            disabled={tamperMut.isPending}
          >
            {tamperMut.isPending ? "Đang xử lý…" : "🚨 Giả lập sửa nhiệt độ DB (+12.5°C)"}
          </button>
          <button
            type="button"
            className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:bg-rose-700 disabled:opacity-50"
            onClick={() => tamperMut.mutate("image")}
            disabled={tamperMut.isPending}
          >
            {tamperMut.isPending ? "Đang xử lý…" : "🚨 Giả lập tráo đổi ảnh kiểm tra"}
          </button>
          <button
            type="button"
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-100 disabled:opacity-50"
            onClick={() => restoreMut.mutate()}
            disabled={restoreMut.isPending}
          >
            {restoreMut.isPending ? "Đang khôi phục…" : "🔄 Khôi phục dữ liệu gốc"}
          </button>
          <button
            type="button"
            className="btn-primary !py-1.5 !text-xs font-bold shadow-md"
            onClick={() => verifyMut.mutate()}
            disabled={verifyMut.isPending}
          >
            {verifyMut.isPending ? "Đang kiểm chứng…" : "🔍 Kiểm chứng Blockchain (Verify)"}
          </button>
        </div>

        {tamperMsg && (
          <div
            className={`mt-3 rounded-lg border p-3 text-xs ${
              tamperMsg.type === "warn"
                ? "border-amber-300 bg-white text-amber-900"
                : "border-emerald-300 bg-white text-emerald-900"
            }`}
          >
            <div className="font-bold">{tamperMsg.title}</div>
            <div className="mt-0.5">{tamperMsg.text}</div>
          </div>
        )}
      </div>

      <ErrorBox error={verifyMut.error || tamperMut.error || restoreMut.error} />

      {/* 3. KẾT QUẢ KIỂM CHỨNG BLOCKCHAIN */}
      {r && (
        <div className="space-y-4">
          <div className={`rounded-xl p-5 text-white shadow-md ${r.overall === "PASS" ? "bg-emerald-600" : "bg-red-600"}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-2xl font-bold">
                {r.overall === "PASS"
                  ? "✔ PASS — DỮ LIỆU TOÀN VẸN 100%"
                  : "✘ FAIL — PHÁT HIỆN CAN THIỆP / SAI LỆCH DỮ LIỆU!"}
              </div>
              <span className="rounded-full bg-white/20 px-3 py-0.5 text-xs font-semibold uppercase tracking-wider">
                Mạng sổ cái: {r.ledgerMode === "evm" ? "Avalanche Fuji / C-Chain" : r.ledgerMode}
              </span>
            </div>

            <div className="mt-2 text-sm opacity-95">
              {r.overall === "PASS" ? (
                <span>
                  Tất cả các bản ghi cảm biến, ảnh kiểm định và chữ ký thiết bị khớp chính xác từng bit với Smart Contract trên Avalanche. Không có dấu hiệu bị can thiệp.
                </span>
              ) : (
                <span className="font-semibold">
                  CẢNH BÁO AN TOÀN CHUỖI CUNG ỨNG: Dữ liệu thực tế trong Database không khớp với bằng chứng mã hóa bất biến được lưu trữ trên Blockchain Avalanche Fuji!
                </span>
              )}
            </div>

            <div className="mt-3 flex flex-wrap gap-4 text-xs font-medium opacity-90">
              <div>Chuỗi hash: {r.chainLinkIntact ? "Liên tục (Intact)" : "BỊ ĐỨT GÃY"}</div>
              <div>Đoạn kiểm tra: {r.segments.length}</div>
              <div>Đoạn sai lệch: <span className={r.segments.filter((s: any) => !s.match).length > 0 ? "underline font-bold" : ""}>{r.segments.filter((s: any) => !s.match).length}</span></div>
              <div>Chữ ký thiết bị sai: <span className={r.signatureFailureCount > 0 ? "underline font-bold" : ""}>{r.signatureFailureCount}</span></div>
              <div>Thời điểm kiểm tra: {r.checkedAt}</div>
            </div>
          </div>

          {/* Bảng phân tích chi tiết từng đoạn sự kiện */}
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-slate-50 text-slate-700">
                  <th className="th">Sự kiện</th>
                  <th className="th">Loại sự kiện</th>
                  <th className="th">Hash trên Smart Contract (Avalanche)</th>
                  <th className="th">Hash tính lại từ dữ liệu DB</th>
                  <th className="th text-center">Kết quả</th>
                  <th className="th">Đánh giá minh bạch</th>
                </tr>
              </thead>
              <tbody>
                {r.segments.map((s: any) => (
                  <tr key={s.eventId} className={`border-b ${s.match ? "" : "bg-red-50/70"}`}>
                    <td className="td font-mono text-xs">{s.eventId}</td>
                    <td className="td font-medium">{EVENT_LABEL[s.type] || s.type}</td>
                    <td className="td"><Hash value={s.onChainDataHash} /></td>
                    <td className="td"><Hash value={s.recomputedHash} /></td>
                    <td className="td text-center text-lg">
                      {s.match ? (
                        <span className="text-emerald-600 font-bold" title="Khớp hoàn hảo">✔</span>
                      ) : (
                        <span className="font-bold text-red-600" title="Sai lệch dữ liệu!">✘</span>
                      )}
                    </td>
                    <td className="td text-xs">
                      {s.match ? (
                        <span className="text-emerald-700">Toàn vẹn</span>
                      ) : (
                        <span className="font-bold text-red-700">
                          {s.type === "INSPECTION"
                            ? "File ảnh đã bị sửa/tráo sau khi ghi sổ cái!"
                            : "Dữ liệu cảm biến trong DB đã bị can thiệp trái phép!"}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Cảnh báo chữ ký cảm biến */}
          {r.signatureFailureCount > 0 && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 shadow-sm">
              <div className="font-bold flex items-center gap-2">
                <span>⚠️ Phát hiện {r.signatureFailureCount} bản ghi cảm biến bị giả mạo chữ ký thiết bị:</span>
              </div>
              <p className="mt-1 text-xs text-red-700">
                Thiết bị IoT đo đạc thực tế ký số từng reading bằng khoá bảo mật. Dữ liệu trong CSDL hiện tại có nội dung khác với lúc thiết bị ký, chứng minh có sự can thiệp trái phép sau khi ghi nhận!
              </p>
              <div className="mt-2 font-mono text-xs text-red-900 bg-red-100/60 p-2 rounded">
                Mốc thời gian vi phạm: {r.signatureFailures.join(", ")}
              </div>
            </div>
          )}

          {r.chainIssues?.length > 0 && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700">
              <b>Vấn đề liên kết chuỗi:</b> {r.chainIssues.map((c: any) => `${c.eventId}: ${c.issue}`).join(" · ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
